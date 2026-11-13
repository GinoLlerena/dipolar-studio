"""The headless session (04 D14, D15, §8.1, §8.2).

State is immutable and replaced atomically under a single writer lock. Four counters stay
separate: the journal sequence, the science revision (advanced only by science events), the
workspace revision (view only) and, later, job status. Proposals have their own event domain and
advance neither revision.

A command runs as ``session.commit(plan)``: under the lock, ``plan(state)`` validates against
the current state and returns the events and the result. The events are written to the journal
(fsynced) **before** they are applied in memory and acknowledged. Replay applies recorded events
and never re-runs computations.

One journal record is one transaction. It holds one or more **steps** (an accepted proposal has
one per accepted command), and each step advances the revisions of the domains it touches, so a
proposal's chain of ``expected_science_revision`` values replays exactly. The record is still
written as one line with one checksum, so it is applied entirely or not at all (M2 step 2).

**Idempotency (§8.1).** A command may carry a ``request_id``. The record stores the request ID and
its outcome, so the deduplication table is rebuilt by replay: a retry after a lost response, or
after a restart, returns the stored outcome and is never applied twice. Keys are scoped to the
actor; reusing a key for a different command is refused.

**Jobs and runs (§8.1, D11, D18; M2 step 3).** Jobs live in the ``job`` domain, which advances
neither revision: ``job.submitted`` records the input identity (science revision and hash) and
``job.finished`` the one terminal state, with the run it produced. A run's result is an immutable
blob, written and fsynced before the record that references it by SHA-256 (``BlobStore``).
Replay never re-runs a job. After commit, listeners (the job runner) see the new state and its
events; a dry run reaches no listener, so it never launches a job.

**Undo (§8.2).** The science history is global and chronological. Every record that changes the
science pushes one undo entry (the project before it); ``history.undo`` and ``history.redo`` are
new, journaled commands whose events say which way they move, so revisions never decrease and
replay rebuilds the stacks.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import os
import threading
import uuid
from collections import deque
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Literal, TypeVar

from dipolar_core.context import numerical_context
from pydantic import BaseModel

from dipolar_app.errors import ErrorCode, OperationError
from dipolar_app.journal import JOURNAL_SCHEMA_VERSION, Journal, JournalCorrupt, Recovery, fsync_dir
from dipolar_app.policy import Principal
from dipolar_app.project import (
    PROJECT_SCHEMA_VERSION,
    Project,
    canonical_json,
    content_hash,
    migrate_project,
    payload_hash,
    science_hash,
)

T = TypeVar("T")

SCIENCE, WORKSPACE, PROPOSAL, JOB = "science", "workspace", "proposal", "job"
DOMAINS = frozenset({SCIENCE, WORKSPACE, PROPOSAL, JOB})

#: Undo depth: the oldest entries are dropped beyond this.
MAX_UNDO = 100
#: Decided proposals kept in the state for listing; pending ones are always kept.
MAX_DECIDED_PROPOSALS = 64
#: Finished jobs and runs kept in the state; unfinished jobs are always kept.
MAX_FINISHED_JOBS = 64
MAX_RUNS = 64
#: Change-feed entries kept in memory for the event stream; a client further behind resyncs.
FEED_SIZE = 1000

HistoryKind = Literal["do", "undo", "redo"]
ProposalStatus = Literal["pending", "accepted", "rejected", "expired"]
JobStatus = Literal["queued", "succeeded", "failed", "cancelled", "interrupted"]
TERMINAL: frozenset[str] = frozenset({"succeeded", "failed", "cancelled", "interrupted"})


Vec3 = tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class Camera:
    """A perspective camera, as the browser's (04 §8.4): positions in Å, angles in degrees."""

    position: Vec3
    target: Vec3
    up: Vec3
    fov_deg: float  # vertical field of view
    near: float
    far: float

    def to_json(self) -> dict[str, Any]:
        return {
            "position": list(self.position),
            "target": list(self.target),
            "up": list(self.up),
            "fov_deg": self.fov_deg,
            "near": self.near,
            "far": self.far,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Camera:
        return cls(
            position=_vec(data["position"]),
            target=_vec(data["target"]),
            up=_vec(data["up"]),
            fov_deg=float(data["fov_deg"]),
            near=float(data["near"]),
            far=float(data["far"]),
        )


def _vec(values: Sequence[float]) -> Vec3:
    x, y, z = (float(v) for v in values)
    return (x, y, z)


@dataclass(frozen=True, slots=True)
class Layers:
    labels: bool = True
    bonds: bool = True
    couplings: bool = True


@dataclass(frozen=True, slots=True)
class ViewState:
    """Shared view state (D15). The beta has a single shared view."""

    selection: tuple[str, ...] = ()
    highlights: tuple[str, ...] = ()
    camera: Camera | None = None  # None: fit the molecule in view automatically
    viewport: tuple[int, int] = (800, 600)  # width, height in pixels
    layers: Layers = field(default_factory=Layers)


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    """One undoable (or redoable) science change."""

    project: Project  # the project that undoing (or redoing) restores
    operation: str  # the command that made the change
    actor: str
    science_revision: int  # the science revision the change produced


@dataclass(frozen=True, slots=True)
class ProposalStep:
    operation: str
    args_json: str  # canonical JSON of the validated arguments (immutable, and its size is known)
    depends_on: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class Proposal:
    id: str
    proposer: str
    created_at: str  # ISO 8601, UTC
    expires_at: str
    base_science_revision: int
    note: str
    steps: tuple[ProposalStep, ...]
    status: ProposalStatus = "pending"
    decided_by: str | None = None
    decided_at: str | None = None
    accepted_steps: tuple[int, ...] = ()
    reason: str = ""

    @property
    def size(self) -> int:
        return sum(len(s.args_json.encode()) for s in self.steps)


@dataclass(frozen=True, slots=True)
class Job:
    """A unit of long-running work (D18). Its input is the science state at submission."""

    id: str
    kind: str  # "fit"
    owner: str  # the actor that committed the submission
    proposed_by: str | None  # the proposer, when a human accepted it from a proposal
    submitted_at: str
    science_revision: int
    science_hash: str
    input_hash: str  # D11 canonical hash: science, options, solver version, numerical context
    options_json: str
    status: JobStatus = "queued"
    finished_at: str | None = None
    run_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    # The input's content hash (project.content_hash), derived when the submission is applied (not
    # journaled); None if it could not be derived, and staleness then compares science_hash.
    content_hash: str | None = None


@dataclass(frozen=True, slots=True)
class Run:
    """An immutable result (D11), published against the input identity of its job."""

    id: str
    job_id: str
    kind: str
    owner: str
    created_at: str
    science_revision: int
    science_hash: str
    input_hash: str
    result_sha256: str
    content_hash: str | None = None  # the job's (see Job.content_hash)


class CurrentScience:
    """The current state's identities, each hashed at most once (listing many jobs or runs)."""

    def __init__(self, state: SessionState) -> None:
        self._state = state
        self._science: str | None = None
        self._content: str | None = None

    @property
    def science(self) -> str:
        if self._science is None:
            self._science = self._state.science_hash
        return self._science

    @property
    def content(self) -> str:
        if self._content is None:
            self._content = self._state.content_hash
        return self._content

    def is_stale(self, item: Job | Run) -> bool:
        """Whether the science differs from a job's or run's input, by content (the owner's
        decision after M3 step 1): an undo that restores the exact input makes it current again."""
        if item.content_hash is not None:
            return item.content_hash != self.content
        return item.science_hash != self.science


@dataclass(frozen=True, slots=True)
class SessionState:
    project: Project | None = None
    view: ViewState = field(default_factory=ViewState)
    seq: int = 0
    science_revision: int = 0
    workspace_revision: int = 0
    undo: tuple[HistoryEntry, ...] = ()  # oldest first
    redo: tuple[HistoryEntry, ...] = ()  # the next redo last
    proposals: tuple[Proposal, ...] = ()  # in the order of their last event (creation or decision)
    next_proposal: int = 1
    jobs: tuple[Job, ...] = ()  # in the order of their last event (submission or finish)
    next_job: int = 1
    runs: tuple[Run, ...] = ()  # oldest first
    next_run: int = 1

    @property
    def science_hash(self) -> str:
        return science_hash(self.project)

    @property
    def content_hash(self) -> str:
        return content_hash(self.project)

    def proposal(self, proposal_id: str) -> Proposal | None:
        return next((p for p in self.proposals if p.id == proposal_id), None)

    def job(self, job_id: str) -> Job | None:
        return next((j for j in self.jobs if j.id == job_id), None)

    def run(self, run_id: str) -> Run | None:
        return next((r for r in self.runs if r.id == run_id), None)


Event = dict[str, Any]


class Steps(tuple[list[Event], ...]):
    """A plan's events split into steps (each advances the revisions of its domains)."""

    __slots__ = ()


Plan = Callable[[SessionState], tuple["list[Event] | Steps", T]]


def as_steps(events: list[Event] | Steps) -> list[list[Event]]:
    if isinstance(events, Steps):
        return [list(step) for step in events if step]
    return [list(events)] if events else []


def _proposal_from_event(data: dict[str, Any]) -> Proposal:
    steps = tuple(
        ProposalStep(operation=s["operation"], args_json=canonical_json(s["args"]), depends_on=tuple(s["depends_on"]))
        for s in data["steps"]
    )
    return Proposal(
        id=data["id"],
        proposer=data["proposer"],
        created_at=data["created_at"],
        expires_at=data["expires_at"],
        base_science_revision=data["base_science_revision"],
        note=data["note"],
        steps=steps,
    )


def _prune(proposals: tuple[Proposal, ...]) -> tuple[Proposal, ...]:
    decided = [p.id for p in proposals if p.status != "pending"]
    dropped = set(decided[: max(0, len(decided) - MAX_DECIDED_PROPOSALS)])
    return tuple(p for p in proposals if p.id not in dropped)


def apply_event(state: SessionState, event: Event) -> SessionState:
    """Pure state transition for one event. Unknown event types are an error, never skipped."""
    kind = event["type"]
    if kind == "project.replaced":
        project = Project.model_validate(migrate_project(event["project"]))
        return replace(state, project=project)
    if kind == "view.selection_set":
        return replace(state, view=replace(state.view, selection=tuple(event["selection"])))
    if kind == "view.highlights_set":
        return replace(state, view=replace(state.view, highlights=tuple(event["highlights"])))
    if kind == "view.camera_set":
        camera = Camera.from_json(event["camera"]) if event["camera"] is not None else None
        width, height = event["viewport"]
        return replace(state, view=replace(state.view, camera=camera, viewport=(int(width), int(height))))
    if kind == "view.layers_set":
        return replace(state, view=replace(state.view, layers=Layers(**event["layers"])))
    if kind == "proposal.created":
        proposal = _proposal_from_event(event["proposal"])
        if proposal.id != f"prp_{state.next_proposal:06d}":
            raise ValueError(f"proposal {proposal.id!r} out of sequence")
        return replace(state, proposals=(*state.proposals, proposal), next_proposal=state.next_proposal + 1)
    if kind == "proposal.decided":
        target = state.proposal(event["id"])
        if target is None or target.status != "pending":
            raise ValueError(f"proposal {event['id']!r} is not pending")
        status = event["status"]
        if status not in ("accepted", "rejected", "expired"):
            raise ValueError(f"unknown proposal status {status!r}")
        decided = replace(
            target,
            status=status,
            decided_by=event["by"],
            decided_at=event["at"],
            accepted_steps=tuple(event["accepted_steps"]),
            reason=event["reason"],
        )
        # A decided proposal moves to the end, so the decided ones stay in decision order and
        # pruning drops the earliest decisions.
        proposals = (*(p for p in state.proposals if p.id != target.id), decided)
        return replace(state, proposals=_prune(proposals))
    if kind == "job.submitted":
        data = event["job"]
        if data["id"] != f"job_{state.next_job:06d}":
            raise ValueError(f"job {data['id']!r} out of sequence")
        job = Job(
            id=data["id"],
            kind=data["kind"],
            owner=data["owner"],
            proposed_by=data["proposed_by"],
            submitted_at=data["submitted_at"],
            science_revision=data["science_revision"],
            science_hash=data["science_hash"],
            input_hash=data["input_hash"],
            options_json=canonical_json(data["options"]),
            # The submission is applied to the state the job computes from, so its content can be
            # derived here, also on replay; checked against the recorded hash to be sure.
            content_hash=state.content_hash if state.science_hash == data["science_hash"] else None,
        )
        return replace(state, jobs=(*state.jobs, job), next_job=state.next_job + 1)
    if kind == "job.finished":
        return _finish_job(state, event)
    raise ValueError(f"unknown event type {kind!r}")


def _finish_job(state: SessionState, event: Event) -> SessionState:
    target = state.job(event["id"])
    if target is None or target.status in TERMINAL:
        raise ValueError(f"job {event['id']!r} is not running")
    status = event["status"]
    if status not in TERMINAL:
        raise ValueError(f"unknown job status {status!r}")
    run_data = event.get("run")
    if (status == "succeeded") != (run_data is not None):
        raise ValueError("a succeeded job, and only a succeeded job, publishes a run")
    error = event.get("error")
    runs, next_run, run_id = state.runs, state.next_run, None
    if run_data is not None:
        if run_data["id"] != f"run_{state.next_run:06d}" or run_data["job_id"] != target.id:
            raise ValueError(f"run {run_data['id']!r} out of sequence")
        run = Run(
            id=run_data["id"],
            job_id=target.id,
            kind=target.kind,
            owner=target.owner,
            created_at=event["at"],
            science_revision=target.science_revision,
            science_hash=target.science_hash,
            input_hash=target.input_hash,
            result_sha256=run_data["result_sha256"],
            content_hash=target.content_hash,
        )
        runs, next_run, run_id = (*state.runs, run)[-MAX_RUNS:], next_run + 1, run.id
    finished = replace(
        target,
        status=status,
        finished_at=event["at"],
        run_id=run_id,
        error_code=error["code"] if error else None,
        error_message=error["message"] if error else None,
    )
    jobs = (*(j for j in state.jobs if j.id != target.id), finished)
    done = [j.id for j in jobs if j.status in TERMINAL]
    dropped = set(done[: max(0, len(done) - MAX_FINISHED_JOBS)])
    jobs = tuple(j for j in jobs if j.id not in dropped)
    return replace(state, jobs=jobs, runs=runs, next_run=next_run)


def _history_kind(steps: Sequence[Sequence[Event]]) -> HistoryKind | None:
    kinds = {e.get("history", "do") for step in steps for e in step if e["domain"] == SCIENCE}
    if not kinds:
        return None
    if len(kinds) > 1 or not kinds <= {"do", "undo", "redo"}:
        raise ValueError(f"a transaction mixes history kinds {sorted(kinds)}")
    kind: HistoryKind = kinds.pop()
    return kind


def apply_record(state: SessionState, steps: Sequence[Sequence[Event]], *, operation: str, actor: str) -> SessionState:
    """Apply one transaction: its steps in order, then one journal sequence number and, if it
    changed the science, one history entry."""
    before = state
    for step in steps:
        domains = set()
        for event in step:
            if event.get("domain") not in DOMAINS:
                raise ValueError(f"unknown event domain {event.get('domain')!r}")
            state = apply_event(state, event)
            domains.add(event["domain"])
        state = replace(
            state,
            science_revision=state.science_revision + (SCIENCE in domains),
            workspace_revision=state.workspace_revision + (WORKSPACE in domains),
        )
    state = replace(state, seq=state.seq + 1)
    kind = _history_kind(steps)
    if kind is None:
        return state
    if kind == "do":
        undo = state.undo
        if before.project is not None:  # opening the first project is not undoable
            entry = HistoryEntry(before.project, operation, actor, state.science_revision)
            undo = (*undo, entry)[-MAX_UNDO:]
        return replace(state, undo=undo, redo=())
    if kind == "undo":
        if not state.undo:
            raise ValueError("an undo with nothing to undo")
        undone = state.undo[-1]
        assert before.project is not None  # an undo entry exists only after a project
        redo_entry = HistoryEntry(before.project, undone.operation, undone.actor, undone.science_revision)
        return replace(state, undo=state.undo[:-1], redo=(*state.redo, redo_entry))
    if not state.redo:
        raise ValueError("a redo with nothing to redo")
    redone = state.redo[-1]
    assert before.project is not None
    undo_entry = HistoryEntry(before.project, redone.operation, redone.actor, state.science_revision)
    return replace(state, undo=(*state.undo, undo_entry)[-MAX_UNDO:], redo=state.redo[:-1])


def apply_transaction(state: SessionState, events: Iterable[Event]) -> SessionState:
    """One single-step transaction (kept for callers that build states by hand)."""
    events = list(events)
    return apply_record(state, [events] if events else [], operation="", actor="")


def request_fingerprint(operation: str, args: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(canonical_json({"operation": operation, "args": args}).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class StoredOutcome:
    """The acknowledged outcome of a request, returned again for a retry with the same key."""

    fingerprint: str
    operation: str
    result: dict[str, Any]
    revisions: dict[str, int]


@dataclass(frozen=True, slots=True)
class Committed[R]:
    """What ``Session.commit`` did: the result and the state it produced (for a dry run, the state
    it *would* produce), or the stored outcome of an earlier request with the same key."""

    result: R | None
    before: SessionState
    state: SessionState
    replayed: StoredOutcome | None = None


class BlobStore:
    """Immutable, content-addressed result blobs (D11, §8.2). With a directory, a blob is written
    to a temporary file, fsynced and renamed before anything references it; without one (tests),
    blobs live in memory."""

    def __init__(self, directory: Path | None) -> None:
        self.directory = directory
        self._memory: dict[str, str] = {}
        self._mkdir_lock = threading.Lock()

    def put(self, data: dict[str, Any]) -> str:
        text = canonical_json(data)
        digest = hashlib.sha256(text.encode()).hexdigest()
        if self.directory is None:
            self._memory[digest] = text
            return digest
        target = self.directory / f"{digest}.json"
        if self.text(digest) == text:
            return digest  # already stored intact; a damaged file is rewritten below (round 33)
        with self._mkdir_lock:  # one creator; the others wait until the directory is durable (round 34)
            if not self.directory.exists():
                self.directory.mkdir(mode=0o700)
                fsync_dir(self.directory.parent)  # the new directory itself is durable (round 33)
        tmp = self.directory / f".{digest}.{uuid.uuid4().hex}.tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            view = memoryview(text.encode())
            while view:
                written = os.write(fd, view)
                if written <= 0:
                    raise OSError("blob write stored no bytes")
                view = view[written:]
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(tmp, target)
        fsync_dir(self.directory)
        return digest

    def collect(self, keep: set[str]) -> int:
        """Delete every blob not in ``keep``, and any leftover temporary file. Returns how many
        files were removed.

        Called only when the session opens, under the project lock, after replay. No other writer
        can be publishing then. ``keep`` is the set of blobs the state's runs reference; replay
        and ``run.get`` need no others. That covers a pruned run's blob (``run.get`` cannot
        reach it), and a late result dropped after a cancel or a journal failure (no run
        references it)."""
        if self.directory is None or not self.directory.is_dir():
            return 0
        removed = 0
        for path in self.directory.iterdir():
            stale_tmp = path.name.startswith(".") and path.name.endswith(".tmp")
            orphan = path.suffix == ".json" and not path.name.startswith(".") and path.stem not in keep
            if path.is_file() and (stale_tmp or orphan):
                path.unlink()
                removed += 1
        if removed:
            fsync_dir(self.directory)
        return removed

    def text(self, digest: str) -> str | None:
        """The blob's text if it exists and matches its digest, else None."""
        if self.directory is None:
            return self._memory.get(digest)
        path = self.directory / f"{digest}.json"
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):  # missing, unreadable or not even UTF-8: damaged (round 34)
            return None
        return text if hashlib.sha256(text.encode()).hexdigest() == digest else None


Listener = Callable[[SessionState, list[Event]], None]


class Session:
    def __init__(self, journal: Journal | None = None, *, contract_version: str) -> None:
        self._lock = threading.Lock()
        self._state = SessionState()
        self._requests: dict[tuple[str, str], StoredOutcome] = {}
        self._journal = journal
        self._contract_version = contract_version
        self._failure: str | None = None
        self._listeners: list[Listener] = []
        self._changed = threading.Condition()
        self._feed: deque[tuple[int, dict[str, Any]]] = deque(maxlen=FEED_SIZE)
        self._cursor = 0
        self._live: dict[str, str] = {}  # job ID -> "running" (not journaled)
        #: Names this process's session for event-stream clients (a restart starts a new feed).
        self.boot_id = uuid.uuid4().hex
        self.blobs = BlobStore(journal.path.parent / "runs" if journal is not None else None)
        #: What opening the journal repaired (an unacknowledged torn tail), if anything.
        self.recovery: Recovery | None = None
        self.collected = 0
        if journal is not None:
            self.recovery = journal.recover_torn_tail()
            self._state, self._requests = replay_full(journal)
            for run in self._state.runs:  # fsynced before its record: a missing blob is damage
                if self.blobs.text(run.result_sha256) is None:
                    raise JournalCorrupt(f"{run.id}: its result blob is missing or damaged")
            #: Blobs removed when the session opened: those no run in the state references.
            self.collected = self.blobs.collect({run.result_sha256 for run in self._state.runs})

    # ------------------------------------------------------------------ observation
    def add_listener(self, listener: Listener) -> None:
        """Called after every applied commit, under the writer lock, with the new state and the
        committed events. Listeners must be quick and must not commit."""
        self._listeners.append(listener)

    def wait_for(self, predicate: Callable[[SessionState], bool], timeout: float) -> SessionState:
        """Block until ``predicate(state)`` holds or ``timeout`` seconds pass; return the state."""
        with self._changed:
            self._changed.wait_for(lambda: predicate(self._state), timeout=max(0.0, timeout))
            return self._state

    def live_status(self, job_id: str) -> str | None:
        return self._live.get(job_id)

    def set_live(self, job_id: str, status: str | None) -> None:
        """Record a job's unjournaled progress (``running``) and announce it on the feed."""
        with self._changed:
            if status is None:
                self._live.pop(job_id, None)
                self._changed.notify_all()
                return
            job = self._state.job(job_id)
            if job is None or job.status in TERMINAL:
                return  # a finished (e.g. cancelled) job never goes back to "running" (round 34)
            self._live[job_id] = status
            self._publish({"kind": "job", "job_id": job_id, "status": status})

    def _publish(self, item: dict[str, Any]) -> None:  # call with self._changed held
        self._cursor += 1
        self._feed.append((self._cursor, item))
        self._changed.notify_all()

    def feed_after(self, cursor: int, timeout: float) -> tuple[list[tuple[int, dict[str, Any]]], int, bool]:
        """Feed entries after ``cursor`` (waiting up to ``timeout`` for one), the latest cursor,
        and whether the client must resync because entries it missed were dropped."""
        with self._changed:
            self._changed.wait_for(lambda: self._cursor > cursor, timeout=max(0.0, timeout))
            oldest = self._feed[0][0] if self._feed else self._cursor + 1
            if cursor > self._cursor or cursor + 1 < oldest:
                return [], self._cursor, cursor != self._cursor
            return [(c, item) for c, item in self._feed if c > cursor], self._cursor, False

    @property
    def cursor(self) -> int:
        return self._cursor

    def snapshot(self) -> tuple[SessionState, int]:
        """The state and the feed cursor that follows it, taken together."""
        with self._changed:
            return self._state, self._cursor

    @property
    def state(self) -> SessionState:
        """A consistent snapshot. Queries compute from it outside the lock."""
        return self._state

    @property
    def failed(self) -> str | None:
        """Why the session stopped accepting commands, or None while it is healthy."""
        return self._failure

    def commit(
        self,
        principal: Principal,
        operation: str,
        args: dict[str, Any],
        plan: Plan[T],
        *,
        request_id: str | None = None,
        dry_run: bool = False,
    ) -> Committed[T]:
        """Plan, journal, then apply, atomically.

        - ``request_id``: a retry of an acknowledged request returns its stored outcome
          (``Committed.replayed``) and changes nothing; the same key with other arguments is
          refused. A request is recorded even when it changes nothing, so its retry stays a no-op.
        - ``dry_run``: plan and apply in memory only. Nothing is journaled, stored or acknowledged
          as done, and no revision is consumed.

        Fail-stop: if the journal append raises, the outcome on disk is uncertain (the record may
        or may not be durable). The in-memory state is left unchanged and **every later command is
        refused** until the process restarts and replays the journal, which is the source of truth.
        Queries keep working on the last acknowledged state.
        """
        if dry_run and request_id is not None:
            raise ValueError("a dry run is never recorded, so it takes no request_id")
        with self._lock:
            if self._failure is not None:
                raise OperationError(
                    ErrorCode.JOURNAL_FAILED,
                    "the session stopped accepting commands after a journal failure",
                    hint="restart dipolar serve; it replays the journal, which is the source of truth",
                    details={"cause": self._failure},
                )
            current = self._state
            fingerprint = request_fingerprint(operation, args)
            if request_id is not None:
                stored = self._requests.get((principal.actor, request_id))
                if stored is not None:
                    if stored.fingerprint != fingerprint:
                        raise OperationError(
                            ErrorCode.IDEMPOTENCY_KEY_REUSED,
                            f"request_id {request_id!r} was already used for a different command",
                            offending_field="request_id",
                            hint="use a new request_id for each distinct command; reuse it only to retry",
                            details={"operation": stored.operation},
                        )
                    return Committed(None, current, current, replayed=stored)
            planned, result = plan(current)
            steps = as_steps(planned)
            if not steps and request_id is None:
                return Committed(result, current, current)
            new_state = apply_record(current, steps, operation=operation, actor=principal.actor)
            if dry_run:
                return Committed(result, current, new_state)
            revisions = {SCIENCE: new_state.science_revision, WORKSPACE: new_state.workspace_revision}
            outcome: StoredOutcome | None = None
            if request_id is not None:
                if not isinstance(result, BaseModel):
                    raise TypeError(f"{operation}: a recorded request needs a model result")
                outcome = StoredOutcome(fingerprint, operation, result.model_dump(mode="json"), revisions)
            if self._journal is not None:
                events = [e for step in steps for e in step]
                record: dict[str, Any] = {
                    "journal_schema": JOURNAL_SCHEMA_VERSION,
                    "project_schema": PROJECT_SCHEMA_VERSION,
                    "contract_version": self._contract_version,
                    "seq": new_state.seq,
                    "txn_id": uuid.uuid4().hex,
                    "timestamp": dt.datetime.now(dt.UTC).isoformat(),
                    "actor": principal.actor,
                    "tier": principal.tier.value,
                    "operation": operation,
                    "args": args,
                    "events": events,
                    "revisions": revisions,
                    "numerical_context": numerical_context(),
                    "science_hash": new_state.science_hash,
                }
                if len(steps) != 1:
                    record["step_lengths"] = [len(step) for step in steps]
                if outcome is not None:
                    record["request"] = {"id": request_id, "outcome": outcome.result}
                try:
                    self._journal.append(record)
                except Exception as exc:
                    self._failure = f"{type(exc).__name__}: {exc}"
                    raise OperationError(
                        ErrorCode.JOURNAL_FAILED,
                        "the journal write failed; whether this command was recorded is uncertain",
                        hint="restart dipolar serve and read the state before retrying",
                        details={"cause": self._failure},
                    ) from exc
            if outcome is not None:
                assert request_id is not None
                self._requests[(principal.actor, request_id)] = outcome
            events = [e for step in steps for e in step]
            # The state and its feed entry change together, so a subscriber's (state, cursor)
            # snapshot never misses a commit (round 33).
            with self._changed:
                self._state = new_state
                for listener in self._listeners:
                    listener(new_state, events)
                self._publish(
                    {
                        "kind": "commit",
                        "seq": new_state.seq,
                        "operation": operation,
                        "actor": principal.actor,
                        "revisions": revisions,
                        "domains": sorted({e["domain"] for e in events}),
                        "jobs": [
                            {
                                "job_id": e["job"]["id"] if e["type"] == "job.submitted" else e["id"],
                                "status": "queued" if e["type"] == "job.submitted" else e["status"],
                            }
                            for e in events
                            if e["type"] in ("job.submitted", "job.finished")
                        ],
                    }
                )
            return Committed(result, current, new_state)


def _record_schema(record: dict[str, Any], previous: int) -> int:
    """The record's project schema, validated (round 24). The metadata cannot choose a hash rule
    on its own:
    - it is a supported integer;
    - it never decreases along the journal;
    - every project payload in the record carries the same schema version.
    """
    seq = record.get("seq")
    version = record.get("project_schema")
    if not isinstance(version, int) or isinstance(version, bool) or not 1 <= version <= PROJECT_SCHEMA_VERSION:
        raise JournalCorrupt(f"record seq {seq}: unsupported project_schema {version!r}")
    if version < previous:
        raise JournalCorrupt(f"record seq {seq}: project_schema {version} follows a record written under {previous}")
    for event in record["events"]:
        if event.get("type") == "project.replaced":
            payload = event.get("project")
            if not isinstance(payload, dict) or payload.get("schema_version") != version:
                raise JournalCorrupt(f"record seq {seq}: a project payload does not match project_schema {version}")
    return version


def _recorded_hash(version: int, state: SessionState, stored: dict[str, Any] | None) -> str:
    """The hash a record should carry: of the current state, or, for a record written under an
    older project schema, of the project payload exactly as it was stored."""
    if version < PROJECT_SCHEMA_VERSION and stored is not None:
        return payload_hash(stored)
    return state.science_hash


def _record_steps(record: dict[str, Any]) -> list[list[Event]]:
    """Split a record's events into its steps (one step unless ``step_lengths`` says otherwise)."""
    events = record["events"]
    if not isinstance(events, list):
        raise JournalCorrupt(f"record seq {record.get('seq')}: events is not a list")
    lengths = record.get("step_lengths")
    if lengths is None:
        return [events] if events else []
    if (
        not isinstance(lengths, list)
        or not all(isinstance(n, int) and not isinstance(n, bool) and n > 0 for n in lengths)
        or sum(lengths) != len(events)
    ):
        raise JournalCorrupt(f"record seq {record.get('seq')}: step_lengths do not split its events")
    steps, start = [], 0
    for n in lengths:
        steps.append(events[start : start + n])
        start += n
    return steps


def _record_request(record: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    request = record.get("request")
    if request is None:
        return None
    if (
        not isinstance(request, dict)
        or set(request) != {"id", "outcome"}
        or not isinstance(request["id"], str)
        or not isinstance(request["outcome"], dict)
    ):
        raise JournalCorrupt(f"record seq {record.get('seq')}: malformed request entry")
    return request["id"], request["outcome"]


def replay_full(journal: Journal) -> tuple[SessionState, dict[tuple[str, str], StoredOutcome]]:
    """Rebuild the state and the request table from the journal, checking sequence, revisions and
    science hash.

    A record written under an older project schema is checked against the hash of the project
    payload *as stored*, then migrated (``migrate_project``, round 22). So old journals replay,
    and their integrity is still verified.
    """
    state = SessionState()
    requests: dict[tuple[str, str], StoredOutcome] = {}
    stored: dict[str, Any] | None = None  # the last project payload as written in the journal
    schema = 1
    for record in journal.records():
        schema = _record_schema(record, schema)
        steps = _record_steps(record)
        for event in record["events"]:
            if event.get("type") == "project.replaced":
                stored = event["project"]
        if record.get("numerical_context") != numerical_context():
            raise JournalCorrupt(
                f"record seq {record.get('seq')}: written under a different numerical context; "
                "a migration is required before replay"
            )
        try:
            state = apply_record(state, steps, operation=str(record.get("operation")), actor=str(record.get("actor")))
        except (KeyError, TypeError, ValueError) as exc:
            raise JournalCorrupt(f"record seq {record.get('seq')}: cannot be applied ({exc})") from None
        recorded = record["revisions"]
        if (
            record["seq"] != state.seq
            or recorded[SCIENCE] != state.science_revision
            or recorded[WORKSPACE] != state.workspace_revision
            or record["science_hash"] != _recorded_hash(schema, state, stored)
        ):
            raise JournalCorrupt(f"record seq {record['seq']}: replay does not reproduce the recorded state")
        request = _record_request(record)
        if request is not None:
            key = (str(record["actor"]), request[0])
            if key in requests:
                raise JournalCorrupt(f"record seq {record['seq']}: request_id {request[0]!r} recorded twice")
            fingerprint = request_fingerprint(str(record["operation"]), record["args"])
            requests[key] = StoredOutcome(fingerprint, str(record["operation"]), request[1], dict(recorded))
    return state, requests


def replay(journal: Journal) -> SessionState:
    return replay_full(journal)[0]
