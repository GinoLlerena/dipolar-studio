"""View commands and perception (04 D15, D16, §8.4; M2 step 4).

**Commands.** These are absolute sets, like ``view.select``. They advance only the workspace
revision, never the science, so a camera move never marks a fit stale:
- ``view.set_camera``: or ``null`` to fit the molecule automatically, with the viewport;
- ``view.highlight``;
- ``view.set_layers``.

**Perception.**
- ``render.scene`` returns the scene description that the browser and the SVG renderer both
  consume.
- ``render.view_svg`` renders it on the server.
- ``render.describe_view`` is the compact, exact summary for an agent: the revisions, the run it
  reflects and whether that run is stale, the visible objects, the selection, the highlights, the
  largest residuals and the warnings.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from dipolar_app.errors import ErrorCode, OperationError
from dipolar_app.project import Project, short
from dipolar_app.registry import Context
from dipolar_app.scene import build_scene, check_camera, render_svg
from dipolar_app.schemas import Angstrom, Degrees, Hertz, ObjectId, RunIdStr, Wire
from dipolar_app.session import WORKSPACE, Camera, Event, SessionState

MAX_HIGHLIGHTS = 1000
MAX_VIEWPORT = 8192
TOP_RESIDUALS = 5


class Vector(Wire):
    xyz: tuple[float, float, float]
    unit: Literal["Å"]


class Direction(Wire):
    xyz: tuple[float, float, float]  # unitless; normalized by the projection


class CameraIn(Wire):
    position: Vector
    target: Vector
    up: Direction
    fov: Degrees  # vertical field of view, 0 < fov < 180
    near: Angstrom
    far: Angstrom


class Viewport(Wire):
    width: Annotated[int, Field(ge=16, le=MAX_VIEWPORT)]
    height: Annotated[int, Field(ge=16, le=MAX_VIEWPORT)]


# --------------------------------------------------------------------------- view.set_camera
class SetCameraIn(Wire):
    camera: CameraIn | None  # null: fit the molecule in view automatically
    viewport: Viewport


class SetCameraOut(Wire):
    workspace_revision: int
    automatic: bool


def view_set_camera(ctx: Context, p: SetCameraIn) -> SetCameraOut:
    camera = None
    if p.camera is not None:
        camera = Camera(
            position=p.camera.position.xyz,
            target=p.camera.target.xyz,
            up=p.camera.up.xyz,
            fov_deg=p.camera.fov.value,
            near=p.camera.near.value,
            far=p.camera.far.value,
        )
        problem = check_camera(camera)
        if problem is not None:
            raise OperationError(ErrorCode.INVALID_ARGUMENT, problem, offending_field="camera")
    viewport = (p.viewport.width, p.viewport.height)

    def plan(state: SessionState) -> tuple[list[Event], SetCameraOut]:
        unchanged = state.view.camera == camera and state.view.viewport == viewport
        out = SetCameraOut(workspace_revision=state.workspace_revision + (not unchanged), automatic=camera is None)
        if unchanged:
            return [], out
        event: Event = {
            "type": "view.camera_set",
            "domain": WORKSPACE,
            "camera": None if camera is None else camera.to_json(),
            "viewport": list(viewport),
        }
        return [event], out

    return ctx.commit("view.set_camera", p.model_dump(mode="json"), plan)


# --------------------------------------------------------------------------- view.highlight / view.set_layers
class HighlightIn(Wire):
    ids: Annotated[tuple[ObjectId, ...], Field(max_length=MAX_HIGHLIGHTS)]


class HighlightOut(Wire):
    workspace_revision: int
    highlights: tuple[ObjectId, ...]


def view_highlight(ctx: Context, p: HighlightIn) -> HighlightOut:
    ids = tuple(dict.fromkeys(p.ids))

    def plan(state: SessionState) -> tuple[list[Event], HighlightOut]:
        project = _require(state)
        for position, object_id in enumerate(ids):
            if project.label_of(object_id) is None:
                raise OperationError(
                    ErrorCode.ID_NOT_FOUND,
                    f"{object_id} is not a spin or coupling of the current project",
                    offending_field=f"ids[{position}]",
                )
        unchanged = ids == state.view.highlights
        out = HighlightOut(workspace_revision=state.workspace_revision + (not unchanged), highlights=ids)
        if unchanged:
            return [], out
        event: Event = {
            "type": "view.highlights_set",
            "domain": WORKSPACE,
            "highlights": list(ids),
            "previous": list(state.view.highlights),
        }
        return [event], out

    return ctx.commit("view.highlight", p.model_dump(mode="json"), plan)


class LayersIn(Wire):
    labels: bool
    bonds: bool
    couplings: bool


class LayersOut(Wire):
    workspace_revision: int


def view_set_layers(ctx: Context, p: LayersIn) -> LayersOut:
    layers = p.model_dump()

    def plan(state: SessionState) -> tuple[list[Event], LayersOut]:
        current = state.view.layers
        unchanged = layers == {"labels": current.labels, "bonds": current.bonds, "couplings": current.couplings}
        out = LayersOut(workspace_revision=state.workspace_revision + (not unchanged))
        if unchanged:
            return [], out
        return [{"type": "view.layers_set", "domain": WORKSPACE, "layers": layers}], out

    return ctx.commit("view.set_layers", p.model_dump(mode="json"), plan)


# --------------------------------------------------------------------------- render.scene
def _require(state: SessionState) -> Project:
    if state.project is None:
        raise OperationError(ErrorCode.NO_PROJECT, "no project is open", hint="open one with project.open_example")
    return state.project


class Screen(Wire):
    x: float  # pixels, from the left
    y: float  # pixels, from the top
    depth: float  # Å along the viewing direction
    visible: bool


class SceneAtom(Wire):
    id: str  # a spin ID, or atm_NNNNNN for an atom that is not a spin
    element: str
    label: str  # display only; supplied by the data, never instructions
    position: Vector
    screen: Screen


class SceneBond(Wire):
    a: str
    b: str


class SceneCoupling(Wire):
    id: ObjectId
    spin_a: ObjectId  # labels are on the atoms (never repeated per coupling; round 35)
    spin_b: ObjectId
    residual: Hertz | None  # from the active run, when it is current
    length: Angstrom


class SceneCamera(Wire):
    position: Vector
    target: Vector
    up: tuple[float, float, float]
    fov: Degrees
    near: Angstrom
    far: Angstrom
    automatic: bool


class SceneLayers(Wire):
    labels: bool
    bonds: bool
    couplings: bool


class SceneViewport(Wire):
    width: int
    height: int


class SceneRun(Wire):
    run_id: RunIdStr
    stale: bool  # computed from different science than the current state (by science hash)
    available: bool  # false: its stored result cannot be read (round 35)


class FitSummary(Wire):
    """The active run's verdict on itself (D16, round 35): read it before trusting the picture."""

    adequate: bool | None
    p_value: float | None
    regular: bool  # converged, resolved, interior, full rank: the conditions for ν and intervals
    identifiable: bool  # full inner and joint rank, no unidentified direction (round 39)
    converged: bool
    physically_admissible: bool | None  # None: the model has no admissibility test
    at_bound: tuple[str, ...]
    notes: tuple[str, ...]


