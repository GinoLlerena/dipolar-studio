"""The fit of a rigid molecule with fixed geometry: no geometry parameter (Phase 2 V1.1).

Design: docs/phase2/v1.0-design.md, D-7 to D-9. With the geometry fixed, the couplings are linear
in the order parameters, D = A·s, so the fit is a weighted linear least-squares problem. There is
nothing to search, profile or scan. ``dipolar_core.fit.fit`` refuses a problem with no geometry
parameter and points here.

**The basis (D-7).** S is expressed in orthonormal coordinates (Frobenius, Σ b_k² = tr S²):

    b = (√(3/2)·Szz, (Sxx − Syy)/√2, √2·Sxy, √2·Sxz, √2·Syz),

a fixed rescaling of ``forward.ORDER_BASIS``. Covariances, functionals and rotations use b. A
frame change S' = Q S Qᵀ acts on b by the orthogonal matrix ``rotation_b(Q)``.

**The symmetry subspace.** A declared point group restricts b to a subspace spanned by the columns
of ``subspace`` (5 × d, orthonormal in b). ``SUBSPACES`` gives them in each group's frame
convention (D-4): one column for D6h/D3h, two for D2h/C2v, three for Cs and five for C1.

**The rank (D-8).** The required rank is d. Singular values only verify it: the rank is verified
when the numerical rank (s_i > ``RANK_RTOL``·s_max) equals d and s_d ≥ ``WEAK_RTOL``·s_max.
Otherwise it is *unverified*: no named component is estimated, no interval and no adequacy are
given, and only the retained directions are reported, as projections.

**Adequacy.** With a verified rank and ν = N − d > 0, the χ² p-value is given; p < ``ADEQUACY_ALPHA``
flags the fit inadequate. Every statistic is conditional on the stated σ (or covariance).

**Admissibility (D-9).** A tensor is physical when λ_min(S) ≥ −1/2. With nullity zero, the fitted
tensor is tested. With null directions, the question is whether *some* tensor of the fitted
family is physical; the answer is decided only by a verified certificate (a feasible tensor, or a
dual matrix), and is "undetermined" otherwise.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Final, Literal

import numpy as np
from numpy.typing import NDArray
from scipy.special import chdtrc

from dipolar_core.inference import RANK_RTOL

Array = NDArray[np.float64]

FIXED_FIT_VERSION: Final = "fixed-linear.1"
#: A retained singular value below WEAK_RTOL·s_max leaves the rank unverified (D-8).
WEAK_RTOL: Final = 1e-6
#: The adequacy policy, as in the app's reporting layer: p < 0.001 is inadequate.
ADEQUACY_ALPHA: Final = 1e-3
#: D-9 tolerances: ε on eigenvalues and conditions, δ for arithmetic.
FEASIBILITY_EPS: Final = 1e-9
FEASIBILITY_DELTA: Final = 1e-12
#: A full covariance is accepted up to this many observations (D-8): about 128 MB at peak,
#: including the caller's N × N matrix.
MAX_COVARIANCE_N: Final = 2000
#: Symmetry tolerance of a covariance, relative to its largest entry; its symmetric part is used.
COVARIANCE_SYMMETRY_RTOL: Final = 1e-12
#: A covariance is positive definite when λ_min ≥ max(1e-12, 64·N·eps)·λ_max (round 71: Cholesky
#: alone can pass an exactly singular matrix by roundoff).
COVARIANCE_PD_RTOL: Final = 1e-12
#: A subspace basis is accepted if max |CᵀC − I| ≤ this, then orthonormalized exactly (round 71).
SUBSPACE_ATOL: Final = 1e-12
#: A strict "feasible" needs λ_min ≥ −1/2 + EIGENVALUE_MARGIN: a bound on the eigenvalue error of a
#: 3 × 3 symmetric matrix of norm ≤ √(3/2) (round 71); between the two it is "within tolerance".
EIGENVALUE_MARGIN: Final = 1e-14
#: Bounded certificate search: Nelder–Mead iterations per start, per null direction (D-11).
SEARCH_ITERATIONS_PER_DIRECTION: Final = 100
#: Two-sided Gaussian quantiles for the reported intervals.
INTERVAL_LEVELS: Final = {"68.3": 1.0, "95": 1.959963984540054}
NAMES: Final = ("Szz", "Sxx-Syy", "Sxy", "Sxz", "Syz")

#: b = ORTHO_SCALE · s5 for s5 in ``forward.ORDER_BASIS``.
ORTHO_SCALE: Final = np.array([math.sqrt(1.5), 1 / math.sqrt(2), math.sqrt(2), math.sqrt(2), math.sqrt(2)])

_R6, _R2 = math.sqrt(6.0), math.sqrt(2.0)
#: S = Σ_k b_k · BASIS[k], an orthonormal basis of traceless symmetric 3 × 3 matrices.
BASIS: Final = np.array(
    [
        np.diag([-1.0, -1.0, 2.0]) / _R6,
        np.diag([1.0, -1.0, 0.0]) / _R2,
        np.array([[0, 1, 0], [1, 0, 0], [0, 0, 0]], dtype=float) / _R2,
        np.array([[0, 0, 1], [0, 0, 0], [1, 0, 0]], dtype=float) / _R2,
        np.array([[0, 0, 0], [0, 0, 1], [0, 1, 0]], dtype=float) / _R2,
    ]
)


def _columns(*indices: int) -> Array:
    out = np.zeros((5, len(indices)))
    for j, i in enumerate(indices):
        out[i, j] = 1.0
    return out


#: The symmetry subspace of b for each supported group, in its frame convention (D-4, D-7).
SUBSPACES: Final = {
    "C1": _columns(0, 1, 2, 3, 4),
    "Cs": _columns(0, 1, 2),
    "C2v": _columns(0, 1),
    "D2h": _columns(0, 1),
    "D3h": _columns(0),
    "D6h": _columns(0),
}


def b_from_s5(s5: Array) -> Array:
    out: Array = np.asarray(s5, dtype=np.float64) * ORTHO_SCALE
    return out


def s5_from_b(b: Array) -> Array:
    out: Array = np.asarray(b, dtype=np.float64) / ORTHO_SCALE
    return out


def matrix_from_b(b: Array) -> Array:
    out: Array = np.einsum("k,kab->ab", np.asarray(b, dtype=np.float64), BASIS)
    return out


def b_from_matrix(s: Array) -> Array:
    out: Array = np.einsum("kab,ab->k", BASIS, np.asarray(s, dtype=np.float64))
    return out


def rotation_b(q: Array) -> Array:
    """The orthogonal 5 × 5 matrix R with b(Q S Qᵀ) = R · b(S), for a rotation Q (passive frames)."""
    q = np.asarray(q, dtype=np.float64)
    rotated = np.einsum("ab,lbc,dc->lad", q, BASIS, q)  # Q M_l Qᵀ
    out: Array = np.einsum("kad,lad->kl", BASIS, rotated)
    return out


def lambda_min(b: Array) -> float:
    return float(np.linalg.eigvalsh(matrix_from_b(b))[0])


AdmissibilityStatus = Literal[
    "admissible", "inadmissible", "feasible", "feasible-within-tolerance", "infeasible", "undetermined"
]
AdequacyStatus = Literal["given", "inadequate", "withheld", "no-dof"]
ComponentStatus = Literal["estimated", "fixed-by-symmetry", "unverified"]


@dataclass(frozen=True, slots=True)
class Admissibility:
    status: AdmissibilityStatus
    lambda_min: float | None  # of the tested tensor, or of the best tensor found in the family
    representative_b: Array | None  # a labelled representative (feasible cases), never "the" tensor
    certificate: str  # how the status was decided
    #: What was tested: "the fitted tensor" (nullity zero), or "the family preserving the retained
    #: projection" (null directions): with an unverified rank, this is a statement about the
    #: retained projection only (round 71).
    family: str = "the fitted tensor"


@dataclass(frozen=True, slots=True)
class Component:
    name: str
    status: ComponentStatus
    coefficients_b: Array  # the functional, in b
    estimate: float | None
    se: float | None
    intervals: dict[str, tuple[float, float]] | None


@dataclass(frozen=True, slots=True)
class FixedResult:
    """Every number is conditional on the stated σ (or covariance) and the fixed geometry."""

    b: Array  # the minimum-norm estimate in b (zero outside the retained directions)
    subspace: Array  # 5 × d
    required_rank: int  # d
    numerical_rank: int
    rank_verified: bool
    rank_reason: str
    singular_ratios: Array  # s_i / s_max of the reduced whitened design
    retained_b: Array  # 5 × r, orthonormal directions in b
    retained_estimates: Array  # the coordinates of b along them
    retained_se: Array  # 1 / s_i
    null_b: Array  # 5 × (d − r), unidentified directions within the subspace
    covariance_b: Array | None  # 5 × 5, only with a verified rank
    components: tuple[Component, ...]
    predictions: Array
    residuals: Array
    chi2: float
    n_obs: int
    nu: int  # N − d
    p_value: float | None
    adequacy: AdequacyStatus
    adequacy_code: str | None
    admissibility: Admissibility
    version: str = FIXED_FIT_VERSION

    @property
    def s5(self) -> Array:
        return s5_from_b(self.b)


def _cholesky_factor(sigma: Array, covariance: object) -> Array | None:
    """The lower Cholesky factor L of a full covariance (Σ = L Lᵀ), or None for a diagonal σ.

    Checked in this order (round 71): the size cap before the covariance is even converted; its
    shape and finiteness; its symmetry, relative to its largest entry (its symmetric part is then
    used); its diagonal against σ; and positive definiteness with a scale-aware margin, since a
    Cholesky factorization alone can succeed on an exactly singular matrix by roundoff. No inverse
    is formed: the factor is applied by triangular solves.
    """
    if covariance is None:
        return None
    n = len(sigma)
    if n > MAX_COVARIANCE_N:
        raise ValueError(f"a full covariance is supported for at most {MAX_COVARIANCE_N} observations, not {n}")
    cov = np.asarray(covariance, dtype=np.float64)
    if cov.shape != (n, n) or not np.all(np.isfinite(cov)):
        raise ValueError("the covariance must be a finite N × N matrix")
    scale = float(np.max(np.abs(cov)))
    asymmetry = max(float(np.max(np.abs(cov[k : k + 256] - cov[:, k : k + 256].T))) for k in range(0, n, 256))
    if asymmetry > COVARIANCE_SYMMETRY_RTOL * scale:
        raise ValueError("the covariance must be symmetric")
    sym = cov + cov.T
    sym *= 0.5
    if not np.allclose(np.sqrt(np.diag(sym)), sigma, rtol=1e-12, atol=0.0):
        raise ValueError("sigma must equal the square root of the covariance diagonal")
    eigenvalues = np.linalg.eigvalsh(sym)
    margin = max(COVARIANCE_PD_RTOL, 64 * n * float(np.finfo(np.float64).eps))
    if not eigenvalues[-1] > 0 or eigenvalues[0] < margin * eigenvalues[-1]:
        raise ValueError("the covariance must be positive definite (its smallest eigenvalue is not resolved)")
    try:
        out: Array = np.linalg.cholesky(sym)
    except np.linalg.LinAlgError:
        raise ValueError("the covariance must be positive definite") from None
    return out


def _check_subspace(subspace: Array) -> Array:
    """An orthonormal copy of the subspace basis: accepted only if CᵀC is the identity within an
    absolute SUBSPACE_ATOL, then orthonormalized exactly with the same span (round 71)."""
    c = np.array(subspace, dtype=np.float64)
    if c.ndim != 2 or c.shape[0] != 5 or not 1 <= c.shape[1] <= 5 or not np.all(np.isfinite(c)):
        raise ValueError("the subspace must be a finite 5 × d matrix with 1 ≤ d ≤ 5")
    if float(np.max(np.abs(c.T @ c - np.eye(c.shape[1])))) > SUBSPACE_ATOL:
        raise ValueError("the subspace's columns must be orthonormal in b")
    q, r = np.linalg.qr(c)
    out: Array = q * np.where(np.diag(r) < 0, -1.0, 1.0)
    return out


def _norm2(v: Array) -> float:
    """‖v‖₂ without overflow or underflow of the squares (round 71)."""
    m = float(np.max(np.abs(v))) if v.size else 0.0
    if m == 0.0:
        return 0.0
    return m * math.sqrt(float(np.sum((v / m) ** 2)))


def _finite(name: str, *values: object) -> None:
    for value in values:
        if not np.all(np.isfinite(np.asarray(value, dtype=np.float64))):
            raise ValueError(f"the problem is not representable in floating point ({name})")


def fit_fixed(
    design_s5: Array,
    y: Array,
    sigma: Array,
    subspace: Array | None = None,
    covariance: Array | None = None,
) -> FixedResult:
    """Fit the order parameters of a fixed geometry: D ≈ design_s5 · s5, with s restricted to the
    symmetry subspace (C1 when ``subspace`` is None)."""
    a5 = np.asarray(design_s5, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    sigma = np.asarray(sigma, dtype=np.float64)
    if y.ndim != 1:
        raise ValueError("y must be a vector")
    n = len(y)
    if a5.ndim != 2 or a5.shape != (n, 5) or sigma.shape != (n,) or n < 1:
        raise ValueError("the design must be N × 5, with y and sigma of length N ≥ 1")
    if not (np.all(np.isfinite(a5)) and np.all(np.isfinite(y)) and np.all(np.isfinite(sigma))):
        raise ValueError("non-finite input")
    if np.any(sigma <= 0):
        raise ValueError("every sigma must be positive")
    c = _check_subspace(SUBSPACES["C1"] if subspace is None else subspace)
    d = c.shape[1]
    chol = _cholesky_factor(sigma, covariance)

    # Whiten first, then change basis: a common scale cancels before anything can overflow.
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        if chol is None:
            wa5, wy = a5 / sigma[:, None], y / sigma
        else:
            from scipy.linalg import solve_triangular

            wa5 = solve_triangular(chol, a5, lower=True, check_finite=False)
            wy = solve_triangular(chol, y, lower=True, check_finite=False)
        wa = (wa5 / ORTHO_SCALE) @ c  # N × d, in reduced b coordinates
    _finite("the whitened design and data", wa, wy)
    # One SVD gives U, s and a complete right basis (d × d), so signs and ties stay paired.
    u, s, vt = np.linalg.svd(wa, full_matrices=n < d)
    v_full = vt.T
    s_max = float(s[0]) if s.size else 0.0
    ratios = s / s_max if s_max > 0 else np.zeros_like(s)
    keep = ratios > RANK_RTOL if s_max > 0 else np.zeros_like(s, dtype=bool)
    r = int(np.count_nonzero(keep))

    if r == 0:
        reason = "nothing is estimable (rank zero)"
    elif r < d:
        reason = f"numerical rank {r} below the required rank {d}"
    elif ratios[d - 1] < WEAK_RTOL:
        reason = f"the weakest direction has s/s_max = {ratios[d - 1]:.3g} < {WEAK_RTOL:g}"
    else:
        reason = "verified: numerical rank equals the required rank, with margin"
    verified = r == d and r > 0 and ratios[d - 1] >= WEAK_RTOL

    with np.errstate(over="ignore", invalid="ignore"):
        coords = (u[:, :r].T @ wy) / s[:r]
        v_r = v_full[:, :r]
        t = v_r @ coords
        b = c @ t
        retained_b = c @ v_r
        null_b = c @ v_full[:, r:]
        predictions = a5 @ s5_from_b(b)
        residuals = y - predictions
        wres = wy - wa @ t
        chi2 = _norm2(wres) ** 2
        # The covariance from the singular reciprocals (round 71: squaring s first can overflow).
        scaled = retained_b / s[:r]
        covariance_b = scaled @ scaled.T if verified else None
    nu = n - d
    _finite("the estimate, predictions and residuals", b, predictions, residuals, chi2)

    components = tuple(_component(name, j, c, b, scaled if verified else None) for j, name in enumerate(NAMES))

    p_value: float | None = None
    adequacy: AdequacyStatus
    code: str | None = None
    if not verified:
        adequacy, code = "withheld", "ADEQUACY_RANK_UNVERIFIED"
    elif nu <= 0:
        adequacy, code = "no-dof", "NO_DOF"
    else:
        p_value = float(chdtrc(nu, chi2))
        adequacy = "inadequate" if p_value < ADEQUACY_ALPHA else "given"

    return FixedResult(
        b=b,
        subspace=c,
        required_rank=d,
        numerical_rank=r,
        rank_verified=verified,
        rank_reason=reason,
        singular_ratios=ratios,
        retained_b=retained_b,
        retained_estimates=coords,
        retained_se=1.0 / s[:r],
        null_b=null_b,
        covariance_b=covariance_b,
        components=components,
        predictions=predictions,
        residuals=residuals,
        chi2=chi2,
        n_obs=n,
        nu=nu,
        p_value=p_value,
        adequacy=adequacy,
        adequacy_code=code,
        admissibility=admissibility(b, null_b),
    )


def _component(name: str, j: int, c: Array, b: Array, scaled: Array | None) -> Component:
    """The named component s5_j = b_j / ORTHO_SCALE_j, as the functional e_j / scale_j in b.

    A component whose functional lies outside the declared subspace (projection ≤ 1e-12 of its
    norm) is fixed at 0 by the symmetry. For the built-in subspaces this is exact; a custom
    subspace with a tiny but nonzero component is treated the same way (round 71, documented).
    ``scaled`` holds the retained directions divided by their singular values.
    """
    coefficients = np.zeros(5)
    coefficients[j] = 1.0 / ORTHO_SCALE[j]
    inside = c @ (c.T @ coefficients)
    if np.linalg.norm(inside) <= 1e-12 * np.linalg.norm(coefficients):
        return Component(name, "fixed-by-symmetry", coefficients, 0.0, None, None)
    if scaled is None:
        return Component(name, "unverified", coefficients, None, None, None)
    estimate = float(coefficients @ b)
    se = _norm2(coefficients @ scaled)
    intervals = {level: (estimate - z * se, estimate + z * se) for level, z in INTERVAL_LEVELS.items()}
    return Component(name, "estimated", coefficients, estimate, se, intervals)


def _strictly_physical(lam: float) -> bool:
    return lam - EIGENVALUE_MARGIN >= -0.5


def admissibility(b0: Array, null_b: Array) -> Admissibility:
    """Is some tensor of the family b0 + span(null_b) physical (λ_min ≥ −1/2)? (D-9)

    ``b0`` must be the minimum-norm point of the family (orthogonal to ``null_b``), and the null
    directions orthonormal. Physical tensors have ‖S‖_F ≤ √(3/2), so only the ball ‖c‖ ≤ √(3/2) of
    the family can hold one. A strict "feasible" needs a margin over the eigenvalue error; within
    ε of the boundary the answer is "feasible-within-tolerance"; "infeasible" needs a verified dual
    certificate; anything else is "undetermined". The search is bounded and stops at the first
    certificate.
    """
    m = null_b.shape[1]
    if m == 0:
        lam = lambda_min(b0)
        ok = lam >= -0.5 - FEASIBILITY_EPS
        return Admissibility("admissible" if ok else "inadmissible", lam, None, "direct: the fitted tensor")
    family_label = "the family preserving the retained projection"
    lam0 = lambda_min(b0)
    if not np.any(b0):
        return Admissibility("feasible", 0.0, np.zeros(5), "S = 0 belongs to the family", family_label)
    if _strictly_physical(lam0):
        return Admissibility("feasible", lam0, b0.copy(), "the fitted point itself is physical", family_label)

    radius = math.sqrt(1.5)

    def family(coeffs: Array) -> Array:
        out: Array = b0 + null_b @ coeffs
        return out

    best_c, best_lam = np.zeros(m), lam0
    for c_start, lam in _search_lambda_min(family, m, radius):
        if lam > best_lam:
            best_c, best_lam = c_start, lam
        if _strictly_physical(best_lam):
            return Admissibility("feasible", best_lam, family(best_c), "a verified feasible tensor", family_label)
        z = _dual_certificate(family(best_c), null_b)
        if z is not None and certifies_infeasible(z, b0, null_b):
            value = float(np.sum(z * matrix_from_b(b0)))
            return Admissibility(
                "infeasible", best_lam, None, f"a verified dual certificate: <Z, S0> = {value:.6g}", family_label
            )
    if best_lam >= -0.5 - FEASIBILITY_EPS:
        return Admissibility(
            "feasible-within-tolerance", best_lam, family(best_c), "a tensor within ε of the boundary", family_label
        )
    return Admissibility("undetermined", best_lam, None, "no certificate could be verified", family_label)


def certifies_infeasible(z: Array, b0: Array, null_b: Array) -> bool:
    """Does Z prove that no tensor of b0 + span(null_b) is physical? (D-9, round 67)

    Z must satisfy, within ε: Z ⪰ 0, tr Z = 1 and ⟨Z, N_k⟩ = 0. Then for any physical completion
    (‖c‖ ≤ √(3/2)), λ_min ≥ −1/2 would force ⟨Z, S0⟩ ≥ −1/2 − (2 + √(3m/2))ε; a value below that,
    by the arithmetic margin δ, is a proof of infeasibility.
    """
    nulls = [matrix_from_b(null_b[:, k]) for k in range(null_b.shape[1])]
    if not (
        float(np.linalg.eigvalsh(z)[0]) >= -FEASIBILITY_EPS
        and abs(float(np.trace(z)) - 1.0) <= FEASIBILITY_EPS
        and all(abs(float(np.sum(z * nk))) <= FEASIBILITY_EPS for nk in nulls)
    ):
        return False
    m = len(nulls)
    bound = -0.5 - (2.0 + math.sqrt(1.5 * m)) * FEASIBILITY_EPS - FEASIBILITY_DELTA
    return float(np.sum(z * matrix_from_b(b0))) < bound


def _search_lambda_min(family: Callable[[Array], Array], m: int, radius: float) -> Iterator[tuple[Array, float]]:
    """Yield the best point of each bounded Nelder–Mead run maximizing the concave λ_min over the
    ball ‖c‖ ≤ radius: first from the fitted point, then from ±radius/2 along each null direction."""
    from scipy.optimize import minimize

    def clip(c: Array) -> Array:
        norm = float(np.linalg.norm(c))
        return c * (radius / norm) if norm > radius else c

    def objective(c: Array) -> float:
        return -lambda_min(family(clip(c)))

    starts = [np.zeros(m), *(radius / 2 * row for row in np.eye(m)), *(-radius / 2 * row for row in np.eye(m))]
    options = {"xatol": 1e-12, "fatol": 1e-14, "maxiter": SEARCH_ITERATIONS_PER_DIRECTION * m}
    for start in starts:
        res = minimize(objective, start, method="Nelder-Mead", options=options)
        best = clip(np.asarray(res.x, dtype=np.float64))
        yield best, lambda_min(family(best))


def _dual_certificate(b_star: Array, null_b: Array) -> Array | None:
    """A dual matrix Z with Z ⪰ 0, tr Z = 1 and ⟨Z, N_k⟩ = 0, verified within ε; None if none is found.

    Z starts as the projector onto the lowest eigenvectors at the best tensor found. It is then
    projected exactly onto the constraints (the N_k are orthonormal and traceless), and mixed with
    I/3, which satisfies every constraint, just enough to make it positive semidefinite.
    """
    values, vectors = np.linalg.eigh(matrix_from_b(b_star))
    lowest = vectors[:, values <= values[0] + 1e-6]
    z = lowest @ lowest.T / lowest.shape[1]
    nulls = [matrix_from_b(null_b[:, k]) for k in range(null_b.shape[1])]
    for nk in nulls:
        z = z - float(np.sum(z * nk)) * nk
    z = z + (1.0 - float(np.trace(z))) * np.eye(3) / 3.0
    low = float(np.linalg.eigvalsh(z)[0])
    if low < 0:
        t = -low / (1.0 / 3.0 - low)
        z = (1.0 - t) * z + t * np.eye(3) / 3.0
    if (
        np.linalg.eigvalsh(z)[0] >= -FEASIBILITY_EPS
        and abs(float(np.trace(z)) - 1.0) <= FEASIBILITY_EPS
        and all(abs(float(np.sum(z * nk))) <= FEASIBILITY_EPS for nk in nulls)
    ):
        out: Array = z
        return out
    return None
