"""The numerical context: every versioned choice that can change a computed number (plan D11).

Scientific identity (the canonical science hash) covers this context as well as the project, so
that changing a constant, a model formula or a solver policy can never keep the same hash.
Bump the matching entry whenever the corresponding code changes its numbers.
"""

from __future__ import annotations

from dipolar_core.inference import ADMISSIBILITY_ATOL, RANK_RTOL
from dipolar_core.nuclides import TABLE_VERSION

FORWARD_MODEL_VERSION = "cartesian-traceless5.1"
INNER_SOLVER_VERSION = "whitened-svd.1"
BIPHENYL_TEMPLATE_VERSION = "regular-hexagon-bisector.1"


def numerical_context() -> dict[str, str | float]:
    return {
        "nuclide_table": TABLE_VERSION,
        "forward_model": FORWARD_MODEL_VERSION,
        "biphenyl_template": BIPHENYL_TEMPLATE_VERSION,
        "inner_solver": INNER_SOLVER_VERSION,
        "rank_rtol": RANK_RTOL,
        "admissibility_atol": ADMISSIBILITY_ATOL,
    }
