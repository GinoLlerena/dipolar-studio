# Validation rounds 49–50: M3 step 4a (the browser suite, the latency targets)

Reviewer: GPT-6.1-Sol (Codex, reasoning effort high), independent of the implementation.
Under the medium plan there are at most two rounds per step. Class (A) findings block; class (B)
findings are documented.

M3 step 4 is done in two halves. **4a** (this one): the browser suite and the latency targets.
**4b** (next): the robot tutorial from an XYZ file, compared with the UI path; virtualised large
tables; a workload limit for the landscape.

## What the step delivers

- **A Playwright suite** (`web/e2e/`, `pnpm run e2e`): the built page against a real
  `dipolar serve` on **Chromium, Firefox and WebKit**. Each test starts its own server on a fresh
  project directory (`e2e/harness.ts`); other clients (the robot, the agent, the user) act over
  HTTP as in production, and the page sees them through the change feed. 19 tests × 3 browsers:
  - **launch:** a single-use link signs a tab in, leaves the address bar, survives a reload, and is
    refused a second time;
  - **workspaces:** open, fit and read a run; a run goes stale after another client's change and
    current again after its undo (staleness by content);
  - **the store (M3 step 1, round 39 fixes 3 and 4, until now without automated coverage):**
    reconnections leave no abort listener behind (counted on every live AbortSignal, against a tab
    that connected first time); a result that cannot be read says so and Retry reads it; a failed
    read is retried by itself when the feed reconnects (the page's clock is fast-forwarded past
    its 40-s watchdog);
  - **the inbox (M3 step 3, rounds 47–48):** a proposal's note is text; dependency-closed choice;
    the dry run; accepting; a workspace change by another client refreshes the dry run and the
    acceptance carries the workspace revision it saw; a dry run refused for the job quota is redone
    when the jobs end; the acceptance carries the workspace revision its dry run saw (a controlled
    race, round 49); a stale proposal says why and is rejected with a reason;
  - **concurrency (04 §7):** the page's edit made at an older revision is refused with
    REVISION_CONFLICT and the robot's edit stays;
  - **the preview's ordering hazards (rounds 47–49):** `project.describe` is held behind a barrier
    and each test asserts the hazardous state before releasing it: a narrowed domain clamps the
    preview; the preview starts at the fit's φ (143°, beyond the default 90°); an invalid first
    edit does not keep the preview from starting; a typographic minus is understood;
  - **replies that are not envelopes** (round 49): a reply that is not JSON is recorded as a
    failed read;
  - **latency (below).**
- **A CI job** "Browsers (Playwright on Chromium, Firefox, WebKit)" on ubuntu-latest, keeping the
  report and traces of failures.
- **The latency targets, measured on named hardware** (`DIPOLAR_RECORD_LATENCY=1`, recorded in
  `docs/validation/data/m3-latency/<browser>-<measurement>.json` with the machine, the browser's
  version and every sample): Intel Core i7-8750H (2.2 GHz, 12 threads), 32 GiB, macOS 15.8.1
  (darwin 24.6.0); browsers headless; the beta fixture (synthetic biphenyl), warm.

  | Browser | Preview: slider gesture → fresh residuals (target p95 < 100 ms) | Perception: robot `view.highlight` → arc drawn (target < 200 ms) |
  |---|---|---|
  | Chromium 159.0 | p50 17.7, **p95 18.7**, max 19.8 ms (60) | p50 11, max **13** ms (20) |
  | Firefox 159.0 | p50 20, **p95 53**, max 82 ms (60) | p50 14, max **17** ms (20) |
  | WebKit 27.2 | p50 19, **p95 33**, max 105 ms (60) | p50 12, max **15** ms (20) |

  The target is the p95; one WebKit sample of 60 exceeded 100 ms. Recorded after round 50 with
  the completion condition below. Earlier recordings, with weaker conditions, gave 19–39 ms p95
  and 13–20 ms; run-to-run spread on this machine is of that order.

  The preview is timed in the page from the slider's input event until the preview line shows the
  new φ *and* the preview's residual table, marked with that φ (`data-phi`), *displays* every
  row's D calc (to 0.1 Hz) and residual (to 0.01 Hz) as `fit.preview` gives them at that φ (read
  from the server before the timed loop). A MutationObserver on the document times DOM updates,
  not painted frames; about eight gestures a second. The
  perception time runs from just before the robot's HTTP call to the page's mutation (both clocks
  on one machine). CI's shared runners are not named hardware: there the tests only guard against
  regressions (p95 < 400 ms, max < 800 ms).

## Before review: found by the suite

- **A typed φ could be overwritten by the preview's automatic start** (WebKit, consistently).
  Typing in the first moments after the pane appeared, before the first preview, left text that
  the start (an effect running a render late) replaced with the landscape's minimum. The start now
  stands down once the user types, and the effects read the φ last asked for from a ref, not from
  a render-old closure. The φ field's Enter and blur read the field itself.
- **A malformed reply crashed the store.** A JSON reply without an error body (a proxy's page, a
  truncated body) made the store read `error.code` of undefined, so a failed result read was
  never recorded. `callOperation` now turns any reply that is not an operation envelope into an
  INTERNAL error envelope ("the server's reply was not an operation envelope (HTTP n)"); the
  reconnection test uses such a reply.

