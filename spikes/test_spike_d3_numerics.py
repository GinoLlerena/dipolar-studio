"""M0 spike 1: the D3 numerical controls (plan §3 D3.7, §8 M0).

Question: does the dipolar-core inner solve, wrapped in a small grid-then-refine profile fit,
pass the D3 controls and reproduce the frozen fixture produced independently by
``tools/reference/``? The prototype fit below is spike code. It uses only dipolar-core's public
functions and SciPy; M1 replaces it with the real D3 stack.

Controls:
  * the weighted-projection case of D3.7;
  * planar and collinear data (D12): which tensor components they determine;
  * a rank-changing path: the full five-component tensor as the biphenyl flattens (φ → 0);
  * the two-parameter rigid model stays regular on its whole domain;
  * grid → refine reproduces ``noisy_fixture.json`` (optimum, predictions, χ², grid minima,
    validity, full-Jacobian covariance, profile intervals) and ``noiseless.json``;
  * the full (joint TRF) fit and the reduced (VarPro profile) fit agree.
"""

from __future__ import annotations

import itertools
import json
import math
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from dipolar_core.biphenyl import PROTON_LABELS, proton_positions, rigid_design
from dipolar_core.forward import ORDER_BASIS, design_rows
from dipolar_core.inference import RANK_RTOL, solve_inner
from dipolar_core.nuclides import dipolar_constant_hz_a3
from numpy.typing import NDArray
from scipy.optimize import brentq, least_squares, minimize_scalar

Array = NDArray[np.float64]
ROOT = Path(__file__).resolve().parents[1]
EXPECTED = ROOT / "datasets" / "biphenyl-synthetic" / "expected"
SPEC = json.loads((EXPECTED / "spec.json").read_text())
TOL = SPEC["tolerances"]["regression"]
K_HH = dipolar_constant_hz_a3("1H", "1H")
GRID = np.arange(0.0, 90.0 + 0.25, 0.5)  # 0:0.5:90, the frozen optimum convention


# --------------------------------------------------------------------------- prototype profile fit
@dataclass(frozen=True)
class Problem:
    pairs: tuple[tuple[int, int], ...]
    y: Array
    sigma: Array

    @classmethod
    def from_fixture(cls, name: str, y_key: str, sigma_key: str) -> Problem:
        data = json.loads((EXPECTED / name).read_text())
        index = {label: i for i, label in enumerate(PROTON_LABELS)}
        pairs = tuple((index[a], index[b]) for a, b in data["pairs"])
        return cls(pairs, np.array(data[y_key], dtype=float), np.array(data[sigma_key], dtype=float))

    def profile(self, phi: float) -> float:
        return solve_inner(rigid_design(phi, self.pairs), self.y, self.sigma).chi2

    def whitened_residual(self, theta: Array) -> Array:
        phi, szz, delta = (float(v) for v in theta)
        residual: Array = (rigid_design(phi, self.pairs) @ np.array([szz, delta]) - self.y) / self.sigma
        return residual


def grid_local_minima(values: Array) -> list[int]:
    """Indices that are no larger than their neighbours (an endpoint has one neighbour)."""
    out = []
    for i in range(len(values)):
        left = values[i - 1] if i > 0 else math.inf
        right = values[i + 1] if i + 1 < len(values) else math.inf
        if values[i] <= left and values[i] <= right:
            out.append(i)
    return out


def refine(problem: Problem, grid_phi: float) -> float:
    """Bounded 1-D refinement over the neighbouring grid cells (the frozen convention)."""
    lo, hi = max(0.0, grid_phi - 0.5), min(90.0, grid_phi + 0.5)
    res = minimize_scalar(problem.profile, bounds=(lo, hi), method="bounded", options={"xatol": 1e-11})
    assert res.success
    return float(res.x)


def fit(problem: Problem) -> dict[str, Any]:
    values = np.array([problem.profile(float(p)) for p in GRID])
    minima = grid_local_minima(values)
    best = int(np.argmin(values))
    phi = refine(problem, float(GRID[best]))
    sol = solve_inner(rigid_design(phi, problem.pairs), problem.y, problem.sigma)
    return {"phi": phi, "sol": sol, "grid_values": values, "grid_minima": minima, "grid_best": float(GRID[best])}


