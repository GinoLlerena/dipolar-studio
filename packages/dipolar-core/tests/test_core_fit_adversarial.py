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
    chi2, ok, _ = _profile_chi2(q, result, 0, 2.0, Settings())
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
    data = json.loads((EXPECTED / "noisy_fixture.json").read_text(encoding="utf-8"))
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
    y = np.array(json.loads((EXPECTED / "noisy_fixture.json").read_text(encoding="utf-8"))["y_Hz"])
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
    y = np.array(json.loads((EXPECTED / "noisy_fixture.json").read_text(encoding="utf-8"))["y_Hz"])
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
    """The certificate, tested directly: TRF claiming a tolerance stop (status 2) at a point where
    χ² can still clearly fall is not converged; at the true optimum it is."""
    from types import SimpleNamespace

    from dipolar_core.fit import _converged, _whole

    q = problem(lambda x: np.array([[1.0], [x[0]], [0.0]]), [1.0, 0.5, 0.0], [0.0], [1.0], sigma=[0.01] * 3)

    def claimed(x: float) -> SimpleNamespace:
        return SimpleNamespace(status=2, x=np.array([x]), active_mask=np.array([0]), message="`ftol` satisfied")

    ok, message = _converged(q, _whole(q), q.profile_residual, claimed(0.9), q.lower, q.upper, 1e-15)
    assert not ok and "non-stationary" in message
    assert _converged(q, _whole(q), q.profile_residual, claimed(0.5), q.lower, q.upper, 1e-15)[0]


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


@pytest.mark.parametrize("scale", [1e3, 1e5, 1e7])
def test_large_misfits_converge_and_stay_regular(scale: float) -> None:
    """The certificate differentiates the model, never the data, so its error grows like ‖r‖, not
    ‖r‖⁴ (round 14). At very large misfits the optimum is resolved to a Δχ² far below the interval
    scale, not to rounding."""
    a, b = np.array([1.0, 2.0, 3.0, 4.0]), np.array([2.0, -1.0, 0.5, 1.0])
    n = np.array([2.0, 0.0, 14.0, -11.0]) / np.sqrt(321.0)
    q = problem(lambda x: (a + x[0] * b)[:, None], list(a + scale * n), [-1.0], [1.0])
    result = fit(q)
    assert result.validity.converged and result.validity.regular and result.nu == 2
    excess = result.chi2 - q.inner(np.array([0.0])).chi2
    assert excess <= 1e-12 * scale**2 + 1e-9  # Δχ² from the exact optimum, at the χ² rounding scale


def test_a_nonlinear_fit_with_a_huge_misfit_is_finished() -> None:
    """Biphenyl couplings with a 1e6 σ misfit (χ² ≈ 6e13), interior optimum: the predicted
    reduction left (about 1e-4) exceeds DECREMENT_ATOL but lies below what TRF can resolve
    (tolerance·χ²), so the fit is finished, not unconverged."""
    pairs = biphenyl_pairs()
    y = np.array(json.loads((EXPECTED / "noisy_fixture.json").read_text(encoding="utf-8"))["y_Hz"])
    noisy = y + 1e6 * np.random.default_rng(6).normal(size=len(y))
    result = fit(rigid(pairs, noisy, None))
    assert result.chi2 > 1e13 and result.validity.at_bound == () and result.validity.converged


def test_the_varpro_jacobian_is_exact_golub_pereyra() -> None:
    """At a sizeable misfit the second Golub–Pereyra term matters; the Jacobian must equal the
    derivative of the profile residual (a careful central difference, trustworthy at this scale)."""
    from dipolar_core.fit import _varpro_jacobian, _whole

    pairs = biphenyl_pairs()
    y = np.array(json.loads((EXPECTED / "noisy_fixture.json").read_text(encoding="utf-8"))["y_Hz"])
    q = rigid(pairs, y + 300.0 * np.random.default_rng(1).normal(size=len(y)), None)
    for phi in (20.0, 37.0, 60.0):
        x = np.array([phi])
        _, jac, _, _ = _varpro_jacobian(q, _whole(q), x, q.lower, q.upper)
        h = 1e-4
        reference = (q.profile_residual(x + h) - q.profile_residual(x - h)) / (2 * h)
        assert np.linalg.norm(jac[:, 0] - reference) <= 1e-6 * np.linalg.norm(reference)


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


# --------------------------------------------------------------------------- validation round 14
def test_a_narrow_bound_range_is_differentiable() -> None:
    """Bounds [0, 1e-5]: the default scan starts on a bound where no fixed-step stencil fits."""
    q = problem(lambda x: np.array([[1.0], [x[0]], [0.0]]), [1.0, 5e-6, 0.0], [0.0], [1e-5])
    result = fit(q)
    assert result.theta[0] == pytest.approx(5e-6, abs=1e-15) and result.validity.regular


