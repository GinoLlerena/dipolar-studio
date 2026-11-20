# Validation rounds 77–78: V1.3, the application (fixed-geometry fits)

Reviewer: GPT-6.2-Sol (Codex, reasoning effort high), independent of the author. The medium plan
allows at most two rounds. Class (A) findings block; class (B) findings are documented.

The step implements `docs/phase2/v1.0-design.md` D-1, D-3, D-5, D-6 and D-10 in the application,
with the §3 V1.3 gates and the four contract items round 76 handed on. The gate tests are in
`packages/dipolar-app/tests/test_app_v13_fixed.py`.

## What V1.3 builds

- **D-1, 0.1 directories.** `dipolar_app.directory.check_directory` reads the journal's first
  complete record and the snapshot headers, read-only, under the instance lock and before anything
  else touches the directory. A directory is opened only if each file is positively this version's
  (project schema 3, journal schema 3 or snapshot schema 2, and the current numerical context).
  Otherwise it is refused with the D-1 message. A lock file the call created is removed. Both
  `Studio.local` and `dipolar serve` (exit code 5) use it.
- **D-2, the context.** It gains `fixed_fit`, `rank_policy`, `symmetry_check`, `tensor_basis` and
  `feasibility_certificate`. SciPy stays off the start path: `fixed.py` now imports `chdtrc` lazily.
- **Schema v3.** `Atom.mass_number` (strict integer, absent for the default isotope),
  `Molecule.symmetry` (point group, axes, tolerance, medium), and the model kind `fixed` (order
  `point-group`, frame `symmetry`, no torsion domain). v2 → v3 only changes the version; v1 files
  migrate through v2. Only export files are migrated.
- **D-3, one validation function** (`science.validate_project`) runs on load, edit, dry run and
  proposal acceptance. It covers:
  - the model states;
  - symmetry only on imported geometry without a torsion;
  - every H atom is a spin under `fixed`;
  - the isotope table with one spelling per identity;
  - the declared symmetry validated by the core;
  - under `fixed`, each row's class is exactly its pair orbit, with one row per orbit.
- **Transitions.**
  - **Entering `fixed`** (`model.set`) needs a symmetry and no torsion, and canonicalizes rows
    losslessly. It is refused with `OBSERVATIONS_CONFLICT`, listing the rows, for two rows in one
    orbit, or for a class that is neither the orbit nor the row's own pair.
  - **Leaving `fixed`** keeps a class only if it is valid for the target model. Otherwise it is
    refused, listing the rows.
  - **Under `fixed`, a symmetry or isotope edit** that changes any row's orbit membership is
    refused. Clearing the symmetry is refused too.
- **New operations:** `molecule.set_symmetry`, `molecule.set_isotope` and `couplings.remove`. All
  are proposable and undoable, with dry runs and `expected_science_revision`.
- **D-5.** Under `fixed`, reconciliation keys rows by pair orbit, using `formats.OrbitOf`:
  - another member of an observed orbit updates that row and keeps its ID;
  - two rows in one orbit are refused;
  - omitted `multiplicity` or `equivalent_pairs` (an absent column or an empty cell, now distinct
    from "1") are filled in from the orbit;
  - explicit ones must match the orbit as sets, or the import is refused with the difference.
- **The D-5 key** is computed from spin IDs: the core's orbit members are mapped to spin IDs, each
  pair is sorted, and the key is the smallest pair (`science.pair_orbit`). It is vectorized over the
  core's permutations.
- **D-6.** The XYZ allowlist is the core's `ISOTOPES` (B and Si added; Cordero covalent radii added
  for bond perception). Mass numbers are strict integers; JSON's `13.0` becomes `13` under the
  registry's published integer rule, while `true` and `13.5` are refused.
- **D-10.** `compute_fixed` returns `FixedRunOut`:
  - rank, components and covariance in b;
  - null directions, adequacy and admissibility;
  - one row per orbit, with spin labels in one table so a row stays about 390 bytes;
  - symmetry, assumptions, coded warnings and provenance.

  Jobs and runs record the input's `model_kind`, and `run.get` decodes by it. `fit.run` checks
  `MAX_FIT_ROWS` first (`FIT_TOO_LARGE`), and so does the worker. `fit.preview` and `fit.landscape`
  refuse with `NO_TORSION`. `run.report` renders a φ-free page (`dipolar-fixed-report.1`) with the
  same CSV columns. The scene and `describe_view` handle fixed runs.
