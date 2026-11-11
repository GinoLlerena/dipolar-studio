# Validation round 25: M1 step 5 (the acceptance gates)

- **Reviewer:** GPT-6.1-Sol (high effort), independent and read-only.
- **Reviewed:** the step-5 commit against 61a80d7 (`m1-step4`).
- **Verdict:** pending.

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

Pending.
