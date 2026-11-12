"""The scene description, its projection and the SVG renderer (04 D15, D16, §8.4; M2 step 4).

**One scene description.** ``build_scene`` assembles it from the session state:
- the view state (camera, viewport, layers, selection, highlights);
- the molecule's coordinates at the displayed torsion;
- the active run's residuals.

Both the browser and the SVG renderer consume it.

**One projection.** ``project`` is the browser's perspective camera (a three.js-style
``PerspectiveCamera`` looking from ``position`` at ``target``):
- vertical field of view ``fov_deg``;
- near and far planes;
- aspect ratio = viewport width / height;
- screen pixels with x to the right and y down.

``web/src/scene/projection.ts`` implements the same arithmetic. The parity fixtures
(``parity_fixtures``, committed as ``web/src/scene/parity-fixtures.json``) are checked against
both implementations: the projected positions, the depths, the visibility and the draw order.

**The displayed torsion** comes from the active run, if it is current. Otherwise it is the
imported dihedral for imported geometry, or ``DEFAULT_PHI_DEG`` for the template. The scene
says which (``phi_source``), so a picture never passes for a fit result.

**Draw order** is far to near (by depth, then by ID), so nearer objects are painted over farther
ones.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Sequence
from typing import Any, Literal
from xml.sax.saxutils import escape, quoteattr

from dipolar_app.project import BiphenylTemplate, ImportedGeometry, Project, short
from dipolar_app.session import Camera, SessionState, Vec3

DEFAULT_PHI_DEG = 45.0
DEFAULT_FOV_DEG = 45.0
#: Numerically safe camera bounds (round 35): angles in degrees, lengths in Å.
MIN_FOV_DEG, MAX_FOV_DEG = 1.0, 170.0
MIN_NEAR, MAX_EXTENT = 1e-3, 1e6
_XML_FORBIDDEN = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff\ud800-\udfff]")


def xml_text(text: str) -> str:
    """``text`` escaped for XML, with the characters XML 1.0 forbids replaced (round 36)."""
    return escape(_XML_FORBIDDEN.sub("\ufffd", text))


#: The auto-fitted camera keeps the molecule's bounding sphere inside the view with this margin.
FIT_MARGIN = 1.15

PhiSource = Literal["run", "imported", "default"]


# --------------------------------------------------------------------------- projection
def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _unit(a: Vec3) -> Vec3:
    n = math.sqrt(_dot(a, a))
    if not n > 0:
        raise ValueError("a zero-length vector")
    return (a[0] / n, a[1] / n, a[2] / n)


def check_camera(camera: Camera) -> str | None:
    """Why ``camera`` cannot project safely, or None."""
    values = [*camera.position, *camera.target, *camera.up, camera.fov_deg, camera.near, camera.far]
    if not all(math.isfinite(v) for v in values):
        return "camera values must be finite"
    if max(abs(v) for v in (*camera.position, *camera.target, camera.far)) > MAX_EXTENT:
        return f"camera coordinates and planes must lie within {MAX_EXTENT:g} Å"
    if not MIN_FOV_DEG <= camera.fov_deg <= MAX_FOV_DEG:
        return f"the field of view must be between {MIN_FOV_DEG:g} and {MAX_FOV_DEG:g} degrees"
    if not MIN_NEAR <= camera.near:
        return f"the near plane must be at least {MIN_NEAR:g} Å"
    forward = _sub(camera.target, camera.position)
    if not _dot(forward, forward) > 1e-12:
        return "the camera position and target coincide"
    if not _dot(camera.up, camera.up) > 1e-12:
        return "the up vector is zero"
    side = _cross(forward, camera.up)
    if not _dot(side, side) > 1e-12 * _dot(forward, forward) * _dot(camera.up, camera.up):
        return "the up vector is parallel to the viewing direction"
    if not camera.near < camera.far:
        return "the planes need 0 < near < far"
    return None


def project(camera: Camera, width: int, height: int, points: Sequence[Vec3]) -> list[tuple[float, float, float, bool]]:
    """Each point as (x, y, depth, visible): screen pixels (x right, y down), the distance along
    the viewing direction, and whether it lies inside the view frustum."""
    forward = _unit(_sub(camera.target, camera.position))
    side = _unit(_cross(forward, camera.up))
    up = _cross(side, forward)
    t = math.tan(math.radians(camera.fov_deg) / 2.0)
    aspect = width / height
    if not (t > 0 and math.isfinite(t)):
        raise ValueError("the field of view cannot project")
    out = []
    for p in points:
        v = _sub(p, camera.position)
        depth = _dot(v, forward)
        if not camera.near <= depth <= camera.far:  # clipped before any division (round 36)
            out.append((0.0, 0.0, depth, False))
            continue
        ndc_x = _dot(v, side) / (depth * t * aspect)
        ndc_y = _dot(v, up) / (depth * t)
        x = (ndc_x + 1.0) / 2.0 * width
        y = (1.0 - ndc_y) / 2.0 * height
        visible = abs(ndc_x) <= 1.0 and abs(ndc_y) <= 1.0
        out.append((x, y, depth, visible))
    return out


#: Depths within this many Å are a tie for the draw order (resolved by ID). Symmetric atoms sit at
#: equal depths that differ only in the last bit, which differs between math libraries; quantizing
#: makes the order the same in Python and in every browser.
DEPTH_QUANTUM = 1e-9


def depth_key(depth: float) -> int:
    """The draw-order key: the depth in quanta, rounded half up (as JavaScript's Math.floor(x + 0.5))."""
    return math.floor(depth / DEPTH_QUANTUM + 0.5)


def draw_order(ids: Sequence[str], projected: Sequence[tuple[float, float, float, bool]]) -> list[str]:
    """The visible IDs, far to near; depths within ``DEPTH_QUANTUM`` tie and go by ID."""
    keyed = [(-depth_key(p[2]), i) for i, p in zip(ids, projected, strict=True) if p[3]]
    return [i for _, i in sorted(keyed)]


def auto_camera(points: Sequence[Vec3], width: int, height: int, fov_deg: float = DEFAULT_FOV_DEG) -> Camera:
    """A camera on +z of the points' centroid that fits their bounding sphere in the view."""
    n = len(points)
    if n == 0:
        return Camera((0.0, 0.0, 10.0), (0.0, 0.0, 0.0), (0.0, 1.0, 0.0), fov_deg, 0.1, 100.0)
    c: Vec3 = (sum(p[0] for p in points) / n, sum(p[1] for p in points) / n, sum(p[2] for p in points) / n)
    radius = max(max(math.sqrt(_dot(_sub(p, c), _sub(p, c))) for p in points), 1.0)
    half = math.radians(fov_deg) / 2.0
    half_h = math.atan(math.tan(half) * min(1.0, width / height))  # the narrower half-angle
    distance = FIT_MARGIN * radius / math.sin(half_h)
    return Camera(
        (c[0], c[1], c[2] + distance),
        c,
        (0.0, 1.0, 0.0),
        fov_deg,
        max(distance - 2.0 * radius, 0.01),
        distance + 2.0 * radius,
    )


# --------------------------------------------------------------------------- the scene
def atom_id(index: int) -> str:
    return f"atm_{index + 1:06d}"


def _active_run(state: SessionState, blobs: Any) -> tuple[Any, dict[str, Any] | None]:
    """The latest run and its result (None when there is no run or its blob is unreadable)."""
    if not state.runs:
        return None, None
    run = state.runs[-1]
    text = blobs.text(run.result_sha256)
    return run, (json.loads(text) if text is not None else None)


def geometry(project: Project, phi_deg: float) -> tuple[list[str], list[str], list[Vec3], list[tuple[int, int]]]:
    """(IDs, elements, coordinates in Å, bonds) at torsion φ. Spins carry their spin IDs; other
    atoms ``atm_NNNNNN`` IDs. The template shows its protons only (it has no other atoms)."""
    from dipolar_core.biphenyl import BiphenylGeometry, proton_positions
    from dipolar_core.torsion import bonds_from_coordinates

    g = project.molecule.geometry
    if isinstance(g, BiphenylTemplate):
        coords = proton_positions(phi_deg, BiphenylGeometry(g.r_cc.value, g.r_ch.value, g.r_inter.value))
        ids = [s.id for s in project.molecule.spins]
        return ids, ["H"] * len(ids), [(float(x), float(y), float(z)) for x, y, z in coords], []
    assert isinstance(g, ImportedGeometry)
    import numpy as np

    from dipolar_app.science import _torsion_geometry

    if g.torsion is not None:
        positions = _torsion_geometry(g).positions(phi_deg)
    else:
        positions = np.array([[a.x, a.y, a.z] for a in g.atoms])
    by_atom = {s.atom: s.id for s in project.molecule.spins}
    elements = [a.element for a in g.atoms]
    ids = [by_atom.get(k, atom_id(k)) for k in range(len(g.atoms))]
    bonds = list(bonds_from_coordinates(elements, positions))
    return ids, elements, [(float(x), float(y), float(z)) for x, y, z in positions], bonds


def displayed_phi(state: SessionState, result: dict[str, Any] | None, current: bool) -> tuple[float, PhiSource]:
    """φ from the run only when the run is current *and* its result is readable."""
    project = state.project
    assert project is not None
    if result is not None and current:
        return float(result["theta"][0]["value"]), "run"
    g = project.molecule.geometry
    if isinstance(g, ImportedGeometry) and g.torsion is not None:
        from dipolar_app.science import _torsion_geometry

        return float(_torsion_geometry(g).phi0_deg), "imported"
    return DEFAULT_PHI_DEG, "default"


def _fit_summary(result: dict[str, Any]) -> dict[str, Any]:
    v = result["validity"]
    return {
        "adequate": result["adequate"],
        "p_value": result["p_value"],
        "regular": v["regular"],
        "converged": v["converged"],
        "at_bound": list(v["at_bound"]),
        "physically_admissible": v["physically_admissible"],
        "notes": [short(n) for n in result["notes"]][:8],
    }


def build_scene(state: SessionState, blobs: Any) -> dict[str, Any]:
    """The scene as plain JSON-ready data (validated by ``render.scene``'s output model)."""
    prj = state.project
    assert prj is not None
    run, result = _active_run(state, blobs)
    current = run is not None and run.science_revision == state.science_revision
    # A current run whose result cannot be read is reported as unavailable, never shown as the
    # fit (round 35).
    usable = current and result is not None
    phi, source = displayed_phi(state, result, usable)
    ids, elements, coords, bonds = geometry(prj, phi)
    width, height = state.view.viewport
    camera = state.view.camera or auto_camera(coords, width, height)
    problem = check_camera(camera)
    if problem is not None:  # an auto-fitted camera is checked like any other (round 36)
        raise ValueError(problem)
    projected = project(camera, width, height, coords)
    residuals = {c["id"]: c["residual"]["value"] for c in result["couplings"]} if usable and result else {}
    labels = {s.id: short(s.label) for s in prj.molecule.spins}
    position = dict(zip(ids, coords, strict=True))
    return {
        "science_revision": state.science_revision,
        "workspace_revision": state.workspace_revision,
        "phi": {"value": phi, "unit": "deg"},
        "phi_source": source,
        "run": None if run is None else {"run_id": run.id, "stale": not current, "available": result is not None},
        "fit": _fit_summary(result) if usable and result else None,
        "camera": {
            "position": {"xyz": list(camera.position), "unit": "Å"},
            "target": {"xyz": list(camera.target), "unit": "Å"},
            "up": list(camera.up),
            "fov": {"value": camera.fov_deg, "unit": "deg"},
            "near": {"value": camera.near, "unit": "Å"},
            "far": {"value": camera.far, "unit": "Å"},
            "automatic": state.view.camera is None,
        },
        "viewport": {"width": width, "height": height},
        "layers": {
            "labels": state.view.layers.labels,
            "bonds": state.view.layers.bonds,
            "couplings": state.view.layers.couplings,
        },
        "atoms": [
            {
                "id": i,
                "element": e,
                "label": labels.get(i, f"{e}{k + 1}"),
                "position": {"xyz": list(p), "unit": "Å"},
                "screen": {"x": q[0], "y": q[1], "depth": q[2], "visible": q[3]},
            }
            for k, (i, e, p, q) in enumerate(zip(ids, elements, coords, projected, strict=True))
        ],
        "bonds": [{"a": ids[a], "b": ids[b]} for a, b in bonds],
        "couplings": [
            {
                "id": c.id,
                "spin_a": c.spin_a,
                "spin_b": c.spin_b,
                "residual": None if c.id not in residuals else {"value": residuals[c.id], "unit": "Hz"},
                "length": {"value": math.dist(position[c.spin_a], position[c.spin_b]), "unit": "Å"},
            }
            for c in prj.couplings
            if c.spin_a in position and c.spin_b in position
        ],
        "draw_order": draw_order(ids, projected),
        "selection": list(state.view.selection),
        "highlights": list(state.view.highlights),
    }


# --------------------------------------------------------------------------- SVG
def _f(x: float) -> str:
    return f"{x:.3f}"


def render_svg(scene: dict[str, Any]) -> str:
    """A standalone SVG of the scene, from its projection alone. Every label is escaped; every
    element carries its object ID (``data-id``), so the picture can be checked against the
    scene."""
    width, height = scene["viewport"]["width"], scene["viewport"]["height"]
    atoms = {a["id"]: a for a in scene["atoms"]}
    selected, highlighted = set(scene["selection"]), set(scene["highlights"])
    depths = [a["screen"]["depth"] for a in scene["atoms"] if a["screen"]["visible"]] or [1.0]
    reference = sum(depths) / len(depths)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" data-science-revision="{scene["science_revision"]}">',
        f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
    ]

    def visible(i: str) -> bool:
        return i in atoms and bool(atoms[i]["screen"]["visible"])

    if scene["layers"]["bonds"]:
        for bond in scene["bonds"]:
            a, b = bond["a"], bond["b"]
            if visible(a) and visible(b):
                pa, pb = atoms[a]["screen"], atoms[b]["screen"]
                parts.append(
                    f'<line x1="{_f(pa["x"])}" y1="{_f(pa["y"])}" x2="{_f(pb["x"])}" y2="{_f(pb["y"])}" '
                    'stroke="#888888" stroke-width="2"/>'
                )
    if scene["layers"]["couplings"]:
        for c in scene["couplings"]:
            if not (visible(c["spin_a"]) and visible(c["spin_b"])):
                continue
            pa, pb = atoms[c["spin_a"]]["screen"], atoms[c["spin_b"]]["screen"]
            colour = "#b0b0b0"
            if c["residual"] is not None:
                colour = "#c0392b" if c["residual"]["value"] > 0 else "#2471a3"
            if c["id"] in highlighted:
                colour = "#f39c12"
            width_px = 3 if c["id"] in selected or c["id"] in highlighted else 1
            parts.append(
                f'<line data-id={quoteattr(c["id"])} x1="{_f(pa["x"])}" y1="{_f(pa["y"])}" '
                f'x2="{_f(pb["x"])}" y2="{_f(pb["y"])}" stroke="{colour}" stroke-width="{width_px}" '
                'stroke-dasharray="4 3"/>'
            )
    for i in scene["draw_order"]:
        a = atoms[i]
        s = a["screen"]
        r = 7.0 * reference / s["depth"]
        fill = "#f39c12" if i in highlighted else ("#ffffff" if a["element"] == "H" else "#555555")
        stroke = "#000000" if i in selected else "#333333"
        parts.append(
            f'<circle data-id={quoteattr(i)} cx="{_f(s["x"])}" cy="{_f(s["y"])}" r="{_f(r)}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{3 if i in selected else 1}"/>'
        )
        if scene["layers"]["labels"]:
            parts.append(
                f'<text x="{_f(s["x"] + r + 2)}" y="{_f(s["y"] - r - 2)}" font-family="sans-serif" '
                f'font-size="11" fill="#222222">{xml_text(a["label"])}</text>'
            )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


