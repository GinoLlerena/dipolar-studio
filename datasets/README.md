# Datasets

| Dataset | Kind | Purpose |
|---|---|---|
| [biphenyl-synthetic/](biphenyl-synthetic/) | Synthetic, with a known answer (rigid D2, φ = 37°, 14 unique couplings, σ = 0.5 Hz) | Numerical truth. M1 gates: exact recovery from **noiseless** couplings; a fixed noisy fixture as a numerical regression; interval coverage calibrated separately on an ensemble of seeds (seeds are never chosen to force coverage). It also documents the equivalences: (±φ, Δ) at fixed labels, and (180±φ, −Δ) only together with the ring-B relabelling H2′↔H6′, H3′↔H5′. |
| [biphenyl-8CB-dipietro2013/](biphenyl-8CB-dipietro2013/) | Experimental (Di Pietro, PhD thesis 2013, Table 3.1): 12 couplings × 10 temperatures | Development and regression on real data; an unweighted rigid+jump fit gives order parameters within 1–2% of the published AP-DPD values (descriptive agreement). **Excluded from the BSD-3 licence; see its README for the publication basis.** |
| *(to be selected)* | Experimental holdout | Untouched until release evaluation (plan §5) |

Scripts need only Python 3 and NumPy: `python3 generate.py`, `python3 check_fit.py`.
