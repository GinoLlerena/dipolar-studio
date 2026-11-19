"""Phase 2 V1.1: the fixed-geometry (k = 0) fit, gated as frozen in docs/phase2/v1.0-design.md §3.

The fixtures and their expected answers are synthetic and exact: noiseless recovery is checked
against the true order matrix, the noisy fit against an independent least-squares solve, and the
intervals by the M1 coverage protocol (1000 seeds, nominal 68.3 %, band 64.5–72.1 %).
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from dipolar_core import fixed
from dipolar_core.forward import design_rows, frame_change, order_matrix
from dipolar_core.nuclides import dipolar_constant_hz_a3
from dipolar_core.problem import Problem

K = dipolar_constant_hz_a3("1H", "1H")


def _all_pairs(n: int) -> list[tuple[int, int]]:
    return [(i, j) for i in range(n) for j in range(i + 1, n)]


def _random_rotation(rng: np.random.Generator) -> np.ndarray:
    q, r = np.linalg.qr(rng.normal(size=(3, 3)))
    q = q * np.sign(np.diag(r))
    if np.linalg.det(q) < 0:
        q[:, 0] = -q[:, 0]
    return q


#: A nonplanar set of six protons (Å): every pair direction distinct, full rank 5.
NONPLANAR = np.array(
    [[0.0, 0.0, 0.0], [2.4, 0.3, 0.1], [1.1, 2.2, -0.4], [-1.3, 1.6, 1.2], [0.4, -1.9, 1.7], [2.9, -1.1, -1.5]]
)
#: A planar set (z = 0): only the in-plane block is visible.
PLANAR = np.array([[0.0, 0.0, 0.0], [2.5, 0.0, 0.0], [3.6, 2.1, 0.0], [1.2, 3.4, 0.0], [-1.0, 2.0, 0.0]])
#: An order matrix in ORDER_BASIS (Szz, Sxx−Syy, Sxy, Sxz, Syz), physical.
S_TRUE = np.array([-0.21, 0.08, 0.03, -0.02, 0.05])
S_PLANAR = np.array([-0.21, 0.08, 0.03, 0.0, 0.0])


def _design(positions: np.ndarray) -> np.ndarray:
    return design_rows(positions, _all_pairs(len(positions)), K)


# ----------------------------------------------------------------------------- the basis (D-7)
def test_the_orthonormal_basis_is_the_core_order_matrix() -> None:
    rng = np.random.default_rng(1)
    gram = np.einsum("kab,lab->kl", fixed.BASIS, fixed.BASIS)
    assert np.allclose(gram, np.eye(5), atol=1e-15)
    for _ in range(20):
        s5 = rng.normal(size=5)
        assert np.allclose(fixed.matrix_from_b(fixed.b_from_s5(s5)), order_matrix(s5), atol=1e-14)
        assert np.isclose(np.sum(fixed.b_from_s5(s5) ** 2), np.sum(order_matrix(s5) ** 2))


def test_a_rotation_acts_orthogonally_and_as_the_frame_change() -> None:
    rng = np.random.default_rng(2)
    for _ in range(10):
        q = _random_rotation(rng)
        r = fixed.rotation_b(q)
        assert np.allclose(r @ r.T, np.eye(5), atol=1e-13)
        b = fixed.b_from_s5(S_TRUE)
        # Passive frames: coordinates x' = Q x and S' = Q S Qᵀ leave every coupling unchanged.
        d_old = _design(NONPLANAR) @ S_TRUE
        d_new = _design(frame_change(q, NONPLANAR)) @ fixed.s5_from_b(r @ b)
        assert np.allclose(d_old, d_new, rtol=1e-12, atol=1e-9)


# ------------------------------------------------------------------------- recovery and rank
def test_noiseless_recovery_of_a_nonplanar_rank_5_fixture() -> None:
    a = _design(NONPLANAR)
    y = a @ S_TRUE
    res = fixed.fit_fixed(a, y, np.full(len(y), 0.5))
    assert res.rank_verified and res.required_rank == res.numerical_rank == 5
    assert np.allclose(res.s5, S_TRUE, atol=1e-10)
    assert [c.status for c in res.components] == ["estimated"] * 5
    assert res.chi2 < 1e-12 and res.nu == len(y) - 5 and res.adequacy == "given"
    assert res.admissibility.status == "admissible"


def test_a_planar_molecule_declared_cs_is_rank_3_and_verified() -> None:
    a = _design(PLANAR)
    y = a @ S_PLANAR
    res = fixed.fit_fixed(a, y, np.full(len(y), 0.5), fixed.SUBSPACES["Cs"])
    assert res.rank_verified and res.required_rank == 3
    assert np.allclose(res.s5, S_PLANAR, atol=1e-10)
    status = {c.name: c.status for c in res.components}
    assert status == {
        "Szz": "estimated",
        "Sxx-Syy": "estimated",
        "Sxy": "estimated",
        "Sxz": "fixed-by-symmetry",
        "Syz": "fixed-by-symmetry",
    }


def test_a_planar_molecule_declared_c1_reports_an_unverified_rank() -> None:
    a = _design(PLANAR)
    y = a @ S_PLANAR
    res = fixed.fit_fixed(a, y, np.full(len(y), 0.5))
    assert not res.rank_verified and res.numerical_rank == 3 and res.required_rank == 5
    assert res.null_b.shape == (5, 2)
    assert {c.status for c in res.components} == {"unverified"}
    assert res.covariance_b is None
    assert res.p_value is None and res.adequacy == "withheld" and res.adequacy_code == "ADEQUACY_RANK_UNVERIFIED"
    # The retained directions still reproduce the data exactly.
    assert np.allclose(res.predictions, y, atol=1e-9)


def test_round_67_near_planar_counterexample_is_unverified() -> None:
    """Pair vectors (1,0,0), (0,1,0), (1,1,0), (1,0,1e-7) pass a 1e-6 Å coplanarity test but have
    rank 4; with one σ raised 1e4 the singular values hide the fourth direction. D-8 never infers a
    rank from geometry: C1 requires 5, so the fit is unverified and adequacy withheld."""
    positions = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 1, 0], [1, 0, 1e-7]], dtype=float) * 2.0
    pairs = [(0, 1), (0, 2), (0, 3), (0, 4)]
    a = design_rows(positions, pairs, K)
    sigma = np.array([1.0, 1.0, 1.0, 1e4])
    res = fixed.fit_fixed(a, a @ S_PLANAR, sigma)
    assert not res.rank_verified and res.adequacy == "withheld"


def test_fewer_observations_than_parameters() -> None:
    a = _design(NONPLANAR)[:3]
    res = fixed.fit_fixed(a, a @ S_TRUE, np.full(3, 0.5))
    assert not res.rank_verified and res.numerical_rank == 3
    assert res.null_b.shape == (5, 2) and np.allclose(res.null_b.T @ res.retained_b, 0, atol=1e-12)
    assert res.nu == -2 and res.adequacy == "withheld"


def test_rank_zero_estimates_nothing() -> None:
    a = np.zeros((4, 5))
    res = fixed.fit_fixed(a, np.ones(4), np.ones(4))
    assert res.numerical_rank == 0 and not res.rank_verified
    assert np.all(res.b == 0) and res.retained_b.shape == (5, 0)
    assert res.admissibility.status == "feasible" and res.admissibility.representative_b is not None


def test_a_weak_direction_leaves_the_rank_unverified() -> None:
    """Nearly planar: a 1e-7 Å out-of-plane offset keeps every direction (s/s_max ≈ 8e-8, above
    the 1e-10 cutoff) but makes one weak (below 1e-6)."""
    positions = PLANAR.copy()
    positions[:, 2] = [0.0, 1e-7, -1e-7, 2e-7, 0.0]
    a = _design(positions)
    res = fixed.fit_fixed(a, a @ S_TRUE, np.full(len(a), 0.5))
    assert res.numerical_rank == 5 and not res.rank_verified
    assert 1e-10 < res.singular_ratios[-1] < 1e-6
    assert "weakest" in res.rank_reason and res.adequacy == "withheld"


def test_ideal_benzene_in_d6h_has_one_order_parameter() -> None:
    r_h = 2.4778
    ring = np.array([[r_h * math.cos(k * math.pi / 3), r_h * math.sin(k * math.pi / 3), 0.0] for k in range(6)])
    pairs = [(0, 1), (0, 2), (0, 3)]  # one per D6h pair orbit: ortho, meta, para
    a = design_rows(ring, pairs, K)
    s5 = np.array([-0.26, 0.0, 0.0, 0.0, 0.0])
    res = fixed.fit_fixed(a, a @ s5, np.array([0.015, 0.02, 0.026]), fixed.SUBSPACES["D6h"])
    assert res.rank_verified and res.required_rank == 1 and res.nu == 2
    estimate = res.components[0].estimate
    assert estimate is not None and abs(estimate + 0.26) <= 1e-12
    assert [c.status for c in res.components[1:]] == ["fixed-by-symmetry"] * 4


# --------------------------------------------------------------------- noise, intervals, frames
def test_the_noisy_fit_equals_an_independent_least_squares_solve() -> None:
    rng = np.random.default_rng(7)
    a = _design(NONPLANAR)
    sigma = rng.uniform(0.2, 1.0, size=len(a))
    y = a @ S_TRUE + rng.normal(size=len(a)) * sigma
    res = fixed.fit_fixed(a, y, sigma)
    expected, *_ = np.linalg.lstsq(a / sigma[:, None], y / sigma, rcond=None)
    assert np.allclose(res.s5, expected, rtol=1e-10, atol=1e-12)
    cov_s5 = np.linalg.inv((a / sigma[:, None]).T @ (a / sigma[:, None]))
    se = np.sqrt(np.diag(cov_s5))
    assert np.allclose([c.se if c.se is not None else math.nan for c in res.components], se, rtol=1e-8)


def test_a_full_covariance_whitens_like_the_core() -> None:
    rng = np.random.default_rng(8)
    a = _design(NONPLANAR)
    n = len(a)
    l_mat = np.tril(rng.normal(scale=0.1, size=(n, n)), -1) + np.diag(rng.uniform(0.3, 0.8, n))
    cov = l_mat @ l_mat.T
    sigma = np.sqrt(np.diag(cov))
    y = a @ S_TRUE + l_mat @ rng.normal(size=n)
    res = fixed.fit_fixed(a, y, sigma, covariance=cov)
    w = np.linalg.inv(np.linalg.cholesky(cov))
    expected, *_ = np.linalg.lstsq(w @ a, w @ y, rcond=None)
    assert np.allclose(res.s5, expected, rtol=1e-9, atol=1e-12)


def test_the_covariance_limit_is_checked_before_anything_is_allocated() -> None:
    n = fixed.MAX_COVARIANCE_N + 1
    with pytest.raises(ValueError, match="at most"):
        fixed.fit_fixed(np.zeros((n, 5)), np.zeros(n), np.ones(n), covariance=np.zeros((1, 1)))


def test_a_rotated_frame_gives_the_same_predictions_and_a_rotated_covariance() -> None:
    rng = np.random.default_rng(9)
    a = _design(NONPLANAR)
    sigma = np.full(len(a), 0.5)
    y = a @ S_TRUE + rng.normal(size=len(a)) * sigma
    q = _random_rotation(rng)
    first = fixed.fit_fixed(a, y, sigma)
    second = fixed.fit_fixed(_design(frame_change(q, NONPLANAR)), y, sigma)
    r = fixed.rotation_b(q)
    assert np.allclose(first.predictions, second.predictions, atol=1e-9)
    assert np.allclose(r @ first.b, second.b, atol=1e-10)
    assert first.covariance_b is not None and second.covariance_b is not None
    assert np.allclose(r @ first.covariance_b @ r.T, second.covariance_b, atol=1e-10)


def test_a_rotated_rank_deficient_fit_keeps_its_estimable_subspace() -> None:
    """Planar C1 (rank 3): the retained subspace rotates with the frame (compared as subspaces)."""
    rng = np.random.default_rng(10)
    a = _design(PLANAR)
    y = a @ S_PLANAR
    q = _random_rotation(rng)
    first = fixed.fit_fixed(a, y, np.full(len(a), 0.5))
    second = fixed.fit_fixed(_design(frame_change(q, PLANAR)), y, np.full(len(a), 0.5))
    r = fixed.rotation_b(q)
    p1 = r @ first.retained_b
    p2 = second.retained_b
    assert np.allclose(p1 @ p1.T, p2 @ p2.T, atol=1e-9)  # the same projector
    assert np.allclose(first.predictions, second.predictions, atol=1e-9)


def test_interval_coverage_follows_the_m1_protocol() -> None:
    """1000 seeds, nominal 68.3 %: each estimated component's coverage lies in 64.5–72.1 %."""
    a = _design(NONPLANAR)
    sigma = np.full(len(a), 0.5)
    rng = np.random.default_rng(20261118)
    hits = np.zeros(5)
    for _ in range(1000):
        y = a @ S_TRUE + rng.normal(size=len(a)) * sigma
        res = fixed.fit_fixed(a, y, sigma)
        for j, c in enumerate(res.components):
            assert c.intervals is not None
            lo, hi = c.intervals["68.3"]
            hits[j] += lo <= S_TRUE[j] <= hi
    assert np.all((hits >= 645) & (hits <= 721)), hits


