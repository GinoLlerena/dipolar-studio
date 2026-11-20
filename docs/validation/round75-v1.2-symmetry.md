# Validation rounds 75–76: V1.2, symmetry and permutation classes

Reviewer: GPT-6.2-Sol (Codex, reasoning effort high), independent of the author. The medium plan
allows at most two rounds. Class (A) findings block; class (B) findings are documented.

The step is `packages/dipolar-core/src/dipolar_core/symmetry.py`, with its tests in
`tests/test_core_symmetry.py`. It is specified by `docs/phase2/v1.0-design.md` (D-4 to D-7, D-11 and
the §3 gates) and the proposal's V1.2. The budgets are recorded in
`docs/validation/data/v12-symmetry-benchmark.json` (Intel i7-8750H).

**Freeze order (the step).** The gate tests and their independent targets were committed first
(`b15844c`), then the implementation (`b8ae4ad`). The targets come from the raw input geometry and
the true tensor rotated into the input frame. All the frozen tests passed unchanged. One test was
added with the implementation, because a surviving mutant had removed the action check from
`validate`.

## Round 75 (on b8ae4ad): NOT READY, 3 A + 3 B

**The reviewer confirmed:**
- the six operation sets and the D-4 frames, consistent with `fixed.SUBSPACES`;
- the passive convention, the centroid and the polar factor;
- the isotope-preserving bijections and the composition convention;
- the equivariance of the averaging. Across six perturbed fixtures, the reduced rows within an
  orbit agree to about 4.4e-15 relative;
- the refusal order;
- single-atom declarations in all six groups;
- the benzene-d₁, ¹³C and 1,4-dichlorobenzene gates;
- that repeats are refused.

**Freeze order (round 75).**
1. The new gate tests were committed first, in `34d52a1`. 9 of them failed on the round-75 code.
2. The fixes came after them.
3. One more test was added with the fixes, because a mutant that dropped exact-zero snapping
   survived the frozen structural-zero test. The new test requires every operation entry to be
   either exactly zero or a coefficient of magnitude at least 0.5.

| # | Class | Finding | Fix |
|---|---|---|---|
| 1 | A | Duplicate detection in `fixed_rows` was quadratic: 20 000 C1 observations took 4.49 s. The benchmark timed only `pair_orbit`. | A set for duplicate detection, with the ordered list kept for output. **Measured:** 20 000 rows in 0.12 s. A gate test allows 1 s. |
| 2 | A | Two mutants passed: the largest orbit key instead of the smallest, and rows built from the raw centred geometry. The recovery helper chose representatives through the module, and the noisy fixture did not check the rows. | **Hard-coded keys and memberships** for 1,4-dichlorobenzene. **A noisy Cs fixture** checked against its analytic projection, computed in the test: the averaged geometry, the reported displacement, and the rows built from the projection. |
| 3 | A | Invalid endpoints were reinterpreted: (−1, 0) as (0, 2), and (0.9, 1) as (0, 1). An out-of-range index gave a bare `IndexError`. | `Validated.endpoints`: integer indices in [0, n) only (bool, float and str are refused), and distinct. Both `pair_orbit` and `fixed_rows` use it, with one code, `OBSERVATION_INVALID_INDEX`. |
| 4 | B | Matching at the cutoff: the decision can depend on the frame by rounding, and the message printed both distances as 0.0625. | The cutoff is documented as inclusive on the computed distance, and the message prints 15 significant digits. A test covers the cases just below, at and just above the cutoff. |
| 5 | B | The resource evidence was a warm 984-atom case. | The benchmark now uses exactly 1000 atoms: 24-atom orbits plus 2-atom orbits on the C6 axis, cycling through all 15 supported isotope identities. It reports the traced allocation (0.41 MB) and the process RSS (no increase) separately. **CPU:** 0.11 s, against a budget of 1 s. |
| 6 | B | Narrower mutants survived. | Direct tests: noncommuting table products (C6·C2′ against C2′·C6), structural zeros, axes 2e-9 outside the tolerance, explicit default masses, a ¹⁵N substitution that breaks D2h, and a reversed H–Cl pair. **Rerun:** the largest key, unnormalized masses, ¹⁵N ignored in matching, the second endpoint unchecked, no snapping, and an axes tolerance of 1e-8 all fail now. |

