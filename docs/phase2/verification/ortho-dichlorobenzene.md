# Verification: ortho-dichlorobenzene (Chandrakumar & Burnell 1993)

**Verification:** `pending`

**V0.3 label:** `pending` (roster 44, compared 0, agreeing 0, disagreeing 0, pending 44)

**Reproduction track:** `pending` (roster 44, compared 0, agreeing 0, disagreeing 0, pending 44)

**Sensitivity (drop-one):** not computed. Nothing is compared yet, so the two frozen drop-one
labels and fragility (V0.3 §7) have no counts to report.

No experimental fit has been run. The first-fit gate ([gates.md](gates.md) §3) is open, and until
the owner signs this dataset's spot-check receipt every target is withheld (amendment P-2).
Every label carries the open spot-check note while that check is open.

| Field | Entry |
|---|---|
| Source and channel | T. Chandrakumar and E. E. Burnell, *Bull. Magn. Reson.* **15**, 199–204 (1993) ([`v0-sources.json`](../v0-sources.json)), © ISMAR. The couplings (22 conditions × 4) and the digitized targets are restricted, local only (`datasets-local/`). This page shares only labels, counts, drop-one outcomes, fragility and the protocol revision. |
| Target provenance | Digitized from Fig. 3 (the primary source) by `tools/datasets/digitize_figure.py`, with a frozen assignment rule. Fig. 2 is the cross-check (V0.3 §5). |
| Role | Development data, no independent holdout. |
| Model and estimand | The benzene-based idealization of the declared geometry (V0.3 §2). Its ring distortions are not bounded. C2v, fitted in V1's frame and converted to the paper's frame by the frozen map and matrix. Two estimands per condition, S_zz and S_xx − S_yy, with the full covariance carried through. Four pair orbits: N = 4, d = 2, ν = 2. Forty-four cells. |
| Project result and reference | None yet. The 44-cell detail and its diagnostics go only to `datasets-local/odcb-chandrakumar1993/verification-v1.5.md`. |
| Criterion | Independent support: S_zz agrees when \|S − S_pub\| ≤ 0.05·\|S_pub\| + 2p. S_xx − S_yy agrees when \|S − S_pub\| ≤ 0.05·\|S_zz,pub\| + 2p, using the same condition's S_zz; p is the digitization precision (V0.3 §6). Reproduction: pending until the authors' inputs are documented. |
| Comparison tracks | Independent support (primary), and reproduction, each with its own counts. The full-data label is primary. The labels without each of the two frozen near-duplicate conditions are reported beside it. |
| Implementation | `tools/validation/verification.py` (V1.5b), through the registry's fixed-geometry path, `fixed-linear.1`. |
| Holdout | None available. |
| Protocol revision | `263f26857da15df184c7e662325e39036c307a02bc0042c610d6b8d4dab700b9`. |
| Gate evidence | [gates.md](gates.md), `tests/test_v15_gates.py`, `tests/test_v15_verification.py`. |