def test_an_exact_optimum_with_a_large_misfit_is_converged() -> None:
    """y = a + 1000 n with n ⟂ a, b: the optimum is exactly x = 0, t = 1, χ² = 1e6, ν = 2. A poor
    fit is not a failed fit: convergence and adequacy are separate (D3.5)."""
    a, b = np.array([1.0, 2.0, 3.0, 4.0]), np.array([2.0, -1.0, 0.5, 1.0])
    n = np.array([2.0, 0.0, 14.0, -11.0]) / np.sqrt(321.0)
    q = problem(lambda x: (a + x[0] * b)[:, None], list(a + 1000 * n), [-1.0], [1.0])
    result = fit(q)
    assert result.validity.converged and result.validity.regular and result.nu == 2
    # The position the convergence certificate guarantees (``_converged``): χ² resolved to
    # DECREMENT_ATOL + ATTAINABLE_FACTOR·tolerance·χ², and χ² rises by |b⊥|²·x² from the optimum,
    # where b⊥ is b's part orthogonal to a. A fixed 1e-9 held on one BLAS and not on Windows' (small
    # batch); the certificate's bound holds on every platform.
    from dipolar_core.fit import ATTAINABLE_FACTOR, DECREMENT_ATOL, Settings

    b_perp = b - (a @ b) / (a @ a) * a
    resolution = DECREMENT_ATOL + ATTAINABLE_FACTOR * Settings().tolerance * 1e6
    assert result.chi2 == pytest.approx(1e6, rel=1e-12)
    assert abs(result.theta[0]) <= np.sqrt(resolution / (b_perp @ b_perp))
    assert result.p_value is not None and result.p_value < 1e-100  # adequacy says "inadequate", separately


def test_a_bound_is_binding_only_if_the_gradient_points_outward() -> None:
    """KKT: TRF stopping at x ≈ 0 with the gradient pointing into the domain is not an optimum."""
    inward = problem(lambda x: np.array([[1.0], [x[0]], [0.0]]), [1.0, 0.5, 0.0], [0.0], [1.0], sigma=[0.1] * 3)
    stuck = fit(inward, Settings(grid=np.array([0.0]), tolerance=1e-8))
    assert stuck.basins == () and not stuck.validity.converged and not stuck.validity.regular
    # The genuine bound optimum (data pull below the bound) is accepted, and flagged as at the bound.
    outward = problem(lambda x: np.array([[1.0], [x[0]], [0.0]]), [1.0, -0.5, 0.0], [0.0], [1.0], sigma=[0.1] * 3)
    pinned = fit(outward)
    assert pinned.validity.converged and pinned.validity.at_bound == ("x0",) and not pinned.validity.regular
    assert pinned.theta[0] == pytest.approx(0.0, abs=1e-9)


def test_basins_inside_the_interval_do_not_split_the_region() -> None:
    """Two minima at (0, ±1) differ only in the nuisance parameter: the x profile's level set is one
    interval, ±1/√99.99."""
    q = problem(
        lambda z: np.array([[100.0], [10 * z[0]], [0.5 * (z[1] ** 2 - 1)], [0.0]]),
        [100.0, 0.0, 0.0, 0.0],
        [-3.0, -2.0],
        [3.0, 2.0],
    )
    result = fit(q)
    assert len(result.basins) == 2
    interval = profile_interval(q, result, "x0")
    assert interval.supported
    np.testing.assert_allclose([interval.lower, interval.upper], [-1 / np.sqrt(99.99), 1 / np.sqrt(99.99)], atol=1e-9)


def test_a_tall_problem_does_not_allocate_n_by_n() -> None:
    import tracemalloc

    rng = np.random.default_rng(3)
    n = 3000
    base, slope = rng.normal(size=n), rng.normal(size=n)
    q = problem(lambda x: (base + x[0] * slope)[:, None], list(base + 0.3 * slope), [-1.0], [1.0])
    tracemalloc.start()
    fit(q, Settings(grid=np.array([0.0, 0.5])))
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    assert peak < 20 * 2**20, f"peak {peak / 2**20:.1f} MiB"  # an N × N float64 matrix would be 69 MiB


