"""The Python API for users: notebooks and scripts (Beta, step B1).

Every call is a registry operation, the same as the browser page, the robot and (in Phase 3) an
AI agent make: `studio.call("fit.preview", phi={"value": 37, "unit": "deg"})` returns the
operation's result, and a refused operation raises `OperationFailed` with the server's error.
There is no Python-only path: arguments are validated as strict JSON, as over HTTP.

Two ways to get a `Studio`:

- `Studio.local(project_dir=None)`: a session in this process, as the human user. With a
  `project_dir` the project is journaled there (and locked, so no `dipolar serve` uses it at the
  same time); without one it lives in memory.
- `Studio.connect(ready_file)`: the session of a running `dipolar serve`, over HTTP, with the
  user's token from its ready file. The browser page shows what the notebook does.

    from dipolar_app.api import Studio

    with Studio.local() as studio:
        studio.call("project.open_example", name="biphenyl-synthetic", expected_science_revision=0)
        run = studio.fit(intervals=True)
        print(run["theta"], run["chi2"])
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from pathlib import Path
from types import TracebackType
from typing import Any, Protocol

__all__ = ["OperationFailed", "Studio"]

from dipolar_app.policy import Principal, Tier

#: How long `job.wait` blocks per call (the operation's own limit is 30 s).
WAIT_SLICE_S = 25.0
#: The human user, as `dipolar serve` names it (cli.PRINCIPALS["user"]; a test keeps them equal).
USER = Principal(actor="user", tier=Tier.APPLY, human=True)


class OperationFailed(Exception):
    """A refused operation: the server's error, with its code, message and hint.

    `code` is one of the server's error codes (the registry's `ErrorCode`), with one exception
    made by this client: `NOT_AN_ENVELOPE`, when a reply over HTTP was not an operation envelope
    at all (a proxy's page, an empty or truncated body). Then `http_status` is the reply's HTTP
    status and `message` starts with it; for every server error `http_status` is None."""

    def __init__(self, operation: str, error: Mapping[str, Any]) -> None:
        self.operation = operation
        self.code: str = str(error.get("code", "INTERNAL"))
        self.message: str = str(error.get("message", ""))
        self.offending_field: str | None = error.get("offending_field")
        self.hint: str | None = error.get("hint")
        self.details: Mapping[str, Any] = error.get("details") or {}
        #: The HTTP status, when the reply over HTTP was not an operation envelope (code NOT_AN_ENVELOPE).
        self.http_status: int | None = None
        text = f"{operation}: {self.code}: {self.message}"
        if self.hint:
            text += f" (hint: {self.hint})"
        super().__init__(text)


class _Transport(Protocol):
    def envelope(self, operation: str, args: Mapping[str, Any]) -> dict[str, Any]: ...

    def close(self) -> None: ...


class _Local:
    """A session in this process. Calls are served one at a time (a `job.wait` in progress, up to
    25 s per slice, holds the others and `close()` back). Closing it (rounds 55–56) refuses further
    calls, waits for a call in progress, stops the session (waiting for a result being published,
    then refusing every write), stops the workers, and only then releases the project's lock."""

    def __init__(self, project_dir: Path | None) -> None:
        from dipolar_app.client import LocalClient
        from dipolar_app.jobs import JobRunner
        from dipolar_app.journal import Journal, make_durable_dirs
        from dipolar_app.operations import build_registry
        from dipolar_app.registry import CONTRACT_VERSION
        from dipolar_app.session import Session

        self._lock_fd: int | None = None
        self._calls = threading.Lock()  # one call at a time, and close() waits for it
        self._closed = False
        self._session: Session | None = None
        self._runner: JobRunner | None = None
        if project_dir is not None:
            from dipolar_app.instance import lock_checked

            make_durable_dirs(project_dir)
            self._lock_fd = lock_checked(project_dir)  # a 0.1 directory is refused here, unchanged (D-1)
        try:  # everything after the lock: a failure releases it (round 55)
            journal = None if project_dir is None else Journal(project_dir / "project.events.jsonl")
            self._session = Session(journal, contract_version=CONTRACT_VERSION)
            self._runner = JobRunner(self._session, mode="thread")
            self._client = LocalClient(build_registry(), self._session, USER)
        except BaseException:
            self._shut_down()
            raise

    def envelope(self, operation: str, args: Mapping[str, Any]) -> dict[str, Any]:
        with self._calls:
            if self._closed:
                raise RuntimeError("this Studio is closed")
            return self._client.call(operation, dict(args))

    def close(self) -> None:
        with self._calls:  # a call in progress ends first; later calls are refused
            if self._closed:
                return
            self._closed = True
        self._shut_down()

    def _shut_down(self) -> None:
        try:
            if self._session is not None:
                self._session.stop()  # no commit after this, from a call or a worker
            if self._runner is not None:
                self._runner.close()
            if self._session is not None:
                self._session.close_feeds()
        finally:
            if self._lock_fd is not None:
                os.close(self._lock_fd)
                self._lock_fd = None


class _Remote:
    def __init__(self, ready_file: Path, who: str) -> None:
        ready = json.loads(Path(ready_file).read_text(encoding="utf-8"))
        tokens = ready.get("tokens", {})
        if who not in tokens:
            raise ValueError(f"the ready file has no {who!r} credential (it has: {', '.join(sorted(tokens))})")
        self._base = str(ready["base_url"])
        self._token = str(tokens[who])
        self._closed = False

    def envelope(self, operation: str, args: Mapping[str, Any]) -> dict[str, Any]:
        if self._closed:
            raise RuntimeError("this Studio is closed")
        request = urllib.request.Request(
            f"{self._base}/api/v1/ops/{urllib.parse.quote(operation, safe='.')}",
            data=json.dumps({"args": dict(args)}, allow_nan=False).encode(),
            method="POST",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self._token}"},
        )
        failure: urllib.error.HTTPError | None = None
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                status, reason = response.status, str(response.reason)  # round 56: 201, 204… as sent
                body = response.read()
        except urllib.error.HTTPError as exc:  # a refusal comes with an error envelope; check it
            failure, status, reason = exc, exc.code, str(exc.reason)
            body = exc.read()
        envelope = _as_envelope(body)
        if envelope is None:  # not an operation envelope: report the HTTP reply itself (round 55)
            snippet = body[:200].decode("utf-8", "replace").strip()
            error = OperationFailed(
                operation,
                {"code": "NOT_AN_ENVELOPE", "message": f"HTTP {status} {reason}: {snippet or '(empty body)'}"},
            )
            error.http_status = status
            raise error from failure
        return envelope

    def close(self) -> None:
        self._closed = True