def test_adequacy_flags_a_misfit_and_has_no_p_value_without_freedom() -> None:
    a = _design(NONPLANAR)
    y = a @ S_TRUE
    y[0] += 50.0
    res = fixed.fit_fixed(a, y, np.full(len(a), 0.1))
    assert res.adequacy == "inadequate" and res.p_value is not None and res.p_value < 1e-3
    exact = _design(NONPLANAR)[:5]
    res = fixed.fit_fixed(exact, exact @ S_TRUE, np.full(5, 0.5))
    assert res.rank_verified and res.nu == 0 and res.p_value is None and res.adequacy == "no-dof"


# ------------------------------------------------------------------------ admissibility (D-9)
def test_a_determined_tensor_is_tested_directly() -> None:
    assert fixed.admissibility(fixed.b_from_s5(S_TRUE), np.zeros((5, 0))).status == "admissible"
    unphysical = fixed.b_from_s5(np.array([-0.8, 0, 0, 0, 0]))  # λ_min = −0.8
    assert fixed.admissibility(unphysical, np.zeros((5, 0))).status == "inadmissible"


def test_feasible_and_infeasible_families_are_certified() -> None:
    nulls = fixed.SUBSPACES["C1"][:, 1:]  # everything but Szz is free
    feasible = fixed.admissibility(fixed.b_from_s5(np.array([-0.3, 0, 0, 0, 0])), nulls)
    assert feasible.status == "feasible" and feasible.representative_b is not None
    assert fixed.lambda_min(feasible.representative_b) >= -0.5
    # S_zz = −0.9 forces λ_min ≤ −0.9 for every completion: no physical tensor exists.
    infeasible = fixed.admissibility(fixed.b_from_s5(np.array([-0.9, 0, 0, 0, 0])), nulls)
    assert infeasible.status == "infeasible" and "dual certificate" in infeasible.certificate


