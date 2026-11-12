"""M2 step 4: the scene description, describe_view, the SVG renderer and projection parity
(04 D15, D16, §8.4, §8.6)."""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import pytest
from conftest import AGENT, ROOT, VIEWER, client, new_session, run_fit
from dipolar_app.client import LocalClient
from dipolar_app.journal import Journal
from dipolar_app.scene import DEFAULT_PHI_DEG, auto_camera, draw_order, parity_fixtures, project
from dipolar_app.science_ops import ETHANE_XYZ
from dipolar_app.session import Camera, Session, replay

OPEN = {"name": "biphenyl-synthetic", "expected_science_revision": 0}
FIXTURES = ROOT / "web" / "src" / "scene" / "parity-fixtures.json"
SVG = "{http://www.w3.org/2000/svg}"


def deg(value: float) -> dict[str, object]:
    return {"value": value, "unit": "deg"}


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


def camera_args(position: list[float], up: list[float], fov: float = 40.0) -> dict[str, Any]:
    return {
        "camera": {
            "position": {"xyz": position, "unit": "Å"},
            "target": {"xyz": [0.0, 0.0, 0.0], "unit": "Å"},
            "up": {"xyz": up},
            "fov": deg(fov),
            "near": {"value": 0.5, "unit": "Å"},
            "far": {"value": 200.0, "unit": "Å"},
        },
        "viewport": {"width": 640, "height": 480},
    }


# --------------------------------------------------------------------------- the scene
def test_the_scene_describes_the_template_before_any_fit() -> None:
    s, c = opened()
    scene = ok(c.call("render.scene"))
    assert scene["phi_source"] == "default" and scene["phi"] == deg(DEFAULT_PHI_DEG) and scene["run"] is None
    assert scene["camera"]["automatic"] and scene["viewport"] == {"width": 800, "height": 600}
    atoms = scene["atoms"]
    assert [a["id"] for a in atoms] == [sp.id for sp in s.state.project.molecule.spins]  # type: ignore[union-attr]
    assert all(a["screen"]["visible"] for a in atoms) and len(scene["draw_order"]) == 10
    depths = {a["id"]: a["screen"]["depth"] for a in atoms}
    assert [depths[i] for i in scene["draw_order"]] == sorted(depths.values(), reverse=True)  # far to near
    position = {a["id"]: a["position"]["xyz"] for a in atoms}
    for cpl in scene["couplings"]:
        assert cpl["residual"] is None
        assert cpl["length"]["value"] == pytest.approx(math.dist(position[cpl["spin_a"]], position[cpl["spin_b"]]))


def test_the_scene_shows_the_current_run_and_marks_it_stale_after_an_edit() -> None:
    _, c = opened()
    fit = ok(run_fit(c))
    scene = ok(c.call("render.scene"))
    assert scene["phi_source"] == "run" and scene["run"] == {"run_id": "run_000001", "stale": False, "available": True}
    assert scene["phi"]["value"] == pytest.approx(fit["theta"][0]["value"])
    residuals = {x["id"]: x["residual"]["value"] for x in fit["couplings"]}
    assert {x["id"]: x["residual"]["value"] for x in scene["couplings"]} == residuals
    view = ok(c.call("render.describe_view"))
    assert view["run"] == scene["run"] and view["phi_source"] == "run"
    ranked = sorted(residuals.items(), key=lambda kv: -abs(kv[1]))[:5]
    assert [(r["id"], r["residual"]["value"]) for r in view["top_residuals"]] == ranked
    kinds = {"kind": "jump4", "order": "bisector-diagonal", "frame": "bisector", "phi_domain": [deg(0), deg(90)]}
    ok(c.call("model.set", {**kinds, "expected_science_revision": 1}))
    stale = ok(c.call("render.describe_view"))
    assert (
        stale["run"] == {"run_id": "run_000001", "stale": True, "available": True} and stale["phi_source"] == "default"
    )
    assert stale["top_residuals"] == [] and any("stale" in w for w in stale["warnings"])


def test_imported_geometry_has_bonds_and_atom_ids() -> None:
    c = client(new_session())
    ok(
        c.call(
            "project.import_xyz",
            {"xyz": ETHANE_XYZ, "name": "ethane", "torsion": [2, 0, 1, 5], "expected_science_revision": 0},
        )
    )
    scene = ok(c.call("render.scene"))
    ids = [a["id"] for a in scene["atoms"]]
    assert len(ids) == 8 and ids[:2] == ["atm_000001", "atm_000002"] and all(i.startswith("spn_") for i in ids[2:])
    assert len(scene["bonds"]) == 7 and scene["phi_source"] == "imported"


