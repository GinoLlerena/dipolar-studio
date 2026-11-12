# Validation rounds 35–36: M2 step 4 (scene description, describe_view, SVG, parity)

Reviewer: GPT-6.1-Sol (Codex, reasoning effort high), independent of the implementation.
Under the medium plan there are at most two rounds per step. Class (A) findings block; class (B)
findings are documented.

## Round 35: NOT READY (five A, one B), on commit 4fe6fb8

The reviewer's independent jump4 and imported-model probes matched the fitted φ and residuals.
The Node parity check and the TypeScript type check passed.

| # | Class | Finding | Resolution |
|---|---|---|---|
| 1 | A | **`describe_view` mixed two snapshots.** It read the state, then built the scene from a second read; a concurrent import produced one project's name with another's atoms. | The scene is built from the state the call read (`_scene(ctx, state)`). Test: `test_describe_view_reads_one_snapshot`. |
| 2 | A | **A missing run blob silently changed the picture.** φ fell back to 45° and the residuals vanished, while the run still read as current. | The run reports `available: false`, `describe_view` warns that its result cannot be read, and the run never drives φ, residuals or the fit summary. Test: `test_an_unreadable_run_result_is_reported_not_shown`. |
| 3 | A | **An accepted camera could break every render.** A field of view of 1e-322 underflowed to a zero projection scale, and every render query raised. | Cameras now have numerically safe bounds: the field of view between 1° and 170°, the near plane at least 1e-3 Å, coordinates within 1e6 Å, and all values finite. The projection also refuses a scale that is not finite and positive, and arithmetic errors map to `INVALID_ARGUMENT`. Test: `test_numerically_unsafe_cameras_are_refused`. |
| 4 | A | **Label expansion multiplied the output size.** Every coupling repeated both spin labels, so one 8 KiB label turned a 0.7 MB document into an 8.6 MB response, and a 1 MiB label would approach 1 GiB. | Couplings no longer carry labels; clients join them to the atoms by ID. Labels in perception outputs (scene atoms, selection, highlights, top residuals) are cut to 64 characters. Test: `test_long_labels_are_cut_in_perception_outputs`. |
| 5 | A | **The primary perception channel omitted the fit's own verdict.** An inadequate fit (p ≈ 1e-259) showed no warning. | `render.scene` and `render.describe_view` carry `fit`: adequate, p, regular, converged, at bound, and notes. `describe_view` warns when a fit is inadequate, irregular or on a bound. Test: `test_describe_view_reports_an_inadequate_fit`. |
| 6 | B | **The parity fixtures did not test the tie-break.** Equal-depth IDs already arrived in ID order, so removing the TypeScript tie-break still passed. | A new fixture, "equal depths, scrambled IDs", catches that mutation. Highlights are carried in the scene unchanged and involve no projection; the browser's highlight rendering arrives with M3, where its parity tests belong. |

Each fix was mutation-checked, except one of the two guards for finding 2. The `usable` flag is
redundant with the `result is not None` checks downstream, so removing it changes nothing; the
`available` flag and the warning are what the test checks.

## Documented limits (B)

- **Highlight parity** is not checked: the browser does not render highlights before M3.
- **The 45° default torsion** for the template before any fit is labelled `phi_source: default`
  and warned about. It is not a result.
- **`render.scene` and `render.view_svg` grow with the project.** They are bounded by the project
  limits: at most 1000 atoms, with bond perception O(n²) on imported geometry.

## Round 36

(Pending.)
