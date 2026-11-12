# M2 exit audit

**Plan §8, M2 exit criteria:**
1. all §8.6 checks pass;
2. replay reproduces the science hash;
3. the registry snapshot, the behavioural fixtures and the contract tests pass on the Python and
   HTTP adapters;
4. the benchmark is published.

This audit maps each criterion, and each 04 §7 check it rests on, to the tests that prove it. It
also records where the evidence differs from the letter of the plan, and why. The benchmark is in
[data/m2-benchmark.json](data/m2-benchmark.json) and is summarised below.

## 04 §7: AI-readiness without an AI

| Check | Evidence | Status |
|---|---|---|
| UI coverage | `tests/test_boundaries.py::test_frontend_has_no_private_api` scans web/src for network access outside the registry, auth and the event stream. `::test_frontend_imports_no_domain_logic` is the dependency boundary. | Pass. Behavioural parity with a UI arrives with the M3 UI. |
| Robot user | `tests/test_app_m2_exit.py::test_the_robot_completes_the_m2_scenario_over_http_only` (details below the table). The M0 scenario is `tests/test_app_http.py::test_robot_completes_the_slice_in_a_clean_process`. | Pass, with the deviations below. |
| Replay | Every journal record carries the science hash, and replay checks it per record (`session.replay_full`). `test_app_agent_safety`, `test_app_jobs` and `test_app_scene` assert `replay(journal) == session.state`. The robot test restarts the server and compares the science hash and revisions. | Pass |
| Proposals | The robot, as the `agent` (propose tier), creates a two-step change set. The test accepts the dependency-closed subset `[0]` and is refused the non-closed `[1]` (`missing: [0]`). Also `test_app_agent_safety.py::test_only_dependency_closed_subsets_are_accepted`. | Pass |
| Concurrency | `test_app_m2_exit.py::test_two_clients_at_the_same_revision_lose_no_update`: a human and the robot over HTTP at the same revision; the second edit gets `REVISION_CONFLICT` and the first stands. Also `test_app_dispatch.py::test_revision_conflict_mutates_nothing`. | Pass |
| Perception | In the robot test, `render.describe_view` reflects the robot's `view.highlight` and `render.view_svg` draws it (`data-id`). The server half of "within 200 ms" is measured: highlight, then `describe_view`, median 5.1 ms and p95 5.9 ms. | Server half: pass. The browser half arrives with M3. |
| Contract | `test_app_m2_exit.py::test_every_operation_returns_the_same_envelope_on_both_adapters`: all 32 registry operations, in one stateful sequence, give identical envelopes over HTTP and in-process (timestamps normalized). The sequence must cover the registry exactly. Also: the snapshot test, the serialization spike (examples, results and dry runs against the published schemas with an independent validator), and `tests/test_ts_contract.py`. | Pass |

**What the robot test does.** The stdlib-only robot runs in a clean process (`python -I`, no
virtualenv or `PYTHON*` variables), over HTTP only:
1. it imports the couplings as a user's CSV and confirms the mapping;
2. it previews, then fits with profile intervals as a job (`job.wait`, `run.get`);
3. it selects and highlights the worst coupling;
4. it checks `describe_view` and the SVG, then exports.

Its fit equals the Python adapter's within the frozen, quantity-specific tolerances (§8.6), and φ
equals the frozen answer.

**Deviations, recorded:**
- **No PNG.** The §7 tutorial says "render a PNG". The beta renders SVG (`render.view_svg`), and
  `render.view_png` is not built. The SVG is the same scene, with object IDs, so it is the stronger
  check. A PNG can be rasterized from it if a client needs one.
- **No torsion binding in the tutorial.** "Bind torsion" applies to imported geometry. The template
  tutorial has none, and `molecule.set_torsion` is covered by the cross-adapter sequence and
  `test_app_science_ops`.
- **No UI path to compare against yet.** "Equal to the UI path" is replaced, until M3 builds the
  UI, by equality with the Python adapter's path.

## 04 §8.6: additional checks

