# ADR-0001: Python API-first scientific core (D1)

- **Status:** Accepted, 2026-11-07 (plan v0.6, Phase 1 baseline)
- **Source:** [D1](../03-redesign-plan.md#3-key-decisions)

## Decision

- `dipolar-core` is pure Python on NumPy/SciPy in float64: no I/O, no global state, no UI.
- Numba or JAX only after profiling shows a hot path; the kernel boundary allows a Rust (PyO3) replacement later.
- The headless application layer lives in a separate package, `dipolar-app` (04 §5).

## Consequences

- Revisit only if measured end-to-end latency targets fail after profiling, or the browser needs compute without Python.

## Verified by

`tests/test_boundaries.py` (core purity).