## Round 76 (on e258f8b): NOT READY, 2 A + 4 B — the final round

**The reviewer confirmed:**
- **A1.** The set keeps the input row order. 20 000 C1 rows took 0.114 s, and restoring the list
  lookup fails the timing gate.
- **A2.** The hard-coded fixture kills the largest-key mutant, and the Cs projection kills the
  raw-geometry-rows mutant.
- **A3.** Negative, out-of-range, repeated, bool, float and str endpoints are refused, and NumPy
  integers are accepted.
- **The B items:**
  - the inclusive cutoff and its boundary test;
  - an exact-limit rerun: 1000 atoms, 24 operations and 15 identities in 0.131 s, with a
    0.41 MiB traced peak and a process RSS increase of 0.26 MiB;
  - all nine round-75 frozen failures reproduced against the old code.
- **An independent probe** across all six groups, noisy, rotated and translated: the reduced rows
  within an orbit agree to about 7e-16 relative.

Round 76 was the last round allowed by the medium plan. Its findings were fixed and are documented
here without another review.

**Freeze order.**
1. The new gate tests were committed first, in `b3ced0e`. Ten of them failed on the round-76 code.
2. Before that commit, one target of my own was corrected: in 1,4-dichlorobenzene, the D2h mirror
   x → −x makes all four protons one site orbit.
3. The fixes came after. No test was changed or added with them.

| # | Class | Finding | Fix |
|---|---|---|---|
| 1 | A | NumPy durations passed as indices: `np.timedelta64(1, "ns")` became atom 1, because NumPy classifies `timedelta64` as `np.signedinteger`. | `_is_index` accepts a Python `int` (not a bool) or a signed or unsigned NumPy integer that is not a `timedelta64`. It is used for endpoints and for mass numbers. Both duration units are refused through both APIs with `OBSERVATION_INVALID_INDEX`. A malformed pair, of the wrong arity or not a pair at all, is refused with the same code instead of a `TypeError`. |
| 2 | A | `fixed_rows` allocated 20 001 and 100 001 rows; D-11 admits 20 000. | `MAX_FIT_ROWS = 20 000`, checked before any work: `FIT_TOO_LARGE`. 20 000 rows are accepted and 20 001 refused. **V1.3:** the worker uses the same admission check. |
| 3 | B | Four mutants survived: QR in place of the polar factor, the largest site representative, a zeroed centroid, and an exclusive cutoff for the second candidate. The refusal printed 0.0625 for both the cutoff and the next float. | Tests: the polar factor of R·(I + εS) must be R to 1e-15; the returned centroid on a translated fixture; hard-coded site representatives; a second candidate exactly on the cutoff (ambiguous); the exact distance in the message (`repr`). All four mutants fail now. |
| 4 | B | Returned arrays could change later fits: `FixedRows.subspace` aliased `fixed.SUBSPACES`. | The subspace is a copy. Every array in `Validated` and `FixedRows` is read-only, and a test writes to each. |
| 5 | B | **V1.3 contract:** orbit keys and the error mapping. Bad coordinates were reported as `AXES_INVALID`. | The core now refuses bad coordinates with `GEOMETRY_INVALID`. **V1.3 must** map each orbit member to spin IDs, sort each pair and take the minimum, to get the D-5 key. The core keys are the minima in atom-index order, and rows and multiplicities follow the observation order. V1.3 must also define the adapter's mapping from every core code (listed in `symmetry.py`) to its error envelope. |
| 6 | B | **V1.3 contract:** isotopes at import. The XYZ allowlist omits B and Si, and the core accepted `True` and `13.0` as mass numbers. | The core now requires strict integer mass numbers (`ISOTOPE_NOT_SUPPORTED` otherwise). **V1.3 must** use the core's `ISOTOPES` table at import, and keep integer mass numbers at the application boundary. |