| Check | Evidence | Status |
|---|---|---|
| The robot runs in a clean process, with no frontend or browser dependencies | `test_app_http.py::test_robot_is_standard_library_only` (an AST check of its imports); both robot tests run with `python -I` and a clean environment. | Pass |
| No tier escalation through arguments | `test_app_agent_safety.py::test_tier_comes_from_the_credential_never_from_arguments`; `test_app_http.py::test_identity_comes_from_the_credential_only`; approval needs a human principal (`test_only_a_human_accepts`). | Pass |
| Rejection of stale proposals | `test_app_agent_safety.py::test_a_stale_proposal_is_refused_with_a_conflict_report` | Pass |
| View changes during running fits leave the science and the runs untouched | `test_app_jobs.py::test_view_changes_during_a_running_fit_leave_science_and_run_untouched` (a fit held running while the selection, highlights, layers and camera change); `test_app_scene.py::test_view_commands_change_only_the_workspace_and_never_stale_a_run` | Pass |
| Deduplication after a disconnect and retry | `test_app_agent_safety.py`: `test_a_retried_request_returns_the_stored_outcome_and_applies_once`, `test_deduplication_survives_a_restart`, `test_concurrent_retries_apply_once`, `test_a_retried_acceptance_survives_pruning_and_restart` | Pass |
| Journal crash recovery, by killing the process mid-commit | `spikes/test_spike_journal_crash.py::test_kill_at_random_moments_loses_no_acknowledged_command`, `::test_a_killed_server_restarts_from_its_torn_journal` (and the long kill loop) | Pass |
| Cross-actor undo conflicts | `test_app_agent_safety.py::test_undo_conflicts_with_a_change_the_caller_has_not_seen` | Pass |
| "Equal results" use quantity-specific tolerances; "within 200 ms" is measured on named hardware | `assert_same_science` uses the frozen regression tolerances (φ 1e-4°, S 1e-6, χ² rtol 1e-6, predictions 1e-6 Hz, interval endpoints). The benchmark names the hardware. | Pass |

## Exit criteria

| Criterion | Evidence | Status |
|---|---|---|
| All §8.6 checks pass | The table above | Pass |
| Replay reproduces the science hash | The per-record hash check in replay, and the robot's restart test | Pass |
| Snapshot, behavioural fixtures and contract tests pass on both adapters | The registry snapshot test, the frozen `datasets/*/expected` fixtures (`tests/test_expected_fixtures.py`, the M1 gates), and the cross-adapter sequence over all 32 operations | Pass |
| The benchmark is published | [data/m2-benchmark.json](data/m2-benchmark.json) (`tools/bench/m2_benchmark.py`) | Pass |

## The benchmark (summary)

The hardware: Intel Core i7-8750H @ 2.20 GHz, 12 logical cores, 32 GiB; macOS 15.8.1 (x86_64),
Python 3.12; NumPy and SciPy versions as recorded. The fixture is the synthetic biphenyl problem
(10 spins, 14 couplings, rigid model).

| Measurement | Default threads | One core |
|---|---|---|
| Cold: import the stack | 790 ms | 778 ms |
| Cold: first fit | 208 ms | 193 ms |
| Warm fit (median of 5) | 192 ms | 189 ms |
| Preview kernel (`profile_residual`, median of 300) | 0.24 ms | 0.24 ms |
| Peak RSS of the kernel process | 63 MiB | 63 MiB |

The fit is single-threaded in effect: one core costs nothing.

| End to end (`dipolar serve`, HTTP on loopback) | Value |
|---|---|
| Server start (to the ready file) | 675 ms |
| `fit.preview` over HTTP, 200 calls | median 24.0 ms, p95 26.5 ms |
| `fit.run` job, submit to finished (3 runs) | median 1.83 s; about 1.6 s of it is spawning the worker process |
| `fit.run` with profile intervals | 7.4 s |
| `view.highlight` then `render.describe_view` (50 runs) | median 5.1 ms, p95 5.9 ms |
| `render.view_svg` (50 calls) | median 2.4 ms |
| Server RSS after the runs | 77 MiB |
| Output sizes | run result 6.6 kB; SVG 4.2 kB; project export 10.2 kB; journal 56 kB after the session |

**Numerical agreement**, against the frozen fixture from the independent reference implementation:

| Quantity | Difference | Tolerance |
|---|---|---|
| φ | 2.4e-9° | 1e-4° |
| Szz | 6.6e-12 | 1e-6 |
| Δ | 2.8e-11 | 1e-6 |
| χ² | relative 2.7e-13 | relative 1e-6 |

**Legacy.** The 1998 fit pipeline (MFC) is not compiled, so its acceptance rate is not measurable;
its grid search accepts nearly every point (bug report B08). The 1998 solver routines are compiled
by the legacy harness (CI): they get 2 of the 7 frozen cases right, and the engine gets all 7. The
fit semantics differ (D3), so legacy numbers are not a target.

**Observations for M3:**
- A preview over HTTP costs about 100× the kernel (24 ms vs 0.24 ms): validation, the registry, the
  session, JSON and HTTP. That is well inside an interactive budget. The M3 preview p95 target
  will be set against it.
- A fit job is dominated by spawning a process per job. A warm worker pool would bring it near the
  kernel's 0.2 s; this is the limit recorded in M2 step 3.
