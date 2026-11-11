"""The engine's four-site jump against the independent reference (tools/reference) and the frozen
8CB answers (M1 step 3; the 8CB part is the step-5 gate, run early)."""

from __future__ import annotations

import json
from itertools import combinations

import biphenyl_reference as R
import numpy as np
import pytest
from dipolar_core.biphenyl import PROTON_LABELS, jump_design, jump_problem
from dipolar_core.fit import fit

INDEX = {label: i for i, label in enumerate(PROTON_LABELS)}
LABEL_PAIRS = [(a, b) for a, b in combinations(R.LABELS, 2)]
HAS_8CB = (R.DIPIETRO_DIR / "couplings.csv").exists()
needs_8cb = pytest.mark.skipif(not HAS_8CB, reason="the third-party 8CB dataset is not present")


def indices(pairs: list[tuple[str, str]] | list[list[str]]) -> tuple[tuple[int, int], ...]:
    return tuple((INDEX[a], INDEX[b]) for a, b in pairs)


@pytest.mark.parametrize("phi", [1.0, 17.5, 33.0, 60.0, 89.0])
def test_engine_jump_equals_the_reference_explicit_average(phi: float) -> None:
    np.testing.assert_allclose(
        jump_design(phi, indices(LABEL_PAIRS)), R.design_jump_explicit(phi, LABEL_PAIRS), rtol=0, atol=1e-9
    )


@needs_8cb
@pytest.mark.parametrize("t", ["0.930", "0.980"])
@pytest.mark.parametrize("configuration", ["unweighted", "weighted"])
def test_engine_reproduces_the_frozen_8cb_jump_fits(t: str, configuration: str) -> None:
    fx = json.loads((R.DIPIETRO_DIR / "expected" / f"T{t}.json").read_text())
    spec = json.loads((R.DIPIETRO_DIR / "expected" / "spec.json").read_text())
    tol = spec["tolerances"]["regression"]
    exp = fx["expected"][configuration]
    y = np.array(fx["y_Hz"])
    sigma = np.ones(len(y)) if configuration == "unweighted" else np.array(fx["sigma_Hz"])
    result = fit(jump_problem(indices(fx["pairs"]), y, sigma))
    assert result.theta[0] == pytest.approx(exp["phi_deg"], abs=tol["phi_atol_deg"])
    np.testing.assert_allclose(result.order, [exp["Szz"], exp["Delta"]], rtol=0, atol=tol["S_atol"])
    np.testing.assert_allclose(result.predictions, exp["predictions_Hz"], rtol=0, atol=tol["predictions_atol_Hz"])
    assert result.chi2 == pytest.approx(exp["objective"], rel=tol["objective_rtol"])
    assert (result.n_obs, result.p_free) == (exp["N"], exp["p_free"])
    assert result.estimand == "jump-model phi"
    if configuration == "unweighted":
        assert float(np.sqrt(np.mean(result.residuals**2))) == pytest.approx(exp["rms_Hz"], abs=1e-6)
    else:  # the inadequacy flag: p < 1e-3 under the spectral-σ likelihood (frozen adequacy policy)
        assert exp["adequate"] is False
        assert result.p_value is not None and result.p_value < 1e-3
    # The frozen fixture's interval policy (round 21, finding 3). The unweighted fit has no error
    # model, and the weighted fit is inadequate, so neither reports intervals. profile_interval does
    # not judge adequacy itself; the reporting layer (M2) must apply this policy. Recorded here so
    # that it cannot be lost.
    assert exp["intervals"].startswith("not supported")
