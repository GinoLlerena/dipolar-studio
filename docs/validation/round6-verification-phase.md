# Validation round 6: the verification phase (plan v0.6 draft)

Reviewer: GPT-6.1-Sol (Codex, reasoning effort high), read-only. 2026-11-07.
Scope: the owner's request to put the post-beta models into a new **Phase 2: verification**,
with AI renumbered to Phase 3. Files: `docs/03-redesign-plan.md` §4, §5, §7–§10;
`docs/04-ai-ready-architecture.md` (renumbering); `README.md`; `datasets/README.md`.

## Verdict

**NOT READY** as the Phase 2 execution baseline. The Phase 1 approval is unaffected, and the
Phase 2→3 renumbering is consistent. Phase 2 needed scientific and release-gate corrections.

## Required changes (all applied in plan v0.6 / 04 v0.4)

1. **Blanket synthetic gate.** Exact parameter recovery and ordinary interval coverage are
   impossible for some rank-deficient or confounded models.
   - Freeze the identifiable estimands, equivalences and per-quantity tolerances for each model.
   - Unidentified directions are reported without finite error bars.
   - M1 coverage applies only to supported 68.3% intervals; nonregular cases need their own
     calibration or report "interval not supported".
2. **V1 rank and scale.**
   - The tests must cover rank 5, rank 3 (planar), rank 1 (collinear) and D6h benzene.
   - Fixed XYZ geometry anchors the scale, but fitted bond-length ratios can reintroduce
     confounding. Proton-only benzene depends on the proton-ring radius, so fixing C–C while
     fitting C–H allows an exact compensating rescaling of S. Fitted geometry therefore needs a
     joint-rank check.
3. **V1 spin equivalence.** "Spin equivalence from the declared point group" is too broad.
   - Derive site and pair permutation classes from the isotopic structure, molecular and medium
     symmetry, and fast motions.
   - Keep symmetry-related sites and chemical equivalence distinct from magnetic equivalence.
   - Merged observations must not inflate the sample count.
4. **V4 quadrupolar and total couplings.**
   - A nonaxial EFG needs C_Q (with its uncertainty and source), the asymmetry, the complete
     orientation, the normalization and sign knowledge (D7).
   - `T = J + 2D` applies only under the dataset's declared convention.
   - Joint fits use predeclared criteria on identifiable combinations; separate fits may be
     underdetermined.
   - Shared order across isotopologues needs justification, covering isotope geometry and
     vibrational averaging.
5. **The ¹³C coplanarity rule** was lost when the "After the beta" table was removed. It is
   restored in §4 and referenced from V4.
6. **The V5 AP-DPD gate** was underspecified.
   - Reproduction depends on recovering the geometry, model, averaging, objective and the
     ten-temperature, 31-parameter parameterization, compared against preregistered tolerances.
   - Agreement with the published uncertainty is reported separately; if inputs are missing,
     the benchmark is *pending*.
   - "About 33.0°" (32.95° and 33.05°) is accurate, but it estimates a different quantity.
7. **V0 terphenyl candidate misidentified.** Castiglione et al., *PCCP* 4, 4921–4930 (2002)
   reports **¹³C–¹⁹F** couplings, not ¹³C–¹H. A separate ¹³C–¹H benchmark is required.
8. **"No architectural change" overpromised.** Single-site observables, multiple torsions and
   distributions need domain and schema extensions. The replacement text keeps the boundaries
   and policy semantics, adds a review of schemas, budgets, D19, hashes and replay, and lets
   schemas evolve through D20 and migrations. VarPro is used only where conditional linearity
   holds.
9. **Holdout policy.**
   - Keep development and holdout cases distinct, with related observations grouped.
   - Freeze the model and criteria before a holdout is opened; once opened, it becomes
     regression data.
   - Report "no independent experimental holdout" separately from "synthetic-only".
10. **Scope and status.**
    - The first release is a bounded V0 + V1; V2–V5 are conditional, and V3/V6 are
      thesis-gated.
    - Separate status labels; an explanation does not turn a failure into validation.
    - Phase 3 may proceed from Phase 1 independently.
    - The README wording is softened accordingly.

## Source checks and optional suggestions (applied)

- **Taggar, Campbell, Yethiraj and Burnell**, *J. Phys. Chem. B* 110, 1363–1368 (2006):
  benzene and 1,3,5-trihalobenzenes in ZLI-1132, with coupling tables in the Supporting
  Information. Plausible; the entries, units and rights still need to be checked.
- **Yethiraj et al.**, *Chem. Phys. Lett.* 2004: fluorobenzene, 1,4-dichlorobenzene and
  1,3,5-trichlorobenzene in 8CB. Correct attribution; a complete numerical coupling dataset is
  **unverified**.
- **Sinton 1981** §4.4.1 (4,4′-d₂-biphenyl): relevant, but whether paired numerical ¹H/²H data
  exist is **unverified**.
- **V3 label:** "independently re-derived; legacy parity unverified". **V6:** a difference may
  also trace to a documented intentional change of model or method.
- **04 D19** said "A4 evaluations"; the evaluation milestone is **A5**. Fixed.

## Round 7: confirmation

Same reviewer, read-only, 2026-11-07. **Verdict: READY WITH MINOR CHANGES.** The ten round-6
remedies are substantively present. Three consistency fixes, all applied:

1. **Status rule.** Implementation status (*implemented* or *deferred*) is reported separately
   from verification status (*pending*, *synthetic-only*, *experimentally supported* or
   *unresolved failure*), and independent-holdout availability separately again. V5 uses
   *pending*, which the old list did not include.
2. **Version summary and §10 row 7.** These still promised verification against published data
   without qualification. They now carry the qualified wording: known-answer verification, plus
   a preregistered experimental comparison where suitable data exist.
3. **§9 thesis-derivation risk row.** "Legacy-compatible" is replaced by "independently
   re-derived; legacy parity unverified".

The reviewer also confirmed these checks:

- Phase 3 independence is consistent with its default start after V0 + V1.
- Rank 5/3/1 and the one-parameter D6h constraint pass numerical spot checks.
- The ¹³C–¹⁹F terphenyl attribution matches the authors' repository record.
- The tables parse with no column mismatches, and `git diff --check` passes.
- The authorship and advisor credits are consistent.
- `CITATION.cff` passes the CFF 1.2.0 schema checks.
- This record accurately reflects round 6.
