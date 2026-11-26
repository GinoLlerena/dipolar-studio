# Reproducing benzene in ZLI-1132 with Dipolar Studio 0.2.0b1

This guide is the outside reproduction exercise of Dipolar Studio's Phase 2 verification
([plan](v1.5-plan.md), [gate ledger](verification/gates.md)). You start from the published
source and work through to the fits:

1. download the authors' supporting information and check its bytes;
2. extract the benzene dipolar couplings yourself;
3. compute the molecule's geometry yourself;
4. fit all 15 conditions in the released app.

When the project has published its own counts, you compare your fits with the paper. Allow
1 to 3 hours.

The data are from A. S. Taggar, C. J. Campbell, A. Yethiraj and E. E. Burnell, "Testing
Assumptions about Solute Concentration Dependence in Liquid Crystal NMR", *J. Phys. Chem. B*
**110**, 1363–1368 (2006), [doi:10.1021/jp052592j](https://doi.org/10.1021/jp052592j). The
supporting information is published under CC BY-NC 4.0.

Record everything in the [evidence worksheet](reproduce-benzene-worksheet.md) as you go.

## Who can take part

You qualify if you are none of these (decision 8):

- the project's owner;
- the 1998 thesis co-authors or their advisor;
- Dipolar Studio contributors;
- anyone who prepared this exercise or had advance access to the project's reference result.

The owner gives you an **opaque participant ID** (`P-` and three digits). Your name and contact
details stay with the owner and never enter the repository.

## Step 1. Install the release

Use the release [v0.2.0b1](https://github.com/GinoLlerena/dipolar-studio/releases/tag/v0.2.0b1),
not the source repository. Make a fresh Python 3.12 (or newer) environment, then install its two
wheels:

```bash
python3 -m venv benzene-env
source benzene-env/bin/activate        # Windows: benzene-env\Scripts\activate
pip install dipolar_core-0.2.0b1-py3-none-any.whl dipolar_app-0.2.0b1-py3-none-any.whl
dipolar --version
```

`dipolar --version` must print exactly
`dipolar 0.2.0b1 (dipolar-core 0.2.0b1, contract 0.12.0)`. Copy that line into the worksheet.

Start the app on a new, empty directory (a directory written by Dipolar Studio 0.1 is refused):

```bash
dipolar serve --project-dir ~/dipolar/benzene/run1-1.31 --open
```

**Optional practice:** the synthetic 1,4-dichlorobenzene example in
[getting started](../user/getting-started.md) goes through the same steps with a known answer.

## Step 2. The source and the couplings

Download `jp052592j_si_001.txt`, the supporting information, from its
[ACS Figshare page](https://acs.figshare.com/articles/dataset/Testing_Assumptions_about_Solute_Concentration_Dependence_in_Liquid_Crystal_NMR/3241549).
Save the file as downloaded. Do not open and save it in an editor, which can change its line
endings. Check its bytes before you read it:

```bash
shasum -a 256 jp052592j_si_001.txt                              # macOS, Linux
Get-FileHash jp052592j_si_001.txt -Algorithm SHA256             # Windows PowerShell
```

The file has 2115 bytes, and its SHA-256 must be
`a52e77b8061b010607d486548c62abb4f9a8f93dad3e4a2a4ff78f65e119dd29`.

### If the hash does not match

Stop the attempt: do not parse or fit anything from that file. Note the hash you got in the
worksheet and tell the owner. The owner tries the publisher's versioned file or the original
download URL (decision 10). A scored attempt needs the original bytes, line endings included.

### Reading the couplings

The file's first section, "DipolarCouplings for benzene", has one row per sample and three
columns, D12, D13 and D14. Each value is printed as a `value(uncertainty)` token, where the
uncertainty is in the last printed digits: `-123.456(78)` means D = −123.456 Hz and σ = 0.078 Hz.
(That token is an invented example.)

- Keep the printed sign and every printed digit. Do not round, and do not change the sign.
- Make one CSV file per condition with the header `spin_a,spin_b,D_obs_Hz,sigma_Hz` and three
  rows, one per coupling, on these pairs:

| Coupling | Pair class | spin_a | spin_b |
|---|---|---|---|
| D12 | ortho | `H1` | `H2` |
| D13 | meta | `H1` | `H3` |
| D14 | para | `H1` | `H4` |

Under D6h each coupling is one pair orbit, so these pairs are one representative each for D12,
D13 and D14. Leave `multiplicity` and `equivalent_pairs` out: the app fills them in from the
orbit.

### The 15 conditions

Fit every condition: there are 15 conditions with 3 couplings each, 45 couplings in all. A
condition is named by its run and its sample, as the source prints them. For the mixed samples,
the name is a label.

| Run | Sample | Your CSV file |
|---|---|---|
| 1 | `1.31` |  |
| 1 | `3.00` |  |
| 1 | `4.48` |  |
| 1 | `5.14` |  |
| 1 | `6.71` |  |
| 1 | `8.32` |  |
| 1 | `mix1` |  |
| 2 | `0.55` |  |
| 2 | `1.101` |  |
| 2 | `2.321` |  |
| 2 | `2.921` |  |
| 2 | `4.969` |  |
| 2 | `mix2.1` |  |
| 2 | `mix2.2` |  |
| 2 | `mix2.3` |  |

## Before you fit

Do not fit any condition until the owner confirms two entries in the project's first-fit log
(the [gate ledger](verification/gates.md), §10):

- the owner's `freeze approved` row, which freezes the gates for every fit of experimental data;
- a `submission` row for your attempt, with the release and the protocol revision.

Until then you may install the release, check the source, and prepare your CSV and XYZ files. A
fit made before both entries cannot be scored. This applies to a trial fit too.

## Step 3. The geometry, the symmetry and the fits

### Compute the geometry

The geometry is frozen in the project's preregistration (V0.3,
[`v0.3-preregistration.json`](v0.3-preregistration.json), its `geometry` and its benzene
`ring_positions`). You may read the constants and angles there, but compute the coordinates
yourself:

- r_e(CC) = 1.3914 Å and r_e(CH) = 1.0802 Å (Gauss and Stanton, 2000; equilibrium values);
- a planar regular hexagon: each carbon at radius r_e(CC) from the centre, and each proton
  radially outward from its carbon, at radius r_e(CC) + r_e(CH);
- at angle θ and radius R, x = R cos θ, y = R sin θ, z = 0, so the ring lies in the xy plane and
  z is normal to the ring.

| Proton | Its carbon | Angle |
|---|---|---|
| `H1` | `C1` | 0° |
| `H2` | `C2` | 60° |
| `H3` | `C3` | 120° |
| `H4` | `C4` | 180° |
| `H5` | `C5` | 240° |
| `H6` | `C6` | 300° |

Write the XYZ file with the six carbons first, C1 to C6, then H1 to H6. In the app, each hydrogen
is named by its atom number, so your H1 is the 7th atom. When you import the couplings, map your
labels to those protons. Record in the worksheet how you computed the coordinates (the tool or
the program, and the formula), the number of decimal places, and the axes.

### Coordinate precision

Write the coordinates with **12 or more decimal places**. The owner then checks your S_zz against
the project's reference within 1e-8 (absolute).

- With 8 to 11 decimal places, the owner adds an allowance. It is
  the absolute change in the reference S_zz, condition by condition,
  when the reference coordinates are rounded to your precision, in the input XYZ frame. The owner
  computes it with identical couplings, mapping and settings, before looking at your estimates,
  and checks your S_zz within 1e-8 plus that allowance.
- With fewer than 8 decimal places, regenerate the XYZ with more.

### Declare the symmetry and fit

The symmetry is **D6h**, with z′ along the six-fold axis, normal to the ring, and x′ through H1
(a C2′ axis). In the app, the axes are rows in your file's coordinates:

| Axis | Row |
|---|---|
| x′ | `1 0 0` |
| y′ | `0 1 0` |
| z′ | `0 0 1` |

For each condition, in **a fresh project directory for each condition** (or, in one project,
after checking that all three couplings were replaced):

1. **Data → Import XYZ geometry…**, your file.
2. In the **Symmetry** form, declare D6h with the axes above.
3. Choose the model **Fixed geometry (no torsion)** and apply it.
4. Import the condition's CSV and confirm the mapping of `H1`, `H2`, `H3` and `H4` to the protons
   of atoms 7, 8, 9 and 10.
5. **Fit → Run fit.** The Fit tab shows S_zz. It must be **estimated**, with the rank
   **verified**.

### Save the selected run

Save each condition's run at full precision, with the installed Python client connected to the
running app. In the Fit tab's list of runs, choose the run to save, and copy its ID (for example
`run_000001`). Run this with the environment's Python while `dipolar serve` runs. Set the two
paths and the run's ID first:

```python
PROJECT_DIR = "~/dipolar/benzene/run1-1.31"  # this condition's project directory
OUT = "run1-1.31.run.json"  # where to save the run
RUN_ID = "run_000001"  # the run you chose, by its ID in the Fit tab's list of runs
import json
from pathlib import Path

from dipolar_app.api import Studio

with Studio.connect(Path(PROJECT_DIR).expanduser() / "serve.ready.json") as studio:
    listed = [r for r in studio.call("run.list")["runs"] if r["id"] == RUN_ID]
    if not listed:
        raise SystemExit(f"{RUN_ID} is not a run of this project")
    if listed[0]["stale"]:
        raise SystemExit(f"{RUN_ID} is stale: the project changed after it. Fit again, and save the new run.")
    got = studio.call("run.get", run_id=RUN_ID)
    if got["run"]["stale"]:  # read with the result: the project may change during the save
        raise SystemExit(f"{RUN_ID} became stale while it was read. Fit again, and save the new run.")
    result = got["result"]
Path(OUT).write_text(json.dumps(result, indent=2), encoding="utf-8")
szz = next(c for c in result["components"] if c["name"] == "Szz")
print("S_zz", szz["status"], repr(szz["estimate"]), "rank verified:", result["rank"]["verified"])
assert szz["status"] == "estimated" and result["rank"]["verified"]
```

S_zz is the component named `Szz` in `result["components"]`. A run is **stale** when the project
changed after it, for example when its couplings were replaced. The snippet refuses a stale run,
including one that becomes stale while it is read.
Keep the saved files: the owner checks them in a private session (see the end of this guide).

## Step 4. Compare with the paper

Do this step only after the owner has signed the benzene spot-check and published the project's
counts on the [benzene verification page](https://github.com/GinoLlerena/dipolar-studio/blob/main/docs/phase2/verification/benzene.md).
Until then, the page shows `pending` and zero compared cells.

1. Read the 15 published S_zz values and their printed uncertainties from the paper's Tables 1
   and 2 yourself.
2. For each condition, apply the frozen criterion (V0.3 §6, independent support). Your S_zz
   agrees with the paper's when |S − S_pub| ≤ 0.05·|S_pub| + 2p, where p is the printed
   uncertainty. A condition whose fit has no verified rank, or that has no published value, is
   pending.
3. Count the conditions **compared, agreeing, disagreeing and pending**. Compare those counts
   with the published counts for the same protocol revision, and record both in the worksheet.

A disagreement with the paper does not fail your reproduction (decision 2A). Whether the model is
adequate (the fit's adequacy flag) is recorded separately.

## What counts as copying

The exercise checks that a reader of the paper can get from the source to the fits. These count
as copying, and an attempt that uses any of them is not scored:

- anything from the repository's `datasets/benzene-zli1132-taggar2006/` (its couplings, its CSV
  or its copy of the source);
- an XYZ file from the repository, or a geometry file made by a project-provided JSON-to-XYZ tool;
- a prepared CSV of the couplings;
- a project file, or a symmetry declaration, prepared by someone else.

You may read the frozen constants and angles in the preregistration, and the project's
documentation.

## What stays on your computer

Keep on your own computer the paper's targets, your margins and signed differences, your
screenshots and your raw reports. Do not post any of them in a public issue, a discussion or a pull
request.

Send the owner only the completed worksheet and the saved run files, through the private channel
the owner gives you (decision 9). The owner checks your fits against the project's reference in
a local session. The repository records only a sanitized receipt keyed by your opaque
participant ID: the release, the protocol revision, the number of conditions, the match status
and the counts.

A problem with the software itself, such as an install failure, a crash or a confusing message,
can be reported as a [public issue](https://github.com/GinoLlerena/dipolar-studio/issues). Leave
out any value from the paper or from your fits.
