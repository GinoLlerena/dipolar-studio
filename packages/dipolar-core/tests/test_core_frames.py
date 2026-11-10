"""M1 step 2: the frozen frame contract, the C2(z)/C1 order models, the moving-bisector form,
the D2d endpoint and the analytic geometry derivatives (plan D12, ADR-0012).

The legacy formulas below are written out independently from ``InteraccCalculada.cpp``
(``CalculaCoeficientesParaD2`` and ``CalculaCoeficientesParaD4``). They use spherical angles of
the internuclear vector: θ is the polar angle from z and ϕ the azimuth, taken with atan2 (the
legacy atan bug B12 does not affect D2 or D4).
"""

from __future__ import annotations

import dataclasses
import json
import math
from collections.abc import Callable
from itertools import combinations
from pathlib import Path

import numpy as np
import pytest
from dipolar_core.biphenyl import (
    ACUTE_BOUND_NOTE,
    D2D_NOTE,
    FRAMES,
    ORDER_MODELS,
    PROTON_LABELS,
    RELABELLING_MAPS,
    RING_B_RELABELLING,
    at_d2d_endpoint,
    constraint,
    frame_axes,
    proton_positions,
    proton_positions_derivative,
    resolve_order_model,
    rigid_design,
    rigid_design_derivative,
    rigid_problem,
)
from dipolar_core.fit import (
    Model,
    Problem,
    Settings,
    _free_model,
    _reduced_model,
    _varpro_jacobian,
    _whole,
    fit,
    profile_interval,
)
from dipolar_core.forward import (
    constraint_moving_bisector,
    design_rows,
    design_rows_derivative,
    frame_change,
    order_matrix,
    order_vector,
)
from dipolar_core.nuclides import dipolar_constant_hz_a3

ALL_PAIRS = tuple(combinations(range(10), 2))
K_HH = dipolar_constant_hz_a3("1H", "1H")
EXPECTED = Path(__file__).resolve().parents[3] / "datasets" / "biphenyl-synthetic" / "expected"
ANGLES = (0.0, 1e-3, 17.3, 37.0, 60.0, 89.9, 90.0)


def rotation(seed: int) -> np.ndarray:
    q, r = np.linalg.qr(np.random.default_rng(seed).normal(size=(3, 3)))
    q = q * np.sign(np.diag(r))
    return q if np.linalg.det(q) > 0 else -q


def reference_derivative(fun: Callable[[float], np.ndarray], x: float, h: float = 0.02) -> np.ndarray:
    """Sixth-order centred stencil: an independent reference, accurate to ~1e-10 relative for
    these smooth functions (truncation ~h⁶, rounding ~ε·|f|/h)."""
    return (
        -fun(x - 3 * h) + 9 * fun(x - 2 * h) - 45 * fun(x - h) + 45 * fun(x + h) - 9 * fun(x + 2 * h) + fun(x + 3 * h)
    ) / (60 * h)


def tensor_map(axes: np.ndarray) -> np.ndarray:
    """5 × 5 M with order_vector(axes S axesᵀ) = M · order_vector(S)."""
    return np.column_stack([order_vector(axes @ order_matrix(e) @ axes.T) for e in np.eye(5)])


# --------------------------------------------------------------------------- analytic derivatives
@pytest.mark.parametrize("order", ORDER_MODELS)
@pytest.mark.parametrize("frame", FRAMES)
def test_the_analytic_design_derivative_matches_finite_differences(order: str, frame: str) -> None:
    for phi in ANGLES:
        exact = rigid_design_derivative(phi, ALL_PAIRS, order=order, frame=frame).ravel()  # type: ignore[arg-type]
        approx = reference_derivative(
            lambda v: rigid_design(v, ALL_PAIRS, order=order, frame=frame).ravel(),  # type: ignore[arg-type]
            phi,
        )
        scale = float(np.abs(rigid_design(phi, ALL_PAIRS, order=order, frame=frame)).max())  # type: ignore[arg-type]
        np.testing.assert_allclose(exact, approx, rtol=0, atol=1e-10 * scale, err_msg=f"{order} {frame} {phi}")


