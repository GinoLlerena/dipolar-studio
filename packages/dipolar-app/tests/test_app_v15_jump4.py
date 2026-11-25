"""Phase 2 V1.5b: the four-site-jump robot tutorial, frozen before its implementation.

The plan (docs/phase2/v1.5-plan.md, exit matrix, "Every implemented model has a robot tutorial"):
"The existing ``m2`` scenario proposes a ``jump4`` fit. V1.5b supplies a runnable tutorial for
that path using synthetic data, with human-tier acceptance, wait, full ``run.get`` evidence under
``jump4``, and a gate for the complete run. Reuse the existing proposal path."

What is frozen here:

- **Synthetic data with a known answer.** ``datasets/biphenyl-synthetic/jump4-couplings.csv`` is
  written by ``jump4_tutorial.py`` from the independent reference's explicit four-conformer
  average (``tools/reference``) at the generator's truth (φ, S_zz, Δ in ``truth.json``), in the
  example's couplings format, at 0.001 Hz.
- **The path.** The robot opens the synthetic example and imports the user's couplings (apply
  tier). The agent (propose tier) is refused a direct model change and proposes the jump model
  and a fit with intervals. The robot then **waits for a human** to accept or reject it, saying so
  on stderr with the proposal's ID; it never accepts. On acceptance it waits for the fit the
  acceptance started and reads the run with ``run.get``.
- **The evidence.** The report carries the refusal, the decided proposal, the job, the run record
  and the complete ``run.get`` result, which must equal the server's, recover the truth, agree
  with the in-process Python adapter, and agree with the independent reference's fit.
- **Failure paths.** A rejection, or no decision within ``--accept-timeout``, ends the run with
  ``ok: false`` and exit 1, and no fit is made.

**Pending implementation.** While robot.py has no ``jump4-tutorial`` scenario, these tests xfail
through ``_scenario()`` alone; once it exists, any exception fails.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from conftest import ROOT, USER, Server, client, new_session
from test_app_m2_exit import assert_same_science

sys.path.insert(0, str(ROOT / "tools" / "reference"))

ROBOT_SCRIPT = ROOT / "tools" / "robot" / "robot.py"
DATA = ROOT / "datasets" / "biphenyl-synthetic"
JUMP4_CSV = DATA / "jump4-couplings.csv"
GENERATOR = DATA / "jump4_tutorial.py"
PAGE = ROOT / "docs" / "phase2" / "verification" / "biphenyl-8cb.md"
JUMP = {
    "kind": "jump4",
    "order": "bisector-diagonal",
    "frame": "bisector",
    "phi_domain": [{"value": 0.0, "unit": "deg"}, {"value": 90.0, "unit": "deg"}],
}


def _scenario() -> None:
    """An xfail while (and only while) robot.py has no jump4-tutorial scenario."""
    if '"jump4-tutorial"' not in ROBOT_SCRIPT.read_text(encoding="utf-8"):
        pytest.xfail("V1.5b: the jump4 robot tutorial is not written yet")


def _documented_command() -> list[str]:
    """The tutorial's arguments as robot.py's docstring writes them."""
    doc = ROBOT_SCRIPT.read_text(encoding="utf-8")
    command = doc.split("--scenario jump4-tutorial \\\n", 1)[1].split("\n", 1)[0].split()
    assert command[:1] == ["--csv"], command
    return command


def _start(server: Server, env: dict[str, str], *args: str) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [
            sys.executable,
            "-I",
            str(ROBOT_SCRIPT),
            "--ready-file",
            str(server.ready_file),
            "--scenario",
            "jump4-tutorial",
            *args,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        cwd=ROOT,
    )


def _waiting_for(proc: subprocess.Popen[str]) -> str:
    """The proposal the robot says it is waiting on (its stderr line)."""
    assert proc.stderr is not None
    line = proc.stderr.readline()
    match = re.search(r"\bprp_\d+\b", line)
    assert "waiting for a human" in line and match, line + (proc.stdout.read() if proc.stdout else "")
    return match.group(0)


def _finish(proc: subprocess.Popen[str]) -> tuple[int, dict[str, Any], str]:
    out, err = proc.communicate(timeout=300)
    return proc.returncode, json.loads(out), err


def _ok(envelope: dict[str, Any]) -> dict[str, Any]:
    assert envelope["ok"], envelope
    result: dict[str, Any] = envelope["result"]
    return result


# ==================================================================== the synthetic data
def _generator() -> Any:
    sys.path.insert(0, str(DATA))
    spec = importlib.util.spec_from_file_location("jump4_tutorial", GENERATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_jump4_data_is_what_its_generator_writes(tmp_path: Path) -> None:
    _scenario()
    out = tmp_path / "jump4-couplings.csv"
    _generator().write(out)
    assert out.read_bytes() == JUMP4_CSV.read_bytes()
    header = JUMP4_CSV.read_text(encoding="utf-8").splitlines()[0]
    assert header == "spin_a,spin_b,equivalent_pairs,multiplicity,D_obs_Hz,sigma_Hz"


def _truth() -> dict[str, float]:
    truth: dict[str, float] = json.loads((DATA / "truth.json").read_text(encoding="utf-8"))
    return truth


def _python_path(csv: str) -> dict[str, Any]:
    """The same science through the in-process Python adapter, as one human user."""
    c = client(new_session(), USER)
    revision = _ok(c.call("project.open_example", {"name": "biphenyl-synthetic", "expected_science_revision": 0}))[
        "science_revision"
    ]
    mapping = _ok(c.call("couplings.reconcile", {"csv": csv}))["proposed_mapping"]
    revision = _ok(
        c.call("couplings.import", {"csv": csv, "confirmed_mapping": mapping, "expected_science_revision": revision})
    )["science_revision"]
    revision = _ok(c.call("model.set", {**JUMP, "expected_science_revision": revision}))["science_revision"]
    job = _ok(c.call("fit.run", {"intervals": True, "expected_science_revision": revision}))["job"]
    while not _ok(c.call("job.wait", {"job_id": job["id"], "timeout_s": 30}))["finished"]:
        pass
    fit: dict[str, Any] = _ok(c.call("run.get", {"run_id": "run_000001"}))["result"]
    return fit


def _reference_phi(csv: str) -> float:
    import biphenyl_reference as R

    rows = [line.split(",") for line in csv.strip().splitlines()[1:]]
    pairs = [(r[0], r[1]) for r in rows]
    y = [float(r[4]) for r in rows]
    sigma = [float(r[5]) for r in rows]
    report = R.fit_report(R.Problem("jump4", pairs, y, sigma), intervals=False)
    return float(report["phi_deg"])


# ================================================================ the complete tutorial
def test_the_robot_jump4_tutorial_as_documented(server: Server, clean_env: dict[str, str]) -> None:
    """The documented command, in a clean process: the agent proposes, a human accepts, the robot
    waits for the fit and reports the complete run."""
    _scenario()
    proc = _start(server, clean_env, *_documented_command())
    try:
        proposal_id = _waiting_for(proc)
        # The human sees what is proposed before deciding.
        shown = _ok(server.call("proposal.get", {"proposal_id": proposal_id}))
        assert shown["proposal"]["status"] == "pending" and shown["proposal"]["stale"] is False
        assert shown["proposal"]["proposer"] == "agent:local"
        assert [s["operation"] for s in shown["steps"]] == ["model.set", "fit.run"]
        assert [s["depends_on"] for s in shown["steps"]] == [[], [0]]
        assert {k: v for k, v in shown["steps"][0]["args"].items() if k in JUMP} == JUMP
        assert shown["steps"][1]["args"]["intervals"] is True
        _ok(server.call("proposal.accept", {"proposal_id": proposal_id}))  # the human tier
        code, report, err = _finish(proc)
    finally:
        if proc.poll() is None:
            proc.kill()
    assert code == 0, (report, err)
    assert report["ok"] is True and report["scenario"] == "jump4-tutorial"
    assert report["refused"] == "PROPOSAL_REQUIRED"  # the agent could not change the science itself
    decided = report["proposal"]
    assert (decided["id"], decided["status"], decided["proposer"]) == (proposal_id, "accepted", "agent:local")
    assert (decided["decided_by"], decided["accepted_steps"]) == ("user", [0, 1])
    job = report["job"]
    assert (job["status"], job["owner"], job["proposed_by"], job["options"]) == (
        "succeeded",
        "user",
        "agent:local",
        {"intervals": True},
    )
    assert report["run"]["job_id"] == job["id"] and report["run"]["stale"] is False

    # The full run.get evidence, under jump4, equal to the server's own.
    result = report["result"]
    assert result["model"] == JUMP
    stored = _ok(server.call("run.get", {"run_id": report["run"]["id"]}))
    assert stored["result"] == result and stored["run"]["id"] == report["run"]["id"]
    assert _ok(server.call("render.describe_view"))["run"] == {
        "run_id": report["run"]["id"],
        "stale": False,
        "available": True,
    }

    # It recovers the synthetic truth ...
    truth = _truth()
    theta = {x["name"]: x["value"] for x in result["theta"]}
    order = {x["name"]: x["value"] for x in result["order"]}
    assert theta["phi_deg"] == pytest.approx(truth["phi_deg"], abs=1e-2)
    assert order["Szz"] == pytest.approx(truth["Szz"], abs=1e-3)
    assert order["Delta"] == pytest.approx(truth["Delta"], abs=1e-3)
    assert result["chi2"] < 0.01 and result["nu"] == result["n_obs"] - 3
    assert len(result["intervals"]) == 3 and all(i["supported"] for i in result["intervals"])
    # ... equals the in-process adapter's fit of the same science ...
    csv = JUMP4_CSV.read_text(encoding="utf-8")
    assert_same_science(result, _python_path(csv))
    # ... and the independent reference's four-site-jump fit.
    assert theta["phi_deg"] == pytest.approx(_reference_phi(csv), abs=1e-4)


def test_the_robot_stops_when_the_human_rejects(server: Server, clean_env: dict[str, str]) -> None:
    _scenario()
    proc = _start(server, clean_env, *_documented_command())
    try:
        proposal_id = _waiting_for(proc)
        _ok(server.call("proposal.reject", {"proposal_id": proposal_id, "reason": "not this model"}))
        code, report, _ = _finish(proc)
    finally:
        if proc.poll() is None:
            proc.kill()
    assert code == 1 and report["ok"] is False
    assert "rejected" in report["error"] and proposal_id in report["error"]
    assert _ok(server.call("run.list"))["runs"] == []  # no fit was made


def test_the_robot_does_not_wait_forever(server: Server, clean_env: dict[str, str]) -> None:
    _scenario()
    proc = _start(server, clean_env, *_documented_command(), "--accept-timeout", "2")
    try:
        proposal_id = _waiting_for(proc)
        code, report, _ = _finish(proc)
    finally:
        if proc.poll() is None:
            proc.kill()
    assert code == 1 and report["ok"] is False
    assert "no human" in report["error"] and proposal_id in report["error"]
    # The proposal is left for the human: still pending, never accepted by the robot.
    assert _ok(server.call("proposal.get", {"proposal_id": proposal_id}))["proposal"]["status"] == "pending"
    assert _ok(server.call("run.list"))["runs"] == []


# ===================================================================== the 8CB page
def test_the_8cb_page_links_the_runnable_tutorial() -> None:
    _scenario()
    rows = [line for line in PAGE.read_text(encoding="utf-8").splitlines() if line.startswith("| Robot tutorial |")]
    assert len(rows) == 1
    row = rows[0]
    assert "robot.py --scenario jump4-tutorial" in row
    assert "test_app_v15_jump4.py" in row
    assert not re.search(r"\bOpen\b|still to be written|cannot pass", row), row
