"""The M2 exit audit (plan §8 M2; 04 §7 and §8.6).

The M2 exit criteria:
- all §8.6 checks pass;
- replay reproduces the science hash;
- the registry snapshot, behavioural fixtures and contract tests pass on the Python and HTTP
  adapters;
- the benchmark is published.

docs/validation/m2-exit-audit.md maps every check to its test. This module adds the end-to-end
ones:
- the robot runs the M2 scenario over HTTP only, in a clean process;
- its results equal the Python adapter's, within quantity-specific tolerances;
- a human accepts a dependency-closed subset of the robot's proposal;
- the restarted server replays to the same science hash;
- every registry operation returns the same envelope over HTTP and in-process.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from conftest import ROBOT, ROOT, USER, Server, client, expected, new_session, start_server, stop_server
from dipolar_app.operations import build_registry
from dipolar_app.science_ops import ETHANE_XYZ, ethane_document

ROBOT_SCRIPT = ROOT / "tools" / "robot" / "robot.py"
PHI = 36.98502906633521
OPEN = {"name": "biphenyl-synthetic", "expected_science_revision": 0}


def ok(envelope: dict[str, Any]) -> dict[str, Any]:
    assert envelope["ok"], envelope
    result: dict[str, Any] = envelope["result"]
    return result


def python_path() -> dict[str, Any]:
    """The robot's apply-tier scenario through the Python adapter (the reference path)."""
    c = client(new_session(), ROBOT)
    ok(c.call("project.open_example", OPEN))
    described = ok(c.call("project.describe"))
    label = {s["id"]: s["label"] for s in described["spins"]}
    rows = ["spin_a,spin_b,equivalent_pairs,multiplicity,D_obs_Hz,sigma_Hz"] + [
        f"{label[x['spin_a']]},{label[x['spin_b']]},{' '.join(x['equivalent_pairs'])},{x['multiplicity']},"
        f"{x['value']['value']!r},{x['sigma']['value']!r}"
        for x in described["couplings"]
    ]
    csv = "\n".join(rows) + "\n"
    mapping = ok(c.call("couplings.reconcile", {"csv": csv}))["proposed_mapping"]
    ok(c.call("couplings.import", {"csv": csv, "confirmed_mapping": mapping, "expected_science_revision": 1}))
    preview = ok(c.call("fit.preview", {"phi": {"value": PHI, "unit": "deg"}}))
    job = ok(c.call("fit.run", {"intervals": True, "expected_science_revision": 2}))["job"]
    while not ok(c.call("job.wait", {"job_id": job["id"], "timeout_s": 30}))["finished"]:
        pass
    fit = ok(c.call("run.get", {"run_id": "run_000001"}))["result"]
    return {"preview": preview, "fit": fit}


def assert_same_science(a: dict[str, Any], b: dict[str, Any]) -> None:
    """Equal within the frozen, quantity-specific regression tolerances (§8.6)."""
    tol = expected("spec.json")["tolerances"]["regression"]
    atol = {"phi_deg": tol["phi_atol_deg"], "Szz": tol["S_atol"], "Delta": tol["S_atol"]}
    for key in ("theta", "order"):
        for x, y in zip(a[key], b[key], strict=True):
            assert x["name"] == y["name"] and x["value"] == pytest.approx(y["value"], abs=atol[x["name"]])
    assert a["chi2"] == pytest.approx(b["chi2"], rel=tol["objective_rtol"])
    for x, y in zip(a["couplings"], b["couplings"], strict=True):
        assert x["id"] == y["id"]
        assert x["calculated"]["value"] == pytest.approx(y["calculated"]["value"], abs=tol["predictions_atol_Hz"])
    endpoint = {"phi_deg": tol["phi_interval_endpoint_atol_deg"], "Szz": tol["S_interval_endpoint_atol"]}
    endpoint["Delta"] = endpoint["Szz"]
    for x, y in zip(a["intervals"], b["intervals"], strict=True):
        assert x["parameter"] == y["parameter"] and x["supported"] == y["supported"]
        if x["supported"]:
            assert x["lower"] == pytest.approx(y["lower"], abs=endpoint[x["parameter"]])
            assert x["upper"] == pytest.approx(y["upper"], abs=endpoint[x["parameter"]])


