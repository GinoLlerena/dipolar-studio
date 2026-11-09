"""The D3 inference stack (plan §3 D3, ADR-0003): separable least squares with honest validity.

A model predicts y ≈ D(θ)·t:
- θ are bounded nonlinear geometry parameters (for example the torsion φ);
- t are the free order parameters;
- D(θ) = A(θ)·C is the design matrix.

With a known, fixed σ (never rescaled), the fit is:

1. **Starts.** A profile scan: on a grid for one geometry parameter, with Sobol points for
   several. The profile objective re-solves t by whitened SVD at every θ (variable projection).
2. **Refinement.** Every start is refined by bounded TRF (`scipy.optimize.least_squares`) on the
   *residual vector* of the profile, never on the scalar χ² (M0 spike 1).
3. **Basins.** Distinct refined optima are reported with their Δχ² from the best one. Competing
   basins are never hidden.
4. **Uncertainty.** Covariance comes from the **full** whitened Jacobian in joint coordinates
   (θ, t). Its rank is the joint rank, reported separately from the inner rank. Directions the
   data do not determine are named and are never given finite error bars.
5. **Intervals.** Profile intervals (the other parameters re-minimized) and slice intervals (the
   other parameters held fixed) are distinct functions with labelled results. Δχ² thresholds are
   raw: 1.00, 3.84, or 2.30 for a two-parameter region. An interval that runs into a bound, or one
   at an irregular optimum, is reported as **not supported** rather than invented.
6. **Validity.** The flags are independent of each other: inner rank and condition number, joint
   rank, convergence, admissibility, bounds and interval support.

Degrees of freedom: ν = N − p_free applies only to a regular, identifiable interior optimum.
Otherwise ν and the p-value are None.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Final, Literal

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import brentq, least_squares
from scipy.special import chdtrc

from dipolar_core.inference import RANK_RTOL, is_admissible, solve_inner
from dipolar_core.problem import DesignFunction as DesignFunction
from dipolar_core.problem import Problem as Problem

Array = NDArray[np.float64]

#: Version of this stack's numerical choices (enters the numerical context when an operation uses it).
FIT_VERSION: Final = "varpro-trf.1"
#: Relative distance (in units of the bound range) under which two refined optima are one basin.
BASIN_RTOL: Final = 1e-6
#: Relative distance to a bound under which a parameter counts as "at the bound".
BOUND_RTOL: Final = 1e-9
#: Raw Δχ² thresholds and their labels (regular-model approximations, D3.4).
DELTA_CHI2_LABELS: Final = {
    1.00: "68.3% one-parameter",
    3.84: "95% one-parameter",
    2.30: "68.3% joint two-parameter",
}


@dataclass(frozen=True)
class Settings:
    """Search and refinement settings (all written policies, D3).

    ``grid``: for one geometry parameter, the scan points (default: 0.5-wide steps over the bounds,
    at least 181 points). ``n_sobol`` and ``n_starts``: for several parameters, the number of
    Sobol points (a power of two) and how many of the best ones are refined. ``seed`` makes the
    Sobol scramble reproducible.
    """

    grid: Array | None = None
    n_sobol: int = 256
    n_starts: int = 8
    seed: int = 19980101
    tolerance: float = 1e-15
    max_nfev: int = 2000


# --------------------------------------------------------------------------- results
@dataclass(frozen=True)
class Scan:
    """The profile objective at the start points; ``minima`` index the grid's local minima."""

    points: Array  # n × k
    chi2: Array  # n
    minima: tuple[int, ...]


@dataclass(frozen=True)
class Basin:
    theta: Array
    chi2: float
    delta_chi2: float  # χ² − χ²_best
    converged: bool
    message: str


@dataclass(frozen=True)
class Covariance:
    """Covariance in joint coordinates (θ then t), known σ, not rescaled by χ²/ν."""

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
    at_bound: tuple[str, ...]  # geometry parameters sitting on a bound
    regular: bool  # interior, converged, full joint rank: the conditions for ν and Δχ² intervals


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
    basins: tuple[Basin, ...]  # best first
    covariance: Covariance | None  # None unless the joint rank is full
    unidentified: tuple[dict[str, float], ...]  # unit null-space directions of J, by parameter name
    validity: Validity
    names: tuple[str, ...] = field(default=())


@dataclass(frozen=True)
class Interval:
    """A Δχ² interval for one parameter. ``kind`` is "profile" (others re-minimized) or "slice"
    (others fixed at the optimum); ``lower``/``upper`` are None where the interval is not
    supported, with the reason in ``note``."""

    parameter: str
    kind: Literal["profile", "slice"]
    delta_chi2: float
    label: str
    estimate: float
    lower: float | None
    upper: float | None
    supported: bool
    note: str


# --------------------------------------------------------------------------- search and refinement
def _local_minima(values: Array) -> tuple[int, ...]:
    out = []
    for i in range(len(values)):
        left = values[i - 1] if i > 0 else math.inf
        right = values[i + 1] if i + 1 < len(values) else math.inf
        if values[i] <= left and values[i] <= right:
            out.append(i)
    return tuple(out)


