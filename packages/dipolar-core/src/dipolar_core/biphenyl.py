"""Biphenyl template geometry (plan D4: fixed template coordinates with one permitted torsion).

**The frozen frame contract (plan D12, M1).**

1. *Rotation.* Building the geometry turns the rings *actively*. Changing frame is *passive*
   (``dipolar_core.forward.frame_change``): coordinates and S are re-expressed together, and the
   couplings do not change (contraction invariance).
2. *Axes.* Two frames are declared:
   - ``"bisector"`` (the frame of the frozen fixture): z runs along the inter-ring axis
     C4–C1–C1′–C4′ with ring A on the z < 0 side; x bisects the two ring planes; y = z × x. Ring A
     spans z and u_A = (cos φ/2, +sin φ/2, 0), ring B spans z and u_B = (cos φ/2, −sin φ/2, 0).
   - ``"ring-a"``: the same z; x = u_A, which lies in ring A's plane on the C2 side; y = z × x.
     Ring A is fixed in this frame, and the bisector sits at angle −φ/2 from its x axis.
3. *Torsion sign and domain.* φ is the inter-ring dihedral. The signed IUPAC dihedral
   τ(C2–C1–C1′–C2′) of this template is −φ.
   - The reflection y → −y maps φ to −φ at fixed labels. It negates Sxy and Syz and leaves the
     other components unchanged. So ``domain="fixed-labels"``, φ ∈ [0°, 180°], is complete for
     every order model.
   - (180° ± φ) is equivalent to φ only together with the ring-B relabelling
     ``RING_B_RELABELLING`` (H2′↔H6′, H3′↔H5′, applied to both ends of every pair) *and* the
     tensor map ``RELABELLING_MAPS[frame][...]`` (round 19). In the bisector frame, with
     s = (Szz, Δ, Sxy, Sxz, Syz): 180° − φ gives (Szz, −Δ, Sxy, Syz, Sxz), and 180° + φ gives
     (Szz, −Δ, −Sxy, −Syz, Sxz).
   - ``domain="acute"``, φ ∈ [0°, 90°], is the frozen fixture's domain and the default. It is
     complete only when ring B's labels have been assigned so that the torsion is acute (a
     precondition on the input). If they were not, the fit can stop at the 90° bound, where it
     gets the note ``ACUTE_BOUND_NOTE``. It can also land on a wrong acute optimum with no note:
     for example, bisector-diagonal data at 137° fit to 34.6° with a large χ² (round 20). The
     note cannot detect wrong labels in general. The χ² and the residuals can.
4. *Constraint basis C(g)*, in ``ORDER_MODELS``. Each maps the free order parameters t onto the
   five ``ORDER_BASIS`` components in the declared frame:
   - ``"bisector-diagonal"`` (legacy alias "D4"): S is diagonal in the bisector frame, with
     t = (Szz, Δ′) and Δ′ = Sxx − Syy there. In the bisector frame C is constant. In the ring-A
     frame it is the moving-bisector form with δ = −φ = τ: Δ = Δ′ cos δ and Sxy = ½Δ′ sin δ.
     That form is regular for every δ. Its δ-derivative is part of the analytic Jacobian.
   - ``"c2z"`` (legacy alias "D2"): t = (Szz, Delta, Sxy) in the declared frame, with
     Delta = Sxx − Syy.
   - ``"c1"``: all five components in the declared frame.

**Scale anchor.** The template's bond lengths are fixed, so the scale freedom r → λr, S → λ³S of
plan D12 is already removed.

**The D2d endpoint (labelled, not enforced).** At φ = 90° the two identical rings have D2d
symmetry, and S4 about z forces S to be uniaxial about z. The data still constrain Δ′ (and Sxy,
Sxz, Syz) there through the individual couplings. So a fit that lands at φ = 90° reports them,
with a note (``D2D_NOTE``) that a nonzero value is phenomenological. The note applies to this
declared identical-ring template only, never to arbitrary imported geometry.

The rings are regular hexagons. Protons sit on C2…C6 of each ring, on the ray from the ring
centre through the carbon, at distance r_cc + r_ch from the centre.

**The symmetric four-site jump** (``jump_problem``, plan §4). Fast exchange among the conformers
+φ, −φ, 180° − φ and 180° + φ, with equal populations. They share one tensor, diagonal in each
conformer's own *acute*-bisector frame, with t = (Szz, Δ). The predicted coupling is the average
over the four conformers.
- **The shortcut.** By ``RELABELLING_MAPS``, the 180° ∓ φ conformers equal the ±φ conformer
  with ring B relabelled. So the design is ½·[D(φ, pairs) + D(φ, relabelled pairs)]
  (``jump_design``). ``jump_design_explicit`` averages the four conformers directly, as an
  independent check (gate (e)).
- **The domain.** The conformer set is unchanged by φ → −φ and φ → 180° − φ. So φ ∈ [0°, 90°] is
  complete at fixed labels, with no label precondition. The model is also invariant under the
  ring-B relabelling.
- **The 90° endpoint.** The acute bisector is undefined there. The model is the continuous limit,
  in which the Δ column vanishes: Δ is unidentified at 90°, as D2d symmetry requires, and the
  inner rank reports it.
- **The estimand** is the "jump-model phi". It is not the rigid effective φ, and not the most
  probable angle of a continuous distribution.

The observations must be independent under the model's own symmetry. The fixture's equivalence
classes (``couplings.csv``, ``equivalent_pairs``) are those of a D2-symmetric molecule and tensor.
They are valid for ``"bisector-diagonal"`` and not for ``"c2z"`` or ``"c1"``.

``"c2z"`` and ``"c1"`` are reference models. They do not impose the D2 symmetry (C2 about x, y
and z) of the identical-ring template. With this template, a nonzero Sxy, Sxz or Syz *in the
bisector frame* (the D2 symmetry axes), at any torsion, describes a tensor less symmetric than
the molecule. For example, Sxy alone gives H2–H6 and H2′–H6′ couplings of opposite sign,
although D2 relates those pairs. Such values are phenomenological, just as Δ′ is at the D2d
endpoint (round 19). In the ring-A frame, a D2-symmetric tensor already has Sxy = ½Δ′ sin δ ≠ 0
(round 20).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final, Literal

import numpy as np
from numpy.typing import NDArray

from dipolar_core.forward import (
    constraint_c1,
    constraint_c2z,
    constraint_diagonal,
    constraint_moving_bisector,
    constraint_moving_bisector_derivative,
    design_rows,
    design_rows_derivative,
    frame_change,
)
from dipolar_core.nuclides import dipolar_constant_hz_a3
from dipolar_core.problem import Problem

Array = NDArray[np.float64]

#: Display labels of the ten protons, in template order (ring A, then ring B).
PROTON_LABELS: Final = ("H2", "H3", "H4", "H5", "H6", "H2'", "H3'", "H4'", "H5'", "H6'")

OrderModel = Literal["bisector-diagonal", "c2z", "c1"]
Frame = Literal["bisector", "ring-a"]
ORDER_MODELS: Final = ("bisector-diagonal", "c2z", "c1")
FRAMES: Final = ("bisector", "ring-a")
#: The 1998 names, accepted as aliases only (plan D12).
LEGACY_ALIASES: Final = {"D4": "bisector-diagonal", "D2": "c2z"}
ORDER_NAMES: Final = {
    "bisector-diagonal": ("Szz", "Delta"),
    "c2z": ("Szz", "Delta", "Sxy"),
    "c1": ("Szz", "Delta", "Sxy", "Sxz", "Syz"),
}
Domain = Literal["acute", "fixed-labels"]
DOMAINS: Final = {"acute": (0.0, 90.0), "fixed-labels": (0.0, 180.0)}
#: H2′↔H6′, H3′↔H5′: the ring-B relabelling, as a permutation of template indices.
RING_B_RELABELLING: Final = (0, 1, 2, 3, 4, 9, 8, 7, 6, 5)
#: The 5 × 5 maps on ORDER_BASIS that go with RING_B_RELABELLING. D at (φ, pairs, s) equals D at
#: (180° ∓ φ, relabelled pairs, M·s) for M = RELABELLING_MAPS[frame]["180-phi" or "180+phi"].
RELABELLING_MAPS: Final = {
    "bisector": {
        "180-phi": np.array(
            [[1, 0, 0, 0, 0], [0, -1, 0, 0, 0], [0, 0, 1, 0, 0], [0, 0, 0, 0, 1], [0, 0, 0, 1, 0]], float
        ),
        "180+phi": np.array(
            [[1, 0, 0, 0, 0], [0, -1, 0, 0, 0], [0, 0, -1, 0, 0], [0, 0, 0, 0, -1], [0, 0, 0, 1, 0]], float
        ),
    },
    "ring-a": {"180-phi": np.diag([1.0, 1.0, -1.0, 1.0, -1.0]), "180+phi": np.eye(5)},
}
ACUTE_BOUND_NOTE: Final = (
    "at the 90 deg bound of the acute domain: this domain assumes ring-B labels assigned so that "
    "the torsion is acute; with fixed labels refit with domain='fixed-labels', or relabel "
    "H2'<->H6', H3'<->H5'"
)
RIGID_ESTIMAND: Final = "rigid effective phi"
JUMP_ESTIMAND: Final = "jump-model phi"
D2D_NOTE: Final = (
    "D2d endpoint: at phi = 90 deg the identical rings have D2d symmetry, which forces S to be "
    "uniaxial about z; nonzero Delta, Sxy, Sxz or Syz there is phenomenological"
)
_DEG: Final = math.pi / 180.0


@dataclass(frozen=True, slots=True)
class BiphenylGeometry:
    """Bond lengths of the rigid template, in Å."""

    r_cc: float = 1.397
    r_ch: float = 1.084
    r_inter: float = 1.489

    def __post_init__(self) -> None:
        for name in ("r_cc", "r_ch", "r_inter"):
            value = getattr(self, name)
            if not (math.isfinite(value) and value > 0):
                raise ValueError(f"{name} must be a positive finite length in Å, got {value!r}")


def proton_positions(phi_deg: float, geometry: BiphenylGeometry | None = None) -> Array:
    """Return the 10×3 proton coordinates (Å, order of ``PROTON_LABELS``) at torsion φ (degrees)."""
    if not math.isfinite(phi_deg):
        raise ValueError("phi_deg must be finite")
    g = geometry or BiphenylGeometry()
    half = math.radians(phi_deg) / 2.0
    z_axis = np.array([0.0, 0.0, 1.0])
    coords = np.empty((10, 3), dtype=np.float64)
    ring_angles = np.radians(60.0 * np.arange(1, 6))  # C2..C6, measured from the C1 direction
    for ring, side in enumerate((-1.0, +1.0)):  # ring A at z < 0, ring B at z > 0
        in_plane = np.array([math.cos(half), -side * math.sin(half), 0.0])
        centre = side * (g.r_inter / 2.0 + g.r_cc) * z_axis
        to_c1 = -side * z_axis
        directions = np.outer(np.cos(ring_angles), to_c1) + np.outer(np.sin(ring_angles), in_plane)
        coords[5 * ring : 5 * ring + 5] = centre + (g.r_cc + g.r_ch) * directions
    return coords


def proton_positions_derivative(phi_deg: float, geometry: BiphenylGeometry | None = None) -> Array:
    """∂ ``proton_positions`` / ∂φ, per degree, in the bisector frame (10 × 3, analytic)."""
    if not math.isfinite(phi_deg):
        raise ValueError("phi_deg must be finite")
    g = geometry or BiphenylGeometry()
    half = math.radians(phi_deg) / 2.0
    out = np.empty((10, 3), dtype=np.float64)
    ring_angles = np.radians(60.0 * np.arange(1, 6))
    for ring, side in enumerate((-1.0, +1.0)):
        d_in_plane = 0.5 * _DEG * np.array([-math.sin(half), -side * math.cos(half), 0.0])
        out[5 * ring : 5 * ring + 5] = (g.r_cc + g.r_ch) * np.outer(np.sin(ring_angles), d_in_plane)
    return out


def frame_axes(phi_deg: float, frame: Frame) -> tuple[Array, Array]:
    """(axes, ∂axes/∂φ per degree): the rows are the declared frame's axes in bisector coordinates."""
    if frame == "bisector":
        return np.eye(3), np.zeros((3, 3))
    if frame != "ring-a":
        raise ValueError(f"unknown frame {frame!r}; expected one of {FRAMES}")
    half = math.radians(phi_deg) / 2.0
    c, s = math.cos(half), math.sin(half)
    axes = np.array([[c, s, 0.0], [-s, c, 0.0], [0.0, 0.0, 1.0]])
    d_axes = 0.5 * _DEG * np.array([[-s, c, 0.0], [-c, -s, 0.0], [0.0, 0.0, 0.0]])
    return axes, d_axes


