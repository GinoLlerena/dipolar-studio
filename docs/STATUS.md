# Status

**M3 step 4a (the browser suite, the latency targets) is done: tag `m3-step4a`.**
- **Playwright on Chromium, Firefox and WebKit** (`web/e2e/`, `pnpm run e2e`, a new CI job): the
  page against a real `dipolar serve`, with the robot and an agent acting over HTTP. It covers the
  launch, the workspaces, staleness by content, the two store fixes of step 1 that waited for a
  browser, the inbox's rounds 47–48 regressions, a REVISION_CONFLICT, and the preview's ordering
  hazards. 19 tests × 3 browsers.
- **The latency targets, on named hardware** (i7-8750H, macOS, headless): preview p95 from a slider
  gesture to the residual table displaying the new values 19–53 ms (target 100 ms); a robot's
  highlight drawn in at most 13–17 ms (target 200 ms), on all three browsers.
- **Found by the suite:** a typed φ could be overwritten by the preview's automatic start
  (WebKit); a malformed reply crashed the store. Both fixed.
- Rounds 49 and 50 returned NOT READY (six and two class-(A) findings: the typing guard, the reply
  check, the harness's teardown, tests that did not prove their claims, stale doc claims); all
  fixed and mutation-checked, the round-50 fixes not reviewed again, under the cap.

See [round49-m3-step4a.md](validation/round49-m3-step4a.md).

**M3 step 3 (the proposal inbox, live preview, the landscape) is done: tag `m3-step3`.**
- **The proposal inbox:** a Proposals workspace follows the feed; each proposal shows its note
  and arguments as text, a dependency-closed choice of steps, and a dry run of exactly the
  acceptance before Accept; stale, expired and decided proposals say why they cannot be accepted.
- **Live preview:** a φ slider with one `fit.preview` in flight and only the newest position
  waiting; it follows science changes and shows its response p95.
- **The landscape:** `fit.landscape` (new; contract 0.8.0) samples the preview's χ² over the
  torsion domain; the page draws it on a log axis with the previewed and fitted φ.

Round 47 returned NOT READY (five class-(A) findings: an acceptance could differ from its dry
run in the workspace; a narrowed domain; a landscape refused for one torsion; all-zero χ²; a
negative φ in the field), round 48 two (a failed dry run cached across a job's end; a lost
starting angle); all were fixed and mutation-checked or checked in Chromium, the round-48 fixes
not reviewed again, under the cap. See
[round47-m3-step3.md](validation/round47-m3-step3.md).

**Interval warm starts are done: tag `interval-warm-starts`.** Profile intervals are first searched with
continuation: each re-minimization starts where it ended at the nearest value already computed,
instead of at its basin (`FIT_VERSION` varpro-trf.9). Continuation can only overstate χ², so the
values the interval's acceptance rests on (both sides of each endpoint, and the component probes)
are recomputed from the basins; on any disagreement a cold pass decides. About 17–20% less CPU on
the protocol seeds. Gate (c) rerun on all 1 000 seeds: the same hits (φ 701, Szz 691, Δ 684), every
endpoint within 1.3e-12 of its interval's width. Rounds 45 and 46 returned NOT READY (one A each:
merged starts could follow the wrong valley; the continuity check used warm values); both were
fixed and mutation-checked, the round-46 fix not reviewed again, under the cap. See
[round45-interval-warm-starts.md](validation/round45-interval-warm-starts.md).

**Journal compaction is done: tag `journal-compaction`.** Verified snapshots of the whole session
state bound the journal and the request table: every 5 000 records the state is written as a
snapshot (kept until the next is complete), the covered journal moves to `archive/` (never
deleted), and opening replays only what follows. Crashes at every step are recovered; a deleted
active journal is refused. Rounds 43 and 44 returned NOT READY (one class-(A) finding each); both
were fixed and mutation-checked, the round-44 fixes not reviewed again, under the cap. See the
ADR-0014 amendment and [round43-journal-compaction.md](validation/round43-journal-compaction.md).

