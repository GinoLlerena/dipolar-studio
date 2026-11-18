# Phase 2, first verification release (V0 + V1): a proposal

**Status: approved by the owner on 2026-11-18** ("follow the recommendations and start now"),
after review rounds 63–65. What the approval covers:

- **Decision 1, scope:** all parts approved — fixed geometry; an achiral, uniaxial medium; the
  point groups C1, Cs, C2v, D2h, D3h and D6h; no fast motions; per-atom isotope identity.
- **Decision 2, timing:** V0 and V1.0 start now.
- **Decision 3, data policy:** the 8CB default.
- **Decision 5:** the owner is the holdout custodian.
- **Decision 7, order:** V0 + V1 before Phase 3.

**Decided on 2026-11-18** ("proceed with the recommendations"):

- **Decision 4, transcription:** two independent AI transcriptions from the rendered pages,
  compared mechanically. The owner spot-checks them. This replaces plan §8's "the owner enters
  each value".
- **When V1 code starts:** now, on `main`. Beta fixes go to the `release/0.1` branch, cut from
  the `v0.1.0b1` tag.
- **The V1.0 design's D-1:** Phase 1 directories are left untouched, and projects carry over by
  their export file.

**Still open:**

- **Decision 6,** the external-reproduction path; it is needed before V1.5.
- **Library access** for the authors' geometries (Diehl & Niederberger 1973; Diehl & Khetrapal
  1968). Until then, the published-value comparisons stay *pending*.

Plan §8 says that after the beta, the owner selects and re-baselines the first verification
release, **V0 (benchmark corpus) plus V1 (rigid molecules from XYZ)**. This page proposes:

- what V0 and V1 contain;
- how they split into steps;
- what each step must prove;
- the decisions the owner needs to make.