def test_round_65_rank_1_admissibility_is_the_same_in_two_frames() -> None:
    """A single direction measured, contraction 0.9: the answer may not depend on the frame."""
    statuses = []
    for direction in (np.array([1.0, 0.0, 1.0]) / math.sqrt(2), np.array([0.0, 0.0, 1.0])):
        a = design_rows(np.array([[0, 0, 0], 2.5 * direction]), [(0, 1)], K)
        contraction = 0.9  # cᵀSc for the unit direction c
        y = np.array([K / 2.5**3 * contraction])
        res = fixed.fit_fixed(a, y, np.array([0.1]))
        statuses.append(res.admissibility.status)
    assert statuses[0] == statuses[1] == "feasible", statuses


def test_the_k0_problem_is_refused_by_the_search_fit() -> None:
    from dipolar_core.fit import fit

    a = _design(NONPLANAR)
    problem = Problem(
        design=lambda theta: a,
        y=a @ S_TRUE,
        sigma=np.full(len(a), 0.5),
        lower=np.zeros(0),
        upper=np.zeros(0),
        theta_names=(),
        order_names=fixed.NAMES,
    )
    with pytest.raises(ValueError, match="fit_fixed"):
        fit(problem)


def test_a_failed_search_never_claims_infeasibility(monkeypatch: pytest.MonkeyPatch) -> None:
    """If the primal search returns a poor point in a family that does hold a physical tensor, the
    dual check must fail and the answer be "undetermined", never "infeasible" (D-9). The family:
    S0 = diag(−0.6, 0.6, 0), unphysical, with Szz free (it reaches λ_min = −0.4)."""
    b0 = fixed.b_from_matrix(np.diag([-0.6, 0.6, 0.0]))
    nulls = fixed.SUBSPACES["C1"][:, :1]
    poor = np.zeros(1)  # the fitted point itself: λ_min = −0.6
    monkeypatch.setattr(
        fixed, "_search_lambda_min", lambda family, m, radius: iter([(poor, fixed.lambda_min(family(poor)))])
    )
    assert fixed.admissibility(b0, nulls).status == "undetermined"


