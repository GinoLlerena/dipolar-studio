# UX research — Dipolar Studio

Panel input from UX research and product strategy, 2026-11-07.
This builds on `docs/legacy/01-legacy-analysis.md` and `02-bug-report.md`. Bug IDs (Bxx) refer to that report.

The core claim of this document: **the product is a fit, not a molecule editor.** Users come for one answer: *which conformations and order matrices agree with my couplings, and how sure am I?* Every decision below should shorten the path to that answer and make it checkable.

## 1. Personas and jobs-to-be-done

**P1 — Dr. Elena, experimental NMR spectroscopist (primary).** She runs ¹H/¹⁹F/²H spectra of solutes in nematics (ZLI-1132, Phase IV) and arrives with an analyzed list of D_ij ± σ. Expert in the physics, impatient with software.
- *When* I have assigned couplings, *I want* the geometries (e.g. biphenyl twist) and order parameters consistent with them, *so that* I can publish a defensible number with error bars.
- *When* a referee asks "how sensitive is φ to r_CH?", *I want* to answer in an hour, not rebuild a project.

**P2 — Tomás, grad student (most frequent user, highest risk).** He is learning what a Saupe matrix is while using the tool.
- *When* I set up my first fit, *I want* the tool to block physically meaningless setups (a coupling with no geometric pair, a zero increment, wrong symmetry), *so that* I don't spend weeks on a wrong result (B08: the default tolerance accepts 1000% errors).

**P3 — Priya, computational chemist / scripter.** She tests MD or DFT conformer ensembles against experimental couplings.
- *When* I have 500 conformers, *I want* to score each (or a weighted ensemble) from Python or the CLI, *so that* it runs in a notebook or on a cluster.
- *When* I publish, *I want* a plain-text project and a pinned engine version so reviewers can rerun it.

**P4 — Prof. Ruiz, PI / reviewer (secondary).** *When* a student shows me a fit, *I want* a one-page report of the inputs, assumptions, residuals and uncertainty, *so that* I can trust it without repeating it.

## 2. Pain points in the legacy workflow

1. **About 50 modal dialogs, with no overview.** Bonds, angles, axes, couplings, parameters and tensor setup each live in a separate property sheet behind fragment-specific menus (`Anillo Fenil → Ángulos → Internos`). No screen shows "what am I fitting, against what, with which freedoms"; the model exists only in the user's head.
2. **Linking by string label.** Couplings reference spins as `"H1, H2"`, parameters bind by typed labels, and the dihedral is found through the magic label `"Dihedral"`. A mistyped, reversed (B25) or mis-parsed (B24) label silently falls back to the origin (B11) or a singular system (B07). The most dangerous defect: **errors of reference look like scientific results.**
3. **Binary result files.** Results go to `.par/.int/.ten/.bin` raw struct dumps. They can't be opened in a spreadsheet, plotted or diffed, and the integrity check marks a file corrupt just because it was read (B26). Bond-length bindings are lost on save (B19).
4. **Binary accept/reject plus top 25.** A grid point "fits" only if *every* coupling falls inside a tolerance, and the user sees only the 25 best points by MAD. There is no χ², no weighting by σ, no landscape and no sense of how flat the minimum is. The order matrix comes from 2–3 hand-picked couplings, so the answer depends on that choice, invisibly.
5. **Cascade delete.** Deleting a fragment deletes every *later* fragment, leaves orphan couplings and duplicate names (B29), and can crash on save (B17).
6. **No undo.** `Editar → Deshacer` is in the menu but has no handler. With item 5, one click destroys an afternoon's setup.
7. **No import.** No structure formats (PDB/XYZ/SDF), no CSV for couplings, only three hard-coded fragments and H/D/F spins. Every project starts by re-typing data the user already has digitally.
8. **Blind, blocking sweeps.** The UI freezes, can loop forever (B09), and only then reveals whether anything fit.
9. **Wrong units.** Couplings in kHz are labelled "mHz"; bond lengths are reported in "Grados" (B31).

## 3. Target end-to-end journey

★ = moment that matters (a point where users either gain trust or abandon the tool).