It sets no dates (see [What the measurements support](#what-the-measurements-support)).

## Where Phase 1 left things

The beta (`v0.1.0b1`) fits one torsion and the order of a biphenyl-type molecule. What V1 can
reuse:

- **Imported geometry.** XYZ geometry is read with bond perception.
- **Order models.** Imported geometry already has two order models in the input frame:
  - `c1`, all five components;
  - `c2z`, three components. It *assumes* that z is a C2 axis but does not check this against
    the geometry.
- **Frame and rank diagnostics.** The frame contract; the inner (order) rank, the joint rank and
  the condition number.
- **Named null directions.** `fit()` already reports the unidentified and uncertain directions
  by name, and the app shows them.
- **The fit's outputs.** Admissibility of the order matrix, adequacy under the stated σ, and
  validity flags, each judged separately.
- **The search.** The fitter supports one or several geometry parameters: a grid for one, Sobol
  points for several, subject to the search's limits.
- **Couplings import.** The CSV reconciliation (D5) and the `multiplicity` and
  `equivalent_pairs` columns.
- **The application.** The application layer (operations, journal, undo, proposals, jobs, runs,
  reports), the browser app, the robot and the CI gates.

What it lacks for V1:

1. **A fit with no geometry parameter.**
   - The core's `Problem` already accepts zero geometry parameters (k = 0), and its inner linear
     solve works.
   - The top-level `fit()` does not: with k = 0 it raises `ValueError: zero-size array to
     reduction operation maximum` (checked on 2026-11-18, round 63).
   - The app refuses imported geometry until a torsion is declared (`science._problem_for`).
   - A rigid molecule with fixed geometry has no geometry parameter, so its fit is a weighted
     *linear* least-squares problem in the order parameters alone.
2. **Symmetry checked against the geometry.**
   - Today the only reductions are `c2z` and the template's bisector-diagonal model. Neither is
     validated as a point group of the imported molecule.
   - The equivalences of imported molecules come only from the user's `equivalent_pairs`
     column.
   - Atoms carry an element but no isotope identity (spins are ¹H only), so an isotopic
     substitution that breaks a symmetry cannot be expressed.
3. **Estimable combinations with uncertainty.**
   - A rank-deficient fit today names its null directions. But it is not "regular", so it gets
     no covariance and no adequacy p-value.
   - A planar molecule, for example, determines only the in-plane block. Its estimable
     combinations deserve errors, and the fit an adequacy test.
4. **The app's views.** The Fit workspace assumes φ (preview slider, χ² landscape), and so do the
   robot tutorials.

## V0: the benchmark corpus

V0 is mostly finding and checking data, not code. Its exit (plan §8):

- every selected extension has at least one experimental dataset or an explicit
  *synthetic-only* label;
- rights are documented before anything is published;
- no transcribed value is left unverified.

**What the candidates can test.** The counts below are symmetry counts. They hold only **if the
paper reports an independent value for each class**, which V0.1 must check; symmetry says
nothing about what a dataset contains. Each count was reproduced independently in rounds 63–65.

| Candidate (plan §8) | Symmetry-distinct H–H classes | Order parameters | ν, with fixed geometry | What it can test |
|---|---|---|---|---|
| Benzene (D6h) | 3 (ortho, meta, para) | 1 (S_zz) | 2 | S_zz, and the coupling ratios against the assumed geometry |
| 1,4-dichlorobenzene (D2h) | 3 (ortho, meta, para) | 2 (S_zz, S_xx − S_yy) | 1 | barely over-determined |
| 1,3,5-trichlorobenzene (D3h) | 1 (meta) | 1 | 0 | nothing beyond the scale: the fit is exactly determined |
| Fluorobenzene (C2v) | 6 | 2 | 4 | a proton-only fit, **if** the paper gives the H–H couplings separately; its H–F couplings are V4 |

So **V1's experimental comparisons may rest on few degrees of freedom**, and its main
verification will be synthetic (known answer). V0 should also look for at least one rigid
dataset with clearly more couplings than order parameters. If that search leads to ¹³C
satellites, they come back to the owner as a separate **V4** selection, not as part of V1.

**What a published comparison can show.**
- **The paper's own conventions.** Each comparison matches the paper's frame, weighting,
  correction conventions (vibrational and other) and estimand, condition by condition.
  Frames differ in practice: Yethiraj et al. put z normal to the ring, whereas a C2v
  implementation may call its in-plane twofold axis z.
- **The published geometry.** It is taken as input.
- **The errors.** The σ come with their provenance. Couplings from a joint spectral fit are
  correlated. Where the covariance is not available, or weights are assumed, the comparison and
  its uncertainty say so.
- **What agreement means.** Matching order parameters that the authors derived from the same
  couplings shows that **we reproduce their analysis**. That is not independent experimental
  support. The status label says which it is.
- **Disagreements** are reported and reviewed, never tuned away.

**Proposed steps:**

- **V0.1 Selection and access.** A written selection protocol, then a confirmation for each
  candidate: where the numbers are (main text, Supporting Information, a thesis), whether the
  table is complete, units, signs, conditions, σ and their provenance, the frame and
  conventions, and the rights basis.
  - **Status on 2026-11-18, from the round 65 reviewer; not yet checked by the author:**
    - the authors' copies of both papers are reachable (they were not from the author's
      machine);
    - Taggar et al. point to coupling tables in free Supporting Information, completeness not
      verified;
    - Yethiraj et al. (2004) describe extracting couplings and give order results in a figure,
      but no complete coupling table was found.
  - Some Supporting Information may need the owner's library access.
- **V0.2 Transcription and verification.** Each value is entered and cross-checked against the
  rendered source page (procedure: owner decision 4). On 2026-11-17 the beta walkthrough did this
  for Di Pietro's Table 3.1 (`docs/validation/beta-walkthrough-v0.1.0b1.md`). Each dataset gets a
  README (source, checksum, rights basis, approved channels, numbering map, conventions,
  estimand, published values).
- **The holdout rules,** all of plan §8's, with a custodian:
  - related observations (the same sample, the same paper series) are grouped and never split;
  - the group manifest is frozen;
  - **a custodian** (proposed: the owner) holds the holdout values, and a log records who or
    which agent has seen them;
  - the model and criteria are frozen before a holdout is opened;
  - an opened or exposed holdout becomes development or regression data;
  - the report says when no independent holdout remains.
- **V0.3 Preregistration.** The estimands, tolerances and agreement criteria for each
  experimental dataset are frozen and committed **before any experimental fit in any V1 step**.

V0 needs no change to the app and does not disturb the beta testers, so it can start at once.

## V1: rigid molecules from XYZ

**Scope proposed for V1** (each item an owner decision, below):

- **Fixed geometry only.** The imported geometry is the scale anchor (D12), and only the order
  parameters are fitted.
- **An achiral, uniaxial medium** (nematic or smectic A, like ZLI-1132 and 8CB). The assumption
  is stored with the project, and a chiral medium is refused.
  - In a chiral medium mirror operations are lost: a Cs solute can need five order parameters
    and a C2v solute three, and mirror-related sites can become distinct (Kumar, Vanakaras and
    Photinos, arXiv:1607.07014, §§4.1–4.3).
  - Deriving the effective ordering symmetry from both molecule and medium is later work.
- **Point groups supported first:** C1, Cs, C2v, D2h, D3h and D6h.
- **No fast internal motions.** Methyl rotation and similar motions come later.
- **Isotopes.** Each atom gets an isotope identity, defaulting to the most abundant isotope.
  An isotopic substitution can then split an orbit (benzene-d₁ is C2v, not D6h). Observations
  stay ¹H–¹H.

**Fitting geometry is deferred**, as a choice of scope; plan §8 makes it conditional, not
mandatory. Examples are a ring radius, or a C–H distance against a fixed C–C.

- **Why defer.** It adds a joint-rank analysis for each model and a geometry-parameter
  interface, and the candidate datasets are still unconfirmed.
- **Few degrees of freedom do not, by themselves, make a geometry parameter unidentifiable.**
  One identifiable parameter can use up one residual degree of freedom. An exactly determined
  model can still be locally identifiable: a D2h proton rectangle with one fixed length and a
  free aspect ratio has 3 coupling classes, 2 order parameters and joint rank 3 at a regular
  point (rounds 63 and 65).
- **Some degeneracies are specific.** Proton-only regular benzene is one:
  - every H–H distance scales with the proton-ring radius R_H, and a coupling goes as 1/r³, so
    the couplings depend only on S_zz / R_H³;
  - changing R_H to R′_H leaves every prediction unchanged when S′_zz = S_zz (R′_H / R_H)³;
  - fitting C–H with C–C fixed therefore rescales S_zz exactly (plan §8).
- **The rule.** Before any geometry parameter is called identifiable or not, a model-specific
  joint-rank calculation is required.
- **Later.** A separate step, **V1b (fitted geometry)**, can be selected once V0 has confirmed
  the data.

### The steps

Each step ends as Phase 1's steps did: tests, at most two review rounds, a tag. **All synthetic
estimands, equivalences and tolerances are frozen before they are evaluated.**

#### V1.0 Design review (before any code)

Plan §8 requires each extension to review these first:
- the observable and parameter schemas;
- the inference assumptions;
- resource budgets: symmetry matching on n atoms, covariance size, and how close an XYZ
  geometry must be to count as symmetric;
- the D19 outputs;
- snapshots, hashes and journal replay.

This step also records two early decisions:
- **old drafts:** how an old imported draft without a torsion is read;
- **replay across contexts:** whether the fit's numerical context changes. Replay today refuses
  a context mismatch before it checks the historical hash, so a change needs its own replay
  test.

**Gate:** a written design note, reviewed, before V1.1 starts.

#### V1.1 Linear rigid fit (core)

- **The k = 0 path.** An explicit path in `fit()`, with no dummy torsion. Its result contract
  covers empty geometry coordinates, no scan, basins or profiles, the covariance, the validity
  flags, the preview and serialization.
- **The estimate.** The order parameters come from weighted linear least squares on the whitened
  design.
- **The tensor basis.** Estimates and covariances are expressed in an **orthonormal tensor
  basis** (under the Frobenius inner product). The current five-component basis is not
  orthonormal, so a covariance in it does not transform like a tensor's.
- **Estimable combinations.** Each has a variance 1/s_i² from the retained singular directions.
  The null directions are reported as unidentified, with no error bars.
- **Structural rank versus numerical rank.**
  - **Structural rank** is exact by construction, for example a planar molecule (rank 3) or a
    declared symmetry.
  - **Numerical rank** is decided only by a cutoff on small singular values.
  - The two are reported separately. A weak but nonzero direction is flagged.
- **Adequacy.** The central χ² p-value with **N − r** degrees of freedom is given only when the
  rank is structural, or the reduced model is declared and frozen. When numerical truncation
  alone sets the rank, the signal in a dropped direction stays in the residual and the statistic
  is no longer central χ². Exact adequacy is then withheld, with the reason.
  - **With N − r = 0** (for example 1,3,5-trichlorobenzene) there is no p-value and no claim of
    adequacy, as the fitter already does (`p_value=None`).
- **Admissibility of a rank-deficient fit.**
  - The current flag tests the solver's minimum-norm completion. That depends on the frame,
    not on the data: in a rank-1 example (round 65), the same data passed in one frame and
    failed in another.
  - So when the tensor is not fully identified, V1 tests whether **any** completion consistent
    with the estimable part is physical, that is, whether (2S + I)/3 can be positive
    semidefinite. This is a small convex feasibility problem. Otherwise it reports
    admissibility as **undetermined**.
  - The unconstrained fit is kept, and any representative tensor shown is labelled as one.
- **Interval assumptions, stated in the result.** Exact Gaussian intervals for estimable
  combinations hold, even near the physical boundary, given:
  - fixed geometry;
  - Gaussian errors with known covariance (independent errors when only a diagonal σ is
    supplied);
  - unconstrained linear estimation.

  Enforcing admissibility, clipping, regularizing, or reporting nonlinear quantities (principal
  values and axes) changes the inference. Those cases need their own calibration, or report
  "interval not supported".

**What V1.1 must prove:**
- **Noiseless recovery** of the order parameters and predictions for three fixtures, each built
  so its rank holds:
  - a nonplanar rank-5 fixture;
  - a planar rank-3 fixture, with the plane xy and enough distinct directions: S_xx, S_yy and
    S_xy are estimable, S_xz and S_yz are not;
  - a collinear rank-1 fixture.
- **Rank, in both directions.** It neither hides a real direction nor invents one. An exact rank
  deficiency and a small nonzero singular value are tested separately.
- **Admissibility.** The completion test passes and fails on constructed cases. A rank-1 case
  gives the same answer in two frames.
- **A rotated input frame,** including a rank-deficient C1 case, gives the same predictions.
  Matched estimable linear functionals agree, with their coefficients transformed dually.
  Singular-coordinate labels and values are never compared literally: their signs are
  arbitrary, and repeated values let them rotate.
- **A fixed-seed noisy regression,** separate from coverage.
- **Coverage:** the M1 protocol (1000 seeds, 64.5–72.1 %) on the supported intervals.
- **Unchanged:** the φ-path results (the biphenyl gates and 8CB).

#### V1.2 Symmetry and permutation classes (core)

- **The declared symmetry,** stored with the project:
  - the point group with its axes, or its operations as matrices in the input frame;
  - a tolerance;
  - the medium assumption (achiral, uniaxial).
- **Validation.** A declared operation must map the geometry onto itself, as an
  **isotope-preserving atom bijection** within the tolerance.
- **Order reductions** in an achiral medium, with the frame on the symmetry axes:

  | Point groups | Order parameters left |
  |---|---|
  | C_n with n ≥ 3 (D6h, D3h, C3v) | 1: S_zz along the axis (S_xx = S_yy = −S_zz/2) |
  | D2h, C2v | 2: S_zz and S_xx − S_yy |
  | C2, Cs, C2h | 3 |
  | C1 | 5 |

- **Orbits.** Site orbits and unordered-pair orbits come from the same validated group action.
  Pair rows are compared **after** the order constraints are applied.
- **Equivalence.** Chemical equivalence is kept distinct from magnetic equivalence.
- **Counting N.** N counts independent measurement information, never pair multiplicity:
  - one supplied estimate per pair orbit is the supported input;
  - a symmetry copy of a coupling is not a new observation;
  - independent repeat measurements of an orbit are not accepted in this release. Aggregating
    them would mean propagating their uncertainty and keeping their within-orbit scatter for
    adequacy.

**What V1.2 must prove:**
- **Recovery.** Frozen noiseless recovery of the known order parameters and the predictions
  for each supported group's synthetic fixture. **Ideal benzene in D6h** recovers its single
  S_zz.
- **Refusals.** A declared symmetry the geometry does not have is refused, and so is a chiral
  medium.
- **Invariance.** Relabelling, and permuting both endpoints of every pair under the symmetry,
  leave the fit unchanged.
- **Isotopes.** A substitution splits the orbit it should (benzene-d₁), with chemical and
  magnetic equivalence kept apart.
- **Counting.** A symmetry copy never inflates N or ν.
- **Benzene's degeneracy.** Proton-only benzene shows the scale degeneracy described above.
- **Resources.** The bounds set in V1.0 hold.

**Checkpoint.** If V1.2 proves bigger than a Phase 1 step, it splits: order reductions first,
then orbits and isotopes. This is re-baselined before V1.2 starts.

#### V1.3 Application

- **What it builds:**
  - the model `rigid` without a torsion for imported geometry, with the symmetry, medium and
    isotope declarations;
  - project schema v3 with a migration (D20);
  - journal replay;
  - readiness: "ready to fit" without a torsion;
  - reports without φ that state the estimable combinations and the interval assumptions;
  - a contract version bump.
- **Compatibility gate:**
  - loading a migrated project and replaying its journal converge on the same **migrated**
    identity;
  - each historical hash is still checked under its original rules, since the hash includes
    the schema version and the numerical context;
  - fixtures cover old project files, journals, compacted snapshots, stored runs, undo/redo and
    staleness;
  - existing biphenyl projects and their torsion fits behave exactly as before;
  - old torsion-less drafts follow the V1.0 decision.
- **Contract gate:** every new operation is in the registry snapshot and has a Python/HTTP
  parity test.

#### V1.4 Browser and robot

- **What it builds:**
  - a Fit workspace without φ: no slider or landscape, and a panel for the estimable
    combinations;
  - a Structure view for one-ring molecules;
  - a robot tutorial (synthetic benzene or 1,4-dichlorobenzene from XYZ), with its browser test
    on three browsers.
- **Gate:** the robot tutorial and the page give the same run (the M3 comparison, fail-closed).
  The AI-readiness checks stay green.

#### V1.5 Verification report and exit

- **The report:** one page per dataset, giving:
  - the data, model and estimand;
  - our result and the published one;
  - the preregistered criterion;
  - the status labels (below).
- **The status labels:**
  - implementation;
  - verification: *pending*, *synthetic-only*, *experimentally supported* or *unresolved
    failure*;
  - holdout availability;
  - whether a comparison is a reproduction of the published analysis or independent support.
- **The exit:**
  - every V0/V1 gate is green;
  - every discrepancy has a **reviewed entry in its dataset README** (estimand, geometry,
    vibrational corrections, solvent);
  - an explained discrepancy is not counted as validation;
  - at least one external user reproduces a Phase 2 dataset, by the path chosen in owner
    decision 6.

**Order of work.** V0.1–V0.3 run beside V1.0–V1.2, since the core work needs no data. V0.3 must
be done before any V1 step fits an experimental dataset.

## What the measurements support

**Measured** (Phase 1 after M0; each can be recounted):

- **Calendar.** 23 tagged work steps from M1 step 1 (tag `m1-step1`, 2026-11-10) to B4 (tag
  `beta-b4`, 2026-11-17), 8 calendar days: 5 in M1, 6 in M2, 8 in M3 and 4 in the beta.
  - Counted with `git for-each-ref refs/tags --sort=creatordate`.
  - Not counted: the milestone markers (`*-complete`), `m1-step1-wip`, `v0.1.0b1` and
    `beta-draft`.
- **Review.** 50 independent review rounds (13–62), recorded in `docs/validation/`.
  - M1 step 1 went through six rounds (13–18). The two-round cap (the medium plan) was adopted
    on 2026-11-10, during that sequence, and every later step stayed within it.
  - The first round of almost every step was NOT READY.
- **Size.** 29 634 inserted lines in `packages/` and `web/src`, product and tests
  (`git diff --shortstat m1-step1 beta-b4 -- packages web/src`).

**Inferred, not measured:**
- As after M0, writing the code did not seem to be the bottleneck. The review records show most
  of each step's work in specifying it and fixing what adversarial review found. Without the
  owner's hours this cannot be confirmed.
- These counts **do not size** symmetry validation or the schema migration, which have no Phase 1
  precedent.

**On that basis:** V0 + V1 is about **9–10 steps**:
- 3 for V0, mostly research and owner time;
- 6 for V1, from V1.0 to V1.5;
- one more if V1.2 splits at its checkpoint.

**The owner's hours are still not logged** (the tables in `docs/STATUS.md` are empty), so neither
the owner's effort nor a calendar estimate can be given. Plan §8 also ties the 1.0 date estimate
to after the beta.

## Decisions for the owner

1. **Scope of V1.** Each part can be approved separately. *All recommended.*
   - fixed geometry only, with fitted geometry deferred to a separately selected V1b;
   - an achiral, uniaxial medium only, with a chiral medium refused;
   - the point groups C1, Cs, C2v, D2h, D3h and D6h;
   - no fast internal motions;
   - per-atom isotope identity in schema v3, with observations staying ¹H–¹H. The narrower
     alternative: no isotopic substitution at all, in which case V1.2's isotope gate is dropped
     and the plan's "declared isotopic structure" is deferred.
2. **Timing.**
   - V0 (research, no code) and V1.0 (the design review) can start **now**, without affecting
     the beta testers. *Recommended.*
   - V1 code either waits for the beta exit, or, if testers are slow, starts on `main` while
     beta fixes go to a `release/0.1` maintenance branch. A tester's fix then never ships half a
     V1.
3. **Data policy, per dataset: the approved channels.**
   - `export-ignore` keeps data out of the release **archives** only. It does not affect the
     public repository, its Git history, reports a user shares, or packages.
   - The 8CB precedent: kept in the public repository for validation, removable on request,
     excluded from release archives and packages.
   - Proposal: the same default, unless a dataset's rights say otherwise. Each README records
     its channels.
4. **Transcription.**
   - Plan §8 says the owner enters each value and an independent AI cross-checks it against the
     rendered page.
   - An alternative, to save the owner's time: two independent AI transcriptions from the
     rendered page, compared mechanically, with the owner spot-checking.
5. **Access and custody.**
   - Some Supporting Information may need the owner's library access.
   - Proposed: the owner is the holdout custodian.
6. **The external reproduction.**
   - Plan §8 asks that at least one external user reproduce a Phase 2 dataset.
   - The owner chooses which dataset, and the path: a transcription from the publication, as
     for 8CB, or the repository copy.
   - The owner also decides whether a synthetic case counts if no suitable experimental dataset
     can be shared.
7. **Alternative.** Plan §8 lets Phase 3 (AI integration) start from Phase 1 instead. This
   proposal follows the plan's default order: V0 + V1 first.

Still open from before: the hours log and the thesis PDF. The thesis matters for V3 and V6, not
for V0 + V1.
