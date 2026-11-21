# Synthetic 1,4-dichlorobenzene: the fixed-geometry tutorial (Phase 2 V1.4)

**A test fixture, not experimental data.** Every coupling is computed from a stated geometry and
order tensor, then perturbed with seeded Gaussian noise (`generate.py`, NumPy only, independent of
the engine). It is covered by the repository's BSD-3-Clause licence.

## The molecule and the answer

- **Geometry:** a regular hexagonal ring in the xy plane (r_CC = 1.395 Å), Cl on C1 and C4 along x
  (r_CCl = 1.740 Å), H on C2, C3, C5 and C6 (r_CH = 1.080 Å). The file's coordinates are rounded to
  6 decimals, and they are the geometry the reference fit uses.
- **Symmetry:** D2h, with the input frame as its symmetry frame (x along Cl–Cl, z normal to the
  ring).
- **Order tensor:** diagonal in that frame, Sxx = 0.22 and Syy = −0.06, so Szz = −0.16 and
  Sxx − Syy = 0.28. D2h leaves these two components free; Sxy, Sxz and Syz are zero by symmetry.
- **Observations:** three pair orbits of two pairs each (ortho H2–H3 and H5–H6, meta H2–H6 and
  H3–H5, para H2–H5 and H3–H6). N = 3, d = 2, ν = 1. σ = 0.3 Hz, seed 20261120.

## The files

| File | What it is |
|---|---|
| `dichlorobenzene.xyz` | The geometry as a user's file: element symbols only, carbons, chlorines, then protons. The comment line lists the atom names (`atoms: C1 … H6`). Imported, the protons are named by atom number (H9 … H12). |
| `couplings.csv` | One row per pair orbit, with its class written out (`equivalent_pairs`), its multiplicity, D and σ in Hz. The labels H2 … H6 must be mapped to the imported protons: the tutorial's "confirm mapping" step. |
| `truth.json` | The truth, the noiseless and observed couplings, and the reference fit (weighted least squares in Sxx and Syy: the estimates, their covariance, χ²). |
| `expected/spec.json` | The frozen tolerances: the page's run against the robot's (`regression`), the engine against the reference fit (`reference`), and noiseless recovery. |

`python3 generate.py` rewrites the first three files byte for byte (a test checks it).

## The tutorial

Through the page (Data, then Fit, then Structure) or with the robot:

    python -I tools/robot/robot.py --ready-file DIR/serve.ready.json --scenario fixed-tutorial \
        --xyz datasets/dichlorobenzene-synthetic/dichlorobenzene.xyz \
        --csv datasets/dichlorobenzene-synthetic/couplings.csv

1. import the XYZ file; 2. declare D2h (the input frame, 0.01 Å); 3. choose the fixed-geometry
fit; 4. import the couplings, mapping H2, H3, H5, H6 to the protons the comment line names so;
5. run the fit; 6. select the worst row and see its whole orbit in the Structure view.

The expected answer: Szz = −0.15987 ± 0.00018 and Sxx − Syy = 0.28002 ± 0.00018, adequacy given
(χ² = 2.37, ν = 1, p = 0.124), physically admissible. `web/e2e/fixed-tutorial.spec.ts` checks that
the page and the robot give the same run, field by field.
