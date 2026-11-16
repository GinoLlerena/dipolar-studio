# File formats

Dipolar Studio reads two kinds of input file, couplings (CSV) and geometry (XYZ), and saves
projects as `.dipolar.json`. Every reader is **strict**: a problem is reported with its line or
row, and nothing is guessed or silently repaired.

## Couplings: CSV

One row per measured dipolar coupling. A header row names the columns.

| Column | Required | Meaning |
|---|---|---|
| `spin_a`, `spin_b` | yes | The two protons, by label (for example `H2` and `H3'`). Labels are kept exactly as written. |
| `D_obs_Hz` | yes | The measured **signed** dipolar coupling D, in Hz |
| `sigma_Hz` | yes | Its uncertainty σ, in Hz (positive). The fit weights each coupling by 1/σ². |
| `sigma_source` | no | Where σ comes from (for example "spectral analysis"); kept with the coupling |
| `multiplicity`, `equivalent_pairs` | no | A coupling that stands for several symmetry-equivalent pairs: their number, and the pairs themselves separated by spaces (`H2-H3 H5-H6`) |
| `observable`, `unit` | no | If present, `D` and `Hz` (the only ones supported) |

Other columns are allowed and reported as ignored.

**Numbers** are plain decimals with a point: `-1124.7`, `0.5`, `1.2e3`. A decimal comma
(`1,5`) is refused: in a comma-separated file it would split the field. A byte-order mark and
Windows line ends (from spreadsheet exports) are accepted.

Example, the synthetic biphenyl's first rows:

```csv
spin_a,spin_b,D_obs_Hz,sigma_Hz
H2,H2',-1124.726,0.5
H2,H3,-1966.69,0.5
H2,H3',-282.349,0.5
```

**Labels and mapping.** On import, the app proposes a mapping from your labels to the molecule's
protons (an exact label match is proposed, never assumed correct) and shows the difference with the
current couplings. You confirm or change the mapping before anything is applied.

- On the **biphenyl template**, the protons are `H2`–`H6` (ring A) and `H2'`–`H6'` (ring B).
- On **imported geometry**, each hydrogen is named by its atom number in the XYZ file (`H13` is
  the 13th atom), unless you map your own labels to them.

**Equivalent pairs** let one measured value stand for a class of pairs that are equivalent by
symmetry. The rules:

- the class lists the coupling's own pair, and `multiplicity` is the number of pairs in it;
- no pair belongs to two couplings (each pair is observed once);
- every pair of the class must be **equivalent under the model you fit**: the app checks that each
  gives the same calculated coupling as the coupling's own pair, whatever the order parameters,
  at several torsions, and refuses the class otherwise.

So whether a class is accepted depends on the geometry and the model. The template's D2 classes
(as in `datasets/biphenyl-synthetic/couplings.csv`) hold under the template's models, but not
under c2z or c1 on imported coordinates, where those pairs are no longer equivalent; a class that
does hold for your geometry and order model is accepted. When unsure, give each measured coupling
for one pair: that is always accepted.

Limits: up to 100 000 couplings in a project, and a couplings file of up to 1 MiB.

## Geometry: XYZ

The usual XYZ format: the atom count, a comment line, then one line per atom with its element and
x, y, z in ångström.

```text
22
synthetic biphenyl, phi = 37.0 deg
C 0.000000 0.000000 -0.744500
C 1.147318 0.383887 -1.443000
...
H 2.037577 0.681764 -0.901000
```

(Abridged from `datasets/biphenyl-synthetic/biphenyl.xyz` in the repository, the tutorial's
geometry.)

- Elements: H, D, C, N, O, F, P, S, Cl, Br, I. Up to 1 000 atoms.
- Coordinates are plain decimals, as above.
- Every hydrogen becomes a proton of the project. Declare the fitted torsion with four atom
  indices (counted from 0 in the order of the file): a, i, j, b, where i–j is the rotating bond.

## Projects: `.dipolar.json`

**Export** in the Data tab saves the whole project: geometry, protons, couplings with their σ and
sources, and the model. **Load a project file…** reads it back, also into another installation.
Files are versioned: an older file is upgraded when it is read; a file from a newer version is
refused rather than guessed at.
