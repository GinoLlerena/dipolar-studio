# Validation rounds 45–46: interval warm starts

Reviewer: GPT-6.1-Sol (Codex, reasoning effort high), independent of the implementation.
Under the medium plan there are at most two rounds per step. Class (A) findings block; class (B)
findings are documented.

## What the step delivers

Faster profile intervals (`dipolar_core.fit`, `FIT_VERSION` varpro-trf.9). The profile χ² at a
value re-minimizes every other parameter once per start slot. Before, every slot started at its
known basin at every value (cold starts). Now an interval is first searched with continuation
(warm starts): each slot begins where it ended at the nearest value already computed, where the
profile is continuous, so fewer iterations are needed.

**What continuation can get wrong, and how it is checked (after round 45).** Every χ² found is
that of a feasible point, so it is at least the profile: continuation can only overstate the
profile (a slot that left its basin's valley), never understate it. A value found below the
threshold is therefore genuine; an overstated value matters only where a value above the
threshold decides something:
- just outside each endpoint (an overstatement there makes the interval too narrow);
- at the component probes beyond the endpoints (an overstatement there misses a second
  component).

Those decisive values are recomputed with cold starts. The warm interval stands only if the cold
starts also find every one of them above the threshold (and converge). Otherwise, and whenever the
warm pass finds the interval unsupported, a whole cold pass decides. So a supported interval's
endpoints and probes are always confirmed from the basins themselves.

**Merged slots.** Slots that end at the same point (within `COLLAPSE_RTOL` = 1e-6, relative and
absolute) have fallen into one valley, which need not be any of theirs; every slot of such a
group restarts from its own basin at the next value (`_continued`).

**Deterministic.** The nearest computed value is chosen with a fixed tie-break (the smaller
value); the order of evaluations is the search's own. `WARM_STARTS = False` gives the cold pass
alone.

## Before review

Gate (c), the 1 000-seed coverage protocol, rerun on the first version (before round 45): the same
hits as the varpro-trf.8 record (φ 701, Szz 691, Δ 684), every endpoint within 1.3e-12 of its
interval's width. Tests: the noisy fixture's Szz and Δ intervals with continuation equal the
cold-start ones to 1e-12 relative; a merged slot goes back to its basin. 801 passed
(`-m "not slow"`) and the 2 slow tests; mypy and Ruff clean.

## Round 45: NOT READY (one A, one B), on commit 6bb2a14

The reviewer's run: 82 passed in the core fit tests. Evaluation order is deterministic (coverage
runs in parallel only across independent seeds); the version bump, provenance, hit counts and
recorded endpoint differences check out.

**(A) Collapse restoration could lose the best basin and accept a too-narrow interval.** Only the
later slots of a merged group restarted. In a regular two-parameter problem whose nuisance wells
merge and separate again (the lower one changing side), the first slot stayed in the wrong well:
the warm interval was [-1.00005, 0.477], supported; the cold one [-1.00005, 1.00005]. At the warm
upper endpoint the cold profile is 0.23 below the threshold. Every run converged, so the
lower-failed-run rule could not see it, and the component probes reused the lost track.
- **Fix:** every slot of a merged group restarts from its basin; and, independently, the cold
  verification of the decisive values described above, with a cold pass on any disagreement. The
  claim that "every basin is still searched" is replaced by that guarantee.
- **Tests** (`test_core_fit_adversarial.py`, the reviewer's problem): the warm interval equals the
  cold one and the search really continues (warm re-minimizations outnumber cold ones more than
  five to one); with the old restoration put back, the verification alone rejects the warm
  interval and a cold pass gives the right one; an unconverged verification confirms nothing.
- **Mutation checks** (each makes a test fail): no verification; later-only restoration; never
  continuing; accepting the warm interval when a verification does not converge.

**(B) The tests did not show that intervals continue.** The fixture test passed with continuation
off. Fixed: the new tests count the re-minimizations by how they start.

**The speed-up was overstated.** The first measurement's cold baseline (38–41 s) ran on a loaded
machine. Measured back to back after the fix, on protocol seeds 0, 1, 2 and 617 (CPU time, all
three intervals, single-threaded BLAS):

| Variant | Time | Re-minimizations |
|---|---|---|
| Cold starts | 24.4–25.9 s | 1 404–1 407 cold |
| Continuation, verified (adopted) | 20.5–21.3 s | 1 387–1 389 warm, 156 cold |

About 17% less. The 156 cold re-minimizations are 13 per interval: the first evaluation (nothing to
continue from) and the 12 decisive values; no interval fell back to a cold pass.

Gate (c) after the fix, rerun on all 1 000 seeds and committed as the record: the same hits as
the varpro-trf.8 record (φ 701, Szz 691, Δ 684), no unsupported interval, every endpoint within
1.3e-12 of its interval's width (φ 8.7e-13, Szz 1.3e-12, Δ 7.1e-13); 1 279 s wall time.

## Round 46

(pending)
