# Validation round 21: M1 step 3 (the symmetric four-site jump)

- **Reviewer:** GPT-6.1-Sol (high effort), independent and read-only.
- **Reviewed:** commit 5c5f25e against 666677e.
- **Verdict: NOT READY.** Two class-(A) findings and one class-(B) finding.
- **Confirmed:**
  - the four-conformer averaging and the Δ sign handling;
  - the analytic derivative;
  - the completeness of the acute domain, and the relabelling invariance;
  - the Δ cancellation at 90°;
  - the estimand;
  - the `s5_map` semantics, which check each conformer's tensor;
  - leaving out the rigid model's endpoint notes.

## 1. (A) The search missed a full-rank basin beside the rank-changing pole

**The counterexample.** All 45 pairs, y = jump_design(89.999°)·(0.25, 0.1), σ = 1e-8. The only
grid minimum was 90°, where the Δ column vanishes and the inner rank is 1. The refinement stayed
on that plateau and returned χ² ≈ 1.2·10¹², marked converged and resolved. A start at 89.5°
finds the regular basin at 89.999°, with χ² ≈ 3.5·10⁻⁸.

**Fix.** `Scan.rank_starts`: each start whose inner rank is below the scan's highest also gets
the nearest highest-rank scan point as a start, for grids and Sobol scans alike.

**Test:** `test_a_full_rank_basin_beside_the_rank_changing_pole_is_found`. The mutation is caught.

## 2. (A) A supported interval ended at a discontinuity

**The counterexample.** φ = 89.9°, σ = 0.5 Hz. The profile interval was reported as supported,
[88.34°, 89.99999999°]. But χ² at the upper end was 1.3·10⁻⁵ above the minimum, not 1: brentq
had converged onto the jump where the inner rank drops.

**Fix.** A located endpoint must meet the threshold to within `ENDPOINT_RTOL` · Δχ²
(ENDPOINT_RTOL = 1e-6). Otherwise the interval is not supported, with the note "the profile jumps
across the threshold … discontinuous". φ = 89° is now unsupported too, because its region also
runs into the pole. An interval at 60° is still supported.

**Tests:** `test_a_profile_that_runs_into_the_pole_is_not_supported` (89.9° and 89°) and
`test_an_interval_away_from_the_pole_is_still_supported`. The mutation is caught.

## 3. (B) The 8CB regression did not assert the frozen interval policy

The frozen fixture declares intervals unsupported: the unweighted fit has no error model, and
the weighted fit is inadequate. `profile_interval` does not judge adequacy.

**Documented** in the `fit` module docstring: callers that report intervals (the reporting layer,
M2) must refuse them when there is no error model, or when the fit is inadequate. The 8CB test
now asserts the fixture's policy, so it cannot be lost.

`FIT_VERSION` is now varpro-trf.7. 421 tests pass (`-m "not slow"`).
