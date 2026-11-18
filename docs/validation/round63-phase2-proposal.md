# Validation rounds 63–65: the Phase 2 proposal (V0 + V1)

Reviewer: GPT-6.1-Sol (Codex, reasoning effort high), independent of the author. The medium plan
allows at most two rounds. Class (A) findings block; class (B) findings are documented.

The document under review is [`docs/phase2-proposal.md`](../phase2-proposal.md). It is a
**planning proposal for the owner**: it changes no code, and nothing in it is approved until the
owner decides.

## Round 63 (on 0097788): NOT READY, 3 A + 7 B

| # | Class | Finding | Fix |
|---|---|---|---|
| 1 | A | "With ν ≤ 2, no fitted geometry could be identified anyway" is false. Few residual degrees of freedom do not make a geometry parameter unidentifiable. Counterexample: a D2h proton rectangle with a free aspect ratio has 3 classes, 2 order parameters and joint rank 3 (checked by the reviewer with the forward model). | Fitted geometry is deferred **as a choice of scope**. A model-specific joint-rank calculation is required before any geometry parameter is called identifiable or not. Benzene's scale degeneracy is described as specific. |
| 2 | A | Fluorobenzene was marked as needing ¹H–¹⁹F. It has 6 symmetry-distinct H–H classes under C2v and 2 order parameters, so a proton-only fit could be V1. | The table row now says "proton-only **if** the paper gives the H–H couplings; its H–F couplings are V4". The table states that symmetry counts say nothing about what a dataset contains. |
| 3 | A | "A class counts once in N" conflates symmetry copies with independent repeat measurements. | N counts independent measurement information, never pair multiplicity. One supplied estimate per class is the supported input; independent repeats are not accepted in this release (aggregating them would need propagated uncertainty and the within-class scatter kept for adequacy). |
| 4 | B | When the intervals are exact was unspecified, including the rank-deficient case. | Estimable combinations are the retained right-singular coordinates, variance 1/s_i². The assumptions are stated (fixed geometry, known σ, unconstrained linear estimation), and adequacy uses χ² with N − r degrees of freedom. Constrained, clipped, regularized or nonlinear outputs need calibration or report "interval not supported". |
| 5 | B | The k = 0 boundary was vague. `Problem` accepts k = 0, but `fit()` raises (`zero-size array to reduction operation maximum`, confirmed by the author). | V1.1 requires an explicit k = 0 path with no dummy torsion, and the result contract that goes with it. |
| 6 | B | The frame and permutation promises were not numerical rules. | V1.2 now specifies: symmetry stored as axes or operation matrices with a tolerance; isotope-preserving bijections; pair comparison after the order constraints; tests for both-endpoint permutation, rotated frames and magnetic inequivalence; and the first supported groups (C1, Cs, C2v, D2h, D3h, D6h), with no fast motions. |
| 7 | B | "Migrate and replay to the same science hash" had no target, since the hash includes the schema version. | Loading and replay converge on the same **migrated** identity, and historical hashes are checked under their original rules. Fixtures cover snapshots, runs, undo/redo and staleness. Biphenyl behaviour is preserved, and a decision on old torsion-less drafts is required. |
| 8 | B | The holdout rules were abbreviated, and no fixed-seed regression gate was listed. | V0.2 carries all of plan §8's holdout rules. V1.1 adds a fixed-seed noisy regression separate from coverage. Synthetic estimands and tolerances are frozen before evaluation, and preregistration precedes any experimental result anywhere in V1. |
| 9 | B | "As the beta did for 8CB": no external tester has reproduced it yet. | Removed. |
| 10 | B | The measurements mixed counts with inference, and the cap's history was unqualified. | Measured and inferred are separated, with reproducible counting commands. The cap is dated (adopted during M1 step 1's rounds 13–18). The tag count is corrected to 23 work steps. |

The reviewer confirmed the benchmark counts (3/1/2, 3/2/1, 1/1/0, given the observations exist),
the rank-5/3/1 fixtures as choices, the chemical/magnetic distinction, and that the proposal
keeps the published comparisons, the status labels and the external-user gate. The deferral of
fitted geometry and the change of transcription procedure are flagged as owner decisions.

## Round 64 (on 624a903): NOT READY, 2 A + 2 B; fixed without re-review (the cap)

The reviewer confirmed each round 63 fix and reproduced its checks:
- the D2h rectangle counterexample, joint rank 3;
- fluorobenzene's 6 classes and rank 2;
- `fit()` failing at k = 0;
- the order reductions;
- the benchmark counts 3/1/2, 3/2/1, 1/1/0 and 6/2/4;
- 23 tagged work steps (5 M1, 6 M2, 8 M3, 4 beta), 50 rounds and 29 634 inserted lines.