# =============================================================================================
# Round 71 gates. These tests and their targets were written and committed before the fixes they
# check (the freeze order of design §3); every target is computed independently of fixed.py.
# =============================================================================================


def _synthetic_b_design(singular: tuple[float, ...], n: int, seed: int) -> np.ndarray:
    """A design in b coordinates with prescribed singular values (ties allowed), as ORDER_BASIS rows."""
    rng = np.random.default_rng(seed)
    u, _ = np.linalg.qr(rng.normal(size=(n, n)))
    v, _ = np.linalg.qr(rng.normal(size=(5, 5)))
    a_b = u[:, :5] @ np.diag(singular) @ v.T
    out: np.ndarray = a_b * fixed.ORTHO_SCALE  # so that (design / ORTHO_SCALE) = a_b
    return out


def test_a_singular_covariance_is_refused() -> None:
    """Eigenvalues exactly 0 and 1: Cholesky may pass by roundoff, the fit must not."""
    a = _design(NONPLANAR)[:2]
    with pytest.raises(ValueError, match="positive definite"):
        fixed.fit_fixed(a, np.zeros(2), np.full(2, math.sqrt(0.5)), covariance=np.full((2, 2), 0.5))


def test_a_nearly_symmetric_covariance_uses_its_symmetric_part() -> None:
    rng = np.random.default_rng(11)
    a = _design(NONPLANAR)
    n = len(a)
    l_mat = np.tril(rng.normal(scale=0.1, size=(n, n)), -1) + np.diag(rng.uniform(0.3, 0.8, n))
    cov = l_mat @ l_mat.T
    skew = np.triu(np.full((n, n), 5e-13 * float(np.max(np.abs(cov)))), 1)  # within the tolerance
    y = a @ S_TRUE + l_mat @ rng.normal(size=n)
    sigma = np.sqrt(np.diag(cov))
    first = fixed.fit_fixed(a, y, sigma, covariance=cov + skew)
    second = fixed.fit_fixed(a, y, sigma, covariance=cov + skew.T)
    # The symmetric part is the same matrix either way, so the fits are bit-identical; factoring
    # one triangle would differ.
    assert np.array_equal(first.b, second.b)


def test_the_cap_is_checked_before_the_covariance_is_converted() -> None:
    class Boom:
        def __array__(self, *args: object, **kwargs: object) -> np.ndarray:
            raise AssertionError("the covariance was converted before the cap was checked")

    n = fixed.MAX_COVARIANCE_N + 1
    with pytest.raises(ValueError, match="at most"):
        fixed.fit_fixed(np.zeros((n, 5)), np.zeros(n), np.ones(n), covariance=Boom())  # type: ignore[arg-type]


def test_whitening_at_the_covariance_limit_stays_within_the_memory_budget() -> None:
    """D-11: peak 128 MB including the caller's N × N covariance (32 MB at N = 2000)."""
    import tracemalloc

    n = fixed.MAX_COVARIANCE_N
    rng = np.random.default_rng(12)
    a = rng.normal(size=(n, 5))
    cov = np.diag(rng.uniform(0.5, 1.5, n))
    cov[0, 1] = cov[1, 0] = 0.1
    y = rng.normal(size=n)
    sigma = np.sqrt(np.diag(cov))
    tracemalloc.start()
    fixed.fit_fixed(a, y, sigma, covariance=cov)
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    assert peak <= 96 * 2**20, f"{peak / 2**20:.0f} MB beyond the caller's covariance"


def test_a_nearly_orthonormal_subspace_is_refused_or_made_exact() -> None:
    """diag(1.000004, 1, 1, 1, 1) is not orthonormal; within 1e-13 it is orthonormalized, and the
    estimate is then the Frobenius minimum-norm one: one row measuring b1 + b2 = 0.3 gives
    b = (0.15, 0.15, 0, 0, 0)."""
    design = (np.array([[1.0, 1.0, 0.0, 0.0, 0.0]])) * fixed.ORTHO_SCALE
    with pytest.raises(ValueError, match="orthonormal"):
        fixed.fit_fixed(design, np.array([0.3]), np.array([1.0]), np.diag([1.000004, 1, 1, 1, 1]))
    near = np.eye(5) + np.diag([1e-14, 0, 0, 0, 0])
    res = fixed.fit_fixed(design, np.array([0.3]), np.array([1.0]), near)
    assert np.allclose(res.b, [0.15, 0.15, 0, 0, 0], atol=1e-15)
    assert np.allclose(res.null_b.T @ res.b, 0, atol=1e-15)


