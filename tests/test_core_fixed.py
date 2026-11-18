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
    dual check must fail and the answer be "undetermined", never "infeasible" (D-9)."""
    nulls = fixed.SUBSPACES["C1"][:, 1:]
    b0 = fixed.b_from_s5(np.array([-0.3, 0, 0, 0, 0]))
    bad = np.array([1.2, 0.0, 0.0, 0.0])  # far along Sxx − Syy: λ_min < −1/2 there
    assert fixed.lambda_min(b0 + nulls @ bad) < -0.5
    monkeypatch.setattr(fixed, "_maximize_lambda_min", lambda family, m, radius: (bad, fixed.lambda_min(family(bad))))
    assert fixed.admissibility(b0, nulls).status == "undetermined"