def test_design_rows_derivative_matches_finite_differences_for_any_geometry() -> None:
    rng = np.random.default_rng(7)
    positions = rng.normal(scale=2.0, size=(6, 3))
    directions = rng.normal(size=(3, 6, 3))
    pairs = tuple(combinations(range(6), 2))
    exact = design_rows_derivative(positions, directions, pairs, K_HH)
    scale = float(np.abs(design_rows(positions, pairs, K_HH)).max())
    for m in range(3):
        approx = reference_derivative(
            lambda v, m=m: design_rows(positions + v * directions[m], pairs, K_HH).ravel(), 0.0, h=1e-3
        )
        np.testing.assert_allclose(exact[m].ravel(), approx, rtol=0, atol=1e-9 * scale)


def test_position_derivative_matches_finite_differences() -> None:
    for phi in ANGLES:
        approx = reference_derivative(lambda v: proton_positions(v).ravel(), phi)
        np.testing.assert_allclose(proton_positions_derivative(phi).ravel(), approx, rtol=0, atol=1e-12)


def test_fits_with_analytic_and_differenced_derivatives_agree() -> None:
    data = json.loads((EXPECTED / "noisy_fixture.json").read_text())
    index = {label: i for i, label in enumerate(PROTON_LABELS)}
    pairs = tuple((index[a], index[b]) for a, b in data["pairs"])
    analytic = rigid_problem(pairs, np.array(data["y_Hz"]), np.array(data["sigma_Hz"]))
    differenced = dataclasses.replace(analytic, design_derivative=None)
    a, d = fit(analytic), fit(differenced)
    assert abs(a.theta[0] - d.theta[0]) < 1e-8
    np.testing.assert_allclose(a.order, d.order, rtol=0, atol=1e-10)
    assert a.covariance is not None and d.covariance is not None
    np.testing.assert_allclose(a.covariance.stderr, d.covariance.stderr, rtol=1e-6)
    assert a.validity.inner_condition_number == pytest.approx(d.validity.inner_condition_number, rel=1e-9)
    assert dataclasses.replace(a.validity, inner_condition_number=None) == dataclasses.replace(
        d.validity, inner_condition_number=None
    )


def test_a_wrong_derivative_shape_is_rejected() -> None:
    problem = rigid_problem(((0, 1), (0, 2)), np.ones(2), np.ones(2))
    broken = dataclasses.replace(problem, design_derivative=lambda theta: np.zeros((2, 2)))
    with pytest.raises(ValueError, match="design_derivative returned shape"):
        broken.checked_design_derivative(np.array([30.0]))


# --------------------------------------------------------------------------- the frame contract
def test_contraction_is_invariant_under_any_rotation() -> None:
    """D = A(r)·s = A(R r)·M(R)·s: frames change coordinates and S together (passive)."""
    positions = proton_positions(37.0)
    for seed in range(5):
        axes = rotation(seed)
        before = design_rows(positions, ALL_PAIRS, K_HH)
        after = design_rows(frame_change(axes, positions), ALL_PAIRS, K_HH) @ tensor_map(axes)
        np.testing.assert_allclose(after, before, rtol=0, atol=1e-9 * np.abs(before).max())


@pytest.mark.parametrize("phi", ANGLES)
def test_the_bisector_diagonal_model_predicts_the_same_in_both_frames(phi: float) -> None:
    bisector = rigid_design(phi, ALL_PAIRS)
    ring = rigid_design(phi, ALL_PAIRS, frame="ring-a")
    np.testing.assert_allclose(ring, bisector, rtol=0, atol=1e-9 * np.abs(bisector).max())