def test_the_retained_and_null_directions_are_orthonormal_and_annihilating() -> None:
    a = _design(PLANAR)
    sigma = np.full(len(a), 0.5)
    rng = np.random.default_rng(13)
    y = a @ S_PLANAR + rng.normal(size=len(a)) * sigma
    res = fixed.fit_fixed(a, y, sigma)  # C1: rank 3, nullity 2
    r, z = res.retained_b, res.null_b
    assert np.allclose(r.T @ r, np.eye(3), atol=1e-12) and np.allclose(z.T @ z, np.eye(2), atol=1e-12)
    assert np.allclose(r.T @ z, 0, atol=1e-12)
    a_b = a / fixed.ORTHO_SCALE
    assert np.max(np.abs(a_b @ z)) <= 1e-9 * np.max(np.abs(a_b))  # the design annihilates them
    expected = np.linalg.pinv((a_b / sigma[:, None]), rcond=1e-10) @ (y / sigma)  # independent min-norm
    assert np.allclose(res.b, expected, rtol=1e-9, atol=1e-12)
    singular = np.linalg.svd(a_b / sigma[:, None], compute_uv=False)[:3]
    assert np.allclose(res.retained_se, 1.0 / singular, rtol=1e-12)


def test_fewer_rows_than_parameters_keep_singular_vectors_paired() -> None:
    a = _design(NONPLANAR)[:2]
    y = a @ S_TRUE
    res = fixed.fit_fixed(a, y, np.ones(2))
    assert np.allclose(res.predictions, y, atol=1e-9)
    a_b = a / fixed.ORTHO_SCALE
    assert np.max(np.abs(a_b @ res.null_b)) <= 1e-9 * np.max(np.abs(a_b))


def test_a_tiny_sigma_keeps_a_representable_uncertainty() -> None:
    """A = I on ORDER_BASIS, σ = 1e-160: SE(Szz) is 1e-160, not 0 (s² would overflow, and the
    squares of 1e-160 would be subnormal)."""
    res = fixed.fit_fixed(np.eye(5), np.full(5, 0.1), np.full(5, 1e-160))
    assert res.rank_verified
    se = res.components[0].se
    assert se is not None and math.isclose(se, 1e-160, rel_tol=1e-12)


def test_a_common_huge_scale_cancels() -> None:
    a = _design(NONPLANAR)
    y = a @ S_TRUE
    plain = fixed.fit_fixed(a, y, np.full(len(a), 0.5))
    scaled = fixed.fit_fixed(a * 1e300, y * 1e300, np.full(len(a), 0.5e300))
    assert np.allclose(plain.b, scaled.b, rtol=1e-12, atol=1e-14)


def test_an_unrepresentable_problem_is_refused() -> None:
    with pytest.raises(ValueError, match="representable"):
        fixed.fit_fixed(np.eye(5), np.full(5, 1e10), np.full(5, 1e-300))


def test_both_interval_widths_are_exact_gaussian_quantiles() -> None:
    a = _design(NONPLANAR)
    rng = np.random.default_rng(14)
    sigma = np.full(len(a), 0.5)
    res = fixed.fit_fixed(a, a @ S_TRUE + rng.normal(size=len(a)) * sigma, sigma)
    for c in res.components:
        assert c.intervals is not None and c.se is not None
        lo68, hi68 = c.intervals["68.3"]
        lo95, hi95 = c.intervals["95"]
        assert math.isclose(hi68 - lo68, 2.0 * c.se, rel_tol=1e-12)
        assert math.isclose(hi95 - lo95, 2.0 * 1.959963984540054 * c.se, rel_tol=1e-12)


def test_an_intermediate_p_value_is_the_chi2_tail() -> None:
    """With ν = 2 the χ² survival function is exp(−χ²/2) exactly."""
    a = _design(NONPLANAR)[:7]
    rng = np.random.default_rng(15)
    sigma = np.full(7, 0.5)
    for _ in range(5):
        res = fixed.fit_fixed(a, a @ S_TRUE + rng.normal(size=7) * sigma, sigma)
        assert res.nu == 2 and res.p_value is not None
        assert math.isclose(res.p_value, math.exp(-res.chi2 / 2), rel_tol=1e-10)


def test_matched_functionals_agree_across_frames_with_tied_singular_values() -> None:
    design = _synthetic_b_design((3.0, 3.0, 2.0, 2.0, 1.0), n=9, seed=16)
    rng = np.random.default_rng(17)
    y = rng.normal(size=9)
    sigma = np.ones(9)
    q = _random_rotation(rng)
    r = fixed.rotation_b(q)
    a_b = design / fixed.ORTHO_SCALE
    rotated = (a_b @ r.T) * fixed.ORTHO_SCALE  # the same data in the rotated frame
    first = fixed.fit_fixed(design, y, sigma)
    second = fixed.fit_fixed(rotated, y, sigma)
    assert first.covariance_b is not None and second.covariance_b is not None
    for c in np.eye(5):
        assert math.isclose(c @ first.b, (r @ c) @ second.b, rel_tol=1e-9, abs_tol=1e-12)
        assert math.isclose(c @ first.covariance_b @ c, (r @ c) @ second.covariance_b @ (r @ c), rel_tol=1e-9)


