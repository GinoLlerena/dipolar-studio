# Validation rounds 51–52: M3 step 4b (the robot tutorial, performance)

Reviewer: GPT-6.1-Sol (Codex, reasoning effort high), independent of the implementation.
Under the medium plan there are at most two rounds per step. Class (A) findings block; class (B)
findings are documented.

M3 step 4 was done in two halves: **4a** (rounds 49–50) delivered the browser suite and the
latency targets; **4b** (this one) the robot tutorial, large projects, and the two class-(B)
items left for it (rounds 47 and 49).

## What the step delivers

- **The robot tutorial** (04 §7, "Robot user": *the final project and results equal those of the
  UI path*). `tools/robot/robot.py --scenario tutorial --xyz F --csv F`, standard library only,
  under `python -I`, over HTTP registry calls only:
  create the project from an XYZ file → reconcile the couplings file → confirm the mapping (the
  file's labels to the imported protons, by the atom names in the XYZ comment line) → check the
  diff is complete → import exactly that diff → bind the torsion (C2–C1–C1'–C2') → set the model
  (rigid, c2z, input frame, φ domain [−90°, 0°]) → check readiness → preview → fit with profile
  intervals → select the coupling with the largest |normalized residual| → check the rendered SVG
  shows it → export. Its inputs come from `datasets/biphenyl-synthetic/tutorial_xyz.py` (the
  generator's own geometry as a user's file: element symbols only; and the 14 measured values
  without the D2 symmetry classes, which an imported geometry under c2z or c1 rightly refuses).
  The preview is at `--phi`, by default the domain's midpoint (a φ outside the domain is refused
  before any change). Result: τ = −36.99° (φ = 37° in the template's convention, IUPAC τ = −φ),
  χ² 12.4 with ν 10, every interval supported, worst coupling at −1.94σ, about 7 s.
- **The same tutorial through the page** (`web/e2e/tutorial.spec.ts`): the XYZ and CSV through the
  Data tab's file buttons, the mapping chosen in its selects, the torsion and model in their
  fields, the fit with intervals, the worst row selected in the residual table, the Structure view
  showing it, and the export downloaded. Then the robot runs on its own server, and the test
  compares: the science hash; the exported project (deep equality); the selected coupling's label;
  θ, the order parameters, their standard errors and χ² to a relative 1e-9, ν exactly; every
  interval to 1e-9. On Chromium, Firefox and WebKit.
- **Large projects.**
  - **Tables render only the rows in view** above 400 rows (`limits.ts` `rowWindow`,
    `common.tsx` `useRowWindow` and `Spacer`): the Data tab's couplings, the Fit tab's residuals,
    the Structure tab's residual table. The scroll height still spans every row; the header stays
    in place.
  - **Drawing is bounded:** the Structure view draws at most 2 000 arcs and the obs/calc plot
    2 000 points (`mostRelevant`): everything selected or highlighted, then the largest |normalized
    residual|; a note says how many of how many are drawn, and the table lists them all.
  - **Values derived from a project are computed once per project** (`ByIdentity`, keyed by the
    immutable project's identity and, for the hashes, the numerical context): the science and
    content hashes and the problem `problem_for` builds. At 45 000 couplings they cost 0.6 s and
    0.85 s on every call before.
  - **Measured** (i7-8750H; the benchmark project, `tools/bench/large_project.py --protons 300`:
    44 850 couplings in a CSV of about 0.8 MB):

    | | before | after |
    |---|---|---|
    | Data tab shown | 14 s | 0.2–0.6 s |
    | Structure tab shown | > 15 s | 0.4 s |
    | Fit tab shown | 48 s | about 15 s (waiting for the server) |
    | `fit.landscape` | 181 samples, about 14 s | 22 samples, 0.9 s |

- **A workload limit for the landscape (round 47 B).** A landscape costs samples × observations;
  `LANDSCAPE_WORK` = 10⁶ (about 2 s on the named hardware whatever the project's size). By default
  it takes as many samples as the limit allows, at most 181 (the beta fixture keeps its 181); an
  explicit `points` above the limit is refused with QUOTA_EXCEEDED, naming the field and the
  maximum. Contract 0.9.0.
- **Shutdown no longer waits for open change feeds (round 49 B).** Each feed waited in a worker
  thread for up to one heartbeat (15 s), and uvicorn's shutdown waited for them. The server now
  closes the feeds when asked to exit (`Session.close_feeds`, from uvicorn's exit handler): every
  waiting feed returns at once and its stream ends; the page reconnects to the next server.

## Before review: found by the suite and by driving the page

- **The D2 classes of the template's couplings file are refused for an imported geometry**
  (c2z or c1: pairs across the rings are not equivalent). The tutorial's couplings file has one
  pair per measured value.
- **The identity cache of the science hash ignored the numerical context**, which the hash
  covers: `test_science_identity_covers_the_numerical_context` failed. The hashes' cache is keyed
  on the context too.
- At 45 000 couplings the page took 14 s to show the Data tab, 15 s or more for the Structure tab,
  48 s for the Fit tab; the landscape alone took about 14 s, at every tier. Fixed as above.

**Known limit (documented, not fixed):** at 45 000 couplings `project.describe` and
`fit.preview` each take 2–3 s and send about 13 MB, so the live preview's 100 ms target applies to
projects of the beta's size, not to the largest ones; the Fit tab waits about 15 s for its reads.

**Mutation checks** (each makes a test fail): no windowing (`WINDOW_FROM` unreachable); no
drawing cap; the cap not keeping the selection (`web/e2e/large.spec.ts`, 2 556 couplings); the
feeds not closed at exit (`test_shutdown_does_not_wait_for_open_event_streams`: the server outlives
12 s with three feeds open); the hash cache without the numerical context.

**Baseline (before review):** 66 browser tests (22 × 3), 832 Python (`-m "not slow"`), 61 web
unit tests, TypeScript (app and suite), mypy, Ruff, the generated contract and projection parity.

## Round 51: NOT READY (three A), on commit 9aae306

The reviewer's run: 832 Python, Ruff, mypy, the generated contract, 61 web unit tests and 22
Chromium tests passed. Scratch browser checks confirmed the preview's windowing, the plot's cap,
the selection kept, and the Structure table's windowing; the default landscape at 51 040
couplings took 19 samples (969 760 work units); with SIGINT the server exited in 0.23 s and
removed its ready file.

1. **(A) A windowed table replaced by a shorter one could hide its last rows.** Reproduced:
   2 556 couplings, the Data table scrolled to the bottom, then another client loads the project
   with its first 500: the table oscillated between no rows and an earlier subset, and scrolling
   to the bottom did not show coupling 500. The old scroll position was beyond the new rows, so
   the window was empty; with no row to measure the row height fell back to a guess (23 px against
   21 px), which moved the window again. **Fix:** a scroll position beyond the rows' end shows the
   last rows (`rowWindow` never returns an empty window for rows that exist); the last measured row
   height is kept when no row is rendered; the table is measured again when its row count changes.
   Tests: `web/tests/limits.test.ts` (positions beyond the end) and the reviewer's scenario in
   `web/e2e/large.spec.ts`, which fails against the step's first version.
2. **(A) The documented tutorial command failed before fitting.** Without `--phi` the robot
   previewed at 37°, outside the tutorial's domain [−90°, 0°], and stopped at OUT_OF_DOMAIN; the
   browser test passed `--phi -37` and so hid it. **Fix:** the tutorial previews by default at the
   domain's midpoint, and a `--phi` outside the domain is refused before any change. Tests:
   `test_robot_tutorial_as_documented` runs the docstring's command as written (and fails with the
   old default); `test_robot_tutorial_refuses_a_phi_outside_its_domain`.
3. **(A) The benchmark was described as the largest CSV the server accepts.** The reviewer
   imported 51 040 couplings (320 protons, 953 198 bytes) over HTTP. **Fix:** 44 850 is described
   as the benchmark's size only.

**Found by CI and by repeated runs under load, on the same commit** (not by the reviewer):

4. **Typed torsion indices were wiped by a science change.** CI's Firefox: the tutorial filled
   the four indices, then the couplings import's new project description arrived and the fields
   were reset to the (undeclared) torsion, so Set torsion stayed disabled. The fields were reset
   on every science change; a user typing while another client edits the project lost the typing
   the same way. **Fix:** they follow the declared torsion only when it changes. Test: another
   client imports the couplings while the indices are typed (fails with the old reset).
5. **A typed φ could become another number.** The preview test "a narrowed domain clamps the
   preview" failed under load, on WebKit and Chromium (five failures in about 590 runs); its trace shows the field
   holding `37.0120`: the automatic start wrote `37.0` into the focused, still empty field between
   the selection and the typing, and Enter previewed 37.012, snapped to 37.0. The round-49 guard
   began only with the first keystroke. **Fix:** neither the automatic start nor the clamp after a
   science change writes the field during an edit (from focus to Enter or leaving the field); they
   still move the slider and preview, and after a commit they write the field again. Test: the
   landscape held, the field focused, the start released (the preview starts, the field stays
   empty), then `60` typed is previewed as 60 (fails without the guard: `37.060`).

**After the fixes:** 834 Python (`-m "not slow"`), 62 web unit tests, 75 browser tests (25 × 3),
TypeScript, mypy, Ruff, the generated contract and projection parity; the preview, latency and
store specs repeated six times on WebKit and Chromium with the Python suite running alongside.

## Round 52: NOT READY (three A), on commit 103e92e

The reviewer's run: 834 Python, 62 web unit tests and the 75 browser tests passed, with Ruff,
mypy, the generated contract, TypeScript, the build and parity. Round 51's three findings were
confirmed resolved; fifteen scratch browser checks covered the slider and the "go to the fit"
button with the field focused, and the clamp followed by leaving the field.

1. **(A) Typed torsion indices survived a geometry replacement.** Reproduced on the three
   browsers: an XYZ without a torsion, `1 0 6 7` typed, then another XYZ with C2 and C6 swapped and
   no torsion: the indices stayed, Set torsion enabled, now naming a dihedral of about +143°
   instead of −37°. Both declared torsions are null, so the round-51 key never changed.
   **Fix:** the draft is reset when the declared torsion or the geometry (the atoms) changes, and
   kept across other science changes. Test: the reviewer's replacement.
2. **(A) After Enter, a new edit was unprotected.** Reproduced: 120 committed with Enter (the
   focus stays), select-all, a narrowed domain clamps to 90 before typing: the clamp replaced the
   selection with `90.0`, and typing `60` made `90.060`, previewed as 90. **Fix:** a key other
   than Enter (a selection, a deletion) or a pointer press in the field starts a new edit, which
   automatic updates do not write into. Test: the reviewer's sequence.
3. **(A) The tutorial test did not prove its interval claim:** two empty interval lists compared
   equal, and "within the interval" checked only the angle's distance from −37°. Reproduced with a
   backend that omits every interval. **Fix:** the test requires the model's four parameters
   (`phi_deg`, `Szz`, `Delta`, `Sxy`), each supported with finite bounds around its estimate, and
   −37° inside the torsion's interval ([−37.009°, −36.967°]).

The reviewer's scratch checks also showed (not listed as a finding) that **focusing and leaving
the field after a clamp undid the clamp**: with nothing typed, leaving the field committed the text
the round-51 guard had kept (120.0) and moved the preview back from 90° to 120°. **Fix:** a commit
with nothing typed shows the current φ and commits nothing. Test: the reviewer's sequence (a clamp
to 90, the domain widened again, then leaving the field keeps 90).

**Mutation checks** (each makes its test fail): the draft's key without the geometry; no new
edit on a key after Enter; an unchanged commit committing its text; a backend without intervals.

Under the cap, these fixes were not reviewed again. **After them:** 834 Python (`-m "not slow"`),
62 web unit tests, 84 browser tests (28 × 3), TypeScript, mypy, Ruff, the generated contract and
projection parity.