def test_the_ring_a_frame_holds_ring_a_still_and_moves_the_bisector() -> None:
    fixed = frame_change(frame_axes(10.0, "ring-a")[0], proton_positions(10.0))[:5]
    for phi in (0.0, 37.0, 90.0):
        axes, _ = frame_axes(phi, "ring-a")
        np.testing.assert_allclose(frame_change(axes, proton_positions(phi))[:5], fixed, atol=1e-12)
        # The bisector-frame diagonal tensor, seen from ring A, is the moving form with δ = −φ.
        s5 = np.array([0.25, 0.03, 0.0, 0.0, 0.0])
        seen = order_vector(axes @ order_matrix(s5) @ axes.T)
        np.testing.assert_allclose(seen, constraint_moving_bisector(-math.radians(phi)) @ s5[:2], atol=1e-15)


def test_the_torsion_sign_convention() -> None:
    """The signed IUPAC dihedral τ(C2–C1–C1′–C2′) of the template is −φ."""

    def dihedral(a: np.ndarray, b: np.ndarray, c: np.ndarray, d: np.ndarray) -> float:
        b1, b2, b3 = b - a, c - b, d - c  # IUPAC: positive = far bond turned clockwise, seen along b2
        y = float(np.linalg.norm(b2) * (b1 @ np.cross(b2, b3)))
        return math.degrees(math.atan2(y, float(np.cross(b1, b2) @ np.cross(b2, b3))))

    from dipolar_core.biphenyl import BiphenylGeometry

    g = BiphenylGeometry()
    a, b, c, d = np.array([1.0, 0, 0]), np.zeros(3), np.array([0, 0, 1.0]), np.array([0, 1.0, 1.0])
    assert dihedral(a, b, c, d) == pytest.approx(90.0)  # the far bond turned +90° about +b2
    for phi in (20.0, 37.0, 70.0):
        h = proton_positions(phi)
        c1, c1p = np.array([0, 0, -g.r_inter / 2]), np.array([0, 0, g.r_inter / 2])
        # H2 and H2′ lie on the rays C1→C2 and C1′→C2′ projected away from the axis.
        assert dihedral(h[0], c1, c1p, h[5]) == pytest.approx(-phi, abs=1e-9)


def test_the_reflection_equivalence_flips_sxy_and_syz() -> None:
    flip = np.diag([1.0, 1.0, -1.0, 1.0, -1.0])
    for phi in (12.0, 37.0):
        np.testing.assert_allclose(
            rigid_design(-phi, ALL_PAIRS, order="c1") @ flip, rigid_design(phi, ALL_PAIRS, order="c1"), atol=1e-9
        )


def test_c2z_spans_the_same_model_in_every_frame_sharing_z() -> None:
    """Rotating about z maps the C2(z) subspace onto itself: equal column spaces in both frames."""
    for phi in (12.0, 37.0, 90.0):
        bisector = rigid_design(phi, ALL_PAIRS, order="c2z")
        ring = rigid_design(phi, ALL_PAIRS, order="c2z", frame="ring-a")
        coefficients, *_ = np.linalg.lstsq(bisector, ring, rcond=None)
        np.testing.assert_allclose(bisector @ coefficients, ring, rtol=0, atol=1e-9 * np.abs(ring).max())


def test_order_model_names_and_legacy_aliases() -> None:
    assert resolve_order_model("D4") == "bisector-diagonal"
    assert resolve_order_model("D2") == "c2z"
    assert resolve_order_model("c1") == "c1"
    with pytest.raises(ValueError, match="unknown order model"):
        resolve_order_model("D2d")
    with pytest.raises(ValueError, match="unknown frame"):
        rigid_problem(((0, 1),), np.ones(1), np.ones(1), frame="lab")  # type: ignore[arg-type]
    assert rigid_problem(((0, 1),), np.ones(1), np.ones(1), order="D2").order_names == ("Szz", "Delta", "Sxy")


