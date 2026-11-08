# ADR-0018: Long-running work is a resource (D18)

- **Status:** Accepted, 2026-11-07 (plan v0.6, Phase 1 baseline)
- **Source:** [D18](../04-ai-ready-architecture.md#d18--long-running-work-is-a-resource-never-a-blocking-call)

## Decision

- Long operations return a JobId; progress streams as events; `job.wait` bounded to 30 s; `job.cancel` is a normal command.

## Verified by

Job runner tests (M2).
