"""The D3 inference stack (plan §3 D3, ADR-0003): separable least squares with honest validity.

A model predicts y ≈ D(θ)·t:
- θ are bounded nonlinear geometry parameters (for example the torsion φ);
- t are the free order parameters;
- D(θ) = A(θ)·C is the design matrix.

The error covariance Σ is known and never rescaled (``dipolar_core.problem``). The fit is:

1. **Starts.** A profile scan: on a grid for one geometry parameter (its local minima become
   starts), or on seeded Sobol points for several. With Sobol points, the starts are the
   lowest-χ² points among the local minima of the nearest-neighbour graph, which keeps them
   spatially diverse. The profile objective re-solves t at every θ (variable projection), and
   each scan point records its own validity diagnostics (D3.5).
2. **Refinement.** Every start is refined by bounded TRF (`scipy.optimize.least_squares`) on the
   *residual vector* of the profile, never on the scalar χ².
3. **Basins.** Converged refinements are deduplicated into basins, reported with their Δχ² from
   the best one. Refinements that did not converge are reported separately as unfinished, never
   as basins. A finite search cannot prove that it found every basin; it reports every basin it
   found.
4. **Uncertainty.** Covariance comes from the **full** whitened Jacobian in joint coordinates
   (θ, t). Its rank is the joint rank, reported separately from the inner rank. A complete basis of
   the directions the data do not determine is named, and those directions never get finite error
   bars.
5. **Intervals.** Profile intervals (the other parameters re-minimized from each known basin, up
   to MAX_PROFILE_STARTS)
   and slice intervals (the other parameters held fixed) are distinct functions with labelled
   results. The interval is not supported, and no number is invented, when:
   - the optimum is irregular;
   - another basin inside the threshold has this parameter outside the interval (that proves a
     second component of the profile's level set);
   - a side reaches a bound;
   - the region continues beyond an endpoint;
   - a constrained re-minimization fails.

   Crossings are searched by geometric sampling outward from the optimum, and every interval is
   then verified by sampling it evenly. A feature narrower than the sampling can still be missed.
   The label states the one-parameter coverage of the raw Δχ² threshold under regular asymptotics.
6. **Validity.** The flags are independent of each other: inner rank and condition number, joint
   rank, convergence, admissibility, bounds and interval support.

Degrees of freedom: ν = N − p_free applies only to a regular, identifiable interior optimum.
Otherwise ν and the p-value are None.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Final, Literal

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import brentq, least_squares
from scipy.special import chdtr, chdtrc

from dipolar_core.inference import RANK_RTOL, is_admissible
from dipolar_core.problem import DesignFunction as DesignFunction
from dipolar_core.problem import Problem as Problem

Array = NDArray[np.float64]

#: Version of this stack's numerical choices (enters the numerical context when an operation uses it).
FIT_VERSION: Final = "varpro-trf.4"
#: Relative distance (in units of the bound range) under which two refined optima are one basin.
BASIN_RTOL: Final = 1e-6
#: A geometry parameter is at a bound if TRF reports the bound active, or if it lies within
#: BOUND_ATOL · max(1, |bound|) of it (an absolute scale, independent of the opposite bound).
BOUND_ATOL: Final = 1e-9
#: A refinement converged only if TRF stopped on a tolerance (status > 0) *and* a first-order
#: certificate holds at the result:
#: - J is our own second-order Jacobian of the residual, not TRF's two-point estimate (round 14);
#: - the free parameters are those not at a bound, plus those at a bound whose gradient points
#:   back into the domain (the KKT sign test);
#: - the predicted Gauss–Newton reduction over the free parameters, ‖P_J r‖², must be at most
#:   DECREMENT_ATOL + ATTAINABLE_FACTOR · tolerance · χ².
#: The second term is the resolution TRF can reach: it ignores improvements below tolerance·χ²/2
#: (its relative ftol), so a large but finished misfit is not mistaken for non-convergence (round
#: 14). Above χ² ≈ 1e13 that floor approaches the Δχ² = 1 interval scale; double precision limits
#: such fits. The measure is in χ² units and independent of the units of θ.
DECREMENT_ATOL: Final = 1e-8
ATTAINABLE_FACTOR: Final = 10.0
#: At a bound, an inward gradient no larger than its own rounding noise counts as zero (binding).
#: Differencing the model part m costs about ε·‖m‖/h, so the gradient's noise is about
#: GRADIENT_NOISE_FACTOR · ε^(2/3) · ‖m‖ · ‖r‖ / max(1, |xᵢ|) (round 15).
GRADIENT_NOISE_FACTOR: Final = 10.0
#: Constrained re-minimizations in a profile start from at most this many known basins.
MAX_PROFILE_STARTS: Final = 16
#: Outward sampling for interval crossings: first distance = Gauss–Newton step · 2^FIRST_EXPONENT;
#: each bracket found is subdivided into SUBDIVISIONS parts to locate the first crossing.
FIRST_EXPONENT: Final = -10
MAX_DOUBLINGS: Final = 60
SUBDIVISIONS: Final = 8
#: Every interval is verified before it is accepted: the profile is sampled at this many evenly
#: spaced interior points (plus any known grid values inside). A sample above the threshold means
#: the region has a gap, which the outward search stepped over (round 15).
INTERVAL_SAMPLES: Final = 64
#: Beyond each endpoint, the profile is probed at these multiples of the interval width.
COMPONENT_PROBES: Final = (0.25, 0.5, 1.0, 2.0, 4.0)


def coverage_label(delta_chi2: float) -> str:
    """One-parameter coverage of a raw Δχ² threshold under regular asymptotics (1.00 → 68.3 %)."""
    return f"{100 * float(chdtr(1, delta_chi2)):.1f}% one-parameter (Δχ² = {delta_chi2:g})"


# --------------------------------------------------------------------------- settings
@dataclass(frozen=True)
class Settings:
    """Search and refinement settings (written policies, D3).

    ``grid``: for one geometry parameter, strictly increasing scan points inside the bounds.
    The default is an even grid over the bounds with spacing at most 0.5, and at least 181 points.
    ``n_sobol`` (a power of two) and ``n_starts``: for several parameters, the number of Sobol
    points, and how many local minima of the scan are refined. ``seed`` makes the Sobol scramble
    reproducible.
    """

    grid: Array | None = None
    n_sobol: int = 256
    n_starts: int = 8
    seed: int = 19980101
    tolerance: float = 1e-15
    max_nfev: int = 2000

    def __post_init__(self) -> None:
        if self.grid is not None:
            g = np.asarray(self.grid, dtype=np.float64)
            if g.ndim != 1 or g.size == 0 or not np.all(np.isfinite(g)) or np.any(np.diff(g) <= 0):
                raise ValueError("the grid must be a non-empty, finite, strictly increasing vector")
        if self.n_sobol < 2 or self.n_sobol & (self.n_sobol - 1):
            raise ValueError("n_sobol must be a power of two, at least 2")
        if self.n_starts < 1:
            raise ValueError("n_starts must be at least 1")
        if not (math.isfinite(self.tolerance) and self.tolerance > 0):
            raise ValueError("tolerance must be positive and finite")
        if self.max_nfev < 1:
            raise ValueError("max_nfev must be at least 1")


# --------------------------------------------------------------------------- results
@dataclass(frozen=True)
class Scan:
    """The profile objective at the scan points, with each point's own diagnostics (D3.5).

    ``starts`` index the points refined. Convergence and interval support do not apply to scan
    points. ``inner_condition`` is inf where the inner rank is deficient.
    """

    points: Array  # n × k
    chi2: Array  # n
    starts: tuple[int, ...]
    inner_rank: NDArray[np.int64]
    inner_condition: Array
    joint_rank: NDArray[np.int64]
    admissible: NDArray[np.bool_] | None

    @property
    def minima(self) -> tuple[int, ...]:  # the name used for one-parameter grids
        return self.starts


@dataclass(frozen=True)
class Basin:
    theta: Array
    chi2: float
    delta_chi2: float  # χ² − χ²_best
    converged: bool
    message: str
    active: tuple[bool, ...]  # bound active per geometry parameter, as reported by TRF


@dataclass(frozen=True)
class Covariance:
    """Covariance in joint coordinates (θ then t); known Σ, not rescaled by χ²/ν."""

    names: tuple[str, ...]
    matrix: Array
    stderr: Array
    correlation: Array


@dataclass(frozen=True)
class Validity:
    """Independent indicators (D3.5). None means "not applicable"."""

    inner_rank: int
    inner_parameters: int
    inner_condition_number: float | None
    joint_rank: int
    joint_parameters: int
    converged: bool
    physically_admissible: bool | None
    at_bound: tuple[str, ...]
    search_resolved: bool  # no unfinished refinement reached a lower χ² than the best basin
    regular: bool  # converged, resolved, interior, full inner and joint rank: the conditions for ν and intervals


@dataclass(frozen=True)
class FitResult:
    theta: Array
    order: Array
    chi2: float
    n_obs: int
    p_free: int
    nu: int | None
    p_value: float | None
    predictions: Array
    residuals: Array  # y − predictions (Hz)
    scan: Scan
    basins: tuple[Basin, ...]  # converged and distinct, best first
    unfinished: tuple[Basin, ...]  # refinements that did not converge: not basins
    covariance: Covariance | None  # None unless the optimum is regular
    unidentified: tuple[dict[str, float], ...]  # a complete basis of the null space of J
    validity: Validity
    names: tuple[str, ...] = field(default=())


@dataclass(frozen=True)
class Interval:
    """A Δχ² interval for one parameter. ``kind`` is "profile" (others re-minimized) or "slice"
    (others fixed at the optimum). ``lower``/``upper`` are None where not supported, and ``note``
    gives the reason."""

    parameter: str
    kind: Literal["profile", "slice"]
    delta_chi2: float
    label: str
    estimate: float
    lower: float | None
    upper: float | None
    supported: bool
    note: str


# --------------------------------------------------------------------------- scan and refinement
def _grid_minima(values: Array) -> tuple[int, ...]:
    out = []
    for i in range(len(values)):
        left = values[i - 1] if i > 0 else math.inf
        right = values[i + 1] if i + 1 < len(values) else math.inf
        if values[i] <= left and values[i] <= right:
            out.append(i)
    return tuple(out)


def _neighbour_minima(unit_points: Array, values: Array, n_starts: int) -> tuple[int, ...]:
    """Local minima of the nearest-neighbour graph (2k neighbours), lowest χ² first."""
    n, k = unit_points.shape
    m = min(2 * k, n - 1)
    distances = np.linalg.norm(unit_points[:, None, :] - unit_points[None, :, :], axis=-1)
    neighbours = np.argsort(distances, axis=1)[:, 1 : m + 1]
    minima = [i for i in range(n) if np.all(values[i] <= values[neighbours[i]])]
    minima.sort(key=lambda i: values[i])
    return tuple(minima[:n_starts])


def scan(problem: Problem, settings: Settings) -> Scan:
    if problem.k == 1:
        if settings.grid is not None:
            grid = np.asarray(settings.grid, dtype=np.float64)
            if grid[0] < problem.lower[0] or grid[-1] > problem.upper[0]:
                raise ValueError("the grid must lie inside the bounds")
        else:
            lo, hi = float(problem.lower[0]), float(problem.upper[0])
            grid = np.linspace(lo, hi, max(181, math.ceil((hi - lo) / 0.5) + 1))
        points = grid[:, None]
    else:
        from scipy.stats import qmc  # only multi-parameter searches pay for scipy.stats

        sobol = qmc.Sobol(d=problem.k, scramble=True, seed=settings.seed)
        unit = sobol.random(settings.n_sobol)
        points = qmc.scale(unit, problem.lower, problem.upper)
    inner = [problem.inner(pt) for pt in points]
    values = np.array([s.chi2 for s in inner])
    if problem.k == 1:
        starts = _grid_minima(values)
    else:
        unit_points = (points - problem.lower) / (problem.upper - problem.lower)
        starts = _neighbour_minima(unit_points, values, settings.n_starts)
    joint = []
    for pt, sol in zip(points, inner, strict=True):
        s = np.linalg.svd(full_jacobian(problem, pt, sol.params), compute_uv=False)
        joint.append(int(np.count_nonzero(s > RANK_RTOL * s[0])) if s.size and s[0] > 0 else 0)
    admissible = None
    if problem.s5_map is not None:
        admissible = np.array([is_admissible(problem.s5_map @ sol.params) for sol in inner], dtype=bool)
    return Scan(
        points=points,
        chi2=values,
        starts=starts,
        inner_rank=np.array([s.rank for s in inner], dtype=np.int64),
        inner_condition=np.array([s.condition for s in inner]),
        joint_rank=np.array(joint, dtype=np.int64),
        admissible=admissible,
    )


def _least_squares(fun: Any, x0: Array, lower: Array, upper: Array, settings: Settings, jac: Any = "2-point") -> Any:
    return least_squares(
        fun,
        np.clip(x0, lower, upper),
        jac=jac,
        bounds=(lower, upper),
        method="trf",
        x_scale="jac",
        xtol=settings.tolerance,
        ftol=settings.tolerance,
        gtol=settings.tolerance,
        max_nfev=settings.max_nfev,
    )


#: A VarPro sub-problem in its free coordinates x: model(x) = (D_free, F) with prediction
#: D_free · t + F, where t is re-solved for every x. F holds any fixed order contribution.
Model = Callable[[Array], tuple[Array, Array]]


def _whole(problem: Problem) -> Model:
    return lambda x: (problem.checked_design(x), np.zeros(len(problem.y)))


def _varpro_jacobian(
    problem: Problem, model: Model, x: Array, lower: Array, upper: Array
) -> tuple[Array, Array, Array]:
    """(r, J, ∂m) at x for a VarPro sub-problem: the exact Golub–Pereyra Jacobian.

    With A = W·D, t* = A⁺·W(y − F) and r = W·(D t* + F − y):

        J = (I − QQᵀ)·∂m − (A⁺)ᵀ·(∂Aᵀ·r)

    where Q spans A and ∂m = W·(∂D·t* + ∂F) is the derivative of the model part with t* held
    fixed. Only the model and the design are differenced, never the data. The residual holds the
    constant −W·y, and differencing it would cost ε·‖r‖ of rounding (round 14). The gradient
    Jᵀr = ∂mᵀ·r is exact, by the envelope theorem, because A⁺·r = 0. TRF and the convergence
    certificate both use this J.
    """
    x = np.asarray(x, dtype=np.float64)
    d_free, fixed = model(x)
    p_free = d_free.shape[1]
    t = problem.solve(d_free, problem.y - fixed).params if p_free else np.empty(0)
    r = problem.whiten(d_free @ t + fixed - problem.y)
    a = problem.whiten(d_free)
    if p_free:
        u, sv, vt = np.linalg.svd(a, full_matrices=False)
        keep = sv > RANK_RTOL * sv[0] if sv[0] > 0 else np.zeros_like(sv, dtype=bool)
        q, pinv_t = u[:, keep], u[:, keep] @ (vt[keep] / sv[keep, None])  # (A⁺)ᵀ = Q S⁻¹ Vᵀ
    else:
        q, pinv_t = np.empty((len(r), 0)), np.empty((len(r), 0))
    n = len(r)
    dm_columns, j_columns = [], []
    for i in range(len(x)):

        def stacked(v: float, i: int = i) -> Array:
            shifted = x.copy()
            shifted[i] = v
            d, f = model(shifted)
            return np.concatenate([problem.whiten(d @ t + f), problem.whiten(d).ravel()])

        derivative = _derivative(stacked, float(x[i]), float(lower[i]), float(upper[i]))
        dm = derivative[:n]
        da = derivative[n:].reshape(n, p_free)
        dm_columns.append(dm)
        j_columns.append(dm - q @ (q.T @ dm) - pinv_t @ (da.T @ r))
    if not dm_columns:
        empty = np.empty((n, 0))
        return r, empty, empty
    return r, np.column_stack(j_columns), np.column_stack(dm_columns)


def _converged(
    problem: Problem, model: Model, result: Any, lower: Array, upper: Array, tolerance: float
) -> tuple[bool, str]:
    """TRF stopped on a tolerance, and the first-order certificate holds (see DECREMENT_ATOL and
    ``_varpro_jacobian``)."""
    if result.status <= 0:
        return False, str(result.message)
    x = np.asarray(result.x, dtype=np.float64)
    r, jac, dm = _varpro_jacobian(problem, model, x, lower, upper)
    gradient = dm.T @ r  # of ½‖r‖² (envelope theorem)
    model_norm = float(np.linalg.norm(r + problem.whiten(problem.y)))  # ‖W·(D t* + F)‖
    active_mask = np.asarray(result.active_mask)
    interior, inward = [], 0.0
    for i in range(len(x)):
        at_lower = active_mask[i] < 0 or _near(float(x[i]), float(lower[i]))
        at_upper = active_mask[i] > 0 or _near(float(x[i]), float(upper[i]))
        if not (at_lower or at_upper):
            interior.append(i)
            continue
        # KKT: a bound binds when the gradient points out of the domain. Otherwise the predicted
        # reduction along this coordinate is limited by the feasible step (the room to the other
        # bound), so a tiny, noisy column cannot promise a huge reduction (round 15).
        g = float(gradient[i])
        noise = GRADIENT_NOISE_FACTOR * np.finfo(float).eps ** (2 / 3) * model_norm * float(np.linalg.norm(r))
        noise /= max(1.0, abs(float(x[i])))
        if (at_lower and g >= -noise) or (at_upper and g <= noise):
            continue
        curvature = float(jac[:, i] @ jac[:, i])
        room = float(upper[i] - x[i]) if at_lower else float(x[i] - lower[i])
        step_len = min(abs(g) / curvature, room) if curvature > 0 else room
        inward += 2 * (abs(g) * step_len - 0.5 * curvature * step_len**2)  # in χ² units (χ² = 2·cost)
    decrement = inward
    if interior:
        u, sv, _ = np.linalg.svd(jac[:, interior], full_matrices=False)
        keep = sv > RANK_RTOL * sv[0] if sv.size and sv[0] > 0 else np.zeros_like(sv, dtype=bool)
        projected = u[:, keep].T @ r
        decrement += float(projected @ projected)
    if decrement > 0:
        floor = ATTAINABLE_FACTOR * tolerance * float(r @ r)
        if decrement > DECREMENT_ATOL + floor:
            why = f"predicted χ² reduction {decrement:.3g}"
            return False, f"stopped ({result.message}) at a non-stationary point: {why}"
    return True, str(result.message)


def _refine(problem: Problem, start: Array, settings: Settings) -> Basin:
    model, lo, hi = _whole(problem), problem.lower, problem.upper

    def jac(x: Array) -> Array:
        return _varpro_jacobian(problem, model, x, lo, hi)[1]

    result = _least_squares(problem.profile_residual, start, lo, hi, settings, jac)
    theta = np.asarray(result.x, dtype=np.float64)
    active = tuple(bool(a) for a in result.active_mask)
    converged, message = _converged(problem, model, result, lo, hi, settings.tolerance)
    return Basin(theta, problem.inner(theta).chi2, 0.0, converged, message, active)


def _dedupe(problem: Problem, trials: list[Basin], best: float) -> tuple[Basin, ...]:
    span = problem.upper - problem.lower
    kept: list[Basin] = []
    for trial in sorted(trials, key=lambda b: b.chi2):
        if all(np.max(np.abs(trial.theta - other.theta) / span) > BASIN_RTOL for other in kept):
            kept.append(trial)
    return tuple(Basin(b.theta, b.chi2, b.chi2 - best, b.converged, b.message, b.active) for b in kept)


# --------------------------------------------------------------------------- derivatives
def _derivative(fun: Callable[[float], Array], x: float, lo: float, hi: float) -> Array:
    """d fun / dx at x without evaluating outside [lo, hi].

    - A centred difference when it fits.
    - Otherwise a second-order one-sided difference toward the roomier side, with its step shrunk
      to fit inside the range.

    An off-centre secant would invent a derivative at a stationary point (round 13), and a fixed
    one-sided step fails on narrow ranges (round 14). The base step is ε^(1/3)·max(1, |x|).
    """
    h = float(np.cbrt(np.finfo(float).eps)) * max(1.0, abs(x))
    room_lo, room_hi = x - lo, hi - x
    centred = min(h, room_lo, room_hi)
    if centred >= h / 16:
        return (fun(x + centred) - fun(x - centred)) / (2 * centred)
    room, sign = (room_hi, 1.0) if room_hi >= room_lo else (room_lo, -1.0)
    step = min(h, room / 2)
    if not step > 0:
        raise ValueError("a zero-width range cannot be differentiated")
    return sign * (-3 * fun(x) + 4 * fun(x + sign * step) - fun(x + 2 * sign * step)) / (2 * step)


def _jacobian(residual: Callable[[Array], Array], x: Array, lower: Array, upper: Array) -> Array:
    x = np.asarray(x, dtype=np.float64)
    columns = []
    for i in range(len(x)):

        def along(v: float, i: int = i) -> Array:
            shifted = x.copy()
            shifted[i] = v
            return residual(shifted)

        columns.append(_derivative(along, float(x[i]), float(lower[i]), float(upper[i])))
    return np.column_stack(columns) if columns else np.empty((len(residual(x)), 0))


def full_jacobian(problem: Problem, theta: Array, t: Array) -> Array:
    """Whitened J of the joint residual in (θ, t): geometry columns from ``_derivative``, order
    columns exact."""
    theta = np.asarray(theta, dtype=np.float64)
    # Differentiate the whitened prediction W·D(θ)·t only, never the data: the constant −W·y would
    # cost ε·‖r‖ of rounding and can invent a derivative, and with it a joint rank (round 15).
    geometry = _jacobian(lambda th: problem.whiten(problem.checked_design(th) @ t), theta, problem.lower, problem.upper)
    return np.column_stack([geometry, problem.whiten(problem.checked_design(theta))])


def _near(value: float, bound: float) -> bool:
    """At a bound: within BOUND_ATOL · max(1, |bound|), on the bound's own scale (round 13)."""
    return abs(value - bound) <= BOUND_ATOL * max(1.0, abs(bound))


