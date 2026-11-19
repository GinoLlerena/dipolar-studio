# Validation rounds 71–72: V1.1, the fixed-geometry linear fit

Reviewer: GPT-6.2-Sol (Codex, reasoning effort high), independent of the author. The medium plan
allows at most two rounds. Class (A) findings block; class (B) findings are documented.

The step is `packages/dipolar-core/src/dipolar_core/fixed.py`, with its tests in
`tests/test_core_fixed.py`, specified by `docs/phase2/v1.0-design.md` (D-7 to D-9 and the §3
gates). The budgets are recorded in `docs/validation/data/v11-fixed-benchmark.json`
(Intel i7-8750H).

## Round 71 (on 04d33ed): NOT READY, 6 A + 3 B

The reviewer confirmed:
- the basis, R(Q), the built-in subspaces, the reduced design and the rank thresholds;
- the ordinary-scale covariance and adequacy;
- coverage of 67.5 / 71.7 / 68.6 / 68.3 / 66.4 % on the five components, all in the band;
- the dual bound's soundness under its preconditions;
- that `fit.py` changed only by the k = 0 refusal.

**Freeze order.** As the reviewer asked, the new tests and their independently computed targets
were committed first (`f75b022`, with 10 tests failing on the old code), and the fixes after
them (`9276d5d`). The fix commit also changed four tests:
- **The test that patches the search** was moved to an unphysical family, because the new early
  return made its old family trivially feasible. Its target, "undetermined", is unchanged.
- **Three tests were strengthened** after mutation testing; their targets are still independent
  of `fixed.py`:
  - the tiny σ moved to 1e-160, where unscaled squares lose precision;
  - the asymmetric-covariance test now requires bit-identical fits at the largest allowed
    asymmetry;
  - the retained SEs are checked against an independent SVD.

