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

1. **A fit with no geometry parameter.**
   - The core's `Problem` already accepts zero geometry parameters (k = 0), and its inner linear
     solve works.
   - The top-level `fit()` does not: with k = 0 it raises `ValueError: zero-size array to
     reduction operation maximum` (checked on 2026-11-18, round 63). The stack's grid or Sobol
     scan, refinement and profiles all assume at least one geometry parameter. Any number from
     one up is supported, not only φ.
   - The app refuses imported geometry until a torsion is declared (`science._problem_for`).
   - A rigid molecule with fixed geometry has no geometry parameter, so its fit is a weighted
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

The counts below are symmetry counts. They hold only **if the paper actually reports an
independent value for each class**, which V0.1 must check; symmetry says nothing about what a
dataset contains.

| Candidate (plan §8) | Symmetry-distinct H–H classes | Order parameters | ν, with fixed geometry | What it can test |
|---|---|---|---|---|
| Benzene (D6h) | 3 (ortho, meta, para) | 1 (S_zz) | 2 | S_zz, and the coupling ratios against the assumed geometry |
| 1,4-dichlorobenzene (D2h) | 3 (ortho, meta, para) | 2 (S_zz, S_xx − S_yy) | 1 | barely over-determined |
| 1,3,5-trichlorobenzene (D3h) | 1 (meta) | 1 | 0 | nothing beyond the scale: the fit is exactly determined |
| Fluorobenzene (C2v) | 6 | 2 | 4 | a proton-only fit, **if** the paper gives the H–H couplings separately; its H–F couplings are V4 |

So **V1's experimental comparisons may rest on few degrees of freedom**. Its main
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
  (source, checksum, rights basis, numbering map, conventions, estimand, published values).
  The development/holdout split follows **all** of plan §8's holdout rules:
  - related observations (the same sample, the same paper series) are grouped and never split
    across the two sides;
  - the model and the criteria are frozen before a holdout is opened;
  - an opened holdout becomes regression data;
  - the report says when no independent holdout exists.
- **V0.3 Preregistration.** The estimands, tolerances and agreement criteria for each
  experimental dataset are frozen and committed **before** any V1 result on it is looked at,
  anywhere in V1, not only in V1.5.

V0 needs no change to the app and does not disturb the beta testers, so it can start at once.

## V1: rigid molecules from XYZ

**Scope proposed for V1: fixed geometry only.** The imported geometry is the scale anchor
(D12), and only the order parameters are fitted.

**Fitting geometry is deferred**, as a choice of scope; plan §8 makes it conditional, not
mandatory. Examples are a ring radius, or a C–H distance against a fixed C–C.
- **Why defer.** It adds a joint-rank analysis for each model and a geometry-parameter
  interface, and the candidate datasets are still unconfirmed.
- **Few degrees of freedom do not, by themselves, make a geometry parameter unidentifiable.**
  One identifiable parameter can use up one residual degree of freedom. An exactly determined
  model can still be locally identifiable: a D2h proton rectangle with one fixed length and a
  free aspect ratio has 3 coupling classes, 2 order parameters and joint rank 3 (round 63).
- **Some degeneracies are specific.** Proton-only regular benzene is one.
  - Every H–H distance scales with the proton-ring radius R_H, and a coupling goes as 1/r³. So
    the couplings depend only on S_zz / R_H³.
  - Changing R_H to R′_H leaves every prediction unchanged when S′_zz = S_zz (R′_H / R_H)³.
  - Fitting C–H with C–C fixed therefore rescales S_zz exactly (plan §8).
- **The rule.** Before any geometry parameter is called identifiable or not, a model-specific
  joint-rank calculation is required.
- **Later.** A separate step, **V1b (fitted geometry)**, can be selected once V0 has confirmed
  the data.

**Proposed steps** (each the size of a Phase 1 step, ending as Phase 1's steps did: tests, at
most two review rounds, a tag):

