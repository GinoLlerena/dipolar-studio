# ADR-0008: The UI is a client of the engine (D8)

- **Status:** Accepted, 2026-11-07 (plan v0.6, Phase 1 baseline)
- **Source:** [D8](../03-redesign-plan.md#3-key-decisions)

## Decision

- The Python API and CLI come first; the UI uses the same registry operations.
- Third-party plugin APIs are frozen only after a real second model exposes the boundary.

## Verified by

Dependency-boundary tests (M3).
