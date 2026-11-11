# Status

**M1 steps 3 and 4 are done: tags `m1-step3` (the four-site jump model) and `m1-step4` (XYZ/CSV
import, D5 reconciliation, `*.dipolar.json` v2).** Each had two review rounds (21 and 23; 22 and
24). Every finding was fixed and mutation-checked, and the final-round fixes were not reviewed
again, under the cap. See [round21-m1-step3.md](validation/round21-m1-step3.md) and
[round22-m1-step4.md](validation/round22-m1-step4.md). **Next: M1 step 5** (gates, coverage,
8CB), or the owner's choice.

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

Earlier stopping points: `m0-step2`, `m0-step3`, `m0-complete`, `m1-step1` (all pushed; `m1-step1-wip` is local).

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
- **The TypeScript client.** Its types are hand-written. M2 generates them from the registry.

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

## Resume here: M1 step 5 (gates, coverage, 8CB), or the owner's choice

Steps 3 and 4 are done (see the M1 table). The outline below was written before step 3.

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

## M1, the scientific core: in progress

The owner approved the re-baseline on 2026-11-09.

| M1 step | Status | Owner hours (owner fills in) |
|---|---|---|
| 1. The D3 stack in dipolar-core | **done** (tag `m1-step1`); rounds 13–18, READY WITH MINOR CHANGES at round 18 | |
| 2. Frame contract, C2(z) and C1 | **done** (tag `m1-step2`); rounds 19–20, both fixed under the cap | |
| 3. Four-site jump model | **done** (tag `m1-step3`); rounds 21 and 23, both fixed under the cap | |
| 4. CSV/XYZ import, JSON v1 | **done** (tag `m1-step4`); rounds 22 and 24, both fixed under the cap | |
| 5. Gates (a)–(e), coverage, 8CB | — | |

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

## Known minor issue

- GitHub Actions warns that `actions/checkout@v4` and the setup actions run on the deprecated
  Node 20. Bump them in a small CI commit.
