"""The M0 vertical-slice operations.

``fit.preview`` and ``view.select`` are the slice (plan §8, M0). Three supporting operations make
it usable end to end: ``project.open_example`` (puts a project in the session), ``project.describe``
and ``render.describe_view`` (the seed of the D16 perception channel).
"""

from __future__ import annotations

import math
from typing import Annotated, Literal

import numpy as np
from dipolar_core.biphenyl import BiphenylGeometry, rigid_design
from dipolar_core.context import numerical_context
from dipolar_core.forward import constraint_diagonal
from dipolar_core.inference import is_admissible, solve_inner
from pydantic import Field

from dipolar_app.errors import ErrorCode, OperationError
from dipolar_app.policy import Capability
from dipolar_app.project import Project, load_example, science_hash
from dipolar_app.registry import Context, Operation, Registry
from dipolar_app.schemas import (
    Angstrom,
    CouplingId,
    Degrees,
    ExampleName,
    Hertz,
    ObjectId,
    Revision,
    SpinId,
    Wire,
    deg,
    hz,
)
from dipolar_app.session import SCIENCE, WORKSPACE, Event, SessionState

MAX_SELECTION = 1000

ESTIMAND = (
    "rigid effective inter-ring torsion φ, folded to [0°, 90°]; at fixed labels (±φ, Δ) are equivalent, "
    "(180° ± φ, −Δ) only with the ring-B relabelling H2′↔H6′, H3′↔H5′"
)
FRAME = "bisector frame: z along the inter-ring axis (ring A at z < 0), x bisects the ring planes, y = z × x"


def _require_project(state: SessionState) -> Project:
    if state.project is None:
        raise OperationError(ErrorCode.NO_PROJECT, "the session has no project", hint="call project.open_example")
    return state.project


# --------------------------------------------------------------------------- project.open_example
class OpenExampleIn(Wire):
    name: ExampleName
    expected_science_revision: Revision


class OpenExampleOut(Wire):
    science_revision: int
    science_hash: str
    n_spins: int
    n_couplings: int


def open_example(ctx: Context, p: OpenExampleIn) -> OpenExampleOut:
    project = load_example(p.name)

    def plan(state: SessionState) -> tuple[list[Event], OpenExampleOut]:
        if p.expected_science_revision != state.science_revision:
            raise OperationError(
                ErrorCode.REVISION_CONFLICT,
                "the science state changed since the caller last read it",
                offending_field="expected_science_revision",
                hint="read the current revision and retry if the change is still wanted",
                details={"current_science_revision": state.science_revision},
            )
        events: list[Event] = [
            {
                "type": "project.replaced",
                "domain": SCIENCE,
                "project": project.model_dump(mode="json"),
                "previous_science_hash": state.science_hash,
            }
        ]
        if state.view.selection:  # IDs of the old project must not stay selected
            events.append(
                {
                    "type": "view.selection_set",
                    "domain": WORKSPACE,
                    "selection": [],
                    "previous": list(state.view.selection),
                }
            )
        return events, OpenExampleOut(
            science_revision=state.science_revision + 1,
            science_hash=science_hash(project),
            n_spins=len(project.molecule.spins),
            n_couplings=len(project.couplings),
        )

    return ctx.commit("project.open_example", p.model_dump(mode="json"), plan)


# --------------------------------------------------------------------------- project.describe
class SpinOut(Wire):
    id: SpinId
    label: str
    isotope: str


class CouplingOut(Wire):
    id: CouplingId
    label: str
    spin_a: SpinId
    spin_b: SpinId
    observable: str
    value: Hertz
    sigma: Hertz
    sigma_source: str
    multiplicity: int
    equivalent_pairs: tuple[str, ...]


class GeometryOut(Wire):
    template: str
    r_cc: Angstrom
    r_ch: Angstrom
    r_inter: Angstrom


class DescribeProjectIn(Wire):
    pass


class DescribeProjectOut(Wire):
    science_revision: int
    science_hash: str
    name: str
    source: str
    geometry: GeometryOut
    spins: tuple[SpinOut, ...]
    couplings: tuple[CouplingOut, ...]
    model: str
    estimand: str