def full_jacobian(problem: Problem, theta: Array, h_deg: float = 1e-5) -> Array:
    """Whitened J in joint coordinates (φ in degrees, Szz, Δ): exact order columns, central φ step."""
    phi = float(theta[0])
    j = np.empty((len(problem.y), 3))
    up, down = (np.r_[phi + s, theta[1:]] for s in (h_deg, -h_deg))
    j[:, 0] = (problem.whitened_residual(up) - problem.whitened_residual(down)) / (2 * h_deg)
    j[:, 1:] = rigid_design(phi, problem.pairs) / problem.sigma[:, None]
    return j


def root(f: Callable[[float], float], a: float, b: float) -> float:
    return float(brentq(f, a, b, xtol=1e-13, rtol=1e-15, maxiter=200))


# --------------------------------------------------------------------------- D3.7 control case
def test_weighted_projection_control() -> None:
    """A = (1, 1)ᵀ, y = (0, 1)ᵀ, L = diag(1, 2) gives t* = 0.8 and χ² = 0.8 (L = diag(1/σ))."""
    sol = solve_inner(np.array([[1.0], [1.0]]), np.array([0.0, 1.0]), np.array([1.0, 0.5]))
    assert sol.params[0] == pytest.approx(0.8, abs=1e-15)
    assert sol.chi2 == pytest.approx(0.8, abs=1e-15)
    assert sol.rank == 1


# --------------------------------------------------------------------------- planar and collinear data
def random_rotation(rng: np.random.Generator) -> Array:
    q, r = np.linalg.qr(rng.normal(size=(3, 3)))
    q = q * np.sign(np.diag(r))
    return q if np.linalg.det(q) > 0 else -q


def s5_of(matrix: Array) -> Array:
    return np.array(
        [matrix[2, 2], matrix[0, 0] - matrix[1, 1], matrix[0, 1], matrix[0, 2], matrix[1, 2]],
    )


def test_coplanar_vectors_determine_the_in_plane_tensor_only() -> None:
    """D12: coplanar vectors fix three of the five components: the in-plane block n⊥ᵀ S n⊥
    (two diagonal values and one off-diagonal; the normal component follows from the trace).
    The two normal–in-plane couplings (n S e₁, n S e₂) are unidentified."""
    rng = np.random.default_rng(12)
    rot = random_rotation(rng)
    e1, e2, normal = rot.T
    angles = rng.uniform(0, np.pi, size=12)
    lengths = rng.uniform(2.0, 5.0, size=12)
    vectors = lengths[:, None] * (np.cos(angles)[:, None] * e1 + np.sin(angles)[:, None] * e2)
    positions = np.vstack([np.zeros(3), vectors])
    pairs = tuple((0, i) for i in range(1, 13))
    design = design_rows(positions, pairs, K_HH)
    s_true = np.array([[0.1, 0.03, -0.05], [0.03, -0.25, 0.08], [-0.05, 0.08, 0.15]])
    y = design @ s5_of(s_true)
    sol = solve_inner(design, y, np.ones(12))
    assert sol.rank == 3
    assert not math.isfinite(sol.condition)
    s_fit = np.zeros((3, 3))
    szz, delta, sxy, sxz, syz = sol.params
    s_fit[:] = [[(delta - szz) / 2, sxy, sxz], [sxy, (-delta - szz) / 2, syz], [sxz, syz, szz]]
    in_plane = np.column_stack([e1, e2])
    np.testing.assert_allclose(in_plane.T @ s_fit @ in_plane, in_plane.T @ s_true @ in_plane, atol=1e-12)
    assert normal @ s_fit @ normal == pytest.approx(normal @ s_true @ normal, abs=1e-12)  # via the trace
    np.testing.assert_allclose(sol.predictions, y, atol=1e-9)
    # The unidentified directions are exactly the normal–in-plane couplings.
    vt = np.linalg.svd(design)[2]
    null = vt[3:]
    for e in (e1, e2):
        m = np.outer(normal, e) + np.outer(e, normal)
        direction = s5_of(m)
        direction /= np.linalg.norm(direction)
        assert np.linalg.norm(null @ direction) == pytest.approx(1.0, abs=1e-10)


