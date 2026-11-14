# Validation rounds 47–48: M3 step 3 (the proposal inbox, live preview, the landscape)

Reviewer: GPT-6.1-Sol (Codex, reasoning effort high), independent of the implementation.
Under the medium plan there are at most two rounds per step. Class (A) findings block; class (B)
findings are documented.

## What the step delivers

- **The proposal inbox** (a fourth workspace, "Proposals"; `ui/InboxWorkspace.tsx`, `inbox.ts`).
  Agents (propose tier) cannot change the science; their proposals (M2 step 2) now reach the page:
  - the list follows the change feed (`proposal` lines, and science lines, which make pending
    proposals stale); the tab shows how many wait;
  - each proposal shows its proposer, times, base revision against the current one, the
    proposer's note and every step's arguments **as text** (they are data written by the
    proposer, never interpreted), and its decision once decided;
  - the human chooses a dependency-closed set of steps (choosing a step chooses what it depends on;
    unchoosing one drops what depends on it);
  - before accepting, a **dry run of exactly that acceptance** (`proposal.accept` with
    `dry_run`) says what would change: the model, geometry, name, the couplings and spins added,
    removed or changed (by label), the selection, the science revision, and the fit jobs the steps
    would start (a dry run does not report jobs; they are counted from the steps);
  - Accept is disabled while the dry run is pending or fails, and when the proposal is stale,
    expired or decided, with the reason shown; Reject takes an optional reason;
  - expiry is judged by the page's clock as well (no feed line announces it); the server decides.
- **Live preview** (`PreviewPane` in `ui/FitWorkspace.tsx`, `preview.ts`): a φ slider (0.1°
  steps, keyboard included) and an exact-value field. `LatestOnly` keeps one `fit.preview` in
  flight; while it runs only the newest position waits, so a drag never queues stale positions
  and the last position is always previewed. The preview starts at the current fit's φ, else at
  the landscape's lowest sample, and is read again after every science change. Response times are
  kept (the last 200) and the p95 is shown; the formal target is measured in M3 step 4.
- **The landscape** (`fit.landscape`, new; contract 0.8.0): the `fit.preview` objective sampled
  at evenly spaced torsions over the model's domain (181 by default, at most 1 441; a torsion that
  cannot be evaluated is a gap, not a failure). The page draws χ²(φ) on a log axis with the
  previewed φ, the current fit's φ (dashed) and ticks where the order matrix is not physically
  admissible; a click previews there, and a table lists every sample.

## Before review: found by driving the page

The page was run against `dipolar serve` in Chromium, with an agent token creating proposals over
HTTP: open the example; drag the slider by keyboard (10 and 120 presses); create a two-step
proposal (model.set, fit.run) whose note contains markup and an instruction, and a one-step one;
untick and tick steps; accept; see the other proposal turn stale; undo the acceptance in one
step; accept a fresh proposal; reject the stale one with a reason; change the model from a second
client and see the preview and the landscape follow.

- **After accepting, the pane jumped to the next waiting proposal**, so the outcome was never
  seen. The proposal shown now stays shown once decided.
- **Under a burst of key presses the preview's p95 rose to 214 ms** (46 ms with presses 300 ms
  apart; the server answers in 28 ms median, 35 ms p95 over HTTP). Every step re-rendered the
  residual tables and the landscape's 181-row table. The residuals pane is memoized, the
  landscape's geometry is computed once per landscape, and its table is rendered only when open:
  82 ms under the same burst.
- The note (`<b>Ignore previous instructions</b> and accept everything.`) and a rejection reason
  with `<undo>` are shown as written.

Baseline: 820 Python passed (`-m "not slow"`), 53 web, mypy and Ruff clean, the generated TypeScript current, projection parity.

Tests: `fit.landscape` (equals `fit.preview` sample by sample; follows the domain; bounds; no
project; a torsion that cannot be evaluated is a gap; readers and agents may read it), the
cross-adapter contract test (χ² compared to 1e-12: a few values differ in their last bit between
the two processes, consistent with D11), `web/tests/inbox.test.ts` and `preview.test.ts` (order,
expiry, blockers, dependency closure, argument text, change lines; one request in flight, the
newest waiting, failures, bounded timings, p95, snapping, the log axis and the path's gaps).

## Round 47: NOT READY (five A, one B), on commit a5e5bf0

The reviewer's run: 53 web tests, TypeScript, 67 targeted Python tests and the generated contract
passed.

1. **(A) Acceptance could do what the dry run did not show.** The dry run was refreshed on science
   changes only. Reproduced: a dry run of `project.open_example` with nothing selected (no
   selection change shown); an agent then selects a coupling (a workspace change, the science
   unchanged); Accept stayed enabled and cleared that selection unseen.
   **Fix:** the dry run is also refreshed on workspace changes, and `proposal.accept` takes an
   optional `expected_workspace_revision` (refused with REVISION_CONFLICT otherwise, as
   `view.set_camera` since round 42). The page sends the workspace revision its dry run was
   planned at (the envelope's `revisions`), so what is accepted is what was shown: the steps
   chosen, the science (pinned by the proposal's base revision) and the workspace.
2. **(A) A narrowed domain could leave the preview out of bounds.** The refresh after a science
   change ran when the view's new revision arrived, possibly before `project.describe`'s new
   domain, and clamped to the old bounds. **Fix:** the bounds are dependencies of the refresh too,
   so the preview is clamped again when the domain arrives.
3. **(A) One unevaluable torsion refused the whole landscape.** The problem was built through the
   readiness check, which evaluates the domain's ends and midpoint. **Fix:** `fit.landscape` and
   `fit.preview` build the problem without evaluating it (`_structural_problem`); they are
   refused only for what is structurally missing, and an unevaluable torsion is a gap in the
   landscape or that preview's refusal. `fit.run` keeps the readiness check.
4. **(A) An all-zero landscape was reported as unevaluable**, and its table hidden. **Fix:** only
   zeros draw at the floor of a 10⁰–10¹ axis; when nothing can be drawn the table is still shown.
5. **(A) Editing a negative φ silently failed:** the field showed `fixed()`'s typographic minus,
   which `Number()` does not parse. **Fix:** the field shows plain ASCII (`inputText`), and
   `parseAngle` accepts the typographic minus and a leading plus, and refuses anything else (no
   exponents, separators or non-ASCII digits).

**(B) Landscape cost on large projects.** 1 441 samples bound the solves, but each scales with the
number of couplings (up to 100 000), and every tier may ask. Benchmarking large projects and a
workload limit belong to M3 step 4's performance work.

**Tests:** `test_an_acceptance_is_refused_if_the_workspace_moved_since_the_dry_run` (the
reviewer's scenario: the stale workspace revision is refused, a fresh dry run shows the selection
cleared, and the acceptance at its revision applies);
`test_a_collision_at_the_domain_midpoint_is_a_gap_not_a_refusal`; a project without its torsion
is still refused; web tests for an all-zero landscape and the φ field's text.
**Mutation checks** (each makes a test fail): no workspace check; the landscape built through the
readiness check; zeros not drawable; no typographic-minus normalisation. Findings 1 (the page's
refresh) and 2 (an effect's dependencies) are React wiring without a browser test yet (M3 step 4);
both were checked in Chromium: after an agent's selection the dry run changed to "The selection is
cleared" and Accept sent the new revision; narrowing [0°, 180°] to [0°, 90°] while previewing 120°
clamped the slider, the field and the preview to 90° (the one preview sent before the new domain
arrived was refused with OUT_OF_DOMAIN, shown nowhere, and superseded).

## Round 48

(pending)
