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
FIT_VERSION: Final = "varpro-trf.6"
#: Relative distance (in units of the bound range) under which two refined optima are one basin.
BASIN_RTOL: Final = 1e-6
#: A geometry parameter is at a bound if TRF reports the bound active, or if it lies within
#: BOUND_ATOL · max(1, |bound|) of it (an absolute scale, independent of the opposite bound).
BOUND_ATOL: Final = 1e-9
#: A refinement converged only if TRF stopped on a tolerance (status > 0) *and* no feasible step
#: really lowers χ² by more than DECREMENT_ATOL + ATTAINABLE_FACTOR · tolerance · χ² (see
#: ``_converged``):
#: - DECREMENT_ATOL is in χ² units, so it is negligible next to the Δχ² = 1 interval scale and
#:   independent of the units of θ;
#: - the second term is the resolution TRF can reach, because its relative ftol ignores
#:   improvements below tolerance·χ²/2 (round 14). Above χ² ≈ 1e13 it approaches the interval
#:   scale, and double precision limits such fits.
DECREMENT_ATOL: Final = 1e-8
ATTAINABLE_FACTOR: Final = 10.0
#: A singular value of the joint Jacobian counts toward the rank only above TRUST_FACTOR times the
#: Frobenius norm of the Jacobian's own error estimate (see ``_rank_split``).
TRUST_FACTOR: Final = 10.0
#: Multiplier of the rounding allowances of derivative columns (``_solve_error``, ``_analytic_error``).
ROUNDING_FACTOR: Final = 8.0
#: Backtracking halvings of the certificate's trial step (see ``_converged``).
TRIAL_HALVINGS: Final = 40
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
    # No joint singular value is hidden by the Jacobian's own error. This expresses agreement of the
    # derivative estimates at the sampling scales used, not guaranteed accuracy: an oscillation
    # finer than the stencils can alias every level alike (round 18, a documented limit).
    derivatives_resolved: bool
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
    unidentified: tuple[dict[str, float], ...]  # a basis of the data's null space of J (rank policy)
    uncertain: tuple[dict[str, float], ...]  # directions the derivatives cannot resolve (not data)
    validity: Validity
    names: tuple[str, ...] = field(default=())
    notes: tuple[str, ...] = field(default=())  # model-specific labels (``Problem.notes``)
    estimand: str = ""  # what θ means under the model (``Problem.estimand``)


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
        jac, error = _full_jacobian(problem, pt, sol.params)
        joint.append(_rank_split(jac, error, problem.k, sol.rank)[0])
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


@dataclass(frozen=True)
class Model:
    """A VarPro sub-problem in its free coordinates x: model(x) = (D_free, F), with prediction
    D_free · t + F, where t is re-solved for every x. F holds any fixed order contribution.

    ``derivative``, when known analytically, returns (∂D_free, ∂F) as (m × N × p_free, m × N)
    arrays for the m coordinates of x. Otherwise the model is differenced (``_derivative``).
    """

    value: Callable[[Array], tuple[Array, Array]]
    derivative: Callable[[Array], tuple[Array, Array]] | None = None

    def __call__(self, x: Array) -> tuple[Array, Array]:
        return self.value(x)


def _whole(problem: Problem) -> Model:
    n = len(problem.y)
    derivative = None
    if problem.design_derivative is not None:

        def derivative(x: Array) -> tuple[Array, Array]:
            return problem.checked_design_derivative(x), np.zeros((problem.k, n))

    return Model(lambda x: (problem.checked_design(x), np.zeros(n)), derivative)


