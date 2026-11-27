# Round 92: scoped pre-freeze review of the round 91 fixes (Claude Opus, independent)

The owner decided this review after round 91 was NOT READY ("Fix all, scoped Claude round 92",
2026-11-26). A fresh Claude Opus reviewer (effort high), independent of the orchestrator,
reviewed branch `v1.5d-prefreeze` at `95ffcb9` in a tracked-only worktree, on 2026-11-26. The
scope was two questions: are round 91's eight findings resolved, and did the fixes introduce a
new defect? Verdict: **NOT READY** (1 A, 7 B).

The report is below, as delivered. Provisional dispositions follow it. After a NOT READY round,
the owner decides how to proceed before any freeze.

## Report

### Class A

1. **An unreadable directory still leaks an unexpected file name through a traceback (A3 is
   only partly fixed).**
   - **Defect.** The round 91 fix guards file reads (`sha256`, `read_text`, `read_bytes`), but
     not the `stat` calls that come before them. On Python 3.12 (the locked interpreter),
     `Path.is_file()` and `Path.is_symlink()` raise `PermissionError` on `EACCES`. That happens
     when a directory can be listed but not searched. The exception message is the full path, so
     an unexpected name ends up on stderr. This is the same symptom as round 91's A3, and the
     disposition promised "no exception".
   - **Synthetic reproduction.**
     1. Build a chain of 3 runs.
     2. Add `retained/benzene-taggar2006.0487368.fit-values.json`.
     3. Run `chmod -R 444` on `retained/`, the usual way to make an archive read-only. It removes
        the search bit from the directory.
     - Result: `restricted_scan.py --root <fixture>` exits 1, prints nothing on stdout, and the
       last stderr line is a `PermissionError` that contains `0487368`.
     - The traceback goes through the `odd` filter. When a directory higher up, or `retained/`
       itself, cannot be searched, the crash comes earlier, at `folder.is_dir()` or
       `kept.is_dir()`. That path names only the directory, but it is still an unhandled
       exception.
   - **Where:** `tools/datasets/restricted_scan.py:571`, and also `:563` and `:565`.
   - **Suggested fix.** Treat an `OSError` from `is_dir`, `is_file` or `is_symlink` as "not a
     regular file" or "cannot be read", with a redacted name. Add a test that patches
     `Path.stat` the way `_unreadable` patches reads.

### Class B

1. **The history-wide floor counts quoted text, and a false floor can never be removed.**
   - Any reachable commit message containing `passed, not skipped; fit tier: results (files:
     benzene-taggar2006 N, odcb-chandrakumar1993 M)` sets the floor, for example one quoting
     round 91's reproduction.
   - Reproduction: a pre-result fixture, then a docs commit whose message quotes the short form
     with `3`, then two unrelated commits. `check_staged` still returns "fewer
     benzene-taggar2006 fit outputs than the latest scan receipt". The only ways out are
     rewriting public history or changing the validator after the freeze.
   - The real history has no such text today: no message from the root commit to `95ffcb9`
     matches.
   - Related: a `HEAD` message that mentions "Scan receipt" only in prose blocks the next commit
     with the Decision 11B form refusal. That one clears after one commit.
   - Recommend a ledger rule before the freeze: no commit message may quote a results receipt
     that is not its own. Otherwise, narrow the history floor. `restricted_scan.py:674`, `:682`.
2. **The carry rule checks only the first receipt in a message.** `_FULL_RECEIPT.search` takes
   the first match. In a squash-merge message holding two receipts, where the first is carried
   and the second is not, `check_staged` returns `[]`. The floor is not affected, and the
   project uses merge commits (30 of them), so this is bookkeeping only.
   `restricted_scan.py:680`.
