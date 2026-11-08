"""Sanity check: fit the experimental 8CB data with a rigid ring geometry + 4-site jump average.

Model: regular hexagonal rings (C-C 1.397, C-H 1.084, C1-C1' 1.489 A; NOT the optimised
geometry of Celebre et al. 2010 used in the thesis). The molecule interconverts rapidly between
the conformers +phi, -phi, 180-phi, 180+phi. The order tensor is diagonal in each conformer's
acute-bisector frame, with the same Szz (long axis a) and Delta = Sbb - Scc for every conformer.
Averaging over the four conformers equals averaging each pair over the ring-B relabelling
H2'<->H6', H3'<->H5', applied to both endpoints. (The round-4 review checked this against
explicitly rotated conformers with acute-frame tensors: agreement to 1.6e-12 Hz at phi = 37 deg.)

This is a single-conformation-plus-jumps model, so it is NOT the thesis' AP-DPD distribution
model. We expect phi near the published 35.4 deg but not equal to it, and residuals of a few Hz
from the geometry and the missing vibrational corrections. That is model error, far above the
0.03-0.17 Hz spectral errors, so this UNWEIGHTED fit reports RMS. Under the spectral-sigma likelihood the model is grossly
inadequate, and that should be reported as such (a weighted fit at 0.980 gives about phi = 33.10, Delta = 0.15221).
"""
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "biphenyl-synthetic"))
from generate import K_HH, proton_positions  # noqa: E402

SWAP_B = {"H2'": "H6'", "H6'": "H2'", "H3'": "H5'", "H5'": "H3'", "H4'": "H4'"}


def row(pos, a, b):
    v = pos[b] - pos[a]; r = np.linalg.norm(v); cx, cy, cz = v / r
    return np.array([K_HH / r**3 * (3 * cz**2 - 1) / 2, K_HH / r**3 * (cx**2 - cy**2) / 2])


def design(phi, pairs):
    pos = proton_positions(phi, 1.397, 1.084, 1.489)
    # permute BOTH endpoints (ring-B relabelling), so ring-B-internal pairs map correctly too
    return np.array([(row(pos, a, b) + row(pos, SWAP_B.get(a, a), SWAP_B.get(b, b))) / 2 for a, b in pairs])


def fit(pairs, y):
    best = None
    for phi in np.arange(0.5, 90.0, 0.05):
        A = design(phi, pairs); s, *_ = np.linalg.lstsq(A, y, rcond=None)
        rms = float(np.sqrt(np.mean((A @ s - y) ** 2)))
        if best is None or rms < best[0]:
            best = (rms, phi, s)
    return best


def main():
    out = {}
    with open(HERE / "couplings.csv") as f:
        data = list(csv.DictReader(f))
    for t, ref in (("0.930", {"phi_max_deg": 35.37, "Saa": 0.425, "Sbb_minus_Scc": 0.182}),
                   ("0.980", {"phi_max_deg": 35.51, "Saa": 0.321, "Sbb_minus_Scc": 0.152})):
        rows = [d for d in data if d["T_red"] == t]
        pairs = [(d["spin_a"], d["spin_b"]) for d in rows]
        y = np.array([float(d["D_obs_Hz"]) for d in rows])
        rms, phi, s = fit(pairs, y)
        out[t] = {"phi_deg": round(phi, 2), "Szz": round(float(s[0]), 4), "Delta": round(float(s[1]), 4),
                  "rms_Hz": round(rms, 2), "thesis_AP_DPD": ref}
    print(json.dumps(out, indent=2))
    (HERE / "check_fit.out.json").write_text(json.dumps(out, indent=2) + "\n")


if __name__ == "__main__":
    main()
