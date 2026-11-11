"""M1 step 4: imported coordinates with one torsion (dipolar_core.torsion)."""

from __future__ import annotations

import math
from collections.abc import Callable
from itertools import combinations

import numpy as np
import pytest
from dipolar_core.biphenyl import BiphenylGeometry, frame_axes, proton_positions, rigid_design
from dipolar_core.fit import fit
from dipolar_core.forward import order_matrix, order_vector
from dipolar_core.torsion import (
    TorsionGeometry,
    bonds_from_coordinates,
    dihedral_deg,
    imported_problem,
    moving_fragment,
)

PHI0 = 37.0


def biphenyl_atoms(phi_deg: float = PHI0) -> tuple[list[str], np.ndarray]:
    """22 atoms in the template's bisector frame: C1…C6 (ring A), C1′…C6′, then H2…H6, H2′…H6′.

    The template's own carbons, rebuilt from its documented construction (biphenyl docstring).
    """
    g = BiphenylGeometry()
    half = math.radians(phi_deg) / 2
    carbons = []
    for side in (-1.0, 1.0):
        in_plane = np.array([math.cos(half), -side * math.sin(half), 0.0])
        centre = side * (g.r_inter / 2 + g.r_cc) * np.array([0.0, 0.0, 1.0])
        to_c1 = -side * np.array([0.0, 0.0, 1.0])
        for k in range(6):
            a = math.radians(60.0 * k)
            carbons.append(centre + g.r_cc * (math.cos(a) * to_c1 + math.sin(a) * in_plane))
    positions = np.vstack([np.array(carbons), proton_positions(phi_deg)])
    return ["C"] * 12 + ["H"] * 10, positions


ELEMENTS, POSITIONS = biphenyl_atoms()
C1, C2, C1P, C2P = 0, 1, 6, 7
H = list(range(12, 22))
TORSION = (C2, C1, C1P, C2P)
H_PAIRS = tuple(combinations(H, 2))


def reference_derivative(fun: Callable[[float], np.ndarray], x: float, h: float = 0.02) -> np.ndarray:
    return (
        -fun(x - 3 * h) + 9 * fun(x - 2 * h) - 45 * fun(x - h) + 45 * fun(x + h) - 9 * fun(x + 2 * h) + fun(x + 3 * h)
    ) / (60 * h)


def test_the_template_rebuilt_with_carbons_has_the_documented_dihedral() -> None:
    assert dihedral_deg(POSITIONS, *TORSION) == pytest.approx(-PHI0, abs=1e-9)  # τ = −φ (frame contract)
    bonds = bonds_from_coordinates(ELEMENTS, POSITIONS)
    assert len(bonds) == 12 + 1 + 10  # two rings, the inter-ring bond, ten C–H


def test_the_moving_fragment_is_ring_b() -> None:
    moving = moving_fragment(22, bonds_from_coordinates(ELEMENTS, POSITIONS), C1, C1P)
    assert moving == tuple(range(6, 12)) + tuple(range(17, 22))


def test_a_ring_bond_or_a_non_bond_cannot_carry_a_torsion() -> None:
    bonds = bonds_from_coordinates(ELEMENTS, POSITIONS)
    with pytest.raises(ValueError, match="in a ring"):
        moving_fragment(22, bonds, C1, C2)
    with pytest.raises(ValueError, match="not bonded"):
        moving_fragment(22, bonds, C1, C2P)
    with pytest.raises(ValueError, match="fixed side"):
        TorsionGeometry.from_atoms(ELEMENTS, POSITIONS, (C2P, C1, C1P, C2))
    with pytest.raises(ValueError, match="no covalent radius"):
        bonds_from_coordinates(["C", "Xx"], np.zeros((2, 3)))