# --------------------------------------------------------------------------- the fit
def fit(problem: Problem, settings: Settings | None = None) -> FitResult:
    settings = settings or Settings()
    sc = scan(problem, settings)
    trials = [_refine(problem, sc.points[i], settings) for i in sc.starts]
    converged = [t for t in trials if t.converged]
    reference = min(t.chi2 for t in (converged or trials))
    basins = _dedupe(problem, converged, reference)
    unfinished = _dedupe(problem, [t for t in trials if not t.converged], reference)
    best = basins[0] if basins else unfinished[0]
    sol = problem.inner(best.theta)
    j = full_jacobian(problem, best.theta, sol.params)
    # A complete right basis: the reduced SVD gives it when N ≥ p_free; full matrices only when N < p_free.
    _, s, vt = np.linalg.svd(j, full_matrices=j.shape[0] < j.shape[1])
    joint_rank = int(np.count_nonzero(s > RANK_RTOL * s[0])) if s.size and s[0] > 0 else 0
    names = problem.names
    unidentified = tuple(
        {n: float(v) for n, v in zip(names, row, strict=True) if abs(v) > 1e-9} for row in vt[joint_rank:]
    )

    at_bound = tuple(
        name
        for i, name in enumerate(problem.theta_names)
        if best.active[i]
        or _near(float(best.theta[i]), float(problem.lower[i]))
        or _near(float(best.theta[i]), float(problem.upper[i]))
    )
    p_free = problem.k + problem.p
    resolved = best.converged and all(u.chi2 >= best.chi2 for u in unfinished)
    regular = resolved and not at_bound and joint_rank == p_free and sol.rank == problem.p
    covariance = None
    if regular:
        matrix = (vt[:joint_rank].T / s[:joint_rank] ** 2) @ vt[:joint_rank]  # (JᵀJ)⁻¹ from the SVD
        stderr = np.sqrt(np.diag(matrix))
        covariance = Covariance(names, matrix, stderr, matrix / np.outer(stderr, stderr))
    nu = len(problem.y) - p_free if regular else None
    p_value = float(chdtrc(nu, sol.chi2)) if nu is not None and nu > 0 else None  # χ² survival function
    validity = Validity(
        inner_rank=sol.rank,
        inner_parameters=problem.p,
        inner_condition_number=sol.condition if math.isfinite(sol.condition) else None,
        joint_rank=joint_rank,
        joint_parameters=p_free,
        converged=best.converged,
        physically_admissible=None if problem.s5_map is None else is_admissible(problem.s5_map @ sol.params),
        at_bound=at_bound,
        search_resolved=resolved,
        regular=regular,
    )
    return FitResult(
        theta=best.theta,
        order=sol.params,
        chi2=sol.chi2,
        n_obs=len(problem.y),
        p_free=p_free,
        nu=nu,
        p_value=p_value,
        predictions=sol.predictions,
        residuals=sol.residuals,
        scan=sc,
        basins=basins,
        unfinished=unfinished,
        covariance=covariance,
        unidentified=unidentified,
        validity=validity,
        names=names,
    )