def describe_project(ctx: Context, _: DescribeProjectIn) -> DescribeProjectOut:
    state = ctx.read()
    project = _require_project(state)
    g = project.molecule.geometry
    return DescribeProjectOut(
        science_revision=state.science_revision,
        science_hash=state.science_hash,
        name=project.name,
        source=project.source,
        geometry=GeometryOut(template=g.template, r_cc=g.r_cc, r_ch=g.r_ch, r_inter=g.r_inter),
        spins=tuple(SpinOut(id=s.id, label=s.label, isotope=s.isotope) for s in project.molecule.spins),
        couplings=tuple(
            CouplingOut(
                id=c.id,
                label=project.coupling_label(c),
                spin_a=c.spin_a,
                spin_b=c.spin_b,
                observable=c.observable,
                value=c.value,
                sigma=c.sigma,
                sigma_source=c.sigma_source,
                multiplicity=c.multiplicity,
                equivalent_pairs=c.equivalent_pairs,
            )
            for c in project.couplings
        ),
        model=f"{project.model.kind} / {project.model.order}",
        estimand=ESTIMAND,
    )


# --------------------------------------------------------------------------- fit.preview
class PreviewIn(Wire):
    phi: Degrees


class PreviewCoupling(Wire):
    id: CouplingId
    label: str
    observed: Hertz
    sigma: Hertz
    calculated: Hertz
    residual: Hertz
    normalized_residual: float


class OrderOut(Wire):
    Szz: float
    Delta: float


class Validity(Wire):
    inner_rank: int
    inner_parameters: int
    inner_condition_number: float | None  # None when rank-deficient (no finite condition number)
    physically_admissible: bool


class PreviewOut(Wire):
    science_revision: int
    science_hash: str
    model: Literal["rigid"]
    frame: str
    estimand: str
    phi: Degrees
    order: OrderOut
    couplings: tuple[PreviewCoupling, ...]
    chi2: float
    n_obs: int
    rms_residual: Hertz
    validity: Validity
    numerical_context: dict[str, str | float]
    statement: str


def fit_preview(ctx: Context, p: PreviewIn) -> PreviewOut:
    state = ctx.read()  # one snapshot: the result names the revision it reflects
    project = _require_project(state)
    lo, hi = project.model.phi_domain_deg
    if not lo <= p.phi.value <= hi:
        raise OperationError(
            ErrorCode.OUT_OF_DOMAIN,
            f"φ = {p.phi.value}° is outside the model domain [{lo}°, {hi}°]",
            offending_field="phi.value",
            hint="the torsion domain is folded; see the estimand for the equivalent angles",
        )
    index = {s.id: i for i, s in enumerate(project.molecule.spins)}
    pairs = tuple((index[c.spin_a], index[c.spin_b]) for c in project.couplings)
    g = project.molecule.geometry
    geometry = BiphenylGeometry(r_cc=g.r_cc.value, r_ch=g.r_ch.value, r_inter=g.r_inter.value)
    y = np.array([c.value.value for c in project.couplings])
    sigma = np.array([c.sigma.value for c in project.couplings])
    sol = solve_inner(rigid_design(p.phi.value, pairs, geometry), y, sigma)
    szz, delta = (float(v) for v in sol.params)
    normalized = sol.residuals / sigma
    return PreviewOut(
        science_revision=state.science_revision,
        science_hash=state.science_hash,
        model="rigid",
        frame=FRAME,
        estimand=ESTIMAND,
        phi=deg(p.phi.value),
        order=OrderOut(Szz=szz, Delta=delta),
        couplings=tuple(
            PreviewCoupling(
                id=c.id,
                label=project.coupling_label(c),
                observed=c.value,
                sigma=c.sigma,
                calculated=hz(float(sol.predictions[i])),
                residual=hz(float(sol.residuals[i])),
                normalized_residual=float(normalized[i]),
            )
            for i, c in enumerate(project.couplings)
        ),
        chi2=sol.chi2,
        n_obs=sol.n_obs,
        rms_residual=hz(math.sqrt(float(np.mean(sol.residuals**2)))),
        validity=Validity(
            inner_rank=sol.rank,
            inner_parameters=sol.n_params,
            inner_condition_number=sol.condition if math.isfinite(sol.condition) else None,
            physically_admissible=is_admissible(constraint_diagonal() @ sol.params),
        ),
        numerical_context=numerical_context(),
        statement=(
            "Profile objective at fixed φ: the order parameters are re-solved by whitened SVD "
            "(known σ, not rescaled). This is a preview, not a fit: no ν, p-value or interval is implied."
        ),
    )


# --------------------------------------------------------------------------- view.select
class SelectIn(Wire):
    ids: Annotated[tuple[ObjectId, ...], Field(max_length=MAX_SELECTION)]


