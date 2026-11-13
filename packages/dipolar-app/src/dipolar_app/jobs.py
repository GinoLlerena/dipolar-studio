"""The job runner (04 D18, §8.1, D10; M2 step 3).

A job is submitted by a journaled command (``fit.run`` commits ``job.submitted``). The runner is a
session listener: it sees each committed submission, with the science state the command
committed against, and queues the job with that **input snapshot**, an immutable project.
Workers compute outside the session lock and publish the result in two steps:

1. the result is written as an immutable blob, fsynced (``Session.blobs``);
2. ``job.finish`` commits ``job.finished`` with the run that references the blob by SHA-256.

**Exactly one terminal state.** Completion and cancellation both commit through the session. The
first to commit wins; the later one finds the job finished and changes nothing (a cancelled job's
late result is dropped, and its blob is an orphan; cleanup is out of scope for the beta).

**Stale results.** A job that finishes after the science changed still publishes its run, against
its own input identity; the run is reported ``stale`` while the science differs from that input
(compared by science hash, so an undo that restores the exact input makes it current again). It
never overwrites newer state.

**Workers.**
- ``process`` (``dipolar serve``): each job runs in a fresh spawned process. A cancel or a timeout
  terminates it, and a crash fails only that job.
- ``thread`` (tests): the job runs in a worker thread. A cancel cannot interrupt the
  computation; its late result is dropped.

**Budgets (D17).** At most ``MAX_WORKERS`` jobs compute at once and each has ``JOB_TIMEOUT_S``.
The number of unfinished jobs, per actor and in total, is bounded when they are submitted
(``dipolar_app.job_ops``).

**Restart.** Replay never re-runs a job. A job left unfinished by a stopped process is marked
``interrupted`` when the runner starts.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import multiprocessing
import os
import queue
import shutil
import tempfile
import threading
import time
from dataclasses import dataclass, field
from multiprocessing.connection import wait as wait_for_objects
from multiprocessing.process import BaseProcess
from typing import Any, Literal

from dipolar_app.errors import OperationError
from dipolar_app.policy import Principal, Tier
from dipolar_app.project import Project
from dipolar_app.session import JOB, TERMINAL, Event, Session, SessionState

LOG = logging.getLogger("dipolar_app.jobs")
MAX_WORKERS = 2
JOB_TIMEOUT_S = 600.0
#: The runner's own identity in the journal (it records terminal states, never science).
SYSTEM = Principal(actor="system:jobs", tier=Tier.ADMIN, human=False)

Mode = Literal["process", "thread"]


def now_iso() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


def compute(kind: str, project_json: str, options: dict[str, Any], revision: int, science_hash: str) -> dict[str, Any]:
    """Compute one job from its input snapshot. Raises ``OperationError`` for a reported failure."""
    if kind != "fit":
        raise ValueError(f"unknown job kind {kind!r}")
    from dipolar_app.science_ops import compute_fit

    project = Project.model_validate_json(project_json)
    result = compute_fit(project, bool(options.get("intervals", False)), revision, science_hash)
    return result.model_dump(mode="json")


def _child(input_path: str, path: str) -> None:
    """The entry point of a worker process. It reads its input from ``input_path`` (so starting it
    sends only two short paths through the spawn pipe, round 34), writes its outcome to ``path``
    and exits; the parent reads the file only after the process has exited, so a partial write
    can never block it (round 33)."""
    try:
        with open(input_path, encoding="utf-8") as handle:
            kind, project_json, options, revision, science_hash = json.load(handle)
        outcome: list[Any] = ["ok", compute(kind, project_json, options, revision, science_hash)]
    except OperationError as exc:
        outcome = ["error", exc.code.value, exc.message]
    except BaseException as exc:  # reported to the parent, which fails the job
        outcome = ["error", "INTERNAL", f"the computation failed ({type(exc).__name__})"]
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(outcome, handle, allow_nan=False)


#: The largest outcome file the parent reads (a fit result is tens of kilobytes; round 34).
MAX_OUTCOME_BYTES = 16 << 20


def _read_outcome(path: str, exitcode: int | None) -> Outcome:
    try:
        if os.path.getsize(path) > MAX_OUTCOME_BYTES:
            return ("error", "INTERNAL", f"the worker's result exceeds {MAX_OUTCOME_BYTES} bytes")
        with open(path, encoding="utf-8") as handle:
            message = json.load(handle)
    except (OSError, ValueError):
        return ("error", "INTERNAL", f"the worker process exited without a result (code {exitcode})")
    if isinstance(message, list) and message[:1] == ["ok"] and len(message) == 2 and isinstance(message[1], dict):
        return ("ok", message[1])
    if isinstance(message, list) and len(message) == 3 and message[0] == "error":
        return ("error", str(message[1]), str(message[2]))
    return ("error", "INTERNAL", "the worker process returned a malformed result")


def _stop(process: BaseProcess) -> None:
    """Terminate, then kill, a worker that has not exited; never wait without a bound."""
    if process.pid is None:
        return  # it never started
    if process.is_alive():
        process.terminate()
        process.join(2)
    if process.is_alive():
        process.kill()
        process.join(2)


@dataclass
class _Task:
    job_id: str
    kind: str
    project_json: str
    options: dict[str, Any]
    revision: int
    science_hash: str
    cancel: threading.Event = field(default_factory=threading.Event)


Outcome = tuple[Literal["ok"], dict[str, Any]] | tuple[Literal["error"], str, str] | tuple[Literal["cancelled"]]


class JobRunner:
    def __init__(self, session: Session, *, mode: Mode = "process", workers: int = MAX_WORKERS) -> None:
        self.session = session
        self.mode = mode
        self._queue: queue.Queue[_Task | None] = queue.Queue()
        self._tasks: dict[str, _Task] = {}
        self._lock = threading.Lock()
        self._threads = [
            threading.Thread(target=self._work, name=f"job-worker-{i}", daemon=True) for i in range(workers)
        ]
        self._closed = False
        self._started = False
        session.add_listener(self._on_commit)
        self._interrupt_unfinished()

    # ------------------------------------------------------------------ session side
    def _on_commit(self, state: SessionState, events: list[Event]) -> None:
        """Queue each submitted job with its input snapshot; flag each cancelled one."""
        for event in events:
            if event["domain"] != JOB:
                continue
            if event["type"] == "job.submitted":
                data = event["job"]
                assert state.project is not None and state.science_hash == data["science_hash"]
                task = _Task(
                    data["id"],
                    data["kind"],
                    state.project.model_dump_json(),
                    dict(data["options"]),
                    data["science_revision"],
                    data["science_hash"],
                )
                with self._lock:
                    self._tasks[task.job_id] = task
                    if not self._started:  # workers start with the first job
                        self._started = True
                        for t in self._threads:
                            t.start()
                self._queue.put(task)
            elif event["type"] == "job.finished":
                with self._lock:
                    found = self._tasks.get(event["id"])
                if found is not None:
                    found.cancel.set()

    def _interrupt_unfinished(self) -> None:
        for job in self.session.state.jobs:
            if job.status not in TERMINAL:
                self.finish(job.id, "interrupted", error=("INTERRUPTED", "the server stopped before the job finished"))

    def finish(
        self,
        job_id: str,
        status: str,
        *,
        result: dict[str, Any] | None = None,
        error: tuple[str, str] | None = None,
    ) -> bool:
        """Commit the job's terminal state, unless it already has one. Returns whether it did."""
        digest = self.session.blobs.put(result) if result is not None else None  # durable first

        def plan(state: SessionState) -> tuple[list[Event], None]:
            job = state.job(job_id)
            if job is None or job.status in TERMINAL:
                return [], None  # cancelled (or finished) first: this outcome is dropped
            event: Event = {
                "type": "job.finished",
                "domain": JOB,
                "id": job_id,
                "status": status,
                "at": now_iso(),
                "error": {"code": error[0], "message": error[1]} if error else None,
                "run": {"id": f"run_{state.next_run:06d}", "job_id": job_id, "result_sha256": digest}
                if digest is not None
                else None,
            }
            return [event], None

        before = self.session.state.seq
        self.session.commit(SYSTEM, "job.finish", {"job_id": job_id, "status": status}, plan)
        return self.session.state.seq != before

    # ------------------------------------------------------------------ workers
    def _work(self) -> None:
        while True:
            task = self._queue.get()
            if task is None:
                return
            try:
                self._run(task)
            except Exception:  # infrastructure failure: the job fails, the worker lives on (round 33)
                LOG.exception("job %s: infrastructure failure", task.job_id)
                try:
                    self.finish(task.job_id, "failed", error=("INTERNAL", "the job could not be run or published"))
                except Exception:
                    LOG.exception("job %s: could not record the failure", task.job_id)
            finally:
                with self._lock:
                    self._tasks.pop(task.job_id, None)
                self.session.set_live(task.job_id, None)

    def _run(self, task: _Task) -> None:
        if task.cancel.is_set() or self._closed:
            return
        self.session.set_live(task.job_id, "running")
        outcome = self._execute(task)
        if self._closed:
            return  # shutting down: the next start records the job as interrupted
        try:
            if outcome[0] == "ok":
                self.finish(task.job_id, "succeeded", result=outcome[1])
            elif outcome[0] == "error":
                self.finish(task.job_id, "failed", error=(outcome[1], outcome[2]))
        except OperationError:
            pass  # the session stopped accepting commands (journal failure): fail-stop
        # Any other exception (a blob write that fails, say) reaches _work, which fails the job.

    def _execute(self, task: _Task) -> Outcome:
        args = (task.kind, task.project_json, task.options, task.revision, task.science_hash)
        if self.mode == "thread":
            try:
                result = compute(*args)
            except OperationError as exc:
                return ("error", exc.code.value, exc.message)
            except Exception as exc:
                return ("error", "INTERNAL", f"the computation failed ({type(exc).__name__})")
            return ("cancelled",) if task.cancel.is_set() else ("ok", result)
        workdir = tempfile.mkdtemp(prefix="dipolar-job-")  # private: mode 0700
        input_path, path = os.path.join(workdir, "input.json"), os.path.join(workdir, "outcome.json")
        with open(input_path, "w", encoding="utf-8") as handle:
            json.dump(list(args), handle)
        process = multiprocessing.get_context("spawn").Process(target=_child, args=(input_path, path), daemon=True)
        deadline = time.monotonic() + JOB_TIMEOUT_S
        try:
            process.start()
            while True:
                # Never blocks longer than the poll interval: cancel, timeout and shutdown are
                # always observed (round 33).
                if wait_for_objects([process.sentinel], timeout=0.05):
                    process.join()
                    return _read_outcome(path, process.exitcode)
                if task.cancel.is_set() or self._closed:
                    return ("cancelled",)
                if time.monotonic() > deadline:
                    return ("error", "TIMEOUT", f"the job exceeded its {JOB_TIMEOUT_S:.0f} s budget")
        finally:
            _stop(process)
            shutil.rmtree(workdir, ignore_errors=True)

    def close(self) -> None:
        """Stop the workers; running processes are terminated. Unfinished jobs stay unfinished in
        the journal and are recorded as interrupted at the next start."""
        self._closed = True
        with self._lock:
            for task in self._tasks.values():
                task.cancel.set()
        if not self._started:
            return
        for _ in self._threads:
            self._queue.put(None)
        for t in self._threads:
            t.join(10)
