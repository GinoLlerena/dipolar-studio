# Validation rounds 43–44: journal compaction

Reviewer: GPT-6.1-Sol (Codex, reasoning effort high), independent of the implementation.
Under the medium plan there are at most two rounds per step. Class (A) findings block; class (B)
findings are documented.

## What the step delivers

Journal compaction (ADR-0014 amendment; `dipolar_app.snapshot`): verified snapshots of the whole
session state, automatic compaction every 5 000 records, archived (never deleted) journal
segments, a bounded request table (10 000 outcomes), and recovery from a crash between the
snapshot and the journal rotation. Existing journals open unchanged; the first compaction happens
once 5 000 records follow the start (or the last snapshot).

## Before review

Tests: `test_app_snapshot.py` (10). A state that uses every field of `SessionState` round-trips;
after compaction the project reopens with the same state and request table, a retried request is
still answered from the table, work continues and replays through the snapshot; the crash between
the two steps is recovered; damage is refused (checksum, metadata, discontinuous journal, covered
records that disagree, numerical context); the request table and the automatic trigger are
bounded; an incomplete codec stops compaction before any file is written.

Mutation checks (each break makes a test fail): the checksum check; the comparison of covered
records with the snapshot; the request bound; the automatic trigger; the numerical-context check;
the recorded-sequence check; the journal rotation; the build-time round-trip guard.

## Round 43: NOT READY (one A, three B), on commit 4382819

The reviewer's run: 790 passed, mypy and Ruff passed. Windows power-loss behaviour was not tested
experimentally.

| # | Class | Finding | Resolution |
|---|---|---|---|
| 1 | A | **A crash in a second or later compaction made the project unopenable.** The new snapshot replaced the old one before the journal rotated; the journal then started after the old snapshot, which no longer existed, and the "starts at 1" recovery did not apply. An injected directory-fsync failure after the replacement did the same while the session kept accepting commands. | The previous snapshot is kept until the new one is complete: next snapshot (`project.snapshot.next.json`), then rotation, then publication by rename. Opening decides from the journal's first sequence number whether to discard or promote the next snapshot (`snapshot.choose`, `settle`); the replay-and-compare path is gone. Any failure after the next snapshot fail-stops the session. Tests: a crash before the rotation (first and later compaction), after it (empty or missing journal), a journal that continues neither snapshot, a failed rotation (fail-stop, then reopening recovers). |
| 2 | B | Compaction is costly: 34 MB of JSON, 5.4 s, 590 MB for 100 undo entries of a 1 000-coupling project, under the writer lock. | Documented in the ADR-0014 amendment, with the numbers. Deduplicating history payloads and building outside the lock are left for later. |
| 3 | B → fixed | Failed snapshot writes left temporary files, one per retry. | `write` removes its temporary file (and an unconfirmed result) on any failure; opening removes leftovers. Tests added. |
| 4 | B → documented | An evicted `fit.run` retry submits a second job: its science revision has not advanced. | The module docstring and the ADR now say that deduplication protection expires and that a revision check helps only when the revision has advanced. A test pins the behaviour. |

Mutation checks: discarding before the rotation, promoting after it, the cleanup of a failed write,
the cleanup at open, the order of rotation and publication, and the fail-stop on a failed rotation
each make a test fail when broken.

## Round 44: NOT READY (one A, one B), on commit a2c1c6f

The reviewer confirmed the round-43 fix by exercising 96 compaction and 40 recovery
process-crash points, I/O-error probes and 12 edge cases: a one-record overlap chooses the
current snapshot; equal or older next snapshots are discarded; damaged next snapshots are refused;
read-only replay and opening agree; promotion and discard survive crashes; failed-write cleanup
never touches the durable snapshot (the only production caller writes the next snapshot).
797 passed; mypy and Ruff passed.

| # | Class | Finding | Resolution |
|---|---|---|---|
| 1 | A | **Recovery could publish a snapshot before its archive was durable.** After a crash between moving the journal into `archive/` and fsyncing that directory, reopening promoted the next snapshot and accepted commands without fsyncing `archive/`; a later power loss could lose the archived segment. | `settle` fsyncs `archive/` and the project directory before it publishes the next snapshot. Test: `promotion makes the archive durable before publishing` (call order). |
| 2 | B → fixed | **Deleting the active journal silently rolled the state back** to the snapshot; the next commit reused a sequence number. | `Journal.created` records that opening had to create the journal; with a snapshot present and no interrupted compaction to explain it, opening refuses (`JournalCorrupt`, "only archive/ segments may be deleted"). Test added. |

Both fixes were mutation-checked. Under the cap, they were not reviewed again.

## Known limits (B, documented)

- **Cost under the writer lock** (round 43): about 5 s and 590 MB for 100 undo entries of a
  1 000-coupling project, once every 5 000 records.
- **Deduplication expires** after 10 000 newer requests; an evicted `fit.run` retry submits again.
- **Hardware power loss was not tested**; the procedure relies on fsync of files and directories
  (a no-op for directories on Windows, where NTFS journals metadata).
- An emptied (truncated, not deleted) active journal cannot be told apart from one just rotated.
