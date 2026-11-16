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