# --------------------------------------------------------------------------- validation round 15
def test_the_full_jacobian_never_differences_the_data() -> None:
    """At a stationary point the geometry column is exactly zero whatever the data. Differencing
    the residual (which holds −W·y) invented a joint rank of 2 and a finite error bar."""
    c = 1e-7

    def design(x: Array) -> Array:
        return np.array([[1.0], [(x[0] - c) ** 2], [0.0]])

    columns = []
    for y in ([1.0, 0.0, 0.0], [1.0, -10.0, 0.0], [1.0, -1e6, 0.0]):
        q = problem(design, y, [0.0], [0.1])
        columns.append(full_jacobian(q, np.array([c]), np.array([1.0]))[:, 0])
    assert all(np.array_equal(columns[0], col) for col in columns[1:])  # independent of y
    q = problem(design, [1.0, -10.0, 0.0], [0.0], [0.1])
    result = fit(q, Settings(grid=np.array([c])))
    assert result.validity.joint_rank == 1 and not result.validity.regular
    assert result.covariance is None and result.nu is None and result.p_value is None
    assert len(result.unidentified) == 1 and abs(result.unidentified[0]["x0"]) == pytest.approx(1.0, abs=1e-9)


def test_a_barrier_between_the_estimate_and_a_rival_is_not_hidden() -> None:
    """Two zero-cost basins at x = 0 and 0.75 separated by a narrow barrier at 0.375 (χ² ≈ 4.8):
    the Δχ² = 1 region has two components, so no single interval may be reported."""

    def g(x: float) -> float:
        return x * (0.75 - x) / 0.75 + 2.0 * np.exp(-(((x - 0.375) / 0.025) ** 2))

    q = problem(lambda x: np.array([[100.0], [g(float(x[0]))], [0.0]]), [100.0, 0.0, 0.0], [-2.0], [2.0])
    result = fit(q)
    assert sorted(round(float(b.theta[0]), 6) for b in result.basins)[:2] == [0.0, 0.75]
    assert q.inner(np.array([0.375])).chi2 > 4.0
    interval = profile_interval(q, result, "x0")
    assert not interval.supported and "several components" in interval.note
    # Even when the search never finds the second basin, the interval is verified before it is
    # accepted, so the barrier is seen.
    alone = fit(q, Settings(grid=np.array([0.0])))
    assert len(alone.basins) == 1
    blind = profile_interval(q, alone, "x0")
    assert not blind.supported and "gap" in blind.note


def test_a_lower_failed_nuisance_trial_makes_the_profile_unresolved() -> None:
    """With a starved budget one nuisance trial stops early *below* the converged one; the
    converged value is then disproved, so the profile point is unresolved, never reported."""
    from dipolar_core.fit import _profile_chi2

    q = problem(
        lambda x: np.array([[100.0], [2 * (x[1] ** 2 - 1)], [x[0] - (x[1] + 1)], [0.1 * (x[1] + 1)]]),
        [100.0, 0.0, 0.0, 0.0],
        [-1.0, -2.0],
        [3.0, 2.0],
    )
    result = fit(q)
    full, ok_full, _ = _profile_chi2(q, result, 0, 0.75, Settings())
    assert ok_full
    starved, ok, _ = _profile_chi2(q, result, 0, 0.75, Settings(max_nfev=10))
    assert (not ok) or starved <= full + 1e-6  # never a converged value that a failed run beats


def test_a_noisy_zero_gradient_at_a_bound_is_binding() -> None:
    """D = a + 0.01 x² n, y = a − 100 n: the optimum is on the bound x = 0 with an exactly zero
    gradient there. Rounding gives a tiny inward gradient; it must not count as a large reduction."""
    a = np.array([1.0, 2.0, 3.0])
    n = np.array([-1.0, 2.0, -1.0]) / np.sqrt(6.0)
    q = problem(lambda x: (a + 0.01 * x[0] ** 2 * n)[:, None], list(a - 100 * n), [0.0], [1.0])
    result = fit(q)
    assert result.validity.converged and result.validity.at_bound == ("x0",)
    assert result.theta[0] == pytest.approx(0.0, abs=1e-6)
    assert result.chi2 == pytest.approx(q.inner(np.array([0.0])).chi2, rel=1e-12)


# --------------------------------------------------------------------------- validation round 16
@pytest.mark.parametrize("grid", [None, np.array([0.0])])
def test_truncation_error_never_invents_a_joint_rank(grid: Array | None) -> None:
    """D = (1, 3x³, 0): the derivative at the optimum x = 0 is exactly 0, so the joint rank is 1.
    A plain central difference gives 3h² ≈ 1e-10, enough to look like information."""
    q = problem(lambda x: np.array([[1.0], [3 * x[0] ** 3], [0.0]]), [10.0, 0.0, 0.0], [-1.0], [1.0])
    result = fit(q, Settings(grid=grid))
    assert result.theta[0] == pytest.approx(0.0, abs=1e-6)
    assert result.validity.joint_rank == 1 and not result.validity.regular
    assert result.covariance is None and result.nu is None and result.p_value is None
    assert not profile_interval(q, result, "x0").supported