@pytest.mark.parametrize("tau", [-90.0, -37.0, -12.0, 0.0, 25.0, 140.0])
def test_setting_the_dihedral_matches_the_template_seen_from_ring_a(tau: float) -> None:
    """An independent route to the same couplings. Imported coordinates (input frame = the bisector
    frame at φ₀, fixed to ring A) at τ must predict what the template predicts in its ring-A frame
    at φ = −τ, for the same physical tensor."""
    geometry = TorsionGeometry.from_atoms(ELEMENTS, POSITIONS, TORSION)
    moved = geometry.positions(tau)
    assert dihedral_deg(moved, *TORSION) == pytest.approx(tau, abs=1e-9)
    np.testing.assert_allclose(moved[:6], POSITIONS[:6], atol=1e-12)  # ring A stays put
    s_input = np.array([0.25, 0.03, 0.02, -0.01, 0.015])
    to_ring_a = frame_axes(PHI0, "ring-a")[0]  # input axes → ring-A axes (both fixed to ring A)
    s_ring_a = order_vector(to_ring_a @ order_matrix(s_input) @ to_ring_a.T)
    problem = imported_problem(geometry, H_PAIRS, [("1H", "1H")] * len(H_PAIRS), np.zeros(45), np.ones(45))
    template_pairs = tuple((a - 12, b - 12) for a, b in H_PAIRS)
    expected = rigid_design(-tau, template_pairs, order="c1", frame="ring-a") @ s_ring_a
    np.testing.assert_allclose(problem.design(np.array([tau])) @ s_input, expected, rtol=0, atol=1e-9)


@pytest.mark.parametrize("tau", [-80.0, -37.0, 0.0, 33.0])
def test_the_analytic_torsion_derivatives(tau: float) -> None:
    geometry = TorsionGeometry.from_atoms(ELEMENTS, POSITIONS, TORSION)
    np.testing.assert_allclose(
        geometry.positions_derivative(tau), reference_derivative(geometry.positions, tau), rtol=0, atol=1e-11
    )
    problem = imported_problem(geometry, H_PAIRS, [("1H", "1H")] * 45, np.zeros(45), np.ones(45))
    exact = problem.checked_design_derivative(np.array([tau]))[0]
    approx = reference_derivative(lambda v: problem.design(np.array([v])), tau)
    np.testing.assert_allclose(exact, approx, rtol=0, atol=1e-10 * np.abs(problem.design(np.array([tau]))).max())


@pytest.mark.parametrize("order", ["c1", "c2z"])
def test_noiseless_recovery_on_imported_coordinates(order: str) -> None:
    geometry = TorsionGeometry.from_atoms(ELEMENTS, POSITIONS, TORSION)
    truth = np.array([0.25, 0.03, 0.02, -0.01, 0.015])[: 5 if order == "c1" else 3]
    probe = imported_problem(geometry, H_PAIRS, [("1H", "1H")] * 45, np.zeros(45), np.ones(45), order=order)
    y = probe.design(np.array([-52.0])) @ truth
    problem = imported_problem(
        geometry, H_PAIRS, [("1H", "1H")] * 45, y, np.full(45, 0.5), order=order, domain_deg=(-90.0, 0.0)
    )
    result = fit(problem)
    assert result.validity.regular and result.estimand == "rigid effective dihedral"
    assert result.theta[0] == pytest.approx(-52.0, abs=1e-8)
    np.testing.assert_allclose(result.order, truth, rtol=0, atol=1e-8)


def test_imported_problem_validation() -> None:
    geometry = TorsionGeometry.from_atoms(ELEMENTS, POSITIONS, TORSION)
    with pytest.raises(ValueError, match="no wider than 360"):
        imported_problem(geometry, H_PAIRS, [("1H", "1H")] * 45, np.zeros(45), np.ones(45), domain_deg=(-180, 200))
    with pytest.raises(ValueError, match="unknown order model"):
        imported_problem(geometry, H_PAIRS, [("1H", "1H")] * 45, np.zeros(45), np.ones(45), order="bisector-diagonal")
    assert geometry.min_nonbonded_distance(0.0) > 1.5  # the ortho protons do not clash at planarity