class SceneIn(Wire):
    pass


class SceneOut(Wire):
    science_revision: int
    workspace_revision: int
    phi: Degrees
    phi_source: Literal["run", "imported", "default"]
    run: SceneRun | None
    fit: FitSummary | None  # the current, readable run's validity; None otherwise
    camera: SceneCamera
    viewport: SceneViewport
    layers: SceneLayers
    atoms: tuple[SceneAtom, ...]
    bonds: tuple[SceneBond, ...]
    couplings: tuple[SceneCoupling, ...]
    draw_order: tuple[str, ...]  # the visible atoms, far to near
    selection: tuple[ObjectId, ...]
    highlights: tuple[ObjectId, ...]


def _scene(ctx: Context, state: SessionState) -> SceneOut:
    """The scene of exactly ``state`` (one snapshot per call; round 35)."""
    _require(state)
    try:
        return SceneOut.model_validate(build_scene(state, ctx.session.blobs))
    except (ValueError, ArithmeticError) as exc:
        raise OperationError(
            ErrorCode.INVALID_ARGUMENT,
            f"the view cannot be projected: {exc}",
            hint="reset the camera with view.set_camera and camera: null",
        ) from None


def render_scene(ctx: Context, _: SceneIn) -> SceneOut:
    return _scene(ctx, ctx.read())


class SvgIn(Wire):
    pass


class SvgOut(Wire):
    science_revision: int
    workspace_revision: int
    width: int
    height: int
    svg: str