# --------------------------------------------------------------------------- profiles and slices
def _profile_chi2(
    problem: Problem, result: FitResult, index: int, value: float, settings: Settings
) -> tuple[float, bool]:
    """χ² with parameter ``index`` held at ``value``, every other parameter re-minimized from each
    known basin (at most MAX_PROFILE_STARTS). Returns (χ², converged)."""
    k = problem.k
    starts = [b.theta for b in result.basins[:MAX_PROFILE_STARTS]] or [result.theta]
    best, ok = math.inf, False
    if index < k:
        free = [i for i in range(k) if i != index]

        def theta_of(free_values: Array) -> Array:
            theta = result.theta.copy()
            theta[index] = value
            theta[free] = free_values
            return theta

        if not free:
            return problem.inner(theta_of(np.empty(0))).chi2, True

        def free_residual(f: Array) -> Array:
            return problem.profile_residual(theta_of(f))

        def free_model(f: Array) -> tuple[Array, Array]:
            return problem.checked_design(theta_of(f)), np.zeros(len(problem.y))

        lo, hi = problem.lower[free], problem.upper[free]

        def free_jac(f: Array) -> Array:
            return _varpro_jacobian(problem, free_model, f, lo, hi)[1]

        failed = math.inf
        for start in starts:
            res = _least_squares(free_residual, start[free], lo, hi, settings, free_jac)
            chi2 = problem.inner(theta_of(np.asarray(res.x))).chi2
            if _converged(problem, free_model, res, lo, hi, settings.tolerance)[0]:
                best, ok = min(best, chi2), True
            else:
                failed = min(failed, chi2)
        # A failed run that went lower disproves the accepted minimum (round 15): unresolved.
        return (failed, False) if failed < best else (best, ok)

    column = index - k
    others = [c for c in range(problem.p) if c != column]

    def reduced(theta: Array) -> Array:
        d = problem.checked_design(theta)
        target = problem.y - d[:, column] * value
        if not others:
            return problem.whiten(-target)
        return problem.whiten(-problem.solve(d[:, others], target).residuals)

    def reduced_model(theta: Array) -> tuple[Array, Array]:
        d = problem.checked_design(theta)
        return d[:, others], d[:, column] * value

    def reduced_jac(theta: Array) -> Array:
        return _varpro_jacobian(problem, reduced_model, theta, problem.lower, problem.upper)[1]

    failed = math.inf
    for start in starts:
        res = _least_squares(reduced, start, problem.lower, problem.upper, settings, reduced_jac)
        r = reduced(np.asarray(res.x))
        if _converged(problem, reduced_model, res, problem.lower, problem.upper, settings.tolerance)[0]:
            best, ok = min(best, float(r @ r)), True
        else:
            failed = min(failed, float(r @ r))
    return (failed, False) if failed < best else (best, ok)


