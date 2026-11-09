"""Adversarial controls for the D3 stack: the validation round 13 counterexamples, kept as tests.

Each test names the round-13 finding it guards. The problems are small synthetic models whose
right answer is known in closed form.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest
from dipolar_core.biphenyl import PROTON_LABELS, proton_positions, rigid_design
from dipolar_core.fit import Problem, Settings, coverage_label, fit, full_jacobian, profile_interval, scan
from dipolar_core.forward import design_rows
from dipolar_core.nuclides import dipolar_constant_hz_a3
from scipy.optimize import brentq

Array = np.ndarray
EXPECTED = Path(__file__).resolve().parents[3] / "datasets" / "biphenyl-synthetic" / "expected"


def problem(
    design: Callable[[Array], Array],
    y: list[float],
    lower: list[float],
    upper: list[float],
    p: int = 1,
    sigma: list[float] | None = None,
) -> Problem:
    return Problem(
        design=design,
        y=np.array(y, dtype=float),
        sigma=np.ones(len(y)) if sigma is None else np.array(sigma, dtype=float),
        lower=np.array(lower, dtype=float),
        upper=np.array(upper, dtype=float),
        theta_names=tuple(f"x{i}" for i in range(len(lower))),
        order_names=tuple(f"t{i}" for i in range(p)),
    )


# --------------------------------------------------------------------------- finding 1: derivatives
def test_a_stationary_point_near_a_bound_has_a_zero_derivative() -> None:
    """D = [1, (θ − c)², 0]ᵀ with c = 1e-7 just inside the bound: ∂r/∂θ = 0 at θ = c. An
    off-centre secant invented a derivative, a full joint rank and a finite error bar."""
    c = 1e-7
    q = problem(lambda x: np.array([[1.0], [(x[0] - c) ** 2], [0.0]]), [1.0, 0.0, 0.0], [0.0], [1.0])
    result = fit(q, Settings(grid=np.array([c])))
    j = full_jacobian(q, result.theta, result.order)
    assert abs(j[1, 0]) < 1e-9
    assert result.validity.joint_rank == 1 and not result.validity.regular and result.covariance is None


def test_one_sided_stencil_on_a_bound_is_second_order() -> None:
    q = problem(lambda x: np.array([[1.0], [x[0] ** 2 + x[0]], [0.0]]), [1.0, 0.0, 0.0], [0.0], [1.0])
    j = full_jacobian(q, np.array([0.0]), np.array([1.0]))  # exactly on the lower bound
    assert j[1, 0] == pytest.approx(1.0, abs=1e-9)  # d/dθ (θ² + θ) at 0, exact for a quadratic


# --------------------------------------------------------------------------- findings 2 and 3: interval topology
def test_a_skipped_crossing_is_found() -> None:
    """D = [100, 0.1θ + 5 sin²(πθ), 0]ᵀ: the Gauss–Newton step is 10, but the first crossing is at
    0.146. Endpoint doubling alone stepped over it."""
    q = problem(
        lambda x: np.array([[100.0], [0.1 * x[0] + 5 * np.sin(np.pi * x[0]) ** 2], [0.0]]),
        [100.0, 0.0, 0.0],
        [-20.0],
        [20.0],
    )
    first = brentq(lambda v: q.inner(np.array([v])).chi2 - 1.0, 0.0, 0.5)
    local = profile_interval(q, fit(q, Settings(grid=np.array([0.0]))), "x0")
    assert local.upper == pytest.approx(first, abs=1e-9)
    # With the default search the other basins (near every integer) are found, so the region is
    # known to have several components and no interval is claimed.
    default = profile_interval(q, fit(q), "x0")
    assert not default.supported and "another basin" in default.note


def test_two_equal_modes_get_no_single_interval() -> None:
    q = problem(lambda x: np.array([[100.0], [10 * (x[0] ** 2 - 1)], [0.0]]), [100.0, 0.0, 0.0], [-2.0], [2.0])
    result = fit(q)
    assert sorted(round(float(b.theta[0]), 6) for b in result.basins) == [-1.0, 1.0]
    interval = profile_interval(q, result, "x0")
    assert not interval.supported and "several components" in interval.note


def test_nuisance_profiles_search_every_basin() -> None:
    """At fixed x0 = 2 the nuisance x1 must reach its other basin (x1 = 1, χ² ≈ 0.04)."""
    from dipolar_core.fit import _profile_chi2

    q = problem(
        lambda x: np.array([[100.0], [10 * (x[1] ** 2 - 1)], [x[0] - (x[1] + 1)], [0.1 * (x[1] + 1)]]),
        [100.0, 0.0, 0.0, 0.0],
        [-1.0, -2.0],
        [3.0, 2.0],
    )
    result = fit(q)
    assert len(result.basins) == 2
    chi2, ok = _profile_chi2(q, result, 0, 2.0, Settings())
    assert ok and chi2 == pytest.approx(q.inner(np.array([2.0, 1.0])).chi2, abs=1e-5)
    assert not profile_interval(q, result, "x0").supported


# --------------------------------------------------------------------------- finding 4: failed re-minimizations
def test_a_failed_nuisance_fit_never_yields_an_interval() -> None:
    q = problem(lambda x: np.array([[1.0], [np.exp(x[0])], [0.0]]), [1.0, 1.0, 0.0], [-2.0], [2.0], sigma=[0.1] * 3)
    result = fit(q)
    starved = profile_interval(q, result, "t0", settings=Settings(max_nfev=1))
    assert not starved.supported and "did not converge" in starved.note
    adequate = profile_interval(q, result, "t0")
    assert adequate.supported
    np.testing.assert_allclose([adequate.lower, adequate.upper], [0.9, 1.1], rtol=0, atol=1e-9)


# --------------------------------------------------------------------------- finding 5: the null space
def test_every_unidentified_direction_is_named_when_n_is_below_p() -> None:
    q = problem(lambda x: np.array([[1.0, 0.0], [x[0], 1.0]]), [1.0, 0.5], [-1.0], [1.0], p=2)
    result = fit(q, Settings(grid=np.array([0.25])))
    assert result.validity.joint_rank == 2 and result.p_free == 3
    assert len(result.unidentified) == result.p_free - result.validity.joint_rank == 1
    assert result.covariance is None and result.nu is None


# --------------------------------------------------------------------------- finding 6: full Σ
def biphenyl_pairs() -> tuple[tuple[int, int], ...]:
    data = json.loads((EXPECTED / "noisy_fixture.json").read_text())
    index = {label: i for i, label in enumerate(PROTON_LABELS)}
    return tuple((index[a], index[b]) for a, b in data["pairs"])


def correlated_covariance(n: int, sigma: float = 0.5, rho: float = 0.6) -> Array:
    """AR(1)-correlated errors: Σᵢⱼ = σ² ρ^|i−j|, positive definite."""
    idx = np.arange(n)
    return sigma**2 * rho ** np.abs(idx[:, None] - idx[None, :])


def rigid(pairs: tuple[tuple[int, int], ...], y: Array, cov: Array | None) -> Problem:
    sigma = np.sqrt(np.diag(cov)) if cov is not None else np.full(len(y), 0.5)
    return Problem(
        design=lambda theta: rigid_design(float(theta[0]), pairs),
        y=y,
        sigma=sigma,
        lower=np.array([0.0]),
        upper=np.array([90.0]),
        theta_names=("phi_deg",),
        order_names=("Szz", "Delta"),
        covariance=cov,
    )


def test_a_diagonal_covariance_matrix_equals_the_sigma_vector() -> None:
    pairs = biphenyl_pairs()
    y = np.array(json.loads((EXPECTED / "noisy_fixture.json").read_text())["y_Hz"])
    plain, full = fit(rigid(pairs, y, None)), fit(rigid(pairs, y, np.diag(np.full(len(y), 0.25))))
    np.testing.assert_allclose(full.theta, plain.theta, rtol=0, atol=1e-10)
    np.testing.assert_allclose(full.order, plain.order, rtol=0, atol=1e-12)
    assert full.chi2 == pytest.approx(plain.chi2, rel=1e-12)
    assert full.covariance is not None and plain.covariance is not None
    np.testing.assert_allclose(full.covariance.matrix, plain.covariance.matrix, rtol=1e-8)


def test_correlated_errors_match_closed_form_generalized_least_squares() -> None:
    """Independent check with Σ⁻¹ applied by np.linalg.solve: at the fitted φ, the order
    parameters and χ² are the GLS solution, and the joint covariance is (Jᵀ Σ⁻¹ J)⁻¹."""
    pairs = biphenyl_pairs()
    rng = np.random.default_rng(7)
    cov = correlated_covariance(len(pairs))
    truth = rigid_design(37.0, pairs) @ np.array([0.25, 0.03])
    y = truth + np.linalg.cholesky(cov) @ rng.normal(size=len(pairs))
    q = rigid(pairs, y, cov)
    result = fit(q)
    d = rigid_design(float(result.theta[0]), pairs)
    t_gls = np.linalg.solve(d.T @ np.linalg.solve(cov, d), d.T @ np.linalg.solve(cov, y))
    r = y - d @ t_gls
    np.testing.assert_allclose(result.order, t_gls, rtol=0, atol=1e-12)
    assert result.chi2 == pytest.approx(float(r @ np.linalg.solve(cov, r)), rel=1e-10)
    h = 1e-6
    dphi = (rigid_design(result.theta[0] + h, pairs) - rigid_design(result.theta[0] - h, pairs)) @ t_gls / (2 * h)
    j_raw = np.column_stack([dphi, d])
    expected = np.linalg.inv(j_raw.T @ np.linalg.solve(cov, j_raw))
    assert result.covariance is not None
    np.testing.assert_allclose(result.covariance.matrix, expected, rtol=1e-5)
    plain = fit(rigid(pairs, y, None))  # ignoring the correlation gives a different answer
    assert abs(plain.theta[0] - result.theta[0]) > 1e-4


@pytest.mark.parametrize(
    ("make", "message"),
    [
        (lambda n: correlated_covariance(n) + np.triu(np.full((n, n), 1e-3), 1), "symmetric"),
        (lambda n: np.eye(n), "sigma must equal"),  # variance 1, but sigma says 0.5
        (lambda n: np.diag(np.r_[np.full(n - 1, 0.25), -0.25]), "diagonal must be positive"),
        (lambda n: 0.25 * np.ones((n, n)), "positive definite"),
    ],
)
def test_covariance_validation(make: Callable[[int], Array], message: str) -> None:
    pairs = biphenyl_pairs()
    cov = make(len(pairs))
    with pytest.raises(ValueError, match=message):
        Problem(
            design=lambda theta: rigid_design(float(theta[0]), pairs),
            y=np.zeros(len(pairs)),
            sigma=np.full(len(pairs), 0.5),
            lower=np.array([0.0]),
            upper=np.array([90.0]),
            theta_names=("phi_deg",),
            order_names=("Szz", "Delta"),
            covariance=cov,
        )


# --------------------------------------------------------------------------- finding 7: pointwise diagnostics
def test_scan_points_carry_their_own_diagnostics() -> None:
    """The full five-component tensor loses rank at the planar point φ = 0 (M0 spike 1)."""
    pairs = biphenyl_pairs()
    k = dipolar_constant_hz_a3("1H", "1H")
    y = np.array(json.loads((EXPECTED / "noisy_fixture.json").read_text())["y_Hz"])
    q = Problem(
        design=lambda theta: design_rows(proton_positions(float(theta[0])), pairs, k),
        y=y,
        sigma=np.full(len(y), 0.5),
        lower=np.array([0.0]),
        upper=np.array([90.0]),
        theta_names=("phi_deg",),
        order_names=("Szz", "Sxx-Syy", "Sxy", "Sxz", "Syz"),
        s5_map=np.eye(5),
    )
    sc = scan(q, Settings(grid=np.array([0.0, 10.0, 37.0])))
    assert sc.inner_rank.tolist() == [3, 5, 5]
    assert np.isinf(sc.inner_condition[0]) and np.all(np.isfinite(sc.inner_condition[1:]))
    assert sc.joint_rank[0] < 6 and sc.admissible is not None and sc.admissible.shape == (3,)


# --------------------------------------------------------------------------- finding 8: diverse starts
def test_a_narrow_lower_well_is_not_hidden() -> None:
    """Two wells in x: a broad one (χ² ≈ 1) and a narrow, deeper one near x = 0.8. The starts must
    reach the narrow well. If its refinement cannot converge, it is reported as unfinished, the
    search is unresolved, and no ν, p-value or interval is claimed."""

    def design(x: Array) -> Array:
        v1 = 1 + 100 * (x[0] - 0.25) ** 2
        v2 = 2 + 100 * (x[0] - 0.8) ** 2 - 1.9 * np.exp(-(((x[0] - 0.8) / 0.0001) ** 2))
        v = -np.logaddexp(-50 * v1, -50 * v2) / 50
        return np.array([[100.0], [np.sqrt(v)], [0.1 * (x[1] - 0.5)], [0.0]])

    q = problem(design, [100.0, 0.0, 0.0, 0.0], [0.0, 0.0], [1.0, 1.0])
    result = fit(q)
    starts = result.scan.points[list(result.scan.starts)]
    assert np.any(np.abs(starts[:, 0] - 0.8) < 0.05)  # the narrow well was among the starts
    lowest = min([b.chi2 for b in result.basins] + [u.chi2 for u in result.unfinished])
    assert lowest < 0.2  # it was found
    if result.chi2 > lowest:  # found but not refined to convergence: say so
        assert not result.validity.search_resolved and not result.validity.regular
        assert result.nu is None and result.p_value is None


def test_a_stop_at_a_non_stationary_point_is_not_convergence() -> None:
    """TRF reports ftol convergence inside the narrow well, where the gradient is still large; the
    predicted Gauss–Newton reduction exposes it."""
    from dipolar_core.fit import _refine

    def design(x: Array) -> Array:
        v1 = 1 + 100 * (x[0] - 0.25) ** 2
        v2 = 2 + 100 * (x[0] - 0.8) ** 2 - 1.9 * np.exp(-(((x[0] - 0.8) / 0.0001) ** 2))
        v = -np.logaddexp(-50 * v1, -50 * v2) / 50
        return np.array([[100.0], [np.sqrt(v)], [0.1 * (x[1] - 0.5)], [0.0]])

    q = problem(design, [100.0, 0.0, 0.0, 0.0], [0.0, 0.0], [1.0, 1.0])
    trial = _refine(q, np.array([0.80192721, 0.75542786]), Settings())
    assert not trial.converged and "non-stationary" in trial.message


# --------------------------------------------------------------------------- finding 9: bounds on their own scale
def test_a_far_bound_does_not_make_the_optimum_a_boundary_point() -> None:
    q = problem(lambda x: np.array([[1.0], [x[0]], [0.0]]), [1.0, 0.5, 0.0], [0.0], [1e9], sigma=[0.01] * 3)
    result = fit(q, Settings(grid=np.array([0.5])))
    assert result.validity.at_bound == () and result.validity.regular


# --------------------------------------------------------------------------- findings 10 and 11: labels and inputs
def test_labels_state_one_parameter_coverage() -> None:
    assert coverage_label(1.0) == "68.3% one-parameter (Δχ² = 1)"
    assert coverage_label(3.84) == "95.0% one-parameter (Δχ² = 3.84)"
    assert coverage_label(2.3) == "87.1% one-parameter (Δχ² = 2.3)"  # not a joint two-parameter region
    assert coverage_label(float(np.float32(3.84))).startswith("95.0%")


@pytest.mark.parametrize("threshold", [0.0, -1.0, float("nan"), float("inf")])
def test_thresholds_must_be_positive_and_finite(threshold: float) -> None:
    q = problem(lambda x: np.array([[1.0], [x[0]], [0.0]]), [1.0, 0.25, 0.0], [-1.0], [1.0], sigma=[0.01] * 3)
    result = fit(q)
    with pytest.raises(ValueError, match="positive and finite"):
        profile_interval(q, result, "x0", threshold)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"grid": np.array([])},
        {"grid": np.array([0.5, np.nan])},
        {"grid": np.array([1.0, 0.0])},
        {"grid": np.array([0.5, 0.5])},
        {"n_starts": 0},
        {"n_sobol": 3},
        {"tolerance": 0.0},
        {"max_nfev": 0},
    ],
)
def test_settings_are_validated(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        Settings(**kwargs)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- finding 12: the default grid
def test_the_default_grid_spacing_is_at_most_half_a_unit() -> None:
    q = problem(lambda x: np.array([[1.0], [x[0]], [0.0]]), [1.0, 0.25, 0.0], [0.0], [90.1])
    points = scan(q, Settings()).points[:, 0]
    assert np.max(np.diff(points)) <= 0.5 and points[0] == 0.0 and points[-1] == 90.1
    biphenyl = problem(lambda x: np.array([[1.0], [x[0]], [0.0]]), [1.0, 0.25, 0.0], [0.0], [90.0])
    np.testing.assert_allclose(np.diff(scan(biphenyl, Settings()).points[:, 0]), 0.5)  # the frozen convention