| Step | What it builds | What it must prove |
|---|---|---|
| **V1.1 Linear rigid fit** (core) | An explicit **k = 0 path** in `fit()`, with no dummy torsion. Its result contract covers empty geometry coordinates, no scan, basins or profiles, the covariance, the validity flags, the preview and serialization. The order parameters come from weighted linear least squares on the whitened design. The **estimable combinations** are the retained right-singular coordinates of the whitened design, each with variance 1/s_i², in the declared frame; null directions are reported as unidentified, with no error bars. Adequacy uses the exact fixed-design χ² with N − r degrees of freedom (r the rank). **With N − r = 0** (for example 1,3,5-trichlorobenzene) there is no adequacy p-value and no claim of adequacy, as the fitter already does (`p_value=None`). Admissibility stays a separate flag. **Interval assumptions, stated in the result:** fixed geometry, Gaussian errors with known covariance (independent errors when only a diagonal σ is supplied) and unconstrained linear estimation give exact Gaussian intervals for estimable combinations, even near the physical boundary. Enforcing admissibility, clipping, regularizing, or reporting nonlinear quantities (principal values and axes) changes the inference. Those cases need their own calibration, or report "interval not supported" | All synthetic estimands, equivalences and tolerances frozen before evaluation. Noiseless recovery for a **nonplanar rank-5**, a **planar rank-3** and a **collinear rank-1** fixture, built so the rank holds: for the planar one the plane is xy, and S_xx, S_yy, S_xy are estimable while S_xz, S_yz are not, with enough distinct directions measured. The rank decision is tested in both directions: it neither hides a real direction nor invents one. A **fixed-seed noisy regression**, separate from coverage. The M1 coverage protocol (1000 seeds, 64.5–72.1 %) on the supported intervals. The φ-path results (biphenyl gates, 8CB) unchanged |
| **V1.2 Symmetry and permutation classes** (core) | **Declared symmetry, stored with the project.** The point group with its axes, or the symmetry operations as matrices in the input frame, and a tolerance. **The medium is assumed achiral and uniaxial** (nematic or smectic A, like ZLI-1132 and 8CB). The assumption is stored with the project, and a chiral medium is refused in this release. In a chiral medium mirror operations are lost: a Cs solute can need five order parameters and a C2v solute three, and mirror-related sites can become distinct (Kumar, Vanakaras and Photinos, arXiv:1607.07014, §§4.1–4.3). Deriving the effective ordering symmetry from both molecule and medium is later work. **Order reductions in an achiral medium, with the frame on the symmetry axes:** a C_n axis with n ≥ 3 (D6h, D3h, C3v) leaves S_zz along it; D2h and C2v leave S_zz and S_xx − S_yy; C2, Cs and C2h leave three; C1 five. **Supported first:** C1, Cs, C2v, D2h, D3h and D6h, with **no fast internal motions** (methyl rotation and the like come later). **Permutation classes** come from the symmetry operations that survive in the medium (all of them, under the achiral assumption), as isotope-preserving atom bijections that map the geometry onto itself within the tolerance. Pair rows are compared **after** the order constraints and any declared averaging are applied. Chemical equivalence is kept distinct from magnetic equivalence. **N counts independent measurement information, never pair multiplicity:** one supplied estimate per class is the supported input. A symmetry copy of a coupling is not a new observation; independent repeat measurements of a class are not accepted in this release (aggregating them would mean propagating their uncertainty and keeping their within-class scatter for adequacy) | **Ideal benzene in D6h has one independent order parameter.** A declared symmetry the geometry does not have is refused. Relabelling and permuting both endpoints of every pair under the symmetry leave the fit unchanged. A rotated input frame gives the same predictions, and the same estimable subspace and covariance once transformed. Singular vectors and singular-coordinate values are **not** compared literally: their signs are arbitrary, repeated singular values let them rotate, and the five-component coordinates are not rotation-invariant. A declared chiral medium is refused. A molecule whose chemically equivalent sites are magnetically inequivalent is handled correctly. A symmetry copy never inflates N or ν. Proton-only benzene shows the scale degeneracy the plan describes |
| **V1.3 Application** | The model `rigid` without a torsion for imported geometry, with the symmetry declaration. Project schema v3 with a migration (D20), journal replay, readiness ("ready to fit" without a torsion), reports without φ, and a contract version bump | **Compatibility:** loading a migrated project and replaying its journal converge on the same **migrated** identity, and each historical hash is still checked under its original rules (the hash includes the schema version and the numerical context, so a migration changes it). Fixtures cover old project files, journals, compacted snapshots, stored runs, undo/redo and staleness. Existing biphenyl projects and their torsion fits behave exactly as before. A decision is recorded on how an old imported draft without a torsion is read. **Contract:** every new operation is in the registry snapshot and has a Python/HTTP parity test. A report states the estimable combinations and its interval assumptions |
| **V1.4 Browser and robot** | A Fit workspace without φ (no slider or landscape; a panel for the identifiable combinations). A Structure view for one-ring molecules. A robot tutorial (synthetic benzene or 1,4-dichlorobenzene from XYZ) and its browser test on three browsers | The robot tutorial and the page give the same run (the M3 comparison, fail-closed). The AI-readiness checks stay green |
| **V1.5 Verification report and exit** | One page per dataset: data, model, estimand, our result, the published result, the preregistered criterion, and the status labels (implementation; verification: *pending*, *synthetic-only*, *experimentally supported* or *unresolved failure*; holdout availability) | Every V0/V1 gate green. Each experimental result carries an honest label; an explained discrepancy is not counted as validation. At least one external user reproduces a Phase 2 dataset |

V0.1–V0.3 run beside V1.1–V1.2, since the core work needs no data. V0.3 must be done before
V1.5 opens any experimental result.

## What the measurements support

**Measured** (Phase 1 after M0; each can be recounted):

- **Calendar.** 23 tagged work steps from M1 step 1 (tag `m1-step1`, 2026-11-10) to B4 (tag
  `beta-b4`, 2026-11-17), 8 calendar days.
  - Counted with `git for-each-ref refs/tags --sort=creatordate`.
  - Not counted: the milestone markers (`*-complete`), `m1-step1-wip`, `v0.1.0b1` and
    `beta-draft`.
- **Review.** 50 independent review rounds (13–62), recorded in `docs/validation/`.
  - M1 step 1 went through six rounds (13–18). The two-round cap (the medium plan) was adopted
    on 2026-11-10, during that sequence, and every later step stayed within it.
  - The first round of almost every step was NOT READY.
- **Size.** About 29 600 inserted lines in `packages/` and `web/src`, product and tests
  (`git diff --shortstat m1-step1 beta-b4 -- packages web/src`).

**Inferred, not measured:** as after M0, writing the code did not seem to be the bottleneck. The
review records show most of each step's work in specifying it and in fixing what adversarial
review found. Without the owner's hours this cannot be confirmed. On that basis V0 + V1 is
about **8 steps**: 3 for V0, mostly research and owner time, and 5 for V1. V1.2 is the largest;
if it proves bigger than a Phase 1 step, it splits into order reductions, then permutation
classes.

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
