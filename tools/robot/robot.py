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

Tutorial scenario (``--scenario tutorial``, M3 step 4b; 04 §7 "Robot user": the biphenyl
tutorial, through HTTP registry calls only, from the user's files):

1. ``project.import_xyz`` the user's geometry (``--xyz``), named after the file as the page does;
2. ``couplings.reconcile`` the user's couplings (``--csv``): no label matches the imported protons
   (named by atom number), so the robot **confirms the mapping** itself, from the atom list in the
   XYZ file's comment line and each spin's atom index; it checks the diff under that mapping and
   ``couplings.import``s exactly that mapping at the diff's revision;
3. **binds the torsion** (``molecule.set_torsion``, ``--torsion``) and sets the model for imported
   geometry (rigid, order c2z, the input frame, the domain ``--domain``);
4. ``fit.preview`` at φ; the **profile fit** (``fit.run`` with intervals, a job, then ``run.get``);
5. **selects the worst coupling** (largest |residual/σ|), renders the view (``render.view_svg``;
   SVG, the M2 audit's recorded deviation from "PNG") and ``project.export``s the project.

The report carries what the page's path must equal (tests compare them): the science hash, the
fit, the selected coupling and the exported project.

    python -I tools/robot/robot.py --ready-file DIR/serve.ready.json --scenario tutorial \
        --xyz datasets/biphenyl-synthetic/biphenyl.xyz --csv datasets/biphenyl-synthetic/tutorial-couplings.csv

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
    ready = json.loads(ready_file.read_text(encoding="utf-8"))
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
    ready = json.loads(ready_file.read_text(encoding="utf-8"))
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


#: The tutorial's model for imported geometry (dipolar_app.science: rigid, c2z or c1, input frame).
TUTORIAL_MODEL = {"kind": "rigid", "order": "c2z", "frame": "input"}


def _atom_names(xyz: str) -> list[str]:
    """The atom names listed in the XYZ comment line ("…; atoms: C1 C2 … H6'"), in file order."""
    comment = xyz.splitlines()[1] if len(xyz.splitlines()) > 1 else ""
    _, _, listed = comment.partition("atoms:")
    names = listed.split()
    if not names:
        raise RobotError("the XYZ comment line does not list the atom names, so the mapping cannot be confirmed")
    return names


def run_tutorial(
    ready_file: Path, xyz_path: Path, csv_path: Path, torsion: list[int], domain: tuple[float, float], phi_deg: float
) -> dict[str, Any]:
    ready = json.loads(ready_file.read_text(encoding="utf-8"))
    robot = Client(ready["base_url"], ready["tokens"]["robot"])
    if robot.instance().get("instance_id") != ready["instance_id"]:
        raise RobotError("the ready file does not describe the server on its port")
    xyz = xyz_path.read_text(encoding="utf-8")
    csv = csv_path.read_text(encoding="utf-8")

    # 1. Create the project from the geometry, named as the page names it (the file's stem).
    revision = robot.call("render.describe_view")["science_revision"]
    name = xyz_path.name[:-4] if xyz_path.name.lower().endswith(".xyz") else xyz_path.name
    revision = robot.call(
        "project.import_xyz", {"xyz": xyz, "name": name or "Imported geometry", "expected_science_revision": revision}
    )["science_revision"]

    # 2. Import the couplings: confirm the mapping, check its diff, import exactly that.
    proposed = robot.call("couplings.reconcile", {"csv": csv})
    atoms = _atom_names(xyz)
    spin_of_atom = {s["atom"]: s["id"] for s in robot.call("project.describe")["spins"]}
    labels = sorted(set(proposed["unmatched_labels"]) | set(proposed["proposed_mapping"]))
    mapping = {}
    for label in labels:
        if label not in atoms or atoms.index(label) not in spin_of_atom:
            raise RobotError(f"no imported proton for the file's label {label!r}")
        mapping[label] = spin_of_atom[atoms.index(label)]
    diff = robot.call("couplings.reconcile", {"csv": csv, "mapping": mapping})
    if not diff["complete"] or diff["removed"]:
        raise RobotError(
            f"the mapping does not reconcile completely: {diff['unmatched_labels']} {diff['unresolved_pairs']}"
        )
    revision = robot.call(
        "couplings.import",
        {"csv": csv, "confirmed_mapping": mapping, "expected_science_revision": diff["science_revision"]},
    )["science_revision"]

    # 3. Bind the torsion; the model for imported geometry.
    revision = robot.call("molecule.set_torsion", {"torsion": torsion, "expected_science_revision": revision})[
        "science_revision"
    ]
    lo, hi = domain
    revision = robot.call(
        "model.set",
        {
            **TUTORIAL_MODEL,
            "phi_domain": [{"value": lo, "unit": "deg"}, {"value": hi, "unit": "deg"}],
            "expected_science_revision": revision,
        },
    )["science_revision"]
    project = robot.call("project.describe")
    if not project["ready_to_fit"]:
        raise RobotError(f"not ready to fit: {project['not_ready_reason']}")

    # 4. Preview; the profile fit as a job.
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
    fit = robot.call("run.get", {"run_id": waited["job"]["run_id"]})["result"]

    # 5. Select the worst coupling, render, export.
    worst = max(fit["couplings"], key=lambda c: abs(c["normalized_residual"]))
    robot.call("view.select", {"ids": [worst["id"]]})
    view = robot.call("render.describe_view")
    if [s["id"] for s in view["selection"]] != [worst["id"]]:
        raise RobotError("the selection is not visible in render.describe_view")
    svg = robot.call("render.view_svg")["svg"]
    if f'data-id="{worst["id"]}"' not in svg:
        raise RobotError("the selected coupling is not drawn in render.view_svg")
    exported = robot.call("project.export")
    return {
        "ok": True,
        "scenario": "tutorial",
        "contract_version": ready["contract_version"],
        "mapping": mapping,
        "science_hash": project["science_hash"],
        "science_revision": revision,
        "estimand": project["estimand"],
        "preview": {"phi": preview["phi"], "chi2": preview["chi2"], "order": preview["order"]},
        "fit": {k: fit[k] for k in ("theta", "order", "chi2", "nu", "intervals", "stderr", "validity") if k in fit},
        "worst_coupling": {
            "id": worst["id"],
            "label": worst["label"],
            "normalized_residual": worst["normalized_residual"],
        },
        "svg_bytes": len(svg.encode()),
        "exported": exported,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ready-file", type=Path, required=True)
    parser.add_argument("--phi", type=float, default=37.0, help="torsion for fit.preview, degrees")
    parser.add_argument("--scenario", choices=("m0", "m2", "tutorial"), default="m0")
    parser.add_argument("--xyz", type=Path, help="tutorial: the user's geometry")
    parser.add_argument("--csv", type=Path, help="tutorial: the user's couplings")
    parser.add_argument("--torsion", type=int, nargs=4, default=[1, 0, 6, 7], help="tutorial: atoms a i j b")
    parser.add_argument("--domain", type=float, nargs=2, default=[-90.0, 0.0], help="tutorial: φ domain, degrees")
    ns = parser.parse_args()
    try:
        if ns.scenario == "tutorial":
            if ns.xyz is None or ns.csv is None:
                raise RobotError("the tutorial needs --xyz and --csv")
            report = run_tutorial(ns.ready_file, ns.xyz, ns.csv, ns.torsion, tuple(ns.domain), ns.phi)
        elif ns.scenario == "m2":
            report = run_m2(ns.ready_file, ns.phi)
        else:
            report = run(ns.ready_file, ns.phi)
    except (RobotError, OSError, KeyError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