**Mutation checks** (each, rebuilt, makes its browser test fail): the reconnection wait keeps its
abort listener; no retry of failed reads on (re)connection; a failed read not recorded; the dry
run's key without the workspace; without the jobs; the acceptance without
`expected_workspace_revision`; the preview's refresh without the domain's bounds; the start
without the domain check; no typing guard (WebKit).

**Baseline (before review):** 48 browser tests (16 × 3) passed twice in a row; 823 Python passed
(`-m "not slow"`), 57 web unit tests, TypeScript (including the suite), mypy, Ruff, the generated
contract and projection parity.

## Round 49: NOT READY (six A), on commit 7e202d6

The reviewer's checks: build, 57 web unit tests, TypeScript, 16 Chromium tests passed; restoring
the abort-listener leak failed its test (4 listeners against 1); disabling the watchdog or the
reconnection retry failed the fake-clock test; the concurrency test held; the recorded summaries
match their samples.

1. **(A) Typing could keep the preview from ever starting.** With the first landscape held back,
   typing `-` and leaving the field left the typing guard on for good. **Fix:** committing the
   field (Enter or leaving it) ends the edit; an invalid entry before any preview resumes the
   automatic start. Test: the reviewer's sequence (the landscape held, `-`, blur, release).
2. **(A) Malformed success replies passed the reply check** (`{"ok":true,"result":{}}`: the run
   stayed "loading" with no Retry), and a reply that is not JSON threw before the check. **Fix:**
   a success envelope needs `operation`, an object `result`, integer `revisions` and `dry_run`; a
   parse failure becomes the INTERNAL envelope too. Tests: `web/tests/api.test.ts` (nine malformed
   shapes) and a browser test with an HTML 502 for `run.get`.
3. **(A) Teardown left the server running.** SIGTERM and SIGKILL reached only `uv`; with a feed
   open, the server outlived its deleted directory by about 10 s. **Fix:** the server runs in its
   own process group; `stop()` signals the group, escalates to SIGKILL after 3 s, waits until no
   process is left, then removes the directory; a failed start is cleaned up the same way.
   Checked: with a live feed the port is closed and the directory gone when `stop()` returns.
4. **(A) The latency test did not establish fresh residuals:** it watched only the preview line;
   an empty residual table passed. **Fix:** the preview's residual table records its φ
   (`data-phi`), and a sample completes only when the line and the table show the new φ and the
   table has a row for every coupling. The measurements were recorded again (above).
5. **(A) The workspace test did not prove the acceptance carries the dry run's revision:**
   sending the page's own revision passed too. **Fix:** a controlled race. The page's feed is cut
   (its watchdog fired on a fake clock, reconnections refused); an agent changes the selection; a
   new choice of steps makes a dry run that the server plans at the new revision, which the page
   does not know. The acceptance must carry that revision (and is accepted); the page's own
   would be refused.
6. **(A) The preview race tests relied on a 1.5-s delay**, which did not guarantee that the domain
   arrived last. **Fix:** `project.describe` is held behind a barrier, and each test asserts the
   hazardous state before releasing it: the view's new revision shown with the old domain's
   maximum; the fit's φ (143°) and the landscape shown with the default domain's.

**(B) Shutting down `dipolar serve` waits for open change feeds.** On SIGTERM, uvicorn's graceful
shutdown takes 2 s, but each open feed waits in a worker thread for up to one heartbeat (15 s)
before the process can exit. Waking the feeds at shutdown belongs to step 4b's performance work.

**Mutation checks** (each makes its test fail): the typing guard never released; an empty preview
residual table; the page's workspace revision sent instead of the dry run's; the start without the
domain check; the refresh without the bounds; no revisions check in the reply check (unit test);
the JSON parse not caught (browser).

**After the fixes:** 57 browser tests (19 × 3) passed twice in a row; 59 web unit tests; the
boundary tests; TypeScript (app and suite).

## Round 50: NOT READY (two A), on commit b64ba42

The reviewer confirmed the round-49 fixes: the typing, workspace-revision, empty-table and
ordering mutants now fail; `asEnvelope` agrees with the server's envelope (object results, a
required `dry_run`, bounded revisions); committing invalid text after the landscape arrives
starts the preview. 19 Chromium tests, 59 unit tests and both TypeScript checks passed; three
early store-test stalls did not reproduce in isolation or in five repetitions of the races.
Process-group cleanup was checked on macOS, not on Linux (CI runs it there).

1. **(A) The latency test still allowed stale residual values:** with the rows frozen at 37°
   and the φ marker updating, it passed (p95 36.9 ms) while the first row showed −0.72 Hz instead
   of +322.32 Hz. **Fix:** the expected D calc and residual of every row at every φ are read from
   the server before the timed loop, and a sample completes only when the table displays them.
   The reviewer's mutant now fails the test; the measurements were recorded again (above).
2. **(A) This overview kept superseded claims** (16 × 3 tests; a 1.5-s delay). Updated: 19 × 3 and
   the barriers; the earlier counts stay in the baseline section.

Under the cap, these fixes were not reviewed again. After them: 57 browser tests (19 × 3) passed.

**CI after round 50.** The first CI run of the browser job on this commit failed once, on Firefox:
the perception test clicked the Structure tab, which took focus but was not selected (the page was
also reconnecting its feed), so no arc appeared. It did not reproduce locally (each test twice on
three browsers: 114 passed). The tests now open tabs through `openTab`, which clicks until the tab
reports itself selected. **(B)** The cause is not known; a retried click could also hide a real
swallowed click. If it is the page's, the M3 step 4b runs should show it again.
