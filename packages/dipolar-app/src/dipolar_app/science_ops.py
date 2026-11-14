"""The science operations of M2 step 1: every project the core can fit reaches the operations.

- **Projects:**
  - ``project.describe``: the project, its model, its estimand, and whether it is ready to fit;
  - ``project.import_xyz``: a new project on imported coordinates;
  - ``project.load``, ``project.export``: ``*.dipolar.json`` text.
- **The model:**
  - ``model.set``: kind, order model, frame and torsion domain;
  - ``molecule.set_torsion``: the four atoms of the imported torsion.
- **Couplings (D5):**
  - ``couplings.reconcile``: the proposed mapping and the diff, with no change;
  - ``couplings.import``: apply the import under a mapping the caller confirmed.
- **Fitting:**
  - ``fit.preview``: the profile objective at a fixed torsion, for any fittable project;
  - ``fit.landscape``: the same objective sampled over the torsion domain (M3 step 3);
  - ``fit.run``: the D3 fit, with intervals under the reporting policy (``dipolar_app.reporting``).

Every science mutation is one ``project.replaced`` event carrying the whole new project, checked
by ``validate_project`` first. Selected IDs that no longer exist are dropped in the same
transaction.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from functools import lru_cache
from typing import Annotated, Literal

import numpy as np
from dipolar_core.context import numerical_context
from dipolar_core.inference import is_admissible
from dipolar_core.problem import Problem
from pydantic import Field

from dipolar_app.errors import ErrorCode, OperationError
from dipolar_app.formats import (
    FormatError,
    ImportDiff,
    apply_import,
    dumps_project,
    loads_project,
    parse_couplings_csv,
    parse_xyz,
    project_from_xyz,
    reconcile,
)
from dipolar_app.project import BiphenylTemplate, ImportedGeometry, ModelSpec, Project, science_hash, short
from dipolar_app.registry import Context
from dipolar_app.reporting import interval_policy
from dipolar_app.schemas import Angstrom, CouplingId, Degrees, Hertz, Revision, SpinId, Wire, deg, hz
from dipolar_app.science import problem_for, validate_project
from dipolar_app.session import SCIENCE, WORKSPACE, Event, SessionState

#: Text arguments are bounded by the HTTP body limit too; this bounds the Python adapter alike.
MAX_TEXT = 1 << 20
Text = Annotated[str, Field(max_length=MAX_TEXT)]
#: The largest project the operations accept or create, measured as it travels (rounds 27–28): the
#: exported document as a JSON string with every non-ASCII character escaped. That is the largest
#: form any client sends (an astral character is 12 bytes as \uXXXX\uXXXX, 4 in UTF-8), so every
#: project in the session exports to a document that ``project.load`` accepts back over HTTP.
MAX_PROJECT_TRANSPORT = 32 << 20
#: ``project.load``'s HTTP request limit: the document plus the envelope and its other arguments.
LOAD_REQUEST_BYTES = MAX_PROJECT_TRANSPORT + (1 << 20)
ProjectText = Annotated[str, Field(max_length=MAX_PROJECT_TRANSPORT)]


def transport_size(text: str) -> int:
    """Bytes of ``text`` as a JSON string with non-ASCII escaped (an upper bound over encodings)."""
    return len(json.dumps(text))


Name = Annotated[str, Field(min_length=1, max_length=200)]
AtomIndex = Annotated[int, Field(ge=0, lt=1_000)]

#: Ethane, staggered, C–C along x (Å): the registry's import and torsion examples.
ETHANE_XYZ = (
    "8\nethane, staggered\n"
    "C 0 0 0\nC 1.54 0 0\n"
    "H -0.36 1.03 0\nH -0.36 -0.515 0.892\nH -0.36 -0.515 -0.892\n"
    "H 1.9 -1.03 0\nH 1.9 0.515 0.892\nH 1.9 0.515 -0.892\n"
)


def ethane_document() -> str:
    """A complete ``*.dipolar.json`` document (ethane, torsion H–C–C–H, no couplings yet)."""
    project = project_from_xyz(parse_xyz(ETHANE_XYZ), name="ethane", source="registry example", torsion=(2, 0, 1, 5))
    return dumps_project(project)


FRAMES = {
    "bisector": "bisector frame: z along the inter-ring axis (ring A at z < 0), x bisects the ring planes, y = z × x",
    "ring-a": "ring-A frame: z along the inter-ring axis, x in the plane of ring A",
    "input": "input frame of the imported coordinates, fixed to the non-moving fragment",
}
DOMAINS = {
    "acute": (
        "folded to [0°, 90°]; complete only when ring-B labels are assigned so that the torsion is acute "
        "(a precondition on the input)"
    ),
    "fixed-labels": "in [0°, 180°] at fixed ring-B labels (complete for every order model)",
}
JUMP_ESTIMAND = (
    "jump-model φ: the symmetric four-site jump among +φ, −φ, 180° − φ and 180° + φ with equal populations, "
    "φ in [0°, 90°] (complete at fixed labels; the model is invariant under the ring-B relabelling)"
)
IMPORTED_ESTIMAND = (
    "rigid effective dihedral τ(a–i–j–b) of the declared torsion, in degrees (IUPAC sign); the dihedral is "
    "periodic, and no symmetry equivalence is assumed for imported geometry"
)
_SYMMETRIES: tuple[tuple[str, bool, Callable[[float], float]], ...] = (
    ("−φ", False, lambda phi: -phi),
    ("180° − φ", True, lambda phi: 180.0 - phi),
    ("180° + φ", True, lambda phi: 180.0 + phi),
)
_PROBES = (23.0, 61.0)


@lru_cache(maxsize=64)
def template_equivalences(
    order: str, frame: str, r_cc: float, r_ch: float, r_inter: float
) -> tuple[tuple[str, bool, tuple[tuple[float, ...], ...]], ...]:
    """The rigid template model's torsion equivalences, derived from the core's own predictions
    (round 27): for each symmetry (φ′, ring B relabelled or not), the order map P with
    D(φ, pairs) t = D(φ′, pairs′) P t for every t, over all 45 proton pairs.

    Only exact signed permutations that hold at every probe torsion are reported, so a stated
    equivalence is always one the model has.
    """
    from dipolar_core.biphenyl import PROTON_LABELS, BiphenylGeometry, relabel_ring_b, rigid_design

    geometry = BiphenylGeometry(r_cc=r_cc, r_ch=r_ch, r_inter=r_inter)
    pairs = tuple((i, j) for i in range(len(PROTON_LABELS)) for j in range(i + 1, len(PROTON_LABELS)))
    relabelled = relabel_ring_b(pairs)
    out = []
    for label, relabel, image in _SYMMETRIES:
        maps = []
        for phi in _PROBES:
            a = rigid_design(phi, pairs, geometry, order=order, frame=frame)  # type: ignore[arg-type]
            b = rigid_design(image(phi), relabelled if relabel else pairs, geometry, order=order, frame=frame)  # type: ignore[arg-type]
            m, *_ = np.linalg.lstsq(b, a, rcond=None)
            rounded = np.round(m)
            exact = np.abs(b @ rounded - a).max() <= 1e-9 * max(1.0, float(np.abs(a).max()))
            signed_permutation = np.all(np.abs(rounded).sum(axis=0) == 1) and np.all(np.abs(rounded).sum(axis=1) == 1)
            maps.append(rounded if exact and signed_permutation else None)
        if maps[0] is not None and all(m is not None and np.array_equal(m, maps[0]) for m in maps):
            out.append((label, relabel, tuple(tuple(float(x) for x in row) for row in maps[0])))
    return tuple(out)


def equivalences_of(project: Project) -> tuple[str, ...]:
    """The stated equivalences of the project's model, in words."""
    from dipolar_core.biphenyl import ORDER_NAMES

    g, m = project.molecule.geometry, project.model
    if not isinstance(g, BiphenylTemplate):
        return ()
    if m.kind == "jump4":
        return ("φ, −φ, 180° − φ and 180° + φ are the same conformer set: one model, no sign choice",)
    names = ORDER_NAMES[m.order]
    lines = []
    for label, relabel, rows in template_equivalences(m.order, m.frame, g.r_cc.value, g.r_ch.value, g.r_inter.value):
        image = []
        for row in rows:
            k = next(i for i, x in enumerate(row) if x != 0)
            image.append(("−" if row[k] < 0 else "") + names[k])
        where = "with ring B relabelled (H2′↔H6′, H3′↔H5′)" if relabel else "at fixed labels"
        lines.append(f"(φ, {', '.join(names)}) predicts the same as ({label}, {', '.join(image)}) {where}")
    return tuple(lines)


