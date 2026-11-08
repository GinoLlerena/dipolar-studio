# ADR-0006: File formats (D6)

- **Status:** Accepted, 2026-11-07 (plan v0.6, Phase 1 baseline)
- **Source:** [D6](../03-redesign-plan.md#3-key-decisions)

## Decision

- `*.dipolar.json` (science, schema-versioned with migrations), `*.workspace.json` (view), `*.events.jsonl` (journal).
- Runs: `run.json` (immutable input snapshot, hash, versions, seed) plus Parquet chunks.
- The legacy `.prj` importer is gated (M-L).

## Verified by

M1 JSON v1 round-trip tests.
