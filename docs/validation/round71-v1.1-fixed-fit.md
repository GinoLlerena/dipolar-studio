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
them.

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
