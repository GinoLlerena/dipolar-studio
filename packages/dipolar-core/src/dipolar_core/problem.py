"""The separable least-squares problem of the D3 stack (see ``dipolar_core.fit``).

Kept apart from the fitter so that building a problem does not import SciPy's optimizer, which
would slow every process start; the fitter imports it when it fits.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from dipolar_core.inference import InnerSolution, solve_inner

Array = NDArray[np.float64]
DesignFunction = Callable[[Array], Array]


@dataclass(frozen=True)
class Problem:
    """y ≈ design(θ) · t with known diagonal σ, θ within finite bounds.

    ``s5_map`` maps t onto the five ``ORDER_BASIS`` components (the constraint C), so that the
    admissibility of the fitted order matrix can be checked; None skips that check.
    """

    design: DesignFunction
    y: Array
    sigma: Array
    lower: Array
    upper: Array
    theta_names: tuple[str, ...]
    order_names: tuple[str, ...]
    s5_map: Array | None = None

    def __post_init__(self) -> None:
        k, n = len(self.theta_names), len(self.y)
        if self.lower.shape != (k,) or self.upper.shape != (k,):
            raise ValueError("bounds must have one entry per geometry parameter")
        if not (np.all(np.isfinite(self.lower)) and np.all(np.isfinite(self.upper))):
            raise ValueError("geometry bounds must be finite")
        if np.any(self.lower >= self.upper):
            raise ValueError("every lower bound must be below its upper bound")
        if self.sigma.shape != (n,) or np.any(self.sigma <= 0):
            raise ValueError("sigma must be positive, one per observation")
        if self.s5_map is not None and self.s5_map.shape != (5, len(self.order_names)):
            raise ValueError("s5_map must be 5 × (number of order parameters)")

    @property
    def names(self) -> tuple[str, ...]:
        return self.theta_names + self.order_names

    @property
    def k(self) -> int:
        return len(self.theta_names)

    @property
    def p(self) -> int:
        return len(self.order_names)

    def checked_design(self, theta: Array) -> Array:
        d = np.asarray(self.design(np.asarray(theta, dtype=np.float64)), dtype=np.float64)
        if d.shape != (len(self.y), self.p):
            raise ValueError(f"design returned shape {d.shape}, expected {(len(self.y), self.p)}")
        return d

    def inner(self, theta: Array) -> InnerSolution:
        return solve_inner(self.checked_design(theta), self.y, self.sigma)

    def profile_residual(self, theta: Array) -> Array:
        """Whitened residual at the inner optimum (the VarPro residual vector)."""
        sol = self.inner(theta)
        residual: Array = -sol.residuals / self.sigma
        return residual

    def joint_residual(self, theta: Array, t: Array) -> Array:
        residual: Array = (self.checked_design(theta) @ t - self.y) / self.sigma
        return residual
