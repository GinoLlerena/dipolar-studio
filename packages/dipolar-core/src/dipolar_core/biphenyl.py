"""Biphenyl template geometry (plan D4: fixed template coordinates with one permitted torsion).

Frame: the *bisector frame* of the synthetic dataset.

* z runs along the inter-ring axis C4–C1–C1′–C4′; ring A is on the z < 0 side.
* x bisects the two ring planes, and y = z × x.
* Ring A spans z and u_A = (cos φ/2, +sin φ/2, 0); ring B spans z and u_B = (cos φ/2, −sin φ/2, 0).
  The inter-ring dihedral is therefore φ.

The rings are regular hexagons. Protons sit on C2…C6 of each ring, on the ray from the ring
centre through the carbon, at distance r_cc + r_ch from the centre.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import NDArray

from dipolar_core.forward import constraint_diagonal, design_rows
from dipolar_core.nuclides import dipolar_constant_hz_a3
from dipolar_core.problem import Problem

Array = NDArray[np.float64]

#: Display labels of the ten protons, in template order (ring A, then ring B).
PROTON_LABELS: Final = ("H2", "H3", "H4", "H5", "H6", "H2'", "H3'", "H4'", "H5'", "H6'")


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


def rigid_design(
    phi_deg: float,
    pairs: tuple[tuple[int, int], ...],
    geometry: BiphenylGeometry | None = None,
) -> Array:
    """Design A·C of the rigid model: one conformer, S diagonal in the bisector frame (Szz, Δ)."""
    k = dipolar_constant_hz_a3("1H", "1H")
    return design_rows(proton_positions(phi_deg, geometry), pairs, k) @ constraint_diagonal()


def rigid_problem(
    pairs: tuple[tuple[int, int], ...],
    y: Array,
    sigma: Array,
    geometry: BiphenylGeometry | None = None,
) -> Problem:
    """The rigid model as a D3 problem: φ in [0°, 90°] (the folded domain), (Szz, Δ) linear."""
    g = geometry or BiphenylGeometry()
    return Problem(
        design=lambda theta: rigid_design(float(theta[0]), pairs, g),
        y=np.asarray(y, dtype=np.float64),
        sigma=np.asarray(sigma, dtype=np.float64),
        lower=np.array([0.0]),
        upper=np.array([90.0]),
        theta_names=("phi_deg",),
        order_names=("Szz", "Delta"),
        s5_map=constraint_diagonal(),
    )
