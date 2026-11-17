# Validation rounds 57–58: beta step B2 (the summary report)

Reviewer: GPT-6.1-Sol (Codex, reasoning effort high), independent of the implementation.
Under the medium plan there are at most two rounds per step. Class (A) findings block; class (B)
findings are documented.

The beta release's steps are in [round55-beta-b1.md](round55-beta-b1.md). B2 delivers the plan's
"deterministic HTML/CSV summary" of a run (03 §4, Phase 1 scope).

## What step B2 delivers

- **`run.report`** (a query, any tier; contract 0.10.0): for one run, a self-contained **HTML
  page** and a **CSV** of the per-coupling table, with the report's format
  (`dipolar-report.1`) and a file name stem.
  - **Deterministic:** rendered from the run's record and its stored result only, never the current
    project or the clock (`dipolar_app/report.py`). The same run gives the same bytes, also after
    the project is reopened from its journal; the report names the software's version.
  - **What it says:** the fit's statement and estimand; the parameters with standard errors; χ²,
    N, free parameters, ν, the p-value, adequacy, the RMS residual; every validity flag, ranks,
    condition number, parameters at a bound, undetermined directions; the interval policy and the
    intervals; the model and torsion domain; the basins; every coupling (observed, σ, calculated,
    residual, residual/σ); and the provenance: run, job, owner, creation time, science revision and
    hash, input hash, result hash, fit version, numerical context, software, report format.
  - **Safe to open:** no script, no external resource; every string escaped. The CSV keeps full
    precision (Python's shortest round-trip form of each number) and quotes a text cell that a
    spreadsheet would run as a formula (one starting with =, +, -, @, tab or CR).
  - It reuses `run.get`'s verified read of the stored result (`_stored_run`): an unknown run is
    ID_NOT_FOUND, a damaged result INTERNAL.
- **The page:** the run panel in the Fit tab has "Download report" (`<stem>.html`) and "Couplings
  CSV" (`<stem>.csv`).
- **The user guide** has a "Reports" section.
- The cross-adapter contract sequence includes `run.report` (its HTML compared with the run's
  creation time masked: each adapter's session makes its own run).

## Before review

- **Driving it:** a report of the synthetic example read as text showed the intervals table
  naming each interval by its kind ("68.3% one-parameter…") instead of its parameter; fixed (the
  kind is a caption).
- **Tests:** `packages/dipolar-app/tests/test_app_report.py`: the same run gives the same report
  after a model change (the run stale) and after reopening the project; the report contains the
  run's identifiers, hashes, fit version, estimand, statement, software and format, φ, every
  coupling's label, no script and no external reference; the CSV has every coupling with exactly
  the stored values; hostile spin labels on an imported project (`<img src=x onerror=…>`,
  `=HYPERLINK(1)`) are escaped in the HTML and quoted in the CSV; an unknown run and a damaged
  result are refused. `web/e2e/report.spec.ts`: on each browser, both downloads equal the server's
  report byte for byte, with the expected file names.
- **Mutation checks** (each makes a test fail): no HTML escaping; no formula guard.
- **Also:** `tutorial.spec.ts` now shows the robot's own error when the robot fails (one failure
  on Firefox under load, with the Python suite running alongside, showed only the command line;
  three repetitions alone passed).

**Baseline (before review):** 864 Python (`-m "not slow"`), 65 web unit and 111 browser tests
(37 × 3), TypeScript, mypy, Ruff, the generated contract (0.10.0), projection parity.
