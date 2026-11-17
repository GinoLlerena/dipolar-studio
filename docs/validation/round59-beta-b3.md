# Validation rounds 59–60: beta step B3 (executed notebooks)

Reviewer: GPT-6.1-Sol (Codex, reasoning effort high), independent of the implementation.
Under the medium plan there are at most two rounds per step. Class (A) findings block; class (B)
findings are documented.

The beta release's steps are in [round55-beta-b1.md](round55-beta-b1.md). B3 delivers the plan's
"docs with executed notebooks" (03 §8, the beta release), using the Python API of B1 and the
report of B2.

## What step B3 delivers

- **Three notebooks**, committed with their outputs in `docs/notebooks/` (with a README), each
  driving the same registry operations as the browser app through `dipolar_app.api.Studio`, and
  each checking its own results with `assert`:
  1. **A first fit** (the synthetic biphenyl, known answer φ = 37°): the project, a preview, the
     landscape, a fit with profile intervals, and the report. It checks a regular, adequate fit
     within three standard errors of 37°, and says whether this realization's 68.3 % interval
     covers 37° (it does not: φ = 36.985 ± 0.008°, 1.8 standard errors away; such intervals miss
     the truth in about a third of realizations, which M1's gate (c) calibrated).
  2. **Your own data**: the tutorial XYZ and couplings files through import, reconciliation, a
     confirmed mapping, the torsion, the model (rigid, c2z, input frame) and a fit (−36.988°).
  3. **Reproducing biphenyl in 8CB from your own transcription** (the owner's choice: users bring
     the data): the user transcribes Di Pietro (2013), Table 3.1 at T_red = 0.930, into a CSV, with
     the thesis-label → proton-pair table given in the notebook; the notebook checks the 12 pairs,
     fits the four-site jump unweighted (σ = 1 Hz) and weighted (the transcribed σ), and compares
     with the frozen reference fits within a transcription's tolerance (φ 1e-3°, S 1e-5); the
     weighted fit must be flagged inadequate. The unweighted fit's χ², p-value and adequacy are
     said to have no statistical meaning.
- **The first 8CB reproduction through the app.** The M1 gates fitted 8CB on the core; through the
  app (open the template, reconcile and import the 12 couplings, set the jump model, fit) both
  configurations equal the frozen fits (φ 32.932075° and 32.974574°; S_zz, Δ, χ² and N equal to
  the printed digits).
- **`tools/notebooks/`**: `build.py` defines the notebooks' cells (the source of truth);
  `run.py --write` builds, executes and saves them with outputs; `run.py --check`, a new step of
  the CI "Python" job, fails if a committed notebook differs from `build.py`, was committed
  without outputs, or no longer runs, and checks the 8CB notebook's typed reference values
  against `datasets/biphenyl-8CB-dipietro2013/expected/T0.930.json`. The 8CB notebook runs on a
  transcription made from the repository's validation copy, and is skipped if that copy is
  removed (it is removable on request); no temporary path is left in the saved outputs.
- `nbformat`, `nbclient` and `ipykernel` join the development dependencies (not the packages').
- Links from the README and the user guide.

## Before review

- **Found by the notebooks' own checks:** the first notebook's claim that the interval would
  contain 37° was false for this fixture (see above); the text and the check now say what the
  calibration promises. The 8CB thesis-label table, first typed by hand, did not match the data;
  it is now the repository's mapping, and the notebook checks the transcribed pairs against it.
- **Mutation checks** (each makes `run.py --check` fail): a committed notebook edited by hand; a
  typed reference value off by 0.01°.

**Baseline (before review):** 870 Python (`-m "not slow"`), Ruff, mypy, the contract; the three
notebooks executed by `run.py --check`. Web code is unchanged.
