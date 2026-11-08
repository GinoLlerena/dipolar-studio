# ADR-0010: Security and lifecycle of the local backend (D10)

- **Status:** Accepted, 2026-11-07 (plan v0.6, Phase 1 baseline)
- **Source:** [D10](../03-redesign-plan.md#3-key-decisions)

## Decision

- Loopback only, OS-assigned port, authenticated readiness handshake; per-launch secret never in URLs, logs or files.
- Host and Origin validation, CSRF protection, side-effect-free GET, strict CSP served by the backend.
- Project-scoped file handles, bounded uploads, points, memory and jobs; supervised worker processes.

## Consequences

- M0 spike with negative tests (DNS rebinding, missing Origin, token leakage).

## Verified by

M0 D10 spike.
