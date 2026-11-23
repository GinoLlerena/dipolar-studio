# Round 84: V1.5b final review after the round 83 fixes (GPT-6.2-Sol)

Final independent review of PR #28 at `e74081d` (`git diff 5b219c4..e74081d`) by GPT-6.2-Sol
(Codex, reasoning effort high), 2026-11-23. This is the second and last Sol round for this PR.
The review used a tracked-only worktree at that commit. Verdict: **NOT READY** (6 A, 2 B). The
report is below, as delivered. The orchestrator's provisional dispositions follow it. Under the
review process, after a NOT READY final round the owner decides how to proceed before any merge.

## Report

### Class A — blocks merge

1. **First-fit authorization deadlocks at the CLI and is bypassed by the Python runner.** A
   staged first submission failed the scan because it had no fit output. The CLI refused to
   produce that output until the submission was committed. Calling `run_report` directly with an
   agent role, a pre-freeze timestamp, and no ledger reached all 15 synthetic fits.
   `tools/validation/verification.py:1007`, `:1362`; `tools/datasets/restricted_scan.py:449`
2. **The fit tier accepts invented roster keys and missing quantities.** Replacing a frozen
   condition with an invented key passed. Deleting 45 of 60 values passed, including every
   reproduction value and every independent discrepancy. The scanner then missed the removed
   reproduction discrepancy in a synthetic blob. `tools/datasets/restricted_scan.py:321`, `:401`
3. **Scan stdout can disclose a fit value.** An unexpected ASCII file name containing a synthetic
   fit value passed the file-name character check, and the CLI echoed it in the error. The
   linked-directory and linked-file write checks passed. `tools/datasets/restricted_scan.py:433`,
   `:505`
4. **The scan rejects a valid rank-pending reproduction result.** The report correctly marked one
   synthetic authors' fit `rank-unverified` and omitted its named estimate. The scanner rejected
   the resulting file for incomplete reproduction coverage. `tools/validation/verification.py:768`,
   `:1291`; `tools/datasets/restricted_scan.py:334`
5. **Placeholder files can count as completed reviews.** Two distinct disagreements became
   `explained discrepancy`. Their annexes contained only `placeholder`, and their receipts pointed
   to the same heading in a file with no body. `tools/validation/evidence.py:173`, `:184`
6. **A rerun loses prior fit provenance.** The local report records the model, frame, science
   hash, versions and flags. A rerun with changed authors' weights at the same `--out` path
   overwrote the first report. The retained numeric file lacked the first run's science hashes,
   and the scan still passed after that retained file was deleted.
   `tools/validation/verification.py:1105`, `:1315`, `:1380`

### Class B — document, do not block

- Round 83's receipt-cutoff regression is caught, and the shared ready-file credential boundary
  is documented. `docs/phase2/verification/gates.md:194`
- Review procedure deviation: the reviewer used an additional `git log` format to extract
  receipt excerpts despite the brief's format restriction. The output contained only
  commit-message excerpts and exposed no author or committer metadata.

### Readings and evidence

- **Checks.** Requested pytest suite: 296 passed. Ruff passed. Mypy passed across 48 source
  files. The owner-local scan entry was skipped as directed.
- **Comparison workflow.**
  - Supported method records drove the authors' fit, and the fallback used its required label.
  - P-2 and rank precedence worked.
  - Invalid protocols were blocked before fitting.
  - The synthetic shared JSON contained no fit values.
- **In-memory mutations.** 9 of 9 caught.
  - Round 83's gated-target and ignored-rank mutation was caught both combined and as two
    separate changes.
  - The other six: a future receipt cutoff, ignored log edits, removed reproduction coverage,
    allowed linked directories, ignored missing review headings, and skipped protocol
    validation.
- **History.** All four gate commits preceded their fixes, and the later gate corrections are
  documented. All 9 message receipts matched their trees and UTC records. Eight appeared in the
  next commit's §6, and the `e74081d` row is pending as planned.

Every data probe and fit was synthetic. The detached worktree was removed.

## Dispositions

The owner chose (2026-11-23T20:15Z) to fix all six, then run one Sol round (round 85) scoped to
those fixes. The fixes are recorded in `docs/phase2/verification/gates.md` §6 ("round 84 fixes").


| Finding | Disposition |
|---|---|
| A1 deadlock and bypass | **Accept.** Require fit outputs only for submissions already in the committed (HEAD) log, so the commit that logs a submission can pass before it is run. Move `authorize` into `run_report`, which then refuses without a committed, authorized submission whoever calls it. |
| A2 invented keys, missing quantities | **Accept.** Bind the fit-values record to the frozen roster's keys (the roster from the public preregistration and the hash-verified couplings), and make it declare every roster cell per track: its estimate or its pending reason, and its discrepancy or why there is none. The scan then requires exactly that. |
| A3 file-name echo | **Accept** (confirmed: any name matching `[A-Za-z0-9._-]+` is printed). Print only names the scanner expects, and a fixed placeholder otherwise. |
| A4 rank-pending coverage | **Accept** (it applies to the independent track too). Coverage counts a declared pending cell as covered, per A2. |
| A5 placeholder reviews | **Accept in part.** Content quality cannot be machine-proven, but structure can. Require distinct public headings with a non-empty body, and an annex entry holding the plan's fields (frame and convention, geometry, corrections, context, numerical comparison, cause). The owner's attestation remains the check of substance. |
| A6 provenance across reruns | **Accept.** Retain earlier local reports as well as fit values. Put each fit's provenance (science hash, versions, method) in the fit-values record. Bind the retained files into the scan, so a deleted retained output is a problem. |
| B items | Recorded. |
