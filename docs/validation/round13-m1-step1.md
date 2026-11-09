# Validation round 13: M1 step 1, the D3 stack

- **Reviewer:** GPT-6.1-Sol (Codex, reasoning effort high), read-only.
- **Date:** 2026-11-09.
- **Scope:** `git diff a27b984..07bdc0c`: `dipolar_core.fit`, `dipolar_core.problem`,
  `biphenyl.rigid_problem` and their tests.

## Verdict

**NOT READY.** The frozen biphenyl path passed. Small adversarial problems, however, reproduced
wrong joint ranks, incomplete null spaces and intervals that were reported as supported when they
were wrong. There were six major findings and six minor ones.

## Findings and fixes

All twelve findings are fixed. Every one of the reviewer's counterexamples is now a permanent test
in `packages/dipolar-core/tests/test_core_fit_adversarial.py`. Each fix was mutation-checked:
restoring the old behaviour makes its test fail.

1. **Major. Asymmetric finite differences invented identifiability.**
   - **The problem.** At a stationary point 10⁻⁷ from a bound, the clipped secant gave a derivative
     of 6·10⁻⁶, a full joint rank and a finite error bar.
   - **The fix.** The stencil never leaves the bounds: a centred difference when it fits, and a
     second-order one-sided difference at or very near a bound. The derivative is now 0, the
     joint rank 1, and the optimum irregular.
2. **Major. Bracket expansion skipped crossings.**
   - **The problem.** Doubling from the Gauss–Newton step (10) jumped over the first crossing
     at 0.146.
   - **The fix.** Geometric sampling outward from 2⁻¹⁰ of that step. Each bracket is subdivided to
     find the *first* crossing, and the profile is probed beyond each endpoint so that further
     components are detected.
   - **Also:** when another basin lies inside the threshold, the region has several components,
     so the interval is not supported. This covers the two-mode and the 42-basin examples.
3. **Major. Nuisance profiles stayed in the original basin.** The fix: constrained re-minimizations
   start from every known basin (up to 16). The reviewer's x = 2 case now finds χ² = 0.04.
4. **Major. Failed nuisance optimizations still produced intervals.** The fix: a profile point
   whose re-minimization does not converge makes the interval unsupported, and the note says why.
5. **Major. The null space was incomplete when N < p_free.** The fix: a full SVD, so the number of
   named directions equals p_free − joint rank.
6. **Major. There was no full error covariance Σ (D3.3).**
   - **The fix.** `Problem(covariance=…)` accepts a full positive-definite Σ, and checks that it is
     symmetric, positive definite, has a positive diagonal and matches σ. The whitening W = L⁻¹ is
     applied consistently in the inner solve, the residuals and the Jacobian.
   - **Controls:**
     - a diagonal Σ given as a matrix equals the σ vector;
     - correlated (AR(1)) errors match an independent closed-form GLS solution: t, χ² and
       (Jᵀ Σ⁻¹ J)⁻¹.
7. **Minor. Scan points carried no validity records.** The fix: every scan point records its inner
   rank, condition number, joint rank and admissibility. A test uses the five-component tensor,
   which loses rank at φ = 0.
8. **Minor. Sobol starts collapsed into one basin, and unfinished runs were called basins.**
   - **Starts.** They are now the local minima of the nearest-neighbour graph, lowest χ² first, so
     the narrow well is reached.
   - **Unfinished trials.** They are reported apart from basins.
   - **Convergence.** "Converged" now also requires a negligible predicted Gauss–Newton
     reduction, ‖P_J r‖² ≤ 10⁻⁸ in χ² units. This exposed TRF stopping on `ftol` at a point that
     is not stationary.
   - **A new flag.** `search_resolved` is False when an unfinished trial has a lower χ² than the
     best basin, and `regular` requires it. The docstring no longer promises that no basin is
     ever missed.
9. **Minor. "At bound" depended on the opposite bound.** The fix: each bound uses its own scale,
   10⁻⁹·max(1, |bound|), or TRF's active-bound report.
10. **Minor. A scalar interval was labelled as a joint region.** The fix: labels state the
    one-parameter coverage of the raw threshold, for example "87.1% one-parameter (Δχ² = 2.3)".