def require_project(state: SessionState) -> Project:
    if state.project is None:
        raise OperationError(ErrorCode.NO_PROJECT, "the session has no project", hint="call project.open_example")
    return state.project


def check_revision(expected: int, state: SessionState) -> None:
    if expected != state.science_revision:
        raise OperationError(
            ErrorCode.REVISION_CONFLICT,
            "the science state changed since the caller last read it",
            offending_field="expected_science_revision",
            hint="read the current revision and retry if the change is still wanted",
            details={"current_science_revision": state.science_revision},
        )


def keep_allocator(state: SessionState, project: Project) -> Project:
    """``project`` with the session's coupling-ID high-water mark. A coupling ID is never handed
    out twice in a session, whatever replaces the project: loading an older file, opening an
    example, importing, undo or redo (D5; rounds 31–32)."""
    current = state.project
    if current is not None and current.next_coupling_id > project.next_coupling_id:
        return project.model_copy(update={"next_coupling_id": current.next_coupling_id})
    return project


def replace_project(
    state: SessionState, project: Project, *, field: str | None = None, same_project: bool = True
) -> list[Event]:
    """The events that put ``project`` in the session, validated first.

    ``same_project``: the change edits the current project (model, torsion, couplings), so the
    selection keeps the IDs that still exist. Otherwise (another document, an import, undo or
    redo) the IDs may name different objects, so the selection is cleared (round 32). The caller
    passes ``keep_allocator(state, project)``; a lower coupling-ID counter is refused here.
    """
    if state.project is not None and project.next_coupling_id < state.project.next_coupling_id:
        raise AssertionError("replace_project needs keep_allocator: the coupling-ID counter would go down")
    try:
        validate_project(project)
    except ValueError as exc:
        raise OperationError(ErrorCode.INVALID_ARGUMENT, str(exc), offending_field=field) from None
    size = transport_size(dumps_project(project))
    if size > MAX_PROJECT_TRANSPORT:  # it could not be exported and loaded back (rounds 27–28)
        raise OperationError(
            ErrorCode.INVALID_ARGUMENT,
            f"the project would take {size} bytes to send as a file, above the limit of {MAX_PROJECT_TRANSPORT}",
            offending_field=field,
        )
    events: list[Event] = [
        {
            "type": "project.replaced",
            "domain": SCIENCE,
            "project": project.model_dump(mode="json"),
            "previous_science_hash": state.science_hash,
        }
    ]
    for kind, key, current in (
        ("view.selection_set", "selection", state.view.selection),
        ("view.highlights_set", "highlights", state.view.highlights),
    ):
        kept = tuple(x for x in current if project.label_of(x) is not None) if same_project else ()
        if kept != current:
            events.append({"type": kind, "domain": WORKSPACE, key: list(kept), "previous": list(current)})
    return events


