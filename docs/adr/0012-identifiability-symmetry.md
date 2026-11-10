# ADR-0012: Model-specific identifiability and symmetry (D12)

- **Status:** Accepted, 2026-11-07 (plan v0.6, Phase 1 baseline)
- **Source:** [D12](../03-redesign-plan.md#3-key-decisions)

## Decision

- Detect scale freedom and require an anchor only when the model has it.
- Enumerate model-specific equivalences and report the chosen domain (biphenyl: (±φ, Δ) at fixed labels; (180±φ, −Δ) only with the ring-B relabelling).
- Planar data constrain at most three S components, collinear at most one.
- Constraints named by basis and frame: C2(z) (legacy "D2"); diagonal tensor in a moving bisector frame (legacy "D4").
- The frame contract (active/passive rotation, axes, torsion sign, constraint basis) is frozen in M1.

## The frozen frame contract (M1 step 2)

The full text is in the `dipolar_core.biphenyl` module docstring. In short:

1. **Rotation.** Geometry is built by active rotations. A frame change is passive: coordinates
   become `axes @ v` and S becomes `axes S axesᵀ`, so every coupling is unchanged.
2. **Axes.**
   - `bisector` (the fixture's frame): z is the inter-ring axis, with ring A at z < 0; x bisects
     the ring planes.
   - `ring-a`: the same z, with x in ring A's plane on the C2 side.
3. **Torsion sign.** The IUPAC dihedral τ(C2–C1–C1′–C2′) is −φ. y → −y maps φ to −φ and negates
   Sxy and Syz. `domain="fixed-labels"`, φ ∈ [0°, 180°], is complete. `domain="acute"`,
   φ ∈ [0°, 90°], is the fixture's domain and the default. It is complete only if ring B's labels
   make the torsion acute, and wrong labels are not always detected (rounds 19 and 20).
4. **Constraint bases.**
   - `bisector-diagonal` ("D4"): t = (Szz, Δ′). In the ring-A frame it is the moving form
     Δ = Δ′cos δ, Sxy = ½Δ′sin δ with δ = −φ.
   - `c2z` ("D2"): (Szz, Δ, Sxy).
   - `c1`: all five components.

   The legacy D4 coefficient ½ sin²θ (cos 2ϕ + tan δ sin 2ϕ) is the moving form with
   Δ_legacy = Δ′cos δ.

At the D2d endpoint φ = 90° of the identical-ring template, the fit is labelled, not
constrained (`D2D_NOTE`). The label never applies to imported geometry.

## Verified by

Frame-contract tests in `packages/dipolar-core/tests/test_core_frames.py` (M1 step 2);
`datasets/*/expected/spec.json` records the fixture frame.