def test_the_robot_completes_the_m2_scenario_over_http_only(tmp_path: Path, clean_env: dict[str, str]) -> None:
    server = start_server(tmp_path)
    try:
        proc = subprocess.run(
            [
                sys.executable,
                "-I",
                str(ROBOT_SCRIPT),
                "--ready-file",
                str(server.ready_file),
                "--scenario",
                "m2",
                "--phi",
                repr(PHI),
            ],
            capture_output=True,
            text=True,
            timeout=600,
            env=clean_env,
            cwd=tmp_path,
            check=False,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        report = json.loads(proc.stdout)

        # The couplings re-imported from the user's CSV keep their IDs (D5) and their science: the
        # values, σ, classes and multiplicities. Only their provenance changes (the labels as
        # imported, the σ source), which the full-field diff reports as changed.
        assert report["reconciled"] == {"complete": True, "added": 0, "removed": 0}
        assert (report["imported"]["added"], report["imported"]["removed"]) == (0, 0)
        e = expected("noisy_fixture.json")["expected"]
        tol = expected("spec.json")["tolerances"]["regression"]
        theta = {x["name"]: x["value"] for x in report["fit"]["theta"]}
        assert theta["phi_deg"] == pytest.approx(e["phi_deg"], abs=tol["phi_atol_deg"])  # the frozen answer
        # The HTTP-only robot's results equal the Python adapter's (quantity-specific tolerances).
        reference = python_path()
        assert_same_science(report["fit"], reference["fit"])
        assert report["preview"]["chi2"] == pytest.approx(reference["preview"]["chi2"], rel=1e-12)
        assert report["fit"]["adequate"] is True and report["view"]["warnings"] == []

        # Proposals (§7): a human accepts a dependency-closed subset; a non-closed one is refused.
        proposal = report["proposal"]
        assert proposal["proposer"] == "agent:local" and [s["depends_on"] for s in proposal["steps"]] == [[], [0]]
        refused = server.call("proposal.accept", {"proposal_id": proposal["id"], "steps": [1]})
        assert refused["error"]["code"] == "INVALID_ARGUMENT" and refused["error"]["details"]["missing"] == [0]
        accepted = server.call("proposal.accept", {"proposal_id": proposal["id"], "steps": [0]})
        assert accepted["ok"] and accepted["result"]["proposal"]["accepted_steps"] == [0]
        before = server.call("render.describe_view")
        hash_before = server.call("project.export")["result"]["science_hash"]
        assert before["result"]["run"]["stale"] is True  # the model changed after the run
    finally:
        stop_server(server)

    # Replay (§7): a restarted server rebuilds the same science from the journal.
    again = start_server(tmp_path)
    try:
        after = again.call("render.describe_view")
        assert after["revisions"] == before["revisions"]
        assert again.call("project.export")["result"]["science_hash"] == hash_before
        assert again.call("run.get", {"run_id": "run_000001"})["ok"]  # the run's blob survived, verified
    finally:
        stop_server(again)


# --------------------------------------------------------------------------- the contract on both adapters
VOLATILE = {"submitted_at", "finished_at", "created_at", "expires_at", "decided_at", "at"}


def normalized(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: ("<time>" if k in VOLATILE else normalized(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [normalized(v) for v in value]
    return value


#: (operation, arguments from the current science revision, credential, expected error or None).
Step = tuple[str, Callable[[int], dict[str, Any]], str, str | None]
JUMP = {
    "kind": "jump4",
    "order": "bisector-diagonal",
    "frame": "bisector",
    "phi_domain": [{"value": 0.0, "unit": "deg"}, {"value": 90.0, "unit": "deg"}],
}
CAMERA = build_registry().get("view.set_camera").examples[1]  # type: ignore[union-attr]
CSV = "spin_a,spin_b,D_obs_Hz,sigma_Hz\nH2,H3,-1124.6,0.5\n"
EVERY_OPERATION: list[Step] = [
    ("render.describe_view", lambda r: {}, "robot", None),
    ("project.open_example", lambda r: {"name": "biphenyl-synthetic", "expected_science_revision": r}, "robot", None),
    ("project.describe", lambda r: {}, "robot", None),
    ("fit.preview", lambda r: {"phi": {"value": 37.0, "unit": "deg"}}, "robot", None),
    ("view.select", lambda r: {"ids": ["cpl_000001"]}, "robot", None),
    ("view.highlight", lambda r: {"ids": ["cpl_000002", "spn_000003"]}, "robot", None),
    ("view.set_layers", lambda r: {"labels": True, "bonds": True, "couplings": False}, "robot", None),
    ("view.set_camera", lambda r: dict(CAMERA), "robot", None),
    ("render.scene", lambda r: {}, "robot", None),
    ("render.view_svg", lambda r: {}, "robot", None),
    ("fit.run", lambda r: {"expected_science_revision": r}, "robot", None),
    ("job.wait", lambda r: {"job_id": "job_000001", "timeout_s": 30}, "robot", None),
    ("job.status", lambda r: {"job_id": "job_000001"}, "robot", None),
    ("job.list", lambda r: {}, "robot", None),
    ("run.list", lambda r: {}, "robot", None),
    ("run.get", lambda r: {"run_id": "run_000001"}, "robot", None),
    ("job.cancel", lambda r: {"job_id": "job_000001"}, "robot", None),
    ("model.set", lambda r: {**JUMP, "expected_science_revision": r}, "robot", None),
    ("history.log", lambda r: {}, "robot", None),
    ("history.undo", lambda r: {"expected_science_revision": r}, "robot", None),
    ("history.redo", lambda r: {"expected_science_revision": r}, "robot", None),
    ("couplings.reconcile", lambda r: {"csv": CSV}, "robot", None),
    (
        "couplings.import",
        lambda r: {
            "csv": CSV,
            "confirmed_mapping": {"H2": "spn_000001", "H3": "spn_000002"},
            "expected_science_revision": r,
        },
        "robot",
        None,
    ),
    ("project.export", lambda r: {}, "robot", None),
    (
        "proposal.create",
        lambda r: {"steps": [{"operation": "history.undo", "args": {"expected_science_revision": r}}]},
        "robot",
        None,
    ),
    ("proposal.list", lambda r: {}, "robot", None),
    ("proposal.get", lambda r: {"proposal_id": "prp_000001"}, "robot", None),
    ("proposal.accept", lambda r: {"proposal_id": "prp_000001"}, "robot", "CAPABILITY_DENIED"),  # not human
    ("proposal.accept", lambda r: {"proposal_id": "prp_000001"}, "user", None),  # the human accepts
    (
        "proposal.create",
        lambda r: {"steps": [{"operation": "history.redo", "args": {"expected_science_revision": r}}]},
        "robot",
        None,
    ),
    ("proposal.reject", lambda r: {"proposal_id": "prp_000002", "reason": "keep it undone"}, "user", None),
    ("project.load", lambda r: {"text": ethane_document(), "expected_science_revision": r}, "robot", None),
    (
        "project.import_xyz",
        lambda r: {"xyz": ETHANE_XYZ, "name": "ethane", "expected_science_revision": r},
        "robot",
        None,
    ),
    ("molecule.set_torsion", lambda r: {"torsion": [2, 0, 1, 5], "expected_science_revision": r}, "robot", None),
]


def test_every_operation_returns_the_same_envelope_on_both_adapters(server: Server) -> None:
    """04 §7 "Contract": every registry operation succeeds at least once in one stateful sequence,
    with the expected outcome at every step, and gives identical envelopes over HTTP and in-process
    (timestamps normalized). Refusals appear only where a step expects one (round 37)."""
    names = set(build_registry().names)
    assert {name for name, *_ in EVERY_OPERATION} == names
    session = new_session()
    py = {"robot": client(session, ROBOT), "user": client(session, USER)}
    revision = 0
    succeeded: set[str] = set()
    for name, make, token, expect in EVERY_OPERATION:
        args = make(revision)
        over_http = server.call(name, args, token=token)
        in_process = py[token].call(name, args)
        assert normalized(over_http) == normalized(in_process), name
        if expect is None:
            assert over_http["ok"], (name, over_http)
            succeeded.add(name)
            revision = over_http["revisions"]["science"]
        else:
            assert over_http["error"]["code"] == expect, (name, over_http)
    assert succeeded == names  # every operation's success path ran on both adapters


def test_two_clients_at_the_same_revision_lose_no_update(server: Server) -> None:
    """04 §7 "Concurrency": a human edit and a robot edit at the same revision; one applies, the
    other gets REVISION_CONFLICT, and nothing is lost or overwritten."""
    ok(server.call("project.open_example", OPEN))
    first = server.call("model.set", {**JUMP, "expected_science_revision": 1})  # the human
    wide = {**JUMP, "kind": "rigid", "phi_domain": [{"value": 0.0, "unit": "deg"}, {"value": 180.0, "unit": "deg"}]}
    second = server.call("model.set", {**wide, "expected_science_revision": 1}, token="robot")
    assert first["ok"] and second["error"]["code"] == "REVISION_CONFLICT"
    assert second["error"]["details"]["current_science_revision"] == 2
    model = ok(server.call("project.describe"))["model"]
    assert model["kind"] == "jump4"  # the first edit stands; the second never applied
