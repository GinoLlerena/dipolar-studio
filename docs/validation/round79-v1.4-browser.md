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

*(pending)*