# --------------------------------------------------------------------------- parity fixtures
def parity_fixtures() -> dict[str, Any]:
    """Fixed projection cases, committed as ``web/src/scene/parity-fixtures.json`` and checked
    against ``web/src/scene/projection.ts`` (04 §8.4 parity test)."""
    from dipolar_core.biphenyl import proton_positions

    protons = [(float(x), float(y), float(z)) for x, y, z in proton_positions(37.0)]
    ids = [f"spn_{k:06d}" for k in range(1, 11)]
    off = [*protons, (40.0, 0.0, 0.0), (0.0, 0.0, 60.0), (0.0, 0.0, -1e4)]
    off_ids = [*ids, "atm_000011", "atm_000012", "atm_000013"]
    cases: list[dict[str, Any]] = []

    def case(name: str, camera: Camera, w: int, h: int, pts: list[Vec3], names: list[str], auto: bool) -> None:
        projected = project(camera, w, h, pts)
        cases.append(
            {
                "name": name,
                "camera": camera.to_json(),
                "auto": auto,
                "viewport": [w, h],
                "points": [list(p) for p in pts],
                "ids": names,
                "expected": [{"x": x, "y": y, "depth": d, "visible": v} for x, y, d, v in projected],
                "draw_order": draw_order(names, projected),
            }
        )

    case("auto 800x600", auto_camera(protons, 800, 600), 800, 600, protons, ids, True)
    case("auto portrait 400x700", auto_camera(protons, 400, 700), 400, 700, protons, ids, True)
    oblique = Camera((9.0, 6.0, 12.0), (0.0, 0.0, 0.5), (0.0, 0.0, 1.0), 30.0, 1.0, 40.0)
    case("oblique, z up, with clipping", oblique, 640, 480, off, off_ids, False)
    tight = Camera((0.0, 12.0, 0.0), (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), 20.0, 11.0, 13.0)
    case("near and far clip", tight, 500, 500, off, off_ids, False)
    # Equal depths in an order that is not the ID order: the tie-break must sort by ID (round 35).
    ring: list[Vec3] = [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (-1.0, 0.0, 0.0), (0.0, -1.0, 0.0), (0.5, 0.5, -2.0)]
    scrambled = ["spn_000004", "spn_000002", "spn_000003", "spn_000001", "atm_000009"]
    front = Camera((0.0, 0.0, 10.0), (0.0, 0.0, 0.0), (0.0, 1.0, 0.0), 45.0, 1.0, 50.0)
    case("equal depths, scrambled IDs", front, 300, 300, ring, scrambled, False)
    # Centred points inside the near plane and beyond the far plane: clipped by depth alone (round 36).
    planes = Camera((0.0, 0.0, 10.0), (0.0, 0.0, 0.0), (0.0, 1.0, 0.0), 45.0, 5.0, 12.0)
    axis: list[Vec3] = [(0.0, 0.0, 0.0), (0.0, 0.0, 8.0), (0.0, 0.0, 10.0 - 1e-300), (0.0, 0.0, -5.0), (0.2, 0.1, -1.9)]
    case("near and far planes on the axis", planes, 320, 240, axis, ["a", "b", "c", "d", "e"], False)
    return {
        "description": "Projection parity fixtures (04 §8.4), generated by dipolar_app.scene.parity_fixtures",
        "tolerance_px": 1e-9,
        "cases": cases,
    }
