# Re-baseline after M0 (M0 step 5)

**Status: approved by the owner on 2026-11-09** ("go"). M1 runs in the slice-sized steps below.

Plan §8 says that phase sizes are re-baselined after M0 from
measured velocity, and that no calendar dates are fixed before then. This page gives:

- the measurements;
- what they do and do not support;
- a proposed shape for M1–M3.

The owner decides.

## What M0 measured

| | M0 |
|---|---|
| Elapsed time | 2026-11-07 19:56 → 2026-11-08 (first commit to spikes complete) |
| Product code (non-blank lines) | dipolar-core 219, dipolar-app 1725, web 357, robot 104 |
| Tests and spikes | 1164 lines of tests, 1134 lines of spikes; 189 tests (188 in CI, plus one long `-m slow` run) |
| Independent tooling | 533 lines (`tools/reference`, legacy harness) |
| Independent review | GPT-6.1-Sol rounds 8–9 on the slice, rounds 10–12 on the spikes (READY WITH MINOR CHANGES at round 12) |
| Defects found after "done" | **step 3: 7 + 2 review findings; step 4: 11 spike findings + 7 + 4 review findings (2 major)**, all fixed (31 in total) |

## What this supports, and what it does not

- **Code is not the bottleneck.** With AI-assisted development the code for a well-specified step
  arrived within hours. The time went to three things:
  1. specifying the contract precisely;
  2. adversarial testing (the review rounds and the spikes);
  3. fixing what they found.
- **The rework rate is the real velocity signal.** About 1.3 findings per 100 lines of product code
  survived the first "done". The reviews of the spikes still found two major security gaps, one
  of them introduced by the fix for the other. Every finding was a real defect: durability,
  coercion, a stale file, an envelope mismatch, a code exposed on a command line, a cleanup that
  followed a symlink. Planning has to assume that each step needs an independent review round and
  a fix round, and that each fix is reviewed again.
- **Wall-clock hours do not measure the owner's effort.** The owner's review and decision time
  was not logged. **Proposal:** from M1, log owner hours per step in `docs/STATUS.md`, so the
  1.0 estimate after the beta has real data (plan §8: "1.0 date estimated only after the beta").

## Proposed shape for M1–M3

Each milestone is cut into **steps the size of the M0 slice**. Each step ends with tests, an
independent review round, fixes and a stopping-point tag, as M0 did.

| Milestone | Steps (proposal) | Relative size |
|---|---|---|
| **M1 scientific core** | 1. D3 stack: grid/Sobol multistart, bounded TRF refinement on the residual vector, full-Jacobian covariance, profiles vs slices, validity flags. Grows from spike 1 into dipolar-core. 2. Frozen frame contract and C2(z)/C1 constraints. 3. Four-site jump model, with explicit averaging equal to the relabelling shortcut. 4. CSV/XYZ import and JSON v1. 5. Gates (a)–(e), including coverage (`-m slow`) and 8CB reproduction | ≈ 5 slice-sized steps; the most numerical risk |
| **M2 application layer** | 1. Operations the beta UI needs, with TypeScript generated from the snapshot (spike 2 made it possible). 2. Idempotency, dry run, proposals, undo. 3. Jobs, D11 runs and the authenticated event stream (D10 note). 4. Scene description, `describe_view` and the SVG renderer with parity | ≈ 4 steps |
| **M3 browser beta** | 1. Data and Fit workspaces. 2. Structure view and reconciliation. 3. Live preview, stale badges and landscape. 4. Playwright on Chromium, Firefox and WebKit; the robot tutorial; the p95 preview target | ≈ 4 steps |

**Scope adjustments proposed by the spikes** (none add features):

- **M1:** refinement uses `least_squares` on residuals (spike 1). The frozen optimum convention is
  unchanged.
- **M2:**
  - add a Windows CI job, for the `msvcrt` lock path and line endings (spike 3);
  - the event stream uses authenticated fetch streaming (D10).
- **Before any packaged release:** ship a licence file in the wheels (spike 3, D9 checklist).
- **Unchanged:** power-loss testing of the journal stays out of scope for the beta (spike 4).

**No calendar dates are proposed.** Two things would allow them: steps of a known size, and owner
hours logged from M1. Both exist from now on. A first date estimate becomes meaningful after two
or three M1 steps.