def _varpro_jacobian(
    problem: Problem, model: Model, x: Array, lower: Array, upper: Array
) -> tuple[Array, Array, Array, Array]:
    """(r, J, ∂m, error of ∂m) at x for a VarPro sub-problem: the exact Golub–Pereyra Jacobian.

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
    dm_columns, j_columns, error_columns = [], [], []
    if model.derivative is not None:
        d_design, d_fixed = model.derivative(x)
        for i in range(len(x)):
            wd, wf = problem.whiten(d_design[i]), problem.whiten(d_fixed[i])
            dm = wd @ t + wf
            dm_columns.append(dm)
            # Only the contraction's rounding. This error feeds the certificate's step 4, which can
            # only *accept* an unrealised prediction as derivative noise. Leaving out the error of t
            # (``_solve_error``) makes that step stricter: an ill-conditioned inner solve can yield
            # "not converged", never a false certificate (round 20 corrected an earlier argument).
            error_columns.append(_analytic_error(wd, wf, t, 0.0))
            j_columns.append(dm - q @ (q.T @ dm) - pinv_t @ (problem.whiten(d_design[i]).T @ r))
    for i in range(len(x) if model.derivative is None else 0):

        def stacked(v: float, i: int = i) -> Array:
            shifted = x.copy()
            shifted[i] = v
            d, f = model(shifted)
            return np.concatenate([problem.whiten(d @ t + f), problem.whiten(d).ravel()])

        derivative, error = _derivative(stacked, float(x[i]), float(lower[i]), float(upper[i]))
        dm = derivative[:n]
        da = derivative[n:].reshape(n, p_free)
        error_columns.append(error[:n])
        dm_columns.append(dm)
        j_columns.append(dm - q @ (q.T @ dm) - pinv_t @ (da.T @ r))
    if not dm_columns:
        empty = np.empty((n, 0))
        return r, empty, empty, empty
    return r, np.column_stack(j_columns), np.column_stack(dm_columns), np.column_stack(error_columns)


def _solve_error(singular: Array, t: Array, r: Array) -> float:
    """A bound on each component of the inner solution's own error δt (round 19).

    Least-squares perturbation theory gives about ε·(κ‖t‖ + κ²‖r‖/s_max), with κ the condition
    number of A = W·D on its numerical rank and r the whitened residual. Every derivative column
    W·∂D·t inherits ∂D·δt, however ∂D is computed. A large or ill-conditioned problem amplifies
    it, and counting it as information can invent a joint rank and a finite covariance. One
    example is ∂D columns that cancel exactly on the true t.
    """
    if not (t.size and singular.size and singular[0] > 0):
        return 0.0
    kept = singular[singular > RANK_RTOL * singular[0]]
    kappa = float(kept[0] / kept[-1])
    eps = float(np.finfo(np.float64).eps)
    return eps * (kappa * float(np.linalg.norm(t)) + kappa**2 * float(np.linalg.norm(r)) / float(kept[0]))


def _analytic_error(wd: Array, wf: Array, t: Array, dt: float) -> Array:
    """Componentwise error allowance of an analytic column W·(∂D·t + ∂F) (round 19).

    An analytic derivative has no truncation error, but it is not exact. The contraction rounds by
    about ε·(|W∂D|·|t| + |W∂F|), and t carries its own error δt (``_solve_error``).
    """
    eps = float(np.finfo(np.float64).eps)
    out: Array = ROUNDING_FACTOR * (eps * (np.abs(wd) @ np.abs(t) + np.abs(wf)) + dt * np.abs(wd).sum(axis=1))
    return out


def _converged(
    problem: Problem,
    model: Model,
    residual: Callable[[Array], Array],
    result: Any,
    lower: Array,
    upper: Array,
    tolerance: float,
) -> tuple[bool, str]:
    """TRF stopped on a tolerance, *and* no feasible step really lowers χ² (round 16).

    1. With J the exact Golub–Pereyra Jacobian (``_varpro_jacobian``), solve the bounded linear
       least-squares step δ = argmin ‖J δ + r‖² over the box lower − x ≤ δ ≤ upper − x. Every
       coordinate is included, interior or at a bound, with their cross terms, so coupled moves
       and the bound signs (KKT) are handled together.
    2. If the predicted reduction ‖r‖² − ‖J δ + r‖² is within the tolerance
       DECREMENT_ATOL + ATTAINABLE_FACTOR · tolerance · χ², the point is converged.
    3. Otherwise the actual χ² is evaluated at x + δ/2ᵏ for k = 0 … TRIAL_HALVINGS. A step that
       really lowers χ² by more than the tolerance means "not converged".
    4. If no step does, that alone proves nothing: nonlinearity can defeat one direction while
       another still helps (round 17). The point is certified only if the derivative's own error
       estimate can account for the prediction; otherwise it is not converged.
    """
    from scipy.optimize import lsq_linear

    if result.status <= 0:
        return False, str(result.message)
    x = np.asarray(result.x, dtype=np.float64)
    r, jac, _, dm_error = _varpro_jacobian(problem, model, x, lower, upper)
    chi2 = float(r @ r)
    tol = DECREMENT_ATOL + ATTAINABLE_FACTOR * tolerance * chi2
    if jac.shape[1] == 0:
        return True, str(result.message)
    lb, ub = np.minimum(lower - x, 0.0), np.maximum(upper - x, 0.0)
    if np.any(ub - lb <= 0):  # lsq_linear needs lb < ub
        ub = np.where(ub - lb <= 0, lb + 1e-300, ub)
    step = np.asarray(lsq_linear(jac, -r, bounds=(lb, ub), method="bvls").x, dtype=np.float64)
    linear = jac @ step + r
    predicted = chi2 - float(linear @ linear)
    if predicted <= tol:
        return True, str(result.message)
    for k in range(TRIAL_HALVINGS + 1):
        trial = np.clip(x + step / 2.0**k, lower, upper)
        trial_residual = residual(trial)
        actual = chi2 - float(trial_residual @ trial_residual)
        if actual > tol:
            why = f"a feasible step lowers χ² by {actual:.3g} (predicted {predicted:.3g})"
            return False, f"stopped ({result.message}) at a non-stationary point: {why}"
    # Step 4: the linear reduction is about 2·|δ|ᵀ|g|, and the error in g is about |E|ᵀ|r|.
    gradient_error = np.abs(dm_error).T @ np.abs(r)
    # TRUST_FACTOR covers errors Richardson cannot remove: for an h^p error with p < 2,
    # |R(h/2) − R(h)| underestimates the remaining error.
    explainable = TRUST_FACTOR * 2 * float(np.abs(step) @ gradient_error)
    if explainable >= predicted:
        return True, f"{result.message} (a predicted reduction of {predicted:.3g} was not realised: derivative noise)"
    return (
        False,
        f"stopped ({result.message}): a predicted reduction of {predicted:.3g} could not be realised or explained",
    )


def _refine(problem: Problem, start: Array, settings: Settings) -> Basin:
    model, lo, hi = _whole(problem), problem.lower, problem.upper

    def jac(x: Array) -> Array:
        return _varpro_jacobian(problem, model, x, lo, hi)[1]

    result = _least_squares(problem.profile_residual, start, lo, hi, settings, jac)
    theta = np.asarray(result.x, dtype=np.float64)
    active = tuple(bool(a) for a in result.active_mask)
    converged, message = _converged(problem, model, problem.profile_residual, result, lo, hi, settings.tolerance)
    return Basin(theta, problem.inner(theta).chi2, 0.0, converged, message, active)


def _dedupe(problem: Problem, trials: list[Basin], best: float) -> tuple[Basin, ...]:
    span = problem.upper - problem.lower
    kept: list[Basin] = []
    for trial in sorted(trials, key=lambda b: b.chi2):
        if all(np.max(np.abs(trial.theta - other.theta) / span) > BASIN_RTOL for other in kept):
            kept.append(trial)
    return tuple(Basin(b.theta, b.chi2, b.chi2 - best, b.converged, b.message, b.active) for b in kept)


# --------------------------------------------------------------------------- derivatives
def _stencil(fun: Callable[[float], Array], x: float, step: float, sign: float, centred: bool) -> Array:
    if centred:
        return (fun(x + step) - fun(x - step)) / (2 * step)
    return sign * (-3 * fun(x) + 4 * fun(x + sign * step) - fun(x + 2 * sign * step)) / (2 * step)


def _derivative(fun: Callable[[float], Array], x: float, lo: float, hi: float) -> tuple[Array, Array]:
    """(d fun / dx at x, componentwise error estimate), never evaluating outside [lo, hi].

    The stencil is centred when it fits. Otherwise it is a second-order one-sided stencil toward
    the roomier side, with its step shrunk to fit (rounds 13 and 14). Both stencils have a leading
    h² error. Richardson extrapolation removes it: R(h) = (4·D(h/2) − D(h))/3. The value returned
    is R(h/2), and |R(h/2) − R(h)| estimates its remaining truncation and rounding error. That
    estimate decides which derivatives can be trusted (rounds 16 and 17). The base step is
    ε^(1/3)·max(1, |x|).

    Limit (round 18): the estimate measures agreement between the sampling scales h, h/2 and h/4.
    A model that oscillates faster than those scales can alias all of them alike, giving a wrong
    derivative with a small error estimate. Smooth models, which D3 targets, are not affected.
    """
    h = float(np.cbrt(np.finfo(float).eps)) * max(1.0, abs(x))
    room_lo, room_hi = x - lo, hi - x
    centred = min(h, room_lo, room_hi)
    if centred >= h / 16:
        step, sign, is_centred = centred, 1.0, True
    else:
        room, sign = (room_hi, 1.0) if room_hi >= room_lo else (room_lo, -1.0)
        step, is_centred = min(h, room / 2), False
        if not step > 0:
            raise ValueError("a zero-width range cannot be differentiated")
    d1 = _stencil(fun, x, step, sign, is_centred)
    d2 = _stencil(fun, x, step / 2, sign, is_centred)
    d4 = _stencil(fun, x, step / 4, sign, is_centred)
    r1, r2 = (4 * d2 - d1) / 3, (4 * d4 - d2) / 3
    # The error of the extrapolated value is estimated from two successive Richardson values, not
    # from the raw differences, which overstate it (round 17).
    return r2, np.abs(r2 - r1)


def _jacobian(residual: Callable[[Array], Array], x: Array, lower: Array, upper: Array) -> tuple[Array, Array]:
    """Column-by-column ``_derivative``: (J, componentwise error estimate)."""
    x = np.asarray(x, dtype=np.float64)
    columns, errors = [], []
    for i in range(len(x)):

        def along(v: float, i: int = i) -> Array:
            shifted = x.copy()
            shifted[i] = v
            return residual(shifted)

        value, error = _derivative(along, float(x[i]), float(lower[i]), float(upper[i]))
        columns.append(value)
        errors.append(error)
    if not columns:
        empty = np.empty((len(residual(x)), 0))
        return empty, empty
    return np.column_stack(columns), np.column_stack(errors)


def full_jacobian(problem: Problem, theta: Array, t: Array) -> Array:
    return _full_jacobian(problem, theta, t)[0]


def _full_jacobian(problem: Problem, theta: Array, t: Array) -> tuple[Array, Array]:
    """Whitened J of the joint residual in (θ, t): geometry columns from ``_derivative``, order
    columns exact."""
    theta = np.asarray(theta, dtype=np.float64)
    order = problem.whiten(problem.checked_design(theta))
    n, k, p = len(problem.y), problem.k, problem.p
    singular = np.linalg.svd(order, compute_uv=False) if p else np.empty(0)
    dt = _solve_error(singular, t, order @ t - problem.whiten(problem.y))
    if problem.design_derivative is not None:
        d_design = problem.checked_design_derivative(theta)
        columns = [problem.whiten(d_design[i]) for i in range(k)]
        geometry = np.column_stack([w @ t for w in columns]).reshape(n, k)
        error = np.column_stack([_analytic_error(w, np.zeros(n), t, dt) for w in columns]).reshape(n, k)
        return np.column_stack([geometry, order]), np.column_stack([error, np.zeros_like(order)])
    # Differentiate the whitened prediction W·D(θ)·t only, never the data: the constant −W·y would
    # cost ε·‖r‖ of rounding and can invent a derivative, and with it a joint rank (round 15).
    # W·D is differenced alongside, so that the error of t can be carried through |W∂D| (round 19).
    stacked, stacked_error = _jacobian(
        lambda th: np.concatenate(
            [problem.whiten(problem.checked_design(th) @ t), problem.whiten(problem.checked_design(th)).ravel()]
        ),
        theta,
        problem.lower,
        problem.upper,
    )
    geometry = stacked[:n]
    d_order = np.abs(stacked[n:]).reshape(n, p, k).sum(axis=1)  # Σ_j |W ∂D|_{·j} per geometry column
    error = stacked_error[:n] + ROUNDING_FACTOR * dt * d_order
    return np.column_stack([geometry, order]), np.column_stack([error, np.zeros_like(order)])


def _rank_split(j: Array, error: Array, k: int, floor: int) -> tuple[int, int]:
    """(trusted rank, policy rank) of the joint Jacobian J = [G | A] (k geometry columns G).

    - The *policy rank* counts the singular values of J above RANK_RTOL·s₀, and is at least
      ``floor``, the exact inner rank of the order columns A (round 17).
    - The *trusted rank* is ``floor`` plus the rank that the geometry adds beyond the span of A:
      the singular values of G⊥ = (I − QQᵀ)·G, with Q spanning A. They count only above
      max(RANK_RTOL·s₀, TRUST_FACTOR·‖E‖_F), where E is the geometry columns' own error estimate
      (round 16). So a derivative that is zero up to truncation or rounding never counts as
      information.

      The order columns are exact. Only the geometry's *additional* information is judged against
      its error (round 20): one global cutoff could discard a well-determined but small order
      direction whenever the parameters are badly scaled.
    - The trusted rank never exceeds the policy rank.

    Directions between the two counts are *uncertain*: not resolved by the derivatives. They are
    not a null space of the data.
    """
    s = np.linalg.svd(j, compute_uv=False)
    if not s.size or s[0] <= 0:
        return floor, floor
    policy = max(int(np.count_nonzero(s > RANK_RTOL * float(s[0]))), floor)
    geometry, order = j[:, :k], j[:, k:]
    if order.shape[1]:
        u, so, _ = np.linalg.svd(order, full_matrices=False)
        q = u[:, so > RANK_RTOL * so[0]] if so[0] > 0 else u[:, :0]
        geometry = geometry - q @ (q.T @ geometry)
    threshold = max(RANK_RTOL * float(s[0]), TRUST_FACTOR * float(np.linalg.norm(error[:, :k])))
    added = int(np.count_nonzero(np.linalg.svd(geometry, compute_uv=False) > threshold)) if k else 0
    return min(floor + added, policy), policy


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
    j, j_error = _full_jacobian(problem, best.theta, sol.params)
    # A complete right basis: the reduced SVD gives it when N ≥ p_free; full matrices only when N < p_free.
    _, s, vt = np.linalg.svd(j, full_matrices=j.shape[0] < j.shape[1])
    joint_rank, policy_rank = _rank_split(j, j_error, problem.k, sol.rank)
    names = problem.names

    def named(rows: Array) -> tuple[dict[str, float], ...]:
        return tuple({n: float(v) for n, v in zip(names, row, strict=True)} for row in rows)

    unidentified = named(vt[policy_rank:])
    uncertain = named(vt[joint_rank:policy_rank])

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
        derivatives_resolved=joint_rank == policy_rank,
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
        uncertain=uncertain,
        validity=validity,
        names=names,
        notes=problem.notes(best.theta) if problem.notes is not None else (),
        estimand=problem.estimand,
    )


# --------------------------------------------------------------------------- profiles and slices
def _free_model(problem: Problem, theta_of: Callable[[Array], Array], free: list[int]) -> Model:
    """The sub-problem in the free geometry coordinates, one geometry parameter held fixed."""
    n = len(problem.y)

    def value(f: Array) -> tuple[Array, Array]:
        return problem.checked_design(theta_of(f)), np.zeros(n)

    def derivative(f: Array) -> tuple[Array, Array]:
        return problem.checked_design_derivative(theta_of(f))[free], np.zeros((len(free), n))

    return Model(value, derivative if problem.design_derivative is not None else None)


def _reduced_model(problem: Problem, column: int, value: float) -> Model:
    """The sub-problem with order parameter ``column`` held at ``value``: its column moves to F."""
    others = [c for c in range(problem.p) if c != column]

    def design(theta: Array) -> tuple[Array, Array]:
        d = problem.checked_design(theta)
        return d[:, others], d[:, column] * value

    def derivative(theta: Array) -> tuple[Array, Array]:
        d = problem.checked_design_derivative(theta)
        return d[:, :, others], d[:, :, column] * value

    return Model(design, derivative if problem.design_derivative is not None else None)


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

        free_model = _free_model(problem, theta_of, free)

        lo, hi = problem.lower[free], problem.upper[free]

        def free_jac(f: Array) -> Array:
            return _varpro_jacobian(problem, free_model, f, lo, hi)[1]

        failed = math.inf
        for start in starts:
            res = _least_squares(free_residual, start[free], lo, hi, settings, free_jac)
            chi2 = problem.inner(theta_of(np.asarray(res.x))).chi2
            if _converged(problem, free_model, free_residual, res, lo, hi, settings.tolerance)[0]:
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

    reduced_model = _reduced_model(problem, column, value)

    def reduced_jac(theta: Array) -> Array:
        return _varpro_jacobian(problem, reduced_model, theta, problem.lower, problem.upper)[1]

    failed = math.inf
    for start in starts:
        res = _least_squares(reduced, start, problem.lower, problem.upper, settings, reduced_jac)
        r = reduced(np.asarray(res.x))
        converged = _converged(problem, reduced_model, reduced, res, problem.lower, problem.upper, settings.tolerance)
        if converged[0]:
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