def test_collinear_vectors_determine_one_component() -> None:
    """D12: collinear vectors fix only cᵀ S c."""
    c = np.array([1.0, 2.0, 2.0]) / 3.0
    positions = np.vstack([np.zeros(3), np.outer([2.0, 3.0, 4.5, 6.0], c)])
    design = design_rows(positions, tuple((0, i) for i in range(1, 5)), K_HH)
    s_true = np.array([[0.1, 0.03, -0.05], [0.03, -0.25, 0.08], [-0.05, 0.08, 0.15]])
    sol = solve_inner(design, design @ s5_of(s_true), np.ones(4))
    assert sol.rank == 1
    szz, delta, sxy, sxz, syz = sol.params
    s_fit = np.array([[(delta - szz) / 2, sxy, sxz], [sxy, (-delta - szz) / 2, syz], [sxz, syz, szz]])
    assert c @ s_fit @ c == pytest.approx(c @ s_true @ c, abs=1e-14)


# --------------------------------------------------------------------------- rank-changing path
def full_tensor_design(phi: float, pairs: tuple[tuple[int, int], ...]) -> Array:
    return design_rows(proton_positions(phi), pairs, K_HH)


def test_full_tensor_rank_changes_as_the_molecule_flattens() -> None:
    """With all five S components free, the planar molecule (φ = 0) gives rank 3: Sxy and Syz are
    unidentified (the molecular plane is xz). Approaching φ = 0 the condition number grows like
    1/φ, and the written rank policy then drops the rank monotonically to 3. Inside the
    tolerance the flag is honest: either the rank is full and the condition number shows the
    near-singularity, or the rank is reduced and no condition number is reported."""
    problem = Problem.from_fixture("noisy_fixture.json", "y_Hz", "sigma_Hz")
    phis = [10.0**-k for k in range(0, 13)] + [0.0]
    ranks, conds = [], []
    for phi in phis:
        sol = solve_inner(full_tensor_design(phi, problem.pairs), problem.y, problem.sigma)
        ranks.append(sol.rank)
        conds.append(sol.condition)
    assert ranks[0] == 5 and ranks[-1] == 3
    assert all(a >= b for a, b in itertools.pairwise(ranks)), ranks
    for rank, cond in zip(ranks, conds, strict=True):
        assert (rank == 5) == math.isfinite(cond)
    # Condition × φ is constant while the rank is full and φ is small (the smallest singular value is linear in φ).
    products = [c * p for c, p, r in zip(conds, phis, ranks, strict=True) if r == 5 and 1e-6 <= p <= 1e-2]
    assert len(products) >= 4 and max(products) / min(products) < 1.01, products
    # At φ = 0 the null space is exactly span{Sxy, Syz}.
    _, s, vt = np.linalg.svd(full_tensor_design(0.0, problem.pairs) / problem.sigma[:, None])
    assert s[3] < RANK_RTOL * s[0] and s[2] > 1e-3 * s[0]
    null = vt[3:]
    for name in ("Sxy", "Syz"):
        e = np.zeros(5)
        e[ORDER_BASIS.index(name)] = 1.0
        assert np.linalg.norm(null @ e) == pytest.approx(1.0, abs=1e-12)


def test_two_parameter_rigid_model_is_regular_on_its_domain() -> None:
    """The diagonal (Szz, Δ) model never changes rank on [0°, 90°]; its condition stays modest."""
    problem = Problem.from_fixture("noisy_fixture.json", "y_Hz", "sigma_Hz")
    sols = [solve_inner(rigid_design(float(p), problem.pairs), problem.y, problem.sigma) for p in GRID]
    assert all(s.rank == 2 for s in sols)
    assert max(s.condition for s in sols) < 10.0


# --------------------------------------------------------------------------- grid → refine vs the frozen fixture
@pytest.fixture(scope="module")
def noisy() -> tuple[Problem, dict[str, Any], dict[str, Any]]:
    problem = Problem.from_fixture("noisy_fixture.json", "y_Hz", "sigma_Hz")
    expected = json.loads((EXPECTED / "noisy_fixture.json").read_text())["expected"]
    return problem, fit(problem), expected


