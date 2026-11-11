"""M1 step 3: the symmetric four-site jump model (plan §4, gate (e))."""

from __future__ import annotations

import math
from collections.abc import Callable
from itertools import combinations

import numpy as np
import pytest
from dipolar_core.biphenyl import (
    JUMP_ESTIMAND,
    RIGID_ESTIMAND,
    jump_design,
    jump_design_derivative,
    jump_design_explicit,
    jump_problem,
    relabel_ring_b,
    rigid_design,
    rigid_problem,
)
from dipolar_core.fit import fit, profile_interval

ALL_PAIRS = tuple(combinations(range(10), 2))
INSIDE = (0.5, 12.0, 33.0, 37.0, 60.0, 89.0, 89.999)


def reference_derivative(fun: Callable[[float], np.ndarray], x: float, h: float = 0.02) -> np.ndarray:
    return (
        -fun(x - 3 * h) + 9 * fun(x - 2 * h) - 45 * fun(x - h) + 45 * fun(x + h) - 9 * fun(x + 2 * h) + fun(x + 3 * h)
    ) / (60 * h)


@pytest.mark.parametrize("phi", INSIDE)
def test_gate_e_explicit_averaging_equals_the_relabelling_shortcut(phi: float) -> None:
    """Gate (e), atol 1e-9 Hz (the frozen spec)."""
    np.testing.assert_allclose(jump_design(phi, ALL_PAIRS), jump_design_explicit(phi, ALL_PAIRS), rtol=0, atol=1e-9)


@pytest.mark.parametrize("phi", INSIDE[:-2])
def test_the_acute_domain_is_complete_at_fixed_labels(phi: float) -> None:
    """The conformer set {±φ, 180° ± φ} does not change under φ → −φ or φ → 180° − φ, so every
    torsion folds into [0°, 90°] with no label precondition."""
    reference = jump_design_explicit(phi, ALL_PAIRS)
    for other in (180.0 - phi, phi - 180.0):
        folded = abs(other) if abs(other) < 90.0 else 180.0 - abs(other)
        np.testing.assert_allclose(jump_design_explicit(folded, ALL_PAIRS), reference, atol=1e-9)
    # and the conformers themselves, built at 180° − φ, average to the same couplings
    total = np.zeros_like(reference)
    for theta in (180.0 - phi, phi - 180.0, phi, -phi):
        acute = 1.0 if math.cos(math.radians(theta)) > 0 else -1.0
        total += rigid_design(theta, ALL_PAIRS) @ np.diag([1.0, acute])
    np.testing.assert_allclose(total / 4, reference, atol=1e-9)


def test_the_jump_model_is_invariant_under_the_ring_b_relabelling() -> None:
    for phi in INSIDE:
        np.testing.assert_allclose(jump_design(phi, relabel_ring_b(ALL_PAIRS)), jump_design(phi, ALL_PAIRS), atol=1e-9)


def test_the_jump_model_differs_from_the_rigid_one() -> None:
    assert np.abs(jump_design(37.0, ALL_PAIRS) - rigid_design(37.0, ALL_PAIRS)).max() > 10.0


def test_the_explicit_average_is_refused_where_the_acute_bisector_is_undefined() -> None:
    for phi in (0.0, 90.0, 120.0):
        with pytest.raises(ValueError, match="0 < phi < 90"):
            jump_design_explicit(phi, ALL_PAIRS)


@pytest.mark.parametrize("phi", (0.0, *INSIDE, 90.0))
def test_the_analytic_jump_derivative(phi: float) -> None:
    exact = jump_design_derivative(phi, ALL_PAIRS)
    approx = reference_derivative(lambda v: jump_design(v, ALL_PAIRS), phi)
    np.testing.assert_allclose(exact, approx, rtol=0, atol=1e-10 * np.abs(jump_design(phi, ALL_PAIRS)).max())


def test_the_90_degree_limit_leaves_delta_unidentified() -> None:
    """D2d at 90°: the Δ column vanishes, so a fit there reports inner rank 1 and no covariance."""
    assert np.abs(jump_design(90.0, ALL_PAIRS)[:, 1]).max() < 1e-9
    y = jump_design(90.0, ALL_PAIRS) @ [0.25, 0.0]
    result = fit(jump_problem(ALL_PAIRS, y, np.full(len(y), 0.5)))
    assert result.validity.inner_rank == 1 and not result.validity.regular and result.covariance is None


@pytest.mark.parametrize("phi", [12.0, 33.0, 37.0, 70.0])
def test_noiseless_recovery_with_the_jump_model(phi: float) -> None:
    y = jump_design(phi, ALL_PAIRS) @ [0.43, 0.185]
    result = fit(jump_problem(ALL_PAIRS, y, np.full(len(y), 0.5)))
    assert result.validity.regular
    assert result.theta[0] == pytest.approx(phi, abs=1e-8)
    np.testing.assert_allclose(result.order, [0.43, 0.185], rtol=0, atol=1e-8)
    assert result.estimand == JUMP_ESTIMAND


def test_the_estimand_is_labelled() -> None:
    y = rigid_design(37.0, ALL_PAIRS) @ [0.25, 0.03]
    assert fit(rigid_problem(ALL_PAIRS, y, np.full(len(y), 0.5))).estimand == RIGID_ESTIMAND


# --------------------------------------------------------------------------- round 21 counterexamples
def test_a_full_rank_basin_beside_the_rank_changing_pole_is_found() -> None:
    """Round 21, finding 1. The grid minimum is the 90° point, where the Δ column vanishes (rank 1).
    The full-rank basin at 89.999° next to it was missed, and the fit returned χ² ≈ 1.2e12. An
    extra start at the nearest full-rank grid point finds it."""
    y = jump_design(89.999, ALL_PAIRS) @ [0.25, 0.1]
    result = fit(jump_problem(ALL_PAIRS, y, np.full(len(y), 1e-8)))
    assert result.scan.rank_starts  # the extra start beside the rank change
    assert result.validity.regular and result.chi2 < 1e-6
    assert result.theta[0] == pytest.approx(89.999, abs=1e-6)
    np.testing.assert_allclose(result.order, [0.25, 0.1], rtol=0, atol=1e-6)


@pytest.mark.parametrize("phi", [89.9, 89.0])
def test_a_profile_that_runs_into_the_pole_is_not_supported(phi: float) -> None:
    """Round 21, finding 2. Toward 90° the profile stays below the threshold, then leaps past it
    where the inner rank drops. brentq converged onto that jump and returned it as an endpoint,
    where χ² was 1e-5, not 1. A crossing must meet the threshold."""
    y = jump_design(phi, ALL_PAIRS) @ [0.25, 0.1]
    problem = jump_problem(ALL_PAIRS, y, np.full(len(y), 0.5))
    result = fit(problem)
    assert result.validity.regular
    interval = profile_interval(problem, result, "phi_deg")
    assert not interval.supported and "jumps across the threshold" in interval.note


def test_an_interval_away_from_the_pole_is_still_supported() -> None:
    y = jump_design(60.0, ALL_PAIRS) @ [0.25, 0.1]
    problem = jump_problem(ALL_PAIRS, y, np.full(len(y), 0.5))
    interval = profile_interval(problem, fit(problem), "phi_deg")
    assert interval.supported and interval.lower is not None and interval.lower < 60.0 < (interval.upper or 0)