def resolve_order_model(order: str) -> OrderModel:
    """The canonical model name; the legacy names "D4" and "D2" are aliases only."""
    name = LEGACY_ALIASES.get(order, order)
    if name not in ORDER_MODELS:
        raise ValueError(f"unknown order model {order!r}; expected one of {ORDER_MODELS} or {tuple(LEGACY_ALIASES)}")
    return name  # type: ignore[return-value]


def constraint(phi_deg: float, order: OrderModel, frame: Frame) -> tuple[Array, Array]:
    """(C, ∂C/∂φ per degree) of an order model in a declared frame (the constraint basis C(g))."""
    if order == "c2z":
        c = constraint_c2z()
    elif order == "c1":
        c = constraint_c1()
    elif frame == "ring-a":  # the moving bisector: δ = −φ
        delta = -math.radians(phi_deg)
        return constraint_moving_bisector(delta), -_DEG * constraint_moving_bisector_derivative(delta)
    else:
        c = constraint_diagonal()
    return c, np.zeros_like(c)


def rigid_design(
    phi_deg: float,
    pairs: tuple[tuple[int, int], ...],
    geometry: BiphenylGeometry | None = None,
    *,
    order: OrderModel = "bisector-diagonal",
    frame: Frame = "bisector",
) -> Array:
    """Design A·C of the rigid model (one conformer) for an order model in a declared frame."""
    axes, _ = frame_axes(phi_deg, frame)
    c, _ = constraint(phi_deg, order, frame)
    k = dipolar_constant_hz_a3("1H", "1H")
    return design_rows(frame_change(axes, proton_positions(phi_deg, geometry)), pairs, k) @ c