3. **What remains of round 91's B2: the scan does not apply `freeze_ok`.** With a `decision
   changed` row after `freeze approved` and an owner submission after both, the runner's
   `authorize` refuses (freeze_ok). The fit tier still reports 0 problems for a record bound to
   that submission, and such a record would have to be written by hand. The disposition scoped
   B2 to the runner role and the freeze time, and that scope is met. `restricted_scan.py:544`.
4. **What remains of round 91's B4. Detecting non-rendering text by listing cases is incomplete
   in both directions.**
   - Still accepted as a body: `&#8203;`, `&nbsp;`, U+2800, U+3164, U+2063, U+034F,
     `<div hidden><div>x</div>y</div>` (nested), an unclosed `<div hidden>`, `[](url)`, `***`,
     an empty table, and `style="display:none"`.
   - Now refused although they render:
     - `[Note]: prose…`, which is not a valid link definition;
     - a body that is only a footnote;
     - a line that is only an autolink, `<https://…>`;
     - `<span class="not-hidden">Agreed.</span>`;
     - a body that starts with a subheading.

     All of these fail closed. `evidence.py:217–219`, `:237`.
5. **A deeply nested JSON file crashes the tier.** `"[" * 200000` as a fit output raises
   `RecursionError` from `json.loads`, which is not caught. No name or value leaks.
   `restricted_scan.py:437–438`.
6. **Test gaps.** Six revert mutants pass every test; see the revert checks below. Of these,
   only the couplings and targets read guards protect against a real crash, and the reviewer
   confirmed by probe that both give value-free problems. `_signed_line`'s guard is reached only
   if the file becomes unreadable between the hash and the read.
7. **B3's known-limit wording.** Documenting the limit before the freeze is acceptable: no
   record exists until the first comparison, and the limit concerns hand edits, not the
   science. One sentence overstates, though. "The owner's receipt, and the next run's
   `previous_sha256`, are the record of it": the receipt records only counts, and the next run's
   hash fixes whatever the latest record holds at that moment, edits included. Suggest saying
   exactly that. `gates.md:873`, `fit_record.py:30`.

### Round 91 findings

| Finding | Status | Evidence |
|---|---|---|
| A1. Merge drops the carry and the floor | **Resolved** | The `_merged` gates pass. Removing either the history floor or the merge-parent carry is caught. The reviewer replayed the carry rule over every non-merge commit from `b413038` on, including the children of `f472b16`, `a0f8c08` and `7d35eb5`. It demands exactly the rows the ledger has: `31f7f21`, `b0e3c1e` and `fdebbf6` are all carried, none is malformed, and every receipt's tree equals its commit's tree. |
| A2. Phrasing variants | **Resolved** | All four phrasings are refused, and each still sets a floor of 3. All 23 real receipts from `b413038` to `95ffcb9` (one per message) match the tightened `_FULL_RECEIPT`. Removing the form refusal is caught. Loosening the status pattern is **missed** (B6). |
| A3. Unreadable file leaks its name | **Partly resolved** | A mode-000 retained file, report, current output and couplings file each give a redacted problem, with no exception. A directory that can be listed but not searched still leaks: **Class A 1**. |
| B1. Huge integer | **Resolved** | `10**400` gives value-free problems, and removing the guard is caught. |
| B2. Agent-bound output | **Resolved (as scoped)** | Refused: an agent, a time before the freeze, no freeze, a time equal to the freeze, and a second freeze (a parse error). A submission after `first access` is accepted by both the scan and `authorize`, which is consistent. The chronology `freeze_ok` checks is not applied (B3). The boundary mutants are missed (B6). |
| B3. Known limit wider | **Documented; acceptable** | See B7 for the wording. |
| B4. Non-rendering body | **Resolved for the reported cases** | Every reported case is refused (4 gates plus a control). Other cases still pass, or are refused although they render (B4). |
| B5. Snippet test gap | **Resolved** | The behavioural gate catches both round 91 mutants: the rank dropped, and `print` in place of the raise. |

### Readings and evidence

