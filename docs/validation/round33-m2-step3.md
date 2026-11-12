# Validation rounds 33–34: M2 step 3 (jobs, D11 runs, event stream)

Reviewer: GPT-6.1-Sol (Codex, reasoning effort high), independent of the implementation. Under
the medium plan there are at most two rounds per step. Class (A) findings block; class (B)
findings are documented.

## Round 33: NOT READY (eight A, one B), on commit 52d8899

The reviewer's other checks passed:
- 80 more cancel and double-finish races;
- pruning and replay checks;
- idempotent retries after pruning and after a restart;
- the snapshot comparison.

| # | Class | Finding | Resolution |
|---|---|---|---|
| 1 | A | **An infrastructure error killed a worker for good.** A spawn failure or a blob-write `OSError` left the job queued forever and the queue unserviced. | `_work` catches any infrastructure exception, fails the job (`INTERNAL`) and keeps the worker. Tests: `test_an_infrastructure_failure_fails_the_job_and_the_worker_lives_on`, `test_a_spawn_failure_fails_only_its_job`. |
| 2 | A | **Blocking IPC defeated timeout, cancel and shutdown.** A child that sent a partial message blocked `recv()` past every deadline. | The child writes its outcome to a private file and exits. The parent waits on the process sentinel in 50 ms slices and reads the file only after the exit, so it never blocks for longer than one slice. Termination is bounded (terminate, then kill, each with a 2 s join). Test: `test_a_process_job_times_out_within_its_budget`. |
| 3 | A | **The new `runs/` directory was not durable.** Its parent directory was never fsynced. | `BlobStore.put` fsyncs the parent after creating the directory. Test: `test_the_blob_directory_is_made_durable`. |
| 4 | A | **Disconnects leaked event-stream slots.** The slot was released only inside the generator, so a disconnect before the first chunk, or a failed send, kept it for good. | `_CountedStream` releases the slot around the whole ASGI response, and on collection if the response is never sent. Test: `test_disconnected_event_streams_free_their_slots`. |
| 5 | A | **A new subscription could skip a commit.** The state and the cursor were read separately. | A commit now sets the state, runs the listeners and publishes its feed entry under one lock. `Session.snapshot()` returns the state and the cursor together, and `hello` uses that pair. Test: `test_a_snapshot_never_pairs_a_new_state_with_an_old_cursor`. |
| 6 | A | **Read-tier waits could starve commands.** Forty `job.wait` calls held every thread of the shared pool. | At most `MAX_BLOCKING_WAITS` (8) waits block at once. A wait beyond that returns the status immediately. Together with the 8 streams, at most 16 of the 40 pool threads can block. Test: `test_blocking_waits_are_capped_so_commands_keep_their_threads`. |
| 7 | A | **A damaged blob was reused.** `put` trusted an existing file. | `put` reuses a blob only if its content verifies; otherwise it rewrites it atomically. Test: `test_a_damaged_blob_is_rewritten_when_the_same_result_is_published`. |
| 8 | A | **An accepted fit reported `proposed_by: null`.** The proposer was stamped on the event after the step's result had been built, and an idempotent retry stored the wrong answer. | Acceptance re-reads every reported job from the state that the stamped events produce. Test: `test_an_accepted_fit_reports_its_proposer`. |
| 9 | B | **Blob storage is not bounded by state pruning.** Pruned runs and dropped late results leave blobs on disk. | Documented. Garbage collection must keep every blob that a journal record references (replay verifies them), so it belongs with journal snapshots and compaction. |

## Round 34 (final under the cap): NOT READY (five A, one B), on commit 81a78df

The reviewer confirmed the following held up: worker recovery, stream-slot cleanup, listener lock
ordering, paired snapshots, the wait cap and proposer stamping. Five siblings were found. All are
fixed and mutation-checked, and, under the two-round cap, **not reviewed again**.

| # | Class | Finding | Resolution |
|---|---|---|---|
| 1 | A | **Spawning still sent the project through a pipe.** `Process.start()` pickled the input snapshot into the bootstrap pipe, so a stalled child could block before any timeout. | The input goes to a private file (the 0700 temporary directory), and the process receives two short paths. Test: `test_a_worker_receives_its_input_through_a_file`. |
| 2 | A | **Two first results could race to create `runs/`.** One got `FileExistsError`, and its valid job failed. | The directory is created and its parent fsynced under a lock, so other publishers wait until it is durable. Test: `test_concurrent_first_publications_both_succeed`. |
| 3 | A | **Non-UTF-8 damage defeated the repair.** `text()` raised `UnicodeDecodeError`. | A decoding failure counts as damage, and the blob is rewritten. Test: `test_a_blob_that_is_not_utf8_is_treated_as_damaged`. |
| 4 | A | **Progress could go from `cancelled` back to `running`.** A cancel committed between the worker's check and `set_live`. | `set_live` checks the job under the same lock that publishes commits, and never announces progress for a finished or missing job. Test: `test_a_finished_job_never_goes_back_to_running`. |
| 5 | A | **New project directories were not durable.** `serve` created the project directory and missing ancestors without fsyncing their parents. | `make_durable_dirs` creates each missing directory (mode 0700) and fsyncs its parent before any work is accepted. Test: `test_new_project_directories_are_made_durable`. |
| 6 | B | **Outcome size was unbounded.** The parent loaded the whole outcome file. | The parent refuses an outcome above 16 MiB before loading it. Test: `test_an_oversized_outcome_is_refused`. |

## Documented limits (B)

- **Blob growth** (finding 9).
- **One spawned process per job.** Starting each worker costs about 1–2 s of interpreter and SciPy
  import time. A warm pool can come later.
- **Thread mode** (tests only) cannot interrupt a running computation; its late result is dropped.
- **No progress beyond `running`.** The fitter exposes no progress callback.
- **Waits beyond the cap** return at once rather than queueing.
- **Outcome parsing** reads up to 16 MiB in the server process, without checking for cancellation
  while it parses (round 34).
- **Directory durability rests on the platform's fsync.** It was checked by instrumentation; power
  loss was not simulated, consistent with the beta scope (spike 4).
- **The event stream starts again on every boot.** A client resyncs (the `boot_id` changes), and
  entries older than the last 1000 are dropped, which also triggers a resync.