def scan(problem: Problem, settings: Settings) -> Scan:
    if problem.k == 1:
        if settings.grid is not None:
            grid = np.asarray(settings.grid, dtype=np.float64)
        else:
            lo, hi = float(problem.lower[0]), float(problem.upper[0])
            grid = np.linspace(lo, hi, max(181, round((hi - lo) / 0.5) + 1))
        if grid.ndim != 1 or np.any(grid < problem.lower[0]) or np.any(grid > problem.upper[0]):
            raise ValueError("the grid must be one-dimensional and inside the bounds")
        points = grid[:, None]
        values = np.array([problem.inner(pt).chi2 for pt in points])
        return Scan(points, values, _local_minima(values))
    from scipy.stats import qmc  # only multi-parameter searches pay for scipy.stats

    sobol = qmc.Sobol(d=problem.k, scramble=True, seed=settings.seed)
    points = qmc.scale(sobol.random(settings.n_sobol), problem.lower, problem.upper)
    values = np.array([problem.inner(pt).chi2 for pt in points])
    best = tuple(int(i) for i in np.argsort(values)[: settings.n_starts])
    return Scan(points, values, best)


def _refine(problem: Problem, start: Array, settings: Settings) -> tuple[Array, float, bool, str]:
    result = least_squares(
        problem.profile_residual,
        np.clip(start, problem.lower, problem.upper),
        bounds=(problem.lower, problem.upper),
        method="trf",
        x_scale="jac",
        xtol=settings.tolerance,
        ftol=settings.tolerance,
        gtol=settings.tolerance,
        max_nfev=settings.max_nfev,
    )
    theta = np.asarray(result.x, dtype=np.float64)
    return theta, problem.inner(theta).chi2, bool(result.status > 0), str(result.message)


def _basins(problem: Problem, refined: list[tuple[Array, float, bool, str]]) -> tuple[Basin, ...]:
    span = problem.upper - problem.lower
    kept: list[tuple[Array, float, bool, str]] = []
    for item in sorted(refined, key=lambda r: r[1]):
        if all(np.max(np.abs(item[0] - other[0]) / span) > BASIN_RTOL for other in kept):
            kept.append(item)
    best = kept[0][1]
    return tuple(Basin(theta, chi2, chi2 - best, converged, message) for theta, chi2, converged, message in kept)


# --------------------------------------------------------------------------- the full Jacobian
def full_jacobian(problem: Problem, theta: Array, t: Array) -> Array:
    """Whitened J of the joint residual in (θ, t). Order columns are exact; geometry columns use
    central differences (one-sided at a bound) with step ε^(1/3)·max(1, |θᵢ|)."""
    n = len(problem.y)
    j = np.empty((n, problem.k + problem.p))
    for i in range(problem.k):
        h = np.cbrt(np.finfo(float).eps) * max(1.0, abs(float(theta[i])))
        up, down = theta.copy(), theta.copy()
        up[i] = min(theta[i] + h, problem.upper[i])
        down[i] = max(theta[i] - h, problem.lower[i])
        j[:, i] = (problem.joint_residual(up, t) - problem.joint_residual(down, t)) / (up[i] - down[i])
    j[:, problem.k :] = problem.checked_design(theta) / problem.sigma[:, None]
    return j


def _covariance(problem: Problem, j: Array) -> tuple[int, Covariance | None, tuple[dict[str, float], ...]]:
    _, s, vt = np.linalg.svd(j, full_matrices=False)
    rank = int(np.count_nonzero(s > RANK_RTOL * s[0])) if s.size and s[0] > 0 else 0
    names = problem.names
    if rank < j.shape[1]:
        null = vt[rank:]
        directions = tuple({n: float(v) for n, v in zip(names, row, strict=True) if abs(v) > 1e-12} for row in null)
        return rank, None, directions
    matrix = (vt.T / s**2) @ vt  # (JᵀJ)⁻¹ from the SVD, never by inverting JᵀJ
    stderr = np.sqrt(np.diag(matrix))
    return rank, Covariance(names, matrix, stderr, matrix / np.outer(stderr, stderr)), ()


# --------------------------------------------------------------------------- the fit
def fit(problem: Problem, settings: Settings | None = None) -> FitResult:
    settings = settings or Settings()
    sc = scan(problem, settings)
    refined = [_refine(problem, sc.points[i], settings) for i in sc.minima]
    basins = _basins(problem, refined)
    best = basins[0]
    sol = problem.inner(best.theta)
    j = full_jacobian(problem, best.theta, sol.params)
    joint_rank, covariance, unidentified = _covariance(problem, j)
    span = problem.upper - problem.lower
    bounds = zip(problem.theta_names, best.theta, problem.lower, problem.upper, span, strict=True)
    at_bound = tuple(name for name, value, lo, hi, w in bounds if min(value - lo, hi - value) <= BOUND_RTOL * w)
    p_free = problem.k + problem.p
    regular = best.converged and not at_bound and joint_rank == p_free and sol.rank == problem.p
    nu = len(problem.y) - p_free if regular else None
    p_value = float(chdtrc(nu, sol.chi2)) if nu is not None and nu > 0 else None  # χ² survival function
    admissible = None if problem.s5_map is None else is_admissible(problem.s5_map @ sol.params)
    validity = Validity(
        inner_rank=sol.rank,
        inner_parameters=problem.p,
        inner_condition_number=sol.condition if math.isfinite(sol.condition) else None,
        joint_rank=joint_rank,
        joint_parameters=p_free,
        converged=best.converged,
        physically_admissible=admissible,
        at_bound=at_bound,
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
        covariance=covariance,
        unidentified=unidentified,
        validity=validity,
        names=problem.names,
    )


