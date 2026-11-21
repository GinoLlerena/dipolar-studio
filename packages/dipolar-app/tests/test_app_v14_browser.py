"""V1.4, the browser and the robot (docs/phase2/v1.4-browser.md, E-1 to E-7): the server side.

These gate tests were frozen before the implementation. The browser side is in
``web/e2e/fixed.spec.ts`` and ``web/e2e/fixed-tutorial.spec.ts``, and the fail-closed comparison
of fixed-geometry runs in ``web/tests/compare.test.ts``.
"""

from __future__ import annotations

import csv as csvlib
import io
import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from conftest import ROOT, Server, client, new_session
from test_app_v13_fixed import (
    C2V_AXES,
    DATA,
    FIXED,
    IDENTITY,
    benzene_draft,
    benzene_orbit,
    benzene_rows,
    by_label,
    csv_of,
    fixed_benzene,
    import_csv,
    ok,
    refused,
    rev,
    ring,
    set_model,
    set_symmetry,
    symmetry,
    xyz_text,
)

DCB = ROOT / "datasets" / "dichlorobenzene-synthetic"
ROBOT_SCRIPT = ROOT / "tools" / "robot" / "robot.py"
#: D6h benzene with its ring in the input yz plane: z′ = input x (the normal), x′ = input y.
YZ_AXES = [[0.0, 1.0, 0.0], [0.0, 0.0, 1.0], [1.0, 0.0, 0.0]]


def old_schemas() -> dict[str, Any]:
    old = json.loads((DATA / "contract-0.10.0.json").read_text(encoding="utf-8"))
    return {o["name"]: o["output_schema"] for o in old["operations"]}


def _validate(instance: Any, schema: dict[str, Any]) -> None:
    import jsonschema

    jsonschema.Draft202012Validator(schema).validate(instance)


def import_ring(c: Any, els: list[str], xyz: np.ndarray, name: str = "ring") -> None:
    ok(c.call("project.import_xyz", {"xyz": xyz_text(els, xyz), "name": name, "expected_science_revision": rev(c)}))


def yz_ring() -> tuple[list[str], np.ndarray]:
    """Benzene turned into the input yz plane: (x, y, z) → (z, x, y)."""
    els, xyz = ring()
    return els, xyz[:, [2, 0, 1]]


def fixed_dcb(c: Any) -> dict[str, str]:
    """The tutorial's steps through the Python API: the mapping it confirmed."""
    xyz = (DCB / "dichlorobenzene.xyz").read_text(encoding="utf-8")
    csv = (DCB / "couplings.csv").read_text(encoding="utf-8")
    ok(c.call("project.import_xyz", {"xyz": xyz, "name": "dichlorobenzene", "expected_science_revision": rev(c)}))
    ok(set_symmetry(c, symmetry("D2h")))
    ok(set_model(c, FIXED))
    names = xyz.splitlines()[1].split("atoms:")[1].split()
    spin_of_atom = {s["atom"]: s["id"] for s in ok(c.call("project.describe"))["spins"]}
    mapping = {label: spin_of_atom[names.index(label)] for label in ("H2", "H3", "H5", "H6")}
    diff = ok(c.call("couplings.reconcile", {"csv": csv, "mapping": mapping}))
    assert diff["complete"] and not diff["removed"]
    ok(
        c.call(
            "couplings.import",
            {"csv": csv, "confirmed_mapping": mapping, "expected_science_revision": diff["science_revision"]},
        )
    )
    return mapping


def run_fixed(c: Any) -> dict[str, Any]:
    job = ok(c.call("fit.run", {"expected_science_revision": rev(c)}))["job"]
    waited = ok(c.call("job.wait", {"job_id": job["id"], "timeout_s": 30}))
    assert waited["finished"] and waited["job"]["status"] == "succeeded", waited
    return ok(c.call("run.get", {"run_id": waited["job"]["run_id"]}))


def orbit_from_images(images: list[list[int]], a: int, b: int) -> set[tuple[int, int]]:
    return {(min(p[a], p[b]), max(p[a], p[b])) for p in images}


# --------------------------------------------------------------------------- E-1: no torsion for a fixed project
def test_the_scene_of_a_fixed_project_describes_no_torsion() -> None:
    c = client(new_session())
    fixed_benzene(c)
    scene = ok(c.call("render.scene"))
    assert scene["phi"] is None and scene["phi_source"] is None
    view = ok(c.call("render.describe_view"))
    assert view["phi"] is None and view["phi_source"] is None
    assert not any("torsion" in w for w in view["warnings"]), view["warnings"]
    run_fixed(c)
    scene = ok(c.call("render.scene"))
    assert scene["phi"] is None and scene["phi_source"] is None and scene["fit"] is not None
    assert "φ" not in ok(c.call("render.view_svg"))["svg"]


