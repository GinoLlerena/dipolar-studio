# Biphenyl in 8CB: experimental ¹H–¹H dipolar couplings (benchmark dataset)

**Status: development/regression case.** Not the untouched holdout (see plan §5).

## Source

M. E. Di Pietro, *RMN dans différents solvants partiellement orientés: pour la détermination de
la structure, l'ordre et la conformation de molécules organiques*, PhD thesis, Université
Paris-Sud / Università della Calabria (co-tutelle), defended 14 Dec 2013.
Chapter 3, **Table 3.1** (pp. 167–168 of the thesis, PDF pages 179–180) and **Table 3.2** (p. 172).
Open copy: <https://lisa.unical.it/bitstreams/1deb8605-44d0-4c62-9a8f-d4f7eb6cafe1/download>
(repository record <http://hdl.handle.net/10955/1001>, Università della Calabria, LISA).

- **Sample:** biphenyl (2P) 2.8 wt% in 8CB, with 1,3,5-trichlorobenzene as orientational probe.
- **Spectra:** Bruker Avance 500 MHz; temperatures 273–307 K.
- **Analysis:** spectral analysis with ARCANA.

The geometry used in the thesis fit is that optimised in G. Celebre, G. De Luca, M. Longeri,
*Liq. Cryst.* **37**, 923–933 (2010). It is not reproduced here.

### Provenance

- Source file: PDF, 42,825,291 bytes, SHA-256
  `0f01deffecfe3dc8b0836c0f70fd2d51e435492df7f4ba45f7036ecc19f9fd30` (downloaded 2026-11-07).
- Values come only from the **"exp"** columns of Table 3.1 (printed pp. 167–168, PDF pp.
  179–180). Simulated ("sim") columns are excluded.
- The 2013 experimental couplings are separate from the 2010 geometry reference
  (Celebre et al.). Nothing from the 2010 paper is reproduced here.

### Basis for publication in this public repository

This directory contains only **numerical measurement values** (120 couplings with their
uncertainties), transcribed with full attribution for scholarly benchmarking. The thesis's
figures, text and PDF are **not** redistributed. The owner decided on 2026-11-07 to publish this
repository. Open access to the PDF and citation do not by themselves establish a redistribution
licence, so this dataset is **excluded from the repository's BSD-3 licence**. It will be removed
on request from the rights holders, and we will ask the author for explicit permission before
any packaged redistribution (for example inside PyPI wheels).

**The repository's licence record** (checked 2026-11-10 through the DSpace REST API):
- The item has no `dc.rights` or `dc.rights.uri` metadata.
- Its LICENSE bundle holds one file whose entire text is "Creative Commons". It gives no version,
  no licence deed, and no rights holder.
- So the terms (for example CC BY or CC BY-NC) cannot be determined from the record.
- The record lists the English title "NMR in different partially ordered media: a route for
  structure, order and conformation of small organic compounds" (2013-11-20).

**Use: validation only.**
- Nothing in the product depends on this directory.
- It can be deleted without affecting the work. See "Removing a third-party dataset" in
  `datasets/README.md`.

## Files

- `couplings.csv`: 120 rows (12 unique couplings × 10 reduced temperatures T_red = T/T_NI,
  0.880–0.990). Columns: the thesis label, a representative pair in this project's labels, the
  value in Hz, and σ (the spectral-analysis error only).
- `check_fit.py` / `check_fit.out.json`: a sanity fit (rigid rings, four-site jump average).

Transcription was verified two ways:

1. a programmatic parse of the PDF text layer;
2. a manual reading of the rendered table at T_red 0.930 and 0.980 (all 24 values match).

## Numbering

The thesis numbering maps to the labels used here. Ring A carries the unprimed labels and ring
B the primed ones; H2 and H2′ are on the same side.

| Thesis | Here | Position |
|---|---|---|
| 1, 1′ | H2, H6 | ortho, ring A |
| 2, 2′ | H3, H5 | meta, ring A |
| 5 | H4 | para, ring A |
| 3, 3′ | H2′, H6′ | ortho, ring B (3 is on the same side as 1) |
| 4, 4′ | H3′, H5′ | meta, ring B |
| 6 | H4′ | para, ring B |

The equalities in the thesis labels (for example D13 = D13′, the same-side and opposite-side
ortho–ortho pairs) are **consistent with** fast interconversion between the ±φ and 180±φ
conformers. A rigid single-conformer model cannot reproduce them. These equalities alone do not
prove a unique equal-population four-site mechanism, since a continuous distribution such as
the thesis's AP-DPD model gives them too. The beta implements the symmetric **four-site jump
average** as the simplest model that respects them (plan v0.5 §4).

## Reference results (thesis Table 3.2, AP-DPD model)

The AP-DPD model uses a Gaussian distribution of twist angles: φ_m is the most probable twist
and Δ_φ is the full width at half maximum. A simultaneous fit of all 10 temperatures adjusted
31 parameters.

| T (K) / T_red | φ_m (°) | Δ_φ (°) | S_aa | S_bb − S_cc |
|---|---|---|---|---|
| 290.0 / 0.93 (SmA) | 35.37 ± 0.12 | 11.93 ± 0.28 | 0.425 ± 0.004 | 0.182 ± 0.005 |
| 305.0 / 0.98 (N) | 35.51 ± 0.12 | 11.93 ± 0.28 | 0.321 ± 0.005 | 0.152 ± 0.003 |

Axis a is the long axis; b bisects the ring planes.

## Sanity fit with this project's model (`check_fit.py`)

The model has regular hexagonal rings (C–C 1.397 Å, C–H 1.084 Å, C1–C1′ 1.489 Å) and a
four-site jump, averaged by relabelling **both** endpoints of each pair. The fit is an
**unweighted** least-squares fit reporting RMS; this is a declared regression configuration, not
the default D3 weighting:

| T_red | φ (°) | S_zz | Δ | RMS (Hz) |
|---|---|---|---|---|
| 0.930 | 32.95 | 0.4308 | 0.1852 | 5.24 |
| 0.980 | 33.05 | 0.3248 | 0.1531 | 3.89 |

**Interpretation.**

- The order parameters agree with the thesis to within 1–2%.
- φ is about 2.4° lower. This is expected, for three reasons:
  1. the **estimand differs**: a rigid effective angle vs the maximum of a distribution;
  2. the ring geometry is idealized;
  3. there are no vibrational corrections.
- These explanations are **plausible hypotheses, not demonstrated attribution**. Agreement of
  the order parameters is descriptive, not independent validation of either model.
- The residuals (4–5 Hz) are about 100 times the spectral σ. Under the spectral-σ likelihood
  the model is **grossly inadequate**, and the engine must report that as such; the spectral σ
  is kept and not rescaled. With spectral-σ weighting, T_red 0.980 gives about φ = 33.10° and
  Δ = 0.15221.

**M1 regression use** (plan v0.5 §8). These are regression targets, not a scientific gold
standard:
- the **unweighted** configuration must reproduce, at both temperatures, φ, S_zz, Δ, RMS and the
  full prediction vector, within stated numerical tolerances;
- the **weighted** configuration must report its result together with the inadequacy flag.

Matching the thesis's AP-DPD φ_m requires a distribution model (a post-beta gate).
