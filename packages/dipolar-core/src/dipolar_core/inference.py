"""Whitened inner linear solve and validity flags (plan D3.1, D3.5).

With L = diag(1/σ) (so LᵀL = Σ⁻¹ for a diagonal Σ), B = L·A·C and b = L·y, the order parameters
are t* = argmin ‖B t − b‖², solved by SVD. Normal equations are never formed. Validity flags are
computed independently of each other: inner rank, condition number, physical admissibility.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import NDArray

from dipolar_core.forward import order_matrix

Array = NDArray[np.float64]

#: Written rank policy: a singular value counts if s > RANK_RTOL · s_max.
RANK_RTOL: Final = 1e-10
#: Written admissibility policy: (2S + I)/3 is accepted if its smallest eigenvalue ≥ −ADMISSIBILITY_ATOL.
ADMISSIBILITY_ATOL: Final = 1e-12


@dataclass(frozen=True, slots=True)
class InnerSolution:
    """Result of the inner solve at fixed geometry."""

    params: Array  # free order parameters t* (minimum-norm if rank-deficient)
    predictions: Array  # A·C·t*, Hz
    residuals: Array  # y − predictions, Hz (unwhitened)
    chi2: float  # ‖L (y − A C t*)‖²
    n_obs: int
    n_params: int
    rank: int
    condition: float  # s_max / s_min of the whitened design (inf if rank-deficient)
    singular_values: Array


def solve_inner(design: Array, y: Array, sigma: Array) -> InnerSolution:
    """Solve the whitened weighted least-squares problem for the order parameters."""
    a = np.asarray(design, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    sigma = np.asarray(sigma, dtype=np.float64)
    if a.ndim != 2 or y.shape != (a.shape[0],) or sigma.shape != y.shape:
        raise ValueError("design must be N×p, and y and sigma must have length N")
    if not (np.all(np.isfinite(a)) and np.all(np.isfinite(y)) and np.all(np.isfinite(sigma))):
        raise ValueError("non-finite input")
    if np.any(sigma <= 0):
        raise ValueError("every sigma must be positive")
    w = 1.0 / sigma
    b_mat = a * w[:, None]
    b_vec = y * w
    u, s, vt = np.linalg.svd(b_mat, full_matrices=False)
    s_max = float(s[0]) if s.size else 0.0
    keep = s > RANK_RTOL * s_max if s_max > 0 else np.zeros_like(s, dtype=bool)
    rank = int(np.count_nonzero(keep))
    coeffs = np.zeros_like(s)
    coeffs[keep] = (u[:, keep].T @ b_vec) / s[keep]
    params = vt.T @ coeffs
    predictions = a @ params
    whitened_residual = b_mat @ params - b_vec
    condition = s_max / float(s[-1]) if rank == a.shape[1] else float("inf")
    return InnerSolution(
        params=params,
        predictions=predictions,
        residuals=y - predictions,
        chi2=float(whitened_residual @ whitened_residual),
        n_obs=a.shape[0],
        n_params=a.shape[1],
        rank=rank,
        condition=condition,
        singular_values=s,
    )


def is_admissible(s5: Array) -> bool:
    """Physical admissibility of an order matrix: (2S + I)/3 must be positive semidefinite."""
    s = order_matrix(s5)
    eigenvalues = np.linalg.eigvalsh((2 * s + np.eye(3)) / 3)
    return bool(eigenvalues.min() >= -ADMISSIBILITY_ATOL)
