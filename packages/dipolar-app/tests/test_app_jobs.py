"""M2 step 3: jobs, runs and the event stream (04 D11, D14, D18, §8.1, §8.6)."""

from __future__ import annotations

import json
import multiprocessing
import os
import threading
import time
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from conftest import AGENT, ROBOT, USER, Server, client, new_session
from dipolar_app import jobs as jobs_module
from dipolar_app.client import LocalClient
from dipolar_app.errors import ErrorCode, OperationError
from dipolar_app.jobs import JobRunner
from dipolar_app.journal import Journal, JournalCorrupt
from dipolar_app.operations import build_registry
from dipolar_app.registry import CONTRACT_VERSION
from dipolar_app.science_ops import compute_fit
from dipolar_app.session import Session, replay

OPEN = {"name": "biphenyl-synthetic", "expected_science_revision": 0}


def deg(value: float) -> dict[str, object]:
    return {"value": value, "unit": "deg"}


JUMP = {"kind": "jump4", "order": "bisector-diagonal", "frame": "bisector", "phi_domain": [deg(0), deg(90)]}


def ok(envelope: dict[str, Any]) -> dict[str, Any]:
    assert envelope["ok"], envelope
    result: dict[str, Any] = envelope["result"]
    return result


def error(envelope: dict[str, Any], code: str, field: str | None = None) -> dict[str, Any]:
    assert not envelope["ok"], envelope
    assert envelope["error"]["code"] == code, envelope
    if field is not None:
        assert envelope["error"]["offending_field"] == field, envelope
    body: dict[str, Any] = envelope["error"]
    return body


def opened(tmp_path: Path | None = None) -> tuple[Session, LocalClient]:
    s = new_session(tmp_path)
    c = client(s)
    ok(c.call("project.open_example", OPEN))
    return s, c


def wait(c: LocalClient, job_id: str) -> dict[str, Any]:
    for _ in range(3):  # at most 90 s: a stuck job fails the test instead of hanging it
        r = ok(c.call("job.wait", {"job_id": job_id, "timeout_s": 30}))
        if r["finished"]:
            job: dict[str, Any] = r["job"]
            return job
    raise AssertionError("the job did not finish")


def submit(c: LocalClient, revision: int = 1, **options: Any) -> str:
    job_id: str = ok(c.call("fit.run", {**options, "expected_science_revision": revision}))["job"]["id"]
    return job_id


@pytest.fixture
def gate(monkeypatch: pytest.MonkeyPatch) -> Iterator[threading.Event]:
    """Hold every thread-mode job inside ``compute`` until the event is set."""
    release = threading.Event()
    real = jobs_module.compute

    def held(*args: Any) -> dict[str, Any]:
        assert release.wait(30)
        return real(*args)

    monkeypatch.setattr(jobs_module, "compute", held)
    yield release
    release.set()


def journal_ops(tmp_path: Path) -> list[str]:
    return [r["operation"] for r in Journal(tmp_path / "project.events.jsonl").records()]


# --------------------------------------------------------------------------- lifecycle
def test_fit_run_returns_a_job_and_publishes_a_run(tmp_path: Path) -> None:
    s, c = opened(tmp_path)
    submitted = ok(c.call("fit.run", {"expected_science_revision": 1}))
    job = submitted["job"]
    assert job["id"] == "job_000001" and job["status"] in ("queued", "running") and job["owner"] == "user"
    assert job["science_revision"] == 1 and job["input_hash"].startswith("sha256:") and job["run_id"] is None
    assert submitted["science_revision"] == 1  # a job advances neither revision
    done = wait(c, job["id"])
    assert done["status"] == "succeeded" and done["run_id"] == "run_000001" and not done["stale"]
    got = ok(c.call("run.get", {"run_id": "run_000001"}))
    assert got["run"]["job_id"] == "job_000001" and got["run"]["stale"] is False
    direct = compute_fit(s.state.project, False, 1, s.state.science_hash)  # type: ignore[arg-type]
    assert got["result"] == direct.model_dump(mode="json")
    blob = tmp_path / "runs" / f"{got['run']['result_sha256']}.json"
    assert blob.exists() and (os.name != "posix" or oct(blob.stat().st_mode & 0o777) == "0o600")
    assert journal_ops(tmp_path)[-2:] == ["fit.run", "job.finish"]
    assert s.state.science_revision == 1 and s.state.workspace_revision == 0
    assert [r["id"] for r in ok(c.call("run.list"))["runs"]] == ["run_000001"]