def test_a_described_view_without_a_project() -> None:
    view = ok(client(new_session()).call("render.describe_view"))
    assert not view["project_open"] and view["visible"] == [] and view["warnings"] == ["no project is open"]
    error(client(new_session()).call("render.scene"), "NO_PROJECT")


# --------------------------------------------------------------------------- view commands
def test_view_commands_change_only_the_workspace_and_never_stale_a_run(tmp_path: Path) -> None:
    s, c = opened(tmp_path)
    ok(run_fit(c))
    science = (s.state.science_revision, s.state.science_hash)
    moved = ok(c.call("view.set_camera", camera_args([20.0, 0.0, 0.0], [0.0, 0.0, 1.0])))
    assert moved == {"workspace_revision": 1, "automatic": False}
    assert ok(c.call("view.set_camera", camera_args([20.0, 0.0, 0.0], [0.0, 0.0, 1.0])))["workspace_revision"] == 1
    ok(c.call("view.highlight", {"ids": ["cpl_000001", "spn_000002"]}))
    ok(c.call("view.set_layers", {"labels": False, "bonds": True, "couplings": True}))
    assert (s.state.science_revision, s.state.science_hash) == science
    scene = ok(c.call("render.scene"))
    assert scene["run"]["stale"] is False and not scene["camera"]["automatic"]
    assert scene["highlights"] == ["cpl_000001", "spn_000002"] and scene["layers"]["labels"] is False
    assert scene["viewport"] == {"width": 640, "height": 480}
    assert replay(Journal(tmp_path / "project.events.jsonl")) == s.state
    ok(c.call("view.set_camera", {"camera": None, "viewport": {"width": 800, "height": 600}}))
    assert ok(c.call("render.scene"))["camera"]["automatic"]


@pytest.mark.parametrize(
    ("position", "up", "fov", "message"),
    [
        ([0.0, 0.0, 0.0], [0.0, 1.0, 0.0], 40.0, "coincide"),
        ([0.0, 0.0, 20.0], [0.0, 0.0, 1.0], 40.0, "parallel"),
        ([0.0, 0.0, 20.0], [0.0, 0.0, 0.0], 40.0, "zero"),
        ([0.0, 0.0, 20.0], [0.0, 1.0, 0.0], 180.0, "field of view"),
    ],
)
def test_a_camera_that_cannot_project_is_refused(
    position: list[float], up: list[float], fov: float, message: str
) -> None:
    _, c = opened()
    body = error(c.call("view.set_camera", camera_args(position, up, fov)), "INVALID_ARGUMENT", "camera")
    assert message in body["message"]


def test_planes_and_viewports_are_bounded() -> None:
    _, c = opened()
    args = camera_args([0.0, 0.0, 20.0], [0.0, 1.0, 0.0])
    args["camera"]["far"] = {"value": 0.1, "unit": "Å"}
    error(c.call("view.set_camera", args), "INVALID_ARGUMENT", "camera")
    args = camera_args([0.0, 0.0, 20.0], [0.0, 1.0, 0.0])
    args["viewport"] = {"width": 10**6, "height": 480}
    error(c.call("view.set_camera", args), "INVALID_ARGUMENT", "viewport.width")


def test_highlights_follow_the_project() -> None:
    s, c = opened()
    error(c.call("view.highlight", {"ids": ["cpl_999999"]}), "ID_NOT_FOUND", "ids[0]")
    ok(c.call("view.highlight", {"ids": ["spn_000001"]}))
    ok(c.call("project.import_xyz", {"xyz": ETHANE_XYZ, "name": "ethane", "expected_science_revision": 1}))
    assert s.state.view.highlights == ()  # another document: cleared, never retargeted


def test_view_permissions() -> None:
    s, _ = opened()
    args = camera_args([0.0, 0.0, 20.0], [0.0, 1.0, 0.0])
    error(client(s, VIEWER).call("view.set_camera", args), "CAPABILITY_DENIED")
    assert ok(client(s, AGENT).call("view.set_camera", args))["automatic"] is False  # view writes are direct
    assert ok(client(s, VIEWER).call("render.view_svg"))["svg"].startswith("<svg")