def test_non_fixed_scenes_keep_the_0_10_0_shape() -> None:
    """The biphenyl example and a torsion-less draft with a declaration (not fixed): no `symmetry`,
    a φ, and the 0.10.0 schemas of render.scene and render.describe_view."""
    schemas = old_schemas()
    c = client(new_session())
    ok(c.call("project.open_example", {"name": "biphenyl-synthetic", "expected_science_revision": rev(c)}))
    draft = client(new_session())
    benzene_draft(draft)
    ok(set_symmetry(draft, symmetry("D6h")))
    for session in (c, draft):
        scene = ok(session.call("render.scene"))
        assert "symmetry" not in scene and scene["phi"] is not None
        _validate(scene, schemas["render.scene"])
        _validate(ok(session.call("render.describe_view")), schemas["render.describe_view"])


# --------------------------------------------------------------------------- E-3: the one-ring Structure view
def test_the_scene_gives_the_group_action_of_a_fixed_project() -> None:
    c = client(new_session())
    xyz = fixed_benzene(c)
    scene = ok(c.call("render.scene"))
    sym = scene["symmetry"]
    assert sym["point_group"] == "D6h"
    np.testing.assert_allclose(sym["origin"]["xyz"], xyz.mean(axis=0), atol=1e-12)
    assert sym["origin"]["unit"] == "Å"
    np.testing.assert_allclose(sym["axes"], IDENTITY, atol=1e-12)
    assert 0 <= sym["max_displacement"]["value"] < 1e-9
    images = sym["images"]
    n = len(scene["atoms"])
    assert len(images) == 24 and all(sorted(p) == list(range(n)) for p in images)
    assert list(range(n)) in images  # the identity
    as_set = {tuple(p) for p in images}
    for p in images:  # closed under composition: a group action
        for q in images:
            assert tuple(p[q[i]] for i in range(n)) in as_set
    index = {a["id"]: k for k, a in enumerate(scene["atoms"])}
    label = {k: a["label"] for k, a in enumerate(scene["atoms"])}
    project = ok(c.call("project.describe"))
    expected = {"H7–H8": "ortho", "H7–H9": "meta", "H7–H10": "para"}
    for coupling in project["couplings"]:
        members = orbit_from_images(images, index[coupling["spin_a"]], index[coupling["spin_b"]])
        assert len(members) == coupling["multiplicity"]
        assert {frozenset((label[a], label[b])) for a, b in members} == benzene_orbit(expected[coupling["label"]])


def test_the_scene_has_no_symmetry_when_the_declaration_is_absent_or_the_model_is_not_fixed() -> None:
    c = client(new_session())
    benzene_draft(c)
    assert "symmetry" not in ok(c.call("render.scene"))
    ok(set_symmetry(c, symmetry("D6h")))
    assert "symmetry" not in ok(c.call("render.scene"))  # declared, but not a fixed-geometry fit


