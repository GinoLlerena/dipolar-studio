"""The D3 stack (M1 step 1) against the frozen fixtures and the D3 controls (plan §3 D3, ADR-0003).

The expected values come from ``tools/reference/`` (independent NumPy/SciPy code) and are frozen
in ``datasets/biphenyl-synthetic/expected/``. The tolerances are the frozen ones in ``spec.json``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from dipolar_core.biphenyl import PROTON_LABELS, BiphenylGeometry, rigid_design, rigid_problem
from dipolar_core.fit import FitResult, Problem, Settings, fit, full_jacobian, profile_interval, slice_interval
from scipy.optimize import least_squares

EXPECTED = Path(__file__).resolve().parents[3] / "datasets" / "biphenyl-synthetic" / "expected"
SPEC = json.loads((EXPECTED / "spec.json").read_text())
TOL = SPEC["tolerances"]["regression"]


def load(name: str, y_key: str) -> tuple[tuple[tuple[int, int], ...], np.ndarray, np.ndarray, dict[str, Any]]:
    data = json.loads((EXPECTED / name).read_text())
    index = {label: i for i, label in enumerate(PROTON_LABELS)}
    pairs = tuple((index[a], index[b]) for a, b in data["pairs"])
    return pairs, np.array(data[y_key]), np.array(data["sigma_Hz"]), data["expected"]


@pytest.fixture(scope="module")
def noisy() -> tuple[Problem, FitResult, dict[str, Any]]:
    pairs, y, sigma, expected = load("noisy_fixture.json", "y_Hz")
    problem = rigid_problem(pairs, y, sigma)
    return problem, fit(problem), expected


# --------------------------------------------------------------------------- gate (b): the frozen regression
def test_optimum_matches_the_frozen_fixture(noisy: tuple[Problem, FitResult, dict[str, Any]]) -> None:
    _, result, exp = noisy
    assert abs(result.theta[0] - exp["phi_deg"]) < 1e-8  # well inside TOL["phi_atol_deg"] = 1e-4
    assert abs(result.theta[0] - exp["phi_deg"]) < TOL["phi_atol_deg"]
    np.testing.assert_allclose(result.order, [exp["Szz"], exp["Delta"]], rtol=0, atol=TOL["S_atol"])
    np.testing.assert_allclose(result.predictions, exp["predictions_Hz"], rtol=0, atol=TOL["predictions_atol_Hz"])
    assert result.chi2 == pytest.approx(exp["objective"], rel=TOL["objective_rtol"])
    assert (result.n_obs, result.p_free, result.nu) == (exp["N"], exp["p_free"], exp["nu"])
    assert result.p_value == pytest.approx(exp["p_value"], rel=1e-6)


def test_competing_basins_are_reported(noisy: tuple[Problem, FitResult, dict[str, Any]]) -> None:
    """D3.2: both grid minima are refined and reported; the far basin has a huge Δχ²."""
    _, result, exp = noisy
    grid_minima = [(float(result.scan.points[i, 0]), float(result.scan.chi2[i])) for i in result.scan.minima]
    want = [(m["phi_grid_deg"], m["chi2"]) for m in exp["grid_local_minima"]]
    assert [p for p, _ in grid_minima] == [p for p, _ in want]
    for (_, got), (_, ref) in zip(grid_minima, want, strict=True):
        assert got == pytest.approx(ref, rel=1e-9)
    assert len(result.basins) == 2 and result.basins[0].delta_chi2 == 0.0
    assert result.basins[1].delta_chi2 > 1e6 and 75.0 < result.basins[1].theta[0] < 85.0
    assert all(b.converged for b in result.basins)


def test_validity_flags(noisy: tuple[Problem, FitResult, dict[str, Any]]) -> None:
    _, result, exp = noisy
    v = result.validity
    assert (v.inner_rank, v.inner_parameters) == (exp["validity"]["inner_rank"], 2)
    assert v.inner_condition_number == pytest.approx(exp["validity"]["inner_condition_number"], rel=1e-6)
    assert (v.joint_rank, v.joint_parameters) == (exp["validity"]["joint_rank"], 3)
    assert v.converged and v.regular and v.at_bound == ()
    assert v.physically_admissible is exp["validity"]["physically_admissible"]


def test_full_jacobian_covariance(noisy: tuple[Problem, FitResult, dict[str, Any]]) -> None:
    """D3.4: covariance from the full whitened Jacobian in (φ, Szz, Δ); known σ, not rescaled."""
    _, result, exp = noisy
    ref = exp["covariance_full_jacobian"]
    assert result.covariance is not None and result.covariance.names == tuple(ref["parameters"])
    np.testing.assert_allclose(result.covariance.stderr, ref["stderr"], rtol=TOL["stderr_rtol"])
    np.testing.assert_allclose(result.covariance.correlation, ref["correlation"], atol=1e-6)
    assert result.unidentified == ()


def test_profile_intervals(noisy: tuple[Problem, FitResult, dict[str, Any]]) -> None:
    problem, result, exp = noisy
    ref = exp["profile_intervals_68pct"]
    for name, atol in (("phi_deg", TOL["phi_interval_endpoint_atol_deg"]), ("Szz", TOL["S_interval_endpoint_atol"])):
        interval = profile_interval(problem, result, name)
        assert interval.supported and interval.kind == "profile" and interval.label == "68.3% one-parameter (Δχ² = 1)"
        np.testing.assert_allclose([interval.lower, interval.upper], ref[name], atol=atol)
    delta = profile_interval(problem, result, "Delta")
    np.testing.assert_allclose([delta.lower, delta.upper], ref["Delta"], atol=TOL["S_interval_endpoint_atol"])


def test_slices_are_not_profiles(noisy: tuple[Problem, FitResult, dict[str, Any]]) -> None:
    """D3.4: a slice holds the others fixed. With correlated parameters it is strictly narrower."""
    problem, result, _ = noisy
    for name in ("phi_deg", "Delta"):  # corr(φ, Δ) = −0.49
        prof, sl = profile_interval(problem, result, name), slice_interval(problem, result, name)
        assert sl.kind == "slice" and sl.supported
        assert prof.lower is not None and prof.upper is not None and sl.lower is not None and sl.upper is not None
        assert prof.lower < sl.lower < sl.upper < prof.upper
    # For a regular model the slice half-width is 1/sqrt((JᵀJ)ᵢᵢ), the profile half-width the stderr.
    assert result.covariance is not None
    j = full_jacobian(problem, result.theta, result.order)
    sl = slice_interval(problem, result, "Szz")
    assert sl.upper is not None and sl.lower is not None
    assert (sl.upper - sl.lower) / 2 == pytest.approx(1 / np.sqrt((j.T @ j)[1, 1]), rel=1e-6)


def test_95_percent_label(noisy: tuple[Problem, FitResult, dict[str, Any]]) -> None:
    problem, result, _ = noisy
    i68, i95 = profile_interval(problem, result, "phi_deg"), profile_interval(problem, result, "phi_deg", 3.84)
    assert i95.label == "95.0% one-parameter (Δχ² = 3.84)"
    assert i95.lower is not None and i68.lower is not None and i95.lower < i68.lower


def test_full_fit_and_reduced_fit_agree(noisy: tuple[Problem, FitResult, dict[str, Any]]) -> None:
    """D3.7: a joint bounded TRF over (φ, Szz, Δ) from the grid start lands on the VarPro optimum."""
    problem, result, _ = noisy
    start = result.scan.points[result.scan.minima[0]]
    x0 = np.r_[start, problem.inner(start).params]
    joint = least_squares(
        lambda x: problem.joint_residual(x[:1], x[1:]),
        x0,
        bounds=([0.0, -np.inf, -np.inf], [90.0, np.inf, np.inf]),
        method="trf",
        x_scale="jac",
        xtol=1e-15,
        ftol=1e-15,
        gtol=1e-15,
    )
    np.testing.assert_allclose(joint.x, np.r_[result.theta, result.order], atol=1e-8)
    assert 2 * joint.cost == pytest.approx(result.chi2, rel=1e-10)  # χ² = 2·cost (D3.3)


# --------------------------------------------------------------------------- gate (a): noiseless recovery
def test_noiseless_recovery() -> None:
    pairs, y, sigma, exp = load("noiseless.json", "D_Hz")
    result = fit(rigid_problem(pairs, y, sigma))
    atol = SPEC["tolerances"]["noiseless_recovery_atol"]
    assert abs(result.theta[0] - exp["phi_deg"]) < 1e-12  # residual-vector refinement (M0 spike 1)
    assert abs(result.order[0] - exp["Szz"]) < atol["Szz"]
    assert abs(result.order[1] - exp["Delta"]) < atol["Delta"]
    assert result.chi2 < 1e-20


# --------------------------------------------------------------------------- irregular cases
def test_an_optimum_on_a_bound_is_flagged_and_gets_no_interval() -> None:
    """Noiseless data from the planar molecule: the optimum sits on the φ = 0 bound."""
    pairs, _, sigma, _ = load("noiseless.json", "D_Hz")
    y = rigid_design(0.0, pairs) @ np.array([0.25, 0.03])
    problem = rigid_problem(pairs, y, sigma)
    result = fit(problem)
    assert result.theta[0] == pytest.approx(0.0, abs=1e-9)
    assert result.validity.at_bound == ("phi_deg",) and not result.validity.regular
    assert result.nu is None and result.p_value is None
    interval = profile_interval(problem, result, "phi_deg")
    assert not interval.supported and interval.lower is None and "not regular" in interval.note


def test_unidentified_directions_are_named_and_get_no_error_bar() -> None:
    """A geometry parameter the data cannot see: the joint rank drops, the covariance is withheld
    and the unidentified direction is named."""
    pairs, y, sigma, _ = load("noisy_fixture.json", "y_Hz")
    blind = Problem(
        design=lambda theta: rigid_design(37.0, pairs),  # ignores θ entirely
        y=y,
        sigma=sigma,
        lower=np.array([0.0]),
        upper=np.array([1.0]),
        theta_names=("blind",),
        order_names=("Szz", "Delta"),
    )
    result = fit(blind, Settings(grid=np.linspace(0.0, 1.0, 11)))
    assert result.validity.joint_rank == 2 and result.covariance is None
    assert len(result.unidentified) == 1 and set(result.unidentified[0]) == {"blind"}
    assert not result.validity.regular and result.nu is None
    assert not profile_interval(blind, result, "Szz").supported


# --------------------------------------------------------------------------- several geometry parameters
def test_sobol_multistart_recovers_two_geometry_parameters() -> None:
    """φ and the inter-ring bond length together, from noiseless couplings (Sobol starts)."""
    pairs, _, sigma, _ = load("noiseless.json", "D_Hz")
    truth_phi, truth_r = 37.0, 1.489
    y = rigid_design(truth_phi, pairs, BiphenylGeometry(r_inter=truth_r)) @ np.array([0.25, 0.03])
    problem = Problem(
        design=lambda theta: rigid_design(float(theta[0]), pairs, BiphenylGeometry(r_inter=float(theta[1]))),
        y=y,
        sigma=sigma,
        lower=np.array([0.0, 1.3]),
        upper=np.array([90.0, 1.7]),
        theta_names=("phi_deg", "r_inter_A"),
        order_names=("Szz", "Delta"),
    )
    settings = Settings(n_sobol=128, n_starts=6)
    result = fit(problem, settings)
    np.testing.assert_allclose(result.theta, [truth_phi, truth_r], rtol=0, atol=1e-8)
    np.testing.assert_allclose(result.order, [0.25, 0.03], rtol=0, atol=1e-10)
    assert result.validity.joint_rank == 4 and result.validity.regular
    # Diverse starts also find a far basin (at the r_inter bound); it is reported, with its Δχ².
    assert all(b.delta_chi2 > 1e3 for b in result.basins[1:])
    again = fit(problem, settings)  # the seeded Sobol scramble makes the search reproducible
    np.testing.assert_array_equal(again.scan.points, result.scan.points)


# --------------------------------------------------------------------------- input checks
@pytest.mark.parametrize(
    ("lower", "upper", "sigma", "message"),
    [
        ([0.0], [0.0], [0.5] * 14, "below its upper"),
        ([-np.inf], [90.0], [0.5] * 14, "finite"),
        ([0.0, 1.0], [90.0, 2.0], [0.5] * 14, "one entry"),
        ([0.0], [90.0], [0.5] * 13 + [0.0], "positive"),
    ],
)
def test_problem_validation(lower: list[float], upper: list[float], sigma: list[float], message: str) -> None:
    pairs, y, _, _ = load("noisy_fixture.json", "y_Hz")
    with pytest.raises(ValueError, match=message):
        Problem(
            design=lambda theta: rigid_design(float(theta[0]), pairs),
            y=y,
            sigma=np.array(sigma),
            lower=np.array(lower),
            upper=np.array(upper),
            theta_names=("phi_deg",),
            order_names=("Szz", "Delta"),
        )