def _slice_chi2(problem: Problem, result: FitResult, index: int, value: float) -> tuple[float, bool]:
    theta, t = result.theta.copy(), result.order.copy()
    if index < problem.k:
        theta[index] = value
    else:
        t[index - problem.k] = value
    r = problem.joint_residual(theta, t)
    return float(r @ r), True


class _Unsupported(Exception):
    pass


def _interval(
    problem: Problem,
    result: FitResult,
    name: str,
    kind: Literal["profile", "slice"],
    delta_chi2: float,
    settings: Settings | None,
) -> Interval:
    if not (math.isfinite(delta_chi2) and delta_chi2 > 0):
        raise ValueError("delta_chi2 must be positive and finite")
    settings = settings or Settings()
    index = problem.names.index(name)
    estimate = float(result.theta[index] if index < problem.k else result.order[index - problem.k])
    label = coverage_label(delta_chi2)

    def unsupported(note: str) -> Interval:
        return Interval(name, kind, delta_chi2, label, estimate, None, None, False, "interval not supported: " + note)

    if not result.validity.regular or result.covariance is None:
        return unsupported("the optimum is not regular (bound, rank, convergence or an unresolved search)")
    # Other basins inside the threshold, with this parameter's value there. The profile at that
    # value is at most the basin's χ², so the value belongs to the profile's level set.
    rivals = []
    if kind == "profile":
        for basin in (*result.basins[1:], *result.unfinished):
            if basin.chi2 - result.chi2 <= delta_chi2:
                value = (
                    basin.theta[index] if index < problem.k else problem.inner(basin.theta).params[index - problem.k]
                )
                rivals.append((float(value), basin))

    def excess(value: float) -> float:
        if kind == "profile":
            chi2, ok = _profile_chi2(problem, result, index, value, settings)
        else:
            chi2, ok = _slice_chi2(problem, result, index, value)
        if not ok:
            raise _Unsupported(f"the constrained re-minimization at {name} = {value:.6g} did not converge")
        return chi2 - result.chi2 - delta_chi2

    bound_lo = float(problem.lower[index]) if index < problem.k else -math.inf
    bound_hi = float(problem.upper[index]) if index < problem.k else math.inf
    step = float(result.covariance.stderr[index]) * math.sqrt(delta_chi2)

    # For one geometry parameter the profile *is* the scan objective: reuse the grid values.
    known: list[tuple[float, float]] = []
    if kind == "profile" and index < problem.k and problem.k == 1:
        known = [
            (float(pt[0]), float(c) - result.chi2 - delta_chi2)
            for pt, c in zip(result.scan.points, result.scan.chi2, strict=True)
        ]

    def first_crossing(direction: float, inner_d: float, outer_d: float) -> float | None:
        """The first point in (inner_d, outer_d] above the threshold, located by sampling: the
        known grid values inside the segment (one geometry parameter), and its outer end."""
        marks = {outer_d}
        for value, _ in known:
            d = (value - estimate) * direction
            if inner_d < d <= outer_d:
                marks.add(d)
        previous = inner_d
        for mark in sorted(marks):
            if excess(estimate + direction * mark) > 0:
                # Refine within (previous, mark] to the first positive subsample, then the root.
                sub_prev = previous
                for sub in np.linspace(previous, mark, SUBDIVISIONS + 1)[1:]:
                    if excess(estimate + direction * float(sub)) > 0:
                        lo, hi = sorted((estimate + direction * sub_prev, estimate + direction * float(sub)))
                        return float(brentq(excess, lo, hi, xtol=1e-14, rtol=1e-14, maxiter=200))
                    sub_prev = float(sub)
            previous = mark
        return None

    def endpoint(direction: float) -> float:
        side = "lower" if direction < 0 else "upper"
        bound = bound_lo if direction < 0 else bound_hi
        inner_d = 0.0
        for m in range(FIRST_EXPONENT, MAX_DOUBLINGS):
            outer_d = step * 2.0**m
            hit_bound = (estimate + direction * outer_d - bound) * direction >= 0
            if hit_bound:
                outer_d = abs(bound - estimate)
            crossing = first_crossing(direction, inner_d, outer_d)
            if crossing is not None:
                return crossing
            if hit_bound:
                raise _Unsupported(f"the {side} side reaches the bound {bound:g}")
            inner_d = outer_d
        raise _Unsupported(f"the {side} side never crosses the threshold")

    try:
        lower, upper = endpoint(-1.0), endpoint(1.0)
        for value, basin in rivals:
            if not lower <= value <= upper:  # in the level set but not in this interval: a second component
                if not basin.converged:
                    raise _Unsupported(
                        f"an unfinished refinement reached Δχ² = {basin.chi2 - result.chi2:.3g} at {name} = {value:.6g}"
                    )
                raise _Unsupported(
                    f"another basin has {name} = {value:.6g} at Δχ² = {basin.chi2 - result.chi2:.3g}, outside "
                    f"[{lower:.6g}, {upper:.6g}]: the region has several components"
                )
        interior = np.linspace(lower, upper, INTERVAL_SAMPLES + 2)[1:-1].tolist()
        interior += [v for v, _ in known if lower < v < upper]
        for point in sorted(interior):
            if excess(float(point)) > 0:
                raise _Unsupported(
                    f"the profile rises above the threshold at {name} = {point:.6g}, inside "
                    f"[{lower:.6g}, {upper:.6g}]: the region has a gap (several components)"
                )
        width = upper - lower
        for direction, end in ((-1.0, lower), (1.0, upper)):
            for factor in COMPONENT_PROBES:
                probe = min(max(end + direction * factor * width, bound_lo), bound_hi)
                if probe != end and excess(probe) <= 0:
                    raise _Unsupported(f"the region continues beyond {end:.6g} (at {probe:.6g}): several components")
    except _Unsupported as why:
        return unsupported(str(why))
    return Interval(name, kind, delta_chi2, label, estimate, lower, upper, True, "")


def profile_interval(
    problem: Problem, result: FitResult, name: str, delta_chi2: float = 1.0, settings: Settings | None = None
) -> Interval:
    """Profile interval: χ²(value) re-minimized over every other parameter, raw Δχ² threshold."""
    return _interval(problem, result, name, "profile", delta_chi2, settings)


def slice_interval(problem: Problem, result: FitResult, name: str, delta_chi2: float = 1.0) -> Interval:
    """Slice interval: every other parameter held at the optimum. Narrower than the profile when
    parameters are correlated; it is labelled so it is never mistaken for a profile."""
    return _interval(problem, result, name, "slice", delta_chi2, None)