# --------------------------------------------------------------------------- legacy equivalence
def legacy_columns(vectors: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    r = np.linalg.norm(vectors, axis=1)
    theta = np.arccos(vectors[:, 2] / r)
    azimuth = np.arctan2(vectors[:, 1], vectors[:, 0])
    p2 = (3 * np.cos(theta) ** 2 - 1) / 2
    return K_HH / r**3, p2, np.sin(theta) ** 2, azimuth


def test_legacy_d4_equals_the_moving_bisector_form_away_from_the_pole() -> None:
    """Legacy D4: ½ sin²θ (cos 2ϕ + tan δ · sin 2ϕ)·Δ_L with Txy = 0. In the ring-A frame, with
    δ = −φ and Δ_L = Δ′ cos δ, it predicts what the bisector-diagonal model predicts."""
    szz, delta_prime = 0.25, 0.03
    for phi in (0.0, 12.0, 37.0, 60.0, 85.0):
        axes, _ = frame_axes(phi, "ring-a")
        positions = frame_change(axes, proton_positions(phi))
        vectors = np.array([positions[j] - positions[i] for i, j in ALL_PAIRS])
        scale, p2, sin2, azimuth = legacy_columns(vectors)
        delta = -math.radians(phi)
        delta_legacy = delta_prime * math.cos(delta)
        legacy = scale * (
            p2 * szz + 0.5 * sin2 * (np.cos(2 * azimuth) + math.tan(delta) * np.sin(2 * azimuth)) * delta_legacy
        )
        ours = rigid_design(phi, ALL_PAIRS, frame="ring-a") @ [szz, delta_prime]
        np.testing.assert_allclose(ours, legacy, rtol=0, atol=1e-9 * np.abs(legacy).max())


def test_the_legacy_d4_form_diverges_at_the_pole_and_ours_does_not() -> None:
    assert abs(math.tan(math.radians(90.0 - 1e-9))) > 1e10
    c, d_c = constraint(90.0, "bisector-diagonal", "ring-a")
    assert np.all(np.isfinite(c)) and np.all(np.isfinite(d_c))
    np.testing.assert_allclose(c[1:3, 1], [0.0, -0.5], atol=1e-15)  # Δ = 0, Sxy = −½Δ′ at δ = −90°


def test_legacy_d2_equals_c2z() -> None:
    """Legacy D2: Tzz → P2(cos θ); Txx − Tyy → ½ sin²θ cos 2ϕ; Txy → sin²θ sin 2ϕ."""
    for frame in FRAMES:
        axes, _ = frame_axes(37.0, frame)  # type: ignore[arg-type]
        positions = frame_change(axes, proton_positions(37.0))
        vectors = np.array([positions[j] - positions[i] for i, j in ALL_PAIRS])
        scale, p2, sin2, azimuth = legacy_columns(vectors)
        legacy = scale[:, None] * np.column_stack([p2, 0.5 * sin2 * np.cos(2 * azimuth), sin2 * np.sin(2 * azimuth)])
        ours = rigid_design(37.0, ALL_PAIRS, order="c2z", frame=frame)  # type: ignore[arg-type]
        np.testing.assert_allclose(ours, legacy, rtol=0, atol=1e-9 * np.abs(legacy).max())


# --------------------------------------------------------------------------- the D2d endpoint
def s4_permutation() -> list[int]:
    """S4 about z at φ = 90°: (x, y, z) → (−y, x, −z) maps the template onto itself."""
    positions = proton_positions(90.0)
    image = positions @ np.array([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, -1.0]]).T
    perm = [int(np.argmin(np.linalg.norm(positions - p, axis=1))) for p in image]
    np.testing.assert_allclose(positions[perm], image, atol=1e-12)
    assert sorted(perm) == list(range(10))
    return perm


