# Validation rounds 79–80: V1.4, the browser and the robot

Reviewer: GPT-6.2-Sol (Codex, reasoning effort high), independent of the author. The medium plan
allows at most two rounds. Class (A) findings block; class (B) findings are documented.

The step implements `docs/phase2/v1.4-browser.md` (E-1 to E-7). Its gate tests were frozen first
(commit `c10cec4`): `packages/dipolar-app/tests/test_app_v14_browser.py`,
`web/e2e/fixed.spec.ts`, `web/e2e/fixed-tutorial.spec.ts`, the fixed-run part of
`web/tests/compare.test.ts` and `web/tests/orbits.test.ts`.

## What V1.4 builds

- **E-1, contract 0.12.0** (breaking for fixed-geometry projects only). `render.scene` and
  `render.describe_view` give `phi: null`, `phi_source: null` for a fixed-geometry project.
  `render.scene` gains `symmetry` for a fixed-geometry project whose declaration validates (absent
  otherwise, so every other scene keeps its 0.10.0 shape). The new query
  `molecule.suggest_symmetry`.
- **E-2, the Fit workspace without φ.** For a fixed-geometry run: no preview, landscape or interval
  option (the option has no effect for `fixed`, D-8; a sentence says why). The run's detail gives
  the rank, the adequacy (or the code that withholds it), the admissibility, the symmetry, the
  warnings and the assumptions, all as the result states them. The estimable-combinations panel
  (`#pane-estimable`) lists the estimated or projected components with their estimates, standard
  errors and both exact intervals (or the reason there are none), the components fixed by symmetry
  apart, and the null directions. The residual table is the result's rows, with each orbit's size.
- **E-3, the one-ring Structure view.** `dipolar_app.scene.symmetry_frame`: the origin and the rows
  of Q, the drawn axes' length, the largest displacement, the group action as `images`, and the
  automatic camera's direction (the symmetry axis with the least spread of the averaged geometry;
  ties to z′, x′, y′) and up. `auto_camera` takes a direction and an up vector in Python and
  TypeScript (two new parity cases). The browser (`web/src/scene/orbits.ts`) and the SVG renderer
  draw every member of each row's orbit with the row's ID (`data-copy` on the copies), and the
  axes x′, y′, z′.
- **E-4, the Data workspace.** The symmetry form (`#pane-symmetry`): point group, axes, tolerance,
  the medium (fixed), Declare and Clear, the current declaration with its largest displacement,
  and the server's suggestion with "Use this suggestion" (it fills the form; declaring validates).
  The model inspector offers `fixed` (one order, one frame, no φ domain). The atom table shows the
  mass numbers (`molecule.declarations`). The page reads `molecule.declarations` and
  `molecule.suggest_symmetry` as one resource after every science change.
- **E-5, `molecule.suggest_symmetry`.** The spins' least-squares plane; Cs with z′ its normal
  (largest component positive), x′ the input axis least aligned with it made orthogonal, y′ = z′ ×
  x′, when every spin lies within the tolerance and no group beyond C1 is declared. Nothing for the
  template, fewer than three spins, or collinear spins.
- **E-6, the tutorial.** `datasets/dichlorobenzene-synthetic/` (its own NumPy generator and
  reference fit; D2h, N = 3, d = 2, ν = 1), the robot's `--scenario fixed-tutorial`, and
  `web/e2e/fixed-tutorial.spec.ts`: the page and the robot each on their own server; the science
  hash, the export, the selection and the whole run compared with `fixedResultDifferences`
  (every number of a FixedRunOut under an explicit rule, frozen in the dataset's
  `expected/spec.json`; anything else fails).

## Frozen-test corrections (before review)

Each correction fixes a defect in a frozen test; none weakens what it checks.

1. `test_the_parity_fixtures_include_directed_automatic_cameras` compared the committed fixtures
   with exact float equality. The fixtures are generated with `math` functions whose last bits can
   differ between platforms; the existing fixture test uses the fixtures' own tolerance
   (`test_app_scene._same`). It now does too, and also checks the case names are the same.