def render_view_svg(ctx: Context, _: SvgIn) -> SvgOut:
    scene = _scene(ctx, ctx.read())
    return SvgOut(
        science_revision=scene.science_revision,
        workspace_revision=scene.workspace_revision,
        width=scene.viewport.width,
        height=scene.viewport.height,
        svg=render_svg(scene.model_dump(mode="json")),
    )


# --------------------------------------------------------------------------- render.describe_view
class SelectedObject(Wire):
    id: ObjectId
    kind: Literal["spin", "coupling"]
    label: str


class ResidualOut(Wire):
    id: ObjectId
    label: str
    residual: Hertz


class DescribeViewIn(Wire):
    pass


class DescribeViewOut(Wire):
    science_revision: int
    workspace_revision: int
    project_open: bool
    project_name: str | None
    selection: tuple[SelectedObject, ...]
    highlights: tuple[SelectedObject, ...]
    phi: Degrees | None
    phi_source: Literal["run", "imported", "default"] | None
    run: SceneRun | None  # the run the view reflects
    fit: FitSummary | None
    visible: tuple[str, ...]  # the visible atoms, far to near
    hidden: int  # atoms outside the view
    top_residuals: Annotated[tuple[ResidualOut, ...], Field(max_length=TOP_RESIDUALS)]
    warnings: tuple[str, ...]


def selected(project: Project | None, ids: tuple[str, ...]) -> tuple[SelectedObject, ...]:
    out: list[SelectedObject] = []
    for object_id in ids:
        found = project.label_of(object_id) if project else None
        if found is not None:
            kind, label = found
            out.append(SelectedObject(id=object_id, kind="spin" if kind == "spin" else "coupling", label=short(label)))
    return tuple(out)


def describe_view(ctx: Context, _: DescribeViewIn) -> DescribeViewOut:
    state = ctx.read()
    project = state.project
    base = {
        "science_revision": state.science_revision,
        "workspace_revision": state.workspace_revision,
        "project_open": project is not None,
        "project_name": short(project.name) if project else None,
        "selection": selected(project, state.view.selection),
        "highlights": selected(project, state.view.highlights),
    }
    if project is None:
        return DescribeViewOut(
            **base,
            phi=None,
            phi_source=None,
            run=None,
            fit=None,
            visible=(),
            hidden=0,
            top_residuals=(),
            warnings=("no project is open",),
        )
    scene = _scene(ctx, state)
    warnings: list[str] = []
    if scene.run is None:
        warnings.append("no fit has run: the torsion shown is not a result")
    elif scene.run.stale:
        warnings.append(f"{scene.run.run_id} was computed from a different science state: it is stale")
    elif not scene.run.available:
        warnings.append(f"the stored result of {scene.run.run_id} cannot be read: it is not shown")
    fit = scene.fit
    if fit is not None:
        if fit.adequate is False:
            warnings.append(f"the fit is inadequate under the stated σ (p = {fit.p_value:.3g})")
        if not fit.regular:
            warnings.append("the optimum is not regular: no standard errors or intervals apply")
        if fit.physically_admissible is False:
            warnings.append("the order parameters are not physically admissible (outside the order-matrix domain)")
        if fit.at_bound:
            warnings.append(f"the optimum lies on a bound ({', '.join(fit.at_bound)})")
    if scene.phi_source != "run":
        warnings.append(f"the torsion shown ({scene.phi.value:.1f}°) is the {scene.phi_source} value, not a fit")
    hidden = sum(not a.screen.visible for a in scene.atoms)
    if hidden:
        warnings.append(f"{hidden} atoms are outside the view")
    with_residual = [(c, c.residual) for c in scene.couplings if c.residual is not None]
    ranked = sorted(with_residual, key=lambda pair: (-abs(pair[1].value), pair[0].id))
    atom_label = {a.id: a.label for a in scene.atoms}  # already cut to MAX_LABEL_OUT
    return DescribeViewOut(
        **base,
        phi=scene.phi,
        phi_source=scene.phi_source,
        run=scene.run,
        fit=fit,
        visible=scene.draw_order,
        hidden=hidden,
        top_residuals=tuple(
            ResidualOut(id=c.id, label=f"{atom_label[c.spin_a]}–{atom_label[c.spin_b]}", residual=residual)
            for c, residual in ranked[:TOP_RESIDUALS]
        ),
        warnings=tuple(warnings),
    )