def test_the_d2d_endpoint_forces_a_uniaxial_tensor() -> None:
    perm = s4_permutation()
    images = tuple((perm[i], perm[j]) for i, j in ALL_PAIRS)
    d, d_image = rigid_design(90.0, ALL_PAIRS, order="c1"), rigid_design(90.0, images, order="c1")
    # A uniaxial tensor gives equal couplings on every S4 orbit…
    np.testing.assert_allclose(d[:, 0], d_image[:, 0], rtol=0, atol=1e-9 * np.abs(d).max())
    # …while Δ′ ≠ 0 breaks the symmetry: the data alone do not enforce it, hence the label.
    assert np.abs(d[:, 1] - d_image[:, 1]).max() > 1e-3 * np.abs(d).max()


def test_a_fit_at_the_d2d_endpoint_is_labelled_and_others_are_not() -> None:
    truth = rigid_design(90.0, ALL_PAIRS) @ [0.25, 0.0]
    at_pole = fit(rigid_problem(ALL_PAIRS, truth, np.full(len(truth), 0.5)))
    assert at_d2d_endpoint(float(at_pole.theta[0]))
    assert at_pole.notes == (D2D_NOTE, ACUTE_BOUND_NOTE)
    assert "phi_deg" in at_pole.validity.at_bound
    inside = fit(rigid_problem(ALL_PAIRS, rigid_design(37.0, ALL_PAIRS) @ [0.25, 0.03], np.full(len(truth), 0.5)))
    assert inside.notes == ()
    assert not at_d2d_endpoint(89.999)


# --------------------------------------------------------------------------- C2(z) and C1 fits
@pytest.mark.parametrize("order", ["c2z", "c1"])
@pytest.mark.parametrize("frame", FRAMES)
def test_noiseless_recovery_with_the_wider_order_models(order: str, frame: str) -> None:
    s5 = np.array([0.25, 0.03, 0.02, -0.01, 0.015])
    p = 3 if order == "c2z" else 5
    truth = s5[:p]
    y = rigid_design(37.0, ALL_PAIRS, order=order, frame=frame) @ truth  # type: ignore[arg-type]
    result = fit(rigid_problem(ALL_PAIRS, y, np.full(len(y), 0.5), order=order, frame=frame))  # type: ignore[arg-type]
    assert result.validity.regular and result.validity.joint_rank == 1 + p
    assert result.theta[0] == pytest.approx(37.0, abs=1e-8)
    np.testing.assert_allclose(result.order, truth, rtol=0, atol=1e-8)
    assert result.chi2 < 1e-12


def test_bisector_diagonal_and_c1_agree_on_d2_data() -> None:
    """A D2 tensor is a special C1 tensor: the C1 fit finds the same φ and zero off-diagonals."""
    y = rigid_design(37.0, ALL_PAIRS) @ [0.25, 0.03]
    result = fit(rigid_problem(ALL_PAIRS, y, np.full(len(y), 0.5), order="c1"))
    assert result.theta[0] == pytest.approx(37.0, abs=1e-8)
    np.testing.assert_allclose(result.order, [0.25, 0.03, 0.0, 0.0, 0.0], rtol=0, atol=1e-8)


def test_fixture_fit_has_no_notes() -> None:
    data = json.loads((EXPECTED / "noisy_fixture.json").read_text())
    index = {label: i for i, label in enumerate(PROTON_LABELS)}
    pairs = tuple((index[a], index[b]) for a, b in data["pairs"])
    assert fit(rigid_problem(pairs, np.array(data["y_Hz"]), np.array(data["sigma_Hz"]))).notes == ()


