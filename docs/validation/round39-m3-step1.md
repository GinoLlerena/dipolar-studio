# Validation rounds 39–40: M3 step 1 (Data and Fit workspaces, change feed in the browser)

Reviewer: GPT-6.1-Sol (Codex, reasoning effort high), independent of the implementation.
Under the medium plan there are at most two rounds per step. Class (A) findings block; class (B)
findings are documented.

## Before review: found by driving the page

The page was run against `dipolar serve` in Chromium (1440 × 900):
- open the example, run a fit as a job, and read the run;
- a second client (the robot token) changed the selection and the model, and the page followed
  within the feed's latency;
- undo from the title bar;
- an out-of-domain φ range came back as an inline error naming `phi_domain`.

Three defects were fixed before the review:
- the status bar said "Result unavailable" for a stale run; it now shows only the stale badge,
  because `describe_view` deliberately gives no fit summary for a stale run;
- the shared-view warnings appeared on every screen; they now appear in the Fit workspace only;
- a comment in `api.ts` named a forbidden network API; the boundary test caught it, and the
  comment was reworded rather than the test loosened.

## Round 39: NOT READY (five A), on commit fcbff94

The reviewer's web type check, the 12 web tests and the targeted Python feed tests passed.

| # | Class | Finding | Resolution |
|---|---|---|---|
| 1 | A | **Regularity was shown as identifiability.** `regular` also needs convergence and an interior optimum, so an imported ethane fit constrained to 50–90°, at full rank with its optimum on the 50° bound, was labelled "Not identifiable". | The fit summary carries `identifiable`, computed on the server: full inner and joint rank and no unidentified direction. The status bar shows identifiability, and separately "Not a regular optimum" when it applies. Test: `test_identifiability_is_not_regularity`. |
| 2 | A | **A delayed read could clear a stale badge.** The view advanced to science revision 2, then a run list read at revision 1 arrived and published `stale: false`. | Every read reports its revision. `RevisionMark` (feed.ts) keeps the newest revisions seen in responses and feed lines; an older response is dropped and read again, at most five times in a row. Test: `a response older than a seen revision is refused`. |
| 3 | A | **Reconnections accumulated abort listeners.** Each backoff wait left one listener attached for the store's lifetime. | The listener is removed when either the timer or the abort fires. |
| 4 | A | **A failed result read showed "Loading" for ever.** Nothing retried `run.get`. | Failed reads are recorded with their error. The run pane says that the result could not be read and offers Retry; every (re)connection retries automatically. |
| 5 | A | **A large preview crashed the plot.** Spreading 2 × 100 000 values into `Math.min` overflowed the call stack. | `extent()` (format.ts) uses a loop and skips non-finite values. Test: `extent copes with the 100 000-coupling limit`. |

Fixes 1, 2 and 5 were mutation-checked: breaking each makes its test fail. Fixes 3 and 4 live in
`studio.ts`, which needs a browser. Their automated coverage arrives with the Playwright suite in
M3 step 4.

## Round 40: NOT READY (one A), on commit 3624ce4

The reviewer confirmed that all five round-39 fixes resolve their findings. Further store checks
confirmed delayed-read rejection, bounded retries and recovery from a failed result read. The web
type check, the 14 web tests, the production build, the boundary tests and the contract check
passed.

| # | Class | Finding | Resolution |
|---|---|---|---|
| 1 | A | **A valid fit could crash the Fit workspace.** With every σ set to 1e-100 Hz the fit is regular and φ has a standard error of 1.6e-102, so `decimalsFor` asked `toFixed` for 103 places, which throws. | Beyond 12 decimals, values are written in scientific notation, to the significant figures the uncertainty implies (at most 16, the digits a double shows without noise). The uncertainty stays nonzero (`36.98502906869832 ± 1.6 × 10⁻¹⁰²`). Interval endpoints use the same rule (`atPlace`). `fixed` caps its decimals and can no longer throw. Test: `a tiny but valid uncertainty never crashes and stays nonzero`. |

The fix was mutation-checked: removing the scientific branch makes the test fail. Under the cap,
the round-40 fix was not reviewed again.

## Known limits (B, documented)

- **Staleness is by revision, not content.** A run stays stale after an undo that restores
  exactly its input, because an undo is a new revision. Comparing the science hash instead is
  the owner's decision; it changes the contract's meaning of `stale`.
- **No proposal inbox yet.** Feed lines in the `proposal` domain trigger no reads. The inbox is a
  later M3 step.
- **Large tables are rendered in full.** 100 000 rows render slowly; virtualised tables belong to
  the performance work in M3 step 4.
- **English only.** The strings are externalised; the Spanish catalogue comes later.