def estimand_of(project: Project) -> str:
    m = project.model
    if isinstance(project.molecule.geometry, ImportedGeometry):
        return IMPORTED_ESTIMAND
    if m.kind == "jump4":
        return JUMP_ESTIMAND
    domain = "acute" if m.phi_domain_deg == (0.0, 90.0) else "fixed-labels"
    return f"rigid effective inter-ring torsion φ, {DOMAINS[domain]}"


def readiness(project: Project) -> str | None:
    """None if the project can be fitted, or why it cannot. The model is evaluated at both ends and
    the middle of the domain, so "ready" means the design can actually be computed (round 27)."""
    try:
        problem = problem_for(project)
        lo, hi = project.model.phi_domain_deg
        for phi in (lo, 0.5 * (lo + hi), hi):
            problem.checked_design(np.array([phi]))
    except ValueError as exc:
        return str(exc)
    return None


def _problem(project: Project) -> Problem:
    reason = readiness(project)
    if reason is not None:
        raise OperationError(
            ErrorCode.PROJECT_NOT_READY,
            f"the project cannot be fitted yet: {reason}",
            hint="project.describe reports what is missing",
        )
    return problem_for(project)


def _structural_problem(project: Project) -> Problem:
    """The project's problem without evaluating it anywhere: refused only when something is
    missing (no torsion, no couplings, an unsupported domain). For the queries that evaluate one
    torsion at a time (fit.preview, fit.landscape), a torsion where the model cannot be evaluated is
    that torsion's problem, not the project's (round 47: a collision at the domain's midpoint used
    to refuse the whole landscape)."""
    try:
        return problem_for(project)
    except ValueError as exc:
        raise OperationError(
            ErrorCode.PROJECT_NOT_READY,
            f"the project cannot be fitted yet: {exc}",
            hint="project.describe reports what is missing",
        ) from None


def _not_evaluable(exc: ValueError) -> OperationError:
    """A model that fails to evaluate somewhere in its domain (for example, two spins meeting at
    one torsion): a structured error, never an internal one (round 27)."""
    return OperationError(
        ErrorCode.PROJECT_NOT_READY,
        f"the model cannot be evaluated: {exc}",
        hint="check the geometry for atoms that meet as the torsion turns (molecule.set_torsion, model.set)",
    )


# --------------------------------------------------------------------------- project.describe
class SpinOut(Wire):
    id: SpinId
    label: str
    isotope: str
    atom: int | None


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
    source_labels: tuple[str, str] | None


class TemplateOut(Wire):
    kind: Literal["template"]
    template: str
    r_cc: Angstrom
    r_ch: Angstrom
    r_inter: Angstrom


class AtomOut(Wire):
    index: int
    element: str
    x: float
    y: float
    z: float


class ImportedOut(Wire):
    kind: Literal["imported"]
    source_format: str
    atoms: tuple[AtomOut, ...]
    torsion: tuple[int, int, int, int] | None


class ModelOut(Wire):
    kind: Literal["rigid", "jump4"]
    order: Literal["bisector-diagonal", "c2z", "c1"]
    frame: Literal["bisector", "ring-a", "input"]
    phi_domain: tuple[Degrees, Degrees]


class DescribeProjectIn(Wire):
    pass