def test_strict_feasibility_needs_a_margin_over_rounding() -> None:
    """The xy block has diagonals −1/2, 1/2 and off-diagonal 1e-9, only Syz free: every completion
    has λ_min < −1/2 by interlacing, by about 1e-18. That is far inside ε, so the honest answer is
    "feasible-within-tolerance", never a strict "feasible"."""
    s = np.array([[-0.5, 1e-9, 0.0], [1e-9, 0.5, 0.0], [0.0, 0.0, 0.0]])
    b0 = fixed.b_from_matrix(s)
    b0[4] = 0.0
    nulls = fixed.SUBSPACES["C1"][:, 4:]
    assert fixed.admissibility(b0, nulls).status == "feasible-within-tolerance"


def test_a_witness_away_from_the_fitted_point() -> None:
    """S0 = diag(−0.6, 0.6, 0) is unphysical; along Szz the family reaches λ_min = −0.4."""
    b0 = fixed.b_from_matrix(np.diag([-0.6, 0.6, 0.0]))
    nulls = fixed.SUBSPACES["C1"][:, :1]
    res = fixed.admissibility(b0, nulls)
    assert res.status == "feasible" and res.representative_b is not None
    assert fixed.lambda_min(res.representative_b) >= -0.5
    assert math.isclose(res.lambda_min or 0.0, -0.4, abs_tol=1e-6)


def test_the_dual_margin_rejects_a_near_separator() -> None:
    """Z = e_z e_zᵀ is a valid dual for "everything but Szz free"; it certifies infeasibility only
    when ⟨Z, S0⟩ = S0_zz is below −1/2 by more than the finite-precision margin."""
    nulls = fixed.SUBSPACES["C1"][:, 1:]
    z = np.diag([0.0, 0.0, 1.0])
    near = fixed.b_from_s5(np.array([-0.5 - 1e-10, 0, 0, 0, 0]))
    far = fixed.b_from_s5(np.array([-0.6, 0, 0, 0, 0]))
    assert not fixed.certifies_infeasible(z, near, nulls)
    assert fixed.certifies_infeasible(z, far, nulls)


def test_tied_lowest_eigenvalues_never_give_a_wrong_answer() -> None:
    """Round 71's example: diag(−.51, −.51, 1.02) + t·diag(1, −2, 1) has no physical member; with
    tied lowest eigenvectors the simple dual may fail, so "undetermined" is allowed, never
    "feasible"."""
    n = np.diag([1.0, -2.0, 1.0]) / math.sqrt(6.0)
    s0 = np.diag([-0.51, -0.51, 1.02])
    s0 = s0 - float(np.sum(s0 * n)) * n  # the minimum-norm point of the family
    res = fixed.admissibility(fixed.b_from_matrix(s0), fixed.b_from_matrix(n)[:, None])
    assert res.status in ("infeasible", "undetermined")


def test_certificates_are_fast() -> None:
    import time

    cases = [
        (fixed.b_from_s5(np.array([-0.3, 0, 0, 0, 0])), fixed.SUBSPACES["C1"][:, 1:]),
        (fixed.b_from_matrix(np.diag([-0.6, 0.6, 0.0])), fixed.SUBSPACES["C1"][:, :1]),
        (fixed.b_from_s5(np.array([-0.9, 0, 0, 0, 0])), fixed.SUBSPACES["C1"][:, 1:]),
    ]
    for b0, nulls in cases:
        start = time.process_time()
        fixed.admissibility(b0, nulls)
        assert time.process_time() - start <= 0.3  # D-11: 0.1 s on the named hardware, 3× margin


def test_the_certificate_reason_names_the_actual_case() -> None:
    """Zero data at nonzero rank: S = 0 belongs to the family, but the rank is not zero."""
    a = _design(PLANAR)
    res = fixed.fit_fixed(a, np.zeros(len(a)), np.full(len(a), 0.5))
    assert res.numerical_rank == 3 and res.admissibility.status == "feasible"
    assert "rank zero" not in res.admissibility.certificate
    assert res.admissibility.family == "the family preserving the retained projection"


def test_the_public_array_contract() -> None:
    a = _design(NONPLANAR)
    with pytest.raises(ValueError):
        fixed.fit_fixed(a, (a @ S_TRUE)[:, None], np.full(len(a), 0.5))
    res = fixed.fit_fixed(a, a @ S_TRUE, np.full(len(a), 0.5))
    res.subspace[0, 0] = 99.0
    assert fixed.SUBSPACES["C1"][0, 0] == 1.0


# =============================================================================================
# Round 72 gates (the final round). Written and committed before the fixes; every target is
# computed independently of fixed.py.
# =============================================================================================


def _two_by_two(delta: float, scale: float) -> np.ndarray:
    """scale · [[1, 1−δ], [1−δ, 1]]: eigenvalues scale·(2 − δ) and scale·δ."""
    return scale * np.array([[1.0, 1.0 - delta], [1.0 - delta, 1.0]])


