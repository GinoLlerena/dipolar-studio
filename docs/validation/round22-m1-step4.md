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
