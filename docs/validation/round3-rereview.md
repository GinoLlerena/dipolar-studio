# Round 3 — focused re-review of plan v0.2

Reviewed 2026-11-07 against `03-redesign-plan.md`, the reconciled bug report, and both prior reviews.

**Verdict: READY WITH MINOR CHANGES for the narrowed scientific beta execution baseline.** Proceed with M0; resolve issues 1–5 in its binding ADRs before accepting M1. The 6–8-month target remains conditional on staffing, workflow selection and spike results. This verdict approves planning and execution, not scientific results or release readiness.

**Method/limits.** Independently checked projection, quantiles, rotation algebra and a joint-rank counterexample using NumPy/standard-library calculations. Re-read the relevant legacy loops and rotation source as Latin-1, read-only. Compared every requested bug row with round 1. No Windows build, packaged spike, experimental refit or coverage experiment was performed. Only this report was written.

## Disposition of the ten round-2 changes

| # | Change | Assessment and reason |
|---|---|---|
| 1 | Scientific/inference contract | **PARTIALLY** — stable whitened VarPro, TRF, full covariance, profiles and gates are present; ν, regularity assumptions and validity semantics need tightening. |
| 2 | Model-specific identifiability/symmetry | **ADDRESSED** — D12 replaces the absolutes, gives the regular bisector algebra and gates historical parity/endpoint interpretation. |
| 3 | Staffed scientific beta | **ADDRESSED** — §4/§8 narrow scope and condition dates on confirmed capacity and reserve in M0. |
| 4 | Sidecar ADR/packaging spike | **ADDRESSED** — D10 and M0 cover authentication, transport, resource/process controls and packaged negative tests. |
| 5 | In-place bug reconciliation | **PARTIALLY** — substantive corrections are integrated; B13 still overstates its masking condition and B09 omits entered-bound qualifications. |
| 6 | Gated legacy import | **ADDRESSED** — fixtures precede the spike; supported variants, ambiguity/loss reporting and reviewed bindings gate runs. |
| 7 | Benchmark specification | **ADDRESSED** — named workloads, cold/warm and persisted timing, memory, acceptance and numerical comparisons replace speedup arithmetic. |
| 8 | Observable schema/extensions | **ADDRESSED** — raw/sign/isotope/error/J metadata and signed-D beta scope separate later measurement models. |
| 9 | Immutable/durable runs | **PARTIALLY** — snapshots, atomic commits, resume and stale revisions are required; hash canonicalization and numerical acceptance rules remain unspecified. |
| 10 | Operational metrics/priorities | **PARTIALLY** — corpus and deferred features are prioritized correctly; several “definitions” still instruct future definition rather than supplying a protocol. |

## Technical checks

**D3:** Whitening and the residual-vector prescription are correct: the control returns `t*=0.8`, `χ²=0.8`. The thresholds are numerically correct: 1.0000, 3.84146 and 2.29575 for the stated confidence levels/dimensions. Profile versus slice and full versus reduced Jacobians are correctly distinguished. Remaining qualifications are below.

**D7:** The angular-γ prefactor has the correct sign and `2π`; its distance-unit conversion and tensor definitions need completion. **D10:** requirements are credible as spike acceptance requirements, not demonstrated controls. **D11:** stale-result and cross-platform principles are sound, pending an executable persistence contract.

**D12:** For active `Rz(δ/2)`, `S=R diag(sx,sy,sz) Rᵀ` gives `Δ=(sx−sy)cosδ` and `Sxy=½(sx−sy)sinδ`; numerical error was below `3×10⁻¹⁷`. C2(z), reflection/scale invariance and planar/collinear rank ceilings are correct. Regularity at 90° does not itself impose D2d; D12 correctly requires the additional endpoint constraint for that ideal model.

**§4/§6:** beta scope and benchmark caveats are coherent. The approximately 43 MB example agrees with round 2 under its stated array layout; it is not a general memory bound. **§5/§11:** corrected confidence/preview language and fluorine values are faithfully carried over. §11's “σ scales linearly” means *parameter uncertainty* scales with measurement σ for a regular fixed design. The remaining D9 wording was not superseded.

## Requested bug-row spot checks