2. `test_a_user_camera_is_kept_for_a_fixed_project` sent `camera.up` as a list; the input schema
   of `view.set_camera` takes `{"xyz": [...]}` (the registry's own example).
3. `test_the_contract_is_0_12_0_and_says_what_changed` imported `build_registry` from
   `dipolar_app.registry`; it lives in `dipolar_app.operations`.
4. `fixed-tutorial.spec.ts` looked for the residual/σ column by the text "/σ"; the header is
   "Residual / σ", so the lookup failed silently and the first row was taken for the worst. It now
   matches "Residual /" and throws if no column matches.
5. `fixed.spec.ts`, "the model inspector enters and leaves the fixed-geometry fit", acted as soon
   as the server had the change, before the page showed it: its next edit was reset by the
   arriving description (the draft follows the model), and Clear was sent at the revision the page
   still showed (`REVISION_CONFLICT`). Both are the page's designed behaviour. The test now waits,
   after each Apply, until the page shows the new revision and has nothing left to apply, as the
   biphenyl tutorial does. It then passed 12 of 12 repeated runs on the three browsers.

**Added after the freeze:** `fixed.spec.ts`, "a science change while the symmetry form is edited
keeps the edit" (as for the torsion and the model, M3 step 4b and beta step B4). It found that the
form followed the declaration only while the declarations' revision matched the project's, so an
unrelated science change reset the draft; the form now follows the latest declaration read.

**An earlier gate moved with the version:** `test_app_v13_fixed.py::
test_the_contract_moves_to_0_11_0_as_breaking` asserted the current version equals 0.11.0. It now
asserts at least 0.11.0; its checks of the 0.11.0 changelog entry and the V1.3 operations are
unchanged. `web/tests/feed.test.ts` lists the new resource `declarations` among those a science
change reads.

## Round 79

Commit `c2d337d`. **Verdict: NOT READY** (7 A, 4 B). The reviewer ran the Python suite (1156
passed, 3 skipped for local datasets), the web tests (72), both type checks, projection parity
(8 cases), the fixed browser specs on the three browsers, and targeted probes for each finding.
Corrections 1–4 were judged appropriate; correction 5 hid finding 2.

Gates frozen first in `4912588`; fixes in the next commit.

| # | Class | Finding | Fix |
|---|---|---|---|
| 1 | A | Clear sent the project's newer revision and removed a declaration the page had not shown; Run fit used the view's revision before the project description showed the change. | Declare and Clear act at the shown declaration's revision and are disabled while it is older than the project; Run fit acts at the project's revision and waits while the view and the project disagree. Gates: two delayed-response browser tests. |
| 2 | A | A late description after Apply erased an edit made meanwhile; correction 5 waited past that window. | The model inspector (and the symmetry form) stay disabled after a command until the page shows its revision. Gate: a delayed-description browser test. Correction 5 stays: it now describes the designed behaviour, and the new test covers the window. |
| 3 | A | The fixed comparator let identical unknown numbers (integers, and provenance numbers by prefix) through, and `in` hid a one-sided `__proto__` key. | Every number of a fixed result has its own rule (counts, ranks, the two numerical-context numbers); own keys with `Object.hasOwn`, in both comparators. Gates in `compare.test.ts`. |
| 4 | A | The page could show a wrong fit while both browser gates passed (they counted cells and compared API reads). | `e2e/rendered.ts`: the shown estimates, standard errors, interval endpoints and residual-table numbers must equal the result's within half a unit of the last shown digit, in the Fit spec and in the tutorial (against the robot's run). |
| 5 | A | The Cs suggestion said the in-plane block "is estimable". | It says Cs reduces the model to the in-plane block and the fit says which combinations the couplings determine; the user guide too. Gate: the reason's wording. |
| 6 | A | The robot took the first of duplicated atom names, mapped a label to the wrong proton and succeeded with a wrong fit. | One unique name per atom, as many names as atoms, checked before any change. Gates: three malformed comment lines, nothing changed. |
| 7 | A | The robot reported success with a stale run and an export of another science state. | `_consistent`: the run is current and of the project's science hash, the view shows it at that revision, the SVG and the export are of that state. Gate: each mismatch raises. |
| B1 | B | The collinearity rule differed from E-5's wording. | E-5 now states the rule used (every spin within the tolerance of the least-squares line); a boundary test pins it. |
| B2 | B | The browser and SVG drawing limits differ; at the limit, a selected row got no copies. | Selected and highlighted rows' copies are always drawn (gate in `orbits.test.ts`); both limits are documented in E-3. |
| B3 | B | The guide overstated face-on and the orbit display. | The guide and E-3 say face-on needs a declared axis normal to the plane, and give the drawing limit. |
| B4 | B | With the couplings layer hidden, the robot's tutorial failed after its fit. | The robot sets the layers it verifies. Gate: a hidden layer beforehand. |

