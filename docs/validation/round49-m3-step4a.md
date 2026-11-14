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
  HTTP as in production, and the page sees them through the change feed. 16 tests × 3 browsers:
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
    when the jobs end; a stale proposal says why and is rejected with a reason;
  - **concurrency (04 §7):** the page's edit made at an older revision is refused with
    REVISION_CONFLICT and the robot's edit stays;
  - **the preview's ordering hazards (rounds 47–48):** a narrowed domain clamps the preview when
    `project.describe` arrives last (held 1.5 s by the test); the preview starts at the fit's φ
    (143°, beyond the default 90°) when the domain arrives last; a typographic minus is
    understood;
  - **latency (below).**
- **A CI job** "Browsers (Playwright on Chromium, Firefox, WebKit)" on ubuntu-latest, keeping the
  report and traces of failures.
- **The latency targets, measured on named hardware** (`DIPOLAR_RECORD_LATENCY=1`, recorded in
  `docs/validation/data/m3-latency/<browser>-<measurement>.json` with the machine, the browser's
  version and every sample): Intel Core i7-8750H (2.2 GHz, 12 threads), 32 GiB, macOS 15.8.1
  (darwin 24.6.0); browsers headless; the beta fixture (synthetic biphenyl), warm.

  | Browser | Preview: slider gesture → fresh residuals (target p95 < 100 ms) | Perception: robot `view.highlight` → arc drawn (target < 200 ms) |
  |---|---|---|
  | Chromium 159.0 | p50 17.8, **p95 19.0**, max 22.5 ms (60) | p50 12, max **13** ms (20) |
  | Firefox 159.0 | p50 19, **p95 22**, max 55 ms (60) | p50 14, max **16** ms (20) |
  | WebKit 27.2 | p50 19, **p95 22**, max 23 ms (60) | p50 12, max **15** ms (20) |

  The preview is timed in the page from the slider's input event to the preview line and
  residuals rendered with the new φ (a MutationObserver), at about eight gestures a second. The
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

**Baseline:** 48 browser tests (16 × 3) passed twice in a row; 823 Python passed
(`-m "not slow"`), 57 web unit tests, TypeScript (including the suite), mypy, Ruff, the generated
contract and projection parity.

## Round 49

(pending)
