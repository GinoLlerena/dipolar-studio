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
branch (the latency records name the commit they measured, 26543ba). **The suites on it:**
834 Python tests (`-m "not slow"`), 62 web unit tests, 84 browser tests (28 tests on Chromium,
Firefox and WebKit), TypeScript, mypy, Ruff, the generated contract, and projection parity.

## The M3 deliverables

| Deliverable (plan) | Where | Browser evidence |
|---|---|---|
| A thin React client on the generated TS client | `web/src`; `generated/contract.ts` from the registry snapshot (M2 step 1b); `callOperation` typed per operation | every browser test |
| Data and Fit workspaces | `ui/DataWorkspace.tsx`, `ui/FitWorkspace.tsx` (M3 step 1) | `basics.spec.ts` "open the example, fit it, and read the run"; the tutorial |
| A minimal Structure view | `ui/StructureWorkspace.tsx` (M3 step 2) | the tutorial (the worst coupling's arc selected); `latency.spec.ts` perception; `large.spec.ts` |
| Reconciliation | the Data tab's CSV import through `couplings.reconcile` and `couplings.import` (M3 step 2) | the tutorial: the mapping confirmed label by label, then "Import 14 couplings" |
| Live preview | `PreviewPane`, `preview.ts` (M3 step 3) | `preview.spec.ts` (7 tests); `latency.spec.ts` |
| Stale badges | staleness by content (`content_hash`, M3 step 2) | `basics.spec.ts` "a run is stale after another client's change and current again after its undo" |
| The landscape | `fit.landscape`, `LandscapePlot` (M3 step 3; work limit in step 4b) | the preview's start at the landscape's lowest sample (`preview.spec.ts`) |
| View sync from events | `GET /api/v1/events`, `feed.ts`, `studio.ts` (M3 step 1) | the perception test; staleness after another client's change; the inbox's refresh on another client's workspace change |

## 04 §7: AI-readiness without an AI

| Check | Evidence | Status |
|---|---|---|
| UI coverage | **The endpoint scan:** `tests/test_boundaries.py::test_frontend_has_no_private_api`. Only `web/src/api.ts` may touch the network, with exactly three kinds of call: registry operations (`/api/v1/ops/`), the launch-code exchange (`/api/v1/auth/session`, the §8.5 authentication exception) and the change feed (`/api/v1/events`, the event-transport exception). Every other file is barred from `fetch`, `XMLHttpRequest`, `WebSocket`, `EventSource`, `sendBeacon` and dynamic `import`. **What the page calls:** 28 of the 33 operations. The other five are a robot's or an agent's: `job.status`, `job.wait`, `proposal.create`, `view.highlight` and `render.view_svg`. **Backed by** the dependency-boundary test and the behavioural-parity test (criterion 2, below). | Pass |
| **Robot user** | `tools/robot/robot.py --scenario tutorial` (M3 step 4b), standard library only, under `python -I` with a clean environment, over HTTP registry calls only. It runs create (`project.import_xyz` of `datasets/biphenyl-synthetic/biphenyl.xyz`) → import couplings (`couplings.reconcile`) → confirm the mapping → import exactly the reconciled diff → bind the torsion (`molecule.set_torsion`) → set the model → preview → profile fit (`fit.run` with intervals, `job.wait`, `run.get`) → select the worst coupling → render (`render.view_svg`, which must show it) → export. Tests: `test_app_http.py::test_robot_tutorial_as_documented` runs the docstring's command as written; `web/e2e/tutorial.spec.ts` "the tutorial through the page equals the robot's" runs the same steps through the page on each browser and compares the results with the robot's (next row). | Pass, with the deviation below |
| — "equal to the UI path" | The tutorial spec compares the page's project and results with the robot's, each on its own server. **Exactly equal:** the science hash, the exported project (deep equality), the selected coupling's label, ν, the interval parameters and their support. **Within a relative 1e-9:** θ, the order parameters, their standard errors and χ²; **within 1e-9:** every interval endpoint. Both paths must also give the four intervals (`phi_deg`, `Szz`, `Delta`, `Sxy`), each supported with finite bounds around its estimate, and the true torsion (−37°) inside the torsion's interval (round 52). | Pass |
| Replay | As in M2: every journal record carries the science hash, which replay checks per record. Since journal compaction (after M2), a project also reopens from a verified snapshot plus the journal that continues it: `test_app_snapshot.py::test_after_compaction_the_project_reopens_identically_and_the_journal_is_archived`, `::test_a_snapshot_that_would_not_reproduce_the_state_is_never_written`, and the refusal of damaged or discontinuous snapshots and journals. | Pass |
| Proposals | Server, as in M2: `test_app_m2_exit.py::test_the_robot_completes_the_m2_scenario_over_http_only` (the agent's two-step change set; the closed subset accepted, the non-closed one refused) and `test_app_agent_safety.py::test_only_dependency_closed_subsets_are_accepted`. **The page** (M3 step 3): `inbox.spec.ts` (5 tests) shows an agent's proposal as data, chooses dependency-closed steps, dry-runs the acceptance and accepts; the acceptance carries the workspace revision its dry run saw; a stale proposal says why and is rejected with a reason. | Pass |
| Concurrency | Server, as in M2: `test_app_m2_exit.py::test_two_clients_at_the_same_revision_lose_no_update`. **The UI edit** the check names: `concurrency.spec.ts` "the page's edit made at an older revision is refused; the robot's stays" (REVISION_CONFLICT; the robot's edit stands). | Pass |
| Perception | Server, as in M2: `render.describe_view` reflects the robot's `view.highlight`, and `render.view_svg` draws it (`data-id`). **The browser** (M3 step 4a): `latency.spec.ts` "perception: a robot's highlight reaches the browser", from just before the robot's HTTP call until the page's DOM shows the arc highlighted, 20 samples per browser. On named hardware (below): **max 13 ms (Chromium), 16 ms (Firefox), 15 ms (WebKit)**, against 200 ms. | Pass, with the deviation below |
| Contract | `test_app_m2_exit.py::test_every_operation_returns_the_same_envelope_on_both_adapters` asserts that its sequence covers the registry exactly (33 operations at contract 0.9.0, including the M3 additions) and that every operation succeeds at least once, with identical envelopes over HTTP and in-process. Also: the snapshot test, `tests/test_ts_contract.py` (the generated TypeScript is current), and the TypeScript type tests. | Pass |

**Deviations, recorded:**
- **No PNG** (as in M2). The tutorial renders SVG (`render.view_svg`), which carries object IDs,
  and the robot checks that the worst coupling's ID is in it. `render.view_png` is not built.
- **Perception times DOM updates, not painted frames.** The page's MutationObserver records when
  the arc's class changes; the paint follows within a frame. Both clocks are on one machine.
- **Resolved since M2:** the tutorial now binds a torsion (it starts from an XYZ file), and "equal
  to the UI path" now compares with the page, no longer with the Python adapter.

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
| "Equal results" use quantity-specific tolerances; "within 200 ms" is measured on named hardware | **Tolerances:** the M2 robot comparison uses the frozen, quantity-specific regression tolerances (`assert_same_science`). The tutorial's page-to-robot comparison is stricter: the same inputs on the same engine, so exact equality where the values are copied (hash, export, labels, ν) and a relative 1e-9 where they are computed in two processes (D11: the last bits may differ). **Timing:** the perception and preview times are measured on the hardware named below, recorded with every sample. | Pass |

## Exit criteria

| Criterion | Evidence | Status |
|---|---|---|
| 1. The 04 §7 and §8.6 checklist is fully green, including the robot's tutorial in a clean process over HTTP only | The two tables above | Pass |
| 2. The dependency-boundary and behavioural-parity tests pass | **Dependency boundary:** `tests/test_boundaries.py::test_frontend_imports_no_domain_logic` (the page imports nothing but its own modules, React and React DOM, so no fitting, reconciliation or selection library) and the endpoint scan above. **Behavioural parity** (04 §8.5: "robot vs UI"): `tutorial.spec.ts`, on three browsers. **Perception parity** (04 §8.4): the page's projection equals the server's, `test_app_scene.py::test_the_browser_projection_matches` and `pnpm run parity` (largest difference 5.7e-14), with `::test_the_parity_check_catches_a_difference`. | Pass, with the limit below |
| 3. The preview p95 target is met on named hardware | `latency.spec.ts` "live preview: p95 from a slider gesture to fresh residuals", recorded with `DIPOLAR_RECORD_LATENCY=1` (below): **p95 9.1 ms (Chromium), 11 ms (Firefox), 13 ms (WebKit)**, against 100 ms. A sample ends only when the preview line and the residual table show the new φ, and every row displays the D calc and residual the server gives at that φ (rounds 49–50). | Pass, on the beta fixture |

**Limits, recorded:**
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
headless; the beta fixture (synthetic biphenyl, 14 couplings), warm. Recorded on commit 26543ba
with an unmodified tree, in [data/m3-latency/](data/m3-latency/) (`<browser>-<measurement>.json`,
every sample, the browser's version, the machine and the commit).

| Browser | Preview: gesture → fresh residuals (target p95 < 100 ms) | Perception: robot highlight → arc in the page (target < 200 ms) |
|---|---|---|
| Chromium 159.0 | p50 7.6, **p95 9.1**, max 9.8 ms (60) | p50 11, p95 13, **max 13** ms (20) |
| Firefox 159.0 | p50 9, **p95 11**, max 22 ms (60) | p50 14, p95 16, **max 16** ms (20) |
| WebKit 27.2 | p50 9, **p95 13**, max 14 ms (60) | p50 12, p95 13, **max 15** ms (20) |

**Faster than at M3 step 4a** (preview p95 19–53 ms then). A hypothesis with one supporting
measurement: step 4b's per-project caches (`ByIdentity`) spare every preview the validation and
construction of the problem and its hashes. Measured on this commit, `fit.preview` over HTTP on
loopback takes a median of 2.6 ms and a p95 of 3.1 ms (200 calls), against the M2 benchmark's 18.6
and 20.4 ms. The components are not timed separately.

CI's shared runners are not named hardware: there the same tests guard only against regressions
(p95 < 400 ms, max < 800 ms).

## Open items carried forward

- **(B, round 50) A tab click that only focused the tab** was seen once on Firefox in CI; the tests
  open tabs through `openTab`, which clicks until the tab reports itself selected. It has not
  recurred in the step 4b runs; its cause is not known.
- The owner's items in STATUS: the hours log, the thesis PDF, Di Pietro's permission.
