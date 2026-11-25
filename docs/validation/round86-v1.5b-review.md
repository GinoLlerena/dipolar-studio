# Round 86: scoped review of the round 85 fixes (GPT-6.2-Sol)

An extra review of PR #28, authorized by the owner after round 85 was NOT READY ("Fix all six,
one more round", 2026-11-25T00:40Z). It is scoped to two questions: are round 85's six findings
resolved, and did the fixes introduce new blocking defects? GPT-6.2-Sol (Codex, reasoning effort
high) reviewed `eda54e8` against `f424cdc`, 2026-11-25, in a tracked-only worktree. Verdict:
**NOT READY** (6 A, 0 B).

The report is below, as delivered. The orchestrator's notes follow it. After a NOT READY round,
the owner decides how to proceed before any merge.

## Report

### Class A — blocks merge

1. **The staged scan can still read the working-copy roster.** The reviewer staged the JSON value
   `null` as the preregistration, left a valid amended preregistration in the working copy, and
   changed a synthetic record to match the amended roster. The staged check returned no problems,
   and the command exited 0. The decoded `null` selects the working-copy fallback.
   `tools/datasets/restricted_scan.py:480`
2. **A retained name can still leak through a traceback.** A directory was named like a retained
   fit-values file with an out-of-sequence synthetic numeric suffix. The parser produced a
   redacted diagnostic, then the unconditional hash read raised `IsADirectoryError`. Both the
   staged check's exception and the command's traceback showed the suffix.
   `tools/datasets/restricted_scan.py:531`
3. **Two receipts can still use one heading on a case-insensitive filesystem.** Two receipts gave
   the same heading, with different letter case in the same public file's name. Review coverage
   accepted both, because it compares the path strings. `tools/validation/evidence.py:267`
4. **A comment-only review body can still pass.** A multiline HTML comment containing a line such
   as `### Hidden` was accepted as the whole body. The parser stopped at that line before it
   removed comments, so the opening `<!--` counted as body text.
   `tools/validation/evidence.py:223`
5. **A target amendment invalidates a valid retained run.** A signed synthetic run passed with
   one target correctly pending. The next protocol revision then supplied that target, and the
   staged scan rejected the unchanged retained run, reporting its committed submission as
   missing a complete output. The scan applied the amended pending set to the earlier run.
   `tools/datasets/restricted_scan.py:445`, `tools/validation/fit_record.py:247`
6. **A results receipt can lose its rollback protection.**
   - With three runs and a receipt only in `HEAD`, the scan accepted an unrelated staged change
     that did not carry the receipt into the ledger. After that change was committed, both scan
     entry points accepted restoring run 1.
   - A receipt with a line break before `(files: …)` set no floor while still in `HEAD`.

   `tools/datasets/restricted_scan.py:312`, `:591`

### Class B

None.

### Readings and evidence

| Round 85 finding | Status |
|---|---|
| 1. Working-copy preregistration | Open: a staged `null` gets around the fix. |
| 2. Retained file-name disclosure | Open: the traceback shows the suffix. |
| 3. Shared heading or empty review body | Open: the `./` case is fixed; letter-case aliases and multiline comments still pass. |
| 4. `--out` overwrites kept outputs | Resolved: the command refused all four protected destinations tested, before any fit. |
| 5. Signed run with every target withheld | Resolved for the original case; Class A 5 is a regression across revisions. |
| 6. Results receipt rollback floor | Open: the tested ledger deletion and the single-line `HEAD` case are fixed; carrying the receipt into the ledger and line wrapping still fail. |

- **Checks.** Pytest: 379 passed. Ruff: 0 violations. Mypy: 0 issues in 48 source files.
  `git diff --check` passed. The owner-only check was excluded.
- **In-memory mutations.** Existing tests caught all six, applied one at a time:
  - staged preregistration bypassed;
  - retained-name redaction removed;
  - HTML comment stripping removed;
  - kept-output protection removed;
  - signed pending consistency removed;
  - the `HEAD` receipt floor removed.
- **History and receipts.** `8156758` preceded `eda54e8`, and §6 documents all four later test
  additions. The `8156758` receipt tree and UTC time (`2026-11-25T00:55Z`) match its §6 row. The
  `eda54e8` receipt matches its commit tree and is pending in §6, as planned.

All test and probe data were synthetic. The detached checkout was removed.

## Orchestrator's notes (pending the owner's decision)

- Every open item concerns the owner-local scan and review checks. They become live only once an
  experimental fit is authorized, and none is: §10 has no `freeze approved` row. No restricted
  value is exposed by the shared output, which no round has faulted.
- Possible fixes, if the owner chooses to fix:
  1. treat a staged preregistration that is absent or not a JSON object as unreadable, never as
     "use the working copy";
  2. skip anything under the verification folders that is not a regular file, with a redacted
     problem and no exception;
  3. compare public paths case-folded, and resolved, through the file system's own identity
     (same device and inode);
  4. remove HTML comments before splitting the section;
  5. judge each run's pending targets at that run's own revision: record the targets file's
     hash in each run's record, and read the pending cells from the file at that hash (or
     from the run's own record of them), not from the current revision;
  6. require a staged ledger to carry forward the latest results receipt from the `HEAD` commit
     message, and match receipts across line breaks.
- Rounds 84 to 86 each closed the earlier findings and found narrower ones in the same local
  checks.
