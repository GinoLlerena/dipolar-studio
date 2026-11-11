# Validation round 22: M1 step 4 (imports, D5 reconciliation, the project file)

- **Reviewer:** GPT-6.1-Sol (high effort), independent and read-only.
- **Reviewed:** commit 4c52a0d against 5c5f25e.
- **Verdict: NOT READY.** Nine class-(A) findings and several class-(B) contracts.
- **Confirmed without defects:** the torsion mathematics (sign, Rodrigues rotation, analytic
  derivative). The template cross-check also holds under a rotated and translated input frame, to
  9·10⁻¹² Hz, and the app's start path still avoids SciPy's optimizer.

## Findings and fixes

Each finding has a permanent test in `packages/dipolar-app/tests/test_app_formats.py`, and each
fix was mutation-checked: all 11 mutations were caught.

1. **Schema-v1 journals no longer replayed** (the order rename "diagonal-bisector" →
   "bisector-diagonal" also changes the hash).
   - **Fix:** PROJECT_SCHEMA_VERSION is now 2, and `project.migrate_project` upgrades v1
     payloads. On replay, a record written under an older schema is checked against the hash of
     its project payload *as stored* (`payload_hash`), then migrated. Integrity is still verified,
     and a tampered v1 record is refused.
   - **Fixture:** the reviewer's v1 journal, written by the pre-step-4 code, is kept as
     `tests/data/schema-v1.events.jsonl`. Project files at v1 migrate through `MIGRATIONS[1]`.
2. **Deleted coupling IDs were reused.**
   - **Fix:** `Project.next_coupling_id` is a persistent counter that only grows.
   - `validate_project` requires it to exceed every coupling number.
3. **Whitespace trimming changed labels.**
   - **Fix:** labels are kept verbatim and matched exactly. A label that is only whitespace is
     still an error.
4. **The diff omitted fields that the import changes.**
   - **Fix:** the diff compares every replaced field: value, σ, σ source, multiplicity,
     equivalent pairs and source labels.
   - An existing pair keeps its stored orientation, so a reversed row is unchanged.
5. **Observation classes were not enforced.**
   - **Fix:** `science.validate_project` checks the classes:
     - a class lists its own pair, and its multiplicity counts it;
     - no pair belongs to two couplings, so N counts independent observations;
     - every pair in a class must give the representative's design row under the selected model,
       at three torsions.
   - The fixture's D2 classes now fail under c2z and c1, and pass under bisector-diagonal.
6. **Loading accepted invalid science.**
   - **Fix:** `loads_project` runs `validate_project`: identity, references, σ, the
     model/geometry/frame/domain rules and the observation classes.
   - A draft that is not yet fittable still loads. `problem_for` adds the readiness checks:
     couplings present, a declared torsion, a supported domain.
7. **The operations guard missed frame and domain.**
   - **Fix:** `project.describe` and `fit.preview` require rigid, bisector-diagonal, the
     bisector frame and [0°, 90°]. Those are exactly what their outputs describe.
8. **The CSV parser repaired malformed quoting.**
   - **Fix:** `csv` strict mode. A malformed or unterminated quoted field is an error.
9. **Deep JSON raised RecursionError.**
   - **Fix:** a bounded bracket-depth scan (strings excluded) and a size limit run before
     decoding.

## Class (B): contracts, now explicit

- **BOM:** one leading BOM is removed; CRLF works.
- **Mappings:** a mapping passed to `reconcile` or `apply_import` is the *complete* confirmed
  mapping, not a supplement, and it must be one-to-one.
- **Memory:** `MAX_ATOMS` is 1000, because bond perception is quadratic (about 24 MB at the cap).
- **Fitting readiness** is separate from validity: `problem_for` refuses an unsupported template
  domain, zero couplings, or a missing torsion.

442 tests pass (`-m "not slow"`).

# Validation round 24 (final under the two-round cap)

- **Reviewed:** commit a78eb29.
- **Verdict: NOT READY.** Four class-(A) findings and two class-(B) contracts.
- **Confirmed:**
  - mixed v1/v2 journals, and v1 followed by view-only records;
  - the hashes of new records;
  - ring-A symmetric classes, and jump domains near 90°: all 498 accepted equivalences also held
    at 101 angles;
  - the JSON depth scan, with escapes, unicode and 1,000 randomized cases;
  - the torsion cross-check.

## Findings and fixes

All have permanent tests, and all 7 mutations were caught.

1. **Journal metadata could choose the hash rule.**
   - **Fix:** `session._record_schema` requires a supported integer `project_schema`. It must
     never decrease along the journal, and it must equal the `schema_version` of every project
     payload in the record.
   - A missing, forged, string or mismatched value is refused.
2. **Imported classes were not translated through the mapping.**
   - **Fix:** `reconcile` resolves class members too. Their labels join the mapping, and entries
     that name no two known labels are reported as `unresolved_pairs`.
   - `apply_import` stores the class in project labels, and keeps the original text in
     `Coupling.source_equivalent_pairs`.
3. **An invalid declared torsion loaded.**
   - **Fix:** `validate_project` builds the declared torsion whenever one is present, so repeated
     atoms, ring bonds and non-bonds are refused on load. A missing torsion is still a valid
     draft.
4. **Project files bypassed the atom cap, and the class check repeated quadratic work.**
   - **Fix:** the caps are in the schema (`MAX_ATOMS`, `MAX_COUPLINGS`, `MAX_CLASS_SIZE`), so every
     path enforces them before any geometry work.
   - The class check builds the geometry once per validation (`_design_function`).

## Class (B): contracts

- **"Unchanged" provenance:** the first population of provenance (`source_labels` or
  `source_equivalent_pairs` going from None to the imported text) is not reported as a change,
  although it changes the science hash. Any later change of provenance is reported.
- **Pair labels:** "A-B" is resolved only when exactly one split names two known labels. An
  ambiguous label is an error, never a guess (`project.split_pair_label`).

## Closing

Under the owner's cap, the round-24 fixes were applied and mutation-checked, and the contracts
are documented. No further round was run, so **these fixes have not been reviewed
independently**. 455 tests pass.
