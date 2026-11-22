# Verification: benzene in ZLI-1132 (Taggar et al. 2006)

**Verification:** `pending`

**V0.3 label:** `pending` (roster 15, compared 0, agreeing 0, disagreeing 0, pending 15)

**Reproduction track:** `pending` (roster 15, compared 0, agreeing 0, disagreeing 0, pending 15)

No experimental fit has been run. The first-fit gate ([gates.md](gates.md) §3) is open, and until
the owner signs the benzene spot-check receipt every target is withheld (amendment P-2), so
nothing can be compared.

| Field | Entry |
|---|---|
| Source and channel | A. S. Taggar, C. J. Campbell, A. Yethiraj and E. E. Burnell, *J. Phys. Chem. B* **110**, 1363–1368 (2006). The couplings come from the Supporting Information ([10.1021/jp052592j.s001](https://doi.org/10.1021/jp052592j.s001), [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/)), used non-commercially with this attribution. The derived file [`couplings.csv`](../../../datasets/benzene-zli1132-taggar2006/couplings.csv) only splits the value(uncertainty) tokens and adds labels ([README](../../../datasets/benzene-zli1132-taggar2006/README.md)). The paper's order parameters (Tables 1–2, © ACS) are the targets. They stay in `datasets-local/` and never appear here. |
| Role | Development data, no independent holdout: its values were seen in V0.1 ([exposure log](../exposure-log.md)). |
| Model and estimand | The fixed declared geometry: Gauss–Stanton r_e on a regular hexagon (V0.3 §2). D6h in V1's frame (z normal to the ring, x along one C2′), one axial S_zz per condition. Three pair orbits per condition: N = 3, d = 1, ν = 2. Fifteen conditions, one cell each. |
| Project result and reference | None yet. The local report pairs each fit with its target, uncertainty, signed difference, margin, ratio residuals and adequacy. It is written only to `datasets-local/benzene-taggar2006-targets/verification-v1.5.md`. This page shows only the labels and their counts (V0.3 §6). |
| Criterion | Independent support: \|S − S_pub\| ≤ 0.05·\|S_pub\| + 2p, with p the printed σ (V0.3 §6). Reproduction (the authors' analysis): pending until the geometry, objective, weights and corrections are documented. Adequacy is reported beside the label and does not set it. The rigid model is expected to fail it (V0.3 §4). |
| Comparison tracks | The independent-support track (primary; it sets the Verification field through the decision 4A crosswalk) and the reproduction track, each with its own counts. Benzene has no drop-one sensitivity. |
| Implementation | `tools/validation/verification.py` (V1.5b): fits each condition through the registry's fixed-geometry path, `fixed-linear.1`. |
| Holdout | None available. The owner is the holdout custodian. |
| Protocol revision | `263f26857da15df184c7e662325e39036c307a02bc0042c610d6b8d4dab700b9` (V0.3 with amendments P-1 and P-2). |
| Gate evidence | [gates.md](gates.md), `tests/test_v15_gates.py`, `tests/test_v15_verification.py`. |

Every label carries the note "development data, no independent holdout". The agreement measured
here is consistency between two analyses of the same couplings, not independent data (V0.3 §6).