class DescribeProjectOut(Wire):
    science_revision: int
    science_hash: str
    name: str
    source: str
    geometry: TemplateOut | ImportedOut
    spins: tuple[SpinOut, ...]
    couplings: tuple[CouplingOut, ...]
    model: ModelOut
    frame: str
    estimand: str
    equivalences: tuple[str, ...]
    ready_to_fit: bool
    not_ready_reason: str | None


def _model_out(m: ModelSpec) -> ModelOut:
    lo, hi = m.phi_domain_deg
    return ModelOut(kind=m.kind, order=m.order, frame=m.frame, phi_domain=(deg(lo), deg(hi)))


def describe_project(ctx: Context, _: DescribeProjectIn) -> DescribeProjectOut:
    state = ctx.read()
    project = require_project(state)
    g = project.molecule.geometry
    geometry: TemplateOut | ImportedOut
    if isinstance(g, BiphenylTemplate):
        geometry = TemplateOut(kind="template", template=g.template, r_cc=g.r_cc, r_ch=g.r_ch, r_inter=g.r_inter)
    else:
        geometry = ImportedOut(
            kind="imported",
            source_format=g.source_format,
            atoms=tuple(AtomOut(index=i, element=a.element, x=a.x, y=a.y, z=a.z) for i, a in enumerate(g.atoms)),
            torsion=g.torsion,
        )
    reason = readiness(project)
    return DescribeProjectOut(
        science_revision=state.science_revision,
        science_hash=state.science_hash,
        name=project.name,
        source=project.source,
        geometry=geometry,
        spins=tuple(SpinOut(id=s.id, label=s.label, isotope=s.isotope, atom=s.atom) for s in project.molecule.spins),
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
                source_labels=c.source_labels,
            )
            for c in project.couplings
        ),
        model=_model_out(project.model),
        frame=FRAMES[project.model.frame],
        estimand=estimand_of(project),
        equivalences=equivalences_of(project),
        ready_to_fit=reason is None,
        not_ready_reason=reason,
    )


# --------------------------------------------------------------------------- shared science outputs
class Science(Wire):
    science_revision: int
    science_hash: str


class NamedValue(Wire):
    name: str
    value: float


class FittedCoupling(Wire):
    id: CouplingId
    label: str
    observed: Hertz
    sigma: Hertz
    calculated: Hertz
    residual: Hertz
    normalized_residual: float


def _fitted(project: Project, predictions: np.ndarray, residuals: np.ndarray) -> tuple[FittedCoupling, ...]:
    return tuple(
        FittedCoupling(
            id=c.id,
            label=project.coupling_label(c),
            observed=c.value,
            sigma=c.sigma,
            calculated=hz(float(predictions[i])),
            residual=hz(float(residuals[i])),
            normalized_residual=float(residuals[i] / c.sigma.value),
        )
        for i, c in enumerate(project.couplings)
    )


def _named(names: tuple[str, ...], values: np.ndarray) -> tuple[NamedValue, ...]:
    return tuple(NamedValue(name=n, value=float(v)) for n, v in zip(names, values, strict=True))


# --------------------------------------------------------------------------- fit.preview
class PreviewIn(Wire):
    phi: Degrees


class PreviewValidity(Wire):
    inner_rank: int
    inner_parameters: int
    inner_condition_number: float | None  # None when rank-deficient (no finite condition number)
    physically_admissible: bool | None


class PreviewOut(Wire):
    science_revision: int
    science_hash: str
    model: ModelOut
    frame: str
    estimand: str
    phi: Degrees
    order: tuple[NamedValue, ...]
    couplings: tuple[FittedCoupling, ...]
    chi2: float
    n_obs: int
    rms_residual: Hertz
    validity: PreviewValidity
    numerical_context: dict[str, str | float]
    statement: str


def fit_preview(ctx: Context, p: PreviewIn) -> PreviewOut:
    state = ctx.read()  # one snapshot: the result names the revision it reflects
    project = require_project(state)
    lo, hi = project.model.phi_domain_deg
    if not lo <= p.phi.value <= hi:
        raise OperationError(
            ErrorCode.OUT_OF_DOMAIN,
            f"φ = {p.phi.value}° is outside the model domain [{lo}°, {hi}°]",
            offending_field="phi.value",
            hint="the torsion domain is set by model.set; see the estimand for the equivalent angles",
        )
    problem = _structural_problem(project)
    try:
        sol = problem.inner(np.array([p.phi.value]))
    except ValueError as exc:
        raise _not_evaluable(exc) from None
    return PreviewOut(
        science_revision=state.science_revision,
        science_hash=state.science_hash,
        model=_model_out(project.model),
        frame=FRAMES[project.model.frame],
        estimand=estimand_of(project),
        phi=deg(p.phi.value),
        order=_named(problem.order_names, sol.params),
        couplings=_fitted(project, sol.predictions, sol.residuals),
        chi2=sol.chi2,
        n_obs=sol.n_obs,
        rms_residual=hz(math.sqrt(float(np.mean(sol.residuals**2)))),
        validity=PreviewValidity(
            inner_rank=sol.rank,
            inner_parameters=sol.n_params,
            inner_condition_number=sol.condition if math.isfinite(sol.condition) else None,
            physically_admissible=None if problem.s5_map is None else is_admissible(problem.s5_map @ sol.params),
        ),
        numerical_context=numerical_context(),
        statement=(
            "Profile objective at fixed φ: the order parameters are re-solved by whitened SVD "
            "(known σ, not rescaled). This is a preview, not a fit: no ν, p-value or interval is implied."
        ),
    )