| Rows | Result against round 1 |
|---|---|
| B04, B07, B08 | Correct: assumed sentinels/extrapolation, partly eliminated RHS and qualified 1000% tolerance. |
| B09 | Negative-counting versus zero-recursion mechanisms corrected; entered-loop bounds still need stating. |
| B12, B15 | Correct: nonzero cross terms and ordinary first/second terminal mappings. |
| B13 | Mechanism/test corrected; “masked … bond passes through the origin” remains false for reversed directed axes. |
| B19–B24 | Correct substantive mechanisms and revised severities, including cache refresh, legal schema 0 and conditional malformed-distance consequences. |
| B25–B30 | Correct: B25 refuted; access time qualified; unused helper downgraded; SDI leak, suffix deletion and capacity/index distinction retained. |
| B34, B46, B54 | Correct overflow sites, stale rename/delete path, and fresh-process versus SDI/latent-plane distinctions. |

Inline severity corrections are authoritative even where rows remain under historical S2 headings. The 56 retained-findings count is appropriate.

## Remaining issues, ranked

1. **Correct ν and joint-rank semantics (D3:95–97).** `rank(B)+n_geometry` can double-count directions absorbed by order parameters. Example: N=3, rank(B)=2 and one geometry derivative inside col(B) gives the plan's ν=0, although joint rank is 2 and residual dimension is 1. For a regular identifiable interior model use `ν=N−p_free`; report joint whitened-J rank separately, with `N−rank(J)` only a local residual-dimension diagnostic outside that case. Zero nominal ν does not establish uniqueness; negative nominal ν flags underdetermination. Active inequality bounds do not justify simple parameter subtraction. [NIST's regular nonlinear-regression convention](https://www.itl.nist.gov/div898/strd/nls/data/LINKS/c-roszman1.shtml) is N−p.

2. **Bind uncertainty to a likelihood (D3).** State fixed positive-definite Gaussian covariance for the baseline; qualify Δχ² thresholds as regular approximations. Boundaries, rank changes and unidentified modes need calibrated coverage or an explicit unsupported-interval status ([Self–Liang](https://doi.org/10.1080/01621459.1987.10478472)). Define `χ²=‖r‖²=2*result.cost` with linear loss: [SciPy minimizes half the squared norm](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.least_squares.html). Do not automatically rescale known-σ covariance by reduced χ². Distinguish copied symmetry rows from genuinely independent repeated measurements.

3. **Make validity flags independent (D3).** Record inner-design rank, joint-J rank, convergence and physical admissibility separately; “full rank” can coexist with a nonphysical optimum. A nonphysical minimum-norm representative does not prove every null-space-equivalent tensor is nonphysical. Show that limitation; enforcing PSD would require a constrained inner solve. Rank thresholds/conditioning and unsupported intervals need explicit policies.

4. **Complete D7's units and definitions.** The written SI K has units Hz·m³; multiply by `10³⁰` for Hz·Å³ if r is in Å. State `S=½⟨3ccᵀ−I⟩`, alignment `A=⟨ccᵀ⟩−I/3`, and `η=(Sxx−Syy)/Szz`. Label degenerate axes nonunique; a display convention cannot make them measured directions.

5. **Freeze the actual symmetry frame (D12/M1).** Document active/passive rotation, ring axes, torsion sign and C(g); include frame derivatives in the full Jacobian. Test contraction invariance, legacy equivalence away from the pole, and the ideal D2d endpoint. “Identical rings” alone must not authorize D2d constraints for arbitrary substituted/imported geometry.

6. **Finish B13/B09 reconciliation.** B13 is masked by the same *directed* nonzero axis, not merely a shared line. For P0=(2,0,0), P1=(1,0,0), the old axis is +x and the intended axis −x. B09's hangs require entering the relevant initial≤final loop.

7. **Make D11 testable in M0/M2.** Specify canonical hash content, model/constants/solver/covariance provenance, validated chunk publication before manifest publication, durability/recovery policy and orphan handling. Supply quantity-specific atol/rtol values before acceptance; compare invariant predictions/subspaces when axes are nonunique.

8. **Freeze evaluation protocols (§5/§7).** Specify actual task events, participant/novice denominators, scoring rules and cancellation limits. Partition corpus development/regression cases from an untouched experimental holdout; do not develop against the holdout.

9. **Correct D9 before distribution.** Replace “clean-room rewrite” with “independent reimplementation informed by source review”; complete ownership/dependency licence checks before adopting a distribution licence.
