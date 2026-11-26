# Dipolar Studio 0.1.0b1: a guide for beta testers

Thank you for testing Dipolar Studio. This beta fits the **inter-ring torsion** and the
**orientational order** of a biphenyl-type molecule dissolved in a liquid crystal, from its NMR
dipolar couplings. It runs locally: a small server and the app in your browser.

This guide is for the **0.1.0b1** release, and its links point to that release's documents. The
8CB exercise uses the 0.1.0b1 wheels, even after newer releases.

The beta has one goal you can help with directly: **two or more people, on their own, reproduce
the published fit of biphenyl in the liquid crystal 8CB** (the exercise below), with no serious
problem left open. Anything else you try, and anything that confuses you, is just as welcome.

## 1. Install and start

Follow [getting started](https://github.com/GinoLlerena/dipolar-studio/blob/v0.1.0b1/docs/user/getting-started.md)
as of 0.1.0b1: Python 3.12 or newer, `pip install` the two wheels of the release, then `dipolar serve --project-dir <a directory> --open`. Check that
`dipolar --version` prints `dipolar 0.1.0b1 …`, and run the synthetic example once (Data → "Open
the synthetic biphenyl example", then Fit → "Run fit"): it should find φ ≈ 37°.

## 2. The exercise: reproduce biphenyl in 8CB

The data are M. E. Di Pietro's (PhD thesis, Université Paris-Sud / Università della Calabria,
2013), **Table 3.1**, open copy: <http://hdl.handle.net/10955/1001>. **The release does not include
them**: transcribing them yourself is part of the test. (The source repository keeps a copy for
its own validation; please work from the publication instead, since the test is that a reader of
the thesis can reproduce the fit.)

**Transcribe** the 12 couplings at **T_red = 0.930** (printed pages 167–168, the **"exp"**
columns) into a CSV file with the header `spin_a,spin_b,D_obs_Hz,sigma_Hz`: one row per thesis
label, the **signed** coupling in Hz as printed, the number after "±" as `sigma_Hz`, all printed
digits kept. Each thesis label goes on this pair of the biphenyl template's protons:

| Thesis label | spin_a | spin_b |
|---|---|---|
| D12=D34 | `H2` | `H3` |
| D13=D13′ | `H2` | `H2'` |
| D11′=D33′ | `H2` | `H6` |
| D22′=D44′ | `H3` | `H5` |
| D14=D14′=D23=D23′ | `H2` | `H3'` |
| D24=D24′ | `H3` | `H3'` |
| D12′=D34′ | `H2` | `H5` |
| D16=D35 | `H2` | `H4'` |
| D15=D36 | `H2` | `H4` |
| D26=D45 | `H3` | `H4'` |
| D25=D46 | `H3` | `H4` |
| D56 | `H4` | `H4'` |

Type the primes as an ASCII apostrophe, as shown (`H2'`).

**Fit it, either way:**

- **In a notebook** (recommended: it checks everything for you): open
  [notebook 3](https://github.com/GinoLlerena/dipolar-studio/blob/v0.1.0b1/docs/notebooks/03-reproduce-8cb.ipynb), set `COUPLINGS_CSV` to your file and run it.
  It checks your 12 pairs, fits both configurations below and compares them with the reference;
  if anything differs it says what to check.
- **In the app:** make a copy of your file with every `sigma_Hz` set to `1` (the "unweighted"
  configuration). Then: Data → "Open the synthetic biphenyl example"; "Choose a CSV file…" with
  that copy (the proposed mapping is right: your labels are the template's); "Import 12
  couplings"; under Model choose "Four-site jump", "Bisector diagonal", "Bisector", φ domain 0 to
  90, and "Apply"; then Fit → "Run fit". The title bar keeps the example's name, "Synthetic
  biphenyl (known answer)": that is expected, the geometry is the example's template and the
  couplings are now yours.

**What you should find** (the four-site jump at T_red = 0.930, unweighted):

| | Value |
|---|---|
| φ | 32.932° |
| S_zz | 0.43075 |
| Δ | 0.18524 |

The app shows each value rounded to its uncertainty (for example Δ = 0.1852 ± 0.0004): a value
that rounds the same way agrees. These are Dipolar Studio's frozen reference fits for the
published data; the thesis's own
analysis agrees with them to 1–2 % in the order parameters. With the thesis's σ instead of 1
("weighted"), φ = 32.975°, S_zz = 0.43097, Δ = 0.18395, and the fit is flagged **inadequate**:
those σ are spectral-analysis errors, much smaller than the model's misfit. The unweighted fit's
χ², p-value and adequacy have no statistical meaning (σ = 1 is a convention), so compare only its
values: the app flags it **inadequate** too, with a yellow banner, and that is expected.

**Then tell us**, with the "Reproduction report" issue form (below), whether you got these values,
how long it took, and what was unclear. A failure is as useful as a success.

## 3. Reporting problems

Open an issue at <https://github.com/GinoLlerena/dipolar-studio/issues/new/choose>: the "Bug
report" form for a problem, the "Reproduction report" form for the exercise. Please include
`dipolar --version`, what you did and what happened, and if you can, the exported project
(`.dipolar.json`) or the fit's report (Fit → "Download report"). Do not attach data you may not
share.

**Severity**, which you choose in the bug form:

| Severity | Meaning | Examples |
|---|---|---|
| **S1** | A wrong scientific result **without a warning**, lost or corrupted work, a security problem, or the app cannot be installed or used at all | a fit reported as valid that is wrong; a project that does not reopen; the server does not start |
| **S2** | Something does not work, or misleads, and there is a way around it | an import refused with an unclear message; a button that does nothing; a wrong label in the report |
| **S3** | Cosmetic, wording, documentation | a typo; a confusing sentence; a layout glitch |

The beta ends when the exercise has been reproduced independently at least twice and no S1 issue
is open.

## 4. What the beta does not do yet

Biphenyl-type molecules only (two rings, one torsion); ¹H–¹H dipolar couplings only; rigid and
four-site-jump models (template) or rigid c2z/c1 (your own XYZ); the structure view draws SVG,
not PNG; very large projects (tens of thousands of couplings) are slow to preview. Other molecule
classes, measurement types and models are Phase 2 work.