# --------------------------------------------------------------------------- fit.landscape
#: Samples of the landscape by default (every 0.5° on the acute domain), and at most.
LANDSCAPE_POINTS = 181
MAX_LANDSCAPE_POINTS = 1441


class LandscapeIn(Wire):
    points: Annotated[int, Field(ge=2, le=MAX_LANDSCAPE_POINTS)] = LANDSCAPE_POINTS


class LandscapeOut(Wire):
    science_revision: int
    science_hash: str
    model: ModelOut
    estimand: str
    unit: Literal["deg"]
    phi: tuple[float, ...]  # evenly spaced over the model's torsion domain, both ends included
    chi2: tuple[float | None, ...]  # None where the model cannot be evaluated
    physically_admissible: tuple[bool | None, ...]  # None when not assessed (or not evaluable)
    n_obs: int
    numerical_context: dict[str, str | float]
    statement: str


def fit_landscape(ctx: Context, p: LandscapeIn) -> LandscapeOut:
    """The profile objective of fit.preview, sampled over the whole torsion domain: the χ²(φ)
    landscape that the live preview moves along (M3 step 3)."""
    state = ctx.read()
    project = require_project(state)
    lo, hi = project.model.phi_domain_deg
    problem = _structural_problem(project)
    phis = [float(v) for v in np.linspace(lo, hi, p.points)]
    chi2: list[float | None] = []
    admissible: list[bool | None] = []
    for phi in phis:
        try:
            sol = problem.inner(np.array([phi]))
        except ValueError:  # for example two spins meeting at this torsion
            chi2.append(None)
            admissible.append(None)
            continue
        chi2.append(float(sol.chi2) if math.isfinite(sol.chi2) else None)
        admissible.append(None if problem.s5_map is None else bool(is_admissible(problem.s5_map @ sol.params)))
    return LandscapeOut(
        science_revision=state.science_revision,
        science_hash=state.science_hash,
        model=_model_out(project.model),
        estimand=estimand_of(project),
        unit="deg",
        phi=tuple(phis),
        chi2=tuple(chi2),
        physically_admissible=tuple(admissible),
        n_obs=int(problem.y.shape[0]),
        numerical_context=numerical_context(),
        statement=(
            "The fit.preview objective (order parameters re-solved at each φ, known σ) at evenly "
            "spaced torsions. A preview, not a fit: its lowest sample locates the minimum only to "
            "the spacing, and no interval is implied."
        ),
    )


# --------------------------------------------------------------------------- fit.run (computed by a job)
class BasinOut(Wire):
    theta: tuple[NamedValue, ...]
    chi2: float
    delta_chi2: float


class FitValidity(Wire):
    inner_rank: int
    inner_parameters: int
    inner_condition_number: float | None
    joint_rank: int
    joint_parameters: int
    converged: bool
    physically_admissible: bool | None
    at_bound: tuple[str, ...]
    search_resolved: bool
    derivatives_resolved: bool
    regular: bool


class IntervalOut(Wire):
    parameter: str
    kind: Literal["profile"]
    label: str
    estimate: float
    lower: float | None
    upper: float | None
    supported: bool
    note: str


class FitRunOut(Wire):
    science_revision: int
    science_hash: str
    model: ModelOut
    frame: str
    estimand: str
    notes: tuple[str, ...]
    theta: tuple[NamedValue, ...]
    order: tuple[NamedValue, ...]
    chi2: float
    n_obs: int
    p_free: int
    nu: int | None
    p_value: float | None
    adequate: bool | None
    validity: FitValidity
    stderr: tuple[NamedValue, ...] | None
    unidentified: tuple[tuple[NamedValue, ...], ...]
    basins: tuple[BasinOut, ...]
    couplings: tuple[FittedCoupling, ...]
    rms_residual: Hertz
    intervals_policy: str
    intervals: tuple[IntervalOut, ...]
    fit_version: str
    numerical_context: dict[str, str | float]
    statement: str


