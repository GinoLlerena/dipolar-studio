# Datasets

| Dataset | Kind | Purpose |
|---|---|---|
| [biphenyl-synthetic/](biphenyl-synthetic/) | Synthetic, with a known answer (rigid D2, φ = 37°, 14 unique couplings, σ = 0.5 Hz) | Numerical truth. M1 gates: exact recovery from **noiseless** couplings; a fixed noisy fixture as a numerical regression; interval coverage calibrated separately on an ensemble of seeds (seeds are never chosen to force coverage). It also documents the equivalences: (±φ, Δ) at fixed labels, and (180±φ, −Δ) only together with the ring-B relabelling H2′↔H6′, H3′↔H5′. |
| [dichlorobenzene-synthetic/](dichlorobenzene-synthetic/) | Synthetic, with a known answer (1,4-dichlorobenzene, D2h, Sxx = 0.22, Syy = −0.06, 3 pair orbits, σ = 0.3 Hz) | The fixed-geometry tutorial (Phase 2 V1.4): the page and the robot fit it from its XYZ file and must give the same run. Its own NumPy reference fit, independent of the engine. |
| [biphenyl-8CB-dipietro2013/](biphenyl-8CB-dipietro2013/) | Experimental (Di Pietro, PhD thesis 2013, Table 3.1): 12 couplings × 10 temperatures | Development and regression on real data; an unweighted rigid+jump fit gives order parameters within 1–2% of the published AP-DPD values (descriptive agreement). **Excluded from the BSD-3 licence; see its README for the publication basis.** |
| *(to be selected)* | Experimental holdout | Sealed until the model and criteria are frozen; once opened it becomes regression data, and the next evaluation needs a fresh holdout (plan §5) |
| [benzene-zli1132-taggar2006/](benzene-zli1132-taggar2006/) | Experimental (Taggar et al. 2006, Supporting Information, **CC BY-NC 4.0**): benzene D12/D13/D14 × 15 conditions in ZLI-1132 | Phase 2 V0 corpus: development data for V1 (rigid molecules). Validation only, not in releases. **Excluded from the BSD-3 licence; see its README.** |
| *(local only)* `datasets-local/odcb-chandrakumar1993/` | Experimental (Chandrakumar & Burnell 1993, © ISMAR): ortho-dichlorobenzene, 4 couplings × 22 conditions | Phase 2 V0 corpus, kept **only on the owner's machine** (git-ignored); see `docs/phase2/v0.2-corpus.md` |
| *(Phase 2, V0)* | Verification corpus candidates: benzene and trihalobenzenes, substituted benzenes in 8CB, 4,4′-d₂-biphenyl, a fluorinated terphenyl (¹³C–¹⁹F), biphenyl in other solvents | Candidates listed in plan §8, Phase 2 V0. Each is added only after its source, its transcription and its rights are confirmed. |

These datasets are **test fixtures**. In the app, users load their own couplings and geometry.

**Frozen expected answers** (M0): each dataset has an `expected/` directory computed by the
independent reference implementation in [tools/reference/](../tools/reference/). It holds a
`spec.json` (frame, estimand, optimum convention, tolerances, gates), the full-precision results,
and a `MANIFEST.sha256` that detects hand edits. The engine's tests compare against these files.

## Removing a third-party dataset

Third-party datasets are used **only to validate** the engine. Today they are
`biphenyl-8CB-dipietro2013/` and `benzene-zli1132-taggar2006/`. If a rights holder asks, remove
one like this (the steps below name the 8CB dataset; the benzene one is the same, and its tests
skip in the same way). Nothing in the product depends on them.

1. **Delete it:** `git rm -r datasets/biphenyl-8CB-dipietro2013`.
2. **Remove its row** from the table above, and its reference entry in `CITATION.cff`.
3. **Run the checks:** `uv run pytest -q -m "not slow"`.
   - The 8CB tests skip by themselves ("the third-party 8CB dataset is not present").
   - Everything else passes. This was verified on 2026-11-10: 321 passed, 5 skipped.
   - `tools/reference/make_expected.py` skips the dataset when it is absent.
4. **Rewrite history only if asked.** Removing the files from git *history* as well needs a
   rewrite (`git filter-repo --path datasets/biphenyl-8CB-dipietro2013 --invert-paths`) and a
   force push. That is a separate, deliberate step.

**What keeps it removable:**
- `tests/test_boundaries.py::test_shipped_code_never_depends_on_third_party_data` fails if any
  package source, web source or packaging script mentions the dataset.
- The datasets are never packaged into the wheels.
- Gate (e) (explicit averaging equals the relabelling shortcut) uses all 45 synthetic pairs, not
  the 8CB pair list.
- Its M1 gate is conditional on its presence. Without it, another experimental dataset from the
  V0 corpus takes the role.

The prototype scripts need only Python 3 and NumPy: `python3 generate.py`, `python3 check_fit.py`.
`python3 tutorial_xyz.py` writes the robot tutorial's inputs (M3 step 4b): `biphenyl.xyz`, the
generator's own geometry as a user's XYZ file, and `tutorial-couplings.csv`, the 14 measured
values without the D2 symmetry classes (each on the first pair of its class), since an imported
geometry is fitted with order c2z or c1.
