# ADR-0014: The headless session and its event log (D14)

- **Status:** Accepted, 2026-11-07 (plan v0.6, Phase 1 baseline)
- **Source:** [D14](../04-ai-ready-architecture.md#d14--the-headless-session-and-its-event-log)

## Decision

- Session = Project (science) + Workspace (view) + Jobs.
- Each accepted command appends events with seq, revision, actor, command, args hash, causation and inverse.
- The journal gives global chronological undo, audit, replay and live multi-client sync; optimistic concurrency via expected_revision.

## Recovery policy (M0 spike 4, 2026-11-08)

- A torn tail (bytes after the last newline) was never acknowledged. It is copied to a private
  quarantine file and then truncated, with every step fsynced, and `serve` reports it.
- A damaged complete line may have been acknowledged. It is refused and the file is left
  untouched.
- After a journal failure the session stays fail-stopped until it restarts (fsync errors cannot
  be retried safely).

## Verified by

Replay and REVISION_CONFLICT tests; `spikes/test_spike_journal_crash.py` (SIGKILL loop, real server
restart); recovery unit tests in `test_app_journal.py`. Evidence:
[docs/spikes/m0-spikes.md](../spikes/m0-spikes.md#4-journal-crash-recovery).
