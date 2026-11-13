# ADR-0003: Scientific and inference contract (D3)

- **Status:** Accepted, 2026-11-07 (plan v0.6, Phase 1 baseline)
- **Source:** [D3](../03-redesign-plan.md#3-key-decisions)

## Decision

- Whitened inner solve by SVD or pivoted QR (never normal equations as the reference); bounded TRF outer fit seeded by a grid or multistart; competing basins reported.
- Gaussian likelihood with a fixed covariance; known σ is never silently rescaled; multiplicity rows never inflate N.
- Covariance from the full Jacobian in joint coordinates; profiles vs slices; raw Δχ² thresholds 1.00 / 3.84 / 2.30 with labelled levels; "interval not supported" outside regular conditions.
- Independent validity flags: inner rank and condition, joint rank, convergence, admissibility, interval support.
- ν = N − p_free for regular interior models; joint rank reported separately.

## Consequences

- The M1 gate is fixed in advance and frozen as data in `datasets/*/expected/` (M0 step 2).

## Verified by

`tests/test_expected_fixtures.py` (frozen answers). M1 step 1 (`FIT_VERSION` varpro-trf.5: full Σ, exact Golub–Pereyra
Jacobian, Richardson derivatives with a trusted rank, a bounded trial-step convergence certificate): `dipolar_core.fit` passes gates (a)
and (b) and the irregular-case tests in `packages/dipolar-core/tests/test_core_fit.py`, and the round-13
adversarial controls in `test_core_fit_adversarial.py`. M1 step 2 (`FIT_VERSION` varpro-trf.6) adds
analytic design derivatives (`Problem.design_derivative`). It also adds an error allowance for the
inner solution's own error in every geometry column of the full Jacobian, on both derivative
paths (round 19). Coverage,
gate (c), comes in M1 step 5. Interval warm starts (`FIT_VERSION` varpro-trf.9, rounds 45–46):
profile re-minimizations continue from the nearest computed value, with merged starts sent back to
their basins; gate (c) was rerun and its record regenerated (the same hits, endpoints within
1.3e-12 of the interval width).

## M0 spike 1 (2026-11-08)

The D3 controls pass on dipolar-core (`spikes/test_spike_d3_numerics.py`). M1 refines with bounded
TRF on the residual vector, held to absolute accuracy:
- within 10⁻¹² ° of the noiseless truth;
- within 10⁻⁸ ° of the frozen noisy optimum.

SciPy's bounded scalar minimizer stopped 1.5·10⁻⁹ ° from the noiseless truth. That is where its
own tolerance stops it, not a limit of the profile. The frozen expected values are unchanged.

## Changelog of frozen fixtures

Any re-freeze of `datasets/*/expected/` (via `tools/reference/make_expected.py`) is recorded here with its reason.

- 2026-11-07: initial freeze (M0 step 2). Synthetic rigid fixture, 8CB jump-model fits at T_red 0.930 and 0.980, coverage reference (φ 70.1%, Szz 69.1%, Δ 68.4%; band 64.5–72.1%).
