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

## Round 57: NOT READY (three A, three B), on commit 452a1ba

The reviewer's run: 863 Python (one scratch-copy failure that passed on rerun), Ruff, mypy, the
contract, 65 web unit and 111 browser tests; PR CI green. For a fixed software version the
snapshot-based determinism held, and excluding staleness and the current project was judged right;
locale and key-order probes, escaping, CSV precision, newlines and quotes in labels passed, and
removing the escaping or the formula guard failed the tests. All six findings were reproduced.

1. **(A) Rounding hid supported intervals and uncertainty.** With the observations set to a fit's
   own predictions and σ = 1e-5 Hz, the φ interval [36.9850289, 36.9850292] showed its estimate and
   both endpoints as 36.985, and its standard error as 1.63954e−07. **Fix:** a parameter's value is
   shown to two significant digits of its standard error, the standard error to two significant
   digits; an interval's estimate and endpoints share a precision from its narrower half-width,
   refined until the three differ. Test: the reviewer's case, three distinct numbers each within its
   displayed precision of the stored value, φ no coarser than its σ.
2. **(A) "Adequate (the model explains the data within σ)" overstated the flag,** which is the
   frozen policy p ≥ 0.001 (χ² = 29.4 with ν = 11, p = 0.002, read "yes"). **Fix:** "Adequate (p ≥
   0.001 under the stated σ)", from `reporting.ADEQUATE_P_MIN`.
3. **(A) "Regular (identifiable)" conflated two things:** an imported geometry with φ at a bound of
   [−30°, 0°] had full ranks and no undetermined direction, yet read "identifiable: no". **Fix:**
   "Regular optimum (converged, resolved, interior, full rank)", with a note that standard errors,
   ν and intervals need it while identifiability is the ranks and the undetermined directions.
   Test: the wording, and every validity value shown.
4. **(B) Content and clock regressions escaped the tests** (removing the Validity and Intervals
   sections, or adding today's date, passed). **Fix:** the tests read the Validity and Intervals
   sections value by value, and render a run twice with the clock moved by a year
   (`time.time`, `datetime.datetime.now`, `datetime.date.today`). Mutants adding today's date or
   the current time, ignoring the uncertainty's precision, hiding the Validity section or
   unlabelling a singular condition number each fail.
5. **(B) "The same report" needed its software qualification** (another installed version words
   the same run differently). **Fix:** the guide and the report's footer say "with the same
   version / software".
6. **(B) An infinite condition number (null on the wire) showed as missing.** **Fix:** with a
   deficient inner rank it reads "∞ (singular)", otherwise "not computed". Test: a one-coupling
   fit (inner rank 1 of 2).

**After the fixes:** 868 Python tests; the report's browser test on the three browsers.
