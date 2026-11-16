"""The Python API for users (dipolar_app.api, Beta step B1): every call a registry operation, a
refusal an exception with the server's error, the same results in-process and over HTTP."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from conftest import Server, expected
from dipolar_app.api import USER, OperationFailed, Studio
from dipolar_app.instance import InstanceRunning

OPEN = {"name": "biphenyl-synthetic", "expected_science_revision": 0}
JUMP = {
    "kind": "jump4",
    "order": "bisector-diagonal",
    "frame": "bisector",
    "phi_domain": [{"value": 0, "unit": "deg"}, {"value": 90, "unit": "deg"}],
}


def test_the_user_is_the_one_dipolar_serve_names() -> None:
    from dipolar_app.cli import PRINCIPALS

    assert USER == PRINCIPALS["user"]


def test_a_local_session_runs_operations_and_fits() -> None:
    e = expected("noisy_fixture.json")["expected"]
    tol = expected("spec.json")["tolerances"]["regression"]
    with Studio.local() as studio:
        opened = studio.call("project.open_example", OPEN)  # a mapping...
        assert opened["science_revision"] == 1
        assert studio.science_revision == 1
        preview = studio.call("fit.preview", phi={"value": 37.0, "unit": "deg"})  # ...or keywords
        assert preview["phi"]["value"] == 37.0
        run = studio.fit()
        phi = {t["name"]: t["value"] for t in run["theta"]}["phi_deg"]
        assert phi == pytest.approx(e["phi_deg"], abs=tol["phi_atol_deg"])  # the frozen answer


def test_a_refusal_is_an_exception_with_the_servers_error() -> None:
    with Studio.local() as studio:
        with pytest.raises(OperationFailed) as caught:
            studio.call("fit.preview", phi={"value": 37.0, "unit": "deg"})  # no project yet
        assert caught.value.code == "NO_PROJECT"
        assert caught.value.operation == "fit.preview" and caught.value.message
        stale = studio.envelope("project.open_example", name="biphenyl-synthetic", expected_science_revision=5)
        assert stale["ok"] is False and stale["error"]["code"] == "REVISION_CONFLICT"  # the raw envelope
        with pytest.raises(OperationFailed) as unknown:
            studio.call("fit.preview", phi={"value": 37.0, "unit": "deg"}, nonsense=1)
        assert unknown.value.code == "INVALID_ARGUMENT"


def test_a_journaled_session_is_locked_and_reopens(tmp_path: Path) -> None:
    project = tmp_path / "project"
    with Studio.local(project) as studio:
        studio.call("project.open_example", OPEN)
        with pytest.raises(InstanceRunning):
            Studio.local(project)  # one live session per project directory
    with Studio.local(project) as again:  # the lock is released on close
        assert again.science_revision == 1
        assert again.call("render.describe_view")["project_open"] is True


def test_connect_drives_a_running_server(server: Server) -> None:
    with Studio.connect(server.ready_file) as studio:
        studio.call("project.open_example", OPEN)
        run = studio.fit()
        with pytest.raises(OperationFailed) as caught:
            studio.call("project.open_example", OPEN)  # revision 0 is gone
        assert caught.value.code == "REVISION_CONFLICT"
    # The server's other clients see the same session.
    assert server.call("render.describe_view")["result"]["run"]["run_id"]
    assert run["chi2"] > 0
    with pytest.raises(ValueError, match="no 'nobody' credential"):
        Studio.connect(server.ready_file, who="nobody")


def test_a_local_session_does_not_load_the_web_server() -> None:
    """Notebooks and scripts need no HTTP stack: the in-process path imports neither uvicorn nor
    starlette."""
    probe = (
        "import sys\n"
        "from dipolar_app.api import Studio\n"
        "s = Studio.local()\n"
        "s.call('project.open_example', name='biphenyl-synthetic', expected_science_revision=0)\n"
        "s.close()\n"
        "bad = sorted(m for m in sys.modules if m.split('.')[0] in ('uvicorn', 'starlette'))\n"
        "assert not bad, bad\n"
    )
    subprocess.run([sys.executable, "-c", probe], check=True, timeout=120)


# --------------------------------------------------------------------------- round 55
def test_a_closed_studio_refuses_calls_and_the_next_one_owns_the_journal(tmp_path: Path) -> None:
    project = tmp_path / "project"
    first = Studio.local(project)
    first.call("project.open_example", OPEN)
    first.close()
    first.close()  # closing twice is harmless
    with pytest.raises(RuntimeError, match="closed"):
        first.call("render.describe_view")
    with Studio.local(project) as second:
        second.call("model.set", **JUMP, expected_science_revision=1)
    with Studio.local(project) as third:  # the journal replays: no write came from the first
        assert third.science_revision == 2


def test_a_result_after_the_session_stopped_writes_nothing(tmp_path: Path) -> None:
    from dipolar_app.errors import OperationError
    from dipolar_app.jobs import JobRunner
    from dipolar_app.journal import Journal
    from dipolar_app.registry import CONTRACT_VERSION
    from dipolar_app.session import Session

    session = Session(Journal(tmp_path / "project.events.jsonl"), contract_version=CONTRACT_VERSION)
    runner = JobRunner(session, mode="thread")
    seq = session.state.seq
    session.stop()
    assert runner.finish("job_000001", "succeeded", result={"late": True}) is False
    assert session.state.seq == seq
    assert not (tmp_path / "runs").exists()  # no result blob either
    with pytest.raises(OperationError, match="closed"):
        session.commit(USER, "view.select", {}, lambda state: ([], None))
    runner.close()


def test_a_fit_running_when_the_studio_closes_publishes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Round 55: a fit still computing in a worker thread when its Studio closed published after
    another Studio had reopened the directory, and the journal no longer replayed."""
    import threading

    from dipolar_app import jobs as jobs_module

    gate = threading.Event()
    real = jobs_module.compute

    def held(*args: object) -> dict[str, object]:
        gate.wait(30)
        return real(*args)  # type: ignore[arg-type]

    monkeypatch.setattr(jobs_module, "compute", held)
    project = tmp_path / "project"
    first = Studio.local(project)
    first.call("project.open_example", OPEN)
    job = first.call("fit.run", expected_science_revision=1)["job"]["id"]
    releaser = threading.Timer(0.3, gate.set)
    releaser.start()
    first.close()  # the worker finishes computing after the session stopped
    releaser.join()
    with Studio.local(project) as second:
        status = second.call("job.status", job_id=job)["job"]["status"]
        assert status == "interrupted"  # recorded at reopening, as after a stopped server
        assert second.call("run.list")["runs"] == []
    with Studio.local(project) as third:  # and the journal still replays
        assert third.call("job.status", job_id=job)["job"]["status"] == "interrupted"