def test_grid_then_refine_reproduces_the_frozen_optimum(noisy: tuple[Problem, dict[str, Any], dict[str, Any]]) -> None:
    problem, result, exp = noisy
    sol = result["sol"]
    assert result["grid_best"] == exp["grid_best_deg"]
    assert abs(result["phi"] - exp["phi_deg"]) < TOL["phi_atol_deg"]
    assert abs(sol.params[0] - exp["Szz"]) < TOL["S_atol"]
    assert abs(sol.params[1] - exp["Delta"]) < TOL["S_atol"]
    np.testing.assert_allclose(sol.predictions, exp["predictions_Hz"], rtol=0, atol=TOL["predictions_atol_Hz"])
    assert sol.chi2 == pytest.approx(exp["objective"], rel=TOL["objective_rtol"])
    rms = math.sqrt(float(np.mean(sol.residuals**2)))
    assert rms == pytest.approx(exp["rms_Hz"], rel=1e-9)
    assert problem.y.size == exp["N"] and exp["p_free"] == 3 and exp["nu"] == exp["N"] - exp["p_free"]


def test_grid_reports_competing_basins(noisy: tuple[Problem, dict[str, Any], dict[str, Any]]) -> None:
    """D3.2: competing basins are reported, not hidden."""
    _, result, exp = noisy
    found = [(float(GRID[i]), float(result["grid_values"][i])) for i in result["grid_minima"]]
    want = [(m["phi_grid_deg"], m["chi2"]) for m in exp["grid_local_minima"]]
    assert [p for p, _ in found] == [p for p, _ in want]
    for (_, got), (_, ref) in zip(found, want, strict=True):
        assert got == pytest.approx(ref, rel=1e-9)


def test_full_fit_and_reduced_fit_agree(noisy: tuple[Problem, dict[str, Any], dict[str, Any]]) -> None:
    """D3.7: a bounded joint TRF fit over (φ, Szz, Δ), seeded from the grid best, lands on the
    VarPro (profile) optimum."""
    problem, result, _ = noisy
    seed_sol = solve_inner(rigid_design(result["grid_best"], problem.pairs), problem.y, problem.sigma)
    x0 = np.r_[result["grid_best"], seed_sol.params]
    joint = least_squares(
        problem.whitened_residual,
        x0,
        bounds=([0.0, -np.inf, -np.inf], [90.0, np.inf, np.inf]),
        method="trf",
        x_scale=np.array([1.0, 1e-3, 1e-3]),
        xtol=1e-15,
        ftol=1e-15,
        gtol=1e-15,
    )
    assert joint.status > 0
    assert abs(joint.x[0] - result["phi"]) < 1e-6
    np.testing.assert_allclose(joint.x[1:], result["sol"].params, atol=1e-8)
    assert 2 * joint.cost == pytest.approx(result["sol"].chi2, rel=1e-10)  # χ² = 2·cost (D3.3)


def test_full_jacobian_covariance_and_joint_rank(noisy: tuple[Problem, dict[str, Any], dict[str, Any]]) -> None:
    """D3.4/D3.5: covariance from the full whitened Jacobian in joint coordinates (known σ, not
    rescaled); joint rank reported separately from the inner rank."""
    problem, result, exp = noisy
    theta = np.r_[result["phi"], result["sol"].params]
    j = full_jacobian(problem, theta)
    s = np.linalg.svd(j, compute_uv=False)
    assert int(np.count_nonzero(s > RANK_RTOL * s[0])) == exp["validity"]["joint_rank"]
    assert result["sol"].rank == exp["validity"]["inner_rank"]
    assert result["sol"].condition == pytest.approx(exp["validity"]["inner_condition_number"], rel=1e-9)
    cov = np.linalg.inv(j.T @ j)
    stderr = np.sqrt(np.diag(cov))
    ref = exp["covariance_full_jacobian"]
    np.testing.assert_allclose(stderr, ref["stderr"], rtol=TOL["stderr_rtol"])
    np.testing.assert_allclose(cov / np.outer(stderr, stderr), ref["correlation"], atol=1e-6)


