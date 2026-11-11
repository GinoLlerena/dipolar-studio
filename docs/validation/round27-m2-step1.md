# Validation rounds 27 and 28: M2 step 1 (the science operations)

- **Reviewer:** GPT-6.1-Sol (high effort), independent and read-only.
- **Reviewed:** 8759d92 against 8027c97 (`m1-complete`).
- **Verdict: NOT READY.** Five class-(A) findings, each reproduced by an external probe.
- **Confirmed without defects:**
  - the interval policy: it judges the same fit result, refuses irregular, ν = 0 and inadequate
    fits, and computes profiles only when asked and allowed;
  - "no unweighted projects": σ is mandatory and positive in the schema;
  - revision checks and journal replay for every new mutation;
  - confirmed mappings are applied as given, and coupling IDs are never reused;
  - the 0.2.0 snapshot, the web page and the robot agree.

## Findings and fixes

Each finding has a permanent test in `packages/dipolar-app/tests/test_app_science_ops.py` (one
in `test_app_http.py`). Each fix was mutation-checked; all six mutations were caught.

1. **Wrong equivalences in the estimand.** One rigid text served every frame and order model. For
   C1 in the ring-A frame it claimed that 180° − φ needs Δ → −Δ. The core keeps Δ there and
   negates Sxy and Syz; the stated map changed predictions by up to 372 Hz.
   - **Fix:** the equivalences are no longer written by hand. `template_equivalences` derives
     them from the core's own predictions: for each symmetry (−φ at fixed labels, 180° ∓ φ with
     ring B relabelled), it solves for the order map over all 45 pairs and keeps it only if it is
     an exact signed permutation at every probe torsion.
   - `project.describe` reports them in a new `equivalences` field. The estimand states the domain
     and, for [0, 90], the label precondition. The jump model and imported geometry have their own
     texts.
   - **Test:** every stated equivalence is checked on all 45 pairs, with random orders, at
     torsions the derivation never probed, for all six order-model × frame combinations.
2. **Malformed imports escaped as internal errors.** A label that appears only in an equivalent
   pair could map to a spin that does not exist (`KeyError`). A 5000-digit multiplicity and 1001
   equivalent pairs raised raw exceptions.
   - **Fix:** every mapping target is checked against the project's spins. Multiplicity must be
     ASCII digits within 1–1000, and a row may name at most 1000 equivalent pairs. Validation
     failures at the operation boundary become `INVALID_ARGUMENT`.
3. **An unfittable imported project was reported ready.** Two coincident atoms passed validation;
   preview and fit then failed with "coincident spins".
   - **Fix:** imported atoms closer than 0.5 Å are refused. `readiness` now evaluates the design at
     both ends and the middle of the domain. A design failure inside the domain (for example,
     spins meeting as the torsion turns) is `PROJECT_NOT_READY`, never an internal error.
4. **An exported project could be impossible to reload.** 100 hydrogens with all 4950 pairs
   exported to 2.5 MB, above the 1 MiB limit on `project.load`'s text and on the HTTP body.
   - **Fix:** project text may be up to 16 MiB. Each operation now declares its HTTP request
     limit (`max_request_bytes`, published in the snapshot). `project.load`'s limit covers that
     text after JSON escaping, and the server reads it only after authentication.
   - Every mutation refuses a project whose export would exceed the limit, so whatever is in the
     session can be exported and loaded back.
5. **`project.open_example` could keep another project's selection.** Selection pruning kept an
   ID that also exists in the example but names a different object.
   - **Fix:** opening the example always clears the selection.

## Class (B), documented

- `fit.run` is synchronous. Its compute is bounded only by the HTTP thread pool until M2 step 3
  adds jobs. It needs the `compute_job` capability, so a read-only credential cannot start it.
- Suggested coverage beyond the counterexamples: numerical checks of imported C2(z) and of more
  template combinations, and replay per operation. Replay is tested through a mixed journal
  (import, model.set, export).

## Round 28: NOT READY on two findings, both fixed under the cap

- **Reviewed:** 641d0d9 (the round-27 fixes) against 8759d92, and the whole step against 8027c97.
- **Confirmed:** findings 1, 2, 3 and 5 are resolved. Independent probes recovered the
  equivalence maps for all six combinations and for several custom geometries, with no false
  equivalence. The estimand texts agree with the core docstring. No path bypasses the size check
  in `replace_project`.

1. **(A) Characters are not bytes.** The size limit counted characters, but HTTP carries bytes. An
   example project whose `source` is 9 million emoji was accepted and exported, then refused with
   413 on reload. A client that escapes non-ASCII (Python's default) sends 12 bytes per emoji.
   - **Fix:** the limit is now on the document *as it travels*: the exported text as a JSON
     string with every non-ASCII character escaped (`transport_size`), the largest form any
     client sends. `MAX_PROJECT_TRANSPORT` is 32 MiB, and `project.load`'s HTTP limit is that
     plus 1 MiB for the envelope.
   - **Tests:** a limit between the character count and the escaped size refuses the project; an
     emoji-heavy project loads, exports and reloads over HTTP with an ASCII-escaped body.
2. **(A) Malformed v1 documents became internal errors** through the newly exposed
   `project.load`: `"project": null` (AttributeError) and `"couplings": null` (TypeError).
   - **Fix:** `migrate_project` checks the shapes it uses (an object, a coupling list, a model
     object) and raises `ValueError`, which `loads_project` reports as `FormatError`, so the
     caller sees `INVALID_ARGUMENT` on `text`. No blanket exception catch was added.

Both fixes were mutation-checked; both mutations were caught. Under the two-round cap they were
not reviewed again. 529 tests pass.

### Class (B) from round 28, documented

- **Broad `ValueError` catches** at the operation boundary turn some programming errors (for
  example, a design of the wrong shape) into `PROJECT_NOT_READY` or `INVALID_ARGUMENT` instead of
  `INTERNAL`. Acceptable for this step; typed exceptions would diagnose better.
- **Resource use before policy.** An authenticated request's JSON is parsed before the capability
  check, on the event loop: a 2 MB array cost about 88 MB of peak memory and 0.6 s. The Python
  adapter serializes arguments before the text-length check. Unauthenticated requests are refused
  before the body is read.
- **Error attribution.** Coincident XYZ coordinates report `offending_field="torsion"` rather
  than `xyz`.