# --------------------------------------------------------------------------- analytic sub-models
def two_parameter_problem(analytic: bool = True) -> Problem:
    """A smooth k = 2 problem with an analytic derivative: D(a, b) = [exp(−a·x), cos(b·x), x]."""
    x = np.linspace(0.0, 3.0, 12)

    def design(theta: np.ndarray) -> np.ndarray:
        return np.column_stack([np.exp(-theta[0] * x), np.cos(theta[1] * x), x])

    def derivative(theta: np.ndarray) -> np.ndarray:
        zero = np.zeros_like(x)
        d_a = np.column_stack([-x * np.exp(-theta[0] * x), zero, zero])
        d_b = np.column_stack([zero, -x * np.sin(theta[1] * x), zero])
        return np.stack([d_a, d_b])

    y = design(np.array([0.7, 1.3])) @ [2.0, -1.0, 0.5] + 0.005 * np.sin(7 * x)
    return Problem(
        design=design,
        design_derivative=derivative if analytic else None,
        y=y,
        sigma=np.full(len(x), 0.01),
        lower=np.array([0.1, 0.5]),
        upper=np.array([2.0, 2.0]),
        theta_names=("a", "b"),
        order_names=("u", "v", "w"),
    )


def assert_model_derivative(model: Model, x: np.ndarray) -> None:
    assert model.derivative is not None
    d_design, d_fixed = model.derivative(x)
    for i in range(len(x)):

        def along(v: float, i: int = i) -> np.ndarray:
            shifted = x.copy()
            shifted[i] = v
            d, f = model(shifted)
            return np.concatenate([d.ravel(), f])

        reference = reference_derivative(along, float(x[i]), h=1e-3)
        np.testing.assert_allclose(np.concatenate([d_design[i].ravel(), d_fixed[i]]), reference, atol=1e-9)


def test_every_analytic_sub_model_derivative_is_right() -> None:
    problem = two_parameter_problem()
    assert_model_derivative(_whole(problem), np.array([0.9, 1.1]))

    def theta_of(f: np.ndarray) -> np.ndarray:
        return np.array([0.9, f[0]])

    assert_model_derivative(_free_model(problem, theta_of, [1]), np.array([1.1]))
    for column in range(problem.p):
        assert_model_derivative(_reduced_model(problem, column, 0.8), np.array([0.9, 1.1]))


@pytest.mark.parametrize("make", ["two-parameter", "biphenyl-c1"])
def test_the_analytic_varpro_jacobian_is_the_profile_residual_jacobian(make: str) -> None:
    """Away from the optimum, where the residual is large, both Golub–Pereyra terms matter."""
    if make == "two-parameter":
        problem, x = two_parameter_problem(), np.array([0.9, 1.1])
    else:
        y = rigid_design(37.0, ALL_PAIRS, order="c1") @ [0.25, 0.03, 0.02, -0.01, 0.015]
        problem, x = rigid_problem(ALL_PAIRS, y, np.full(len(y), 0.5), order="c1"), np.array([55.0])
    r, jac, _, error = _varpro_jacobian(problem, _whole(problem), x, problem.lower, problem.upper)
    assert np.linalg.norm(r) > 10
    assert np.all(error <= 1e-10 * np.abs(jac).max())  # a rounding allowance only (round 19)
    for i in range(len(x)):

        def along(v: float, i: int = i) -> np.ndarray:
            shifted = x.copy()
            shifted[i] = v
            return problem.profile_residual(shifted)

        reference = reference_derivative(along, float(x[i]), h=1e-3)
        np.testing.assert_allclose(jac[:, i], reference, rtol=0, atol=1e-7 * np.abs(reference).max())


def test_profiles_agree_with_analytic_and_differenced_derivatives_for_two_parameters() -> None:
    analytic, differenced = two_parameter_problem(), two_parameter_problem(analytic=False)
    a, d = fit(analytic), fit(differenced)
    np.testing.assert_allclose(a.theta, d.theta, atol=1e-8)
    for name in ("a", "u"):
        ia, id_ = profile_interval(analytic, a, name), profile_interval(differenced, d, name)
        assert ia.supported and id_.supported
        assert ia.lower == pytest.approx(id_.lower, abs=1e-7) and ia.upper == pytest.approx(id_.upper, abs=1e-7)


