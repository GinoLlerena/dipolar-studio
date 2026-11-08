# ADR-0017: Agent-safety primitives built into Phase 1 (D17)

- **Status:** Accepted, 2026-11-07 (plan v0.6, Phase 1 baseline)
- **Source:** [D17](../04-ai-ready-architecture.md#d17--agent-safety-primitives-built-into-phase-1)

## Decision

- Actor and tier (read / propose / apply / admin) derived from the credential, never from arguments.
- Dry run on every command; proposals for propose-tier mutations, accepted by a human; per-actor budgets.
- Inputs are data, never instructions; seeds explicit; runs reproducible.

## Verified by

Robot-user tests (M2/M3).