@pytest.mark.parametrize(
    ("y", "sigma", "upper"),
    [([1.0, 1.0, 0.0], [1.0] * 3, 90.0), ([1.0, 1e-9, 0.0], [1e-9] * 3, 10.0)],
)
def test_a_small_genuine_inward_gradient_is_not_mistaken_for_noise(
    y: list[float], sigma: list[float], upper: float
) -> None:
    """D = (1, 3e-10 x, 0): at the bound x = 0 the gradient is small but real, and moving inward
    lowers χ² (to zero with precise data). A stop at the bound must not be certified."""
    q = problem(lambda x: np.array([[1.0], [3e-10 * x[0]], [0.0]]), y, [0.0], [upper], sigma=sigma)
    result = fit(q, Settings(grid=np.array([0.0]), tolerance=1e-8))
    best_possible = min(q.inner(np.array([v])).chi2 for v in np.linspace(0.0, upper, 201))
    if result.validity.converged:
        assert result.chi2 <= best_possible + 1e-6
    else:
        assert result.basins == () and not result.validity.regular


def test_coupled_bound_moves_are_seen() -> None:
    """D = (1, 1e5 (x − z), x + z): at (0, 0) each coordinate alone barely helps, but moving both
    together lowers χ² from 1 to 0. A stop at (0, 0) must not be certified."""
    from dipolar_core.fit import _refine

    q = problem(
        lambda x: np.array([[1.0], [1e5 * (x[0] - x[1])], [x[0] + x[1]]]),
        [1.0, 0.0, 1.0],
        [0.0, 0.0],
        [1.0, 1.0],
    )
    trial = _refine(q, np.array([0.0, 0.0]), Settings(tolerance=1e-8))
    assert (not trial.converged) or trial.chi2 < 1e-6


def test_named_null_directions_are_the_numerical_basis() -> None:
    """Order columns a and 5e-10·a with |a| ~ 1e9: the null direction (−5e-10, 1) must be kept as
    computed. Rounding it to (0, 1) is no longer a null direction (‖J v‖ ≈ 1.9)."""
    a = 1e9 * np.array([1.0, 2.0, 3.0])
    q = Problem(
        design=lambda x: np.column_stack([a, 5e-10 * a]),
        y=a.copy(),
        sigma=np.ones(3),
        lower=np.array([0.0]),
        upper=np.array([1.0]),
        theta_names=("x0",),
        order_names=("t0", "t1"),
    )
    result = fit(q, Settings(grid=np.array([0.5])))
    j = full_jacobian(q, result.theta, result.order)
    assert len(result.unidentified) == result.p_free - result.validity.joint_rank == 2
    for direction in result.unidentified:
        v = np.array([direction[n] for n in result.names])
        assert np.linalg.norm(j @ v) <= 1e-6 * np.linalg.norm(j)


def test_a_singular_value_inside_the_jacobian_error_is_not_rank() -> None:
    """The trust rule itself: a singular value no larger than the Jacobian's own error estimate
    carries no information, whatever the rank policy alone would say."""
    from dipolar_core.fit import _rank_split

    j = np.array([[0.0, 1.0], [1e-9, 0.0], [0.0, 0.0]])  # geometry column, then an order column
    assert _rank_split(j, np.zeros((3, 2)), 1, 1)[0] == 2  # no error: the rank policy decides
    assert _rank_split(j, np.full((3, 2), 1e-9), 1, 1)[0] == 1  # inside the error: not information


def test_an_unverifiable_prediction_is_not_certified() -> None:
    """D = (1, 1e-9 sin(1e9 x), 0): the wiggle is far below the differencing step, so every stencil
    aliases it alike and the derivative's error estimate stays small. The linear model then
    promises a reduction that no step delivers and the estimate cannot explain. That point is not
    certified (round 17): failed trials alone prove nothing."""
    from types import SimpleNamespace

    from dipolar_core.fit import _converged, _whole

    q = problem(lambda x: np.array([[1.0], [1e-9 * np.sin(1e9 * x[0])], [0.0]]), [1.0, 1e-3, 0.0], [0.0], [1.0])
    claimed = SimpleNamespace(status=2, x=np.array([0.5]), active_mask=np.array([0]), message="`xtol` satisfied")
    ok, message = _converged(q, _whole(q), q.profile_residual, claimed, q.lower, q.upper, 1e-15)
    assert not ok and "could not be realised or explained" in message


