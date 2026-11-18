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
#: A full covariance is accepted up to this many observations (D-8): about 128 MB at peak.
MAX_COVARIANCE_N: Final = 2000
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


def _whitener(sigma: Array, covariance: Array | None) -> Array | None:
    if covariance is None:
        return None
    n = len(sigma)
    if n > MAX_COVARIANCE_N:
        raise ValueError(f"a full covariance is supported for at most {MAX_COVARIANCE_N} observations, not {n}")
    cov = np.asarray(covariance, dtype=np.float64)
    if cov.shape != (n, n) or not np.all(np.isfinite(cov)) or not np.allclose(cov, cov.T, rtol=1e-12, atol=0.0):
        raise ValueError("the covariance must be a finite, symmetric N × N matrix")
    if not np.allclose(np.sqrt(np.diag(cov)), sigma, rtol=1e-12, atol=0.0):
        raise ValueError("sigma must equal the square root of the covariance diagonal")
    try:
        chol = np.linalg.cholesky(cov)
    except np.linalg.LinAlgError:
        raise ValueError("the covariance must be positive definite") from None
    out: Array = np.linalg.solve(chol, np.eye(n))
    return out


def _check_subspace(subspace: Array) -> Array:
    c = np.asarray(subspace, dtype=np.float64)
    if c.ndim != 2 or c.shape[0] != 5 or not 1 <= c.shape[1] <= 5:
        raise ValueError("the subspace must be a 5 × d matrix with 1 ≤ d ≤ 5")
    if not np.allclose(c.T @ c, np.eye(c.shape[1]), atol=1e-12):
        raise ValueError("the subspace's columns must be orthonormal in b")
    return c


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
    n = len(y)
    if a5.ndim != 2 or a5.shape != (n, 5) or sigma.shape != (n,) or n < 1:
        raise ValueError("the design must be N × 5, with y and sigma of length N ≥ 1")
    if not (np.all(np.isfinite(a5)) and np.all(np.isfinite(y)) and np.all(np.isfinite(sigma))):
        raise ValueError("non-finite input")
    if np.any(sigma <= 0):
        raise ValueError("every sigma must be positive")
    c = _check_subspace(SUBSPACES["C1"] if subspace is None else subspace)
    d = c.shape[1]
    whiten = _whitener(sigma, covariance)

    a_red = (a5 / ORTHO_SCALE) @ c  # N × d, in reduced b coordinates
    wa = whiten @ a_red if whiten is not None else a_red / sigma[:, None]
    wy = whiten @ y if whiten is not None else y / sigma
    u, s, vt = np.linalg.svd(wa, full_matrices=False)
    v_full = np.linalg.svd(wa, full_matrices=True)[2].T if n < d else vt.T  # d × d right basis
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

    coords = (u[:, :r].T @ wy) / s[:r]
    v_r = v_full[:, :r]
    t = v_r @ coords
    b = c @ t
    retained_b = c @ v_r
    null_b = c @ v_full[:, r:]
    predictions = a5 @ s5_from_b(b)
    residuals = y - predictions
    wres = wy - wa @ t
    chi2 = float(wres @ wres)
    nu = n - d

    covariance_b = None
    if verified:
        covariance_b = retained_b @ np.diag(1.0 / s[:r] ** 2) @ retained_b.T

    components = tuple(_component(name, j, c, b, covariance_b) for j, name in enumerate(NAMES))

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


def _component(name: str, j: int, c: Array, b: Array, covariance_b: Array | None) -> Component:
    """The named component s5_j = b_j / ORTHO_SCALE_j, as the functional e_j / scale_j in b."""
    coefficients = np.zeros(5)
    coefficients[j] = 1.0 / ORTHO_SCALE[j]
    inside = c @ (c.T @ coefficients)
    if np.linalg.norm(inside) <= 1e-12 * np.linalg.norm(coefficients):
        return Component(name, "fixed-by-symmetry", coefficients, 0.0, None, None)
    if covariance_b is None:
        return Component(name, "unverified", coefficients, None, None, None)
    estimate = float(coefficients @ b)
    se = math.sqrt(max(float(coefficients @ covariance_b @ coefficients), 0.0))
    intervals = {level: (estimate - z * se, estimate + z * se) for level, z in INTERVAL_LEVELS.items()}
    return Component(name, "estimated", coefficients, estimate, se, intervals)


def admissibility(b0: Array, null_b: Array) -> Admissibility:
    """Is some tensor of the family b0 + span(null_b) physical (λ_min ≥ −1/2)? (D-9)

    ``b0`` must be the minimum-norm point of the family (orthogonal to ``null_b``), and the null
    directions orthonormal. Physical tensors have ‖S‖_F ≤ √(3/2), so only the ball ‖c‖ ≤ √(3/2) of
    the family can hold one.
    """
    m = null_b.shape[1]
    if m == 0:
        lam = lambda_min(b0)
        ok = lam >= -0.5 - FEASIBILITY_EPS
        return Admissibility("admissible" if ok else "inadmissible", lam, None, "direct: the fitted tensor")
    if not np.any(b0):  # rank zero: the family is the whole subspace, which holds S = 0
        return Admissibility("feasible", 0.0, np.zeros(5), "rank zero: S = 0 is in the family")

    radius = math.sqrt(1.5)

    def family(coeffs: Array) -> Array:
        out: Array = b0 + null_b @ coeffs
        return out

    best_c, best_lam = _maximize_lambda_min(family, m, radius)
    if best_lam >= -0.5:
        return Admissibility("feasible", best_lam, family(best_c), "a verified feasible tensor")
    if best_lam >= -0.5 - FEASIBILITY_EPS:
        return Admissibility("feasible-within-tolerance", best_lam, family(best_c), "a tensor within ε of the boundary")
    z = _dual_certificate(family(best_c), null_b)
    if z is not None:
        bound = -0.5 - (2.0 + math.sqrt(1.5 * m)) * FEASIBILITY_EPS - FEASIBILITY_DELTA
        value = float(np.sum(z * matrix_from_b(b0)))
        if value < bound:
            return Admissibility("infeasible", best_lam, None, f"a verified dual certificate: <Z, S0> = {value:.6g}")
    return Admissibility("undetermined", best_lam, None, "no certificate could be verified")


def _maximize_lambda_min(family: object, m: int, radius: float) -> tuple[Array, float]:
    """Maximize the concave λ_min over the ball ‖c‖ ≤ radius (a bounded, derivative-free search)."""
    from scipy.optimize import minimize

    fam = family  # typed loosely: a callable Array → Array

    def objective(c: Array) -> float:
        norm = float(np.linalg.norm(c))
        if norm > radius:
            c = c * (radius / norm)
        return -lambda_min(fam(c))  # type: ignore[operator]

    starts = [np.zeros(m), *(radius / 2 * row for row in np.eye(m)), *(-radius / 2 * row for row in np.eye(m))]
    best_c, best_value = np.zeros(m), objective(np.zeros(m))
    for start in starts:
        options = {"xatol": 1e-12, "fatol": 1e-14, "maxiter": 4000}
        res = minimize(objective, start, method="Nelder-Mead", options=options)
        if res.fun < best_value:
            best_c, best_value = res.x, float(res.fun)
    norm = float(np.linalg.norm(best_c))
    if norm > radius:
        best_c = best_c * (radius / norm)
    return best_c, lambda_min(fam(best_c))  # type: ignore[operator]


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