def test_a_run_finished_after_an_edit_is_stale_and_changes_nothing(gate: threading.Event) -> None:
    s, c = opened()
    job_id = submit(c)
    ok(c.call("model.set", {**JUMP, "expected_science_revision": 1}))
    before = s.state
    gate.set()
    done = wait(c, job_id)
    assert done["status"] == "succeeded" and done["stale"] is True
    run = ok(c.call("run.get", {"run_id": done["run_id"]}))
    assert run["run"]["stale"] and run["run"]["science_revision"] == 1
    assert run["result"]["model"]["kind"] == "rigid"  # computed from its own input snapshot
    assert s.state.project == before.project and s.state.science_revision == before.science_revision


def test_cancel_and_completion_resolve_to_one_terminal_state(tmp_path: Path, gate: threading.Event) -> None:
    s, c = opened(tmp_path)
    job_id = submit(c)
    s.wait_for(lambda _: s.live_status(job_id) == "running", 10)
    cancelled = ok(c.call("job.cancel", {"job_id": job_id}))
    assert cancelled["cancelled"] and cancelled["job"]["status"] == "cancelled"
    gate.set()  # the computation finishes after the cancel: its result is dropped
    time.sleep(0.5)
    job = s.state.job(job_id)
    assert job is not None and job.status == "cancelled" and job.run_id is None and s.state.runs == ()
    again = ok(c.call("job.cancel", {"job_id": job_id}))
    assert again["cancelled"] is False
    finished = [
        e
        for r in Journal(tmp_path / "project.events.jsonl").records()
        for e in r["events"]
        if e["type"] == "job.finished"
    ]
    assert len(finished) == 1 and finished[0]["status"] == "cancelled"


def test_failures_are_reported_on_the_job(monkeypatch: pytest.MonkeyPatch) -> None:
    def refused(*_: Any) -> dict[str, Any]:
        raise OperationError(ErrorCode.PROJECT_NOT_READY, "coincident spins")

    monkeypatch.setattr(jobs_module, "compute", refused)
    _, c = opened()
    job = wait(c, submit(c))
    assert job["status"] == "failed" and job["error"] == {"code": "PROJECT_NOT_READY", "message": "coincident spins"}

    def crashed(*_: Any) -> dict[str, Any]:
        raise RuntimeError("secret detail")

    monkeypatch.setattr(jobs_module, "compute", crashed)
    job = wait(c, submit(c))
    assert job["status"] == "failed" and job["error"]["code"] == "INTERNAL" and "secret" not in job["error"]["message"]