**M3 step 2 (Structure view, couplings reconciliation, staleness by content) is done: tag
`m3-step2`.**
- **Staleness by content** (the owner's decision): a run is stale when the science differs from
  its input by content; an undo that restores the exact input makes it current again
  (ADR-0011 amendment; the coupling-ID allocator is excluded; derived on replay, never journaled).
- **Structure view:** the shared scene in the browser with misfit arcs (colour and width),
  selection, layers, and a camera committed once per gesture with `expected_workspace_revision`.
- **Couplings CSV import in the browser:** keyboard mapping, collisions flagged, each pair's values
  now and after, the full diff as CSV, and an import of exactly the mapping shown.
- **Stricter numbers:** CSV values and XYZ coordinates must be plain ASCII decimals.

Contract 0.7.0. Rounds 41 and 42 returned NOT READY (three and two class-(A) findings); all were
fixed and mutation-checked; the round-42 fixes were not reviewed again, under the cap. See
[round41-m3-step2.md](validation/round41-m3-step2.md).

**M3 step 1 (the Data and Fit workspaces): tag `m3-step1`.** The browser page is now a
working client:
- it follows the change feed (`GET /api/v1/events`) instead of polling, and re-reads through
  registry operations;
- the Data workspace opens, loads, imports and exports projects, edits the model and the torsion,
  and lists couplings and spins with shared selection;
- the Fit workspace runs fits as jobs (with cancel), lists jobs and runs with stale badges, and
  shows each run's estimates, intervals, quality, validity and residuals;
- the status bar keeps convergence, adequacy, identifiability and admissibility separate.

Feed lines are part of the contract (0.6.0). Rounds 39 and 40 returned NOT READY (five and one
class-(A) findings). All were fixed and mutation-checked, except two store fixes that need a
browser test (M3 step 4); the round-40 fix was not reviewed again, under the cap. See "M3" below
and [round39-m3-step1.md](validation/round39-m3-step1.md).

**The M2 exit audit passed: tag `m2-exit-audit`.** Rounds 37 and 38 (three and two class-(A) findings, all about overstated evidence) were fixed; the round-38 fixes were not reviewed again, under the cap. Every M2 exit criterion and every 04 §7 and
§8.6 check maps to a passing test, with the deviations recorded (SVG instead of PNG; the Python
adapter's path stands in for the UI's until M3). The benchmark is published, and the robot now
runs the full M2 scenario over HTTP. See [m2-exit-audit.md](validation/m2-exit-audit.md) and
[m2-benchmark.json](validation/data/m2-benchmark.json).

**M2, the application layer, is complete: tag `m2-complete`** (step 4, tag `m2-step4`). Step 4
added the scene description, `render.describe_view` and the server-side SVG renderer. The
browser's projection (`web/src/scene/projection.ts`) is checked against the Python renderer in CI.
Rounds 35 and 36 each returned NOT READY (five class-(A) findings each). All were fixed and
mutation-checked; the round-36 fixes were not reviewed again, under the cap. See "Step 4" below and
[round35-m2-step4.md](validation/round35-m2-step4.md).

**M2 step 3 (jobs, D11 runs, the authenticated event stream) is done: tag `m2-step3`.**
- `fit.run` returns a job at once; the fit runs in a supervised worker process.
- Results are durable runs, verified by hash and reported `stale` after an edit.
- Agents propose fits.
- `GET /api/v1/events` streams every change.

Rounds 33 and 34 each returned NOT READY (eight and five class-(A) findings). All were fixed and
mutation-checked; the round-34 fixes were not reviewed again, under the cap. See "Step 3" below
and [round33-m2-step3.md](validation/round33-m2-step3.md).

**M2 step 2 (idempotency keys, dry run, proposals, undo) is done: tag `m2-step2`.**
- Commands take a `request_id` and are applied at most once, even across a restart.
- Any command can be dry-run.
- Agents change the science only through proposals that a human accepts, atomically.
- Undo and redo are global, chronological and audited.

Rounds 31 and 32 each returned NOT READY (three class-(A) findings each). All were fixed and
mutation-checked; the round-32 fixes were not reviewed again, under the cap. See "Step 2" below
and [round31-m2-step2.md](validation/round31-m2-step2.md).

**M2 step 1b (TypeScript generated from the registry snapshot) is done: tag `m2-step1b`, also
the stopping point.** `tools/codegen/ts_contract.py` writes `web/src/generated/contract.ts` and
`conformance.ts` from `registry.snapshot.json`. `callOperation` takes one operation name and
exactly its arguments, and returns that operation's result type. CI fails if the generated
files are stale. Rounds 29 and 30 returned NOT READY (five and two class-(A) findings). All were
fixed and mutation-checked; the round-30 fixes were not reviewed again, under the cap. See "Step
1b" below and [round29-m2-step1b.md](validation/round29-m2-step1b.md) (rounds 29 and 30).

**M2 step 1 (the science operations) is done: tag `m2-step1`.** Rounds 27 and 28 each returned NOT READY (five and two findings). All were fixed and mutation-checked; the round-28 fixes were not reviewed again, under the cap. Every project the
core can fit now reaches the operations:
- imported XYZ geometry with a declared torsion;
- the four-site jump model;
- the C2(z) and C1 order models;
- both template frames and the [0, 180] domain.

The new operations are `fit.run` (with the interval policy), `model.set`, `project.import_xyz`,
`molecule.set_torsion`, `couplings.reconcile`, `couplings.import`, `project.load` and
`project.export`. The contract version is now 0.2.0. See
[round27-m2-step1.md](validation/round27-m2-step1.md) (rounds 27 and 28).

**M1 is complete: step 5 (the acceptance gates) is done, tag `m1-step5`.** Round 25 returned NOT
READY on two test-assertion gaps, both fixed; round 26 returned **READY**. Every frozen gate now
names an engine test, and a ledger test fails if one goes missing. Gate (c) holds on the engine:
over the 1000 frozen seeds the 68.3% profile intervals cover φ, Szz and Δ in 70.1%, 69.1% and 68.4%
of seeds. That is inside the 64.5–72.1% band, every interval is supported, and the counts equal the
reference implementation's (701, 691, 684). The record names the fitter version and its inputs. See
[round25-m1-step5.md](validation/round25-m1-step5.md) (rounds 25 and 26).

**M1 steps 3 and 4 are done: tags `m1-step3` (the four-site jump model) and `m1-step4` (XYZ/CSV
import, D5 reconciliation, `*.dipolar.json` v2).** Each had two review rounds (21 and 23; 22 and
24). Every finding was fixed and mutation-checked, and the final-round fixes were not reviewed
again, under the cap. See [round21-m1-step3.md](validation/round21-m1-step3.md) and
[round22-m1-step4.md](validation/round22-m1-step4.md).

**M1 step 2 (the frame contract, C2(z) and C1, analytic derivatives) is done: tag `m1-step2`.**
Round 19 returned NOT READY with two class-(A) findings, both fixed. One of them also fixed a
sibling defect in step 1's finite-difference path. Round 20, the last round under the cap,
returned NOT READY on one class-(A) regression in the round-19 fix. It is fixed, mutation-checked
and documented, but not reviewed again, and the class-(B) limits are documented. See
[docs/validation/round19-m1-step2.md](validation/round19-m1-step2.md). **Next: decide the rest of
M1 (steps 3–5) from real usage, as agreed.**

**M1 step 1 (the D3 stack) is done: tag `m1-step1`, pushed.** Validation rounds 13–17 each
returned NOT READY, and every finding was fixed. Round 18, the second round under the two-round
cap, returned READY WITH MINOR CHANGES, and its one class-(B) limit is documented.

**Phase 1, milestone M0: all five steps are done.** The spikes (step 4) pass with evidence, and
the owner approved the re-baseline (step 5) on 2026-11-09. Validation round 10 (GPT-6.1-Sol) returned
NOT READY with one major and six minor findings, all fixed
([docs/validation/round10-m0-spikes.md](validation/round10-m0-spikes.md)). Round 11 confirmed
those fixes but returned NOT READY on a new major problem in the redirect-page cleanup (a symlinked
directory) and three minor ones, all fixed. **Round 12: READY WITH MINOR CHANGES**; both minor
changes are applied. M0 is the baseline at tag `m0-complete`.

Earlier stopping points: `m0-step2`, `m0-step3`, `m0-complete`, `m1-step1` to `m1-step5` (all pushed; `m1-step1-wip` is local).

## Done

- **Step 1, foundations.**
  - The uv workspace and the web/ package.
  - CI with three jobs (Python, Web, Legacy goldens).
  - ADRs 0001–0020.
  - The legacy goldens in `tools/legacy-harness/`.
- **Step 2, frozen fixtures.** The expected answers in `datasets/*/expected/` were produced by the
  independent reference in `tools/reference/`. Stopping point: tag `m0-step2`.
- **Step 3, the vertical slice.** `fit.preview` and `view.select` run end to end:
  - through one typed dispatcher, then policy, then the session (separate science and workspace
    revisions), then the journal;
  - over the Python adapter (`LocalClient`) and the HTTP adapter (`dipolar serve`);
  - from a minimal browser page (`web/`) and from the robot (`tools/robot/robot.py`, which uses
    only the standard library and runs under `python -I`).

  | Piece | Where |
  |---|---|
  | Forward model, biphenyl template, whitened SVD inner solve, validity flags | `packages/dipolar-core/src/dipolar_core/` |
  | Registry and dispatcher, policy matrix, session, journal, operations | `packages/dipolar-app/src/dipolar_app/` |
  | Registry contract snapshot (version 0.1.0) | `packages/dipolar-app/registry.snapshot.json` |
  | Numerical context (part of the science hash, D11) | `packages/dipolar-core/src/dipolar_core/context.py` |
  | Tests | `packages/*/tests/`, `tests/test_boundaries.py` (83 tests at step 3) |

### What the slice demonstrates

- **Science.** `fit.preview` at the frozen optimum reproduces the frozen fixture: Szz, Δ, χ² and
  all 14 predictions agree to about 10⁻¹³, far inside the frozen tolerances. The same values come
  back through Python, through HTTP and from the robot.
- **Contract.** The Python and HTTP adapters return identical envelopes for a 10-call sequence,
  including the error cases. The HTTP registry equals the committed snapshot.
- **Policy.** Identity and tier come only from the credential:
  - a `read` token cannot write the view;
  - a `propose` token gets `PROPOSAL_REQUIRED` for science changes;
  - `actor` or `tier` fields in a request change nothing.
- **Revisions.** A view change never moves the science revision or the science hash. A stale
  `expected_science_revision` returns `REVISION_CONFLICT` and nothing changes. Reopening a project
  clears the selection in the same transaction.
- **Journal.**
  - Each accepted command is one checksummed, fsynced JSON Lines record, written in full before
    the command is acknowledged.
  - **Fail-stop:** after any journal failure, every later command returns `JOURNAL_FAILED`
    until a restart replays the journal. Queries keep working.
  - Replay reproduces the science hash and the revisions, and a new process resumes from the
    journal.
  - A tampered or torn journal is refused.
- **Localhost controls.**
  - Loopback only, on an OS-assigned port.
  - The tokens are in a mode-0600 ready file; they are never printed and never put in URLs the
    server sees.
  - Host and Origin allow-lists: a foreign Host gets 421, which is the DNS-rebinding defence.
  - A bearer token on every API call, JSON content type only, a 1 MiB body limit, no side effects
    on GET, and a strict CSP.
- **Browser.** Checked by hand in Chromium (Playwright):
  - open the example, preview, select a row;
  - the robot's selection then appeared on the page;
  - the old preview was marked stale after the robot reopened the project;
  - a superseded preview that arrived late was discarded. This check is manual; automated browser
    tests arrive with M3.
- **Validation** (GPT-6.1-Sol), recorded in
  [docs/validation/round8-m0-slice.md](validation/round8-m0-slice.md):
  - **Round 8: NOT READY.** Seven findings, all fixed. Six of the fixes have automated regression
    tests; the frontend fix was checked by hand in a browser.
  - **Round 9: READY WITH MINOR CHANGES.** Both minor fixes are applied.

### Deliberate limits of the slice (each is planned work)

- **Three supporting operations.** `project.open_example`, `project.describe` and
  `render.describe_view` exist so the slice can run end to end. Each is in the registry like any
  other operation.
- **What `fit.preview` is.** It is the profile objective at a fixed φ: the order parameters are
  re-solved, and it is not a fit. The full D3 stack (grid, then refinement, intervals, full
  Jacobian) is M1.
- **Browser token hand-off.** Decided in step 4: a launch code exchanged for a tab token.
- **Deferred to M2, as the plan says:** idempotency keys, dry run, proposals, undo and the event
  stream. The page polls `render.describe_view` every 2 s until the event stream exists.
- **Damaged journals.** Settled in step 4: a torn tail is recovered, any other damage is refused,
  and a fail-stopped session needs a restart.
- **The TypeScript client.** Its types were hand-written in M0. Since M2 step 1b they are
  generated from the registry snapshot.

- **Step 4, the spikes.** Evidence, findings and decisions:
  [docs/spikes/m0-spikes.md](spikes/m0-spikes.md). Every spike is an executable module in
  `spikes/`, and CI runs them.
  1. **D3 numerical controls: pass.** M1 refines on the residual vector.
  2. **JSON serialization: pass after fixes.** Validation is strict (no type coercion), the HTTP
     JSON parser is strict, and the envelopes are published.
  3. **D10 localhost security: pass after fixes, on the installed wheel.**
     - The browser hand-off is decided: a single-use launch code, passed through a private
       redirect page (never on a command line), is exchanged for a tab token.
     - Instance lock, instance handshake, page bundled in the wheel.
     - A new `packaged` CI job.
  4. **Journal crash recovery: pass.** A torn tail is quarantined and discarded; damage is refused.
     200 SIGKILLs lost 0 acknowledged commands.
- **Step 5, re-baseline: a proposal.** [docs/rebaseline-after-m0.md](rebaseline-after-m0.md) gives
  the measured velocity, proposes the shape of M1–M3 in slice-sized steps, and sets no dates.

## Resume here: M3 step 4b (the robot tutorial, performance)

**Stopping point: tag `m3-step4a`.** Earlier stopping points: `m3-step3`, `interval-warm-starts`, `journal-compaction`, `m3-step2`, `m3-step1`, `m2-complete`,
`m2-exit-audit`, and one tag per step before them. To resume:

1. Check the baseline:

   ```sh
   uv sync --locked && uv run pytest -q -m "not slow"   # 823 passed
   uv run python tools/codegen/ts_contract.py --check   # the generated TypeScript is current
   (cd web && pnpm install --frozen-lockfile && pnpm run build && pnpm run parity && pnpm test)  # 59 web tests
   (cd web && pnpm exec playwright install chromium firefox webkit && pnpm run e2e)  # 57 browser tests
   ```

2. **Next, as the owner chose (2026-11-13):**
   - ~~journal compaction~~: done (tag `journal-compaction`);
   - ~~interval warm starts~~: done (tag `interval-warm-starts`);
   - ~~M3 step 3~~ (the proposal inbox, live preview, the landscape): done (tag `m3-step3`);
   - ~~M3 step 4a~~ (Playwright on three browsers, the step-1 store fixes, the latency targets
     on named hardware): done (tag `m3-step4a`);
   - then M3 step 4b: the robot tutorial from an XYZ file (create → import couplings → confirm
     mapping → bind torsion → preview → profile fit → select the worst coupling → render → export),
     over HTTP only, compared with the same tutorial through the page; virtualised large tables;
     a workload limit for `fit.landscape` on large projects (round 47 B); waking open change feeds
     at shutdown (round 49 B). Then the M3 exit check.
   - **Use pnpm 9** (as CI): `node_modules` linked by pnpm 10 makes `pnpm add` fail.
3. Work under the medium plan (below): at most two review rounds per step, a fresh session per
   step.
4. **When the registry changes,** regenerate the snapshot, then run
   `uv run python tools/codegen/ts_contract.py`, and commit both.
5. **When the registry changes and a command is proposable,** a proposal re-runs its handler up
   to the commit (`capture_plan`). Keep handlers free of side effects before `ctx.commit`.
6. **To see the page,** build it (`cd web && pnpm run build`), run
   `uv run dipolar serve --project-dir <dir> --static-dir web/dist`, then
   `uv run dipolar open --project-dir <dir>`.

The outline below was written before step 3.

### Earlier outline (before step 3)

1. Check the baseline:

   ```sh
   uv sync --locked && uv run pytest -q -m "not slow"   # 325 passed
   ```

2. **The owner decides the scope** of the rest of M1 from real usage, as agreed on 2026-11-10.
   - Step 3: the four-site jump model.
   - Step 4: CSV/XYZ import and JSON v1.
   - Step 5: gates (a)–(e), coverage, and the 8CB data. The 8CB gate applies only while that
     third-party dataset is present; it is removable on request (datasets/README.md).
3. **Step 3, if chosen.** The symmetric four-site jump (±φ, 180° ± φ, equal populations, one
   tensor shared in each conformer's acute-bisector frame), as plan §4 Phase 1 describes. What it
   builds on:
   - the frame contract and `RELABELLING_MAPS` (step 2) give each conformer's frame and the
     relabelling;
   - analytic derivatives carry over as sums over the conformers;
   - gate (e): explicit four-conformer averaging must equal the relabelling shortcut.
4. **Review:** at most two rounds, then push and tag `m1-step3`.

**What the review loop has taught:**
- Reviewers' synthetic counterexamples break general numerics that the frozen fixture never
  exercises: rounds 13–20.
- Every allowance or cutoff added for one counterexample needs a test with the *opposite*
  failure. Round 20 found a cutoff that hid a well-determined parameter.
- Mutation checks keep finding untested branches. Run them for every fix.

### Plan agreed with the owner on 2026-11-10 ("medium plan")

- **A cap of two review rounds per step.** If the second round still finds problems, fix them,
  document the remaining limits, and move on. For M1 step 1, rounds 17 and 18 count as the final
  pair.
- **Target for this week** (the usage window resets on Nov 13): push M1 step 1, then complete and
  push M1 step 2. Then decide on the rest of M1 from real usage.
- **Start each step in a fresh session** (`/clear`), resuming from this file and from memory.
  Long sessions re-read their whole context on every message.
- **Analytic derivatives.** Step 2 should give the biphenyl template analytic geometry derivatives.
  That removes the finite-difference issues behind rounds 13–17.
- **Small items** go in one batch: the Node 24 action bump, a licence file in the wheels, and a
  Windows CI job.

## M1, the scientific core: done

The owner approved the re-baseline on 2026-11-09.

| M1 step | Status | Owner hours (owner fills in) |
|---|---|---|
| 1. The D3 stack in dipolar-core | **done** (tag `m1-step1`); rounds 13–18, READY WITH MINOR CHANGES at round 18 | |
| 2. Frame contract, C2(z) and C1 | **done** (tag `m1-step2`); rounds 19–20, both fixed under the cap | |
| 3. Four-site jump model | **done** (tag `m1-step3`); rounds 21 and 23, both fixed under the cap | |
| 4. CSV/XYZ import, JSON v1 | **done** (tag `m1-step4`); rounds 22 and 24, both fixed under the cap | |
| 5. Gates (a)–(e), coverage, 8CB | **done** (tag `m1-step5`); round 25 fixed, READY at round 26 | |

### Step 1: the D3 stack

`dipolar_core.fit` is the stack, and `dipolar_core.problem` holds the problem definition.
`biphenyl.rigid_problem` builds the rigid model. The stack does the following:

- **Starts.** It scans the profile on a grid for one geometry parameter, or on seeded Sobol points
  for several.
- **Refinement.** Each start is refined by bounded TRF on the residual vector.
- **Basins.** Distinct basins are reported with their Δχ².
- **Uncertainty.**
  - The covariance comes from the full whitened Jacobian in joint coordinates (θ, t).
  - The joint rank is reported separately from the inner rank.
  - Directions the data do not determine are named, and they get no error bar.
- **Intervals.** Profile and slice intervals are separate, with their labels and raw Δχ²
  thresholds. They are "not supported" at a bound or at an irregular optimum.
- **Validity flags.** They are independent of each other. ν and the p-value are given only for a
  regular interior optimum.

**Validation round 13** returned NOT READY: six major findings and six minor ones on adversarial
problems. All are fixed ([docs/validation/round13-m1-step1.md](validation/round13-m1-step1.md)):
- the derivative stencil stays inside the bounds;
- crossings are searched outward and every interval is verified by sampling, so multi-component
  regions are refused (sampling can still miss a feature narrower than its spacing);
- profiles search every known basin (up to 16 starts);
- an interval is refused when a re-minimization fails, or when a failed run went lower;
- the null space is complete;
- a **full covariance Σ** is accepted;
- every scan point records its own diagnostics;
- starts are diverse, and unfinished runs are not called basins;
- convergence is checked by the predicted Gauss–Newton reduction;
- each bound is judged on its own scale;
- labels state one-parameter coverage;
- inputs are validated.

**Validation round 14** confirmed nine of the round-13 fixes. It returned NOT READY on three new
major problems that the round-13 fixes introduced, plus two minor issues; all are fixed:
- the stencil shrinks to fit narrow bounds;
- the convergence certificate uses the exact **Golub–Pereyra** VarPro Jacobian, differentiating
  only the model and never the data. TRF uses the same Jacobian;
- active bounds pass the KKT sign test;
- a floor for TRF's attainable resolution keeps large but finished misfits converged;
- a reduced SVD is used unless N < p_free;
- another basin refuses the interval only if it lies outside it.

**Validation round 15** returned NOT READY on three more major problems and one minor one, all
fixed:
- `full_jacobian` no longer differences the data;
- every interval is verified by even sampling before it is accepted;
- a failed run that goes lower makes the profile unresolved;
- a noisy near-zero gradient at a bound counts as binding.

**Validation round 16** returned NOT READY on three more major problems and one minor one. The
fragile mechanisms were replaced:
- geometry derivatives use Richardson extrapolation with an error estimate, and the joint rank
  counts only singular values above that error;
- convergence is certified by a bounded linear least-squares step over all coordinates. That step
  is then *tried* on the real χ², so noise can neither hide a real improvement nor block a real
  optimum;
- named null directions are the numerical basis, unfiltered.

**Validation round 17** returned NOT READY on two more major problems. Both are fixed locally and
await round 18:
- an unrealised prediction is certified only if the derivative's error estimate explains it;
- a three-level Richardson error estimate is used;
- the joint rank is floored at the inner rank;
- uncertain directions are reported apart from the data's null space.

**Tests:**
- `test_core_fit.py`: 16 tests.
- `test_core_fit_adversarial.py`: 57 tests, made from the round-13 counterexamples, plus GLS
  controls for correlated errors.

The `test_core_fit.py` tests:
- **Gate (b), noisy fixture.** All frozen regression tolerances are met with wide margins:
  - φ within 2.3·10⁻⁹ °;
  - standard errors within about 10⁻¹¹ relative;
  - interval endpoints within about 10⁻¹⁴.
- **Gate (a), noiseless recovery:** φ to 10⁻¹² °.
- **The fit itself:**
  - both grid basins are reported;
  - the full fit and the reduced fit agree;
  - a slice is narrower than its profile.
- **Irregular cases:** an optimum on the bound, and a geometry parameter the data cannot see.
- **Two geometry parameters at once:** φ and r_inter are recovered by Sobol multistart, and the
  search is reproducible.
- **Mutation checks:** ignoring the bound, ignoring the rank, skipping basin deduplication, and
  treating a profile as a slice each make a test fail.

`dipolar_app` still starts without importing SciPy's optimizer. A boundary test guards this,
because the import costs 1.5 s per process start.

The fitter is not yet an operation. Operations come in M2, as the beta UI needs them.

Check the baseline before resuming:

```sh
uv sync --locked && uv run pytest -q -m "not slow"     # 455 passed
uv run ruff check . && uv run ruff format --check . && uv run mypy
(cd web && pnpm install --frozen-lockfile && pnpm build)
LEGACY=path/to/NMRApllication tools/legacy-harness/run.sh
tools/package/build.sh && uv venv /tmp/pkg && uv pip install --python /tmp/pkg/bin/python dist/packages/*.whl \
  && DIPOLAR_BIN=/tmp/pkg/bin/dipolar uv run pytest spikes/test_spike_d10_localhost.py   # 32 passed
```

### Step 2: the frame contract, C2(z) and C1

The frame contract is frozen in the `dipolar_core.biphenyl` module docstring and summarized in
ADR-0012. It covers four things:
1. **Rotation:** geometry is built by active rotations, and frame changes are passive
   (`forward.frame_change`).
2. **Axes:** the frozen fixture's bisector frame, plus a ring-A frame.
3. **Torsion sign:** the IUPAC dihedral τ(C2–C1–C1′–C2′) is −φ.
4. **Constraint basis C(g):** one per order model.

What was built:
- **Order models** (`rigid_problem(..., order=, frame=)`):
  - `bisector-diagonal`, legacy alias "D4";
  - `c2z` (Szz, Δ, Sxy), legacy alias "D2";
  - `c1` (all five components).
- **The moving-bisector form.** In the ring-A frame, the bisector-diagonal model is
  Δ = Δ′cos δ and Sxy = ½Δ′sin δ, with δ = −φ = τ. It is regular for every δ, and its
  δ-derivative is part of the Jacobian.
- **Analytic geometry derivatives:**
  - `forward.design_rows_derivative` works for any geometry;
  - `biphenyl.rigid_design_derivative` includes the frame's own rotation and ∂C;
  - `Problem.design_derivative` makes the fitter use them in place of finite differences, in
    TRF, the certificate, the full Jacobian and every profile sub-model.

  On the fixture, the intervals are identical and the profiles run about 1.6× faster
  (Szz 3.4 s, down from 5.3 s).
- **The D2d endpoint is labelled, not enforced.** At φ = 90°, S4 symmetry forces a uniaxial
  tensor, but the individual couplings still constrain Δ′. A fit that lands there carries
  `FitResult.notes = (D2D_NOTE,)`.

The tests are in `packages/dipolar-core/tests/test_core_frames.py` (60 tests after round 20):
- the analytic derivatives against an independent sixth-order stencil, and every sub-model;
- contraction invariance under random rotations, and in both frames;
- the ring-A frame holds ring A still, and the δ sign;
- the IUPAC torsion sign, and the reflection equivalence;
- legacy D4 against the moving-bisector form away from the pole (with Δ_L = Δ′cos δ), and
  legacy D2 against c2z;
- the S4 invariance at the D2d endpoint, and the label;
- noiseless recovery with c2z and c1 in both frames;
- analytic against differenced fits and profiles.

Every new piece was mutation-checked; two survivors led to new sub-model tests.

**Round 19 fixes:**
- Derivative columns carry an allowance for the inner solution's own error, on both paths.
- A `domain=` option: `"acute"` (the default, which needs acute ring-B labels) or
  `"fixed-labels"` (0–180°).
- The ring-B relabelling maps are published.
- An acute fit at the 90° bound gets a note.

**Round 20 fix:** the trusted joint rank judges only what the geometry adds beyond the exact
order columns. A global cutoff had discarded a small but exact order direction.

**Limits:**
- An acute fit with wrong ring-B labels is not always flagged; the χ² and residuals show it.
- The round-20 fix has not been reviewed independently.
- c2z and c1 do not impose the template's D2 symmetry, so with identical rings nonzero
  off-diagonal components are phenomenological.
- Legacy D4 parity of the *reported tensor* (B55) still needs the thesis.
- The fixture's equivalence classes are D2 classes, so they are valid only for
  `bisector-diagonal`.

### Step 3: the symmetric four-site jump

`biphenyl.jump_problem` models fast exchange among +φ, −φ, 180° − φ and 180° + φ, with equal
populations. The conformers share one tensor, diagonal in each conformer's acute-bisector frame,
with t = (Szz, Δ).
- **The design** is the relabelling shortcut ½·[D(φ, pairs) + D(φ, relabelled pairs)], with its
  analytic derivative. `jump_design_explicit` averages the four conformers directly.
- **Gate (e):** explicit averaging equals the shortcut to 1e-9 Hz, and the engine equals the
  independent reference's explicit average.
- **The domain** φ ∈ [0°, 90°] is complete at fixed labels: the conformer set does not change
  under φ → −φ or 180° − φ. The model is invariant under the ring-B relabelling.
- **At 90°** the Δ column vanishes, so D2d is enforced by the model itself and Δ is reported as
  unidentified.
- **Estimands:** `FitResult.estimand` is "jump-model phi" or "rigid effective phi".
- **The 8CB reproduction** (the step-5 gate, run early): the engine reproduces the frozen jump
  fits at T_red 0.930 and 0.980 within the frozen tolerances. That covers the unweighted fit (φ,
  S, predictions, objective, RMS) and the weighted fit with its inadequacy flag. The test skips
  if the third-party data are removed.

Tests: `packages/dipolar-core/tests/test_core_jump.py` and `tests/test_engine_jump_reference.py`
(39 tests). They were mutation-checked, and every mutation was caught.

### Step 4: imports and the project file

- **Imported geometry** (`dipolar_core.torsion`, pure functions):
  - bonds from covalent radii;
  - the moving fragment across a torsion bond (ring bonds are refused);
  - φ as the signed IUPAC dihedral τ(a–i–j–b), set by a right-handed turn of the moving fragment
    about i → j, with an analytic derivative;
  - `imported_problem` (c1 or c2z in the input frame, which is fixed to the non-moving
    fragment).

  Cross-checked: imported coordinates at τ predict what the template predicts in its ring-A
  frame at φ = −τ.
- **Formats** (`dipolar_app.formats`):
  - strict XYZ and couplings-CSV parsers, with errors by line or row; unknown columns are
    reported, never used;
  - `project_from_xyz` (one spin per hydrogen);
  - **D5 reconciliation**: `reconcile` only proposes exact label matches. Unmatched labels need
    a mapping the user confirms. The diff lists added, removed, changed and unchanged pairs, and
    a reversed pair is the same observation. `apply_import` keeps the original labels in
    `source_labels`, and keeps each existing pair's stable coupling ID;
  - **`*.dipolar.json` v1**: a format tag and schema version, strict JSON-mode validation, exact
    round trips, and a migration chain. A newer file is refused.
- **Project schema v2** (round 22: v1 files and journals migrate; see
  docs/validation/round22-m1-step4.md): a geometry union (template or imported XYZ with a declared
  torsion); spins with atom indices; `source_labels` on couplings; and a model spec with kind
  (rigid or jump4), order, frame and domain. The order model's name is now `bisector-diagonal`,
  matching the core.
- **`dipolar_app.science`:** `check_project` states the consistency rules, and `problem_for`
  builds the D3 problem for the template (rigid or jump) and for imported coordinates.
- **The operations** (`project.describe`, `fit.preview`) still serve only the rigid
  bisector-diagonal template model. Other projects get `OUT_OF_DOMAIN` until M2 wires them in.

Tests: `test_core_torsion.py` (16) and `test_app_formats.py` (35), mutation-checked; 417 pass in
total.

### Step 5: the acceptance gates

- **The gate ledger** (`tests/test_m1_acceptance.py`): `GATE_TESTS` names the engine test of every
  gate in the frozen `spec.json` files, and a test checks that each named test exists. The 8CB
  gates are checked only while that dataset is present.
- **Gate (a)** on the engine against the spec's tolerances; **gate (d)** on the engine: reversed
  pairs and every symmetry class of `forward.json`, at 0°, 37° and 90°. Gates (b), (e) and the 8CB
  fits already had engine tests (steps 1 and 3).
- **Gate (c), coverage, on the engine:** `tools/coverage/engine_coverage.py` runs the frozen
  protocol and records every seed in `docs/validation/data/m1-gate-c-engine-coverage.json`.
  - Result: φ 70.1%, Szz 69.1%, Δ 68.4% (band 64.5–72.1%), no unsupported interval; the hit
    counts equal the reference implementation's.
  - The default suite recomputes the record's summary from its seeds (band, hits, no unsupported
    interval), checks its provenance (`FIT_VERSION` and input hashes) and reproduces seeds 0 and
    617. The slow test reruns all 1000 seeds and compares them
    with the record.
  - Cost: 9–26 CPU-s per seed, almost all in the Szz and Δ profile searches, so the full run takes
    about 40 min on 11 workers. Caching interval evaluations (an open item) would cut this; the
    fitter was left unchanged here.

Tests: 461 pass (`-m "not slow"`), plus the slow coverage rerun.

## M2, the application layer: done

| M2 step | Status | Owner hours (owner fills in) |
|---|---|---|
| 1. Science operations the beta UI needs | **done** (tag `m2-step1`); rounds 27–28, both fixed under the cap | |
| 1b. TypeScript generated from the registry snapshot | **done** (tag `m2-step1b`); rounds 29–30, both fixed under the cap | |
| 2. Idempotency, dry run, proposals, undo | **done** (tag `m2-step2`); rounds 31–32, both fixed under the cap | |
| 3. Jobs, D11 runs, the authenticated event stream | **done** (tag `m2-step3`); rounds 33–34, both fixed under the cap | |
| 4. Scene description, `describe_view`, the SVG renderer | **done** (tag `m2-step4`); rounds 35–36, both fixed under the cap | |

The plan's step 1 is "operations the beta UI needs, with TypeScript generated from the
snapshot". The owner chose to start with the science operations; the TypeScript generation is
split out as step 1b.

### Step 1: the science operations

- **`dipolar_app.science_ops`** holds the operations. Each science mutation is one
  `project.replaced` event. `validate_project` checks the new project first. Selected IDs that no
  longer exist are dropped in the same transaction, and journal replay reproduces the science hash.
- **`project.describe`** and **`fit.preview`** serve every fittable project:
  - the geometry is either the template or imported atoms with their torsion;
  - order parameters are named by the model (`order` is now a list of `{name, value}`, a breaking
    change under 0.x, hence 0.2.0);
  - the frame and the estimand follow the model;
  - `describe` reports `ready_to_fit` and, if not ready, why.
- **`fit.run`** (a query, capability `compute_job`) runs the D3 fit. It returns the estimates,
  validity, ν, p, adequacy, standard errors (regular optimum only), unidentified directions,
  basins and residuals. Profile intervals are optional, under **`dipolar_app.reporting`**: they
  are reported only for a regular optimum of an adequate fit (p ≥ 1e-3, the frozen 8CB policy).
  Otherwise each interval is "not supported", with the reason. This enforces round 21's
  finding 3.
- **`model.set`**: kind, order, frame, domain. The template's domains are [0, 90] and [0, 180]
  (rigid), or [0, 90] (jump). The example's D2 symmetry classes are not equivalences of C2(z) or
  C1, so switching the example to those models is refused until its couplings are re-imported
  without classes (round 22's class rule, working as intended).
- **`project.import_xyz`** and **`molecule.set_torsion`** (imported geometry);
  **`couplings.reconcile`** (a query: the proposed mapping and the diff) and
  **`couplings.import`** (under the confirmed mapping; stable IDs kept);
  **`project.load`** and **`project.export`** (`*.dipolar.json`).
- **New error code `PROJECT_NOT_READY`** (409): fitting a project that has no torsion or no
  couplings.
- **Web:** the slice page reads the named order values.

Tests: `test_app_science_ops.py` (32). They compare the operations with the core and the frozen
fixtures, including fit.run against the noisy fixture and its frozen intervals, and an imported
ethane fit recovering its truth. Mutation-checked: the adequacy rule, the policy gate in fit.run,
validation before the event, and selection pruning. Round 27's fixes added the derived
equivalences (`project.describe` → `equivalences`), bounded CSV fields, the 0.5 Å atom rule, a
readiness check that evaluates the design, per-operation request limits (`project.load` takes up
to 32 MiB as sent, measured in escaped bytes after round 28), shape checks on old documents, and an
always-cleared selection on `project.open_example`. 529 pass in total.

### Step 1b: TypeScript generated from the registry snapshot

- **`tools/codegen/ts_contract.py`** (standard library only) reads the committed snapshot and
  writes two files under `web/src/generated/`:
  - **`contract.ts`**: one type per schema definition and per operation input and output;
    `Operations`, which maps each name to its input and output types; the envelopes, with
    `SuccessEnvelope<N>` specialised per operation; `ErrorCode`; `CONTRACT_VERSION`; and
    `OPERATIONS`, each operation's metadata (kind, effect, capability, cost, request limit). The
    header carries the snapshot's sha256.
  - **`conformance.ts`**: every registry example must satisfy its operation's input type
    (`satisfies`, so unknown properties fail too). Nothing imports it; `tsc` checks it.
- **It fails closed.** A keyword it cannot represent exactly (`allOf`, `oneOf`, `not`,
  `patternProperties`, an object `const`, a non-local or dangling `$ref`, a variable-length
  `prefixItems`, …) is an error. So are one definition name with two schemas, a type name used
  twice, and a success envelope whose shape no longer matches the template. Bounds, lengths and
  patterns cannot be expressed in TypeScript; they become doc comments, and the server enforces
  them. Optional input properties (defaults) are `?:`. Under `exactOptionalPropertyTypes` they
  can be left out but not set to `undefined`. An argument-free input is exactly the empty object.
- **`web/src/api.ts`**: `callOperation<N>(name, args: OperationInput<N>, token)` returns
  `Envelope<N>`, so arguments and results always match the registry. The hand-written types are
  gone; the page uses the generated ones.
- **Round 29 hardening.**
  - Unions of closed objects are exclusive: each branch forbids the others' keys.
  - Typed `additionalProperties` beside named properties, other mixes of object branches, and
    structural siblings of `$ref`/`anyOf`/`const`/`enum` are all refused.
  - The success envelope must match its template exactly.
  - At the call boundary, `callOperation(name: N & SingleName<N>, args: A & Exact<…>)` takes one
    operation name and exactly its arguments. That holds even for a variable, at every depth.
  - `SuccessEnvelope<N>` distributes over unions.
  - Remaining limit: outside `callOperation`, TypeScript's structural typing still lets a
    variable carry undeclared keys.
- **Round 30 hardening.**
  - `Exact` checks each member of a union-typed argument on its own, so a valid member cannot
    mask an invalid one.
  - The check stops at targets that accept any JSON value.
  - The generator refuses recursive definitions (`JsonValue` excepted).
- **Checks.** `tests/test_ts_contract.py` (67 tests after round 30): the committed files are current, the chain
  from the live registry to TypeScript, every operation and definition is emitted, the renderer
  cases, and every fail-closed path. `web/src/contract.typetest.ts` uses `@ts-expect-error` to
  check that the generated types reject what the schema rejects: unknown operations, wrong unit
  literals, missing or unknown properties, explicit `undefined`, short tuples, values outside an
  enum, the wrong result type, unknown error codes. CI runs `ts_contract.py --check` in the
  Python job, and the web job's `tsc` checks both generated files. Mutation-checked: 9 mutations
  of the generated types (all caught by `tsc`) and 16 of the generator (all caught by the tests).
- **Not in scope:** `callOperation` still trusts the server's reply (a cast, not a runtime
  validation), and a network failure still rejects, as before.

### Step 2: idempotency keys, dry run, proposals and undo

The 04 D14, D17 and §8.1–§8.3 primitives. They are built for a non-human caller now; the chat UI
waits for Phase 3.

**Request options.** Every call is `{"args": {...}, "request_id"?, "dry_run"?}`
(`RequestEnvelope` in the snapshot; `LocalClient.call(..., request_id=, dry_run=)`;
`callOperation(..., options)` on the web).

**Idempotency keys** (`request_id`, §8.1):
- A retried command returns the stored outcome (`replayed: true`) and is never applied twice.
- Keys are scoped to the actor. Reusing a key for another command is refused
  (`IDEMPOTENCY_KEY_REUSED`).
- The table lives in the journal: each record carries `request: {id, outcome}`. Replay
  rebuilds the table, so deduplication survives a restart.
- A refused request is not recorded. A request that changed nothing is recorded, so its retry
  stays a no-op.

**Dry run** (`dry_run`, D17, §8.3):
- It plans the command under the lock and applies its events in memory only.
- It returns a `DryRunReport`: the revisions the state would reach, the science diff (spin and
  coupling IDs added, removed or changed), the new selection, and the proposals touched.
- It journals nothing, stores nothing and consumes no revision.
- Queries refuse it. A dry run with a `request_id` is refused.
- An agent may dry-run a science change; a viewer may not.

**Proposals** (`proposal.create`, `.list`, `.get`, `.accept`, `.reject`; §8.3):
- **Direct calls.** A `propose`-tier caller that calls a science command directly still gets
  `PROPOSAL_REQUIRED`, now with a hint naming `proposal.create`.
- **Creation.** A proposal is an ordered change set of proposable commands. Creating it
  validates every step on a scratch state, so a failing step is reported with its index and
  field.
- **What a proposal records:** its base science revision, each step's dependencies, a 24 h
  expiry and the proposer. Proposals have their own event domain and advance no revision.
- **Dependencies.** Step *i* expects the revision step *i − 1* produces, so the dependency-closed
  subsets are the prefixes.
- **Acceptance** is for a **human** principal only: the new `approve` capability requires
  `human`, so a script or agent token is refused whatever its tier. A whole proposal or a
  closed subset is re-planned and committed as **one** journal record (`step_lengths`), so it
  applies entirely or not at all.
- **Refusals.** A stale base is refused with a conflict report (`PROPOSAL_STALE`; no rebase). An
  expired or decided proposal is closed (`PROPOSAL_CLOSED`).
- **Bounds.** At most 8 pending proposals (`QUOTA_EXCEEDED`), with 20 steps each and bounded
  argument bytes. The 64 latest decided proposals are kept.

**Undo** (`history.undo`, `.redo`, `.log`; D14, §8.2):
- Undo is global and chronological. Each transaction that changes the science pushes one entry
  (the project before it), so an accepted proposal undoes as one change.
- Undo and redo are new journaled commands: revisions never decrease, and replay rebuilds the
  stacks.
- They need `expected_science_revision`, so an undo never reverts another actor's change that
  its caller has not seen (the §8.6 cross-actor check).
- Opening the first project is not undoable. The depth is limited to 100.
- Undo and redo clear the selection: the restored project may be another document, whose IDs
  name other objects (round 32).
- An undo or redo must be proposed alone, never inside a multi-step proposal (round 31).
- Coupling IDs are never reused within a session. Every replacement keeps the coupling-ID
  high-water mark (`keep_allocator`; rounds 31–32).

**Journal and contract:**
- Journal schema 2 (multi-step records and request outcomes); schema-1 records still replay.
- Contract 0.3.0 adds the request envelope, `replayed` and `dry_run` in the success envelope,
  the `proposable` flag, five error codes, and the `propose` and `approve` capabilities.
- The ready file has an `agent` token (`agent:local`, tier `propose`).

**Tests and checks:**
- `tests/test_app_agent_safety.py` (39 tests) covers the §8.6 checks this step touches:
  deduplication after a retry and a restart, concurrent retries, no tier escalation through
  arguments, stale and expired proposals, dependency closure, cross-actor undo, and replay
  equality.
- The serialization spike now prepares a state for every new operation. It validates their
  examples, results and dry-run envelopes against the published schemas, and produces every
  new error code.
- 12 mutations of the safety checks were each caught, and so was every review fix.

**Validation:** rounds 31 and 32 each returned NOT READY, with three class-(A) findings each. All
were fixed and mutation-checked. The round-32 fixes were not reviewed again, under the cap. See
[round31-m2-step2.md](validation/round31-m2-step2.md) (rounds 31 and 32 and the (B) limits:
request-table growth, step parsing under the lock, selection cleared on undo).

**Not in this step (planned):**
- compute proposals (`fit.run` from an agent) arrive with jobs in step 3;
- the view undo stack;
- rebasing stale proposals;
- marking runs from undone states stale (no stored runs before step 3).

### Step 3: jobs, D11 runs and the authenticated event stream

The 04 D18, §8.1 and §8.2 contracts and the D11 run contract. Long work is a resource, never a
blocking call.

**`fit.run` is a job.** It is a command (effect `compute`) that needs
`expected_science_revision`. It commits a `job.submitted` event and returns the job at once.

The job records:
- its input identity: the science revision and hash;
- the D11 canonical input hash, over the science, the options, `FIT_VERSION` and the
  numerical context.

The other operations:
- `job.status`, `job.list`, and `job.wait`, which waits at most 30 s and can be called again;
- `job.cancel`: a `propose`-tier caller may cancel only its own or its proposed jobs;
- `run.get`: the result, verified against its SHA-256;
- `run.list`.

Jobs live in their own `job` domain, which advances neither revision.

**The job runner** (`dipolar_app.jobs`) is a session listener: it queues each committed
submission with the committed project as its **input snapshot**.
- **`dipolar serve` uses one spawned process per job.** A cancel or a timeout terminates the
  process, and a crash fails only its job. Tests use worker threads.
- **Results are published durably.** The result is written as an immutable, content-addressed blob
  in `runs/` (fsynced), then `job.finished` references it by hash.
- **Exactly one terminal state.** A cancel and a completion both commit through the session; the
  first wins and the later outcome is dropped.
- **Stale runs.** A run that finishes after an edit is published against its own input and
  reported `stale`. It never changes the state.
- **Restart.** Replay never re-runs a job. Unfinished jobs are marked `interrupted` at the next
  start, and every run's blob is verified when the session opens.
- **Budgets (D17):** 2 unfinished jobs per caller and 8 in total, 2 workers, 600 s per job.

**Agents.** A `propose`-tier caller proposes `fit.run`, and a human's acceptance starts the job,
which records the proposer. In a proposal, compute steps come after every science change.

**Event stream.** `GET /api/v1/events?after=N` streams one JSON object per line (NDJSON), over an
authenticated fetch (D10). Any tier may listen. The line kinds:
- `hello`: the boot ID, the cursor and the revisions;
- `commit`: one per acknowledged transaction, with the operation, the actor, the revisions,
  the domains and the job changes;
- `job`: progress, such as `running`;
- `ping`: a heartbeat;
- `resync`: entries were dropped, or belong to an earlier boot.

The stream is a read: arguments and labels never appear in it. At most 8 streams may be open.

**Validation:** rounds 33 and 34 each returned NOT READY (eight and five class-(A) findings). All
were fixed and mutation-checked; the round-34 fixes were not reviewed again, under the cap. The
fixes cover:
- worker survival and bounded IPC;
- durable directories and blob repair;
- event-stream slots and consistent snapshots;
- the wait cap, attribution, and progress ordering.

See [round33-m2-step3.md](validation/round33-m2-step3.md).

**Contract:** 0.4.0, because `fit.run`'s input and output changed. Tests:
`tests/test_app_jobs.py` (17), with real worker processes and a cancel that kills one. 10
mutations of the job guarantees were each caught.

### Step 4: scene description, `describe_view` and the SVG renderer

The 04 D15, D16 and §8.4 contracts. An agent perceives exactly what the user sees, without a
browser.

**View state** (D15). The shared view now has:
- a perspective **camera** (position, target and up in Å; vertical field of view; near and far
  planes);
- a **viewport**, **layers** (labels, bonds, coupling lines) and **highlights**, next to the
  selection.

The new commands are `view.set_camera` (`null` fits the molecule automatically),
`view.highlight` and `view.set_layers`. They are absolute sets that advance only the workspace
revision, so a camera move never marks a fit stale (§8.6). Highlights follow the project as the
selection does: they are pruned within a document and cleared when another document replaces it.

**One scene description** (§8.4): `render.scene`, built by `dipolar_app.scene`. It contains:
- atoms with stable IDs (spin IDs, or `atm_NNNNNN`), coordinates at the displayed torsion, and
  projected screen positions with depth and visibility;
- bonds (imported geometry) and couplings with their lengths and the current run's residuals;
- the camera, the layers, the selection, the highlights and the far-to-near draw order.

The displayed torsion comes from the current run, else the imported dihedral, else a 45° default.
`phi_source` says which, so a picture never passes for a fit result.

**Perception** (D16):
- `render.describe_view` is the exact, compact channel. It reports the revisions, the run it
  reflects and whether that run is **stale**, the torsion and its source, the visible objects, the
  selection, the highlights, the five largest residuals and warnings.
- `render.view_svg` renders the scene on the server. Labels are escaped and every element carries
  its object ID.

**Projection parity** (§8.4):
- `web/src/scene/projection.ts` implements the same projection as the Python renderer: a
  three.js-style perspective camera, screen y down, and near, far and frustum clipping.
- Python generates the parity fixtures (`web/src/scene/parity-fixtures.json`), which cover
  auto-fitted landscape and portrait views, an oblique camera with clipping, and near and far
  clipping.
- `pnpm run parity` (in the CI web job and in pytest) checks the positions, depths, visibility and
  draw order against them. The largest difference is 6e-14 px.

**Contract:** 0.5.0. **Tests:** `tests/test_app_scene.py` (32), including a negative parity test
(a 1 px change fails). Six parity fixtures; every review fix was mutation-checked in Python and
TypeScript.

**Validation:** rounds 35 and 36 each returned NOT READY (five class-(A) findings each). All were
fixed and mutation-checked; the round-36 fixes were not reviewed again, under the cap. They cover:
- one snapshot per perception call;
- unreadable results reported, never shown;
- numerically safe cameras and geometry, with clipping before division;
- labels bounded in every output, and XML-safe SVG text;
- the fit's adequacy, regularity and admissibility in `describe_view`.

See [round35-m2-step4.md](validation/round35-m2-step4.md).

## M3, the browser beta: in progress

### Step 1: the Data and Fit workspaces

- **Change feed in the browser.** `api.ts` streams `GET /api/v1/events` with the tab's bearer
  token (an authenticated fetch, D10). `feed.ts` splits and parses the lines and maps each to the
  reads it invalidates. Every (re)connection reads everything; a watchdog reopens a silent stream,
  and reconnection backs off from 0.5 s to 10 s. The 2-second polling is gone.
- **Feed lines are typed.** `FeedItem` (hello, commit, job, ping, resync) is in the registry
  snapshot as `envelopes.event` and generated into `contract.ts`; contract 0.6.0. Tests validate
  every line the feed and the HTTP stream send.
- **The store** (`studio.ts`) reads only through registry operations. Reads are coalesced per
  resource, and a response older than the newest revision seen is dropped and read again (D11).
- **Data workspace:** open the example, load and export `*.dipolar.json`, import XYZ; readiness;
  geometry, with the torsion form for imported geometry; the model inspector; couplings and
  spins tables, whose rows select in the shared view (mouse or keyboard).
- **Fit workspace:** run a fit as a job (optionally with intervals), cancel it; jobs and runs with
  stale badges; per run, estimates ± standard error, profile intervals, quality, validity, other
  minima and numerical context; residuals with diverging bars on a fixed ±3σ scale; the
  observed-vs-calculated plot; a preview at a fixed torsion.
- **Status bar:** convergence, adequacy, identifiability (a server verdict, new in the fit
  summary) and admissibility are separate icon-and-label chips, with "Not a regular optimum" when
  it applies. A stale run shows only its stale badge.
- **Formatting** (`format.ts`, ui-design §5): uncertainty to 1–2 significant figures, the value
  rounded to the same place, the true minus sign, thin-space thousands, scientific notation for
  tiny uncertainties.
- **Tests:** `pnpm test` (Node's test runner) covers the formatter and the feed helpers, in CI.
  The page was driven by hand in Chromium against `dipolar serve`, including a second client's
  changes appearing live. Automated browser tests are M3 step 4.

### Step 2: Structure view, reconciliation, staleness by content

- **Staleness by content** (owner's decision after step 1): `project.content_hash` is the science
  hash without `next_coupling_id`; a job's is derived when its submission is applied (on replay
  too) and its run inherits it; `CurrentScience.is_stale` compares it, falling back to
  `science_hash` when it could not be derived. `science_hash`, `input_hash` and journal hashes
  are unchanged.
- **Structure view** (`ui/StructureWorkspace.tsx`, `scene/view.ts`): `render.scene` is a page
  resource; projection.ts draws it; misfit arcs; click and shift-click selection; layers; drag,
  arrow keys, + and −, 0 to fit; `CameraCommits` commits once per gesture with
  `expected_workspace_revision` (new, optional, on `view.set_camera`); moves stay within the
  server's camera limits.
- **Reconciliation** (`ui/ImportCouplings.tsx`, `reconcile.ts`): `PairOut.before`/`after` in the
  contract; the import sends the exact mapping and revision of the diff shown.
- **Formats:** strict ASCII decimals in CSV values and XYZ coordinates (and the atom count).
- **Tests:** 780 Python, 37 web (formatter, feed, camera, reconciliation). Driven by hand in
  Chromium, including a robot-set camera and import → undo making the run current again.

### Step 3: the proposal inbox, live preview, the landscape

- **Inbox** (`ui/InboxWorkspace.tsx`, `inbox.ts`): `proposals` is a page resource
  (`proposal.list`), re-read on `proposal` and science feed lines; the Proposals tab counts the
  waiting ones. Note, arguments and reasons are shown as text. Steps are chosen
  dependency-closed. A dry run of `proposal.accept` with exactly the chosen steps
  (`Studio.dryRun`, shown in place, never in the error banner) lists what would change, by label,
  plus the fit jobs the steps would start. Expiry is also judged by the page's clock.
- **Live preview** (`preview.ts` `LatestOnly`, `PreviewPane`): one request in flight, the newest
  position waiting; it starts at the fit's φ or the landscape's lowest sample, follows science
  changes, and shows the response p95 of the last 200 previews.
- **Landscape** (`fit.landscape`, contract 0.8.0; `LandscapePlot`): χ²(φ) at evenly spaced
  torsions on a log axis, with the previewed and fitted φ, inadmissible ticks, click to preview,
  and a table of every sample.
- **Tests:** 57 web (inbox and preview helpers added); `fit.landscape` in the Python tests and the
  cross-adapter contract test. Driven by hand in Chromium with an agent token proposing.

### Step 4a: the browser suite, the latency targets

- **Playwright** (`web/e2e/`, `playwright.config.ts`, `tsconfig.e2e.json`): one `dipolar serve`
  per test on a fresh directory (`e2e/harness.ts`: `startServer`, `server.call/ok`,
  `launchUrl`, the signed-in `app` fixture); Chromium, Firefox, WebKit; CI job "Browsers".
- **Specs:** basics (launch, fit, staleness by content), store (round 39 fixes 3 and 4, with a
  fake clock for the feed watchdog), inbox, concurrency, preview (ordering hazards, with
  `project.describe` held back by the test), latency.
- **Latency on named hardware** (`DIPOLAR_RECORD_LATENCY=1` → `docs/validation/data/m3-latency/`):
  preview p95 19–53 ms (values displayed, checked against the server); perception max 13–17 ms;
  looser bounds on CI.
- **Fixes:** `callOperation` returns an INTERNAL envelope for any malformed reply; the preview's
  start stands down once the user types, and its effects read the latest φ from a ref.

## The small batch (after M2)

Housekeeping chosen by the owner after the M2 exit audit. It went through pull request #1, so that
the new Windows job could be brought to green before merging.

- **CI off Node 20:** actions/checkout, setup-node and setup-python are at v7.
- **The licence in the wheels:** each package ships the repository `LICENSE` (`license-files`).
  `tools/package/build.sh` checks it in both wheels, and a boundary test keeps the copies equal to
  the repository file.
- **Caching interval evaluations:** profile intervals memoize the excess at each value.
  - **The measured gain is small:** about 4% fewer re-minimizations on the fixture (4 to 6 of
    about 120 evaluations repeat). The cost is each constrained re-fit, 0.06–0.1 s for Szz and Δ.
  - **A bigger cut would need warm starts:** each re-fit would start from its neighbour's solution.
    That changes the numerics, so it needs a `FIT_VERSION` bump and a rerun of the 40-minute gate (c).
    It was done afterwards (tag `interval-warm-starts`).
  - **Measuring this exposed run-to-run variation** in the last bits of interval endpoints
    (about 1e-17, apparently BLAS threading). The unmemoized code already showed it; it is far
    below every tolerance, and consistent with D11 (byte identity only in a pinned environment).
- **Blob collection:** when a session opens, it removes the result blobs that no run in the state
  references: pruned runs, dropped late results and leftover temporary files. This closes the M2
  step 3 (B) item on blob growth. **Journal compaction** (the request table and the journal itself)
  remains open: it needs snapshots that replay can verify.
- **A Windows CI job** (spike 3: the msvcrt lock, paths and line endings):
  - `fsync_dir` is a no-op on Windows, where a directory cannot be opened for fsync and NTFS
    journals its metadata;
  - text files keep LF line endings everywhere (`.gitattributes`), so the SHA-256 fixture checks
    hold;
  - POSIX-only tests are skipped on Windows: mode bits, symlinks, SIGKILL, `select` on pipes, and
    the launch directory's ownership checks (ADR-0010).

## Open items for the owner

- Log your hours per M1 step in the table above. The re-baseline needs them for a first date
  estimate.
- Approve plan v0.6 formally (the "go" started M0).
- Supply the thesis PDF. It is needed for B55/D4, the ρ formula and Phase 2 V3/V6.
- Get Di Pietro's permission to redistribute the 8CB couplings. This is needed only for packaged
  redistribution. The data are used for validation only and are removable at any time
  (datasets/README.md). The repository record's licence file says only "Creative Commons", with
  no version.

## Decisions recorded

- 2026-11-10: Marco Idrogo is **not** a co-author of the new implementation. `CITATION.cff`
  lists Gino Llerena as the only author of Dipolar Studio. Marco Idrogo stays credited as
  co-author of the original 1998 thesis and *Proyecto* application: in the README credits and in
  the cited 1998 reference in `CITATION.cff`.
- 2026-11-13: **Staleness is by content.** A run is current whenever the science equals its
  input, so an undo that restores the exact input makes it current again (ADR-0011 amendment,
  M3 step 2).

## Known minor issue

- None open (the Node 20 warning is fixed in the small batch).
