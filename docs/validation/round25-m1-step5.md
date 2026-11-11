# Validation rounds 25 and 26: M1 step 5 (the acceptance gates)

- **Reviewer:** GPT-6.1-Sol (high effort), independent and read-only.
- **Reviewed:** the step-5 commit against 61a80d7 (`m1-step4`).
- **Verdict: NOT READY.** Two class-(A) findings, both gaps in test assertions. The reviewer found
  no deviation in the coverage generator and no sign that the committed results are wrong. They
  also confirmed that the gate tests cover the 1e-8 recovery, all 45 and reversed pairs, the
  0°/90° predictions, explicit averaging, both 8CB temperatures and configurations, the
  prediction vectors, RMS, the inadequacy criterion and the estimand label. Seeds 0, 617 and 573
  (near a coverage boundary) reproduced.

## What step 5 claims

1. Every gate frozen in `datasets/*/expected/spec.json` has at least one engine test, and the
   ledger in `tests/test_m1_acceptance.py` fails if a named test disappears (mutation-checked: a
   renamed test is caught).
2. Gate (c) holds on the engine under the frozen protocol: 1000 seeds, profile intervals at raw
   Δχ² = 1, band 64.5–72.1%.

   | Parameter | Engine hits | Reference hits | Coverage | Unsupported |
   |---|---|---|---|---|
   | φ | 701 | 701 | 0.701 | 0 |
   | Szz | 691 | 691 | 0.691 | 0 |
   | Δ | 684 | 684 | 0.684 | 0 |

   The per-seed record is `docs/validation/data/m1-gate-c-engine-coverage.json`, produced by
   `uv run python -I tools/coverage/engine_coverage.py --seeds 1000 --workers 11 --out …`. The
   record tests were mutation-checked: a changed endpoint and a changed hit count are both caught.
3. The 8CB gates (unweighted and weighted fits at T_red 0.930 and 0.980, the inadequacy flag, the
   estimand label) were already met in step 3 by `tests/test_engine_jump_reference.py`; the
   ledger now names them. They run only while the third-party dataset is present.

## Findings and fixes

Each fix was mutation-checked; all three mutations were caught.

1. **(A) The record check trusted the summary's unsupported count.** Hits were counted over the
   supported intervals only, so a seed whose interval was replaced by "not supported" passed.
   - **Fix:** `test_gate_c_record_is_within_the_band` recomputes every summary field from the
     seeds: unsupported (must be 0), hits, coverage and the band verdict. Every interval must be
     finite and contain its own estimate.
2. **(A) Gate (b)'s interval test allowed errors beyond the frozen absolute tolerances**, through
   NumPy's default relative tolerance (a pre-existing weakness in `test_core_fit.py`).
   - **Fix:** `rtol=0` in both interval comparisons. The reviewer's displaced endpoints now fail.

## Class (B): documented limits, and one improvement taken

- **Provenance (taken).** The record now names the fitter version and the SHA-256 of the frozen
  inputs it was made from, and the record test requires them to match the current ones. A change
  of `FIT_VERSION` or of the inputs marks the record stale until it is regenerated. The record
  was produced at b15a963. The fitter and the datasets there are unchanged since `m1-step4`, so
  the provenance was added to it without rerunning. Within one `FIT_VERSION`, the default suite
  reproduces only two seeds; the slow test compares all 1000.
- **Agreement with the reference.** The ±3-seed check against the reference's counts was removed.
  Agreeing counts do not prove agreeing intervals, and endpoint changes inside the tolerances can
  move more than three hits. The acceptance criterion is the frozen band. That the engine's counts
  equal the reference's (701, 691, 684) is recorded here as an observation.
- **Calibration scope.** Coverage is established at one truth, (37°, 0.25, 0.03), under the frozen
  Gaussian noise. That is the frozen M1 experiment. It does not calibrate other truths,
  boundaries, the jump model or irregular cases (plan: those need their own calibration or report
  "interval not supported"). The band is per parameter, not a joint three-parameter guarantee.
- **BLAS threads under `fork`.** The thread limits take effect in freshly spawned workers (the
  macOS default). Under `fork`, an already-imported NumPy keeps its thread pool, which affects
  speed only.

## Round 26: READY

- **Reviewed:** cad2d74 (the round-25 fixes) against b15a963, and the whole step against 61a80d7.
- **Verdict: READY**, with no class-(A) findings. Both round-25 blockers are resolved; the
  reviewer's in-memory mutations were rejected. Seeds 0, 617 and 5 reproduced.
- **Class (B), documented:**
  - The fast checks establish that the record is consistent, not that it is authentic: a
    fabricated seed that is not among the two sampled ones, with a matching summary, would pass.
    The slow test reruns and compares all 1000 seeds.
  - `FIT_VERSION` is a manual label. A digest of the engine and generator sources would detect a
    stale record even if someone changed the fitter without bumping the version. A possible
    later improvement; the engine is unchanged here.
  - Exact equality of `coverage` with hits / n is safe for this record: every thousandth ratio
    round-trips through JSON exactly.