@pytest.mark.parametrize(
    ("case", "axes", "direction", "up"),
    [
        ("xy ring, D6h", IDENTITY, (0.0, 0.0, 1.0), (0.0, 1.0, 0.0)),
        ("yz ring, D6h", YZ_AXES, (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
        # C2 in the plane (z′ = input x): the least spread is y′ = input z, so up is z′.
        ("xy ring, C2v", C2V_AXES, (0.0, 0.0, 1.0), (1.0, 0.0, 0.0)),
    ],
)
def test_the_automatic_camera_shows_the_ring_face_on(
    case: str, axes: list[list[float]], direction: tuple[float, ...], up: tuple[float, ...]
) -> None:
    c = client(new_session())
    els, xyz = yz_ring() if case.startswith("yz") else ring()
    import_ring(c, els, xyz)
    ok(set_symmetry(c, symmetry(case.split(", ")[1], axes)))
    ok(set_model(c, FIXED))
    scene = ok(c.call("render.scene"))
    sym = scene["symmetry"]
    np.testing.assert_allclose(sym["camera_direction"], direction, atol=1e-12)
    np.testing.assert_allclose(sym["camera_up"], up, atol=1e-12)
    camera = scene["camera"]
    assert camera["automatic"] is True
    position, target = np.array(camera["position"]["xyz"]), np.array(camera["target"]["xyz"])
    np.testing.assert_allclose(target, xyz.mean(axis=0), atol=1e-12)
    offset = position - target
    np.testing.assert_allclose(offset / np.linalg.norm(offset), direction, atol=1e-12)
    np.testing.assert_allclose(camera["up"], up, atol=1e-12)
    depths = [a["screen"]["depth"] for a in scene["atoms"]]
    assert all(a["screen"]["visible"] for a in scene["atoms"])
    assert max(depths) - min(depths) <= 1e-9 * max(depths)  # face-on: the ring is square to the view


def test_a_user_camera_is_kept_for_a_fixed_project() -> None:
    c = client(new_session())
    fixed_benzene(c)
    camera = {
        "position": {"xyz": [3.0, 4.0, 12.0], "unit": "Å"},
        "target": {"xyz": [0.0, 0.0, 0.0], "unit": "Å"},
        "up": {"xyz": [0.0, 1.0, 0.0]},
        "fov": {"value": 40.0, "unit": "deg"},
        "near": {"value": 1.0, "unit": "Å"},
        "far": {"value": 40.0, "unit": "Å"},
    }
    view = ok(c.call("render.describe_view"))
    ok(
        c.call(
            "view.set_camera",
            {
                "camera": camera,
                "viewport": {"width": 640, "height": 480},
                "expected_workspace_revision": view["workspace_revision"],
            },
        )
    )
    scene = ok(c.call("render.scene"))
    assert scene["camera"]["automatic"] is False
    assert scene["camera"]["position"]["xyz"] == [3.0, 4.0, 12.0]
    assert "symmetry" in scene  # the frame is still described


def test_the_svg_draws_every_orbit_member_and_the_symmetry_axes() -> None:
    c = client(new_session())
    fixed_benzene(c)
    run_fixed(c)
    svg = ok(c.call("render.view_svg"))["svg"]
    for coupling in ok(c.call("project.describe"))["couplings"]:
        drawn = re.findall(rf'<(?:line|path)[^>]*data-id="{coupling["id"]}"', svg)
        assert len(drawn) == coupling["multiplicity"], coupling["label"]
    for axis in ("x", "y", "z"):
        assert len(re.findall(rf'data-axis="{axis}"', svg)) == 1
    assert "φ" not in svg
    biphenyl = client(new_session())
    ok(biphenyl.call("project.open_example", {"name": "biphenyl-synthetic", "expected_science_revision": 0}))
    assert "data-axis" not in ok(biphenyl.call("render.view_svg"))["svg"]  # unchanged elsewhere


def test_the_parity_fixtures_include_directed_automatic_cameras() -> None:
    from dipolar_app.scene import parity_fixtures

    cases = parity_fixtures()["cases"]
    directed = [k for k in cases if k.get("auto") and k.get("view")]
    assert len(directed) >= 2
    assert any(abs(k["view"]["direction"][2]) < 0.5 for k in directed)  # one not along z
    from test_app_scene import _same

    committed = json.loads((ROOT / "web" / "src" / "scene" / "parity-fixtures.json").read_text(encoding="utf-8"))
    assert [k["name"] for k in committed["cases"]] == [k["name"] for k in cases]
    _same(committed, json.loads(json.dumps(parity_fixtures())), committed["tolerance_px"])


def test_the_default_automatic_camera_is_unchanged() -> None:
    """The biphenyl scene's camera is the one before V1.4 (on +z, up +y)."""
    from dipolar_app.scene import auto_camera

    pts = [(1.0, 2.0, 0.5), (-1.0, 0.0, -0.5), (0.3, -2.0, 0.1)]
    base = auto_camera(pts, 640, 480)
    directed = auto_camera(pts, 640, 480, direction=(0.0, 0.0, 1.0), up=(0.0, 1.0, 0.0))
    assert base == directed
    assert base.up == (0.0, 1.0, 0.0) and base.position[:2] == base.target[:2]


# --------------------------------------------------------------------------- E-5: the Cs suggestion
def suggest(c: Any) -> dict[str, Any]:
    return ok(c.call("molecule.suggest_symmetry"))


def test_a_planar_ring_without_a_declaration_is_suggested_cs() -> None:
    c = client(new_session())
    benzene_draft(c)
    out = suggest(c)
    s = out["suggestion"]
    assert s["point_group"] == "Cs" and s["medium"] == "achiral-uniaxial"
    assert s["tolerance"] == {"value": 0.01, "unit": "Å"}
    np.testing.assert_allclose(s["axes"], IDENTITY, atol=1e-12)
    assert out["plane"]["max_distance"]["value"] < 1e-12
    assert "not validated" in out["reason"]
    assert out["science_revision"] == rev(c)
    ok(set_symmetry(c, s))  # declaring it validates it
    assert ok(c.call("molecule.declarations"))["symmetry"]["point_group"] == "Cs"


def test_the_suggestion_follows_a_tilted_plane() -> None:
    angle = math.radians(35.0)
    rot = np.array([[1.0, 0.0, 0.0], [0.0, math.cos(angle), -math.sin(angle)], [0.0, math.sin(angle), math.cos(angle)]])
    els, xyz = ring()
    c = client(new_session())
    import_ring(c, els, xyz @ rot.T + np.array([0.4, -1.0, 2.0]))
    s = suggest(c)["suggestion"]
    axes = np.array(s["axes"])
    np.testing.assert_allclose(axes @ axes.T, np.eye(3), atol=1e-9)
    assert np.linalg.det(axes) == pytest.approx(1.0, abs=1e-9)
    normal = rot @ np.array([0.0, 0.0, 1.0])
    np.testing.assert_allclose(axes[2], normal * np.sign(normal[np.argmax(np.abs(normal))]), atol=1e-9)
    np.testing.assert_allclose(axes[0], [1.0, 0.0, 0.0], atol=1e-9)  # input x is least aligned with the normal
    ok(set_symmetry(c, s))


@pytest.mark.parametrize(("group", "suggested"), [("C1", True), ("Cs", False), ("D6h", False)])
def test_the_suggestion_is_given_only_without_a_group_beyond_c1(group: str, suggested: bool) -> None:
    c = client(new_session())
    benzene_draft(c)
    ok(set_symmetry(c, symmetry(group)))
    out = suggest(c)
    assert (out["suggestion"] is not None) is suggested, out
    assert out["reason"]


@pytest.mark.parametrize(
    ("lift", "declared_tolerance", "suggested"),
    [(0.05, None, False), (0.005, None, True), (0.05, 0.1, True)],
)
def test_the_plane_test_uses_the_tolerance(lift: float, declared_tolerance: float | None, suggested: bool) -> None:
    els, xyz = ring()
    xyz = xyz.copy()
    xyz[6, 2] += lift  # one proton out of the plane
    c = client(new_session())
    import_ring(c, els, xyz)
    if declared_tolerance is not None:
        ok(set_symmetry(c, symmetry("C1", tolerance={"value": declared_tolerance, "unit": "Å"})))
    out = suggest(c)
    assert (out["suggestion"] is not None) is suggested, out
    assert out["tolerance"]["value"] == (declared_tolerance or 0.01)


@pytest.mark.parametrize(
    "atoms",
    [
        [("C", 0.0, 0.0, 0.0), ("C", 1.2, 0.0, 0.0), ("H", -1.06, 0.0, 0.0), ("H", 2.26, 0.0, 0.0)],  # two spins
        [("H", 0.0, 0.0, 0.0), ("H", 1.0, 0.0, 0.0), ("H", 2.0, 0.0, 0.0), ("C", 0.0, 1.0, 0.3)],  # collinear
    ],
)
def test_no_plane_no_suggestion(atoms: list[tuple[str, float, float, float]]) -> None:
    c = client(new_session())
    import_ring(c, [a[0] for a in atoms], np.array([a[1:] for a in atoms]))
    out = suggest(c)
    assert out["suggestion"] is None and out["plane"] is None and out["reason"]


def test_the_template_has_no_suggestion_and_any_tier_may_ask() -> None:
    from conftest import AGENT

    c = client(new_session())
    ok(c.call("project.open_example", {"name": "biphenyl-synthetic", "expected_science_revision": 0}))
    out = suggest(c)
    assert out["suggestion"] is None and "template" in out["reason"]
    session = new_session()
    owner, agent = client(session), client(session, AGENT)
    benzene_draft(owner)
    assert ok(agent.call("molecule.suggest_symmetry"))["suggestion"]["point_group"] == "Cs"
    refused(client(new_session()).call("molecule.suggest_symmetry"), "NO_PROJECT")


def test_suggest_symmetry_has_python_http_parity(server: Server) -> None:
    from conftest import USER

    py = client(new_session(), USER)
    els, xyz = ring()
    sequence: list[tuple[str, dict[str, Any]]] = [
        ("project.import_xyz", {"xyz": xyz_text(els, xyz), "name": "benzene", "expected_science_revision": 0}),
        ("molecule.suggest_symmetry", {}),
        ("molecule.set_symmetry", {"symmetry": symmetry("D6h"), "expected_science_revision": 1}),
        ("molecule.suggest_symmetry", {}),
    ]
    for name, args in sequence:
        assert server.call(name, args, token="user") == py.call(name, args), name


# --------------------------------------------------------------------------- E-1: the contract
def test_the_contract_is_0_12_0_and_says_what_changed() -> None:
    from dipolar_app.operations import build_registry
    from dipolar_app.registry import CONTRACT_CHANGES, CONTRACT_VERSION

    assert CONTRACT_VERSION == "0.12.0"
    entry = next(e for e in CONTRACT_CHANGES if e["version"] == "0.12.0")
    assert entry["breaking"] is True
    assert "molecule.suggest_symmetry" in build_registry().names
    snapshot = json.loads((ROOT / "packages" / "dipolar-app" / "registry.snapshot.json").read_text(encoding="utf-8"))
    assert snapshot["contract_version"] == "0.12.0"
    assert "## 0.12.0" in (ROOT / "docs" / "contract-changelog.md").read_text(encoding="utf-8")


# --------------------------------------------------------------------------- E-6: the tutorial's dataset
def test_the_dataset_is_what_its_generator_writes(tmp_path: Path) -> None:
    work = tmp_path / "dcb"
    shutil.copytree(DCB, work, ignore=shutil.ignore_patterns("__pycache__"))
    for name in ("dichlorobenzene.xyz", "couplings.csv", "truth.json"):
        (work / name).unlink()
    subprocess.run([sys.executable, "-I", "generate.py"], cwd=work, check=True, timeout=60)
    for name in ("dichlorobenzene.xyz", "couplings.csv"):  # the user's files: byte for byte
        assert (work / name).read_bytes() == (DCB / name).read_bytes(), name
    # truth.json carries a least-squares fit, whose last bits depend on the platform's linear
    # algebra (CI, Linux): its numbers are compared to 1e-12 relative, everything else exactly.
    _same_json(json.loads((work / "truth.json").read_text(encoding="utf-8")), _truth())


def _truth() -> Any:
    return json.loads((DCB / "truth.json").read_text(encoding="utf-8"))


def _same_json(a: Any, b: Any, path: str = "truth") -> None:
    if isinstance(a, dict):
        assert isinstance(b, dict) and a.keys() == b.keys(), path
        for k in a:
            _same_json(a[k], b[k], f"{path}.{k}")
    elif isinstance(a, list):
        assert isinstance(b, list) and len(a) == len(b), path
        for k, (x, y) in enumerate(zip(a, b, strict=True)):
            _same_json(x, y, f"{path}[{k}]")
    elif isinstance(a, float) and isinstance(b, float):
        assert math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-300), (path, a, b)
    else:
        assert a == b and type(a) is type(b), (path, a, b)


def _spec() -> dict[str, Any]:
    spec: dict[str, Any] = json.loads((DCB / "expected" / "spec.json").read_text(encoding="utf-8"))
    return spec


def test_the_engine_recovers_the_reference_fit() -> None:
    from scipy.stats import chi2 as chi2_dist

    truth = json.loads((DCB / "truth.json").read_text(encoding="utf-8"))
    ref = truth["reference_fit_noisy"]
    tol = _spec()["tolerances"]["reference"]
    c = client(new_session())
    fixed_dcb(c)
    result = run_fixed(c)["result"]
    by = {k["name"]: k for k in result["components"]}
    assert result["n_obs"] == 3 and result["rank"]["required"] == 2 and result["rank"]["verified"]
    assert by["Szz"]["estimate"] == pytest.approx(ref["Szz"], abs=tol["S_atol"])
    assert by["Sxx-Syy"]["estimate"] == pytest.approx(ref["Sxx"] - ref["Syy"], abs=tol["S_atol"])
    (vxx, cxy), (_, vyy) = ref["covariance_Sxx_Syy"]
    assert by["Szz"]["se"] == pytest.approx(math.sqrt(vxx + vyy + 2 * cxy), rel=tol["stderr_rtol"])
    assert by["Sxx-Syy"]["se"] == pytest.approx(math.sqrt(vxx + vyy - 2 * cxy), rel=tol["stderr_rtol"])
    assert {k["name"] for k in result["components"] if k["status"] == "fixed-by-symmetry"} == {"Sxy", "Sxz", "Syz"}
    adequacy = result["adequacy"]
    assert adequacy["nu"] == 1 and adequacy["status"] == "given"
    assert adequacy["chi2"] == pytest.approx(ref["chi2"], rel=tol["objective_rtol"])
    assert adequacy["p_value"] == pytest.approx(float(chi2_dist.sf(ref["chi2"], 1)), rel=tol["objective_rtol"])
    assert [r["multiplicity"] for r in result["rows"]] == [2, 2, 2]


def test_the_engine_recovers_the_truth_without_noise() -> None:
    truth = json.loads((DCB / "truth.json").read_text(encoding="utf-8"))
    t = truth["truth"]
    rows = list(csvlib.DictReader(io.StringIO((DCB / "couplings.csv").read_text(encoding="utf-8"))))
    out = io.StringIO()
    writer = csvlib.DictWriter(out, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    for row, value in zip(rows, truth["noiseless_Hz"], strict=True):
        writer.writerow({**row, "D_obs_Hz": repr(value)})
    c = client(new_session())
    xyz = (DCB / "dichlorobenzene.xyz").read_text(encoding="utf-8")
    ok(c.call("project.import_xyz", {"xyz": xyz, "name": "dcb", "expected_science_revision": 0}))
    ok(set_symmetry(c, symmetry("D2h")))
    ok(set_model(c, FIXED))
    names = xyz.splitlines()[1].split("atoms:")[1].split()
    spin_of_atom = {s["atom"]: s["id"] for s in ok(c.call("project.describe"))["spins"]}
    mapping = {label: spin_of_atom[names.index(label)] for label in ("H2", "H3", "H5", "H6")}
    ok(
        c.call(
            "couplings.import",
            {"csv": out.getvalue(), "confirmed_mapping": mapping, "expected_science_revision": rev(c)},
        )
    )
    by = {k["name"]: k for k in run_fixed(c)["result"]["components"]}
    atol = _spec()["tolerances"]["noiseless_recovery_atol"]["S"]
    assert by["Szz"]["estimate"] == pytest.approx(-t["Sxx"] - t["Syy"], abs=atol)
    assert by["Sxx-Syy"]["estimate"] == pytest.approx(t["Sxx"] - t["Syy"], abs=atol)


def test_the_scene_of_the_tutorial_draws_each_orbit_and_looks_along_z() -> None:
    c = client(new_session())
    fixed_dcb(c)
    run_fixed(c)
    scene = ok(c.call("render.scene"))
    sym = scene["symmetry"]
    assert sym["point_group"] == "D2h" and len(sym["images"]) == 8
    np.testing.assert_allclose(sym["camera_direction"], [0.0, 0.0, 1.0], atol=1e-12)
    index = {a["id"]: k for k, a in enumerate(scene["atoms"])}
    for coupling in scene["couplings"]:
        assert len(orbit_from_images(sym["images"], index[coupling["spin_a"]], index[coupling["spin_b"]])) == 2


# --------------------------------------------------------------------------- E-6: the robot
def _robot(server: Server, env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", str(ROBOT_SCRIPT), "--ready-file", str(server.ready_file), *args],
        capture_output=True,
        text=True,
        timeout=300,
        env=env,
        cwd=ROOT,
        check=False,
    )


def test_the_robot_fixed_tutorial_as_documented(server: Server, clean_env: dict[str, str]) -> None:
    """The fixed-geometry tutorial command of robot.py's docstring, as written, in a clean
    process: it recovers the reference fit, selects the worst row and exports."""
    doc = ROBOT_SCRIPT.read_text(encoding="utf-8")
    command = doc.split("--scenario fixed-tutorial \\\n", 1)[1].split("\n", 1)[0].split()
    assert command[:1] == ["--xyz"], command
    proc = _robot(server, clean_env, "--scenario", "fixed-tutorial", *command)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    report = json.loads(proc.stdout)
    assert report["ok"] and report["scenario"] == "fixed-tutorial"
    assert report["contract_version"] == "0.12.0"
    assert set(report["mapping"]) == {"H2", "H3", "H5", "H6"}
    ref = json.loads((DCB / "truth.json").read_text(encoding="utf-8"))["reference_fit_noisy"]
    by = {k["name"]: k for k in report["fit"]["components"]}
    assert by["Szz"]["estimate"] == pytest.approx(ref["Szz"], abs=1e-8)
    assert report["fit"]["adequacy"]["status"] == "given"
    # The worst row is the para orbit (|z| ≈ 1.38); the view selects it and draws both members.
    assert report["worst_coupling"]["source_labels"] == ["H2", "H5"]
    assert report["selected_arcs"] == 2
    assert report["exported"]["filename"].endswith(".json")
    view = server.call("render.describe_view")["result"]
    assert [s["id"] for s in view["selection"]] == [report["worst_coupling"]["id"]]
    assert view["phi"] is None


def test_the_robot_refuses_a_file_without_atom_names(server: Server, clean_env: dict[str, str], tmp_path: Path) -> None:
    xyz = (DCB / "dichlorobenzene.xyz").read_text(encoding="utf-8").splitlines()
    xyz[1] = "no names here"
    path = tmp_path / "unnamed.xyz"
    path.write_text("\n".join(xyz) + "\n", encoding="utf-8")
    proc = _robot(
        server, clean_env, "--scenario", "fixed-tutorial", "--xyz", str(path), "--csv", str(DCB / "couplings.csv")
    )
    assert proc.returncode == 1
    assert "atom names" in json.loads(proc.stdout)["error"]


# --------------------------------------------------------------------------- E-4: what the page reads
def test_the_page_can_read_every_declaration_of_a_draft() -> None:
    """The symmetry form shows the declaration of a draft (not fixed) through
    molecule.declarations, with its largest displacement; project.describe keeps 0.10.0."""
    c = client(new_session())
    benzene_draft(c)
    ok(set_symmetry(c, symmetry("D6h", tolerance={"value": 0.02, "unit": "Å"})))
    declared = ok(c.call("molecule.declarations"))["symmetry"]
    assert declared["point_group"] == "D6h" and declared["tolerance"]["value"] == 0.02
    assert "max_displacement" in declared
    _validate(ok(c.call("project.describe")), old_schemas()["project.describe"])


def test_leaving_and_entering_fixed_from_the_draft_model() -> None:
    """The model inspector's two moves: a φ-domain model to fixed and back (no rows)."""
    from test_app_v13_fixed import DRAFT

    c = client(new_session())
    benzene_draft(c)
    ok(set_symmetry(c, symmetry("D6h")))
    ok(set_model(c, FIXED))
    assert "phi_domain" not in ok(c.call("project.describe"))["model"]
    ok(set_model(c, DRAFT))
    assert ok(c.call("project.describe"))["model"]["phi_domain"][1]["value"] == 180.0
    ok(set_model(c, FIXED))
    ok(import_csv(c, csv_of(benzene_rows(ring()[1]))))
    labels = by_label(c)
    assert labels["H7"].startswith("spn_")


# --------------------------------------------------------------------------- round 79
def test_r79_the_suggestion_does_not_promise_estimability() -> None:
    """Round 79, finding 5: Cs reduces the model to the in-plane block; which combinations the
    couplings determine is the fit's to say (one coupling of three planar protons has rank 1 of 3)."""
    c = client(new_session())
    benzene_draft(c)
    reason = suggest(c)["reason"]
    assert "is estimable" not in reason and "estimable" not in reason.replace("which combinations", "")
    assert "in-plane" in reason and "the fit" in reason and "not validated" in reason


def _robot_module() -> Any:
    import importlib.util

    spec = importlib.util.spec_from_file_location("robot_under_test", ROBOT_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "names",
    [
        "C1 C2 C3 C4 C5 C6 Cl1 Cl4 H3 H2 H5 H6 H2 H3",  # round 79: duplicated, and more names than atoms
        "C1 C2 C3 C4 C5 C6 Cl1 Cl4 H2 H2 H5 H6",  # a duplicate, as many names as atoms
        "C1 C2 C3 C4 C5 C6 Cl1 Cl4 H2 H3 H5",  # one name short
    ],
)
def test_r79_the_robot_refuses_ambiguous_atom_names_before_any_change(
    server: Server, clean_env: dict[str, str], tmp_path: Path, names: str
) -> None:
    """Round 79, finding 6: one unique name per atom, checked before the project is replaced."""
    xyz = (DCB / "dichlorobenzene.xyz").read_text(encoding="utf-8").splitlines()
    xyz[1] = f"synthetic 1,4-dichlorobenzene (D2h); atoms: {names}"
    path = tmp_path / "ambiguous.xyz"
    path.write_text("\n".join(xyz) + "\n", encoding="utf-8")
    proc = _robot(
        server, clean_env, "--scenario", "fixed-tutorial", "--xyz", str(path), "--csv", str(DCB / "couplings.csv")
    )
    assert proc.returncode == 1, proc.stdout
    assert "atom names" in json.loads(proc.stdout)["error"]
    assert server.call("render.describe_view")["result"]["science_revision"] == 0  # nothing was changed


def test_r79_the_robot_checks_that_everything_it_reports_is_one_science_state() -> None:
    """Round 79, finding 7: a run, view, SVG and export from different science states (another client
    changed a coupling meanwhile) is a failure, not a success."""
    robot = _robot_module()
    good: dict[str, Any] = {
        "project": {"science_revision": 4, "science_hash": "sha256:a"},
        "run": {"run": {"id": "run_000001", "stale": False, "science_hash": "sha256:a", "science_revision": 4}},
        "view": {"science_revision": 4, "run": {"run_id": "run_000001", "stale": False, "available": True}},
        "svg": {"science_revision": 4},
        "exported": {"science_revision": 4, "science_hash": "sha256:a"},
    }
    robot._consistent(**good)  # no error
    bad: list[tuple[str, str, Any]] = [
        ("run", "run", {"id": "run_000001", "stale": True, "science_hash": "sha256:a", "science_revision": 4}),
        ("run", "run", {"id": "run_000001", "stale": False, "science_hash": "sha256:b", "science_revision": 4}),
        ("view", "science_revision", 5),
        ("view", "run", {"run_id": "run_000002", "stale": False, "available": True}),
        ("view", "run", {"run_id": "run_000001", "stale": True, "available": True}),
        ("svg", "science_revision", 5),
        ("exported", "science_hash", "sha256:b"),
        ("exported", "science_revision", 5),
    ]
    for part, key, value in bad:
        altered = json.loads(json.dumps(good))
        altered[part][key] = value
        with pytest.raises(robot.RobotError):
            robot._consistent(**altered)


def test_r79_the_robot_sets_the_view_it_verifies(server: Server, clean_env: dict[str, str]) -> None:
    """Round 79, B: with the couplings layer hidden beforehand, the tutorial still verifies its arcs."""
    view = server.call("render.describe_view")["result"]
    hidden = server.call("view.set_layers", {"labels": True, "bonds": True, "couplings": False})
    assert hidden["ok"], hidden
    assert view["project_open"] is False
    files = ["--xyz", str(DCB / "dichlorobenzene.xyz"), "--csv", str(DCB / "couplings.csv")]
    proc = _robot(server, clean_env, "--scenario", "fixed-tutorial", *files)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert json.loads(proc.stdout)["selected_arcs"] == 2


@pytest.mark.parametrize(("offset", "suggested"), [(0.0135, False), (0.0165, True)])
def test_r79_the_collinearity_rule_is_the_largest_distance_from_the_line(offset: float, suggested: bool) -> None:
    """Round 79, B: spins are collinear when every one lies within the tolerance of their
    least-squares line (here at most 2·offset/3 from it); then no plane is unique."""
    atoms = [("H", 0.0, offset, 0.0), ("H", 1.0, 0.0, 0.0), ("H", 2.0, offset, 0.0), ("C", 1.0, 1.0, 0.0)]
    c = client(new_session())
    import_ring(c, [a[0] for a in atoms], np.array([a[1:] for a in atoms]))
    out = suggest(c)
    assert (out["suggestion"] is not None) is suggested, out


# --------------------------------------------------------------------------- round 80
def test_r80_the_suggestion_claims_nothing_about_a_c1_fit() -> None:
    """Round 80, finding 5: five protons within 0.001 Å of a plane fit C1 with a verified rank; the
    suggestion states the measured distance and what Cs constrains, nothing about C1's rank."""
    c = client(new_session())
    benzene_draft(c)
    reason = suggest(c)["reason"]
    for claim in ("cannot be verified", "withheld", "unverified"):
        assert claim not in reason, reason
    assert "farthest is" in reason and "in-plane block" in reason and "not validated" in reason


class _Injecting:
    """A robot client that runs `action` (once) just before the first call of `before`."""

    def __init__(self, robot: Any, ready: dict[str, Any], before: str, action: Any) -> None:
        self.inner = robot.Client(ready["base_url"], ready["tokens"]["robot"])
        self.before, self.action, self.done = before, action, False

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)

    def call(self, name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
        if name == self.before and not self.done:
            self.done = True
            self.action()
        result: dict[str, Any] = self.inner.call(name, args)
        return result


def _fixed_tutorial_with(server: Server, before: str, action: Any) -> Any:
    robot = _robot_module()
    ready = json.loads(server.ready_file.read_text(encoding="utf-8"))
    client = _Injecting(robot, ready, before, action)
    return robot, lambda: robot.fixed_tutorial(client, ready, DCB / "dichlorobenzene.xyz", DCB / "couplings.csv", "D2h")


def test_r80_the_robot_fits_the_geometry_it_imported(server: Server) -> None:
    """Round 80, finding 3: another client loads a scaled copy of the project between model.set and
    the reconciliation; the robot must fail, not fit the other geometry."""

    def load_scaled() -> None:
        exported = server.call("project.export")["result"]
        document = json.loads(exported["text"])
        for atom in document["project"]["molecule"]["geometry"]["atoms"]:
            for axis in ("x", "y", "z"):
                atom[axis] *= 1.25
        revision = server.call("render.describe_view")["result"]["science_revision"]
        loaded = server.call("project.load", {"text": json.dumps(document), "expected_science_revision": revision})
        assert loaded["ok"], loaded

    robot, run = _fixed_tutorial_with(server, "couplings.reconcile", load_scaled)
    with pytest.raises(robot.RobotError):
        run()


def test_r80_the_robot_fails_when_a_coupling_changes_between_the_fit_and_the_export(server: Server) -> None:
    """Round 80, finding 4: the consistency guard is exercised by the workflow, not only by itself."""

    def change_a_coupling() -> None:
        revision = server.call("render.describe_view")["result"]["science_revision"]
        removed = server.call(
            "couplings.remove", {"coupling_ids": ["cpl_000001"], "expected_science_revision": revision}
        )
        assert removed["ok"], removed

    robot, run = _fixed_tutorial_with(server, "project.export", change_a_coupling)
    with pytest.raises(robot.RobotError):
        run()


def test_r80_the_robot_verifies_the_selected_drawing_it_reports(server: Server) -> None:
    """Round 80, finding 4: the selection cleared between describe_view and view_svg is a failure."""

    def clear() -> None:
        assert server.call("view.select", {"ids": []})["ok"]

    robot, run = _fixed_tutorial_with(server, "render.view_svg", clear)
    with pytest.raises(robot.RobotError):
        run()


def test_r80_the_robot_resets_a_camera_that_hides_the_molecule(server: Server, clean_env: dict[str, str]) -> None:
    """Round 80, B: a valid saved camera pointed away from the molecule survives project
    replacement; the tutorial sets the automatic camera before it verifies the drawing."""
    away = {
        "camera": {
            "position": {"xyz": [0.0, 0.0, 500.0], "unit": "Å"},
            "target": {"xyz": [0.0, 0.0, 1000.0], "unit": "Å"},
            "up": {"xyz": [0.0, 1.0, 0.0]},
            "fov": {"value": 45.0, "unit": "deg"},
            "near": {"value": 1.0, "unit": "Å"},
            "far": {"value": 100.0, "unit": "Å"},
        },
        "viewport": {"width": 640, "height": 480},
        "expected_workspace_revision": server.call("render.describe_view")["result"]["workspace_revision"],
    }
    assert server.call("view.set_camera", away)["ok"]
    files = ["--xyz", str(DCB / "dichlorobenzene.xyz"), "--csv", str(DCB / "couplings.csv")]
    proc = _robot(server, clean_env, "--scenario", "fixed-tutorial", *files)
    assert proc.returncode == 0, proc.stdout + proc.stderr
