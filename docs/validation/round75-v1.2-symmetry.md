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