**A correction to a round-79 gate (before review):** the delayed-description test held
`project.describe` as soon as the crumb showed rev 2, while the description of rev 2 could still be
in flight; Apply then (correctly) acted at the revision the page showed and was refused. The test
now waits until the symmetry form is current (it is only when the project description is) before
holding the reads.

**Found by the full browser runs after the fixes:**
- The symmetry form judged itself current against the project description alone. With the view
  already at a newer revision, Clear was enabled and refused (`REVISION_CONFLICT`). The rule is
  now one for every form: a command acts at the revision of the data it shows, and only while that
  data, the project description and the view show the same revision (the symmetry form, the model
  inspector and Run fit).
- The robot's HTTP timeout (30 s) equalled the server's bound on `job.wait` (30 s): under load a
  wait the server ended at its bound was cut off first ("timed out", the biphenyl tutorial). The
  robot's requests now time out at 60 s.
- The browser harness resent a query once after `ECONNRESET` on a reused kept-alive connection;
  the same idle-close race also shows as `UND_ERR_SOCKET` ("other side closed"), seen once in the
  biphenyl tutorial (the reviewer saw it too). It is now resent the same way, once, for queries
  only.

## Round 80

Commit `486f9c0`. **Verdict: NOT READY** (7 A, 2 B), the final round under the cap. The reviewer
confirmed every round-79 fix and its gate (each new gate failed against the old code), and that
refusal, undo and project replacement release the forms, the harness retry propagates repeated
failures, and the robot's timeout exceeds the `job.wait` bound. It ran the Python suite (1164
passed, 3 skipped), the web tests (75), parity (8), the type checks and the fixed browser specs
(27 on three browsers), with targeted probes.

Gates frozen first in `e4b13e6`; fixes in the next commit.

| # | Class | Finding | Fix |
|---|---|---|---|
| 1 | A | With `model.set` (or `molecule.declarations` after Declare) delayed, an edit made while the command was in flight was erased by its answer. | The model inspector and the whole symmetry form (every input, the suggestion button) are locked from the click until the page shows the outcome. Gates: both delays. |
| 2 | A | One failed `project.describe` left the page a revision behind and Run fit disabled until the next science change. | A failed read is tried again four times (0.5, 1, 2, 4 s). Gate: one aborted read. |
| 3 | A | Another client's project load between `model.set` and the reconciliation made the robot fit another geometry and succeed. | Every read after the robot's own last change must be at that revision (reconciliations, the spin lookup, the description), and the import names it. Gate: a workflow test that loads a scaled copy mid-run. |
| 4 | A | The robot counted any arc with the row's ID (a cleared selection passed), and the consistency gate passed with the guard disconnected. | The robot counts arcs drawn selected, checks the SVG is of the view it described (workspace revision), and the guard is exercised by workflow tests (a coupling removed between the fit and the export; the selection cleared before the SVG). |
| 5 | A | The suggestion said a C1 fit of the molecule would have an unverified rank; five protons within 0.001 Å of a plane fitted C1 with a verified rank. | The suggestion states the measured distance and what Cs constrains, and nothing about C1. The guide keeps the statement for exactly planar molecules. |
| 6 | A | A wrong rendered verdict (a required rank of 52) passed both browser gates. | The verdict's facts carry `data-fact` and `e2e/rendered.ts` checks each against the result (rank, N/d/ν, χ², p, RMS, adequacy, admissibility, symmetry), in the Fit spec and the tutorial. |
| 7 | A | A literal top-level key `"rank.required"` took the nested field's rule. | Path segments that are not plain names are quoted, in both comparators. Gate: four path-like keys. |
| B1 | B | 2000 kept rows × 24 members emitted 48 000 arcs. | Kept rows' copies have their own budget of 2000 (at most 4000 arcs); the guide and E-3 say so. Gate in `orbits.test.ts`. |
| B2 | B | A saved camera pointed away from the molecule failed the robot's tutorial. | The robot sets the automatic camera before it verifies the drawing. Gate: such a camera beforehand. |

**A correction to a round-80 gate (before review):** the symmetry-form test unrouted its hold
while held requests were still being continued (`Route is already handled`); a released hold lets
later requests through at once, so the unroute was dropped.

**Outcome:** both rounds under the cap were NOT READY. Every finding of both is fixed with a gate
frozen first; the owner decides whether to merge.
