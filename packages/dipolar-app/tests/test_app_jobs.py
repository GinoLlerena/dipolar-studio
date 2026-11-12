"""M2 step 3: jobs, runs and the event stream (04 D11, D14, D18, §8.1, §8.6)."""

from __future__ import annotations

import json
import multiprocessing
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
    for _ in range(20):
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
    assert blob.exists() and oct(blob.stat().st_mode & 0o777) == "0o600"
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
    blob.write_text(blob.read_text().replace("chi2", "chi3", 1))
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