1. **Start from data, not a blank canvas.** Import a structure (XYZ/SDF/PDB, or a template such as "biphenyl, D2") and a coupling table (CSV: `spin_i, spin_j, D_obs, σ, unit`).
2. ★ **Assignment check.** Coupling rows are matched to spins (by label, index, or clicking two atoms in 3D) in a reconciliation table of matched, ambiguous and unmatched rows. Unmatched rows must be fixed or excluded before continuing. *This is where the legacy app silently failed.*
3. **Declare freedoms.** Click a dihedral, bond or angle in 3D → "make variable", with a proposed range and step in units. Symmetry is suggested from the structure and confirmed by the user.
4. ★ **Live preview before any sweep.** At the current geometry, the order matrix is solved by weighted least squares over *all* couplings, and predicted vs. observed values appear immediately. Dragging the dihedral slider updates residuals in under 100 ms, so intuition comes before CPU time.
5. **Explore.** 1D/2D scan or global search plus local refinement, with streaming results, cancel and resume.
6. ★ **Understand the fit.** χ² landscape, confidence region, per-coupling residuals and leave-one-out influence, principal order parameters with uncertainties, and the principal-axis frame drawn on the molecule.
7. **Compare models.** Duplicate a model ("rigid" vs "two-site jump", D2 vs none) and compare by χ²_red and AIC/BIC.
8. ★ **Publish.** Report (PDF/HTML), CSV tables, SVG figures, a draft Methods paragraph, and a plain-text project bundle with engine version, inputs and run log.

## 4. Information architecture

Four workspaces, as tabs that all share one model and one selection:

| Workspace | Purpose | Primary view |
|---|---|---|
| **Structure** | Geometry, spins, variable parameters, symmetry | 3D viewer + structure tree + inspector |
| **Data** | Observed couplings, assignment, uncertainties, conditions (solvent, T, field) | Coupling table + spectrum-style stick plot |
| **Fit** | Models, solver settings, runs | Live residual panel + landscape plots + run queue |
| **Report** | Results, comparison, export | Composable report preview |

A persistent **Project panel** lists models and runs; a **Validation tray** shows blocking issues.

**Objects (stable IDs; display names are cosmetic):**
- **Molecule**: atoms, bonds, rigid fragments, frame definition.
- **Spin**: atom + isotope (¹H, ²H, ¹⁹F, ¹³C, …), optional equivalence group. Never a free-text label.
- **Coupling**: D_ij (value, σ, unit, sign known or not) linked to spin *IDs*; may average several geometric pairs (the legacy "component" concept, made an explicit *averaging rule*).
- **Parameter**: a degree of freedom bound by reference to a geometric element; value, range/step or prior, unit, state (fixed, scanned, fitted).
- **Model**: Molecule + Couplings + Parameters + symmetry + motional model + solver settings. Duplicable and diffable.
- **Run**: immutable execution of a Model (inputs hash, engine version, seed, log).
- **Result**: read-only output of a Run (best fit, covariance, landscape, order matrix and frame, residuals).

## 5. UX principles for this domain

1. **Live feedback beats batch.** Edits that change predictions update residuals in under 100 ms. Sweeps confirm; they don't discover.
2. **Provenance by construction.** Every number can answer "where did you come from?". Projects are plain text (TOML/JSON), git-diffable; Runs are immutable; Results are re-derived, never edited.
3. **Progressive disclosure.** Default path: template → import couplings → one dihedral → fit. The ρ distortion model, custom averaging, K constants and solver internals sit behind "Advanced" in the inspector, not in separate dialogs.
4. **Error prevention over error messages.** Pick by ID from 3D or a list, never type strings. Delete shows dependents and offers detach or delete. Unlimited undo/redo. Ranges are validated (step > 0, point count shown) before a run.
5. **Units everywhere.** Every field carries a unit (kHz/Hz, Å/pm, °/rad) and converts on input ("108 pm" is accepted). Export column headers include units.
6. **Explainable fits.** Never show a "best" without context: per-coupling residuals, the landscape, the confidence region, and degeneracy warnings ("Sxy and φ are 0.97 correlated"). χ² weighted by σ_D replaces the binary tolerance, which survives only as a visual band.
7. **Honest about assumptions.** Reports always state symmetry, fixed geometry, motional model and the sign convention for D, and flag order matrices that are not physically admissible (eigenvalues outside [−½, 1]).
8. **The GUI is a client of the engine.** Everything is also reachable from Python and the CLI with the same project file.

