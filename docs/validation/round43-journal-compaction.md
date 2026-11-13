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
