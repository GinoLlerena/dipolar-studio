# Round 91: pre-freeze review of the owner-local checks (Claude Opus, independent)

The owner decided this review after round 90 delivered no verdict ("Fix both, Claude review",
2026-11-26). A fresh Claude Opus reviewer (effort high), independent of the orchestrator,
reviewed branch `v1.5d-prefreeze` at `9283329` in a tracked-only worktree, on 2026-11-26. It
covered:

- the round 87 fixes (round 86's six findings);
- the round 89 fix;
- the round 90 fixes.

Verdict: **NOT READY** (3 A, 5 B).

The report is below, as delivered. Provisional dispositions follow it. After a NOT READY round,
the owner decides how to proceed before any freeze.

## Report

### Class A

1. **A merge commit drops both the carry rule and the receipt floor.**
   - **Defect.** `_staged` reads only the last commit's message (`git log -1 HEAD`). When HEAD
     is a merge commit, the merged branch's last receipt sits in the second parent's message,
     and no check reads it.
     - The next commit is not required to carry that receipt into §6.
     - That receipt's counts no longer set the floor.
   - **This happens in the normal workflow.** Each PR ends on a receipt that has not been
     carried yet, and GitHub then adds a merge commit. In the real history, `fdebbf6`'s row was
     added by `244d7d8`, whose parent is the merge `7d35eb5`. The ledger calls that row "owed":
     it was added by hand, and no check required it.
   - **Reproduction (synthetic).**
     1. On `main`, commit three runs.
     2. On a feature branch, commit with a full receipt in the message: `Scan receipt (Decision
        11B): tree … at 2026-11-25T11:00Z: passed, not skipped; fit tier: results (files:
        benzene-taggar2006 3, odcb-chandrakumar1993 0).`
     3. Control: on the branch, an unrelated staged change is refused because the receipt is
        not carried.
     4. `git merge --no-ff` into `main`, restore run 1 (one output), and stage an unrelated
        change.
     - Result: `check_staged` returns `[]` and `main` returns 0.
   - **Where:** `tools/datasets/restricted_scan.py:644`, `:646–657`.
2. **A results receipt phrased slightly differently falls back to the tree-only match, or needs
   no carry at all.**
   - **Defect.** The carry rule uses `_FULL_RECEIPT`, but the floor uses `_RESULTS_RECEIPT`. A
     message where the floor regex matches but the full regex does not is still a results
     receipt while HEAD holds it. The carry check then matches on the tree alone, which is the
     round 90 (a) defect again.
   - **Reproduction (synthetic).** Each of these four messages was tested:
     - a time with seconds (`at 2026-11-25T11:00:00Z:`);
     - no final period (the receipt is followed by the `Co-Authored-By` trailer);
     - a comma instead of ` at `;
     - `Scan receipt: passed, not skipped; fit tier: results (files: …)`, the form the suite
       itself uses in `_receipt_repo`, which needs no carry at all.

     For each one:
     1. Commit three runs with that message. Its counts give a floor of 3 while it is in HEAD.
     2. Stage a §6 row with the tree and `benzene-taggar2006 1`. It is accepted.
     3. Commit, then restore run 1.
     - Result: `check_staged` returns `[]` and `main` returns 0. The control, a well-formed
       receipt, refuses the lowered row.
   - **Where:** `restricted_scan.py:318–320`, `:648–655`.
   - **Suggested fix for 1 and 2 together.** Outputs never decrease legitimately. So take the
     floor as the maximum `_RESULTS_RECEIPT` count over every commit message reachable from
     HEAD (`git log --format=%B HEAD`) as well as the ledger. That covers merges, squashes, any
     phrasing and lowered rows. Keep the carry rule only for bookkeeping.
3. **An unreadable retained file leaks its unexpected name through a traceback.**
   - **Defect.** Round 86's finding 2 is fixed for directories and links, but not for a regular
     file that cannot be read. The record read catches `OSError`, but the unconditional
     `fr.sha256(path)` then raises `PermissionError`, and its message contains the full path.
   - **Reproduction (synthetic).** Use a chain of two runs, plus
     `retained/benzene-taggar2006.48736829.fit-values.json` with mode `000`.
     - `check_staged` raises `PermissionError`, and the traceback contains `48736829`.
     - The command exits 1 with `48736829` on stderr.
   - The same pattern exists for a run's report: `sha256(report)` and `_signed_line` catch
     nothing but `UnicodeDecodeError`.
   - **Where:** `restricted_scan.py:581`, `tools/validation/fit_record.py:95`, `:385`, `:395`.

### Class B

1. **A huge JSON integer crashes the fit tier.** A value written as `1` followed by 400 zeros
   raises an unhandled `OverflowError` from `math.isfinite`. The message (`int too large to
   convert to float`) contains no value. `restricted_scan.py:466`, `fit_record.py:176`.
2. **An output bound to an `agent` submission is accepted.** A ledger logging a submission with
   runner `agent`, plus a record bound to it, gives `fit_tier` with no problems. The runner
   refuses agents (`AUTHORIZED_RUNNERS`), so such a record would have to be written by hand.
   The scan never checks the runner role or `freeze_ok`. `restricted_scan.py:452–457`.
3. **Finding 5's known limit is wider than documented.**
   - The latest record is not protected by any hash: nothing checks its own hash, and its report
     hash binds the report, not the record's fields. Nothing compares `pending_targets` with
     the report.
   - Probe: after the amendment was committed, the reviewer edited the current o-DCB record of
     the earlier revision. It added a second pending cell and turned its discrepancy into
     `no-target`. `main` still returned 0, and one discrepancy value dropped out of the tier.
   - Editing a value of the current record is not detected either. The docstring's "editing …
     any run's record … breaks the chain" does not hold for the latest run.
     `fit_record.py:28–30`, `restricted_scan.py:487–488`.
4. **A receipt's body can be text that does not render.**
   - Each of these was accepted by `check_receipt` as a body: `[//]: # (a hidden note)`, a
     single zero-width space, and `<div hidden>x</div>`.
   - A parent heading whose only body is a child heading's section was also accepted, so two
     receipts can share one review text.
   - These are the same class as round 86's finding 4, but beyond HTML comments.
     `tools/validation/evidence.py:215–232`.
5. **A test gap for round 90 (b).** The gate is a text-position check. The `print(...)` line
   before the write already contains `["rank"]["verified"]`, so two mutants pass all 61 tests
   in `test_v15c_release.py`:
   - the rank condition dropped from the check;
   - `raise SystemExit` replaced by `print`.

   `tests/test_v15c_release.py:873`, `docs/phase2/reproduce-benzene.md:226–228`.

### Round 86 findings

| Finding | Status | Evidence |
|---|---|---|
| 1. Staged preregistration fallback | Resolved | The gate test passes for `null`, `[]` and `"text"`. The reviewer's variants were also refused with "roster cannot be read": a staged `{}`, and the preregistration removed from the index. The revert was caught. |
| 2. Retained name in a traceback | Partly resolved | Directories and links give a redacted problem (test passes; revert caught). An unreadable file still leaks its name: **A3**. |
| 3. Case aliases sharing a heading | Resolved | Headings are compared by device and inode, and `DATASETS-LOCAL` is treated as local. Both reverts were caught. |
| 4. Comment-only body | Resolved for HTML comments | Closed, multiline and unclosed comments are all refused, and both reverts were caught. Other text that does not render: **B4**. |
| 5. Amendment invalidates a retained run | Resolved; known limit assessed | The unchanged run passes at revisions A and B. A targets hash named by no revision is refused, and so is a pending cell outside the roster. All three reverts were caught. The documented limit is wider than stated: **B3**. |
| 6. Rollback floor | Resolved for the tested cases; still open | The missing-carry and wrapped-receipt cases are fixed (reverts caught). A merge commit (**A1**) or a receipt phrased slightly differently (**A2**) still lowers the floor. |

### Rounds 89 and 90

- **The snippet is now correct.**
  - It selects the run by `RUN_ID`, refuses a stale run as `run.list` reports it, and refuses it
    again by the `run.stale` flag that `run.get` returns. `run.get` reads the run record and
    the result in one `ctx.read()` (`job_ops.py`, `run_get`).
  - It then checks that S_zz is estimated with a verified rank, and only then writes the file.
  - **Fixed model:** the snippet does not check this by name, but the check holds. Only
    `FixedRunOut` has `components` and `rank`, and `FixedModelOut` allows only
    `fixed`/`point-group`/`symmetry`. A search-model run raises `KeyError` before the write. It
    is refused with a traceback rather than a message, which is a usability point, not a
    finding.
- **`during_the_save` really does make the run stale between the two calls.** The rehearsal
  passed all six `ok` lines (synthetic S_zz off by 4.4e-11). The reviewer then swapped the
  `run.get` refusal message for a marker. The marker fired after the `run.list` check had
  passed, which shows the second connection made the run stale between `run.list` and
  `run.get`.
- **Round 90 (a) and the real ledger.**
  - Every commit message from `8156758` to `244d7d8` has a receipt. All 16 match their §6 rows
    by tree, time and whole status, as the new pattern requires.
  - `9283329`'s own receipt (tree `8ca7444…`, 17:58Z, pre-result) is still to be carried, as
    expected, and its tree equals the commit's tree.
  - The new rule refuses lowered counts, missing counts and a different time (gate tests and
    the reviewer's control).
  - It can still fall back to the tree-only match while the message holds a results receipt,
    or skip the carry entirely: **A2**.

### Readings and evidence

**Checks** (in `/private/tmp/r91` at `9283329`):
- `uv sync --locked`: passed.
- `pytest` on the six named files: **622 passed, 0 failed, 0 skipped** (11 min 43 s).
- `ruff check .`: all checks passed.
- `mypy`: no issues in 48 source files.
- D6h rehearsal on the workspace environment: passed.

**Revert checks**, applied one at a time and restored after each:

| Revert | Result |
|---|---|
| F1: non-object preregistration not treated as unreadable | caught |
| F2: non-file filter removed | caught |
| F3a: headings compared by path string | caught |
| F3b: `DATASETS-LOCAL` case recognition removed | caught |
| F4: comments not removed before the check | caught |
| F4b: unclosed comment kept | caught |
| F5: earlier revision judged by the current file | caught |
| F5b: unknown targets hash accepted | caught |
| F5c: roster-cell check on pending targets removed | caught |
| F6a: carry check removed | caught |
| F6b: no matching across line breaks | caught |
| R87: `run_report` writes an empty pending list | caught |
| `check_out` kept-output guard removed | caught |
| R90a: full match bypassed | caught |
| R90a: status not compared | caught |
| R89: `run.get` stale check removed | caught |
| R90b: write moved back before the check | caught |
| R90b: `estimated` dropped from the check | caught |
| R90b: rank dropped from the check | **missed** (B5) |
| R90b: check prints instead of refusing | **missed** (B5) |

Git history was read with `--format='%h %s'`. To compare receipts with §6 rows, the reviewer
printed only the `Scan receipt (Decision 11B)` text from each message body, with no author,
committer or trailer fields.

All test data were synthetic. The detached checkout was removed.

## Dispositions (provisional; pending the owner's decision)

| Finding | Disposition |
|---|---|
| A1. Merge commits | **Accept.** The floor becomes the largest count of any results receipt in every commit message reachable from `HEAD` (`git log --format=%B`), and in the committed and staged ledgers. The carry rule also applies to the receipt at the tip of each parent of a merge, which is the hand-owed row case. |
| A2. Receipt phrasing | **Accept.** The floor fix above reads every phrasing. A message that holds a results receipt but no well-formed `Scan receipt (Decision 11B)` line is refused. The suite's own short-form fixture is updated. |
| A3. Unreadable file leaks its name | **Accept.** Every read in the fit tier and the chain (hashes, reports, the signed line) catches `OSError`, and gives a redacted problem with no exception. |
| B1. Huge integer | **Accept.** An `OverflowError` gives a value-free problem. |
| B2. Agent-bound output | **Accept.** The fit tier refuses an output whose logged submission is not by an authorized runner, or comes before `freeze approved`. |
| B3. Known limit wider | **Accept, documented.** The ledger states the wider limit: the latest record is not bound by a hash until the next run retains it. A design change to bind it (for example, its SHA-256 in the results receipt) is left to the V1.5e audit. |
| B4. Receipt body that does not render | **Accept.** Link-reference definitions, whitespace and zero-width characters, and `hidden` HTML do not count as a body. A heading's body is the text before its first subheading. |
| B5. Test gap for the snippet check | **Accept.** A behavioural gate runs the snippet against a stand-in client whose result has an unverified rank or an S_zz that is not estimated. The snippet must exit non-zero, and write nothing. |
