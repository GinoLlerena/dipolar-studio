"""The separable least-squares problem of the D3 stack (see ``dipolar_core.fit``).

Kept apart from the fitter so that building a problem does not import SciPy's optimizer, which
would slow every process start; the fitter imports it when it fits.

**Error model (D3.3).** The likelihood is Gaussian with a fixed, positive-definite covariance Σ.
- By default Σ = diag(σ²).
- A full Σ may be supplied for correlated errors, for example couplings from one
  spin-Hamiltonian fit. σ must then equal √diag(Σ).
- With Σ = L·Lᵀ (Cholesky), every residual and design is whitened by W = L⁻¹, consistently, in
  the inner solve, the residual vector and the Jacobian.
- Σ is known and is never rescaled.

Each row must be an independent observation. Rows copied by symmetry are merged by the caller
before they reach a Problem, so that they never inflate N.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from dipolar_core.inference import InnerSolution, solve_inner

Array = NDArray[np.float64]
DesignFunction = Callable[[Array], Array]
NotesFunction = Callable[[Array], tuple[str, ...]]


@dataclass(frozen=True)
class Problem:
    """y ≈ design(θ) · t with known Gaussian errors, θ within finite bounds.

    ``s5_map`` maps t onto the five ``ORDER_BASIS`` components (the constraint C), so that the
    admissibility of the fitted order matrix can be checked; None skips that check.

    ``design_derivative``, when given, returns the analytic ∂D/∂θ as a k × N × p array, and the
    fitter uses it in place of finite differences. ``notes`` returns model-specific labels for a
    fitted θ, for example the D2d endpoint of the biphenyl template.
    """

    design: DesignFunction
    y: Array
    sigma: Array
    lower: Array
    upper: Array
    theta_names: tuple[str, ...]
    order_names: tuple[str, ...]
    s5_map: Array | None = None
    covariance: Array | None = None
    design_derivative: DesignFunction | None = None
    notes: NotesFunction | None = None
    _whitener: Array | None = field(init=False, repr=False, compare=False, default=None)

    def __post_init__(self) -> None:
        k, n = len(self.theta_names), len(self.y)
        if self.y.ndim != 1 or not np.all(np.isfinite(self.y)):
            raise ValueError("y must be a finite vector")
        if self.lower.shape != (k,) or self.upper.shape != (k,):
            raise ValueError("bounds must have one entry per geometry parameter")
        if not (np.all(np.isfinite(self.lower)) and np.all(np.isfinite(self.upper))):
            raise ValueError("geometry bounds must be finite")
        if np.any(self.lower >= self.upper):
            raise ValueError("every lower bound must be below its upper bound")
        if self.sigma.shape != (n,) or not np.all(np.isfinite(self.sigma)) or np.any(self.sigma <= 0):
            raise ValueError("sigma must be positive and finite, one per observation")
        if self.s5_map is not None and self.s5_map.shape != (5, len(self.order_names)):
            raise ValueError("s5_map must be 5 × (number of order parameters)")
        if len(set(self.theta_names + self.order_names)) != k + len(self.order_names):
            raise ValueError("parameter names must be unique")
        if self.covariance is not None:
            cov = np.asarray(self.covariance, dtype=np.float64)
            if cov.shape != (n, n) or not np.all(np.isfinite(cov)):
                raise ValueError("the covariance must be a finite N × N matrix")
            if not np.allclose(cov, cov.T, rtol=1e-12, atol=0.0):
                raise ValueError("the covariance must be symmetric")
            if np.any(np.diag(cov) <= 0):
                raise ValueError("the covariance diagonal must be positive")
            if not np.allclose(np.sqrt(np.diag(cov)), self.sigma, rtol=1e-12, atol=0.0):
                raise ValueError("sigma must equal the square root of the covariance diagonal")
            try:
                chol = np.linalg.cholesky(cov)
            except np.linalg.LinAlgError:
                raise ValueError("the covariance must be positive definite") from None
            object.__setattr__(self, "_whitener", np.linalg.solve(chol, np.eye(n)))

    @property
    def names(self) -> tuple[str, ...]:
        return self.theta_names + self.order_names

    @property
    def k(self) -> int:
        return len(self.theta_names)

    @property
    def p(self) -> int:
        return len(self.order_names)

    def whiten(self, a: Array) -> Array:
        """W·a for a vector or an N × m matrix (W = diag(1/σ), or L⁻¹ for a full Σ)."""
        if self._whitener is not None:
            out: Array = self._whitener @ a
            return out
        scaled: Array = a / self.sigma if a.ndim == 1 else a / self.sigma[:, None]
        return scaled

    def checked_design(self, theta: Array) -> Array:
        d = np.asarray(self.design(np.asarray(theta, dtype=np.float64)), dtype=np.float64)
        if d.shape != (len(self.y), self.p):
            raise ValueError(f"design returned shape {d.shape}, expected {(len(self.y), self.p)}")
        return d

    def solve(self, design: Array, target: Array) -> InnerSolution:
        """The whitened inner solve for any design and target; predictions and residuals are
        returned unwhitened (Hz), χ², rank and condition number in the whitened metric."""
        whitened = solve_inner(self.whiten(design), self.whiten(target), np.ones(len(target)))
        predictions = design @ whitened.params
        return InnerSolution(
            params=whitened.params,
            predictions=predictions,
            residuals=target - predictions,
            chi2=whitened.chi2,
            n_obs=whitened.n_obs,
            n_params=whitened.n_params,
            rank=whitened.rank,
            condition=whitened.condition,
            singular_values=whitened.singular_values,
        )

    def checked_design_derivative(self, theta: Array) -> Array:
        if self.design_derivative is None:
            raise ValueError("this problem has no analytic design derivative")
        d = np.asarray(self.design_derivative(np.asarray(theta, dtype=np.float64)), dtype=np.float64)
        if d.shape != (self.k, len(self.y), self.p) or not np.all(np.isfinite(d)):
            raise ValueError(f"design_derivative returned shape {d.shape}, expected {(self.k, len(self.y), self.p)}")
        return d

    def inner(self, theta: Array) -> InnerSolution:
        return self.solve(self.checked_design(theta), self.y)

    def profile_residual(self, theta: Array) -> Array:
        """Whitened residual at the inner optimum (the VarPro residual vector), W·(D t* − y)."""
        return self.whiten(-self.inner(theta).residuals)

    def joint_residual(self, theta: Array, t: Array) -> Array:
        return self.whiten(self.checked_design(theta) @ t - self.y)