11. **Minor. Some inputs were not validated.** The fix: the grid, `n_sobol` (a power of two),
    `n_starts`, the tolerance, `max_nfev` and Δχ² (finite and positive) are checked before any
    numerical work.
12. **Nit. Some tests and docs overstated precision.**
    - The recovery tests now use `rtol=0`.
    - The default grid now has a spacing of at most 0.5, and exactly 0.5 on [0°, 90°].
    - The import guard now builds a problem, the registry and the HTTP app.

**Version.** `FIT_VERSION` is now `varpro-trf.2`.

## Checked and found correct by the reviewer

- **The residual vector.** `profile_residual` has the right sign, and TRF works on the residual
  vector.
- **SciPy settings.** `x_scale="jac"` works with bounds.
- **The standard parts.**
  - The ε^(1/3) central difference in the interior is right.
  - The order columns are exact.
  - The full-rank SVD covariance is right.
  - Known σ is not rescaled.
- **Profiles and slices.** In a single regular basin the right nuisance parameters are
  re-minimized, and slices hold them fixed.
- **Irregular optima.** At an inner-rank-deficient optimum the result is irregular and the
  direction is named. ν = 0 gives no p-value, and `chdtrc` is used correctly.
- **The import guard** runs in a fresh process.

## Round 14: confirmation

- **Reviewer and date:** the same reviewer, read-only, 2026-11-09.
- **Scope:** commit 375d79c.
- **Verdict: NOT READY.** Nine round-13 findings were resolved and two partially resolved. Three
  new major problems were introduced by the round-13 fixes. There were also two minor findings and
  one nit.

**New findings, all fixed** (`test_core_fit_adversarial.py`, each mutation-checked):

1. **Major. Narrow bounds crashed the scan.** With bounds [0, 1e-5], no fixed-step stencil fits.
   The fix: one shared stencil, `_derivative`. It is centred when it fits; otherwise it is
   second-order one-sided toward the roomier side, with its step shrunk to fit.
2. **Major. Finite-difference noise rejected an exact optimum with a large χ².**
   - **The root cause.** The residual contains the constant −W·y. Differencing it costs ε·‖r‖ of
     rounding, so the noise in the certificate grew like ‖r‖⁴.
   - **The fix.** `_varpro_jacobian` differentiates only the model and the design, never the data,
     and builds the **exact Golub–Pereyra Jacobian**, J = (I − QQᵀ)·∂m − (A⁺)ᵀ(∂Aᵀ r). Its gradient
     Jᵀr = ∂mᵀr is exact (envelope theorem). TRF uses this Jacobian too.
   - **A floor.** A certificate floor of 10 · tolerance · χ² stands for TRF's attainable resolution:
     its relative `ftol` ignores smaller improvements. Without it, interior optima with large
     misfits were rejected.
   - **Tests.** Exact misfits at 1e3, 1e5 and 1e7 σ, ν = 2; a nonlinear biphenyl misfit at 1e6 σ;
     and the Jacobian against a careful finite difference. Mutation checks show that both the floor
     and the second Golub–Pereyra term are needed.
3. **Major. Active columns were dropped without the bound's gradient sign.** The fix: a bound
   binds only if the gradient points out of the domain (KKT). A TRF stop on a bound with an inward
   gradient is unfinished, and a genuine bound optimum is accepted and flagged.
4. **Minor. The full SVD allocated N × N.** The fix: full matrices only when N < p_free. Peak
   memory on N = 3000 is now below 20 MiB.
5. **Minor. "Several components" was claimed without proof.** The fix: another basin inside the
   threshold refuses the interval only if its value of the profiled parameter lies *outside* the
   interval. That proves a second component of the profile's level set. The reviewer's connected
   two-basin case now gets its analytic interval, ±1/√99.99.
6. **Nit. STATUS anticipated the verdict.** The fix: STATUS gives the actual verdicts and test
   counts, and notes the 16-start cap.

**Measured.** A fit of the fixture takes 0.18 s. The profiles take 0.02 s for φ, 1.8 s for Szz and
1.5 s for Δ.
