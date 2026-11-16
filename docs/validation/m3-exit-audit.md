# M3 exit audit

**Plan §8, M3 exit criteria** (03-redesign-plan.md, "M3 Browser beta UI"):
1. the AI-readiness checklist (04 §7 and §8.6) is fully green, including the robot completing the
   biphenyl tutorial in a clean process through HTTP only;
2. the dependency-boundary and behavioural-parity tests pass;
3. the preview p95 target is met on named hardware.

This audit maps each criterion, and each 04 §7 and §8.6 check, to the tests that prove it. It
records where the evidence differs from the letter of the plan, and why. It builds on the
[M2 exit audit](m2-exit-audit.md): the checks that M2 established on the server are cited again
only where M3 added to them; every test cited there still exists and passes.

**The code audited:** `main` at the merge of the plan's approval (f9c0618), plus this audit's
branch: its tests (the whole-run comparison, the UI coverage spec) and the latency records, which
name the commit they measured (7ae4dcc; the application code is `main`'s). **The suites on it:**
834 Python tests (`-m "not slow"`), 65 web unit tests, 108 browser tests (36 tests on Chromium,
Firefox and WebKit), TypeScript, mypy, Ruff, the generated contract, and projection parity.

## The M3 deliverables

| Deliverable (plan) | Where | Browser evidence |
|---|---|---|
| A thin React client on the generated TS client | `web/src`; `generated/contract.ts` from the registry snapshot (M2 step 1b); `callOperation` typed per operation | every browser test |
| Data and Fit workspaces | `ui/DataWorkspace.tsx`, `ui/FitWorkspace.tsx` (M3 step 1) | `basics.spec.ts` "open the example, fit it, and read the run"; the tutorial |
| A minimal Structure view | `ui/StructureWorkspace.tsx` (M3 step 2) | the tutorial (exactly one arc selected, and it is the worst coupling's, by `data-id`); `latency.spec.ts` perception; `large.spec.ts`; `coverage.spec.ts` (layers, camera, selection) |
| Reconciliation | the Data tab's CSV import through `couplings.reconcile` and `couplings.import` (M3 step 2) | the tutorial: the mapping confirmed label by label, then "Import 14 couplings" |
| Live preview | `PreviewPane`, `preview.ts` (M3 step 3) | `preview.spec.ts` (7 tests); `latency.spec.ts` |
| Stale badges | staleness by content (`content_hash`, M3 step 2) | `basics.spec.ts` "a run is stale after another client's change and current again after its undo" |
| The landscape | `fit.landscape`, `LandscapePlot` (M3 step 3; work limit in step 4b) | the preview's start at the landscape's lowest sample (`preview.spec.ts`) |
| View sync from events | `GET /api/v1/events`, `feed.ts`, `studio.ts` (M3 step 1) | the perception test; staleness after another client's change; the inbox's refresh on another client's workspace change |

## 04 §7: AI-readiness without an AI

| Check | Evidence | Status |
|---|---|---|
| UI coverage | **By effect** (rounds 53–54): every page control that changes shared state is used in a browser test, and its change is read back from the server by another client (the map below, which also lists the controls that change only the page). A control that changed only the page fails: page-only layer toggles, wheel zoom or "Fit to view", a camera that never commits, and Data-table rows that do not select each fail `coverage.spec.ts`. **The endpoint scan:** `tests/test_boundaries.py::test_frontend_has_no_private_api`. Only `web/src/api.ts` may touch the network, with exactly three kinds of call: registry operations (`/api/v1/ops/`), the launch-code exchange (`/api/v1/auth/session`, the §8.5 authentication exception) and the change feed (`/api/v1/events`, the event-transport exception). Every other file is barred from `fetch`, `XMLHttpRequest`, `WebSocket`, `EventSource`, `sendBeacon` and dynamic `import`. **What the page calls:** 28 of the 33 operations, 15 commands and 13 queries; the other five are a robot's or an agent's (`job.status`, `job.wait`, `proposal.create`, `view.highlight`, `render.view_svg`). **Backed by** the dependency-boundary test and the behavioural-parity test (criterion 2, below). | Pass, with the limit below |
| **Robot user** | `tools/robot/robot.py --scenario tutorial` (M3 step 4b), standard library only, under `python -I` with a clean environment, over HTTP registry calls only. It runs create (`project.import_xyz` of `datasets/biphenyl-synthetic/biphenyl.xyz`) → import couplings (`couplings.reconcile`) → confirm the mapping → import exactly the reconciled diff → bind the torsion (`molecule.set_torsion`) → set the model → preview → profile fit (`fit.run` with intervals, `job.wait`, `run.get`) → select the worst coupling → render (`render.view_svg`, which must show it) → export. Tests: `test_app_http.py::test_robot_tutorial_as_documented` runs the docstring's command as written; `web/e2e/tutorial.spec.ts` "the tutorial through the page equals the robot's" runs the same steps through the page on each browser and compares the results with the robot's (next row). | Pass, with the deviation below |
| — "equal to the UI path" | The tutorial spec compares the page's project and results with the robot's, each on its own server, the robot's read with the robot's own credential (round 54: read as the user, a server answering the user differently corrupted both sides alike). **Exactly equal:** the science hash, the exported project (deep equality), the selected coupling (its ID and label), and the run's kind, input hash, science hash, science revision and staleness. **The whole run result, field by field** (`web/e2e/compare.ts`, round 53), with the frozen quantity-specific tolerances (§8.6 row below): θ and the order parameters, their standard errors, χ², the p-value, adequacy, every validity flag and rank, every coupling's prediction, residual and normalized residual, the basins, the intervals, the model and the numerical context. Both paths must also give the four intervals (`phi_deg`, `Szz`, `Delta`, `Sxy`), each supported with finite bounds around its estimate, and the true torsion (−37°) inside the torsion's interval (round 52). | Pass |
| Replay | As in M2: every journal record carries the science hash, which replay checks per record. Since journal compaction (after M2), a project also reopens from a verified snapshot plus the journal that continues it: `test_app_snapshot.py::test_after_compaction_the_project_reopens_identically_and_the_journal_is_archived`, `::test_a_snapshot_that_would_not_reproduce_the_state_is_never_written`, and the refusal of damaged or discontinuous snapshots and journals. | Pass |
| Proposals | Server, as in M2: `test_app_m2_exit.py::test_the_robot_completes_the_m2_scenario_over_http_only` (the agent's two-step change set; the closed subset accepted, the non-closed one refused) and `test_app_agent_safety.py::test_only_dependency_closed_subsets_are_accepted`. **The page** (M3 step 3): `inbox.spec.ts` (5 tests) shows an agent's proposal as data, chooses dependency-closed steps, dry-runs the acceptance and accepts; the acceptance carries the workspace revision its dry run saw; a stale proposal says why and is rejected with a reason. | Pass |
| Concurrency | Server, as in M2: `test_app_m2_exit.py::test_two_clients_at_the_same_revision_lose_no_update`. **The UI edit** the check names: `concurrency.spec.ts` "the page's edit made at an older revision is refused; the robot's stays" (REVISION_CONFLICT; the robot's edit stands). | Pass |
| Perception | Server, as in M2: `render.describe_view` reflects the robot's `view.highlight`, and `render.view_svg` draws it (`data-id`). **The browser** (M3 step 4a): `latency.spec.ts` "perception: a robot's highlight reaches the browser", from just before the robot's HTTP call until the page's DOM shows the arc highlighted, 20 samples per browser. On named hardware (below): **max 14 ms (Chromium), 18 ms (Firefox), 16 ms (WebKit)**, against 200 ms. | Pass, with the deviation below |
| Contract | `test_app_m2_exit.py::test_every_operation_returns_the_same_envelope_on_both_adapters` asserts that its sequence covers the registry exactly (33 operations at contract 0.9.0, including the M3 additions) and that every operation succeeds at least once, with identical envelopes over HTTP and in-process. Also: the snapshot test, `tests/test_ts_contract.py` (the generated TypeScript is current), and the TypeScript type tests. | Pass |

**Deviations, recorded:**
- **No PNG** (as in M2). The tutorial renders SVG (`render.view_svg`), which carries object IDs,
  and the robot checks that the worst coupling's ID is in it. `render.view_png` is not built.
- **Perception times DOM updates, not painted frames.** The page's MutationObserver records when
  the arc's class changes; the paint follows within a frame. Both clocks are on one machine.
- **Resolved since M2:** the tutorial now binds a torsion (it starts from an XYZ file), and "equal
  to the UI path" now compares with the page, no longer with the Python adapter.

### The page's controls and their operations

Every command the page sends, the control that sends it, and the browser test that uses the
control and reads the change back from the server (not from the page):

| Operation (command) | Control | Test |
|---|---|---|
| `project.open_example` | Data: "Open the synthetic biphenyl example" | `coverage.spec.ts` (science revision and `project_open`) |
| `project.import_xyz` | Data: "Import XYZ geometry…" | `tutorial.spec.ts` (the science hash equals the robot's) |
| `project.load` | Data: "Load a project file…" | `coverage.spec.ts` (the file's name and domain on the server) |
| `couplings.import` | Data: the mapping, then "Import n couplings" | `tutorial.spec.ts` (science hash, export) |
| `molecule.set_torsion` | Data: the indices a, i, j, b, then "Set torsion" | `tutorial.spec.ts` (science hash) |
| `model.set` | Data: kind, order, frame, φ domain, then "Apply" | `tutorial.spec.ts` (science hash) |
| `fit.run` | Fit: "Run fit" (with "Profile intervals") | `tutorial.spec.ts` (the run, read with `run.get`) |
| `job.cancel` | Fit: a job's "Cancel" | `coverage.spec.ts` (the job `cancelled` in `job.list`) |
| `history.undo`, `history.redo` | the title bar's Undo and Redo | `coverage.spec.ts` (the science hash restored, the model again) |
| `view.select` | a row of any coupling or spin table (click, or Enter and Space); an arc or atom (shift adds); a point of the observed-against-calculated plot; "Clear" | `tutorial.spec.ts` (the Fit tab's residual row), `coverage.spec.ts` (the Data tab's coupling and spin rows, a row by Enter, the Structure table's row, "Clear", an arc, an atom, a shift-click adding an arc, a plot point; the clicks on SVG elements are dispatched to them, bypassing hit-testing; Space shares Enter's handler) |
| `view.set_layers` | Structure: the Labels, Bonds and Couplings checkboxes | `coverage.spec.ts` (each layer off and on in `render.scene`) |
| `view.set_camera` | Structure: drag, the wheel, arrow keys, + and −, 0 and Home, "Fit to view" | `coverage.spec.ts` (arrow keys, +, a pointer drag, 0, the wheel, "Fit to view": `render.scene`'s camera changes each time, and "Fit to view" restores the automatic camera; − and Home share + and 0's handlers) |
| `proposal.accept`, `proposal.reject` | Proposals: "Accept", "Reject" | `coverage.spec.ts` (`proposal.get`'s status; the accepted model on the server) |

The 13 queries (`couplings.reconcile`, `fit.landscape`, `fit.preview`, `history.log`, `job.list`,
`project.describe`, `project.export`, `proposal.get`, `proposal.list`, `render.describe_view`,
`render.scene`, `run.get`, `run.list`) change nothing; what the page shows from them is checked
where it matters: the preview's residuals against the server's (`latency.spec.ts`), the
reconciliation in the tutorial, the export against the robot's.

**Controls that change only the page, by design** (no shared state): the workspace tabs; the
error banner's dismissal; the drafts of the torsion indices and of the model, and the model's
Reset; the couplings import's choice of file and mapping, its Reset and the diff's download; the
Fit tab's choice of run, "Profile intervals" before Run fit, and a result's Retry (a read); the
preview's slider, φ field, "to the fit" button and the landscape's clicks (`fit.preview`, a
query); the inbox's choice of proposal and of steps, "Check again" (a dry run) and the rejection
reason before Reject.

## 04 §8.6: additional checks

The server checks are those of the M2 exit audit; every test it cites still exists and passes.
M3 adds the browser's half of the timing check.

| Check | Evidence | Status |
|---|---|---|
| The robot runs in a clean process, with no frontend or browser dependencies | `test_app_http.py::test_robot_is_standard_library_only` (an AST check of its imports). The Python tests run all three robot scenarios with `python -I` and an environment without `PYTHON*`, `VIRTUAL_ENV` or `UV_` variables; `tutorial.spec.ts` runs `python3 -I` (`DIPOLAR_ROBOT_PYTHON` to override; isolated mode ignores `PYTHON*` variables and the user site). Either way the robot is the standard-library-only script. | Pass |
| No tier escalation through arguments | `test_app_agent_safety.py::test_tier_comes_from_the_credential_never_from_arguments`, `test_app_http.py::test_identity_comes_from_the_credential_only`, `test_app_agent_safety.py::test_only_a_human_accepts` | Pass |
| Rejection of stale proposals | `test_app_agent_safety.py::test_a_stale_proposal_is_refused_with_a_conflict_report`; on the page, `inbox.spec.ts` "a stale proposal says why and can be rejected with a reason" | Pass |
| View changes during running fits leave the science and the runs untouched | `test_app_jobs.py::test_view_changes_during_a_running_fit_leave_science_and_run_untouched` | Pass |
| Deduplication after a disconnect and retry | `test_app_agent_safety.py`: `test_a_retried_request_returns_the_stored_outcome_and_applies_once`, `test_deduplication_survives_a_restart`, `test_concurrent_retries_apply_once`, `test_a_retried_acceptance_survives_pruning_and_restart`; with compaction, `test_app_snapshot.py::test_deduplication_expires_with_the_bounded_request_table` (the documented bound) | Pass |
| Journal crash recovery, by killing the process mid-commit | `spikes/test_spike_journal_crash.py::test_kill_at_random_moments_loses_no_acknowledged_command`, `::test_a_killed_server_restarts_from_its_torn_journal`; with compaction, simulated crashes before and after the snapshot rotation (`test_app_snapshot.py::test_a_crash_before_the_rotation_discards_the_next_snapshot`, `::test_a_crash_after_the_rotation_promotes_the_next_snapshot`; not a killed process) | Pass |
| Cross-actor undo conflicts | `test_app_agent_safety.py::test_undo_conflicts_with_a_change_the_caller_has_not_seen` | Pass |
| "Equal results" use quantity-specific tolerances; "within 200 ms" is measured on named hardware | **Tolerances:** both robot comparisons use the frozen regression tolerances of `datasets/biphenyl-synthetic/expected/spec.json`: the M2 one (`assert_same_science`, whose relative comparisons have no absolute floor since round 54: `pytest.approx`'s default 1e-12 had accepted p-values of 1e-14 and 5e-13; its rejection test now includes that pair) and the tutorial's whole-run comparison (`compare.ts`, which reads them from that file). Its rules, for \|a − b\|: φ (θ, basins, the φ interval's estimate) ≤ 1e-4°; S_zz, Δ, S_xy (and their interval estimates) ≤ 1e-6; φ interval endpoints ≤ 1e-4°, S endpoints ≤ 1e-6; standard errors ≤ 1e-3 × max(\|a\|, \|b\|); χ², the p-value and each basin's χ² ≤ 1e-6 × max(\|a\|, \|b\|); a basin's Δχ² ≤ 1e-6 × max(1, χ²); predictions, residuals and the RMS residual ≤ 1e-6 Hz; a normalized residual ≤ 1e-6 Hz / σ. Inputs copied into the result (observed values, σ, the domain, the numerical context) and every string, boolean and integer (counts, ranks, ν) are equal exactly. **Not in the frozen spec:** the inner condition number, a diagnostic, ≤ 1e-6 × max(\|a\|, \|b\|). The comparison is fail-closed: a non-integer number without a rule, a field on one side only or a different length is a difference; an integer without a rule must be equal exactly. `web/tests/compare.test.ts` checks that an equal result passes, that values within the tolerances pass, and that each altered field fails (including the reviewer's: predictions 1 000 Hz off, a flipped validity flag, a changed adequacy and p-value). **Timing:** the perception and preview times are measured on the hardware named below, recorded with every sample. | Pass |

## Exit criteria

| Criterion | Evidence | Status |
|---|---|---|
| 1. The 04 §7 and §8.6 checklist is fully green, including the robot's tutorial in a clean process over HTTP only | The two tables above | Pass |
| 2. The dependency-boundary and behavioural-parity tests pass | **Dependency boundary:** `tests/test_boundaries.py::test_frontend_imports_no_domain_logic` (the page imports nothing but its own modules, React and React DOM, so no fitting, reconciliation or selection library) and the endpoint scan above. **Behavioural parity** (04 §8.5: "robot vs UI"): `tutorial.spec.ts`, on three browsers. **Perception parity** (04 §8.4): the page's projection equals the server's, `test_app_scene.py::test_the_browser_projection_matches` and `pnpm run parity` (largest difference 5.7e-14), with `::test_the_parity_check_catches_a_difference`. | Pass, with the limit below |
| 3. The preview p95 target is met on named hardware | `latency.spec.ts` "live preview: p95 from a slider gesture to fresh residuals", recorded with `DIPOLAR_RECORD_LATENCY=1` (below): **p95 10.7 ms (Chromium), 13 ms (Firefox), 15 ms (WebKit)**, against 100 ms. A sample ends only when the preview line and the residual table show the new φ, and every row displays the D calc and residual the server gives at that φ (rounds 49–50). | Pass, on the beta fixture |

**Limits, recorded:**
- **UI coverage is established for the controls that exist.** `coverage.spec.ts` and the tests
  named in the map use every control that sends a command; a control added later is covered only
  when a test uses it. The endpoint scan holds for any code, but cannot tell a command the page
  sends from one it omits.
- **The dependency-boundary test checks imports, not code.** It proves the page uses no domain
  library; it cannot prove that the page reimplements none. The page's own logic is presentation:
  which steps a checkbox selects with their dependencies (`inbox.ts`; the server refuses any
  subset that is not closed), which rows and arcs to draw (`limits.ts`), the slider's snapping and
  the landscape's drawing (`preview.ts`), and the camera during a gesture (`scene/view.ts`; the projection it
  feeds, `scene/projection.ts`, is checked by the projection parity). Fitting, reconciliation, selection and staleness are server
  operations.
- **The preview target holds for projects of the beta's size.** At about 45 000 couplings,
  `project.describe` and `fit.preview` each take 2–3 s and send about 13 MB (M3 step 4b), so the
  live preview is not interactive there; the tables and the Structure view stay responsive.

## Latency on named hardware

Intel Core i7-8750H (2.2 GHz, 12 threads), 32 GiB, macOS 15.8.1 (darwin 24.6.0); browsers
headless; the beta fixture (synthetic biphenyl, 14 couplings), warm. Recorded on commit 7ae4dcc
with `modified: false`, in [data/m3-latency/](data/m3-latency/) (`<browser>-<measurement>.json`,
every sample, the browser's version, the machine and the commit). `modified` is `git status` of
`web/`, `packages/` and `tools/` from the repository's root; it was checked both ways before
recording (false on a clean tree, true with an edited server file; round 53 found the first
version looking in the wrong directories).

| Browser | Preview: gesture → fresh residuals (target p95 < 100 ms) | Perception: robot highlight → arc in the page (target < 200 ms) |
|---|---|---|
| Chromium 159.0 | p50 8.4, **p95 10.7**, max 12.2 ms (60) | p50 12, p95 14, **max 14** ms (20) |
| Firefox 159.0 | p50 10, **p95 13**, max 31 ms (60) | p50 15, p95 18, **max 18** ms (20) |
| WebKit 27.2 | p50 12, **p95 15**, max 17 ms (60) | p50 15, p95 16, **max 16** ms (20) |

**Faster than at M3 step 4a** (preview p95 19–53 ms then). A hypothesis with one supporting
measurement: step 4b's per-project caches (`ByIdentity`) spare every preview the validation and
construction of the problem and its hashes. **An ad hoc measurement, not committed:** on the same
code, 200 calls of `fit.preview` over HTTP on loopback (after 20 warm-up calls, one client, φ
varying) took a median of 2.6 ms and a p95 of 3.1 ms, against the M2 benchmark's committed 18.6
and 20.4 ms. The components are not timed separately.

CI's shared runners are not named hardware: there the same tests guard only against regressions
(p95 < 400 ms, max < 800 ms).

## Open items carried forward

- **(B, round 50) A tab click that only focused the tab** was seen once on Firefox in CI; the tests
  open tabs through `openTab`, which clicks until the tab reports itself selected. It has not
  recurred in the step 4b runs; its cause is not known.
- The owner's items in STATUS: the hours log, the thesis PDF, Di Pietro's permission.

## Validation: round 53

Round 53 returned NOT READY, with five class-(A) findings and one class (B), on commit 07b43a7.
The reviewer's run: 834 Python, 62 web unit and 84 browser tests passed, with the strict latency
recording; the six latency summaries match their samples; the 28-of-33 inventory is right;
projection parity rejected a one-pixel mutant, and perception a 250 ms delay (measured 267 ms).

| # | Class | Finding | Resolution |
|---|---|---|---|
| 1 | A | **The page-to-robot comparison was partial.** An HTTP mutant that put the page path's predictions 1 000 Hz off, flipped `validity.regular` and changed adequacy and the p-value passed. | The whole run result is compared field by field with the frozen quantity-specific tolerances (`compare.ts`, fail-closed), and the run's inputs exactly. `compare.test.ts` rejects every altered field; a server mutant that moves the page path's predictions by 1 000 Hz now fails the tutorial, listing each coupling. |
| 2 | A | **"The worst coupling's arc selected" was unproven:** the test accepted any one selected arc. | The selected arc's `data-id` must be the worst coupling's ID, which must also be the shared view's selection and the robot's. A mutant that marked another arc selected now fails. |
| 3 | A | **UI coverage was not established:** a layer toggle made page-only passed the boundary checks and every browser test. | `coverage.spec.ts` uses every control that sends a command and reads its effect back from the server (the map above); the coverage claim is qualified (limits). The reviewer's mutant and a camera that never commits now fail. |
| 4 | A | **`modified: false` did not prove a clean tree:** the recorder looked at `docs/web` and `docs/packages`. | It checks `web/`, `packages/` and `tools/` from the repository's root; checked both ways (false clean, true with an edited server file) before the records were made again on 7ae4dcc. |
| 5 | A | **The tolerance description was wrong** (endpoints were `1e-9 + 1e-9 × max`, not absolute) and the uniform tolerance was not quantity-specific. | Replaced by the frozen quantity-specific tolerances, each formula stated in the §8.6 row; the one rule outside the frozen spec (the condition number) is named. |
| 6 | B | **The 2.6/3.1 ms HTTP preview timing was not archived.** | Labelled as an ad hoc measurement with its procedure; the committed comparison is the M2 benchmark. |

**Also changed:** the browser harness resends a **query** once after a connection error. Node's
fetch reused a kept-alive connection that a server had closed while the robot ran for seconds
(ECONNRESET, which the reviewer also met); commands are never resent. Narrowed in round 54.

**After the fixes:** 834 Python, 65 web unit and 105 browser tests (35 × 3) passed.

## Validation: round 54 (final under the cap)

Round 54 returned NOT READY, with three class-(A) findings and one class (B), on commit 45ff1b6.
The reviewer confirmed that the wrong-arc, page-only layer and uncommitted camera mutants fail;
that the six latency summaries match their samples and the audit; and that 7ae4dcc's application
code is that of 45ff1b6 and `main`. Its run: 834 Python, 65 web unit and 105 browser tests.
Under the two-round cap, these fixes were **not reviewed again**.

| # | Class | Finding | Resolution |
|---|---|---|---|
| 1 | A | **The original result mutant still passed:** the robot's run was read with the user's credential, so a server corrupting the user's view corrupted both sides. | The robot's view and run are read with the robot's credential. The reviewer's mutant (keyed on the caller: predictions +1 000 Hz, a flipped validity flag, adequacy, the p-value) now fails, listing each field. |
| 2 | A | **"Every control" was unproven:** page-only wheel zoom and "Fit to view", and Data-table rows that did not select, passed every test. | `coverage.spec.ts` now also uses the wheel, "Fit to view", the Data tab's coupling and spin rows, a row by keyboard, a shift-click and a plot point; the map lists every control, and the page-only ones by design. The reviewer's three mutants each fail (each confirmed to build). |
| 3 | A | **The M2 comparison's relative tolerances had a hidden absolute floor** (1e-12, from `pytest.approx`), so the stated formulas overstated it. | `abs=0` on every relative comparison; a p-value pair of 5e-13 and 1e-14 must be rejected (it is, and it was accepted with the floor restored). |
| 4 | B | **The query retry could hide any transient transport failure.** | It now resends a query only after `ECONNRESET`, once, and logs it ("harness: … resent once after ECONNRESET"); any other failure, a second reset and any command failure are errors. It fires at most once per tutorial run, on `project.describe` after the robot's run: in the final full run, on Chromium and Firefox, not WebKit. |

**After the fixes:** 834 Python, 65 web unit and 108 browser tests (36 × 3) passed.
