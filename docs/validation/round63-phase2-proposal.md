# Validation rounds 63–64: the Phase 2 proposal (V0 + V1)

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

The proposal goes to the owner with these fixes. Under the medium plan there is no third round.