def test_a_prediction_explained_by_derivative_error_is_noise() -> None:
    """D = (1, 1e-3 + c·max(x − ½, 0)^1.5, 0): at the weak minimum x = ½ the central difference
    gives c·h^0.5/2, and Richardson cannot remove an h^0.5 error, so the error estimate is as large
    as the derivative. The prediction it drives is explained by that error, and no step lowers χ²:
    the point is certified."""
    from types import SimpleNamespace

    from dipolar_core.fit import _converged, _whole

    q = problem(lambda x: np.array([[1.0], [1e-3 + max(x[0] - 0.5, 0.0) ** 1.5], [0.0]]), [1.0, 0.0, 0.0], [0.0], [1.0])
    claimed = SimpleNamespace(status=2, x=np.array([0.5]), active_mask=np.array([0]), message="`xtol` satisfied")
    ok, message = _converged(q, _whole(q), q.profile_residual, claimed, q.lower, q.upper, 1e-15)
    assert ok and "derivative noise" in message


def test_another_direction_is_tried_when_the_joint_step_fails() -> None:
    """D = (100, 1e-6 x, 1e-7 z, z², 0), y = (100, 1, 1, 0, 0): the joint Gauss–Newton step is
    useless (the z² term), but moving x alone halves χ². A stop at (0, 0) is not certified."""
    from dipolar_core.fit import _refine

    q = problem(
        lambda x: np.array([[100.0], [1e-6 * x[0]], [1e-7 * x[1]], [x[1] ** 2], [0.0]]),
        [100.0, 1.0, 1.0, 0.0, 0.0],
        [0.0, 0.0],
        [2e6, 2e7],
    )
    trial = _refine(q, np.array([0.0, 0.0]), Settings())
    assert (not trial.converged) or trial.chi2 <= 1.0 + 1e-6


def test_exact_order_columns_keep_their_rank_and_derivatives_are_refined() -> None:
    """D = (1, x + 1e10 x³, 0) at x = 0: J = [[0, 1], [1, 0], [0, 0]], rank 2 and condition 1. The
    cubic term made the error estimate of a two-step extrapolation large enough to erase both
    directions; the three-step estimate resolves it."""
    q = problem(lambda x: np.array([[1.0], [x[0] + 1e10 * x[0] ** 3], [0.0]]), [1.0, 0.0, 0.0], [-1.0], [1.0])
    result = fit(q, Settings(grid=np.array([0.0])))
    assert result.validity.joint_rank == 2 and result.validity.derivatives_resolved
    assert result.unidentified == () and result.uncertain == ()
    assert result.validity.regular and result.covariance is not None


def test_the_joint_rank_never_drops_below_the_inner_rank() -> None:
    from dipolar_core.fit import _rank_split

    j = np.array([[1.0, 0.0], [0.0, 1.0], [0.0, 0.0]])
    assert _rank_split(j, np.full((3, 2), 1.0), 1, floor=1) == (1, 2)  # uncertain, not unidentified
    assert _rank_split(j, np.zeros((3, 2)), 1, floor=1) == (2, 2)


def test_a_geometry_column_inside_the_order_span_adds_no_trusted_rank() -> None:
    """Round 20: only the geometry's information *beyond* the order columns is judged. Here the
    geometry column nearly repeats the order column. Its distinguishing part (1e-9) lies inside its
    error estimate, so it adds no trusted rank, although the column itself is large."""
    from dipolar_core.fit import _rank_split

    j = np.array([[1.0, 1.0], [1e-9, 0.0], [0.0, 0.0]])  # geometry column, then an order column
    assert _rank_split(j, np.full((3, 2), 1e-9), 1, floor=1) == (1, 2)  # uncertain, not information
    assert _rank_split(j, np.zeros((3, 2)), 1, floor=1) == (2, 2)


# --------------------------------------------------------------------------- interval warm starts
def test_warm_starts_never_let_a_basin_track_collapse_into_another() -> None:
    """A start slot that ended where an earlier slot ended restarts from its own basin, so every
    basin is still searched; distinct slots continue from where they were."""
    from dipolar_core.fit import _continued

    origins = [np.array([0.0]), np.array([10.0]), np.array([20.0])]
    previous = [np.array([1.0]), np.array([1.0 + 1e-9]), np.array([19.0])]
    starts = _continued(previous, origins)
    assert starts[0] is previous[0] and starts[2] is previous[2]
    assert starts[1] is origins[1]  # merged into slot 0's valley: back to its basin