# --------------------------------------------------------------------------- SVG
def test_the_svg_draws_the_scene_it_describes() -> None:
    _, c = opened()
    ok(run_fit(c))
    ok(c.call("view.select", {"ids": ["spn_000003"]}))
    ok(c.call("view.highlight", {"ids": ["cpl_000002"]}))
    scene = ok(c.call("render.scene"))
    out = ok(c.call("render.view_svg"))
    root = ET.fromstring(out["svg"])
    assert root.get("width") == "800" and out["science_revision"] == scene["science_revision"]
    circles = root.findall(f"{SVG}circle")
    assert [x.get("data-id") for x in circles] == scene["draw_order"]  # painted far to near
    screen = {a["id"]: a["screen"] for a in scene["atoms"]}
    for x in circles:
        s = screen[x.get("data-id")]
        assert float(x.get("cx")) == pytest.approx(s["x"], abs=1e-3)
        assert float(x.get("cy")) == pytest.approx(s["y"], abs=1e-3)
    selected = next(x for x in circles if x.get("data-id") == "spn_000003")
    assert selected.get("stroke-width") == "3"
    lines = {x.get("data-id"): x for x in root.findall(f"{SVG}line") if x.get("data-id")}
    assert lines["cpl_000002"].get("stroke") == "#f39c12"
    assert len(root.findall(f"{SVG}text")) == 10
    ok(c.call("view.set_layers", {"labels": False, "bonds": True, "couplings": False}))
    plain = ET.fromstring(ok(c.call("render.view_svg"))["svg"])
    assert plain.findall(f"{SVG}text") == [] and plain.findall(f"{SVG}line") == []


def test_labels_are_escaped_as_data() -> None:
    c = client(new_session())
    ok(c.call("project.import_xyz", {"xyz": ETHANE_XYZ, "name": "ethane", "expected_science_revision": 0}))
    doc = json.loads(ok(c.call("project.export"))["text"])
    doc["project"]["molecule"]["spins"][0]["label"] = '<script>alert("x")</script>&'
    ok(c.call("project.load", {"text": json.dumps(doc), "expected_science_revision": 1}))
    svg = ok(c.call("render.view_svg"))["svg"]
    assert "<script>" not in svg and "&lt;script&gt;" in svg
    ET.fromstring(svg)  # still well-formed


# --------------------------------------------------------------------------- projection and parity
def test_projection_basics() -> None:
    cam = Camera((0.0, 0.0, 10.0), (0.0, 0.0, 0.0), (0.0, 1.0, 0.0), 90.0, 1.0, 100.0)
    (centre, right, behind, far) = project(cam, 200, 100, [(0, 0, 0), (5, 0, 0), (0, 0, 20), (0, 0, -200)])
    assert centre == (100.0, 50.0, 10.0, True)
    assert right[0] == pytest.approx(100 + 0.5 * 100 / 2) and right[1] == 50.0  # tan 45° = 1, aspect 2
    assert behind[3] is False and behind[2] < 0 and far[3] is False
    assert draw_order(["b", "a", "c", "d"], [centre, right, behind, far]) == ["a", "b"]  # equal depth: by ID
    pts = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 3.0, 0.0)]
    auto = auto_camera(pts, 300, 600)
    assert all(p[3] for p in project(auto, 300, 600, pts))  # portrait: fitted to the narrow side