def rigid_design_derivative(
    phi_deg: float,
    pairs: tuple[tuple[int, int], ...],
    geometry: BiphenylGeometry | None = None,
    *,
    order: OrderModel = "bisector-diagonal",
    frame: Frame = "bisector",
) -> Array:
    """∂(A·C)/∂φ per degree, analytic: ∂A·C + A·∂C, including the frame's own rotation."""
    axes, d_axes = frame_axes(phi_deg, frame)
    c, d_c = constraint(phi_deg, order, frame)
    k = dipolar_constant_hz_a3("1H", "1H")
    positions = proton_positions(phi_deg, geometry)
    framed = frame_change(axes, positions)
    d_framed = frame_change(axes, proton_positions_derivative(phi_deg, geometry)) + frame_change(d_axes, positions)
    d_rows = design_rows_derivative(framed, d_framed[None], pairs, k)[0]
    out: Array = d_rows @ c + design_rows(framed, pairs, k) @ d_c
    return out


def relabel_ring_b(pairs: tuple[tuple[int, int], ...]) -> tuple[tuple[int, int], ...]:
    """Apply ``RING_B_RELABELLING`` (H2′↔H6′, H3′↔H5′) to both endpoints of every pair."""
    return tuple((RING_B_RELABELLING[i], RING_B_RELABELLING[j]) for i, j in pairs)