- **The core error codes.** The explicit table `science.CORE_ERROR_CODES` maps every
  `SymmetryError` code to an envelope code. The envelope also carries `details.core_code`.
- **The contract** moves to **0.11.0, breaking**, with a `changelog` in the snapshot and
  `docs/contract-changelog.md`. Responses for projects without a fixed model are unchanged: a gate
  test validates them against the frozen 0.10.0 snapshot.
- **The web client** compiles against the new types. It does not show a fixed run's components yet
  (V1.4) and points to the report; the model pane and the preview step aside for a fixed model.

**Budgets (D-11), at 20 000 C1 rows on the named i7-8750H:**

| Step | Time |
|---|---|
| Validation | 0.44 s |
| Rows, validation included | 0.70 s |
| Fit | 0.46 s |

The result is 7.3 MiB (about 390 bytes per row) with 61-character astral labels. The process
worker admits 20 000 rows (a slow test), and 20 001 rows are refused on the direct call, the dry
run, proposal creation and in the worker's `compute`.

## Freeze order and corrections

1. The gate tests and the 0.1 fixtures were committed first, in `047e773`. The fixtures were
   written by 0.1 code with `tools/fixtures/phase1_fixtures.py`. On that code, 40 of the 42 new
   tests failed, and the 0.10.0 contract test passed.
2. The implementation came after.
3. Four frozen tests had defects of their own, corrected as follows. No assertion was weakened.
   - **`test_v1_and_v2_export_files_load_to_one_v3_identity_by_both_paths`:** `science_hash` is now
     read from `project.describe`; `render.describe_view` has none.
   - **`test_leaving_fixed_keeps_valid_classes_and_refuses_the_others`:** the frozen test expected
     benzene's D6h orbits to stay valid classes of the draft's c1 model. Under the full order
     tensor, symmetry-related pairs have different design rows, so D-3's existing check always
     refuses them. Now a C1 project leaves `fixed` and keeps its single-pair classes. A D6h project
     is refused, listing all three rows, and leaves once they are removed.
   - **`big_c1_document`:** each row's single-pair class repeated 61-character astral labels, so
     the 20 000-row project exceeded the existing 32 MiB transport limit. The classes are now empty
     (a C1 orbit is the row's own pair); the long labels stay in the spin table, which is what the
     worker's outcome carries.
   - **The `test_app_m2_exit.py` sequence:** benzene's coordinates printed as `np.float64(…)`; they
     are now converted with `float()`.

**Existing tests changed by the step:**

| Test | Change |
|---|---|
| Schema-1 journal tests in `test_app_formats.py` | Replay of a 0.1 journal is retired by D-1/D-2: it is refused (numerical context), and its project still loads from an export file. |
| Version expectations | 2 becomes 3 (project and journal schemas). |
| Draft message | Now the D-3 wording. |
| Spike serialization tests | They prepare benzene for the new examples and produce each new error code. |

## Interpretations recorded for the reviewer

- **Draft symmetry edits.** D-3's "while rows exist, a symmetry or isotope edit … is refused if any
  row's orbit changes" is applied under `fixed` only. A draft's rows carry no orbit keys, so a check
  there would block the XYZ → CSV → symmetry workflow without protecting anything. Entering `fixed`
  checks the rows.
- **The orbit in a run row** is its key, not its full membership. With up to 24 members per orbit,
  full memberships could break the 16 MiB cap at 20 000 rows. `project.describe` lists the full
  class.
- **Options of a fixed job.** A fixed job records no options, so `intervals` has no effect, and the
  input hash uses `fixed-linear.1`.
- **Unverified rank.** The projected components carry their SE (1/s_i) and the retained covariance
  block, as D-10's "the retained block" requires. Their intervals are "not supported".
- **Phase 1 detection.** A journal with no complete record and no snapshot opens as new: nothing was
  acknowledged. Opening quarantines a torn first line as for any torn tail.