# --------------------------------------------------------------------------- round 19 counterexamples
def test_analytic_rounding_never_invents_a_joint_rank() -> None:
    """Round 19, finding 1: D(x)·[1, 1] = y for every x, so x is unidentified (joint rank 2).

    The ∂D columns cancel on the exact t, but the computed t carries rounding, which the large ∂D
    amplifies into a spurious singular value of about 1e-7. A zero error estimate counted it,
    gave joint rank 3 and a finite stderr of about 8e6.
    """
    a = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    c = np.array([0.0, 1.0, -1.0, 2.0, -2.0, 3.0])
    b = np.array([-5.0, 1.0, 1.0, 0.0, 0.0, 0.0])
    scale = 1e8

    def design(theta: np.ndarray) -> np.ndarray:
        return np.column_stack([a + scale * theta[0] * b, c - scale * theta[0] * b])

    problem = Problem(
        design=design,
        design_derivative=lambda theta: np.column_stack([scale * b, -scale * b])[None],
        y=a + c,
        sigma=np.ones(6),
        lower=np.array([-1 / scale]),
        upper=np.array([1 / scale]),
        theta_names=("x",),
        order_names=("u", "v"),
    )
    for p in (problem, dataclasses.replace(problem, design_derivative=None)):
        result = fit(p, Settings(grid=np.array([0.0])))
        assert result.validity.joint_rank == 2 and not result.validity.regular
        assert result.covariance is None and result.nu is None


@pytest.mark.parametrize("frame", FRAMES)
def test_the_ring_b_relabelling_maps(frame: str) -> None:
    """Round 19, finding 2: (180° ∓ φ) ≡ φ only with the ring-B relabelling and the tensor map."""
    s5 = np.array([0.25, 0.03, 0.02, -0.01, 0.015])
    images = tuple((RING_B_RELABELLING[i], RING_B_RELABELLING[j]) for i, j in ALL_PAIRS)
    for phi in (12.0, 37.0, 80.0):
        reference = rigid_design(phi, ALL_PAIRS, order="c1", frame=frame) @ s5  # type: ignore[arg-type]
        for kind, angle in (("180-phi", 180.0 - phi), ("180+phi", 180.0 + phi)):
            m = RELABELLING_MAPS[frame][kind]
            mapped = rigid_design(angle, images, order="c1", frame=frame) @ (m @ s5)  # type: ignore[arg-type]
            np.testing.assert_allclose(mapped, reference, rtol=0, atol=1e-9 * np.abs(reference).max())


@pytest.mark.parametrize("order", ORDER_MODELS)
def test_an_obtuse_torsion_needs_the_fixed_label_domain(order: str) -> None:
    """Round 19, finding 2: with fixed labels, a 143° torsion is out of reach of the acute domain;
    the fit sits at the 90° bound with a note, and the fixed-label domain recovers it."""
    s5 = np.array([0.25, 0.03, 0.02, -0.01, 0.015])
    p = len(rigid_problem(((0, 1),), np.ones(1), np.ones(1), order=order).order_names)
    y = rigid_design(143.0, ALL_PAIRS, order=order) @ s5[:p]  # type: ignore[arg-type]
    sigma = np.full(len(y), 0.5)
    acute = fit(rigid_problem(ALL_PAIRS, y, sigma, order=order))
    assert acute.theta[0] == pytest.approx(90.0) and acute.chi2 > 1e3
    assert ACUTE_BOUND_NOTE in acute.notes
    fixed = fit(rigid_problem(ALL_PAIRS, y, sigma, order=order, domain="fixed-labels"))
    assert fixed.theta[0] == pytest.approx(143.0, abs=1e-8) and fixed.chi2 < 1e-12
    np.testing.assert_allclose(fixed.order, s5[:p], rtol=0, atol=1e-8)
    assert fixed.validity.regular and fixed.notes == ()


