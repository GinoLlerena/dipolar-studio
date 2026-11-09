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
5. **Intervals.** Profile intervals (the other parameters re-minimized from every known basin)
   and slice intervals (the other parameters held fixed) are distinct functions with labelled
   results. The interval is not supported, and no number is invented, when:
   - the optimum is irregular;
   - another basin lies inside the threshold;
   - a side reaches a bound;
   - the region continues beyond an endpoint;
   - a constrained re-minimization fails.

   Crossings are searched by geometric sampling outward from the optimum, so a feature narrower
   than the sampling can still be missed. The label states the one-parameter coverage of the raw
   Δχ² threshold under regular asymptotics.
6. **Validity.** The flags are independent of each other: inner rank and condition number, joint
   rank, convergence, admissibility, bounds and interval support.

Degrees of freedom: ν = N − p_free applies only to a regular, identifiable interior optimum.
Otherwise ν and the p-value are None.
"""

from __future__ import annotations

import math
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
FIT_VERSION: Final = "varpro-trf.2"
#: Relative distance (in units of the bound range) under which two refined optima are one basin.
BASIN_RTOL: Final = 1e-6
#: A geometry parameter is at a bound if TRF reports the bound active, or if it lies within
#: BOUND_ATOL · max(1, |bound|) of it (an absolute scale, independent of the opposite bound).
BOUND_ATOL: Final = 1e-9
#: A refinement converged only if TRF stopped on a tolerance (status > 0) *and* the predicted
#: Gauss–Newton reduction of χ² over the free parameters, ‖P_J r‖², is at most DECREMENT_ATOL. This
#: is in χ² units, so it is negligible next to the Δχ² = 1 interval scale and independent of the
#: units of θ. It catches TRF stopping on ftol at a point that is not stationary (round 13).
DECREMENT_ATOL: Final = 1e-8
#: Constrained re-minimizations in a profile start from at most this many known basins.
MAX_PROFILE_STARTS: Final = 16
#: Outward sampling for interval crossings: first distance = Gauss–Newton step · 2^FIRST_EXPONENT;
#: each bracket found is subdivided into SUBDIVISIONS parts to locate the first crossing.
FIRST_EXPONENT: Final = -10
MAX_DOUBLINGS: Final = 60
SUBDIVISIONS: Final = 8
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


def _least_squares(fun: Any, x0: Array, lower: Array, upper: Array, settings: Settings) -> Any:
    return least_squares(
        fun,
        np.clip(x0, lower, upper),
        bounds=(lower, upper),
        method="trf",
        x_scale="jac",
        xtol=settings.tolerance,
        ftol=settings.tolerance,
        gtol=settings.tolerance,
        max_nfev=settings.max_nfev,
    )


def _converged(result: Any) -> tuple[bool, str]:
    """Status > 0 and a negligible predicted Gauss–Newton reduction (see DECREMENT_ATOL)."""
    if result.status <= 0:
        return False, str(result.message)
    jac = np.asarray(result.jac)[:, np.asarray(result.active_mask) == 0]
    if jac.size:
        u, s, _ = np.linalg.svd(jac, full_matrices=False)
        keep = s > RANK_RTOL * s[0] if s[0] > 0 else np.zeros_like(s, dtype=bool)
        projected = u[:, keep].T @ np.asarray(result.fun)
        decrement = float(projected @ projected)
        if decrement > DECREMENT_ATOL:
            why = f"predicted χ² reduction {decrement:.3g}"
            return False, f"stopped ({result.message}) at a non-stationary point: {why}"
    return True, str(result.message)


def _refine(problem: Problem, start: Array, settings: Settings) -> Basin:
    result = _least_squares(problem.profile_residual, start, problem.lower, problem.upper, settings)
    theta = np.asarray(result.x, dtype=np.float64)
    active = tuple(bool(a) for a in result.active_mask)
    converged, message = _converged(result)
    return Basin(theta, problem.inner(theta).chi2, 0.0, converged, message, active)


def _dedupe(problem: Problem, trials: list[Basin], best: float) -> tuple[Basin, ...]:
    span = problem.upper - problem.lower
    kept: list[Basin] = []
    for trial in sorted(trials, key=lambda b: b.chi2):
        if all(np.max(np.abs(trial.theta - other.theta) / span) > BASIN_RTOL for other in kept):
            kept.append(trial)
    return tuple(Basin(b.theta, b.chi2, b.chi2 - best, b.converged, b.message, b.active) for b in kept)


# --------------------------------------------------------------------------- the full Jacobian
def full_jacobian(problem: Problem, theta: Array, t: Array) -> Array:
    """Whitened J of the joint residual in (θ, t).

    Order columns are exact. Geometry columns use a stencil that never leaves the bounds:
    - a centred difference when it fits;
    - a second-order one-sided difference at or very near a bound.
    An off-centre secant would invent a derivative at a stationary point (validation round 13).
    The base step is ε^(1/3)·max(1, |θᵢ|).
    """
    j = np.empty((len(problem.y), problem.k + problem.p))
    theta = np.asarray(theta, dtype=np.float64)

    def at(i: int, offset: float) -> Array:
        shifted = theta.copy()
        shifted[i] = theta[i] + offset
        return problem.joint_residual(shifted, t)

    for i in range(problem.k):
        h = float(np.cbrt(np.finfo(float).eps)) * max(1.0, abs(float(theta[i])))
        room_lo, room_hi = float(theta[i] - problem.lower[i]), float(problem.upper[i] - theta[i])
        centred = min(h, room_lo, room_hi)
        if centred >= h / 16:
            j[:, i] = (at(i, centred) - at(i, -centred)) / (2 * centred)
        elif room_hi >= 2 * h:
            j[:, i] = (-3 * at(i, 0.0) + 4 * at(i, h) - at(i, 2 * h)) / (2 * h)
        elif room_lo >= 2 * h:
            j[:, i] = (3 * at(i, 0.0) - 4 * at(i, -h) + at(i, -2 * h)) / (2 * h)
        else:  # a bound range narrower than the step: the widest centred stencil that fits
            if centred <= 0:
                raise ValueError(f"the bounds of {problem.theta_names[i]} are too narrow to differentiate")
            j[:, i] = (at(i, centred) - at(i, -centred)) / (2 * centred)
    j[:, problem.k :] = problem.whiten(problem.checked_design(theta))
    return j


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
    _, s, vt = np.linalg.svd(j, full_matrices=True)  # full: a complete null basis even when N < p_free
    joint_rank = int(np.count_nonzero(s > RANK_RTOL * s[0])) if s.size and s[0] > 0 else 0
    names = problem.names
    unidentified = tuple(
        {n: float(v) for n, v in zip(names, row, strict=True) if abs(v) > 1e-12} for row in vt[joint_rank:]
    )

    def near(value: float, bound: float) -> bool:  # each bound on its own scale (round 13, finding 9)
        return abs(value - bound) <= BOUND_ATOL * max(1.0, abs(bound))

    at_bound = tuple(
        name
        for i, name in enumerate(problem.theta_names)
        if best.active[i]
        or near(float(best.theta[i]), float(problem.lower[i]))
        or near(float(best.theta[i]), float(problem.upper[i]))
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
        for start in starts:
            res = _least_squares(
                lambda f: problem.profile_residual(theta_of(f)),
                start[free],
                problem.lower[free],
                problem.upper[free],
                settings,
            )
            if _converged(res)[0]:
                best, ok = min(best, problem.inner(theta_of(np.asarray(res.x))).chi2), True
        return best, ok

    column = index - k
    others = [c for c in range(problem.p) if c != column]

    def reduced(theta: Array) -> Array:
        d = problem.checked_design(theta)
        target = problem.y - d[:, column] * value
        if not others:
            return problem.whiten(-target)
        return problem.whiten(-problem.solve(d[:, others], target).residuals)

    for start in starts:
        res = _least_squares(reduced, start, problem.lower, problem.upper, settings)
        if _converged(res)[0]:
            r = reduced(np.asarray(res.x))
            best, ok = min(best, float(r @ r)), True
    return best, ok


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
    if kind == "profile":
        for basin in (*result.basins[1:], *result.unfinished):
            if basin.chi2 - result.chi2 <= delta_chi2:
                where = ", ".join(f"{n} = {v:.6g}" for n, v in zip(problem.theta_names, basin.theta, strict=True))
                return unsupported(
                    f"another basin ({where}, Δχ² = {basin.chi2 - result.chi2:.3g}) lies inside the threshold, "
                    "so the region has several components"
                )

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

    def endpoint(direction: float) -> float:
        side = "lower" if direction < 0 else "upper"
        bound = bound_lo if direction < 0 else bound_hi
        inner_d = 0.0
        for m in range(FIRST_EXPONENT, MAX_DOUBLINGS):
            outer_d = step * 2.0**m
            hit_bound = (estimate + direction * outer_d - bound) * direction >= 0
            if hit_bound:
                outer_d = abs(bound - estimate)
            if excess(estimate + direction * outer_d) > 0:
                # The first crossing lies in (inner_d, outer_d]: subdivide to find the first positive sample.
                previous = inner_d
                for mark in np.linspace(inner_d, outer_d, SUBDIVISIONS + 1)[1:]:
                    if excess(estimate + direction * float(mark)) > 0:
                        lo, hi = sorted((estimate + direction * previous, estimate + direction * float(mark)))
                        return float(brentq(excess, lo, hi, xtol=1e-14, rtol=1e-14, maxiter=200))
                    previous = float(mark)
            if hit_bound:
                raise _Unsupported(f"the {side} side reaches the bound {bound:g}")
            inner_d = outer_d
        raise _Unsupported(f"the {side} side never crosses the threshold")

    try:
        lower, upper = endpoint(-1.0), endpoint(1.0)
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
