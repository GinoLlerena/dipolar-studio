# Validation rounds 45–46: interval warm starts

Reviewer: GPT-6.1-Sol (Codex, reasoning effort high), independent of the implementation.
Under the medium plan there are at most two rounds per step. Class (A) findings block; class (B)
findings are documented.

## What the step delivers

Faster profile intervals (`dipolar_core.fit`, `FIT_VERSION` varpro-trf.9). The profile χ² at a
value re-minimizes every other parameter once per start slot. Before, every slot started at its
known basin at every value. Now each slot continues from where it ended at the nearest value
already computed (continuation), where the profile is continuous, so far fewer iterations are
needed.

**Every basin is still searched.** Plain continuation lets a slot slide into another slot's
valley and follow that valley from then on, so a basin could be dropped for the rest of the
interval. `_continued` detects a slot that ended where an earlier slot ended (within
`COLLAPSE_RTOL` = 1e-6, relative and absolute) and restarts it from its own basin. The slots
therefore never collapse.

**Deterministic.** The nearest computed value is chosen with a fixed tie-break (the smaller
value), and the order of evaluations is the interval search's own, which is unchanged. The memo
of computed values (the small batch) is unchanged. `WARM_STARTS = False` restores the cold starts
(used by a test).

## Before review

**Gate (c), the 1 000-seed coverage protocol,** rerun in full on the final code
(`tools/coverage/engine_coverage.py`; record `docs/validation/data/m1-gate-c-engine-coverage.json`):
- hit counts identical to the varpro-trf.8 record: φ 701, Szz 691, Δ 684 (band 64.5–72.1 %);
  no unsupported interval;
- every seed's interval endpoints agree with the varpro-trf.8 record to at most 1.3e-12 of the
  interval's width (φ 8.7e-13, Szz 1.3e-12, Δ 5.8e-13); estimates to 2e-16 relative;
- 1 353 s wall time, against about 40 minutes before (not a controlled comparison: one run each).

**Measured on four protocol seeds (0, 1, 2, 617), CPU time for all three intervals:**

| Variant | Time |
|---|---|
| Cold starts (varpro-trf.8) | 38–41 s |
| Continuation, no collapse restoration | 24–25 s |
| Continuation with collapse restoration (adopted) | 24–28 s |

Endpoints agree with cold starts to about 3e-15 relative on those seeds.

Tests:
- `test_warm_started_intervals_equal_cold_ones_on_the_fixture`: the noisy fixture's Szz and Δ
  intervals with continuation equal the cold-start intervals to 1e-12 relative;
- `test_warm_starts_never_let_a_basin_track_collapse_into_another`: a merged slot is sent back to
  its basin; distinct slots continue.

Baseline: 801 passed (`-m "not slow"`) and the 2 slow tests (the full gate (c) rerun equals the new record seed by seed), mypy and Ruff clean; the record's provenance and the
seed-0 and seed-617 regressions are checked by `tests/test_m1_acceptance.py`.

## Round 45

(pending)
