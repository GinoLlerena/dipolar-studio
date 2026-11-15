# Validation rounds 51–52: M3 step 4b (the robot tutorial, performance)

Reviewer: GPT-6.1-Sol (Codex, reasoning effort high), independent of the implementation.
Under the medium plan there are at most two rounds per step. Class (A) findings block; class (B)
findings are documented.

M3 step 4 was done in two halves: **4a** (rounds 49–50) delivered the browser suite and the
latency targets; **4b** (this one) the robot tutorial, large projects, and the two class-(B)
items left for it (rounds 47 and 49).

## What the step delivers

- **The robot tutorial** (04 §7, "Robot user": *the final project and results equal those of the
  UI path*). `tools/robot/robot.py --scenario tutorial --xyz F --csv F`, standard library only,
  under `python -I`, over HTTP registry calls only:
  create the project from an XYZ file → reconcile the couplings file → confirm the mapping (the
  file's labels to the imported protons, by the atom names in the XYZ comment line) → check the
  diff is complete → import exactly that diff → bind the torsion (C2–C1–C1'–C2') → set the model
  (rigid, c2z, input frame, φ domain [−90°, 0°]) → check readiness → preview → fit with profile
  intervals → select the coupling with the largest |normalized residual| → check the rendered SVG
  shows it → export. Its inputs come from `datasets/biphenyl-synthetic/tutorial_xyz.py` (the
  generator's own geometry as a user's file: element symbols only; and the 14 measured values
  without the D2 symmetry classes, which an imported geometry under c2z or c1 rightly refuses).
  Result: τ = −36.99° (φ = 37° in the template's convention, IUPAC τ = −φ), χ² 12.4 with ν 10,
  every interval supported, worst coupling at −1.94σ, about 7 s.
- **The same tutorial through the page** (`web/e2e/tutorial.spec.ts`): the XYZ and CSV through the
  Data tab's file buttons, the mapping chosen in its selects, the torsion and model in their
  fields, the fit with intervals, the worst row selected in the residual table, the Structure view
  showing it, and the export downloaded. Then the robot runs on its own server, and the test
  compares: the science hash; the exported project (deep equality); the selected coupling's label;
  θ, the order parameters, their standard errors and χ² to a relative 1e-9, ν exactly; every
  interval to 1e-9. On Chromium, Firefox and WebKit.
- **Large projects.**
  - **Tables render only the rows in view** above 400 rows (`limits.ts` `rowWindow`,
    `common.tsx` `useRowWindow` and `Spacer`): the Data tab's couplings, the Fit tab's residuals,
    the Structure tab's residual table. The scroll height still spans every row; the header stays
    in place.
  - **Drawing is bounded:** the Structure view draws at most 2 000 arcs and the obs/calc plot
    2 000 points (`mostRelevant`): everything selected or highlighted, then the largest |normalized
    residual|; a note says how many of how many are drawn, and the table lists them all.
  - **Values derived from a project are computed once per project** (`ByIdentity`, keyed by the
    immutable project's identity and, for the hashes, the numerical context): the science and
    content hashes and the problem `problem_for` builds. At 45 000 couplings they cost 0.6 s and
    0.85 s on every call before.
  - **Measured** (i7-8750H; `tools/bench/large_project.py --protons 300`: 44 850 couplings, the
    most a 1 MiB CSV holds):

    | | before | after |
    |---|---|---|
    | Data tab shown | 14 s | 0.2–0.6 s |
    | Structure tab shown | > 15 s | 0.4 s |
    | Fit tab shown | 48 s | about 15 s (waiting for the server) |
    | `fit.landscape` | 181 samples, about 14 s | 22 samples, 0.9 s |

- **A workload limit for the landscape (round 47 B).** A landscape costs samples × observations;
  `LANDSCAPE_WORK` = 10⁶ (about 2 s on the named hardware whatever the project's size). By default
  it takes as many samples as the limit allows, at most 181 (the beta fixture keeps its 181); an
  explicit `points` above the limit is refused with QUOTA_EXCEEDED, naming the field and the
  maximum. Contract 0.9.0.
- **Shutdown no longer waits for open change feeds (round 49 B).** Each feed waited in a worker
  thread for up to one heartbeat (15 s), and uvicorn's shutdown waited for them. The server now
  closes the feeds when asked to exit (`Session.close_feeds`, from uvicorn's exit handler): every
  waiting feed returns at once and its stream ends; the page reconnects to the next server.

## Before review: found by the suite and by driving the page

- **The D2 classes of the template's couplings file are refused for an imported geometry**
  (c2z or c1: pairs across the rings are not equivalent). The tutorial's couplings file has one
  pair per measured value.
- **The identity cache of the science hash ignored the numerical context**, which the hash
  covers: `test_science_identity_covers_the_numerical_context` failed. The hashes' cache is keyed
  on the context too.
- At 45 000 couplings the page took 14 s to show the Data tab, 15 s or more for the Structure tab,
  48 s for the Fit tab; the landscape alone took about 14 s, at every tier. Fixed as above.

**Known limit (documented, not fixed):** at 45 000 couplings `project.describe` and
`fit.preview` each take 2–3 s and send about 13 MB, so the live preview's 100 ms target applies to
projects of the beta's size, not to the largest ones; the Fit tab waits about 15 s for its reads.

**Mutation checks** (each makes a test fail): no windowing (`WINDOW_FROM` unreachable); no
drawing cap; the cap not keeping the selection (`web/e2e/large.spec.ts`, 2 556 couplings); the
feeds not closed at exit (`test_shutdown_does_not_wait_for_open_event_streams`: the server outlives
12 s with three feeds open); the hash cache without the numerical context.

**Baseline (before review):** 66 browser tests (22 × 3), 832 Python (`-m "not slow"`), 61 web
unit tests, TypeScript (app and suite), mypy, Ruff, the generated contract and projection parity.
