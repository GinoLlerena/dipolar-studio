# Validation round 19: M1 step 2 (frame contract, C2(z)/C1, analytic derivatives)

- **Reviewer:** GPT-6.1-Sol (high effort), independent and read-only.
- **Reviewed:** commit 27306e0 against `m1-step1` (ba69b05).
- **Verdict: NOT READY.** Two class-(A) findings and one class-(B) finding.
- **Confirmed without defects:** the frame formulas, the torsion sign, the legacy D4 and D2
  coefficient equivalences, the analytic geometry derivatives, the D2d label and the sub-model
  derivatives. The reviewer also checked randomized k = 3 GLS Jacobians.

## Findings and responses

### 1. (A) A zero analytic error estimate invented identifiability

**The counterexample.** D(x) = [a + 10⁸·x·b, c − 10⁸·x·b] with y = a + c, so that
D(x)·[1, 1] = y for every x. The parameter x is unidentified, and the true joint rank is 2.

The computed t* differs from [1, 1] by rounding, and the large ∂D amplifies that difference into
a spurious singular value of about 1.3·10⁻⁷. Because the analytic path counted zero error, it
reported:
- joint rank 3 and `regular=True`;
- a finite stderr of about 7.9·10⁶ and ν = 3.

**Fix.** Analytic columns carry a rounding allowance, `fit._analytic_error`. It counts the
contraction's own rounding, ε·(|W∂D|·|t| + |W∂F|), and the error of t*, `fit._solve_error`.

**A sibling found while mutation-checking the fix.** The finite-difference path of step 1, which
is already pushed, had the same defect. With an ill-conditioned inner design
D(x) = [a + x·b, a + g·c − x·b]:
- for g = 10⁻⁶ … 10⁻⁸, or with a residual orthogonal to every column, both paths reported joint
  rank 3 and `regular=True` for the unidentified x;
- t* carries an error of about ε·(κ‖t‖ + κ²‖r‖/s_max) along t₁ − t₂, exactly the direction the ∂D
  columns read. With the residual, the realised error reached 0.09.

**Fix for the sibling.** `_full_jacobian` now adds ROUNDING_FACTOR · δt · Σ_j |W∂D|_{·j} to every
geometry column on both paths. On the finite-difference path, W·D is differenced alongside W·D·t
to obtain |W∂D|.

The certificate's gradient error (`_varpro_jacobian`) keeps only the contraction rounding: by
the envelope theorem, Aᵀr = 0 makes the gradient insensitive to δt to first order.

`FIT_VERSION` is now varpro-trf.6. The fixture gates are unchanged.

Tests:
- `test_analytic_rounding_never_invents_a_joint_rank`;
- `test_the_inner_solve_error_never_invents_a_joint_rank`, with 10 cases: three gaps, a
  residual, and both paths.

Mutation checks: dropping the allowance, its δt term, or its κ² term each makes a test fail.

### 2. (A) [0°, 90°] is not a complete fold at fixed labels

**The counterexample.** All 45 labelled pairs, generated with c1 at 143°. The acute fit lands at
90° with χ² ≈ 6.9·10⁶. With the upper bound at 180°, the fit recovers 143° exactly.

**Fix.**
- `rigid_problem(..., domain=)`:
  - `"acute"` is [0°, 90°], the default and the frozen fixture's domain. Its precondition is
    stated: ring-B labels are assigned so that the torsion is acute.
  - `"fixed-labels"` is [0°, 180°]. It is complete for every order model, by the y → −y
    reflection.
- An acute fit that sits at the 90° bound carries `ACUTE_BOUND_NOTE`.
- The relabelling is published as `RING_B_RELABELLING`, and the tensor maps the reviewer derived
  as `RELABELLING_MAPS[frame]["180-phi" | "180+phi"]`, for both frames.

Tests:
- `test_the_ring_b_relabelling_maps`, for both frames, both maps and three angles;
- `test_an_obtuse_torsion_needs_the_fixed_label_domain`, for all three order models.

### 3. (B) The wider tensors break the template's D2 symmetry

At φ = 37°, Sxy alone gives H2–H6 and H2′–H6′ couplings of opposite sign, although D2 relates
those pairs.

**Documented** in the `biphenyl` module docstring: c2z and c1 are reference models, and nonzero
off-diagonal components with the identical-ring template are phenomenological.

The test `test_wider_order_models_break_the_template_d2_symmetry` records the fact.

## State after the fixes

320 tests pass (`-m "not slow"`), and ruff and mypy are clean. Round 20 is the second and last
round under the owner's two-round cap.
