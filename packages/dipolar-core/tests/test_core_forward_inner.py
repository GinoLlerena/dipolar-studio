"""dipolar-core against the frozen fixtures and the D3 control cases.

The expected numbers come from ``datasets/*/expected/`` (frozen by the independent reference in
``tools/reference/``); this package never produced them.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from dipolar_core.biphenyl import PROTON_LABELS, BiphenylGeometry, proton_positions, rigid_design
from dipolar_core.forward import constraint_diagonal, design_rows, order_matrix
from dipolar_core.inference import is_admissible, solve_inner
from dipolar_core.nuclides import dipolar_constant_hz_a3

ROOT = Path(__file__).resolve().parents[3]
SYNTHETIC = ROOT / "datasets" / "biphenyl-synthetic"
EXPECTED = SYNTHETIC / "expected"
INDEX = {label: i for i, label in enumerate(PROTON_LABELS)}


def load(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((EXPECTED / name).read_text())
    return data


def pairs_of(labels: list[list[str]]) -> tuple[tuple[int, int], ...]:
    return tuple((INDEX[a], INDEX[b]) for a, b in labels)


@pytest.fixture(scope="module")
def generator() -> Any:
    spec = importlib.util.spec_from_file_location("biphenyl_generate", SYNTHETIC / "generate.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_constant_matches_dataset(generator: Any) -> None:
    assert dipolar_constant_hz_a3("1H", "1H") == pytest.approx(generator.K_HH, rel=1e-15)
    assert load("spec.json")["K_HH_Hz_A3"] == pytest.approx(dipolar_constant_hz_a3("1H", "1H"), rel=1e-15)
    with pytest.raises(ValueError, match="nuclide table"):
        dipolar_constant_hz_a3("1H", "99X")


@pytest.mark.parametrize("phi", [0.0, 12.3, 37.0, 89.0, 90.0])
def test_positions_match_generator(generator: Any, phi: float) -> None:
    g = BiphenylGeometry()
    reference = generator.proton_positions(phi, g.r_cc, g.r_ch, g.r_inter)
    ours = proton_positions(phi, g)
    for label, i in INDEX.items():
        np.testing.assert_allclose(ours[i], reference[label], atol=1e-12)


def test_forward_all_45_pairs() -> None:
    fwd = load("forward.json")
    pairs = pairs_of(fwd["pairs"])
    s = np.array([0.25, 0.03])
    for phi, expected in fwd["by_phi_deg"].items():
        np.testing.assert_allclose(rigid_design(float(phi), pairs) @ s, expected, rtol=0, atol=1e-6)
        reversed_pairs = tuple((b, a) for a, b in pairs)
        np.testing.assert_allclose(rigid_design(float(phi), reversed_pairs) @ s, expected, rtol=0, atol=1e-9)


def test_noisy_fixture_inner_solve_at_frozen_optimum() -> None:
    fx = load("noisy_fixture.json")
    e = fx["expected"]
    tol = load("spec.json")["tolerances"]["regression"]
    sol = solve_inner(rigid_design(e["phi_deg"], pairs_of(fx["pairs"])), np.array(fx["y_Hz"]), np.array(fx["sigma_Hz"]))
    assert sol.params[0] == pytest.approx(e["Szz"], abs=tol["S_atol"])
    assert sol.params[1] == pytest.approx(e["Delta"], abs=tol["S_atol"])
    np.testing.assert_allclose(sol.predictions, e["predictions_Hz"], rtol=0, atol=tol["predictions_atol_Hz"])
    assert sol.chi2 == pytest.approx(e["objective"], rel=tol["objective_rtol"])
    assert sol.rank == e["validity"]["inner_rank"]
    assert sol.condition == pytest.approx(e["validity"]["inner_condition_number"], rel=1e-9)
    assert is_admissible(constraint_diagonal() @ sol.params) is e["validity"]["physically_admissible"]


def test_noiseless_inner_recovery() -> None:
    nl = load("noiseless.json")
    truth = nl["truth"]
    atol = load("spec.json")["tolerances"]["noiseless_recovery_atol"]
    sol = solve_inner(
        rigid_design(truth["phi_deg"], pairs_of(nl["pairs"])), np.array(nl["D_Hz"]), np.array(nl["sigma_Hz"])
    )
    assert sol.params[0] == pytest.approx(truth["Szz"], abs=atol["Szz"])
    assert sol.params[1] == pytest.approx(truth["Delta"], abs=atol["Delta"])
    assert sol.chi2 < 1e-12


def test_weighted_projection_control_case() -> None:
    """Plan D3.7: A = (1,1)ᵀ, y = (0,1)ᵀ, L = diag(1,2) gives t* = 0.8 and χ² = 0.8."""
    sol = solve_inner(np.array([[1.0], [1.0]]), np.array([0.0, 1.0]), np.array([1.0, 0.5]))
    assert sol.params[0] == pytest.approx(0.8, abs=1e-14)
    assert sol.chi2 == pytest.approx(0.8, abs=1e-14)


def test_rank_deficient_design_is_flagged() -> None:
    a = np.array([[1.0, 2.0], [2.0, 4.0], [3.0, 6.0]])
    sol = solve_inner(a, np.array([1.0, 2.0, 3.1]), np.ones(3))
    assert sol.rank == 1
    assert sol.condition == float("inf")
    c = 14.3 / 14  # least-squares coefficient of the column (1, 2, 3) for y = (1, 2, 3.1)
    np.testing.assert_allclose(sol.params, [c / 5, 2 * c / 5], atol=1e-14)  # minimum-norm t1 + 2 t2 = c


def test_inputs_are_checked() -> None:
    with pytest.raises(ValueError, match="positive"):
        solve_inner(np.ones((2, 1)), np.ones(2), np.array([1.0, 0.0]))
    with pytest.raises(ValueError, match="non-finite"):
        solve_inner(np.ones((2, 1)), np.array([1.0, np.nan]), np.ones(2))
    with pytest.raises(ValueError, match="itself"):
        design_rows(proton_positions(37.0), ((1, 1),), -1.0)
    with pytest.raises(ValueError, match="positive finite"):
        BiphenylGeometry(r_cc=-1.0)


def test_order_matrix_and_admissibility() -> None:
    s5 = np.array([0.25, 0.03, 0.01, -0.02, 0.005])
    s = order_matrix(s5)
    assert np.trace(s) == pytest.approx(0.0, abs=1e-15)
    np.testing.assert_allclose(s, s.T)
    assert s[0, 0] - s[1, 1] == pytest.approx(0.03)
    assert is_admissible(np.array([1.0, 0.0, 0.0, 0.0, 0.0]))  # perfect alignment along z
    assert is_admissible(np.array([-0.5, 0.0, 0.0, 0.0, 0.0]))  # z perpendicular, uniaxial
    assert not is_admissible(np.array([1.2, 0.0, 0.0, 0.0, 0.0]))
    assert not is_admissible(np.array([-0.6, 0.0, 0.0, 0.0, 0.0]))