def test_profile_intervals_match_the_fixture(noisy: tuple[Problem, dict[str, Any], dict[str, Any]]) -> None:
    """D3.4: 68.3 % one-parameter profile intervals at raw Δχ² = 1.00, other parameters re-minimised."""
    problem, result, exp = noisy
    phi_hat: float = result["phi"]
    szz_hat, delta_hat = (float(v) for v in result["sol"].params)
    chi2_min: float = result["sol"].chi2
    ref = exp["profile_intervals_68pct"]
    assert ref["delta_chi2"] == 1.0

    def phi_excess(phi: float) -> float:
        return problem.profile(phi) - chi2_min - 1.0

    phi_interval = (root(phi_excess, phi_hat - 1.0, phi_hat), root(phi_excess, phi_hat, phi_hat + 1.0))
    np.testing.assert_allclose(phi_interval, ref["phi_deg"], atol=TOL["phi_interval_endpoint_atol_deg"])

    def order_profile(which: int, value: float) -> float:
        """χ² minimised over φ and the other order parameter with this one held at ``value``."""
        other = 1 - which

        def at_phi(phi: float) -> float:
            design = rigid_design(phi, problem.pairs)
            reduced = solve_inner(design[:, [other]], problem.y - design[:, which] * value, problem.sigma)
            return reduced.chi2

        res = minimize_scalar(at_phi, bounds=(phi_hat - 1.0, phi_hat + 1.0), method="bounded", options={"xatol": 1e-12})
        return float(res.fun)

    for which, name, hat in ((0, "Szz", szz_hat), (1, "Delta", delta_hat)):

        def excess(value: float, which: int = which) -> float:
            return order_profile(which, value) - chi2_min - 1.0

        width = 10 * exp["covariance_full_jacobian"]["stderr"][1 + which]
        interval = (root(excess, hat - width, hat), root(excess, hat, hat + width))
        np.testing.assert_allclose(interval, ref[name], atol=TOL["S_interval_endpoint_atol"])


def test_noiseless_recovery() -> None:
    """Gate (a): noiseless couplings computed in code recover the truth to 1e-8."""
    problem = Problem.from_fixture("noiseless.json", "D_Hz", "sigma_Hz")
    exp = json.loads((EXPECTED / "noiseless.json").read_text())["expected"]
    atol = SPEC["tolerances"]["noiseless_recovery_atol"]
    result = fit(problem)
    assert abs(result["phi"] - exp["phi_deg"]) < atol["phi_deg"]
    assert abs(result["sol"].params[0] - exp["Szz"]) < atol["Szz"]
    assert abs(result["sol"].params[1] - exp["Delta"]) < atol["Delta"]
    assert result["sol"].chi2 < 1e-12


def test_residual_vector_refinement_is_sharper_than_scalar_refinement() -> None:
    """Spike finding. A scalar minimiser of χ²(φ) resolves φ only to about √ε of the curvature
    scale: at a zero-residual optimum that is 1.5e-9°, inside the 1e-8° gate but with a thin margin.
    Refining the VarPro *residual vector* with bounded TRF (as D3.1 prescribes) recovers φ to
    rounding. M1 therefore refines with ``least_squares`` on residuals, not ``minimize_scalar``."""
    problem = Problem.from_fixture("noiseless.json", "D_Hz", "sigma_Hz")
    exp = json.loads((EXPECTED / "noiseless.json").read_text())["expected"]
    scalar = fit(problem)

    def reduced_residual(phi: Array) -> Array:
        sol = solve_inner(rigid_design(float(phi[0]), problem.pairs), problem.y, problem.sigma)
        return sol.residuals / problem.sigma

    vector = least_squares(
        reduced_residual,
        [scalar["grid_best"]],
        bounds=([0.0], [90.0]),
        method="trf",
        xtol=1e-15,
        ftol=1e-15,
        gtol=1e-15,
    )
    assert abs(vector.x[0] - exp["phi_deg"]) < 1e-12
    assert abs(vector.x[0] - exp["phi_deg"]) < abs(scalar["phi"] - exp["phi_deg"])