## 6. Prioritized features

**MVP: replaces the thesis workflow correctly**
- XYZ/SDF import + templates (phenyl, biphenyl, branched): no more re-entering geometry.
- CSV coupling import with reconciliation table: kills the #1 source of silent errors.
- ID-based spins/couplings/parameters picked in 3D: removes the string-label bug class.
- Weighted least-squares order matrix over all couplings (D4/D2/none): no dependence on hand-picked couplings.
- 1D/2D scan with χ² landscape and per-coupling residuals: the core "understand the fit" moment.
- Live residual preview: catches setup errors before any sweep.
- Undo/redo and dependency-aware delete: removes the fear of editing.
- Plain-text project, CSV/JSON export, units everywhere: provenance and portability.
- Python API + CLI on the same engine: P3 from day one; doubles as the regression harness.
- Best-effort legacy `.prj` importer with validation report: keeps the thesis data alive.

**v1: makes it publishable and teachable**
- Global search + Levenberg–Marquardt refinement with covariance: real error bars instead of a top-25 list.
- Model comparison (χ²_red, AIC/BIC): answers "rigid vs. flexible?" directly.
- Motional averaging models (jumps, two-site, weighted rotors): the "component" idea made explicit.
- One-click PDF/HTML report, Methods paragraph, SVG figures: the P4 deliverable.
- Principal frame drawn on the molecule: makes the Saupe matrix tangible for P2.
- Symmetry auto-detection: prevents mismatched symmetry.
- Sensitivity panel (leave-one-out, r_CH ± 0.01 Å): the referee question in minutes.

**Later: widens the audience**
- MD/DFT ensemble scoring (fitted or MaxEnt weights): P3's main job.
- Spectrum simulation from fitted D, J and shifts, overlaid on the measured spectrum: sanity check against raw data.
- ¹³C/¹⁵N and weak-alignment RDC conventions (Q-factor): opens the biomolecular community.
- NMR-STAR and RDC-format interop: fits existing pipelines.
- Web report viewer: reviewers inspect results without installing anything.

## 7. Research and validation plan

**Recruit (n ≈ 10–12):** 4 liquid-crystal NMR spectroscopists (the owner's network and authors of recent papers on oriented solutes), 4 grad students or postdocs, 2–3 computational chemists, and 1–2 PIs.

**Phase 0 — contextual inquiry (weeks 1–3).** 60-minute sessions in which participants walk through their *last real* analysis: files, tools (spreadsheets? in-house Fortran?), copy-paste steps, and how they report uncertainty. Collect 3–5 anonymized datasets as benchmarks.

**Phase 1 — concept tests (weeks 3–5).** Clickable prototype of the Data and Fit workspaces. Tasks: import couplings, resolve 2 seeded ambiguous assignments, make the inter-ring dihedral variable, report φ ± σ from the landscape. Think-aloud.

**Phase 2 — MVP benchmark (weeks 8–12).** Run the MVP on the benchmarks and the owner's thesis molecules, and compare with published values and with a bug-fixed legacy engine (B01–B18). Novices get the same tasks without training.

**Phase 3 — diary study (4 weeks)** with 3–4 groups on live projects; weekly check-ins plus opt-in, local-only usage logs.

**Success metrics**

| Metric | Target |
|---|---|
| Coupling table → first fitted result (P1, installed) | ≤ 15 min (legacy baseline measured in Phase 0) |
| Seeded assignment errors that reach a Run | 0 |
| Novices report φ ± σ correctly without help | ≥ 80% |
| Users who can explain *why* the best fit wins | ≥ 70% |
| Exported bundle rerun on another OS | Agrees to 1e-9 relative |
| Benchmark agreement with published values | Within reported uncertainty, every case |
| SUS after Phase 3 | ≥ 75 |
| Adoption | ≥ 3 external groups within 6 months of v1; ≥ 1 citation within 18 months |

**Pivot triggers.** If Phase 0 shows most users already script their fits, ship the Python API and report first and keep the GUI thin. If assignment happens *upstream* in spectral-analysis tools, build importers for them before our own 3D picking.
