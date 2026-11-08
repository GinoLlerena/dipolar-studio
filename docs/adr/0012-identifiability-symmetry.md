# ADR-0012: Model-specific identifiability and symmetry (D12)

- **Status:** Accepted, 2026-11-07 (plan v0.6, Phase 1 baseline)
- **Source:** [D12](../03-redesign-plan.md#3-key-decisions)

## Decision

- Detect scale freedom and require an anchor only when the model has it.
- Enumerate model-specific equivalences and report the chosen domain (biphenyl: (±φ, Δ) at fixed labels; (180±φ, −Δ) only with the ring-B relabelling).
- Planar data constrain at most three S components, collinear at most one.
- Constraints named by basis and frame: C2(z) (legacy "D2"); diagonal tensor in a moving bisector frame (legacy "D4").
- The frame contract (active/passive rotation, axes, torsion sign, constraint basis) is frozen in M1.

## Verified by

Frame-contract tests (M1); `datasets/*/expected/spec.json` records the fixture frame.
