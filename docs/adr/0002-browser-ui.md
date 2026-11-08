# ADR-0002: Browser UI on web technology (D2)

- **Status:** Accepted, 2026-11-07 (plan v0.6, Phase 1 baseline)
- **Source:** [D2](../03-redesign-plan.md#3-key-decisions)

## Decision

- React + TypeScript (strict) with a react-three-fiber viewer; `dipolar serve` opens it on localhost.
- The browser is the beta's only UI path (owner decision 2026-11-07); a Tauri desktop shell is deferred.
- The UI is a thin client of the operation registry (ADR-0013): no business logic, no private API.

## Consequences

- Desktop packaging questions move after the beta; localhost security (ADR-0010) becomes critical.

## Verified by

CI job `web` (strict typecheck and build).