# --------------------------------------------------------------------------- profiles and slices
def _profile_chi2(problem: Problem, result: FitResult, index: int, value: float, settings: Settings) -> float:
    """χ² with parameter ``index`` held at ``value`` and every other parameter re-minimized."""
    k = problem.k
    if index < k:
        free = [i for i in range(k) if i != index]

        def theta_of(free_values: Array) -> Array:
            theta = result.theta.copy()
            theta[index] = value
            theta[free] = free_values
            return theta

        if not free:
            return problem.inner(theta_of(np.empty(0))).chi2
        start = result.theta[free]
        res = least_squares(
            lambda f: problem.profile_residual(theta_of(f)),
            start,
            bounds=(problem.lower[free], problem.upper[free]),
            method="trf",
            x_scale="jac",
            xtol=settings.tolerance,
            ftol=settings.tolerance,
            gtol=settings.tolerance,
            max_nfev=settings.max_nfev,
        )
        return problem.inner(theta_of(np.asarray(res.x))).chi2

    column = index - k
    others = [c for c in range(problem.p) if c != column]

    def reduced(theta: Array) -> Array:
        d = problem.checked_design(theta)
        target = problem.y - d[:, column] * value
        if not others:
            fixed: Array = (-target) / problem.sigma
            return fixed
        sol = solve_inner(d[:, others], target, problem.sigma)
        residual: Array = -sol.residuals / problem.sigma
        return residual

    res = least_squares(
        reduced,
        result.theta,
        bounds=(problem.lower, problem.upper),
        method="trf",
        x_scale="jac",
        xtol=settings.tolerance,
        ftol=settings.tolerance,
        gtol=settings.tolerance,
        max_nfev=settings.max_nfev,
    )
    r = reduced(np.asarray(res.x))
    return float(r @ r)


def _slice_chi2(problem: Problem, result: FitResult, index: int, value: float) -> float:
    theta, t = result.theta.copy(), result.order.copy()
    if index < problem.k:
        theta[index] = value
    else:
        t[index - problem.k] = value
    r = problem.joint_residual(theta, t)
    return float(r @ r)


def _interval(
    problem: Problem,
    result: FitResult,
    name: str,
    kind: Literal["profile", "slice"],
    delta_chi2: float,
    settings: Settings | None,
) -> Interval:
    settings = settings or Settings()
    index = problem.names.index(name)
    estimate = float(result.theta[index] if index < problem.k else result.order[index - problem.k])
    label = DELTA_CHI2_LABELS.get(delta_chi2, f"Δχ² = {delta_chi2:g} (no standard label)")

    def unsupported(note: str) -> Interval:
        return Interval(name, kind, delta_chi2, label, estimate, None, None, False, note)

    if not result.validity.regular:
        return unsupported("interval not supported: the optimum is not regular (bound, rank or convergence)")

    def excess(value: float) -> float:
        if kind == "profile":
            return _profile_chi2(problem, result, index, value, settings) - result.chi2 - delta_chi2
        return _slice_chi2(problem, result, index, value) - result.chi2 - delta_chi2

    if result.covariance is not None:
        step = float(result.covariance.stderr[index]) * math.sqrt(delta_chi2)
    else:
        step = 1e-3 * max(1.0, abs(estimate))
    ends: list[float | None] = []
    for direction in (-1.0, 1.0):
        inner, outer, end = estimate, estimate + direction * step, None
        for _ in range(60):
            if index < problem.k:
                bound = problem.lower[index] if direction < 0 else problem.upper[index]
                if (outer - bound) * direction >= 0:
                    outer = float(bound)
                    if excess(outer) <= 0:
                        break  # the region reaches the bound: no endpoint on this side
            if excess(outer) > 0:
                lo, hi = sorted((inner, outer))
                end = float(brentq(excess, lo, hi, xtol=1e-14, rtol=1e-14, maxiter=200))
                break
            inner, outer = outer, estimate + 2 * (outer - estimate)
        ends.append(end)
    lower, upper = ends
    if lower is None or upper is None:
        side = "lower" if lower is None else "upper"
        return Interval(
            name, kind, delta_chi2, label, estimate, lower, upper, False,
            f"interval not supported: the {side} side reaches a bound or never crosses the threshold",
        )  # fmt: skip
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