def compute_fit(project: Project, intervals: bool, science_revision: int, science_hash: str) -> FitRunOut:
    """The D3 fit of ``project``, as a job computes it (``dipolar_app.jobs``). Pure: it reads no
    session state, so it runs the same in a worker thread or a worker process."""
    from dipolar_core.fit import FIT_VERSION, fit, profile_interval  # SciPy stays off the start path

    problem = _problem(project)
    try:
        result = fit(problem)
    except ValueError as exc:
        raise _not_evaluable(exc) from None
    v = result.validity
    policy = interval_policy(result)
    out: list[IntervalOut] = []
    if intervals:
        estimates = dict(zip(result.names, (*result.theta, *result.order), strict=True))
        for name in result.names:
            if policy.allowed:
                try:
                    iv = profile_interval(problem, result, name)
                except ValueError as exc:
                    raise _not_evaluable(exc) from None
                out.append(
                    IntervalOut(
                        parameter=name,
                        kind="profile",
                        label=iv.label,
                        estimate=iv.estimate,
                        lower=iv.lower,
                        upper=iv.upper,
                        supported=iv.supported,
                        note=iv.note,
                    )
                )
            else:
                out.append(
                    IntervalOut(
                        parameter=name,
                        kind="profile",
                        label="68.3% one-parameter (Δχ² = 1)",
                        estimate=float(estimates[name]),
                        lower=None,
                        upper=None,
                        supported=False,
                        note=f"interval not supported: {policy.reason}",
                    )
                )
    return FitRunOut(
        science_revision=science_revision,
        science_hash=science_hash,
        model=_model_out(project.model),
        frame=FRAMES[project.model.frame],
        estimand=estimand_of(project),
        notes=result.notes,
        theta=_named(problem.theta_names, result.theta),
        order=_named(problem.order_names, result.order),
        chi2=result.chi2,
        n_obs=result.n_obs,
        p_free=result.p_free,
        nu=result.nu,
        p_value=result.p_value,
        adequate=policy.adequate,
        validity=FitValidity(
            inner_rank=v.inner_rank,
            inner_parameters=v.inner_parameters,
            inner_condition_number=v.inner_condition_number,
            joint_rank=v.joint_rank,
            joint_parameters=v.joint_parameters,
            converged=v.converged,
            physically_admissible=v.physically_admissible,
            at_bound=v.at_bound,
            search_resolved=v.search_resolved,
            derivatives_resolved=v.derivatives_resolved,
            regular=v.regular,
        ),
        stderr=None if result.covariance is None else _named(result.covariance.names, result.covariance.stderr),
        unidentified=tuple(tuple(NamedValue(name=k, value=x) for k, x in d.items()) for d in result.unidentified),
        basins=tuple(
            BasinOut(theta=_named(problem.theta_names, b.theta), chi2=b.chi2, delta_chi2=b.delta_chi2)
            for b in result.basins
        ),
        couplings=_fitted(project, result.predictions, result.residuals),
        rms_residual=hz(math.sqrt(float(np.mean(result.residuals**2)))),
        intervals_policy=policy.statement,
        intervals=tuple(out),
        fit_version=FIT_VERSION,
        numerical_context=numerical_context(),
        statement=(
            "D3 fit: grid and multistart scan, bounded refinement of the variable-projection residual, "
            "known σ (not rescaled by χ²/ν). Standard errors come from the full Jacobian and only for a "
            "regular optimum."
        ),
    )


# --------------------------------------------------------------------------- model.set
class ModelSetIn(Wire):
    kind: Literal["rigid", "jump4"]
    order: Literal["bisector-diagonal", "c2z", "c1"]
    frame: Literal["bisector", "ring-a", "input"]
    phi_domain: tuple[Degrees, Degrees]
    expected_science_revision: Revision


class ModelSetOut(Science):
    model: ModelOut
    ready_to_fit: bool
    not_ready_reason: str | None


def model_set(ctx: Context, p: ModelSetIn) -> ModelSetOut:
    spec = ModelSpec(
        kind=p.kind, order=p.order, frame=p.frame, phi_domain_deg=(p.phi_domain[0].value, p.phi_domain[1].value)
    )

    def plan(state: SessionState) -> tuple[list[Event], ModelSetOut]:
        check_revision(p.expected_science_revision, state)
        project = require_project(state).model_copy(update={"model": spec})
        if isinstance(project.molecule.geometry, BiphenylTemplate):
            supported = {(0.0, 90.0)} if spec.kind == "jump4" else {(0.0, 90.0), (0.0, 180.0)}
            if spec.phi_domain_deg not in supported:
                raise OperationError(
                    ErrorCode.OUT_OF_DOMAIN,
                    f"the template's {spec.kind} model supports the domains "
                    f"{sorted(supported)} only, not {list(spec.phi_domain_deg)}",
                    offending_field="phi_domain",
                    hint="[0, 90] is the acute domain; [0, 180] keeps ring-B labels fixed (rigid only)",
                )
        events = replace_project(state, project)
        reason = readiness(project)
        return events, ModelSetOut(
            science_revision=state.science_revision + 1,
            science_hash=science_hash(project),
            model=_model_out(spec),
            ready_to_fit=reason is None,
            not_ready_reason=reason,
        )

    return ctx.commit("model.set", p.model_dump(mode="json"), plan)