def test_covariance_validation_does_not_depend_on_scale() -> None:
    a = _design(NONPLANAR)[:2]
    y = np.array([0.1, -0.2])
    for scale in (1.0, 1e-300, 1e300):
        sigma = np.full(2, math.sqrt(scale))
        # λ_min/‖C‖∞ = δ/2: 0.83e-12 < 1e-12 is refused at every scale; 2e-12 is accepted.
        with pytest.raises(ValueError, match="positive definite"):
            fixed.fit_fixed(a, y * math.sqrt(scale), sigma, covariance=_two_by_two(1.666e-12, scale))
        fixed.fit_fixed(a, y * math.sqrt(scale), sigma, covariance=_two_by_two(4e-12, scale))
    big = 1e308 * np.eye(len(_design(NONPLANAR)))
    a_full = _design(NONPLANAR)
    res = fixed.fit_fixed(a_full, a_full @ S_TRUE * 1e154, np.full(len(a_full), 1e154), covariance=big)
    plain = fixed.fit_fixed(a_full, a_full @ S_TRUE, np.ones(len(a_full)))
    assert np.allclose(res.b * 1e-154, plain.b, rtol=1e-10, atol=1e-14)


def test_a_float32_covariance_stays_within_the_memory_budget() -> None:
    """D-11: 128 MB including the caller's matrix; a float32 input is 16 MB at N = 2000."""
    import tracemalloc

    n = fixed.MAX_COVARIANCE_N
    rng = np.random.default_rng(21)
    cov = np.diag(rng.uniform(0.5, 1.5, n)).astype(np.float32)
    sigma = np.sqrt(np.diag(cov).astype(np.float64))
    a = rng.normal(size=(n, 5))
    y = rng.normal(size=n)
    tracemalloc.start()
    fixed.fit_fixed(a, y, sigma, covariance=cov)
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    assert peak <= 112 * 2**20, f"{peak / 2**20:.0f} MB beyond the caller's 16 MB matrix"


def test_boundary_and_undetermined_certificates_are_fast() -> None:
    import time

    n = np.diag([1.0, -2.0, 1.0]) / math.sqrt(6.0)
    s0 = np.diag([-0.51, -0.51, 1.02])
    s0 = s0 - float(np.sum(s0 * n)) * n
    cases = [
        (fixed.b_from_s5(np.array([-0.5, 0, 0, 0, 0])), fixed.SUBSPACES["C1"][:, 1:]),  # the boundary
        (fixed.b_from_matrix(s0), fixed.b_from_matrix(n)[:, None]),  # tied eigenvectors
    ]
    for b0, nulls in cases:
        fixed.admissibility(b0, nulls)  # warm
        start = time.process_time()
        fixed.admissibility(b0, nulls)
        assert time.process_time() - start <= 0.2  # D-11: 0.1 s on the named hardware, 2× margin


def test_unrepresentable_uncertainties_are_refused() -> None:
    """σ = 1e155 makes the covariance overflow, σ = 1e-165 underflow: neither can be returned."""
    for sigma in (1e155, 1e-165):
        with pytest.raises(ValueError, match="representable"):
            fixed.fit_fixed(np.eye(5), np.zeros(5), np.full(5, sigma))


def test_a_huge_design_is_fitted_with_finite_outputs() -> None:
    """A 1e150 design: SE 1e-150 and a covariance diagonal of 1e-300, both representable. (A 1e300
    design would need a 1e-600 covariance, which the representability rule refuses.)"""
    res = fixed.fit_fixed(1e150 * np.eye(5), np.full(5, 1e149), np.ones(5))
    assert res.rank_verified and np.all(np.isfinite(res.singular_ratios))
    assert np.allclose(res.s5, 0.1, rtol=1e-12)
    se = res.components[0].se
    assert se is not None and math.isclose(se, 1e-150, rel_tol=1e-12)
    with pytest.raises(ValueError, match="representable"):
        fixed.fit_fixed(1e300 * np.eye(5), np.full(5, 1e299), np.ones(5))


def test_rounding_below_sigma_withholds_adequacy() -> None:
    """Two identical rows measuring only Szz, y = 0.25, σ = 1e-20: the exact optimum has χ² = 0,
    but σ is far below the rounding of y, so no adequacy decision can be made."""
    row = design_rows(np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 2.5]]), [(0, 1)], K)
    a = np.vstack([row, row])
    res = fixed.fit_fixed(a, np.full(2, 0.25), np.full(2, 1e-20), fixed.SUBSPACES["D6h"])
    assert res.adequacy == "withheld" and res.adequacy_code == "ADEQUACY_NUMERICAL"


def test_the_dual_verifier_requires_a_symmetric_witness_and_its_preconditions() -> None:
    nulls = fixed.SUBSPACES["C1"][:, :1]  # Szz free
    b0 = fixed.b_from_s5(np.array([0.0, 0.0, -0.1, 0.0, 0.0]))  # Sxy = −0.1: physical
    z = np.eye(3) / 3
    z[0, 1] = 10.0
    assert not fixed.certifies_infeasible(z, b0, nulls)
    with pytest.raises(ValueError):
        fixed.certifies_infeasible(np.eye(3) / 3, b0 + nulls[:, 0], nulls)  # b0 not ⟂ the nulls
    with pytest.raises(ValueError):
        fixed.certifies_infeasible(np.eye(3) / 3, b0, 2 * nulls)  # not orthonormal


def test_the_tolerance_status_is_guarded_against_rounding() -> None:
    """Every completion has λ_min ≤ Szz < −0.500000001 (by about 3.8e-17): not within tolerance."""
    b0 = np.array([-0.6123724369205394, 0.0, 0.0, 0.0, 0.0])
    res = fixed.admissibility(b0, fixed.SUBSPACES["C1"][:, 1:])
    assert res.status in ("infeasible", "undetermined")


