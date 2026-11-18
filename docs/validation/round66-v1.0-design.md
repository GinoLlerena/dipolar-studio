# Validation rounds 66–67: V1.0 design review (rigid molecules from XYZ)

Reviewer: GPT-6.2-Sol (Codex, reasoning effort high), independent of the author; the owner
chose this model for Phase 2's reviews. The medium plan allows at most two rounds per step.
Class (A) findings block; class (B) findings are documented.

The document under review is [`docs/phase2/v1.0-design.md`](../phase2/v1.0-design.md). It is
the pre-implementation design review of plan §8 and the gate before V1.1. It changes no code.

## Round 66 (on 0f6c191): NOT READY, 10 A + 3 B

The reviewer confirmed the main code facts:
- replay refuses a record under a different context;
- `_recorded_hash` uses the live context;
- a new context key breaks existing journals and snapshots;
- `fit()` fails at k = 0;
- `D` atoms are not spins.

| # | Class | Finding | Fix |
|---|---|---|---|
| 1 | A | Writing each project at the lowest version conflicts with the journal's rules: the version must never decrease, and one version per record. v2 → v3 → v2 through undo, or a proposal that replaces the project several times, fails replay. | **Replaced** by one complete migration per directory (D-1), a compaction across versions. Afterwards there is one schema. |
| 2 | A | A feature-scoped context and the snapshot format leave mixed states unreadable: a v2 active project with v3 history, proposals or runs. | **Replaced:** one global context after the migration (D-2). Snapshots and journals hold one version only. |
| 3 | A | Run provenance and staleness need the context at submission. A v3 job can finish after an undo to v2; `input_hash` and the results use the live context. | With one schema and context after migration, there is no mixed state. Migrated runs keep their original identities plus the migrated ones, from a map built during the legacy replay. Runs with unrecoverable inputs are stale, never current. Fixtures cover undo, compaction, proposals and the allocator case. |
| 4 | A | Model and isotope transitions were underspecified. `rigid` already means torsion fits and drafts, and v2 drafts store a domain. | A new kind `fixed` and a table of legal states (D-3). Transitions are atomic and validated on every path. Old drafts keep their domain. Isotope rules are in D-6. |
| 5 | A | The group action and the averaged geometry were undefined: no origin, no frame convention, no proof that the average is symmetric. | Centroid origin; frame conventions per group; generators closed into the group table; bijections that must form a group action (π_gh = π_g∘π_h). x* = \|G\|⁻¹ Σ g⁻¹ x_{π_g(i)}. One design row per orbit (D-4). |
| 6 | A | Pair orbits had no import or reconciliation contract. The reconciler keys rows by representative pair, and the CSV turns an omitted multiplicity into 1. | Rows keyed by orbit (spin IDs after mapping). Another member updates the same row and keeps its ID. Omitted and explicit values are distinguished, and classes compared as sets. Orbit-changing edits are refused while rows exist. Every H atom must be a spin (D-5). |
| 7 | A | A small singular value cannot establish structural rank: a ratio near 1e-13 moved across the cutoff when one weight changed. | The required rank comes from the model: d, reduced only by geometric degeneracies verified in Å, independent of the weights. The singular values only verify it, with margins; otherwise the rank is unverified and exact adequacy is withheld. N < d and s_max = 0 are defined (D-8). |
| 8 | A | The estimand after truncation, and the estimability test, were ill-defined (an absolute 1e-9 is not scale-invariant). | A relative projection error after mapping into the symmetry subspace. Symmetry-fixed components are reported separately. With an unverified rank, estimates are labelled approximate, with no exact interval. All statistics are stated as conditional on σ (D-8). |
| 9 | A | Completion must stay inside the symmetry subspace, and the end of an SLSQP run cannot certify infeasibility. | Null directions within the symmetry subspace; a direct test when r_req = d. Feasible means a verified candidate; infeasible means a verified dual certificate Z ⪰ 0, tr Z = 1, ⟨Z, N_k⟩ = 0, ⟨Z, S₀⟩ < −1/2; otherwise "undetermined" (D-9). |
| 10 | A | The observable, result and resource contracts were incomplete: a dense covariance at N = 100 000 is 80 GB; `fit.run` returns a job; `model.set` takes a unit-bearing `phi_domain`. | Covariance stays core-only, with a cap checked before allocation (N ≤ 5000). A typed fixed result with a discriminator, and search-only fields absent. Interfaces keep their shapes. Budgets are measured and enforced on every path (D-10, D-11). |
| 11 | B | Qualify §1: empty journals; the staleness fallback; the job record stores identities; the standalone loader's own message. | §1 rewritten. |
| 12 | B | Equivalence and scope: the definition of magnetic equivalence; C2, C2h and C3v refused only for new declarations, with legacy `c2z` kept. | D-4. |
| 13 | B | Carry the approved gates into §3 explicitly. | §3 lists the V1.1–V1.3 gates and the proposal's open items. |