def test_a_failed_start_releases_the_project_lock(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    journal = project / "project.events.jsonl"
    journal.symlink_to(tmp_path / "nowhere")  # a dangling symlink: opening the journal fails
    with pytest.raises(OSError):
        Studio.local(project)
    journal.unlink()
    with Studio.local(project) as studio:  # not InstanceRunning: the lock was released
        assert studio.science_revision == 0


def test_a_reply_that_is_not_an_envelope_keeps_its_http_status(server: Server) -> None:
    with Studio.connect(server.ready_file) as studio:
        with pytest.raises(OperationFailed) as caught:
            studio.call("project/describe")
        assert caught.value.code == "NOT_AN_ENVELOPE" and caught.value.http_status == 404
        assert "HTTP 404" in caught.value.message
    with pytest.raises(RuntimeError, match="closed"):
        studio.call("render.describe_view")


@pytest.mark.parametrize(
    "body",
    [
        b"",
        b"<html>502</html>",
        b"[]",
        b'{"ok": "yes"}',
        b'{"ok": true}',
        b'{"ok": false}',
        b'{"ok": true, "result": 3}',
    ],
)
def test_only_operation_envelopes_are_accepted(body: bytes) -> None:
    from dipolar_app.api import _as_envelope

    assert _as_envelope(body) is None
    assert _as_envelope(b'{"ok": true, "result": {}}') == {"ok": True, "result": {}}


def test_a_result_already_being_published_at_close_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The narrow case (round 55): the worker has passed its 'closed?' check and is about to
    publish when the Studio closes. The session's stop refuses the publication."""
    import threading

    from dipolar_app.jobs import JobRunner

    entered, gate = threading.Event(), threading.Event()
    real = JobRunner.finish

    def held(self: JobRunner, *args: object, **kwargs: object) -> bool:
        entered.set()
        gate.wait(30)
        return real(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(JobRunner, "finish", held)
    project = tmp_path / "project"
    first = Studio.local(project)
    first.call("project.open_example", OPEN)
    job = first.call("fit.run", expected_science_revision=1)["job"]["id"]
    assert entered.wait(60)  # computed, past the check, held before publishing
    releaser = threading.Timer(0.3, gate.set)
    releaser.start()
    first.close()
    releaser.join()
    monkeypatch.setattr(JobRunner, "finish", real)
    with Studio.local(project) as second:
        assert second.call("job.status", job_id=job)["job"]["status"] == "interrupted"
        assert second.call("run.list")["runs"] == []