| # | Class | Finding | Fix |
|---|---|---|---|
| 1 | A | V1.2 omitted **medium symmetry**, which plan §8 requires. In a chiral medium a Cs solute can need five order parameters and a C2v solute three, and mirror-related sites can become distinct. | This release is bounded to an **achiral uniaxial medium**. The assumption is stored with the project, and a chiral medium is refused, with a rejection test. The reduction table and the permutation classes are qualified ("the operations that survive in the medium"). Deriving the effective symmetry from molecule and medium is later work. |
| 2 | A | The benzene degeneracy was stated as "radius times S". The couplings go as S_zz / R_H³. | Now written explicitly: predictions are unchanged when S′_zz = S_zz (R′_H / R_H)³. |
| 3 | B | The interval assumptions omitted Gaussian errors with known covariance (and independence for a diagonal σ). The N − r = 0 case was unspecified. | Both added. With N − r = 0 there is no adequacy p-value and no claim of adequacy, as the fitter already does (`p_value=None`). |
| 4 | B | "A rotated frame gives the same estimable quantities" had no comparison rule, since singular coordinates are not unique. | Compare the predictions, and the estimable subspace and covariance once transformed, never singular-coordinate labels or values literally. |

Under the medium plan there is no third round. The owner then asked for a further, independent validation with a newer model (round 65).

## Round 65 (on 42dbfc8, at the owner's request): GPT-6.2-Sol, NOT READY, 6 A + 4 B

A new, independent reviewer: GPT-6.2-Sol, reasoning effort high. It was asked to judge rounds
63–64 independently. It reproduced the four benchmark rows (3/1/2, 3/2/1, 1/1/0, 6/2/4), the
rank-3 rectangle, the k = 0 failure, the benzene scaling and the order reductions in an achiral
medium.

| # | Class | Finding | Fix |
|---|---|---|---|
| 1 | A | Exact adequacy needs the rank of the model being tested. The inner solve drops singular values at a relative cutoff, and a dropped but nonzero direction leaves signal in the residual, so the statistic is no longer central χ². | The central χ² with N − r is given only for a structural rank or a declared, frozen reduced model. Structural and numerical rank are reported separately, and weak directions are flagged. Exact adequacy is withheld when truncation alone sets the rank. Exact deficiency and a small nonzero singular value are tested separately. |
| 2 | A | Admissibility of a rank-deficient fit tests the solver's minimum-norm completion, which depends on the frame (a rank-1 example passed in one frame and failed in another). | V1 tests whether any completion consistent with the estimable part makes (2S + I)/3 positive semidefinite (a small convex feasibility problem), or reports admissibility as undetermined. The unconstrained fit is kept and a representative is labelled. A two-frame test is added. |
| 3 | A | The rotated-frame covariance gate had no defined estimand: the five-component basis is not orthonormal under the tensor inner product. | Estimates and covariances use an orthonormal tensor basis. Rotations are compared on matched estimable linear functionals with coefficients transformed dually. A rotated rank-deficient C1 fixture is added. |
| 4 | A | The permutation scope (medium, groups, no fast motions) was not posed as an owner decision. Site orbits were not gated, and atoms have no isotope identity. | Owner decision 1 now lists each part. Site and pair orbits come from the same validated action. Per-atom isotope identity is added to schema v3 (or the narrower alternative goes to the owner), with an isotope test (benzene-d₁) that splits an orbit. |
| 5 | A | The step table omitted plan §8 gates: the pre-implementation review of schemas, assumptions, budgets, D19, hashes and replay; noiseless recovery for the symmetry models; reviewed discrepancy entries at exit. | A new step **V1.0 design review** before any code. V1.2 adds frozen noiseless recovery and predictions for each supported group. V1.5 requires a reviewed README entry for every discrepancy. |
| 6 | A | The capability inventory understated existing support (`c2z` exists; null directions are already named and shown) and overstated generality (the multi-parameter search has limits). | Rewritten: the additions are geometry-validated point-group reductions and estimable combinations with uncertainty. The fitter supports one or several geometry parameters, subject to the search's limits. |
| 7 | B | Make experimental eligibility executable. The reviewer reached both papers: Taggar points to free SI coupling tables (completeness unverified), and Yethiraj has order results in a figure but no complete coupling table. Match frames, weights, conventions and estimands; σ provenance; correlated couplings; reproduction versus independent support. | V0.1's status and "What a published comparison can show" now say this. The reviewer's access findings are marked as not yet checked by the author. |
| 8 | B | The holdout needs a custodian and an exposure log. | Added (proposed custodian: the owner). Exposed cases become development data. |
| 9 | B | Re-baseline the critical path. The counts do not size symmetry validation or migration. Resource bounds, approximate symmetry, early torsion-less-draft decision, replay across numerical contexts. | Added to V1.0 and the measurements section. V1.2 has a checkpoint. The estimate is now 9–10 steps. |
| 10 | B | Publication and reproduction choices: `export-ignore` covers archives only; channels per dataset; the external-reproduction path; whether synthetic counts; ¹³C satellites as a separate V4 selection. | Owner decisions 3 and 6, and the V0 text. |

This round was beyond the two-round cap, at the owner's request. Its fixes are not re-reviewed
unless the owner asks.
