"""Reference check: recover (phi, Szz, Delta) from couplings.csv with the D3 method.

Inner problem: weighted linear least squares for s = (Szz, Delta) via SVD (np.linalg.lstsq)
on the whitened design matrix B = L A(phi), b = L y. Outer problem: 1-D profile over phi
(scan + golden-section refinement). Uncertainty: profile Delta-chi2 = 1 interval for phi.

This is a numpy-only prototype of the engine's contract, used to validate the fixture.
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import numpy as np

from generate import K_HH, TRUTH, proton_positions

HERE = Path(__file__).parent


def design(phi: float, pairs: list[tuple[str, str]]) -> np.ndarray:
    t = TRUTH
    pos = proton_positions(phi, t["r_CC_ring_A"], t["r_CH_A"], t["r_C1C1p_A"])
    rows = []
    for a, b in pairs:
        v = pos[b] - pos[a]
        r = np.linalg.norm(v)
        cx, cy, cz = v / r
        rows.append([K_HH / r**3 * (3 * cz**2 - 1) / 2, K_HH / r**3 * (cx**2 - cy**2) / 2])
    return np.array(rows)


def chi2_at(phi: float, pairs, y, sigma):
    L = 1.0 / sigma
    B = design(phi, pairs) * L[:, None]
    b = y * L
    s, *_ = np.linalg.lstsq(B, b, rcond=None)
    r = B @ s - b
    return float(r @ r), s, np.linalg.matrix_rank(B)


def main() -> None:
    with open(HERE / "couplings.csv", encoding="utf-8") as f:
        data = list(csv.DictReader(f))
    pairs = [(d["spin_a"], d["spin_b"]) for d in data]
    y = np.array([float(d["D_obs_Hz"]) for d in data])
    sigma = np.array([float(d["sigma_Hz"]) for d in data])

    grid = np.arange(0.5, 90.0, 0.5)
    prof = np.array([chi2_at(p, pairs, y, sigma)[0] for p in grid])
    lo, hi = grid[max(prof.argmin() - 1, 0)], grid[min(prof.argmin() + 1, len(grid) - 1)]
    g = (math.sqrt(5) - 1) / 2
    for _ in range(80):                                   # golden-section refinement
        c, d = hi - g * (hi - lo), lo + g * (hi - lo)
        if chi2_at(c, pairs, y, sigma)[0] < chi2_at(d, pairs, y, sigma)[0]:
            hi = d
        else:
            lo = c
    phi_hat = (lo + hi) / 2
    chi2_min, s_hat, rank = chi2_at(phi_hat, pairs, y, sigma)

    def crossing(direction: int) -> float:                # profile interval, Delta-chi2 = 1
        p = phi_hat
        while chi2_at(p, pairs, y, sigma)[0] - chi2_min < 1.0:
            p += direction * 0.001
        return p

    ci = (crossing(-1), crossing(+1))
    n, p_free = len(y), 3
    report = {
        "phi_hat_deg": round(phi_hat, 4),
        "phi_68pct_profile_interval_deg": [round(ci[0], 3), round(ci[1], 3)],
        "Szz_hat": round(float(s_hat[0]), 5),
        "Delta_hat": round(float(s_hat[1]), 5),
        "chi2": round(chi2_min, 3), "nu": n - p_free,
        "chi2_reduced": round(chi2_min / (n - p_free), 3),
        "inner_rank": int(rank),
        "truth": {k: TRUTH[k] for k in ("phi_deg", "Szz", "Delta")},
        "equivalent_solutions_note": "At fixed labels, (phi, Delta) and (-phi, Delta) give identical couplings. "
                                     "(180 +/- phi, -Delta) is equivalent ONLY together with the ring-B relabelling "
                                     "H2'<->H6', H3'<->H5' (x moves to the other bisector). Domain folded to phi in [0, 90] deg.",
    }
    print(json.dumps(report, indent=2))
    (HERE / "check_fit.out.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