def test_wider_order_models_break_the_template_d2_symmetry() -> None:
    """Round 19, finding 3 (documented): Sxy alone gives D2-related pairs opposite couplings."""
    index = {label: i for i, label in enumerate(PROTON_LABELS)}
    pairs = ((index["H2"], index["H6"]), (index["H2'"], index["H6'"]))
    d = rigid_design(37.0, pairs, order="c2z") @ [0.0, 0.0, 0.02]
    assert d[0] == pytest.approx(-d[1]) and abs(d[0]) > 1.0


def test_an_unknown_domain_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown domain"):
        rigid_problem(((0, 1),), np.ones(1), np.ones(1), domain="obtuse")  # type: ignore[arg-type]


@pytest.mark.parametrize(("gap", "residual"), [(1e-6, 0.0), (1e-7, 0.0), (1e-8, 0.0), (1e-5, 100.0), (1e-6, 100.0)])
@pytest.mark.parametrize("analytic", [True, False])
def test_the_inner_solve_error_never_invents_a_joint_rank(gap: float, residual: float, analytic: bool) -> None:
    """Round 19 follow-up: the same unidentified x, now with an ill-conditioned inner design.

    Here ∂D is small, so the contraction's own rounding is negligible. But t* carries an error of
    about ε·κ along t₁ − t₂, exactly the direction the ∂D columns read. Without the inner-solve
    allowance, both derivative paths reported joint rank 3 and regular = True. That included the
    finite-difference path of step 1. A residual orthogonal to every column (x stays unidentified)
    adds the κ²‖r‖ part of the error.
    """
    a = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    c = np.array([0.0, 1.0, -1.0, 2.0, -2.0, 3.0])
    b = np.array([-5.0, 1.0, 1.0, 0.0, 0.0, 0.0])
    perpendicular = np.linalg.qr(np.column_stack([a, b, c]), mode="complete")[0][:, 3]

    def design(theta: np.ndarray) -> np.ndarray:
        return np.column_stack([a + theta[0] * b, a + gap * c - theta[0] * b])

    problem = Problem(
        design=design,
        design_derivative=(lambda theta: np.column_stack([b, -b])[None]) if analytic else None,
        y=design(np.zeros(1)) @ np.ones(2) + residual * perpendicular,
        sigma=np.ones(6),
        lower=np.array([-1e-3]),
        upper=np.array([1e-3]),
        theta_names=("x",),
        order_names=("u", "v"),
    )
    result = fit(problem, Settings(grid=np.array([0.0])))
    assert result.validity.inner_rank == 2
    assert result.validity.joint_rank == 2 and not result.validity.regular and result.covariance is None


@pytest.mark.parametrize("scale", [1.0, 1e-7])
@pytest.mark.parametrize("analytic", [True, False])
def test_a_small_but_exact_order_direction_keeps_its_rank(scale: float, analytic: bool) -> None:
    """Round 20: D = [a, g·(c + x·b)] with orthonormal a, b, c and y = a + c, σ = 0.001. At x = 0,
    t = (1, 1/g) and the joint singular values are (1000, 1000, 1e-4·(g/1e-7)): all identifiable.

    The round-19 allowance (‖E‖ ≈ 1.8e-5 for g = 1e-7) once cut every singular value below
    TRUST_FACTOR·‖E‖. That discarded the exact order direction v and reported rank 2. Now only the
    geometry's information beyond the order span is judged against E.
    """
    a, c, b = np.eye(6)[:3]
    problem = Problem(
        design=lambda x: np.column_stack([a, scale * (c + x[0] * b)]),
        design_derivative=(lambda x: np.column_stack([0 * a, scale * b])[None]) if analytic else None,
        y=a + c,
        sigma=np.full(6, 0.001),
        lower=np.array([-0.1]),
        upper=np.array([0.1]),
        theta_names=("x",),
        order_names=("u", "v"),
    )
    result = fit(problem, Settings(grid=np.array([0.0])))
    assert result.validity.joint_rank == 3 and result.validity.regular
    assert result.uncertain == () and result.covariance is not None
    assert result.covariance.stderr[0] == pytest.approx(0.001, rel=1e-6)
