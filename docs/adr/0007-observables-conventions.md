# ADR-0007: Observables and conventions (D7)

- **Status:** Accepted, 2026-11-07 (plan v0.6, Phase 1 baseline)
- **Source:** [D7](../03-redesign-plan.md#3-key-decisions)

## Decision

- K = −(μ0/4π)·γiγj·ħ/(2π) from a versioned nuclide table; couplings stored in Hz, distances in Å.
- Observable records carry value, unit, type, sign status, isotopes, uncertainty and its source.
- Beta scope: signed dipolar D only. Total couplings and ²H quadrupolar data enter in Phase 2 (V4) with their own schemas.
- S = ½⟨3ccᵀ − I⟩; principal values ordered |Szz| ≥ |Syy| ≥ |Sxx|; degenerate axes labelled nonunique.

## Verified by

Analytical coefficient tests (M1).
