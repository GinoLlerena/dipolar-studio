"""The scripted robot user (04 §7, §8.6): a non-LLM client that drives the app over HTTP only.

It uses the Python standard library alone, so it runs in a clean process with no frontend,
browser or dipolar packages (CI runs it with ``python -I``). M0 scenario:

1. read the ready file (port and the robot's credential), check that the instance answering on the
   port is the one the ready file names (a stale file or a reused port fails here), then check the
   registry;
2. ``project.open_example`` at the science revision read from ``render.describe_view``;
3. ``fit.preview`` at the requested φ;
4. ``view.select`` the coupling with the largest |normalized residual|;
5. ``render.describe_view`` and check that the selection is visible there.

M2 scenario (``--scenario m2``, the M2 exit audit; 04 §7 "Robot user" and "Proposals"):

1. as the ``robot`` (apply tier): open the example; write its couplings as a CSV, as a user would
   supply their file; ``couplings.reconcile`` it and ``couplings.import`` it under the proposed
   mapping, once confirmed complete;
2. ``fit.preview`` at φ; ``fit.run`` with profile intervals, a job: ``job.wait`` until it finishes,
   then ``run.get``;
3. ``view.select`` and ``view.highlight`` the coupling with the largest |normalized residual| of
   the fit; ``render.describe_view`` must reflect the current run, the selection and the highlight,
   and ``render.view_svg`` must draw it;
4. ``project.export``;
5. as the ``agent`` (propose tier): a direct science change must be refused
   (``PROPOSAL_REQUIRED``), and ``proposal.create`` submits a two-step change set (the jump model,
   then a fit). Acceptance is a human's, so the test accepts it, not the robot.

Prints one JSON report on stdout and exits 0 on success, 1 on any failed step.

    python -I tools/robot/robot.py --ready-file DIR/serve.ready.json --phi 36.98502906633521
    python -I tools/robot/robot.py --ready-file DIR/serve.ready.json --scenario m2
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


class RobotError(Exception):
    pass


class Client:
    def __init__(self, base_url: str, token: str) -> None:
        self.base_url = base_url
        self.token = token

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        data = None if body is None else json.dumps(body, allow_nan=False).encode()
        request = urllib.request.Request(self.base_url + path, data=data, method=method)
        request.add_header("Authorization", f"Bearer {self.token}")
        if data is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload: Any = json.loads(response.read())
        except urllib.error.HTTPError as exc:
            payload = json.loads(exc.read())
        if not isinstance(payload, dict):
            raise RobotError(f"{path} did not return a JSON object")
        return payload

    def instance(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/instance")

    def registry(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/registry")

    def envelope(self, name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._request("POST", f"/api/v1/ops/{name}", {"args": args or {}})

    def call(self, name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
        envelope = self.envelope(name, args)
        if not envelope.get("ok"):
            raise RobotError(f"{name} failed: {envelope.get('error')}")
        result: dict[str, Any] = envelope["result"]
        return result


def run(ready_file: Path, phi_deg: float) -> dict[str, Any]:
    ready = json.loads(ready_file.read_text("utf-8"))
    client = Client(ready["base_url"], ready["tokens"]["robot"])

    try:
        answered = client.instance().get("instance_id")
    except (RobotError, OSError, ValueError):
        answered = None
    if answered != ready["instance_id"]:
        raise RobotError("the ready file does not describe the server on its port (stopped, or the port was reused)")

    names = [op["name"] for op in client.registry()["operations"]]
    missing = {"project.open_example", "fit.preview", "view.select", "render.describe_view"} - set(names)
    if missing:
        raise RobotError(f"registry lacks {sorted(missing)}")

    view = client.call("render.describe_view")
    opened = client.call(
        "project.open_example",
        {"name": "biphenyl-synthetic", "expected_science_revision": view["science_revision"]},
    )
    preview = client.call("fit.preview", {"phi": {"value": phi_deg, "unit": "deg"}})
    if preview["science_revision"] != opened["science_revision"]:
        raise RobotError("the preview does not reflect the project the robot opened")

    worst = max(preview["couplings"], key=lambda c: abs(c["normalized_residual"]))
    selected = client.call("view.select", {"ids": [worst["id"]]})
    view = client.call("render.describe_view")
    if [s["id"] for s in view["selection"]] != [worst["id"]]:
        raise RobotError("the selection is not visible in render.describe_view")

    return {
        "ok": True,
        "contract_version": ready["contract_version"],
        "opened": opened,
        "preview": preview,
        "worst_coupling": {
            "id": worst["id"],
            "label": worst["label"],
            "normalized_residual": worst["normalized_residual"],
        },
        "select": selected,
        "view": view,
    }


JUMP = {
    "kind": "jump4",
    "order": "bisector-diagonal",
    "frame": "bisector",
    "phi_domain": [{"value": 0.0, "unit": "deg"}, {"value": 90.0, "unit": "deg"}],
}


def _csv(project: dict[str, Any]) -> str:
    """The project's couplings as a user's CSV file, in the dataset's format: spin labels, the
    symmetry class and its multiplicity, D and σ in Hz."""
    label = {s["id"]: s["label"] for s in project["spins"]}
    rows = ["spin_a,spin_b,equivalent_pairs,multiplicity,D_obs_Hz,sigma_Hz"]
    for c in project["couplings"]:
        rows.append(
            f"{label[c['spin_a']]},{label[c['spin_b']]},{' '.join(c['equivalent_pairs'])},{c['multiplicity']},"
            f"{c['value']['value']!r},{c['sigma']['value']!r}"
        )
    return "\n".join(rows) + "\n"


def run_m2(ready_file: Path, phi_deg: float) -> dict[str, Any]:
    ready = json.loads(ready_file.read_text("utf-8"))
    robot = Client(ready["base_url"], ready["tokens"]["robot"])
    agent = Client(ready["base_url"], ready["tokens"]["agent"])
    if robot.instance().get("instance_id") != ready["instance_id"]:
        raise RobotError("the ready file does not describe the server on its port")

    revision = robot.call("render.describe_view")["science_revision"]
    revision = robot.call(
        "project.open_example", {"name": "biphenyl-synthetic", "expected_science_revision": revision}
    )["science_revision"]
    csv = _csv(robot.call("project.describe"))
    reconciled = robot.call("couplings.reconcile", {"csv": csv})
    if not reconciled["complete"]:
        raise RobotError(
            f"the CSV does not reconcile: {reconciled['unmatched_labels']} {reconciled['unresolved_pairs']}"
        )
    imported = robot.call(
        "couplings.import",
        {"csv": csv, "confirmed_mapping": reconciled["proposed_mapping"], "expected_science_revision": revision},
    )
    revision = imported["science_revision"]

    preview = robot.call("fit.preview", {"phi": {"value": phi_deg, "unit": "deg"}})
    job = robot.call("fit.run", {"intervals": True, "expected_science_revision": revision})["job"]
    for _ in range(40):  # at most 20 minutes; each wait is bounded by the server (≤ 30 s)
        waited = robot.call("job.wait", {"job_id": job["id"], "timeout_s": 30})
        if waited["finished"]:
            break
    else:
        raise RobotError(f"{job['id']} did not finish")
    if waited["job"]["status"] != "succeeded":
        raise RobotError(f"{job['id']} {waited['job']['status']}: {waited['job']['error']}")
    run = robot.call("run.get", {"run_id": waited["job"]["run_id"]})
    fit = run["result"]

    worst = max(fit["couplings"], key=lambda c: abs(c["normalized_residual"]))
    robot.call("view.select", {"ids": [worst["id"]]})
    robot.call("view.highlight", {"ids": [worst["id"]]})
    view = robot.call("render.describe_view")
    if view["run"] != {"run_id": run["run"]["id"], "stale": False, "available": True}:
        raise RobotError(f"describe_view does not reflect the current run: {view['run']}")
    if [s["id"] for s in view["selection"]] != [worst["id"]] or [h["id"] for h in view["highlights"]] != [worst["id"]]:
        raise RobotError("the selection or the highlight is not visible in render.describe_view")
    svg = robot.call("render.view_svg")["svg"]
    if f'data-id="{worst["id"]}"' not in svg:
        raise RobotError("the highlighted coupling is not drawn in render.view_svg")
    exported = robot.call("project.export")

    refused = agent.envelope("model.set", {**JUMP, "expected_science_revision": revision})
    if refused.get("ok") or refused["error"]["code"] != "PROPOSAL_REQUIRED":
        raise RobotError(f"the agent changed the science directly: {refused}")
    proposal = agent.call(
        "proposal.create",
        {
            "steps": [
                {"operation": "model.set", "args": {**JUMP, "expected_science_revision": revision}},
                {"operation": "fit.run", "args": {"expected_science_revision": revision + 1}},
            ],
            "note": "compare with the four-site jump model",
        },
    )["proposal"]
    return {
        "ok": True,
        "scenario": "m2",
        "contract_version": ready["contract_version"],
        "reconciled": {
            "complete": reconciled["complete"],
            "added": len(reconciled["added"]),
            "removed": len(reconciled["removed"]),
        },
        "imported": imported,
        "preview": preview,
        "job": waited["job"],
        "run": run["run"],
        "fit": fit,
        "worst_coupling": {"id": worst["id"], "normalized_residual": worst["normalized_residual"]},
        "view": view,
        "svg_bytes": len(svg.encode()),
        "exported": exported,
        "proposal": proposal,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ready-file", type=Path, required=True)
    parser.add_argument("--phi", type=float, default=37.0, help="torsion for fit.preview, degrees")
    parser.add_argument("--scenario", choices=("m0", "m2"), default="m0")
    ns = parser.parse_args()
    try:
        report = run_m2(ns.ready_file, ns.phi) if ns.scenario == "m2" else run(ns.ready_file, ns.phi)
    except (RobotError, OSError, KeyError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
