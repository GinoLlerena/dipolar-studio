# Phase 2, first verification release (V0 + V1): a proposal

**Status: draft for the owner (2026-11-18).** Nothing here is approved. Plan §8 says that after
the beta, the owner selects and re-baselines the first verification release, **V0 (benchmark
corpus) plus V1 (rigid molecules from XYZ)**. This page proposes:

- what V0 and V1 contain;
- how they split into steps;
- what each step must prove;
- the decisions the owner needs to make.

It sets no dates (see [What the measurements support](#what-the-measurements-support)).

## Where Phase 1 left things

The beta (`v0.1.0b1`) fits one torsion and the order of a biphenyl-type molecule. What V1 can
reuse:

- **Imported geometry.** XYZ geometry is read with bond perception.
- **Order models.** The order models `c2z` and `c1` work in the input frame. The frame
  contract and the rank diagnostics are in place: inner (order) rank, joint rank, and the
  condition number.
- **The fit's outputs.** Admissibility of the order matrix, adequacy under the stated σ, and
  validity flags, each judged separately.
- **Couplings import.** The CSV reconciliation (D5) and the `multiplicity` and
  `equivalent_pairs` columns.
- **The application.** The application layer (operations, journal, undo, proposals, jobs, runs,
  reports), the browser app, the robot and the CI gates.

What it lacks for V1:

1. **A fit with no geometry parameter.** Every fit today has a torsion φ: the D3 stack scans φ
   on a grid, refines it and profiles it. An imported XYZ is refused until a torsion is declared
   (`science.problem_for`). A rigid molecule has no geometry parameter, so its fit is a weighted
   *linear* least-squares problem in the order parameters alone.
2. **Symmetry.** There are no declared symmetry reductions (for example, one order parameter for
   benzene in D6h). The equivalences of imported molecules come only from the user's
   `equivalent_pairs` column, not from the molecule's symmetry.
3. **Reporting what is identifiable.** Results do not say which combinations of order parameters
   the data determine. A planar molecule, for example, determines only the in-plane block.
4. **The app's views.** The Fit workspace assumes φ (preview slider, χ² landscape), and so do the
   robot tutorials.

## V0: the benchmark corpus

V0 is mostly finding and checking data, not code. Its exit (plan §8):

- every selected extension has at least one experimental dataset or an explicit
  *synthetic-only* label;
- rights are documented before anything is published;
- no transcribed value is left unverified.

**What the candidates can test.** Proton-only rigid benchmarks are small. Under the molecule's
symmetry:

| Candidate (plan §8) | Proton couplings (distinct) | Order parameters | ν | What it can test |
|---|---|---|---|---|
| Benzene (D6h) | 3 (ortho, meta, para) | 1 (S_zz) | 2 | the scale, and the geometry's shape |
| 1,4-dichlorobenzene (D2h) | 3 (ortho, meta, para) | 2 (S_zz, S_xx − S_yy) | 1 | barely over-determined |
| 1,3,5-trichlorobenzene (D3h) | 1 (meta) | 1 | 0 | nothing beyond the scale: the fit is exactly determined |
| Fluorobenzene | needs ¹H–¹⁹F | | | V4 (a new measurement type), not V1 |

So **V1's experimental comparisons would rest on very few degrees of freedom**. Its main
verification would be synthetic (known answer). V0 should therefore also look for at least one
rigid dataset with clearly more couplings than order parameters, either proton-rich or with
¹³C satellites. ¹³C satellites, however, are V4 unless they are selected.

**The published order parameters depend on the authors' geometry**, and often on vibrational
corrections too. A fair comparison takes the published geometry as input. The agreement
criterion is then preregistered on that basis, and any disagreement is reported, not tuned away.

**Proposed steps:**

- **V0.1 Selection and access.** A written selection protocol, then a confirmation for each
  candidate: where the numbers are (main text, Supporting Information, a thesis), whether the
  table is complete, units, signs, conditions, and the rights basis.
  - Status on 2026-11-18: the authors' copies of the Yethiraj (2004) and Taggar (2006) papers
    could not be reached from here, so both stay **unverified**.
  - The ACS Supporting Information may need the owner's library access.
- **V0.2 Transcription and verification.** Each value is entered once and cross-checked against
  the rendered source page. On 2026-11-17 the beta walkthrough did exactly this for Di Pietro's
  Table 3.1 (`docs/validation/beta-walkthrough-v0.1.0b1.md`). Each dataset gets a README
  (source, checksum, rights basis, numbering map, conventions, estimand, published values) and a
  development/holdout split.
- **V0.3 Preregistration.** The estimands, tolerances and agreement criteria for each dataset
  are frozen and committed **before** any V1 result on it is looked at.

V0 needs no change to the app and does not disturb the beta testers, so it can start at once.

## V1: rigid molecules from XYZ

**Scope proposed for V1: fixed geometry only.** The imported geometry is the scale anchor
(D12), and only the order parameters are fitted.

**Fitting geometry is deferred.** Examples are a ring radius, or a C–H distance against a fixed
C–C. Plan §8 requires a joint-rank check and enough independent constraints for any fitted
geometry. Its own example is exactly this trap: for proton-only benzene, fitting the C–H bond
while fixing C–C rescales S exactly. With the candidates above (ν ≤ 2), no fitted geometry
could be identified anyway. If a richer dataset turns up in V0, a separate step **V1b (fitted
geometry)** can be selected later.

**Proposed steps** (each the size of a Phase 1 step, ending as Phase 1's steps did: tests, at
most two review rounds, a tag):

| Step | What it builds | What it must prove |
|---|---|---|
| **V1.1 Linear rigid fit** (core) | A fit with no geometry parameter: the order parameters by weighted linear least squares on the whitened design. The identifiable combinations come from its SVD, in the declared frame; unidentified directions are reported with no error bars. The covariance of the identifiable combinations; adequacy and admissibility as today. Exact linear-Gaussian intervals | Noiseless recovery for a **nonplanar rank-5**, a **planar rank-3** (S_xx, S_yy, S_xy; S_xz and S_yz unidentified) and a **collinear rank-1** case. The rank decision tested in both directions (it neither hides a real direction nor invents one). The M1 coverage protocol (1000 seeds, 64.5–72.1 %) on the supported intervals. The φ-path results (the biphenyl gates, 8CB) unchanged |
| **V1.2 Symmetry and permutation classes** (core) | A declared point group and frame, which reduce the order matrix (for example D6h → S_zz only; D2h → S_zz, S_xx − S_yy). Permutation classes of sites and pairs derived from the declared isotopic structure, molecular symmetry, medium symmetry and fast motions, checked numerically against the geometry. Chemical equivalence kept distinct from magnetic equivalence. A class counts once in N | **Ideal benzene in D6h has one independent order parameter.** A declared symmetry the geometry does not have is refused. Merged observations never inflate N or ν. Relabelling under the symmetry leaves the fit unchanged. A geometry-confounding check: proton-only benzene shows the scale degeneracy the plan describes |
| **V1.3 Application** | The model `rigid` without a torsion for imported geometry, with the symmetry declaration. Project schema v3 with a migration (D20), journal replay, readiness ("ready to fit" without a torsion), reports without φ, and a contract version bump | v1/v2 projects migrate and replay to the same science hash. Every new operation is in the registry snapshot and has a Python/HTTP parity test. A report states the identifiable combinations |
| **V1.4 Browser and robot** | A Fit workspace without φ (no slider or landscape; a panel for the identifiable combinations). A Structure view for one-ring molecules. A robot tutorial (synthetic benzene or 1,4-dichlorobenzene from XYZ) and its browser test on three browsers | The robot tutorial and the page give the same run (the M3 comparison, fail-closed). The AI-readiness checks stay green |
| **V1.5 Verification report and exit** | One page per dataset: data, model, estimand, our result, the published result, the preregistered criterion, and the status labels (implementation; verification: *pending*, *synthetic-only*, *experimentally supported* or *unresolved failure*; holdout availability) | Every V0/V1 gate green. Each experimental result carries an honest label; an explained discrepancy is not counted as validation. At least one external user reproduces a Phase 2 dataset, as the beta did for 8CB |

V0.1–V0.3 run beside V1.1–V1.2, since the core work needs no data. V0.3 must be done before
V1.5 opens any experimental result.

## What the measurements support

Phase 1 after M0 measured:

- **Calendar.** From M1 step 1 (2026-11-10) to the draft release (2026-11-17): 22 tagged steps
  in 8 calendar days.
- **Review.** About 50 independent review rounds (13–62). The first round of almost every step
  was NOT READY, and every finding was fixed under the two-round cap.
- **Size.** About 29 600 inserted lines in `packages/` and `web/src` (product and tests).

As after M0, **writing the code was not the bottleneck**. The time went to specifying the step,
adversarial review and fixing what it found. On that basis V0 + V1 is about **8 steps**:
3 for V0, mostly research and owner time, and 5 for V1.

**The owner's hours are still not logged** (the tables in `docs/STATUS.md` are empty), so
neither the owner's effort nor a calendar estimate can be given. Plan §8 also ties the 1.0 date
estimate to after the beta.

## Decisions for the owner

1. **Scope.** Approve V0 + V1 as above, with **fixed geometry only**, and fitted geometry
   deferred to a later, separately selected V1b. *Recommended.*
2. **Timing.**
   - V0 (research, no code) can start **now** without affecting the beta testers. *Recommended.*
   - V1 code either waits for the beta exit, or, if testers are slow, starts on `main` while
     beta fixes go to a `release/0.1` maintenance branch. A tester's fix then never ships half a
     V1.
3. **Data policy.** By default, as for 8CB: published data are used for validation only, kept
   removable, and **not redistributed** in releases (export-ignore), unless a dataset's rights
   clearly allow it.
4. **Transcription.**
   - Plan §8 says the owner enters each value and an independent AI cross-checks it against the
     rendered page.
   - To save the owner's time, an alternative: two independent AI transcriptions from the
     rendered page, compared mechanically, with the owner spot-checking. The owner chooses.
5. **Access.** The ACS Supporting Information and some papers may need the owner's library
   access.
6. **Alternative.** Plan §8 lets Phase 3 (AI integration) start from Phase 1 instead. This
   proposal follows the plan's default order: V0 + V1 first.

Still open from before: the hours log and the thesis PDF. The thesis matters for V3 and V6, not
for V0 + V1.
