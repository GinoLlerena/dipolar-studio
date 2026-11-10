"""Cartesian forward model for dipolar couplings (plan D3.1, D7).

For a spin pair with internuclear unit vector c (molecule frame) and distance r,

    D = K / r³ · Σ_ab S_ab c_a c_b

with S the traceless symmetric Saupe order matrix. S is parameterised by five independent
components in ``ORDER_BASIS``; a model's constraint matrix C maps its free order parameters t
onto those five, so the design is ``A·C`` and the prediction is ``A·C·t``.

**Frames (the frozen frame contract, plan D12).** Coordinates and S are always expressed in the
same frame. Changing frame is *passive*: with ``axes`` the 3 × 3 matrix whose rows are the new
axes in old coordinates, a vector becomes ``axes @ v`` and S becomes ``axes @ S @ axes.T``
(``frame_change``). The contraction cᵀSc, and so every coupling, is unchanged.
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


#: Row k is the symmetric matrix M_k with row_k(v) = vᵀ M_k v / |v|⁵ (times K), for v = r_j − r_i.
_QUADRATIC: Final = np.array(
    [
        [[-0.5, 0, 0], [0, -0.5, 0], [0, 0, 1]],  # Szz: (3 vz² − |v|²) / 2
        [[0.5, 0, 0], [0, -0.5, 0], [0, 0, 0]],  # Sxx − Syy: (vx² − vy²) / 2
        [[0, 1, 0], [1, 0, 0], [0, 0, 0]],  # Sxy: 2 vx vy
        [[0, 0, 1], [0, 0, 0], [1, 0, 0]],  # Sxz: 2 vx vz
        [[0, 0, 0], [0, 0, 1], [0, 1, 0]],  # Syz: 2 vy vz
    ],
    dtype=np.float64,
)


def design_rows_derivative(
    positions: Array, d_positions: Array, pairs: Sequence[tuple[int, int]], k_hz_a3: float
) -> Array:
    """Analytic derivative of ``design_rows`` along m position directions: an m × N × 5 array.

    ``d_positions`` is m × n_spins × 3 (∂positions/∂θ_i for each geometry parameter θ_i). With
    row_k = K·q_k(v)/|v|⁵ and q_k(v) = vᵀ M_k v,

        ∂row_k = K·(2 vᵀ M_k ∂v / |v|⁵ − 5 q_k(v) (v·∂v) / |v|⁷).
    """
    idx = np.asarray(pairs, dtype=np.intp)
    v = positions[idx[:, 1]] - positions[idx[:, 0]]  # N × 3
    dv = d_positions[:, idx[:, 1]] - d_positions[:, idx[:, 0]]  # m × N × 3
    r2 = np.einsum("na,na->n", v, v)
    if np.any(r2 <= 0):
        raise ValueError("coincident spins")
    mv = np.einsum("kab,nb->nka", _QUADRATIC, v)  # M_k v, N × 5 × 3
    q = np.einsum("na,nka->nk", v, mv)  # N × 5
    first = 2 * np.einsum("mna,nka->mnk", dv, mv) / r2[None, :, None] ** 2.5
    second = 5 * q[None] * np.einsum("na,mna->mn", v, dv)[:, :, None] / r2[None, :, None] ** 3.5
    out: Array = k_hz_a3 * (first - second)
    return out


def frame_change(axes: Array, positions: Array) -> Array:
    """Passive change of frame: coordinates of ``positions`` (n × 3) on the rows of ``axes``."""
    out: Array = positions @ axes.T
    return out


def constraint_diagonal() -> Array:
    """C for a tensor diagonal in the molecule frame: free parameters (Szz, Δ = Sxx − Syy)."""
    c = np.zeros((5, 2))
    c[0, 0] = 1.0
    c[1, 1] = 1.0
    return c


def constraint_c2z() -> Array:
    """C for a C2(z)-symmetric tensor (legacy alias "D2"): free (Szz, Sxx − Syy, Sxy).

    A rotation about z maps this subspace onto itself, so the model is the same in every frame
    that shares the z axis; only the values of Sxx − Syy and Sxy depend on the choice of x.
    """
    c = np.zeros((5, 3))
    c[0, 0] = c[1, 1] = c[2, 2] = 1.0
    return c


def constraint_c1() -> Array:
    """C for an unconstrained tensor (no symmetry, C1): the five ``ORDER_BASIS`` components."""
    return np.eye(5)


def constraint_moving_bisector(delta_rad: float) -> Array:
    """C for a tensor diagonal in a frame turned by δ/2 about z (the moving-bisector form).

    Free (Szz, Δ′), Δ′ being Sxx − Syy in the turned frame. In the declared frame:
    Sxx − Syy = Δ′·cos δ and Sxy = ½Δ′·sin δ. This is regular for every δ; the legacy "D4"
    coefficient ½ sin²θ (cos 2ϕ + tan δ · sin 2ϕ) is the same model with Δ_legacy = Δ′·cos δ,
    which diverges at δ = 90° (bug B44).
    """
    c = np.zeros((5, 2))
    c[0, 0] = 1.0
    c[1, 1] = np.cos(delta_rad)
    c[2, 1] = 0.5 * np.sin(delta_rad)
    return c


def constraint_moving_bisector_derivative(delta_rad: float) -> Array:
    """∂C/∂δ (per radian) of ``constraint_moving_bisector``."""
    c = np.zeros((5, 2))
    c[1, 1] = -np.sin(delta_rad)
    c[2, 1] = 0.5 * np.cos(delta_rad)
    return c


def order_vector(s: Array) -> Array:
    """The five ``ORDER_BASIS`` components of a 3 × 3 traceless symmetric S (inverse of ``order_matrix``)."""
    return np.array([s[2, 2], s[0, 0] - s[1, 1], s[0, 1], s[0, 2], s[1, 2]], dtype=np.float64)


def order_matrix(s5: Array) -> Array:
    """Assemble the 3×3 traceless symmetric S from its five ``ORDER_BASIS`` components."""
    szz, delta, sxy, sxz, syz = (float(v) for v in s5)
    sxx = (delta - szz) / 2
    syy = (-delta - szz) / 2
    return np.array([[sxx, sxy, sxz], [sxy, syy, syz], [sxz, syz, szz]])
