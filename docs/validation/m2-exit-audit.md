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
| Contract | `test_app_m2_exit.py::test_every_operation_returns_the_same_envelope_on_both_adapters` runs one stateful sequence that covers the registry exactly and asserts each step's expected outcome. **Every one of the 32 operations succeeds at least once on both adapters**, including a human's `proposal.accept` and `proposal.reject` through the `user` credential. The only refusal is the one the step expects (the robot's non-human accept). Envelopes are identical over HTTP and in-process (timestamps normalized). A dispatcher that refused everything now fails the test (round 37). Also: the snapshot test, and `tests/test_ts_contract.py`. The serialization spike checks every example, result and dry run against the published schemas with an independent validator, **through the Python adapter only**. | Pass |

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
| View changes during running fits leave the science and the runs untouched | `test_app_jobs.py::test_view_changes_during_a_running_fit_leave_science_and_run_untouched`. A fit is held running while the selection, highlights, layers and camera change. Its result must equal, number for number, a baseline run on the same inputs; the published baseline run's record and blob must be unchanged; and the science must be unchanged. A mutation that let view changes shift φ now fails it (round 37). `test_app_scene.py::test_view_commands_change_only_the_workspace_and_never_stale_a_run` checks only that staleness and the science are unaffected. | Pass |
| Deduplication after a disconnect and retry | `test_app_agent_safety.py`: `test_a_retried_request_returns_the_stored_outcome_and_applies_once`, `test_deduplication_survives_a_restart`, `test_concurrent_retries_apply_once`, `test_a_retried_acceptance_survives_pruning_and_restart` | Pass |
| Journal crash recovery, by killing the process mid-commit | `spikes/test_spike_journal_crash.py::test_kill_at_random_moments_loses_no_acknowledged_command`, `::test_a_killed_server_restarts_from_its_torn_journal` (and the long kill loop) | Pass |
| Cross-actor undo conflicts | `test_app_agent_safety.py::test_undo_conflicts_with_a_change_the_caller_has_not_seen` | Pass |
| "Equal results" use quantity-specific tolerances; "within 200 ms" is measured on named hardware | `assert_same_science` uses the frozen regression tolerances (φ 1e-4°, S 1e-6, χ² rtol 1e-6, predictions 1e-6 Hz, interval endpoints). The benchmark names the hardware. | Pass |

## Exit criteria

| Criterion | Evidence | Status |
|---|---|---|
| All §8.6 checks pass | The table above | Pass |
| Replay reproduces the science hash | The per-record hash check in replay, and the robot's restart test | Pass |
| Snapshot, behavioural fixtures and contract tests pass on both adapters | **The snapshot:** the registry snapshot test, and `GET /api/v1/registry` equal to it. **The contract:** the cross-adapter sequence, with every operation succeeding on both adapters. **The behavioural fixtures** on both adapters: the robot's fit over HTTP equals the frozen noisy fixture's φ and the Python adapter's fit within the frozen tolerances. The other frozen gates (M1) run on the engine directly, not through an adapter. `tests/test_expected_fixtures.py` checks the independent reference implementation, not the adapters. | Pass |
| The benchmark is published | [data/m2-benchmark.json](data/m2-benchmark.json) (`tools/bench/m2_benchmark.py`) | Pass |

## The benchmark (summary)

The hardware: Intel Core i7-8750H @ 2.20 GHz, 12 logical cores, 32 GiB; macOS 15.8.1 (x86_64),
Python 3.12; NumPy and SciPy versions as recorded. The numbers below are from the run committed in
the JSON (round 37 rerun). The fixture is the synthetic biphenyl problem
(10 spins, 14 couplings, rigid model).

| Measurement | Inherited environment | Thread limits set to 1 |
|---|---|---|
| Cold: import the stack | 814 ms | 770 ms |
| Cold: first fit | 193 ms | 209 ms |
| Warm fit (median of 5) | 185 ms | 192 ms |
| Preview kernel (`profile_residual`, median of 300) | 0.23 ms | 0.24 ms |
| Peak RSS of the kernel process (`ru_maxrss`) | 64 MiB | 64 MiB |

**A thread-limit experiment, not a core-scaling study** (round 37). The kernel ran with the OMP,
OpenBLAS, MKL and vecLib thread variables set to 1 and compared against the inherited environment.
The differences are within run-to-run noise. The BLAS backend's effective thread counts are not
recorded, and the HTTP timings ran only in the inherited environment.

| End to end (`dipolar serve`, HTTP on loopback) | Value |
|---|---|
| Server start (to the ready file) | 596 ms |
| `fit.preview` over HTTP, 200 calls | median 18.6 ms, p95 20.4 ms |
| `fit.run` job, submit to finished (3 runs) | median 1.39 s |
| `fit.run` with profile intervals | 7.7 s |
| `view.highlight` then `render.describe_view` (50 runs) | median 5.0 ms, p95 6.0 ms |
| `render.view_svg` (50 calls) | median 2.6 ms |
| Server RSS, sampled once after the runs | 77 MiB |
| Peak RSS of the server and its worker processes | **not measured** |
| Output sizes | run result 6.6 kB; SVG 4.2 kB; project export 10.2 kB; journal 56 kB after the session |

**Numerical agreement**, against the frozen fixture from the independent reference implementation:

| Quantity | Difference | Tolerance |
|---|---|---|
| φ | 2.4e-9° | 1e-4° |
| Szz | 6.6e-12 | 1e-6 |
| Δ | 2.8e-11 | 1e-6 |
| χ² | relative 2.7e-13 | relative 1e-6 |

**Legacy acceptance rate: not measured** (corrected in round 37).
- **What B08 establishes:** the 1998 grid search accepts a point when |Dobs − Dcalc| ≤ 10·|Dobs|
  for every coupling. That is the default allowance, 1000% relative. The rate it gives depends on
  the data and is not established.
- **Why it cannot be measured here:** that needs the 1998 fit pipeline, which is not compiled. The
  legacy harness compiles only the 1998 solver routines (eigenvalues, linear systems). They are
  wrong in 5 of their 7 frozen cases, which says nothing about acceptance.
- **The legacy numbers are not a target**, because the fit semantics differ (D3).

**Observations for M3.** These are hypotheses: the components are not timed separately
(round 37).
- **A preview over HTTP costs about 80× the kernel timing** (18.6 ms vs 0.23 ms). The kernel
  timing excludes what the operation also does: build and check the problem from the project, solve
  the order parameters, build the scientific output, validate, run the registry and the session,
  and the JSON and HTTP. That is well inside an interactive budget. The M3 preview p95 target will
  be set against an instrumented breakdown.
- **A fit job takes about 7× the warm kernel fit** (1.4 s vs 0.19 s). The likely cause is spawning
  one worker process per job (interpreter start and SciPy import), the limit recorded in M2 step 3.
  A warm worker pool would test that.

## Validation: round 37

Round 37 returned NOT READY, with three class-(A) findings and three class (B). All six are fixed
or documented above:

| # | Class | Finding | Resolution |
|---|---|---|---|
| 1 | A | **The cross-adapter test asserted only equality.** A dispatcher that refused every operation on both adapters still passed. | Each step now asserts its expected outcome, every operation must succeed at least once, and human accept and reject run successfully. The "refuse everything" mutation now fails. |
| 2 | A | **The running-fit check never compared results.** A mutation that made view changes shift φ by 10° still passed. | The held run must equal a baseline run on the same inputs, number for number, and the published run's record and blob must be unchanged. The mutation now fails. |
| 3 | A | **The legacy statement overstated B08.** It claimed the 1998 search accepts nearly every point, which B08 explicitly does not establish. | Replaced: the acceptance rate is not measured, and the record states only B08's established allowance. |
| 4 | B | **The core comparison claimed more than it tested.** | It is relabelled as a thread-limit experiment, with its environment recorded. |
| 5 | B | **The server's peak memory was not measured.** | Declared as not measured; the MiB figures are rounded correctly. |
| 6 | B | **Performance attributions were stated as fact.** | Labelled as hypotheses. |