def test_the_parity_fixtures_are_current() -> None:
    current = json.dumps(parity_fixtures(), indent=1, sort_keys=True) + "\n"
    if os.environ.get("DIPOLAR_UPDATE_SNAPSHOT") == "1":
        FIXTURES.write_text(current, encoding="utf-8")
    assert FIXTURES.read_text(encoding="utf-8") == current, "rerun with DIPOLAR_UPDATE_SNAPSHOT=1"


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_browser_projection_matches(tmp_path: Path) -> None:
    """The TypeScript projection (web/src/scene/projection.ts) reproduces the fixtures."""
    out = subprocess.run(
        ["node", "--experimental-strip-types", "--no-warnings", "scripts/projection-parity.mjs"],
        cwd=ROOT / "web",
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert out.returncode == 0, out.stderr
    assert "projection parity OK" in out.stdout


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_parity_check_catches_a_difference(tmp_path: Path) -> None:
    """The check is not vacuous: a fixture moved by one pixel fails it."""
    work = tmp_path / "web"
    shutil.copytree(ROOT / "web" / "scripts", work / "scripts")
    shutil.copytree(ROOT / "web" / "src" / "scene", work / "src" / "scene")
    data = json.loads((work / "src" / "scene" / "parity-fixtures.json").read_text())
    data["cases"][0]["expected"][0]["x"] += 1.0
    (work / "src" / "scene" / "parity-fixtures.json").write_text(json.dumps(data))
    out = subprocess.run(
        ["node", "--experimental-strip-types", "--no-warnings", "scripts/projection-parity.mjs"],
        cwd=work,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert out.returncode == 1 and "point 0 x" in out.stderr


# --------------------------------------------------------------------------- round 35
def test_describe_view_reads_one_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    from dipolar_app import view_ops

    s, c = opened()
    other = client(s)
    real = view_ops.selected
    calls = {"n": 0}

    def racing(project: Any, ids: Any) -> Any:
        calls["n"] += 1
        if calls["n"] == 1:  # another client changes the project mid-call
            other.call("project.import_xyz", {"xyz": ETHANE_XYZ, "name": "ethane", "expected_science_revision": 1})
        return real(project, ids)

    monkeypatch.setattr(view_ops, "selected", racing)
    env = c.call("render.describe_view")
    view = ok(env)
    assert view["project_name"].startswith("Synthetic biphenyl") and len(view["visible"]) == 10
    assert view["science_revision"] == env["revisions"]["science"] == 1
    assert s.state.science_revision == 2  # the change did happen, after the snapshot


def test_an_unreadable_run_result_is_reported_not_shown(tmp_path: Path) -> None:
    _, c = opened(tmp_path)
    ok(run_fit(c))
    for blob in (tmp_path / "runs").glob("*.json"):
        blob.unlink()
    view = ok(c.call("render.describe_view"))
    assert view["run"] == {"run_id": "run_000001", "stale": False, "available": False}
    assert view["phi_source"] == "default" and view["fit"] is None and view["top_residuals"] == []
    assert any("cannot be read" in w for w in view["warnings"])


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"fov": deg(1e-322)}, "field of view"),
        ({"fov": deg(179.9)}, "field of view"),
        ({"near": {"value": 1e-9, "unit": "Å"}}, "near plane"),
        ({"position": {"xyz": [0.0, 0.0, 1e300], "unit": "Å"}}, "within"),
    ],
)
def test_numerically_unsafe_cameras_are_refused(change: dict[str, Any], message: str) -> None:
    s, c = opened()
    args = camera_args([0.0, 0.0, 20.0], [0.0, 1.0, 0.0])
    args["camera"].update(change)
    body = error(c.call("view.set_camera", args), "INVALID_ARGUMENT", "camera")
    assert message in body["message"] and s.state.view.camera is None


def test_long_labels_are_cut_in_perception_outputs() -> None:
    from dipolar_app.scene import MAX_LABEL_OUT

    c = client(new_session())
    ok(c.call("project.import_xyz", {"xyz": ETHANE_XYZ, "name": "ethane", "expected_science_revision": 0}))
    doc = json.loads(ok(c.call("project.export"))["text"])
    doc["project"]["molecule"]["spins"][0]["label"] = "H" * 100_000
    ok(c.call("project.load", {"text": json.dumps(doc), "expected_science_revision": 1}))
    spin = doc["project"]["molecule"]["spins"][0]["id"]
    scene = ok(c.call("render.scene"))
    assert max(len(a["label"]) for a in scene["atoms"]) == MAX_LABEL_OUT
    assert len(json.dumps(scene)) < 20_000  # the 100 000-character label is not copied out
    assert len(ok(c.call("view.select", {"ids": [spin]}))["selection"][0]["label"]) == MAX_LABEL_OUT
    assert len(ok(c.call("render.describe_view"))["selection"][0]["label"]) == MAX_LABEL_OUT


def test_describe_view_reports_an_inadequate_fit() -> None:
    _, c = opened()
    doc = json.loads(ok(c.call("project.export"))["text"])
    for coupling in doc["project"]["couplings"]:
        coupling["sigma"]["value"] = 0.05  # σ far below the actual noise
    ok(c.call("project.load", {"text": json.dumps(doc), "expected_science_revision": 1}))
    ok(run_fit(c))
    view = ok(c.call("render.describe_view"))
    assert view["fit"]["adequate"] is False and view["fit"]["p_value"] < 1e-3 and view["fit"]["regular"]
    assert any("inadequate" in w for w in view["warnings"])
    good = ok(run_fit(opened()[1]))
    assert good["adequate"] is True