def test_a_dry_run_never_launches_a_job(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[Any] = []
    monkeypatch.setattr(jobs_module, "compute", lambda *a: calls.append(a) or {})
    s, c = opened()
    env = c.call("fit.run", {"expected_science_revision": 1}, dry_run=True)
    assert env["ok"] and env["result"]["job"]["id"] == "job_000001"
    time.sleep(0.2)
    assert s.state.jobs == () and calls == []


def test_unfinished_jobs_are_bounded(gate: threading.Event) -> None:
    s, user = opened()
    robot = client(s, ROBOT)
    submit(user)
    submit(user)
    error(user.call("fit.run", {"expected_science_revision": 1}), "QUOTA_EXCEEDED")
    submit(robot)  # the limit is per caller, then global
    gate.set()


def test_job_wait_is_bounded(gate: threading.Event) -> None:
    s, c = opened()
    job_id = submit(c)
    error(c.call("job.wait", {"job_id": job_id, "timeout_s": 31}), "INVALID_ARGUMENT", "timeout_s")
    s.wait_for(lambda _: s.live_status(job_id) == "running", 10)
    start = time.monotonic()
    r = ok(c.call("job.wait", {"job_id": job_id, "timeout_s": 0.2}))
    assert not r["finished"] and r["job"]["status"] == "running" and time.monotonic() - start < 5
    error(c.call("job.status", {"job_id": "job_000099"}), "ID_NOT_FOUND", "job_id")
    error(c.call("run.get", {"run_id": "run_000099"}), "ID_NOT_FOUND", "run_id")


def test_submission_needs_the_current_revision_and_a_ready_project() -> None:
    s, c = opened()
    error(c.call("fit.run", {"expected_science_revision": 0}), "REVISION_CONFLICT")
    error(c.call("fit.run", {}), "INVALID_ARGUMENT", "expected_science_revision")
    from dipolar_app.science_ops import ETHANE_XYZ

    ok(c.call("project.import_xyz", {"xyz": ETHANE_XYZ, "name": "ethane", "expected_science_revision": 1}))
    error(c.call("fit.run", {"expected_science_revision": 2}), "PROJECT_NOT_READY")
    assert s.state.jobs == ()


# --------------------------------------------------------------------------- agents
def test_an_agent_proposes_a_fit_and_a_human_starts_it() -> None:
    s, user = opened()
    agent = client(s, AGENT)
    body = error(agent.call("fit.run", {"expected_science_revision": 1}), "PROPOSAL_REQUIRED")
    assert "proposal.create" in body["hint"]
    steps = [
        {"operation": "model.set", "args": {**JUMP, "expected_science_revision": 1}},
        {"operation": "fit.run", "args": {"expected_science_revision": 2}},
    ]
    ok(agent.call("proposal.create", {"steps": steps}))
    assert s.state.jobs == ()  # nothing runs before a human accepts
    accepted = ok(user.call("proposal.accept", {"proposal_id": "prp_000001"}))
    job = accepted["results"][1]["result"]["job"]
    assert job["owner"] == "user" and job["science_revision"] == 2
    done = wait(user, job["id"])
    assert done["proposed_by"] == "agent:test" and done["status"] == "succeeded"
    run = ok(agent.call("run.get", {"run_id": done["run_id"]}))
    assert run["result"]["model"]["kind"] == "jump4"  # the job computed after the proposal's model change


def test_compute_steps_come_last_in_a_proposal() -> None:
    s, _ = opened()
    steps = [
        {"operation": "fit.run", "args": {"expected_science_revision": 1}},
        {"operation": "model.set", "args": {**JUMP, "expected_science_revision": 1}},
    ]
    error(client(s, AGENT).call("proposal.create", {"steps": steps}), "INVALID_ARGUMENT", "steps[1].operation")


def test_a_propose_tier_caller_cancels_only_its_own_jobs(gate: threading.Event) -> None:
    s, user = opened()
    agent = client(s, AGENT)
    mine = submit(user)
    error(agent.call("job.cancel", {"job_id": mine}), "CAPABILITY_DENIED", "job_id")
    ok(agent.call("proposal.create", {"steps": [{"operation": "fit.run", "args": {"expected_science_revision": 1}}]}))
    proposed = ok(user.call("proposal.accept", {"proposal_id": "prp_000001"}))["results"][0]["result"]["job"]["id"]
    assert ok(agent.call("job.cancel", {"job_id": proposed}))["cancelled"]
    assert ok(client(s, ROBOT).call("job.cancel", {"job_id": mine}))["cancelled"]  # apply tier: any job
    gate.set()


# --------------------------------------------------------------------------- restart and replay
def test_a_restart_interrupts_unfinished_jobs_and_replays_runs(tmp_path: Path) -> None:
    _, c = opened(tmp_path)
    wait(c, submit(c))
    bare = Session(Journal(tmp_path / "project.events.jsonl"), contract_version=CONTRACT_VERSION)
    LocalClient(build_registry(), bare, USER).call("fit.run", {"expected_science_revision": 1})  # no runner
    assert bare.state.job("job_000002").status == "queued"  # type: ignore[union-attr]
    restarted = Session(Journal(tmp_path / "project.events.jsonl"), contract_version=CONTRACT_VERSION)
    JobRunner(restarted, mode="thread")
    job = restarted.state.job("job_000002")
    assert job is not None and job.status == "interrupted" and job.error_code == "INTERRUPTED"
    assert replay(Journal(tmp_path / "project.events.jsonl")) == restarted.state
    again = LocalClient(build_registry(), restarted, USER)
    assert ok(again.call("run.get", {"run_id": "run_000001"}))["result"]["chi2"] >= 0


def test_a_damaged_result_blob_is_refused(tmp_path: Path) -> None:
    _, c = opened(tmp_path)
    wait(c, submit(c))
    (blob,) = (tmp_path / "runs").glob("*.json")
    blob.write_text(blob.read_text(encoding="utf-8").replace("chi2", "chi3", 1), encoding="utf-8")
    with pytest.raises(JournalCorrupt, match="blob"):
        Session(Journal(tmp_path / "project.events.jsonl"), contract_version=CONTRACT_VERSION)


# --------------------------------------------------------------------------- worker processes
def test_process_workers_compute_and_cancel(tmp_path: Path) -> None:
    session = Session(Journal(tmp_path / "project.events.jsonl"), contract_version=CONTRACT_VERSION)
    runner = JobRunner(session, mode="process")
    try:
        c = LocalClient(build_registry(), session, USER)
        ok(c.call("project.open_example", OPEN))
        done = wait(c, submit(c))
        assert done["status"] == "succeeded"
        result = ok(c.call("run.get", {"run_id": done["run_id"]}))["result"]
        assert result == compute_fit(session.state.project, False, 1, session.state.science_hash).model_dump(  # type: ignore[arg-type]
            mode="json"
        )
        slow = submit(c, intervals=True)  # profile intervals take seconds
        session.wait_for(lambda _: session.live_status(slow) == "running", 30)
        start = time.monotonic()
        ok(c.call("job.cancel", {"job_id": slow}))
        session.wait_for(lambda _: session.live_status(slow) is None, 15)
        assert time.monotonic() - start < 3 and not multiprocessing.active_children()  # terminated at once
        assert session.state.job(slow).status == "cancelled"  # type: ignore[union-attr]
    finally:
        runner.close()


# --------------------------------------------------------------------------- the change feed
def test_the_feed_reports_commits_and_job_progress(gate: threading.Event) -> None:
    s, c = opened()
    start = s.cursor
    job_id = submit(c)
    s.wait_for(lambda _: s.live_status(job_id) == "running", 10)
    gate.set()
    wait(c, job_id)
    items, latest, resync = s.feed_after(start, 0)
    assert not resync and latest == s.cursor
    kinds = [
        (i["kind"], i.get("operation"), tuple((j["job_id"], j["status"]) for j in i.get("jobs", ()))) for _, i in items
    ]
    assert kinds[0] == ("commit", "fit.run", ((job_id, "queued"),))
    assert ("job", None, ()) in [(k, o, ()) for k, o, _ in kinds]
    assert kinds[-1] == ("commit", "job.finish", ((job_id, "succeeded"),))
    assert s.feed_after(latest + 5, 0)[2] is True  # a cursor from the future (another boot): resync


def read_lines(resp: Any, n: int) -> list[dict[str, Any]]:
    out = []
    while len(out) < n:
        line = resp.readline()
        assert line, "the stream ended"
        out.append(json.loads(line))
    return out


def test_http_event_stream(server: Server) -> None:
    req = urllib.request.Request(server.base_url + "/api/v1/events")
    req.add_header("Authorization", f"Bearer {server.tokens['viewer']}")  # any tier may listen
    with urllib.request.urlopen(req, timeout=30) as resp:
        assert resp.headers["Content-Type"].startswith("application/x-ndjson")
        (hello,) = read_lines(resp, 1)
        assert hello["kind"] == "hello" and hello["seq"] == 0 and hello["revisions"] == {"science": 0, "workspace": 0}
        assert server.call("project.open_example", OPEN)["ok"]
        (commit,) = read_lines(resp, 1)
        assert commit["kind"] == "commit" and commit["operation"] == "project.open_example"
        assert commit["actor"] == "user" and commit["revisions"]["science"] == 1 and "args" not in commit
        assert commit["cursor"] > hello["cursor"]
    assert server.request("GET", "/api/v1/events", token=None).status == 401
    assert server.request("GET", "/api/v1/events?after=abc").status == 400


def test_a_late_outcome_is_dropped_quietly(gate: threading.Event) -> None:
    """The runner's finish after a cancel changes nothing and raises nothing (its worker lives on)."""
    session = Session(None, contract_version=CONTRACT_VERSION)
    runner = JobRunner(session, mode="thread")
    c = LocalClient(build_registry(), session, USER)
    ok(c.call("project.open_example", OPEN))
    job_id = submit(c)
    ok(c.call("job.cancel", {"job_id": job_id}))
    seq = session.state.seq
    assert runner.finish(job_id, "succeeded", result={"late": True}) is False
    assert runner.finish(job_id, "failed", error=("INTERNAL", "late")) is False
    assert session.state.seq == seq and session.state.job(job_id).status == "cancelled"  # type: ignore[union-attr]
    gate.set()


# --------------------------------------------------------------------------- round 33
def test_an_infrastructure_failure_fails_the_job_and_the_worker_lives_on(monkeypatch: pytest.MonkeyPatch) -> None:
    s, c = opened()
    real = s.blobs.put
    calls = {"n": 0}

    def flaky(data: dict[str, Any]) -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("disk full")
        return real(data)

    monkeypatch.setattr(s.blobs, "put", flaky)
    first = wait(c, submit(c))
    assert first["status"] == "failed" and first["error"]["code"] == "INTERNAL"
    for _ in range(3):  # more jobs than workers: every worker survived
        assert wait(c, submit(c))["status"] == "succeeded"


def test_a_spawn_failure_fails_only_its_job(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    session = Session(Journal(tmp_path / "project.events.jsonl"), contract_version=CONTRACT_VERSION)
    runner = JobRunner(session, mode="process", workers=1)
    real = jobs_module.multiprocessing.get_context
    calls = {"n": 0}

    class Broken:
        def Process(self, *a: Any, **k: Any) -> Any:
            proc = real("spawn").Process(*a, **k)

            def start() -> None:
                raise OSError("cannot fork")

            proc.start = start  # type: ignore[method-assign]
            return proc

    def context(method: str) -> Any:
        calls["n"] += 1
        return Broken() if calls["n"] == 1 else real(method)

    monkeypatch.setattr(jobs_module.multiprocessing, "get_context", context)
    try:
        c = LocalClient(build_registry(), session, USER)
        ok(c.call("project.open_example", OPEN))
        assert wait(c, submit(c))["status"] == "failed"
        assert wait(c, submit(c))["status"] == "succeeded"
    finally:
        runner.close()


def test_a_process_job_times_out_within_its_budget(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jobs_module, "JOB_TIMEOUT_S", 1.5)
    session = Session(Journal(tmp_path / "project.events.jsonl"), contract_version=CONTRACT_VERSION)
    runner = JobRunner(session, mode="process")
    try:
        c = LocalClient(build_registry(), session, USER)
        ok(c.call("project.open_example", OPEN))
        start = time.monotonic()
        job = wait(c, submit(c, intervals=True))
        assert job["status"] == "failed" and job["error"]["code"] == "TIMEOUT"
        assert time.monotonic() - start < 6 and not multiprocessing.active_children()
    finally:
        runner.close()


def test_the_blob_directory_is_made_durable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from dipolar_app import session as session_module

    synced: list[Path] = []
    real = session_module.fsync_dir
    monkeypatch.setattr(session_module, "fsync_dir", lambda p: (synced.append(p), real(p))[1])
    _, c = opened(tmp_path)
    wait(c, submit(c))
    assert tmp_path in synced and tmp_path / "runs" in synced


def test_a_damaged_blob_is_rewritten_when_the_same_result_is_published(tmp_path: Path) -> None:
    _, c = opened(tmp_path)
    first = wait(c, submit(c))
    (blob,) = (tmp_path / "runs").glob("*.json")
    blob.write_text("damaged", encoding="utf-8")
    second = wait(c, submit(c))
    assert second["status"] == "succeeded"
    assert ok(c.call("run.get", {"run_id": second["run_id"]}))["result"]["chi2"] >= 0
    assert ok(c.call("run.get", {"run_id": first["run_id"]}))["run"]["result_sha256"] == blob.stem


def test_an_accepted_fit_reports_its_proposer(gate: threading.Event) -> None:
    s, user = opened()
    agent = client(s, AGENT)
    ok(agent.call("proposal.create", {"steps": [{"operation": "fit.run", "args": {"expected_science_revision": 1}}]}))
    accepted = ok(user.call("proposal.accept", {"proposal_id": "prp_000001"}, request_id="acc"))
    assert accepted["results"][0]["result"]["job"]["proposed_by"] == "agent:test"
    gate.set()


def test_blocking_waits_are_capped_so_commands_keep_their_threads(gate: threading.Event) -> None:
    from dipolar_app import job_ops

    _s, c = opened()
    job_id = submit(c)
    holders = [
        threading.Thread(target=c.call, args=("job.wait", {"job_id": job_id, "timeout_s": 30}))
        for _ in range(job_ops.MAX_BLOCKING_WAITS)
    ]
    for t in holders:
        t.start()
    time.sleep(0.3)
    start = time.monotonic()
    extra = ok(c.call("job.wait", {"job_id": job_id, "timeout_s": 30}))
    assert not extra["finished"] and time.monotonic() - start < 2  # answered at once
    gate.set()
    for t in holders:
        t.join(30)


def test_a_snapshot_never_pairs_a_new_state_with_an_old_cursor() -> None:
    s, c = opened()
    seen: list[tuple[int, int]] = []

    def listener(state: Any, events: Any) -> None:
        reader = threading.Thread(target=lambda: seen.append((lambda st, cur: (st.seq, cur))(*s.snapshot())))
        reader.start()
        time.sleep(0.1)  # the reader runs while the commit is being published

    s.add_listener(listener)
    ok(c.call("view.select", {"ids": ["cpl_000001"]}))
    time.sleep(0.3)
    ((seq, cursor),) = seen
    at_cursor = dict(s.feed_after(cursor - 1, 0)[0])[cursor]
    assert seq == s.state.seq and at_cursor.get("seq") == seq  # the cursor is exactly the commit's entry


def test_disconnected_event_streams_free_their_slots() -> None:
    import asyncio

    from dipolar_app.auth import Credentials
    from dipolar_app.http import MAX_STREAMS, create_app

    s, _ = opened()
    app = create_app(build_registry(), s, Credentials({"tok": USER}), port=1)
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/events",
        "raw_path": b"/api/v1/events",
        "query_string": b"",
        "headers": [(b"host", b"127.0.0.1:1"), (b"authorization", b"Bearer tok")],
        "http_version": "1.1",
        "scheme": "http",
        "server": ("127.0.0.1", 1),
        "client": ("127.0.0.1", 2),
        "root_path": "",
    }

    async def receive() -> dict[str, Any]:
        return {"type": "http.disconnect"}

    async def failing_send(message: dict[str, Any]) -> None:
        raise OSError("the client went away")

    async def run() -> int:
        for _ in range(MAX_STREAMS + 2):
            try:
                await app(dict(scope), receive, failing_send)
            except OSError:
                pass
        status: list[int] = []

        async def send(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                status.append(message["status"])

        await app(dict(scope), receive, send)
        return status[0]

    assert asyncio.run(run()) == 200


# --------------------------------------------------------------------------- round 34
def test_a_worker_receives_its_input_through_a_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Starting a worker sends two short paths through the spawn pipe, never the project."""
    seen: list[tuple[Any, ...]] = []
    real = jobs_module.multiprocessing.get_context

    class Recording:
        def Process(self, *a: Any, **k: Any) -> Any:
            seen.append(tuple(k.get("args", ())))
            return real("spawn").Process(*a, **k)

    monkeypatch.setattr(jobs_module.multiprocessing, "get_context", lambda _m: Recording())
    session = Session(Journal(tmp_path / "project.events.jsonl"), contract_version=CONTRACT_VERSION)
    runner = JobRunner(session, mode="process")
    try:
        c = LocalClient(build_registry(), session, USER)
        ok(c.call("project.open_example", OPEN))
        assert wait(c, submit(c))["status"] == "succeeded"
    finally:
        runner.close()
    ((input_path, outcome_path),) = seen
    assert all(isinstance(x, str) and len(x) < 1024 for x in (input_path, outcome_path))


def test_concurrent_first_publications_both_succeed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from dipolar_app import session as session_module
    from dipolar_app.session import BlobStore

    real = session_module.fsync_dir
    monkeypatch.setattr(session_module, "fsync_dir", lambda p: (time.sleep(0.2), real(p))[1])  # widen the window
    store = BlobStore(tmp_path / "runs")
    barrier = threading.Barrier(2)
    digests: list[str] = []
    errors: list[BaseException] = []

    def publish(k: int) -> None:
        barrier.wait()
        try:
            digests.append(store.put({"k": k}))
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=publish, args=(k,)) for k in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors and len(digests) == 2 and all(store.text(d) is not None for d in digests)


def test_a_blob_that_is_not_utf8_is_treated_as_damaged(tmp_path: Path) -> None:
    from dipolar_app.session import BlobStore

    store = BlobStore(tmp_path / "runs")
    digest = store.put({"chi2": 1.0})
    (tmp_path / "runs" / f"{digest}.json").write_bytes(b"\xff\xfe\x80")
    assert store.text(digest) is None
    assert store.put({"chi2": 1.0}) == digest and store.text(digest) is not None  # rewritten


def test_a_finished_job_never_goes_back_to_running(gate: threading.Event) -> None:
    s, c = opened()
    job_id = submit(c)
    s.wait_for(lambda _: s.live_status(job_id) == "running", 10)
    ok(c.call("job.cancel", {"job_id": job_id}))
    cursor = s.cursor
    s.set_live(job_id, "running")  # a worker that checked before the cancel committed
    assert s.cursor == cursor and ok(c.call("job.status", {"job_id": job_id}))["job"]["status"] == "cancelled"
    gate.set()


def test_new_project_directories_are_made_durable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from dipolar_app import journal as journal_module

    synced: list[Path] = []
    monkeypatch.setattr(journal_module, "fsync_dir", lambda p: synced.append(p))
    journal_module.make_durable_dirs(tmp_path / "a" / "b" / "c")
    assert (tmp_path / "a" / "b" / "c").is_dir()
    assert synced == [tmp_path, tmp_path / "a", tmp_path / "a" / "b"]


def test_an_oversized_outcome_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jobs_module, "MAX_OUTCOME_BYTES", 100)
    path = tmp_path / "outcome.json"
    path.write_text(json.dumps(["ok", {"x": "y" * 200}]), encoding="utf-8")
    assert jobs_module._read_outcome(str(path), 0)[:2] == ("error", "INTERNAL")


def test_view_changes_during_a_running_fit_leave_science_and_run_untouched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """04 §8.6: view writes while a fit is running never touch the science, the running fit's
    result, or the runs already published (round 37: the result itself is compared)."""
    s, c = opened()
    baseline = wait(c, submit(c))  # run_000001: the same inputs, no view changes
    before_run = s.state.run(baseline["run_id"])
    before_blob = s.blobs.text(before_run.result_sha256)  # type: ignore[union-attr]
    release = threading.Event()
    real = jobs_module.compute

    def held(*args: Any) -> dict[str, Any]:
        assert release.wait(30)
        return real(*args)

    monkeypatch.setattr(jobs_module, "compute", held)
    job_id = submit(c)
    s.wait_for(lambda _: s.live_status(job_id) == "running", 10)
    science = (s.state.science_revision, s.state.science_hash)
    ok(c.call("view.select", {"ids": ["cpl_000001"]}))
    ok(c.call("view.highlight", {"ids": ["spn_000002"]}))
    ok(c.call("view.set_layers", {"labels": False, "bonds": True, "couplings": True}))
    ok(c.call("view.set_camera", {"camera": None, "viewport": {"width": 640, "height": 480}}))
    assert (s.state.science_revision, s.state.science_hash) == science and s.state.workspace_revision == 4
    release.set()
    done = wait(c, job_id)
    assert done["status"] == "succeeded" and done["stale"] is False
    held_result = ok(c.call("run.get", {"run_id": done["run_id"]}))
    baseline_result = ok(c.call("run.get", {"run_id": baseline["run_id"]}))
    assert held_result["run"]["stale"] is False
    assert held_result["result"] == baseline_result["result"]  # the same fit, number for number
    assert s.state.run(baseline["run_id"]) == before_run  # the published run is untouched
    assert s.blobs.text(before_run.result_sha256) == before_blob  # type: ignore[union-attr]


# --------------------------------------------------------------------------- blob collection (small batch)
def test_opening_a_session_collects_unreferenced_blobs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Blobs that no run in the state references are removed when the session opens: a pruned
    run's, a dropped late result, a leftover temporary file. The others stay and verify (M2 step 3,
    B limit: blob growth)."""
    from dipolar_app import session as session_module

    monkeypatch.setattr(session_module, "MAX_RUNS", 2)
    s, c = opened(tmp_path)
    first = wait(c, submit(c))  # the rigid model
    ok(c.call("model.set", {**JUMP, "expected_science_revision": 1}))
    wait(c, submit(c, revision=2))  # the jump model
    wide = {**JUMP, "kind": "rigid", "phi_domain": [deg(0), deg(180)]}
    ok(c.call("model.set", {**wide, "expected_science_revision": 2}))
    wait(c, submit(c, revision=3))  # the rigid model on [0, 180]: run_000001 is pruned now
    assert s.state.run(first["run_id"]) is None
    pruned_blob = tmp_path / "runs" / f"{first_blob(s, tmp_path, first)}.json"
    s.blobs.put({"dropped": "a late result after a cancel"})
    leftover = tmp_path / "runs" / ".abc.123.tmp"
    leftover.write_text("partial", encoding="utf-8")
    kept = {r.result_sha256 for r in s.state.runs}
    assert len(kept) == 2 and pruned_blob.exists()
    reopened = Session(Journal(tmp_path / "project.events.jsonl"), contract_version=CONTRACT_VERSION)
    assert reopened.collected == 3  # the pruned run's blob, the dropped result, the temporary file
    assert {p.stem for p in (tmp_path / "runs").glob("*.json")} == kept and not leftover.exists()
    for run in reopened.state.runs:
        assert LocalClient(build_registry(), reopened, USER).call("run.get", {"run_id": run.id})["ok"]
    assert Session(Journal(tmp_path / "project.events.jsonl"), contract_version=CONTRACT_VERSION).collected == 0


def first_blob(s: Session, tmp_path: Path, job: dict[str, Any]) -> str:
    """The blob of a finished job's run, read from the journal (its run may be pruned from the state)."""
    for record in Journal(tmp_path / "project.events.jsonl").records():
        for event in record["events"]:
            if event["type"] == "job.finished" and event["id"] == job["id"] and event["run"]:
                digest: str = event["run"]["result_sha256"]
                return digest
    raise AssertionError("no run for the job")
