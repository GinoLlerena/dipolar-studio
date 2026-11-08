# ADR-0011: Durable runs and stale results (D11)

- **Status:** Accepted, 2026-11-07 (plan v0.6, Phase 1 baseline)
- **Source:** [D11](../03-redesign-plan.md#3-key-decisions)

## Decision

- Atomic chunk + manifest publication (chunks fsynced first); resume validates coverage and content.
- Edits mark earlier results stale; previews carry revision IDs; late responses are discarded.
- Canonical hash over model, observations, covariance, constants version, solver settings, plugins and seed.
- Cross-platform agreement by per-quantity atol + rtol, not byte identity.

## Verified by

M2 run tests.
