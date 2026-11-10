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

## Round 15: confirmation

- **Reviewer and date:** the same reviewer, read-only, 2026-11-09.
- **Scope:** commit 5542447.
- **Verdict: NOT READY.**
  - Every frozen tolerance still passed, and the Golub–Pereyra Jacobian agreed with independent
    finite differences (relative error below 2.5·10⁻¹⁰).
  - Three earlier fixes held only for their original reproductions: the derivatives, the crossing
    search and the handling of failed profiles.

**Findings, all fixed** (`test_core_fit_adversarial.py`, each mutation-checked):

1. **Major. `full_jacobian` still differenced the data.** At a stationary point it reported joint
   rank 2, a finite error bar and ν = 1. The fix: the geometry columns differentiate W·D(θ)·t only.
   A test checks that the column is identical for three very different y.
2. **Major. A rival inside the interval hid a gap.** Two zero-cost basins were separated by a
   barrier at χ² ≈ 4.8, and the search stepped over it.
   - **The fix.** Every interval is now **verified before it is accepted**: the profile is sampled
     at 64 evenly spaced interior points, plus any known grid values. A sample above the threshold
     refuses the interval as having a gap.
   - **The test** also covers a search that never found the second basin.
3. **Major. A lower failed nuisance trial was discarded.** The fix: if a failed re-minimization
   reaches a lower χ² than every converged one, the profile point is unresolved, never reported.
   This applies to geometry and order profiles alike.
4. **Minor. Rounding noise flipped a near-zero KKT gradient.**
   - **The fix, part one.** At a bound, an inward gradient within its own rounding noise counts as
     zero. That noise is about 10·ε^(2/3)·‖m‖·‖r‖.
   - **The fix, part two.** A real inward gradient is credited only with the reduction it can
     achieve within the feasible step. A tiny column can no longer promise a large reduction.

**Also:**
- named null directions dropped components below 10⁻⁹. Round 16 showed that this was wrong:
  such components can be genuine. The filter has been removed;
- a redundant segment-sampling pass was removed, because no test needed it once intervals were
  verified.

**Measured.** A fit of the fixture takes 0.18 s. The profiles take 0.03 s for φ, 4.3 s for Szz and
2.6 s for Δ; the verification doubles their cost.

## Round 16: confirmation

- **Reviewer and date:** the same reviewer, read-only, 2026-11-10.
- **Scope:** commit dc88681.
- **Verdict: NOT READY.** The four round-15 reproductions passed. There were three new major
  findings and one minor finding. Round 13 onward had each patched a specific counterexample, and
  each time the next round found a sibling, so this round replaced the two fragile mechanisms with
  principled ones.

**Findings, all fixed** (`test_core_fit_adversarial.py`, each mutation-checked):

1. **Major. Truncation error still invented a joint rank.** For D = (1, 3x³, 0) the derivative at
   the optimum is exactly zero, but the central difference gave 3h², which was counted as rank,
   with an interval, ν and a p-value.
   - **Richardson extrapolation.** Every geometry derivative is now (4·D(h/2) − D(h))/3, with the
     componentwise error estimate |D(h/2) − D(h)|.
   - **A trusted rank.** A singular value counts toward the joint rank only above 10 times the
     Frobenius norm of that error, both in the scan and at the optimum.
   - **Result.** The cubic now gets rank 1. The rule itself has a direct test.
2. **Major. The gradient-noise allowance hid genuine improvement.** For example, a stop at a bound
   was accepted although a feasible move reached χ² = 0.
3. **Major. Summing bound reductions independently missed coupled moves.**
   - **The fix for 2 and 3.** One certificate replaces both the noise allowance and the
     per-coordinate KKT logic.
     - It solves the **bounded linear least-squares step** over all coordinates (`lsq_linear`,
       BVLS) with the exact Golub–Pereyra J, so bounds, signs and cross terms are included.
     - If the predicted reduction exceeds the tolerance, it **tries the step**, halving it up to 40
       times. A step that really lowers χ² means "not converged".
     - Round 16 concluded that a prediction no step realises came from derivative noise. Round 17
       showed that this is wrong (see below).
   - **Tests:** the reviewer's small-gradient cases, at unit precision and with precise data; the
     coupled-bounds case; and a direct test with a 10⁻⁹-amplitude, high-frequency model whose
     derivative promises a reduction that cannot happen.
4. **Minor. The null-vector filter removed genuine components.** The fix: named null directions are
   the numerical basis, unfiltered. A test checks ‖J v‖ ≈ 0 for every reported direction.

**Measured.** A fit of the fixture takes 0.20 s. The profiles take 0.03 s for φ, 4.4 s for Szz and
2.6 s for Δ.

**Accepted limitation.** A barrier narrower than the interval verification's sampling, such as the
reviewer's width-0.001 variant, can still be missed. The docs state this.

## Round 17: confirmation

- **Reviewer and date:** the same reviewer, read-only, 2026-11-10.
- **Scope:** commit f673c60.
- **Verdict: NOT READY.** The four round-16 findings were resolved, but there were two new major
  findings.

**Findings, both fixed and not yet confirmed by a reviewer** (`test_core_fit_adversarial.py`,
each mutation-checked):

1. **Major. A failed trial step was taken as derivative noise.** Nonlinearity can make the joint
   Gauss–Newton direction useless while another feasible move, here x alone, halves χ².
   - **The fix.** An unrealised prediction is certified only if the derivative's own error estimate
     can account for it: TRUST_FACTOR · 2 · |δ|ᵀ(|E|ᵀ|r|) must be at least the predicted reduction.
     Otherwise the point is not converged.
   - **Tests:**
     - the reviewer's case;
     - a high-frequency model whose derivative is aliased, which is not certified;
     - a one-sided cusp whose derivative error is genuinely large, which is certified.
   - **Trying further directions** was considered and dropped, because no test needed it once the
     rule above was in place.
2. **Major. The derivative error estimate erased exactly identifiable directions.** For
   D = (1, x + 10¹⁰x³, 0) the joint rank was 0, although J = [[0, 1], [1, 0], [0, 0]].
   - **Three Richardson levels.** The value is R(h/2), and the error is |R(h/2) − R(h)| rather than
     the raw difference.
   - **A floor.** The joint rank is never below the exact inner rank.
   - **A separate report.** Directions the derivatives cannot resolve are reported in
     `FitResult.uncertain` and flagged by `Validity.derivatives_resolved`. They are no longer
     called unidentified.

**Cost.** A fit of the fixture takes 0.31 s. The profiles take 0.03 s for φ, 6.7 s for Szz and
3.9 s for Δ. The third Richardson level costs about 1.5×.
