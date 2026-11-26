# Round 90: pre-freeze re-review of the owner-local checks (GPT-6.2-Sol), incomplete

The owner asked for this review on 2026-11-26, before the `freeze approved` row ("Re-review
now"). It covers two sets of fixes that were merged without a follow-up review:

- **round 87:** `1456a88` and `31f7f21`, in `fit_record.py`, the scan's fit tier,
  `evidence.py`, and the runner's input checks;
- **round 89:** `60edaea` and `b0e3c1e`, the guide snippet's stale check.

The reviewer was GPT-6.2-Sol (Codex, reasoning effort high), reviewing `main` at `7d35eb5` in a
tracked-only worktree.

**Both attempts stopped before a report.** The provider's safety filter flagged each one.
Neither delivered a verdict. What they reported before stopping, and what the orchestrator
confirmed from the code, follows.

## What the attempts established

1. **First attempt.** Its last message said the round 86 regressions are covered by the focused
   suite. It was examining two nearby cases:
   - (a) whether carrying a receipt forward keeps its counts;
   - (b) whether the guide's snippet writes an unsuitable run before checking it.
2. **Second attempt** (neutral wording, with (a) and (b) given as leads to judge independently).
   Its last message:
   - (a) **confirmed.** "The lower-count receipt passed, and both scan entry points accepted the
     one-run rollback after it was committed."
   - **Reverts.** The existing tests catch a missing receipt and a wrapped receipt.

## The orchestrator's reading

- **(a) A carried receipt can lose its file counts.**
  - The carry rule matches only the tree hash of the last commit's `Scan receipt (Decision 11B)`
    (`tools/datasets/restricted_scan.py`, the `_LAST_RECEIPT` check in `_staged`).
  - A staged §6 row that names the tree, with lower counts or none, passes.
  - Once that commit lands, the `HEAD` message no longer carries the higher counts, and the
    floor that round 86's finding 6 protects is lost.
  - This is live only once results exist, after the first fit. It is a class A for the freeze:
    the rollback guard must hold from the first results receipt on.
- **(b) The snippet writes before it checks.**
  - `docs/phase2/reproduce-benzene.md`, "Save the selected run": `Path(OUT).write_text(...)`
    comes before the check that S_zz is estimated and the rank verified.
  - A run that cannot be used still leaves a file behind, although the snippet then fails.
  - The owner's numerical check would refuse it. Class B.

No restricted value was involved: the probes were synthetic, and no experimental fit ran.
