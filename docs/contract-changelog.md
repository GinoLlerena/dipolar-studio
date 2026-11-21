# Tool contract changelog

The operation registry has its own semantic version (ADR-0020, plan D20), independent of the package
version. Under SemVer 0.x, a breaking change moves the minor version. The registry snapshot
(`packages/dipolar-app/registry.snapshot.json`, also served at `GET /api/v1/registry`) carries the
entries from 0.11.0 on in its `changelog` field; this page also lists the earlier versions.

## 0.12.0 (Phase 2 V1.4, 2026-11-20): breaking

The browser and the robot for fixed-geometry projects (`docs/phase2/v1.4-browser.md`, E-1).

- **Breaking:** `render.scene` and `render.describe_view` give `phi: null` and `phi_source: null`
  for a fixed-geometry project: there is no torsion to show. `render.scene`'s `phi` is nullable.
- **Added:** for a fixed-geometry project only, `render.scene` has `symmetry`: the point group, the
  origin (the centroid) and axes of the symmetry frame, the drawn axes' length, the largest
  displacement, the group action (`images`: per operation, each atom's image by index), and the
  automatic camera's direction and up. Its automatic camera looks along the symmetry axis with the
  least spread, so a ring is seen face-on. `render.view_svg` draws the axes and every member of
  each row's pair orbit.
- **Added:** the query `molecule.suggest_symmetry`: Cs, with the spins' plane as the mirror, when
  every spin lies within the tolerance of one plane and no group beyond C1 is declared. It is a
  suggestion, not validated: declaring it validates it.
- **Unchanged for projects without a fixed model:** `render.scene` and `render.describe_view` keep
  their 0.10.0 shapes (a gate test validates them, a torsion-less draft with a declaration
  included).

## 0.11.0 (Phase 2 V1.3, 2026-11-19): breaking

Fixed-geometry fits of imported molecules (`docs/phase2/v1.0-design.md`, D-3 to D-10).

- **Breaking:** `run.get` can return a `FixedRunOut` (its `result.model.kind` is `"fixed"`) for a
  fixed-geometry run. A client that assumes the search-era `FitRunOut` fails on such a run.
- **Breaking:** `project.describe` and `model.set` return a model without `phi_domain` for a
  fixed-geometry project (`kind` "fixed", `order` "point-group", `frame` "symmetry").
- **Added:** `molecule.set_symmetry`, `molecule.set_isotope` and `couplings.remove`, each with
  `expected_science_revision`, proposable, with a dry run, and undoable; and the query
  `molecule.declarations` (the declared symmetry and the non-default isotopes of any project).
- **Added:** `model.set` takes `kind: "fixed"`; its `phi_domain` is optional: absent for "fixed" and
  required otherwise (`INVALID_ARGUMENT` names it).
- **Added:** for a fixed-geometry project, `project.describe` has `symmetry` and
  `geometry.atoms[].mass_number` (when set). Every other project keeps the 0.10.0 shape, even with
  declarations; `molecule.declarations` reads them.
- **Added:** the error codes `OBSERVATIONS_CONFLICT`, `SYMMETRY_NOT_SATISFIED`,
  `POINT_GROUP_NOT_SUPPORTED`, `MEDIUM_NOT_SUPPORTED`, `ISOTOPE_NOT_SUPPORTED`, `NO_TORSION` and
  `FIT_TOO_LARGE`. A refusal from the core keeps its own code in `details.core_code`.
- `fit.preview` and `fit.landscape` refuse a fixed-geometry model (`NO_TORSION`). `run.report`
  renders a fixed-geometry run without a torsion (format `dipolar-fixed-report.1`), with the same CSV
  columns.
- **Unchanged for projects without a fixed model:** every response keeps its 0.10.0 shape. A gate
  test validates the biphenyl and imported-torsion responses against the 0.10.0 snapshot's schemas
  (`tests/data/contract-0.10.0.json`), which forbid extra fields.

Within this version, the web client and the Python API ship in the same wheels.

## Earlier versions

| Version | Step | Commit |
|---|---|---|
| 0.10.0 | Beta B2: `run.report` | `452a1ba` |
| 0.9.0 | M3 step 4b: the landscape's work limit | `9aae306` |
| 0.8.0 | M3 step 3: the proposal inbox, the live preview, `fit.landscape` | `a5e5bf0` |
| 0.7.0 | M3 step 2: couplings reconciliation diff, staleness by content | `a43ceb7` |
| 0.6.0 | M3 step 1: the generated client and the change feed | `fcbff94` |
| 0.5.0 | M2 step 4: the scene description, `describe_view`, SVG | `4fe6fb8` |
| 0.4.0 | M2 step 3: jobs, runs and the event stream | `52d8899` |
| 0.3.0 | M2 step 2: idempotency keys, dry runs, proposals, undo | `92ec004` |
| 0.2.0 | M2 step 1: the science operations | `8759d92` |
| 0.1.0 | M0 step 3: the vertical slice | `0c562d8` |
