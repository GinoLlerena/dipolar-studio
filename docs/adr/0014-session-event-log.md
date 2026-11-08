# ADR-0014: The headless session and its event log (D14)

- **Status:** Accepted, 2026-11-07 (plan v0.6, Phase 1 baseline)
- **Source:** [D14](../04-ai-ready-architecture.md#d14--the-headless-session-and-its-event-log)

## Decision

- Session = Project (science) + Workspace (view) + Jobs.
- Each accepted command appends events with seq, revision, actor, command, args hash, causation and inverse.
- The journal gives global chronological undo, audit, replay and live multi-client sync; optimistic concurrency via expected_revision.

## Verified by

Replay and REVISION_CONFLICT tests; M0 journal crash-recovery spike.