# --------------------------------------------------------------------------- project.import_xyz
class ImportXyzIn(Wire):
    xyz: Text
    name: Name
    source: Annotated[str, Field(max_length=2000)] = ""
    torsion: tuple[AtomIndex, AtomIndex, AtomIndex, AtomIndex] | None = None
    order: Literal["c2z", "c1"] = "c1"
    expected_science_revision: Revision


class ImportXyzOut(Science):
    n_atoms: int
    n_spins: int
    ready_to_fit: bool
    not_ready_reason: str | None


def import_xyz(ctx: Context, p: ImportXyzIn) -> ImportXyzOut:
    try:
        molecule = parse_xyz(p.xyz)
        project = project_from_xyz(
            molecule, name=p.name, source=p.source or "imported XYZ", torsion=p.torsion, order=p.order
        )
    except (FormatError, ValueError) as exc:  # ValidationError is a ValueError
        raise OperationError(ErrorCode.INVALID_ARGUMENT, str(exc), offending_field="xyz") from None

    def plan(state: SessionState) -> tuple[list[Event], ImportXyzOut]:
        check_revision(p.expected_science_revision, state)
        imported = keep_allocator(state, project)
        events = replace_project(state, imported, field="torsion", same_project=False)
        reason = readiness(imported)
        return events, ImportXyzOut(
            science_revision=state.science_revision + 1,
            science_hash=science_hash(imported),
            n_atoms=len(molecule.elements),
            n_spins=len(project.molecule.spins),
            ready_to_fit=reason is None,
            not_ready_reason=reason,
        )

    return ctx.commit("project.import_xyz", p.model_dump(mode="json"), plan)


# --------------------------------------------------------------------------- molecule.set_torsion
class SetTorsionIn(Wire):
    torsion: tuple[AtomIndex, AtomIndex, AtomIndex, AtomIndex]
    expected_science_revision: Revision


class SetTorsionOut(Science):
    torsion: tuple[int, int, int, int]
    phi0: Degrees


def set_torsion(ctx: Context, p: SetTorsionIn) -> SetTorsionOut:
    def plan(state: SessionState) -> tuple[list[Event], SetTorsionOut]:
        check_revision(p.expected_science_revision, state)
        project = require_project(state)
        g = project.molecule.geometry
        if not isinstance(g, ImportedGeometry):
            raise OperationError(
                ErrorCode.OUT_OF_DOMAIN,
                "the biphenyl template has a fixed torsion; only imported geometry declares one",
                offending_field="torsion",
            )
        new = project.model_copy(
            update={
                "molecule": project.molecule.model_copy(
                    update={"geometry": g.model_copy(update={"torsion": p.torsion})}
                )
            }
        )
        events = replace_project(state, new, field="torsion")
        from dipolar_app.science import _torsion_geometry

        phi0 = _torsion_geometry(new.molecule.geometry).phi0_deg  # type: ignore[arg-type]
        return events, SetTorsionOut(
            science_revision=state.science_revision + 1,
            science_hash=science_hash(new),
            torsion=p.torsion,
            phi0=deg(phi0),
        )

    return ctx.commit("molecule.set_torsion", p.model_dump(mode="json"), plan)


# --------------------------------------------------------------------------- couplings.reconcile / couplings.import
class PairValues(Wire):
    value: Hertz
    sigma: Hertz


class PairOut(Wire):
    spin_a: SpinId
    spin_b: SpinId
    label: str
    # What the project has for this pair (null when it is new) and what the import would set
    # (null when the import removes it), so a wrong mapping shows as a wrong value (M3 step 2).
    before: PairValues | None
    after: PairValues | None


class ReconcileIn(Wire):
    csv: Text
    mapping: Annotated[dict[Annotated[str, Field(max_length=200)], SpinId], Field(max_length=1_000)] | None = None


class ReconcileOut(Science):
    proposed_mapping: dict[str, SpinId]
    unmatched_labels: tuple[str, ...]
    unresolved_pairs: tuple[str, ...]
    complete: bool
    added: tuple[PairOut, ...]
    removed: tuple[PairOut, ...]
    changed: tuple[PairOut, ...]
    unchanged: tuple[PairOut, ...]
    ignored_columns: tuple[str, ...]


def _pairs(project: Project, keys: tuple[tuple[str, str], ...], diff: ImportDiff) -> tuple[PairOut, ...]:
    def label(i: str) -> str:
        s = project.spin(i)
        return short(s.label) if s else i

    current = {(min(c.spin_a, c.spin_b), max(c.spin_a, c.spin_b)): c for c in project.couplings}

    def before(key: tuple[str, str]) -> PairValues | None:
        c = current.get((min(key), max(key)))
        return None if c is None else PairValues(value=c.value, sigma=c.sigma)

    def after(key: tuple[str, str]) -> PairValues | None:
        row = diff.incoming.get(key)
        return None if row is None else PairValues(value=hz(row.value_hz), sigma=hz(row.sigma_hz))

    return tuple(
        PairOut(spin_a=a, spin_b=b, label=f"{label(a)}–{label(b)}", before=before((a, b)), after=after((a, b)))
        for a, b in keys
    )


