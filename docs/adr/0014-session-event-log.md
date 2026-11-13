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

## Compaction (after M3 step 2, 2026-11-13)

The journal and the request table no longer grow for ever (`dipolar_app.snapshot`).

- **A snapshot** (`project.snapshot.json`) is the whole session state at one sequence number:
  project, view, undo and redo stacks, proposals, jobs, runs, ID counters and the most recent
  10 000 request outcomes, with the revisions, science hash, schema versions, numerical context
  and a checksum. It is written only after decoding it reproduces the in-memory state exactly.
- **Compaction** runs automatically after 5 000 records since the last snapshot (after a commit,
  or when a project opens), and keeps the previous snapshot until the new one is complete
  (round 43): (1) the new snapshot is written atomically as `project.snapshot.next.json`;
  (2) the covered journal moves to `archive/project.events.<first>-<last>.jsonl` and an empty
  journal starts; (3) the new snapshot is renamed over `project.snapshot.json`. Nothing is
  deleted; archives keep the audit trail.
- **Opening** tells from the journal where a crash stopped: a journal that still starts right
  after the current snapshot means the rotation never happened (the next snapshot is discarded);
  an empty or missing journal, or one that starts right after the next snapshot, means it did
  (the next snapshot is promoted). Any other journal is refused. Replay then starts from the
  chosen snapshot, verified, and the first record must continue its sequence. Temporary files
  from an interrupted snapshot write are removed.
- **Bounded deduplication:** protection expires. A retry of a request older than the last
  10 000, after a compaction, is treated as new. An expected revision then protects only if that
  revision has advanced since: `fit.run`, which does not advance the science revision, would
  submit a second job (round 43).
- A failed snapshot write leaves everything as it was, with no file left behind (the commits are
  durable; compaction is retried after the next commit). A failure after it (archive, rotation,
  publication) fail-stops the session like a failed append; reopening finishes or discards the
  compaction.
- **Cost:** compaction encodes and verifies the whole state under the writer lock. Round 43
  measured 100 undo entries of a 1 000-coupling project at about 34 MB of JSON, 5.4 s and
  590 MB peak memory; commands wait meanwhile, once every 5 000 records. Deduplicating the
  history's project payloads and preparing the snapshot outside the lock are left for later.

## Verified by

Replay and REVISION_CONFLICT tests; `spikes/test_spike_journal_crash.py` (SIGKILL loop, real server
restart); recovery unit tests in `test_app_journal.py`; compaction in `test_app_snapshot.py`. Evidence:
[docs/spikes/m0-spikes.md](../spikes/m0-spikes.md#4-journal-crash-recovery).