def jump_design(phi_deg: float, pairs: tuple[tuple[int, int], ...], geometry: BiphenylGeometry | None = None) -> Array:
    """Design of the symmetric four-site jump (the relabelling shortcut): N × 2, t = (Szz, Δ)."""
    return 0.5 * (rigid_design(phi_deg, pairs, geometry) + rigid_design(phi_deg, relabel_ring_b(pairs), geometry))


def jump_design_derivative(
    phi_deg: float, pairs: tuple[tuple[int, int], ...], geometry: BiphenylGeometry | None = None
) -> Array:
    """∂ ``jump_design`` / ∂φ per degree, analytic."""
    return 0.5 * (
        rigid_design_derivative(phi_deg, pairs, geometry)
        + rigid_design_derivative(phi_deg, relabel_ring_b(pairs), geometry)
    )


def jump_design_explicit(
    phi_deg: float, pairs: tuple[tuple[int, int], ...], geometry: BiphenylGeometry | None = None
) -> Array:
    """The four conformers averaged explicitly, each with the tensor diagonal in its own acute
    bisector frame (gate (e)). Valid for 0° < φ < 90°, where the acute bisector is defined.

    Conformer θ is ``proton_positions(θ)``. Its x axis bisects the ring planes, and that is the
    acute bisector when cos θ > 0. Otherwise the acute bisector is y, and Δ changes sign there.
    """
    if not 0.0 < phi_deg < 90.0:
        raise ValueError("the explicit average needs 0 < phi < 90 (the acute bisector is undefined at 90)")
    total = np.zeros((len(pairs), 2))
    for theta in (phi_deg, -phi_deg, 180.0 - phi_deg, 180.0 + phi_deg):
        acute = 1.0 if math.cos(math.radians(theta)) > 0 else -1.0
        total += rigid_design(theta, pairs, geometry) @ np.diag([1.0, acute])
    out: Array = total / 4
    return out