def test_the_arithmetic_margin_of_the_dual_is_required() -> None:
    """Halfway between the cutoff with δ and without it: rejected only because of δ."""
    m = 4
    eps, delta = fixed.FEASIBILITY_EPS, fixed.FEASIBILITY_DELTA
    s_zz = -0.5 - (2.0 + math.sqrt(1.5 * m)) * eps - delta / 2
    z = np.diag([0.0, 0.0, 1.0])
    assert not fixed.certifies_infeasible(
        z, fixed.b_from_s5(np.array([s_zz, 0, 0, 0, 0])), fixed.SUBSPACES["C1"][:, 1:]
    )


def test_the_certificate_text_shows_the_separation() -> None:
    b0 = fixed.b_from_s5(np.array([-0.50000001, 0, 0, 0, 0]))
    res = fixed.admissibility(b0, fixed.SUBSPACES["C1"][:, 1:])
    if res.status == "infeasible":
        assert "-0.50000001" in res.certificate and "cutoff" in res.certificate


def test_fixed_by_symmetry_is_reserved_for_structural_zeros() -> None:
    """A custom direction (1, 0, 1e-13, 0, 0) is not a symmetry: Sxy is not fixed at zero."""
    direction = np.array([1.0, 0.0, 1e-13, 0.0, 0.0])
    custom = np.column_stack([direction / np.linalg.norm(direction), *fixed.SUBSPACES["C1"][:, [1, 3, 4]].T])
    a = _design(NONPLANAR)
    res = fixed.fit_fixed(a, a @ S_TRUE, np.full(len(a), 0.5), custom)
    status = {c.name: c.status for c in res.components}
    assert status["Sxy"] != "fixed-by-symmetry"


def test_a_covariance_near_overflow_is_normalized_exactly() -> None:
    """Round 72 (a surviving mutant): Σ = 4^511 Σ₀ has finite entries but an overflowing
    ‖Σ‖∞, so only the power-of-4 normalization can test and factor it. The normalization is exact,
    so the fit is bit-for-bit the fit of the unscaled problem."""
    rng = np.random.default_rng(72)
    n = 8
    cov0 = 0.4 * np.eye(n) + 0.6  # (1 − ρ)I + ρJ with ρ = 0.6: positive definite, row sums 5.2
    a0 = rng.normal(size=(n, 5))
    y0 = a0 @ S_TRUE + rng.normal(size=n)
    scale = 2.0**511
    with np.errstate(over="ignore"):
        assert np.isinf(np.sum(np.abs(cov0[0] * scale**2)))  # the unnormalized norm overflows
    ref = fixed.fit_fixed(a0, y0, np.sqrt(np.diag(cov0)), covariance=cov0)
    big = fixed.fit_fixed(a0 * scale, y0 * scale, np.sqrt(np.diag(cov0)) * scale, covariance=cov0 * scale**2)
    assert np.array_equal(big.b, ref.b)
    assert np.array_equal(big.retained_se, ref.retained_se)
    assert big.chi2 == ref.chi2


def test_a_design_whose_norm_overflows_still_reports_its_retained_estimates() -> None:
    """Round 72 (a surviving mutant): every whitened entry is finite but ‖wa‖₂ is not. Without the
    power-of-two normalization the singular values overflow and the fit is refused; with it, a
    rank-deficient fit (no covariance is reported) returns its retained estimates, equal to the
    estimates of the problem scaled down by the same power of two."""
    rng = np.random.default_rng(73)
    n = 4096
    a0 = rng.normal(size=(n, 5))
    a0[:, 4] = 0.0  # Syz is not estimable: rank 4 < 5, so the rank is unverified
    y = rng.normal(size=n)
    scale = 2.0**1018
    with np.errstate(over="ignore"):
        assert not np.isfinite(np.linalg.norm(a0[:, 0] * scale))
    ref = fixed.fit_fixed(a0, y, np.ones(n))
    big = fixed.fit_fixed(a0 * scale, y, np.ones(n))
    assert not big.rank_verified and big.numerical_rank == 4 and big.covariance_b is None
    np.testing.assert_allclose(big.b * scale, ref.b, rtol=1e-12, atol=0)
    np.testing.assert_allclose(big.retained_se * scale, ref.retained_se, rtol=1e-12, atol=0)
    assert big.chi2 == pytest.approx(ref.chi2, rel=1e-12)


@pytest.mark.parametrize("order", ["C", "F"])
def test_the_in_place_factorization_leaves_the_callers_covariance_alone(order: str) -> None:
    """Round 72: the factorization works in place on its own workspace, never on the caller's
    matrix, in either memory order."""
    rng = np.random.default_rng(74)
    n = 300  # larger than one row block
    m = rng.normal(size=(n, n)) / math.sqrt(n)
    cov = np.array(m @ m.T + np.eye(n), order=order)
    before = cov.copy()
    a = rng.normal(size=(n, 5))
    res = fixed.fit_fixed(a, a @ S_TRUE, np.sqrt(np.diag(cov)), covariance=cov)
    assert np.array_equal(cov, before)
    lower = np.linalg.cholesky(before)
    wa = np.linalg.solve(lower, a)
    wy = np.linalg.solve(lower, a @ S_TRUE)
    s5 = np.linalg.lstsq(wa, wy, rcond=None)[0]
    np.testing.assert_allclose(res.s5, s5, rtol=1e-9, atol=1e-12)
