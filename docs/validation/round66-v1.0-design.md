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

## Round 67 (on 28ed78d, the final round under the cap): NOT READY, 11 A + 4 B; fixed without re-review

The reviewer ran the 100 existing journal, snapshot and format tests (all passing). It confirmed
the round 66 fixes for the symmetry average (x* is exactly symmetric, by reindexing with
k = gh), the basis and the reduction table.

| # | Class | Finding | Fix |
|---|---|---|---|
| 1 | A | A "legacy reader" built from today's code is not frozen: it imports the live context and snapshot modules, and opening a session repairs, settles, collects and compacts. Even a `Journal` constructor can create files. | **D-1 replaced:** Phase 1 directories are never opened for writing, only detected read-only and refused with instructions. Projects carry over by their export file. No legacy reader is needed. |
| 2 | A | Publication and crash recovery across versions: `snapshot.choose` loads both snapshots under one context. A fully compacted directory has the same sequence in both. Migration lineage is lost at the next compaction. | Gone with D-1 (no in-place migration). The requirements are kept in D-1 in case the alternative is chosen later. |
| 3 | A | Archived inputs and job staleness: replay never walks `archive/`, idempotency keys can be reused after compaction, and jobs and runs need a per-submission input index. | Gone with D-1: runs and jobs stay in the 0.1 directory. |
| 4 | A | Request outcomes and proposal expiry under a changed contract. | Gone with D-1: the request table and proposals are not carried over. |
| 5 | A | Result blobs: `run.get` decodes every blob as `FitRunOut`; legacy decoding and digest checks are needed before publication. | Gone for legacy blobs (D-1). For new runs, the decoder is chosen from the run record's model kind, which is trusted (D-10). |
| 6 | A | Transitions with populated rows: entering `fixed` can merge two singleton rows, and an edit can *expand* an orbit with one observed row. No way to resolve conflicts (an empty CSV import is refused). No guards or isotope table for the new mutations. | D-3: lossless canonicalization on entry, refusal on merge, split *or* expansion, a defined exit, and a new `couplings.remove` operation. Both new mutations take `expected_science_revision`. D-6: one isotope table on every path. |
| 7 | A | A required rank from a 1e-6 Å coplanarity test can certify a truncated model. Counterexample: (1,0,0), (0,1,0), (1,1,0), (1,0,1e-7) pass the test but have rank 4, and one σ change hides the fourth direction. | **The required rank is d, always.** The only exact reductions are symmetry reductions: a planar molecule is declared Cs, with its plane as the mirror. The counterexample is a V1.1 fixture that must report *unverified*. Rank zero is handled before any ratio. |
| 8 | A | Exact intervals need an exact estimand: a functional with a small nonzero null component can pass a projection test. | With the rank verified, every functional of the d coordinates is exact. With it unverified, only projected coordinates, labelled, with no intervals. Coefficient vectors, levels and `interval_support` are machine-readable; `fit.run(intervals)` has no effect for `fixed`. |
| 9 | A | A tolerance on ⟨Z, N_k⟩ alone does not bound the unbounded family; the direct test only applies at zero nullity. | The finite-precision bound over the bounded physical set (‖c‖ ≤ √(3/2)): ⟨Z, S₀⟩ < −1/2 − (2 + √(3m/2))ε − δ. "Feasible within tolerance" is a separate outcome. The direct test is used only at nullity zero, and rank zero is special-cased. |
| 10 | A | The fixed result lacked the report's rows, the covariance, the null space and the interval support. Old clients break on `run.get` and on `project.describe.model` without `phi_domain`. | `FixedRunOut` is specified with rows, `covariance_b` and `null_directions_b`. The change is **classified breaking** under D20 (contract 0.10.0 → 0.11.0, listed as breaking). For non-fixed projects the responses are unchanged, gated with the 0.10.0 types. |
| 11 | A | Budgets omitted the dominant costs: archive length, n² pair enumeration, peak covariance memory, the worker's 16 MiB result cap, and rank zero with five null directions. | No migration. Orbits for observed pairs only. Covariance cap N ≤ 2000 (about 128 MB peak). Fixed-fit admission N ≤ 20 000 under the 16 MiB cap, tested through the process worker. Rank zero special-cased. |
| 12 | B | §1 and D-2 wording: the request outcomes in snapshots; proposal transactions with jobs; wrong D-numbers for the context entries. | Corrected. |
| 13 | B | D-4/D-7: document the passive frame convention, re-orthonormalizing the axes and the conversion to `ORDER_BASIS`. Ambiguity and failed composition cannot occur with the 0.5 Å minimum separation, so test them below the validation layer. | Added. |
| 14 | B | Equivalence wording; distinct reduced rows; a specified tensor in the 1,4-dichlorobenzene fixture; why the medium must be achiral. | Added. |
| 15 | B | Restore the gates: symmetry copies leave N and ν unchanged; freeze the protocol and fixtures; the V1.2 checkpoint; `fixed` supersedes the proposal's wording; the Fit workspace is V1.4. | §3 restored. |

**One owner decision** comes out of this round: D-1. Carrying Phase 1 projects over by export
file narrows the proposal's V1.3 compatibility gate. The in-place alternative and its
requirements are written in D-1.