| # | Class | Finding | Fix |
|---|---|---|---|
| 1 | A | An exactly singular covariance (`full((2,2), 0.5)`) passed Cholesky by roundoff and gave a "verified" fit. A near-symmetric matrix was factored from one triangle. | The covariance's symmetric part is used, after a symmetry check relative to its largest entry. Positive definiteness needs λ_min ≥ max(1e-12, 64·N·ε)·λ_max. Tests: the singular matrix is refused, and either asymmetric triangle gives bit-identical fits. |
| 2 | A | The budgets: whitening at N = 2000 peaked at 160 MB (an explicit inverse factor), and certificates took 0.25–0.63 s. | **Whitening:** triangular solves against the design and data, with no inverse (peak 91.6 MB beyond the caller's matrix, under the 96 MB budget; tested). **Certificates:** an early return when the fitted point is physical; each search start ends at the first verified certificate, with a bounded number of iterations. **Measured:** medians 0.04 ms, 5.9 ms and 11.8 ms, against 0.1 s (benchmark file). |
| 3 | A | A nearly orthonormal subspace (`diag(1.000004, …)`) passed `allclose` and broke the minimum-norm property. Two SVD calls for N < d could pair vectors differently. | An absolute tolerance (1e-12) on CᵀC − I, then exact re-orthonormalization by QR, keeping the span. One SVD (`full_matrices=N < d`) gives U, s and the complete right basis. Tests: that matrix is refused; within 1e-13 the estimate is exactly (0.15, 0.15, 0, 0, 0); the null directions annihilate the design. |
| 4 | A | Finite scaling erased uncertainty: σ = 1e-155 gave SE = 0, because s² overflowed. A common huge scale could overflow before whitening. | The covariance is built from singular reciprocals, and SEs from scaled norms. Whitening comes before the change of basis. Every intermediate and output is checked for representability; an unrepresentable problem is refused. Tests: σ = 1e-160 gives SE = 1e-160; a common 1e300 scale cancels; an overflowing problem is refused. |
| 5 | A | A strict "feasible" was false at roundoff: an xy block (−½, ½, off-diagonal 1e-9) with only Syz free gave λ_min = −0.4999999999999999. | A strict "feasible" needs λ_min ≥ −½ + 1e-14, a bound on the 3 × 3 eigenvalue error; otherwise it is "feasible-within-tolerance". Tests: that case, and a witness that must move away from the fitted point (λ_min = −0.4). |
| 6 | A | Six of the reviewer's mutants passed: zeroed null vectors, doubled SEs, a wrong 95 % quantile, a binary p-value, no dual margin, and covariance conversion before the cap. | New tests for each: null-space annihilation and orthonormality; minimum norm against an independent pseudo-inverse; retained SEs against an independent SVD; both interval widths; the χ² tail for ν = 2 (exp(−χ²/2)); matched functionals across frames with tied singular values; the dual margin on a near-separator (`certifies_infeasible`, now public); the cap checked with an object that refuses conversion. All 14 mutants of the revised code are caught. |
| 7 | B | The dual construction is incomplete: with tied lowest eigenvectors, equal weights can fail where an exact dual exists. | Documented. The reviewer's example is a test that allows "infeasible" or "undetermined", never "feasible". |
| 8 | B | Carry the rank caveat: admissibility after truncation concerns the family preserving the retained projection; the "rank zero" text appeared at nonzero rank. | `Admissibility.family` labels what was tested. The certificate text names the case ("S = 0 belongs to the family"). |
| 9 | B | The array contract: `y` was not checked to be 1-D; the result's subspace aliased the shared default; tiny nonzero components of a custom subspace counted as "fixed by symmetry". | `y` must be a vector. The subspace is a fresh orthonormal copy. The threshold for custom subspaces is documented in `_component`. |

## Round 72 (on 7dd67f7): NOT READY, 7 A + 3 B — the final round

The reviewer confirmed every round-71 fix at ordinary scale:
- the singular matrix is refused, and near-singular matrices straddle the cutoff at N = 2 and
  N = 128;
- correlated fits for every 1 ≤ N < 5 match an independent whitened pseudo-inverse;
- the subspace check, the QR re-orthonormalization and the single-SVD pairing;
- the family label and the rank-zero text;
- all six round-71 mutants are caught; `fit.py` differs only by the k = 0 refusal.

Round 72 was the last round allowed by the medium plan. Its findings were fixed and are
documented here without another review.

**Freeze order.** The new tests and their independent targets were committed first (`55e18d3`;
8 failed on the old code). One frozen target was self-contradictory and was corrected in its own
commit (`c7291d7`), still before any fix: a design scaled by 1e300 has a covariance of order
1e-600, which no float64 can hold, so the test now requires finite estimates and a refusal of the
uncertainties, not a covariance. The fixes came after both. The fix commit adds three tests (the
two normalization mutants and the in-place factorization) and changes no frozen test.

| # | Class | Finding | Fix |
|---|---|---|---|
| 1 | A | Covariance validation depended on scale: `1e308·I` overflowed in `C + Cᵀ`, and a subnormal 2 × 2 matrix with an eigenvalue ratio of 8.33e-13 passed the 1e-12 cutoff by underflow. | Σ is normalized by an exact power of 4 (4^k, with k from its largest entry) into its symmetric part, in row blocks, before any spectral test; σ is checked against the original diagonal; the factor is rescaled by 2^k. Tests: the same 2 × 2 matrices at scales 1, 1e-300 and 1e300 give the same decisions; `1e308·I` fits like the unscaled problem; a matrix at 4^511 (finite entries, overflowing ‖Σ‖∞) fits bit-for-bit like the unscaled one. |
| 2 | A | The covariance path exceeded the memory gate: a dense eigensolve, 91.6 MB traced, process peak RSS +147 MB at N = 2000, and 122 MB for a float32 input. | Positive definiteness is a Cholesky factorization of Σ_n − τI, τ = max(1e-12, 64·N·ε)·‖Σ_n‖∞, which proves λ_min ≥ τ up to backward error far below τ. Both factorizations run in place in one N × N workspace (row blocks of 64). **Measured** (benchmark file): 31.6 MB traced; process peak RSS +62 MB beyond the caller's resident matrix, against 96 MB. Test: a float32 covariance stays within the budget. |
| 3 | A | The boundary certificate (Szz = −½, four free directions) took 0.17–0.30 s. | The dual is tried at the fitted point first; the search has one evaluation cap across all starts (1500). **Measured:** boundary median 72 ms; tied eigenvectors 0.2 ms; the other cases as before. A gate test allows 0.2 s (2× margin) on any machine. |
| 4 | A | Representability gaps: σ = 1e155 returned infinite covariance diagonals, σ = 1e-165 zero ones, a rank-zero fit could return a NaN ratio, and χ² could raise `OverflowError` or underflow to zero. | The SVD is of a power-of-two normalization of the whitened design (singular values s_n · g); uncertainties are built from reciprocals and scaled by g last; the singular values, ratios, SEs, covariance diagonals and χ² are all checked, and an unrepresentable result is refused. Tests: both σ cases are refused; a 1e300 design gives finite estimates; a design whose ‖wa‖₂ overflows still reports its retained estimates when no covariance is due. |
| 5 | A | Whitened cancellation made an exact fit inadequate: two identical rows, y = 0.25, σ = 1e-20, gave χ² ≈ 3.4e7 and p = 0. | A bound δ = ‖(8 + N)·ε·(|wy| + |wa|·|t|)‖ on the residual's rounding error. When the decision at α = 1e-3 differs between χ ± δ, adequacy is withheld with `ADEQUACY_NUMERICAL`. Test: that case is withheld, not inadequate. |
| 6 | A | `certifies_infeasible` accepted an asymmetric witness (Z = I/3 with Z[0,1] = 10) and certified a physical family. | The verifier requires a finite, exactly symmetric 3 × 3 Z, and checks its preconditions (orthonormal null directions, b₀ orthogonal to them), raising `ValueError` otherwise. Test: the reviewer's witness is refused, and so are broken preconditions. |
| 7 | A | "Feasible within tolerance" could overclaim: b₀ = (−0.61237243692053940, 0, 0, 0, 0) has every completion below −0.500000001 by about 3.8e-17. | The tolerance status uses the same 1e-14 eigenvalue margin as the strict status, on the safe side. Test: that case is not within tolerance. |
| 8 | B | Removing `FEASIBILITY_DELTA` passed all tests. | Test: an axial dual halfway between the cutoffs with and without δ is rejected only because of δ. |
| 9 | B | The certificate text showed `<Z, S0> = -0.5` at Szz = −0.50000001. | The text uses 12 significant digits and states the cutoff. Test. |
| 10 | B | A custom direction (1, 0, 1e-13, 0, 0) labelled Sxy "fixed-by-symmetry" while it was 8.66. | The label is reserved for structural zeros (the component's functional is exactly zero on the subspace). Test. |

**Mutation testing after the fixes.** Two mutants survived the frozen tests: no covariance
normalization (k = 0) and no SVD normalization (g = 1). Each now fails one new test (rows 1 and
4). The SVD normalization matters only when every whitened entry is finite but ‖wa‖₂ overflows.
Then a verified fit is refused either way, because its covariance is of order 1/‖wa‖² and
underflows; the normalization keeps the rank-deficient results, whose estimates are representable.

**The benchmark baseline.** The process measurement now writes the caller's covariance before
reading the baseline. `np.diag` returns lazily zeroed pages, so the earlier baseline left the
caller's 32 MB out, and counted it against the fit.

**Residual risk, documented.** The boundary certificate uses about 72 % of its 0.1 s budget on the
named machine; one benchmark run measured a single repeat at 0.127 s. The tied-eigenvector dual
remains incomplete (round 71, row 7): such cases may be "undetermined", never "feasible".

**Commit hashes.** The branch was rebased onto `main` after V0.2 merged; the patches are
identical (`git range-diff`). The reviewed hashes above map to: `04d33ed` → `b9788e6`,
`f75b022` → `d96dc1c`, `9276d5d` → `0f93cbf`, `7dd67f7` → `3888b75`.
