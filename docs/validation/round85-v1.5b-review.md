# Round 85: scoped review of the round 84 fixes (GPT-6.2-Sol)

An extra review of PR #28, authorized by the owner after round 84 was NOT READY ("Fix all six,
scoped Sol check", 2026-11-23T20:15Z). It is scoped to two questions: are round 84's six findings
and two later cases resolved, and did the fixes introduce new blocking defects? GPT-6.2-Sol (Codex,
reasoning effort high) reviewed `a435803` against `35c0f9f`, 2026-11-24, in a tracked-only
worktree. Verdict: **NOT READY** (6 A, 2 B).

**First attempt.** A first attempt on `9ca2803` (2026-11-23) stopped partway, because the
provider's safety filter flagged the run, and it delivered no report. Its last message named two
cases the scan accepted: a false no-target declaration, and a rollback to an earlier chain. Both
were confirmed from the code. The owner chose to fix them and rerun this round ("Fix both, then
rerun 85", 2026-11-24T23:15Z). They were fixed in `0fac7e8` (tests) and `a435803` (fixes), and
this report is of the rerun.

The report is below, as delivered. Provisional dispositions follow it. After a NOT READY round,
the owner decides how to proceed before any merge.

## Report

### Class A — blocks merge

1. **A2. The scan can use a roster from the wrong protocol revision.** The reviewer replaced a
   synthetic condition in the couplings, updated the hash only in the unstaged preregistration,
   and changed the fit record to match. The staged scan passed under the original committed
   submission and protocol revision. `tools/validation/fit_record.py:85`
2. **A3. A retained file name can still disclose a value.** A synthetic restricted input value was
   put in the numeric suffix of an out-of-sequence retained file name. The scan printed it, both
   on the command's output and in the staged-check diagnostics.
   `tools/datasets/restricted_scan.py:350`, `tools/validation/fit_record.py:300`
3. **A5. Review receipts can share a heading or cite an empty rendered section.**
   - Two receipts for the same heading passed when one path had a `./` prefix. The runner then
     classified both discrepancies as explained.
   - Distinct headings with only HTML comments beneath them also passed.

   `tools/validation/evidence.py:210`, `:256`
4. **A6. The command can overwrite a retained report.** A synthetic comparison was rerun with
   `--out` set to run 1's stored report. The command overwrote that report and returned success.
   The next scan rejected the broken chain. `tools/validation/verification.py:1438`
5. **A false pending declaration is still possible for a signed run.** All 30 discrepancy
   declarations were changed to `no-target`, leaving the signed report byte-for-byte intact. The
   scan accepted the record, and it missed a synthetic value in a document that it had flagged
   before. `tools/validation/fit_record.py:210`
6. **A staged ledger edit can erase the rollback guard.** After three runs were recorded, run 1
   was restored and removal of the committed receipt row was staged. Both scan entry points
   passed. The staged check also passed when the three-run receipt existed only in the preceding
   commit message. `tools/datasets/restricted_scan.py:515`

### Class B — document, do not block

- The owner's attestation remains responsible for the scientific substance of review entries, as
  agreed.
- One `%B` history command displayed co-author trailers. Later history output was filtered to
  receipt fields.

### Readings and evidence

| Item | Status |
|---|---|
| A1: logging order and runner authorization | Resolved |
| A2: frozen roster and complete declarations | Open |
| A3: value-free file-name diagnostics | Open |
| A4: rank-unverified fits on either track | Resolved |
| A5: structured review evidence | Open |
| A6: rerun provenance and retention | Open |
| False pending | Open |
| Rollback | Open |

- **Checks.** Pytest: 366 passed. Ruff: no violations. Mypy: no issues in 48 source files.
  `git diff --check` passed. The owner-only restricted-data check was excluded.
- **In-memory mutations.** Existing tests caught all eight, one at a time:
  - bypassed authorization;
  - removed roster checking;
  - removed file-name redaction;
  - disallowed rank-pending declarations;
  - skipped review-body checking;
  - skipped chain checking;
  - skipped pending consistency;
  - removed the receipt floor.
- **History.** Both test commits preceded their fixes, and the later test corrections are
  documented in §6. All five receipt tree hashes matched. Four UTC and tree pairs appeared in the
  next commit's §6; the `a435803` row is pending, as planned.

All probe data and fits were synthetic. The detached checkout was removed.

## Dispositions (provisional; pending the owner's decision)

| Finding | Disposition |
|---|---|
| 1. Roster from another revision | **Accept.** Read the preregistration from the same tree as the ledger (the staged index, for a receipt), not the working copy. Require each record's protocol revision to be that preregistration's hash. |
| 2. Retained name suffix printed | **Accept.** Print a retained file's name only within the expected sequence, and never a number from an unexpected name, in the tier's problems or in the chain's. |
| 3. Shared heading through `./`; comment-only body | **Accept.** Refuse a non-canonical public path, so one file has one spelling. Do not count HTML comments as a section's body. |
| 4. `--out` over a retained report | **Accept.** Refuse an `--out` under `datasets-local/verification/`, where the workflow keeps its own outputs. |
| 5. All no-target on a signed run | **Accept.** Each record declares whether the spot-check was signed. The scan checks that against the bound report's own "Spot-check signed" line. The no-target rule then uses the declared state: withheld only when unsigned. |
| 6. Rollback guard erased | **Accept.** Take the receipt floor from the committed ledger and the `HEAD` commit message as well as the staged ledger. Refuse a staged ledger that drops or changes a committed §6 receipt row. |
| B items | Recorded. |
