# Benzene in ZLI-1132: experimental ¹H–¹H dipolar couplings (Phase 2 V0 corpus)

**Status: development data for V1** (rigid molecules from XYZ). It is not a holdout: its values
were seen during V0.1 (`docs/phase2/exposure-log.md`).

## Source and licence

A. S. Taggar, C. J. Campbell, A. Yethiraj and E. E. Burnell, "Testing Assumptions about Solute
Concentration Dependence in Liquid Crystal NMR", *J. Phys. Chem. B* **110**, 1363–1368 (2006),
**Supporting Information**, DOI [10.1021/jp052592j.s001](https://doi.org/10.1021/jp052592j.s001)
(ACS Figshare).

- **Licence of the Supporting Information:** [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/).
  This dataset is used non-commercially, with this attribution.
- **`source/jp052592j_si_001.txt`** is the file as published, byte for byte: SHA-256
  `a52e77b8061b010607d486548c62abb4f9a8f93dad3e4a2a4ff78f65e119dd29`, 2115 bytes. It was retrieved
  on 2026-11-18 (`docs/phase2/v0-sources.json`).
- **Changes made:** `couplings.csv` is **derived** from the source by `tools/datasets/taggar2006.py`.
  The changes are:
  - only the benzene section is kept;
  - the "value(uncertainty)" tokens are split into a value and σ;
  - spin labels are added;
  - the mixed-sample compositions are added from the paper's Tables 1–2 footnotes.

  No value is altered. **The derived CSV carries the same licence and the same non-commercial
  condition as the source.**
- **This directory is not covered by the repository's BSD-3-Clause licence.** It is kept for
  validation only. It is excluded from source archives, releases and packages (`.gitattributes`
  export-ignore; `docs/phase2/v0.1-selection.md` §5), and it can be removed on request
  (`datasets/README.md`).
- **The paper itself** (© 2006 American Chemical Society) is not reproduced here. Its published
  order parameters (Tables 1–2) are cited as comparison targets in V0.3, not stored.

## What the values are

- **The observable.** The source's **dipolar couplings D** (Hz), from LEQUOR fits of the proton
  spectra. They are *published effective D under the authors' spectral assumptions*.
  - They are kept as printed: the sign is as printed, no J is subtracted, and there is no factor
    of 2.
  - The isotropic J inputs for benzene are not given in the paper. The anisotropic-J treatment
    for benzene is not stated.
- **σ** is the printed uncertainty in the last digits: `-1024.174(15)` means D = −1024.174 Hz and σ = 0.015 Hz. Its
  confidence level and the covariance between couplings are **unspecified**. The three couplings
  of one sample come from one spectral fit, so they are probably correlated. Their use as
  weights is preregistered in V0.3.
- **The labels.** Benzene's protons are H1–H6 around the ring.
  - D12 is the **ortho** pair, `H1`–`H2`.
  - D13 is the **meta** pair, `H1`–`H3`.
  - D14 is the **para** pair, `H1`–`H4`.

  Under D6h each column is one pair orbit, so the rows are one estimate per orbit.
- **The frame of the published S_zz:** z normal to the ring, with S_xx = S_yy = −S_zz/2.

## Conditions and grouping (the group manifest)

- **The medium:** ZLI-1132. **The temperature:** a nominal setting of 300.9 K, made reproducible
  by a reference sample (±0.05 K). **The spectrometer:** Bruker AMX-500.
- **The samples:** 15 conditions, 45 values.
  - **Run 1.** One tube for the benzene series, with solute added sequentially: 1.31, 3.00,
    4.48, 5.14, 6.71 and 8.32 mol %. Plus `mix1`, a separate tube with all four solutes.
  - **Run 2.** A separate tube for each sample: 0.55, 1.101, 2.321, 2.921 and 4.969 mol %. Plus
    the mixed tubes `mix2.1`, `mix2.2` and `mix2.3`.
  - **Mixed-sample compositions** (mol % benzene/tfb/tcb/tbb):
    - `mix1`: 3.65/2.70/4.29/2.77;
    - `mix2.1`: 2.129/0/1.984/0;
    - `mix2.2`: 1.748/1.669/0.885/0.510;
    - `mix2.3`: 2.846/0/1.060/0.
- **Groups:**
  - the whole paper is one group;
  - Run 1's single-solute series shares one tube (not independent samples);
  - each mixed sample is linked to its co-solutes.

## The coupling ratios (V0.1)

- In the first row (Run 1, 1.31 mol %), D13/D12 = 0.194036 and D14/D12 = 0.126594. A rigid
  regular hexagon gives 0.192450 and 0.125000, so the measured ratios are 0.824 % and 1.275 %
  higher.
- A scale check against the paper's published S_zz is kept in the local, untracked target record
  (`datasets-local/benzene-taggar2006-targets/README.md`): the paper's values are © ACS and are
  not reproduced here (round 73).

## Columns of `couplings.csv`

`run, sample, benzene_mol_percent, co_solutes_mol_percent, coupling, class, spin_a, spin_b,
D_token, D_obs_Hz, sigma_Hz`.

`D_token` is the source's token, verbatim. `D_obs_Hz` and `sigma_Hz` are exact decimal readings
of it.

## Checks

- `uv run python tools/datasets/taggar2006.py --check` verifies the source's SHA-256, and that
  `couplings.csv` is exactly what the parser produces.
- `tests/test_v0_corpus.py` checks the counts, the token readings and the export-ignore. It skips
  if the dataset is removed.