def couplings_reconcile(ctx: Context, p: ReconcileIn) -> ReconcileOut:
    state = ctx.read()
    project = require_project(state)
    try:
        table = parse_couplings_csv(p.csv)
        diff = reconcile(table, project, p.mapping)
    except (FormatError, ValueError) as exc:  # ValidationError is a ValueError
        raise OperationError(ErrorCode.INVALID_ARGUMENT, str(exc), offending_field="csv") from None
    return ReconcileOut(
        science_revision=state.science_revision,
        science_hash=state.science_hash,
        proposed_mapping=dict(diff.proposed_mapping),
        unmatched_labels=diff.unmatched_labels,
        unresolved_pairs=diff.unresolved_pairs,
        complete=not diff.unmatched_labels and not diff.unresolved_pairs,
        added=_pairs(project, diff.added, diff),
        removed=_pairs(project, diff.removed, diff),
        changed=_pairs(project, diff.changed, diff),
        unchanged=_pairs(project, diff.unchanged, diff),
        ignored_columns=table.ignored_columns,
    )


class ImportCouplingsIn(Wire):
    csv: Text
    confirmed_mapping: Annotated[dict[Annotated[str, Field(max_length=200)], SpinId], Field(max_length=1_000)]
    expected_science_revision: Revision


class ImportCouplingsOut(Science):
    n_couplings: int
    added: int
    removed: int
    changed: int
    unchanged: int
    ready_to_fit: bool
    not_ready_reason: str | None


def couplings_import(ctx: Context, p: ImportCouplingsIn) -> ImportCouplingsOut:
    try:
        table = parse_couplings_csv(p.csv)
    except (FormatError, ValueError) as exc:  # ValidationError is a ValueError
        raise OperationError(ErrorCode.INVALID_ARGUMENT, str(exc), offending_field="csv") from None

    def plan(state: SessionState) -> tuple[list[Event], ImportCouplingsOut]:
        check_revision(p.expected_science_revision, state)
        project = require_project(state)
        try:
            diff = reconcile(table, project, p.confirmed_mapping)
            if diff.unmatched_labels or diff.unresolved_pairs:
                missing = [*diff.unmatched_labels, *diff.unresolved_pairs]
                raise FormatError(f"the confirmed mapping leaves labels or pairs unresolved: {missing}")
            new = apply_import(project, table, p.confirmed_mapping)
        except (FormatError, ValueError) as exc:  # ValidationError is a ValueError
            raise OperationError(
                ErrorCode.INVALID_ARGUMENT,
                str(exc),
                offending_field="confirmed_mapping",
                hint="couplings.reconcile proposes a mapping and shows the diff",
            ) from None
        events = replace_project(state, new, field="csv")
        reason = readiness(new)
        return events, ImportCouplingsOut(
            science_revision=state.science_revision + 1,
            science_hash=science_hash(new),
            n_couplings=len(new.couplings),
            added=len(diff.added),
            removed=len(diff.removed),
            changed=len(diff.changed),
            unchanged=len(diff.unchanged),
            ready_to_fit=reason is None,
            not_ready_reason=reason,
        )

    return ctx.commit("couplings.import", p.model_dump(mode="json"), plan)


# --------------------------------------------------------------------------- project.load / project.export
class LoadIn(Wire):
    text: ProjectText
    expected_science_revision: Revision


class LoadOut(Science):
    name: str
    n_spins: int
    n_couplings: int


def project_load(ctx: Context, p: LoadIn) -> LoadOut:
    try:
        project = loads_project(p.text)
    except (FormatError, ValueError) as exc:  # ValidationError is a ValueError
        raise OperationError(ErrorCode.INVALID_ARGUMENT, str(exc), offending_field="text") from None

    def plan(state: SessionState) -> tuple[list[Event], LoadOut]:
        check_revision(p.expected_science_revision, state)
        loaded = keep_allocator(state, project)
        events = replace_project(state, loaded, field="text", same_project=False)
        return events, LoadOut(
            science_revision=state.science_revision + 1,
            science_hash=science_hash(loaded),
            name=project.name,
            n_spins=len(project.molecule.spins),
            n_couplings=len(project.couplings),
        )

    return ctx.commit("project.load", p.model_dump(mode="json"), plan)


class ExportIn(Wire):
    pass


class ExportOut(Science):
    filename: str
    text: str


def project_export(ctx: Context, _: ExportIn) -> ExportOut:
    state = ctx.read()
    project = require_project(state)
    stem = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in project.name).strip("-") or "project"
    return ExportOut(
        science_revision=state.science_revision,
        science_hash=state.science_hash,
        filename=f"{stem}.dipolar.json",
        text=dumps_project(project),
    )
