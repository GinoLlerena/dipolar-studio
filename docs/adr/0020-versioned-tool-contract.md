# ADR-0020: Versioned tool contract (D20)

- **Status:** Accepted, 2026-11-07 (plan v0.6, Phase 1 baseline)
- **Source:** [D20](../04-ai-ready-architecture.md#d20--versioned-tool-contract)

## Decision

- The registry has its own semantic version; additive changes are minor, removals and renames major; deprecations keep working for one minor release.
- A conformance suite runs the registry examples on every adapter.

## Verified by

Contract suite (M0 slice onward).
