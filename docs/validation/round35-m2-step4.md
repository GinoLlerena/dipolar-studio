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

## Found by CI after round 36: draw order across platforms

The symmetric biphenyl protons sit at depths that are equal in exact arithmetic but differ in the
last bit. Linux and macOS libm round them differently, so the far-to-near order of a symmetric pair
flipped between platforms, and could flip between Python and a browser too. Depths are now
quantized to 1e-9 Å for ordering (`depth_key`, rounding half up identically in Python and
TypeScript), so true ties go by ID everywhere. The fixture test compares numbers within
`tolerance_px` and orders exactly. A TypeScript drawOrder without quantization fails parity.

## Documented limits (B)

- **The draw order uses depth quanta of 1e-9 Å.** Two depths exactly at a rounding boundary could
  still order differently across platforms. This is vanishingly rare, and it is a draw-order tie,
  never a position error.
- **The round-36 fixes were not reviewed again** (the two-round cap).
- **Highlight parity** is not checked: the browser does not render highlights before M3.
- **The 45° default torsion** for the template before any fit is labelled `phi_source: default`
  and warned about. It is not a result.
- **`render.scene` and `render.view_svg` grow with the project.** They are bounded by the project
  limits: at most 1000 atoms, with bond perception O(n²) on imported geometry.

## Round 36 (final under the cap): NOT READY (five A, one B), on commit 74b1751

The reviewer confirmed that the following held up:
- the round-35 snapshot fix and missing-result handling;
- snapshot consistency and replay;
- workspace/science separation;
- parity and the TypeScript contract.

They found five siblings. All are fixed and mutation-checked, and, under the two-round cap,
**not reviewed again**.

| # | Class | Finding | Resolution |
|---|---|---|---|
| 1 | A | **The fit summary dropped physical admissibility.** A fit with S outside the order-matrix domain read as adequate and regular, with no warning. | `fit.physically_admissible` is carried through the scene and `describe_view`, with a warning when it is false. Test: `test_describe_view_reports_physical_inadmissibility`. |
| 2 | A | **An atom inside the near plane broke every render.** The projection divided by a depth of ~5e-324 before clipping. | The projection clips by depth (near ≤ depth ≤ far) before any division, in Python and TypeScript alike. A new parity fixture, "near and far planes on the axis", places centred points inside the near plane and beyond the far plane. Test: `test_an_atom_inside_the_near_plane_never_breaks_rendering`. |
| 3 | A | **Imported coordinates bypassed the numerical bounds.** One H at 1e20 Å, or two atoms 1e200 Å apart, imported fine and then broke the auto-fitted camera. | Coordinates are bounded to ±1e4 Å (`Atom`, on import and on load), and template bond lengths to at most 10 Å (`validate_project`). An auto-fitted camera is checked like any other. Test: `test_geometry_is_bounded_on_import_and_load`. |
| 4 | A | **`project.describe` amplified labels.** Coupling labels repeated the full spin labels, so a 0.36 MB document gave an 8.6 MB response. | `Project.coupling_label` and `label_of` join display labels cut to 64 characters, wherever they are used: `project.describe`, fit results, reconciliation, the selection. A spin's own label is still shown whole, once. Test: `test_coupling_labels_never_repeat_a_long_spin_label`. |
| 5 | A | **Control characters made the SVG invalid.** A label with U+0000 escaped to malformed XML. | `xml_text` replaces the characters XML 1.0 forbids with U+FFFD before escaping. Test: `test_control_characters_never_break_the_svg`. |
| 6 | B | **`describe_view` copied the project name whole.** | It is cut to 64 characters. Test: `test_the_project_name_is_cut_in_the_view_summary`. |