class SelectedObject(Wire):
    id: ObjectId
    kind: Literal["spin", "coupling"]
    label: str


class SelectOut(Wire):
    workspace_revision: int
    selection: tuple[SelectedObject, ...]


def _selected(project: Project | None, ids: tuple[str, ...]) -> tuple[SelectedObject, ...]:
    out: list[SelectedObject] = []
    for object_id in ids:
        found = project.label_of(object_id) if project else None
        if found is not None:
            kind, label = found
            out.append(SelectedObject(id=object_id, kind="spin" if kind == "spin" else "coupling", label=label))
    return tuple(out)


def view_select(ctx: Context, p: SelectIn) -> SelectOut:
    ids = tuple(dict.fromkeys(p.ids))  # de-duplicate, keep order

    def plan(state: SessionState) -> tuple[list[Event], SelectOut]:
        project = _require_project(state)
        for position, object_id in enumerate(ids):
            if project.label_of(object_id) is None:
                raise OperationError(
                    ErrorCode.ID_NOT_FOUND,
                    f"{object_id} is not a spin or coupling of the current project",
                    offending_field=f"ids[{position}]",
                    hint="read IDs from project.describe or fit.preview",
                )
        out = SelectOut(
            workspace_revision=state.workspace_revision + (ids != state.view.selection),
            selection=_selected(project, ids),
        )
        if ids == state.view.selection:
            return [], out  # nothing changes: no event, no revision
        event: Event = {
            "type": "view.selection_set",
            "domain": WORKSPACE,
            "selection": list(ids),
            "previous": list(state.view.selection),
        }
        return [event], out

    return ctx.commit("view.select", p.model_dump(mode="json"), plan)


# --------------------------------------------------------------------------- render.describe_view
class DescribeViewIn(Wire):
    pass


class DescribeViewOut(Wire):
    science_revision: int
    workspace_revision: int
    project_open: bool
    project_name: str | None
    selection: tuple[SelectedObject, ...]


def describe_view(ctx: Context, _: DescribeViewIn) -> DescribeViewOut:
    state = ctx.read()
    return DescribeViewOut(
        science_revision=state.science_revision,
        workspace_revision=state.workspace_revision,
        project_open=state.project is not None,
        project_name=state.project.name if state.project else None,
        selection=_selected(state.project, state.view.selection),
    )


# --------------------------------------------------------------------------- registry
def build_registry() -> Registry:
    registry = Registry()
    registry.register(
        Operation(
            name="project.open_example",
            kind="command",
            effect="model",
            capability=Capability.SCIENCE_MUTATION,
            summary="Replace the session's project with a bundled example dataset.",
            input_model=OpenExampleIn,
            output_model=OpenExampleOut,
            handler=open_example,
            revision_check="expected_science_revision (required)",
            examples=({"name": "biphenyl-synthetic", "expected_science_revision": 0},),
        )
    )
    registry.register(
        Operation(
            name="project.describe",
            kind="query",
            effect="none",
            capability=Capability.QUERY,
            summary="Describe the project: geometry, spins and observed couplings, with IDs and labels.",
            input_model=DescribeProjectIn,
            output_model=DescribeProjectOut,
            handler=describe_project,
            idempotent=True,
            examples=({},),
        )
    )
    registry.register(
        Operation(
            name="fit.preview",
            kind="query",
            effect="none",
            capability=Capability.PREVIEW,
            summary="Preview the fit at a fixed torsion: order parameters re-solved, predictions and residuals.",
            input_model=PreviewIn,
            output_model=PreviewOut,
            handler=fit_preview,
            idempotent=True,
            examples=({"phi": {"value": 37.0, "unit": "deg"}},),
        )
    )
    registry.register(
        Operation(
            name="view.select",
            kind="command",
            effect="view",
            capability=Capability.VIEW_WRITE,
            summary="Set the shared selection to the given spin or coupling IDs (replaces it).",
            input_model=SelectIn,
            output_model=SelectOut,
            handler=view_select,
            idempotent=True,
            revision_check="none: an absolute set; IDs are validated atomically and never reused",
            examples=({"ids": ["cpl_000002"]},),
        )
    )
    registry.register(
        Operation(
            name="render.describe_view",
            kind="query",
            effect="none",
            capability=Capability.QUERY,
            summary="Describe the shared view: revisions and the current selection, with labels.",
            input_model=DescribeViewIn,
            output_model=DescribeViewOut,
            handler=describe_view,
            idempotent=True,
            examples=({},),
        )
    )
    return registry