def jump_problem(
    pairs: tuple[tuple[int, int], ...],
    y: Array,
    sigma: Array,
    geometry: BiphenylGeometry | None = None,
) -> Problem:
    """The symmetric four-site jump as a D3 problem: φ in [0°, 90°] (complete at fixed labels),
    (Szz, Δ) linear, with the analytic φ-derivative of the design."""
    g = geometry or BiphenylGeometry()
    return Problem(
        design=lambda theta: jump_design(float(theta[0]), pairs, g),
        design_derivative=lambda theta: jump_design_derivative(float(theta[0]), pairs, g)[None],
        y=np.asarray(y, dtype=np.float64),
        sigma=np.asarray(sigma, dtype=np.float64),
        lower=np.array([0.0]),
        upper=np.array([90.0]),
        theta_names=("phi_deg",),
        order_names=ORDER_NAMES["bisector-diagonal"],
        s5_map=constraint_diagonal(),  # each conformer's tensor, in its own acute-bisector frame
        estimand=JUMP_ESTIMAND,
    )


def at_d2d_endpoint(phi_deg: float) -> bool:
    """True at the D2d endpoint φ = 90°, within 1e-9 relative (the fitter's bound tolerance)."""
    return abs(phi_deg - 90.0) <= 1e-9 * 90.0


def rigid_problem(
    pairs: tuple[tuple[int, int], ...],
    y: Array,
    sigma: Array,
    geometry: BiphenylGeometry | None = None,
    *,
    order: str = "bisector-diagonal",
    frame: Frame = "bisector",
    domain: Domain = "acute",
) -> Problem:
    """The rigid model as a D3 problem: φ in ``DOMAINS[domain]``, the order parameters of
    ``order`` linear, with the analytic φ-derivative of the design."""
    g = geometry or BiphenylGeometry()
    model = resolve_order_model(order)
    frame_axes(0.0, frame)  # validates the frame name
    if domain not in DOMAINS:
        raise ValueError(f"unknown domain {domain!r}; expected one of {tuple(DOMAINS)}")
    lower, upper = DOMAINS[domain]

    def notes(theta: Array) -> tuple[str, ...]:
        phi = float(theta[0])
        out = (D2D_NOTE,) if at_d2d_endpoint(phi) else ()
        return out + ((ACUTE_BOUND_NOTE,) if domain == "acute" and at_d2d_endpoint(phi) else ())

    s5_map = {"bisector-diagonal": constraint_diagonal(), "c2z": constraint_c2z(), "c1": constraint_c1()}[model]
    return Problem(
        design=lambda theta: rigid_design(float(theta[0]), pairs, g, order=model, frame=frame),
        design_derivative=lambda theta: rigid_design_derivative(float(theta[0]), pairs, g, order=model, frame=frame)[
            None
        ],
        notes=notes,
        y=np.asarray(y, dtype=np.float64),
        sigma=np.asarray(sigma, dtype=np.float64),
        lower=np.array([lower]),
        upper=np.array([upper]),
        theta_names=("phi_deg",),
        order_names=ORDER_NAMES[model],
        estimand=RIGID_ESTIMAND,
        # The tensor in *some* frame suffices: admissibility depends only on the eigenvalues. For
        # "bisector-diagonal", t gives S in the bisector frame whatever the declared frame.
        s5_map=s5_map,
    )