**Checks** (in `/private/tmp/r92` at `95ffcb9`, run one after another):
- `uv sync --locked`: passed.
- `pytest` on the six named files: **645 passed, 0 failed, 0 skipped** (355 s). There were no
  skips to name.
- `ruff check .`: all checks passed.
- `mypy`: no issues in 48 source files.
- `restricted_scan.py --root .`: `fit tier: pre-result (no experimental fit is logged and no
  local fit output exists)`, then `receipt: fit tier: pre-result`. Exit 1, with one problem:
  "the last commit's scan receipt is not carried into §6 with its time and status". This is
  expected: it is `95ffcb9`'s own pre-result receipt at 19:12Z, and its tree `8bb45cc…` equals
  the commit's tree. That row is owed by the next commit.
- **Performance of the history-wide floor:** 50,000 synthetic commits with about 295 MB of
  messages took 19.1 s for `check_staged`, and time grows linearly with the amount of text. The
  real repo has 231 commits.

**Revert checks** (one at a time, each restored; the tree was clean afterwards):

| Revert | Result |
|---|---|
| A1: floor from `HEAD`'s message only | caught |
| A1: merge parents ignored | caught |
| A2: form refusal removed | caught |
| A2: status pattern loosened back to `(.+?)` | **missed** |
| A3: retained digest unguarded | caught |
| A3: chain report hash unguarded | caught |
| A3: `_signed_line` narrowed to `UnicodeDecodeError` | **missed** (masked by the hash guard) |
| A3: couplings read unguarded | **missed** |
| A3: targets read unguarded | **missed** |
| B1: overflow guard removed | caught |
| B2: authorized filter removed | caught |
| B2: problem removed | caught |
| B2: `<=` changed to `<` (a time equal to the freeze accepted) | **missed** |
| B2: filter `>` changed to `>=` | **missed** |
| B4: hidden-element removal dropped | caught |
| B4: link-definition removal dropped | caught |
| B4: invisible-character removal dropped | caught |
| B4: subheading stop limited by level | caught |
| B4: bare-tag stripping dropped | **missed** |
| B5: rank dropped from the check | caught |
| B5: check prints instead of refusing | caught |

In all, 21 reverts: 15 caught and 6 missed, all six in the fit-tier and evidence code and none
in the snippet. (As delivered, the report also counted the two B2 boundary mutants as one and
reached 7. The table lists them separately.)

Git history was read with `--format='%h %s'`. Only `Scan receipt (Decision 11B)` text was
printed from message bodies. Nothing under the owner's `datasets-local/` was opened, and
nothing was run in the main clone except the worktree commands.

All test data were synthetic. The detached checkout was removed.

## Dispositions (provisional; pending the owner's decision)

| Finding | Disposition |
|---|---|
| A1. Unreadable directory | **Accept.** Every `is_dir`, `is_file` and `is_symlink` in the fit tier and the chain treats an `OSError` as a value-free "cannot be read", with redacted names. A test patches `Path.stat`. |
| B1. Quoted receipts set a false floor | **Accept.** The history floor reads only full Decision 11B receipts (`_FULL_RECEIPT`, a commit's own tree), and short forms only in the ledger. A ledger rule: a commit message carries only its own receipt. |
| B2. Only the first receipt carried | **Accept.** Every full receipt in a carried message must be carried. |
| B3. `freeze_ok` not applied | **Accept.** The tier applies the same chronology as the runner. |
| B4. Listing non-rendering cases | **Accept a positive rule.** A body needs a line with a word of visible letters, after markup, entities and invisible characters are removed. The remaining edge cases fail closed or are left to the owner's attestation, as agreed in round 85 (B). |
| B5. Deep nesting | **Accept.** `RecursionError` gives a value-free problem. |
| B6. Test gaps | **Accept.** A test for each missed revert. |
| B7. Known-limit wording | **Accept.** Say exactly what the receipt and the next run's hash record. |