def _as_envelope(body: bytes) -> dict[str, Any] | None:
    """The reply as an operation envelope, or None when it is not one."""
    try:
        data = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("ok"), bool):
        return None
    if data["ok"] and not isinstance(data.get("result"), dict):
        return None
    if not data["ok"] and not isinstance(data.get("error"), dict):
        return None
    return data


class Studio:
    """A Dipolar Studio session, driven through registry operations. Use `Studio.local()` or
    `Studio.connect(ready_file)`; close it (or use it in a `with` block) when done."""

    def __init__(self, transport: _Transport) -> None:
        self._transport = transport

    @classmethod
    def local(cls, project_dir: str | Path | None = None) -> Studio:
        """A session in this process, as the human user; journaled in `project_dir` if given."""
        return cls(_Local(None if project_dir is None else Path(project_dir)))

    @classmethod
    def connect(cls, ready_file: str | Path, *, who: str = "user") -> Studio:
        """The session of a running `dipolar serve`, as `who` (a credential of its ready file)."""
        return cls(_Remote(Path(ready_file), who))

    def envelope(self, operation: str, args: Mapping[str, Any] | None = None, /, **kwargs: Any) -> dict[str, Any]:
        """The operation's whole JSON envelope, success or refusal, as `POST /api/v1/ops/...`."""
        return self._transport.envelope(operation, {**(args or {}), **kwargs})

    def call(self, operation: str, args: Mapping[str, Any] | None = None, /, **kwargs: Any) -> dict[str, Any]:
        """The operation's result; `OperationFailed` if it was refused. Arguments may be given as a
        mapping, as keywords, or both."""
        envelope = self.envelope(operation, args, **kwargs)
        if not envelope.get("ok"):
            raise OperationFailed(operation, envelope.get("error") or {})
        result: dict[str, Any] = envelope["result"]
        return result

    @property
    def science_revision(self) -> int:
        """The project's current science revision (commands that change it name the one they
        expect)."""
        return int(self.call("render.describe_view")["science_revision"])

    def wait(self, job_id: str, *, timeout: float = 600.0) -> dict[str, Any]:
        """Wait for a job to finish (`job.wait`, repeatedly) and return it; `TimeoutError` if it
        is still running after `timeout` seconds."""
        deadline = time.monotonic() + timeout
        while True:
            left = deadline - time.monotonic()
            slice_s = max(0.0, min(WAIT_SLICE_S, left))
            job: dict[str, Any] = self.call("job.wait", job_id=job_id, timeout_s=slice_s)["job"]
            if job["status"] not in ("queued", "running"):
                return job
            if time.monotonic() >= deadline:
                raise TimeoutError(f"job {job_id} is still {job['status']} after {timeout} s")

    def fit(self, *, intervals: bool = False, timeout: float = 600.0) -> dict[str, Any]:
        """Fit the current project (`fit.run` at the current science revision), wait for the job
        and return the run's result (`run.get`). A failed or cancelled job raises
        `OperationFailed` with the job's error."""
        job = self.call("fit.run", intervals=intervals, expected_science_revision=self.science_revision)["job"]
        done = self.wait(job["id"], timeout=timeout)
        if done["status"] != "succeeded":
            error = done.get("error") or {"code": done["status"].upper(), "message": f"the job was {done['status']}"}
            raise OperationFailed("fit.run", error)
        result: dict[str, Any] = self.call("run.get", run_id=done["run_id"])["result"]
        return result

    def close(self) -> None:
        self._transport.close()

    def __enter__(self) -> Studio:
        return self

    def __exit__(self, kind: type[BaseException] | None, value: BaseException | None, tb: TracebackType | None) -> None:
        self.close()
