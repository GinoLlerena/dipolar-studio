"""The reporting policy for intervals (M2 step 1; ADR-0003, plan §8 M1, round 21 finding 3).

``dipolar_core.fit.profile_interval`` does not judge model adequacy. Whoever reports an interval
must. Here, a profile interval is reported only when both hold:

1. **The optimum is regular** (``Validity.regular``): converged, the search resolved, interior to
   the bounds, and of full inner and joint rank. Otherwise ν and the χ² calibration do not apply.
2. **The fit is adequate under the stated σ:** p ≥ ``ADEQUATE_P_MIN``, the frozen adequacy policy
   of the 8CB set. An inadequate fit means the σ do not describe the residuals, so a Δχ² = 1
   interval would describe nothing.

Every project states σ for each coupling (the schema requires it), so a project always has an
error model. The 8CB "unweighted" configuration (ordinary least squares, no error model) is not a
project setting. If it becomes one, it must refuse intervals here too.

The M1 coverage gate (c) calibrates these intervals for the rigid template model at its frozen
truth. Other models and truths are uncalibrated; ``POLICY_STATEMENT`` says so.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from dipolar_core.fit import FitResult

ADEQUATE_P_MIN: Final = 1e-3

POLICY_STATEMENT: Final = (
    "Profile intervals (Δχ² = 1, 68.3% one-parameter) are reported only for a regular optimum of an "
    f"adequate fit (p ≥ {ADEQUATE_P_MIN:g} under the stated σ). Their coverage is calibrated for the rigid "
    "template model at the M1 gate's truth (gate c); elsewhere it is not calibrated."
)


@dataclass(frozen=True)
class IntervalPolicy:
    allowed: bool
    adequate: bool | None  # None when the fit has no p-value (irregular, or ν = 0)
    reason: str  # why intervals are refused; "" when allowed
    statement: str = POLICY_STATEMENT


def _irregularity(result: FitResult) -> str:
    v = result.validity
    if not v.converged:
        return "the refinement did not converge"
    if not v.search_resolved:
        return "the search is unresolved (an unfinished refinement reached a lower χ²)"
    if v.at_bound:
        return f"the optimum lies on a bound ({', '.join(v.at_bound)})"
    if v.inner_rank < v.inner_parameters:
        return "the order parameters are not all determined (inner rank deficient)"
    if v.joint_rank < v.joint_parameters:
        return "some parameter combinations are not determined (joint rank deficient)"
    return "the optimum is not regular"


def interval_policy(result: FitResult) -> IntervalPolicy:
    """Whether intervals may be reported for ``result``, and why not."""
    if not result.validity.regular:
        return IntervalPolicy(False, None, _irregularity(result))
    if result.p_value is None:
        return IntervalPolicy(False, None, "no degrees of freedom are left (N ≤ number of parameters)")
    if result.p_value < ADEQUATE_P_MIN:
        return IntervalPolicy(
            False,
            False,
            f"the fit is inadequate (p = {result.p_value:.3g} < {ADEQUATE_P_MIN:g}): the stated σ do not "
            "describe the residuals",
        )
    return IntervalPolicy(True, True, "")
