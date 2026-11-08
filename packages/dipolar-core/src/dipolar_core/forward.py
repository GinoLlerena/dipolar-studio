"""Cartesian forward model for dipolar couplings (plan D3.1, D7).

For a spin pair with internuclear unit vector c (molecule frame) and distance r,

    D = K / r³ · Σ_ab S_ab c_a c_b

with S the traceless symmetric Saupe order matrix. S is parameterised by five independent
components in ``ORDER_BASIS``; a model's constraint matrix C maps its free order parameters t
onto those five, so the design is ``A·C`` and the prediction is ``A·C·t``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

import numpy as np
from numpy.typing import NDArray

Array = NDArray[np.float64]

#: The five independent components of a traceless symmetric S.
ORDER_BASIS: Final = ("Szz", "Sxx-Syy", "Sxy", "Sxz", "Syz")


def design_rows(positions: Array, pairs: Sequence[tuple[int, int]], k_hz_a3: float) -> Array:
    """Return the N×5 design matrix: D = rows @ s5 for the five components of ``ORDER_BASIS``."""
    if not pairs:
        raise ValueError("at least one spin pair is required")
    idx = np.asarray(pairs, dtype=np.intp)
    if idx.ndim != 2 or idx.shape[1] != 2:
        raise ValueError("pairs must be a sequence of (i, j) index tuples")
    if np.any(idx[:, 0] == idx[:, 1]):
        raise ValueError("a spin cannot couple to itself")
    vectors = positions[idx[:, 1]] - positions[idx[:, 0]]
    r = np.linalg.norm(vectors, axis=1)
    if np.any(r <= 0):
        raise ValueError("coincident spins")
    cx, cy, cz = (vectors / r[:, None]).T
    scale = k_hz_a3 / r**3
    rows: Array = scale[:, None] * np.column_stack(
        (
            (3 * cz**2 - 1) / 2,  # Szz
            (cx**2 - cy**2) / 2,  # Sxx − Syy
            2 * cx * cy,  # Sxy
            2 * cx * cz,  # Sxz
            2 * cy * cz,  # Syz
        )
    )
    return rows


def constraint_diagonal() -> Array:
    """C for a tensor diagonal in the molecule frame: free parameters (Szz, Δ = Sxx − Syy)."""
    c = np.zeros((5, 2))
    c[0, 0] = 1.0
    c[1, 1] = 1.0
    return c


def order_matrix(s5: Array) -> Array:
    """Assemble the 3×3 traceless symmetric S from its five ``ORDER_BASIS`` components."""
    szz, delta, sxy, sxz, syz = (float(v) for v in s5)
    sxx = (delta - szz) / 2
    syy = (-delta - szz) / 2
    return np.array([[sxx, sxy, sxz], [sxy, syy, syz], [sxz, syz, szz]])
