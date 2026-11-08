"""Synthetic biphenyl known-answer dataset (rigid D2 model).

This is a test fixture, NOT experimental data. Every coupling is computed from a stated
geometry and order tensor, then (optionally) perturbed with seeded Gaussian noise. The
engine must recover the truth within the stated uncertainty.

Frame (molecule-fixed, "bisector" frame):
  z  along the inter-ring axis C4-C1-C1'-C4'
  x  bisects the two ring planes; y completes a right-handed frame
  ring A lies in the plane spanned by z and u_A = ( cos(phi/2),  sin(phi/2), 0)
  ring B lies in the plane spanned by z and u_B = ( cos(phi/2), -sin(phi/2), 0)
  so the inter-ring dihedral is phi. In this frame an ideal twisted biphenyl (D2) has a
  diagonal order tensor: only Szz and Delta = Sxx - Syy are free.

Coupling: D_ij = K_HH / r^3 * [ Szz * (3 cz^2 - 1)/2 + Delta * (cx^2 - cy^2)/2 ]
with K_HH = -(mu0/4pi) * gammaH^2 * hbar / (2 pi), in Hz * Angstrom^3.

Usage:  python3 generate.py            (numpy only; writes couplings.csv and truth.json)
"""
from __future__ import annotations

import csv
import json
import math
from itertools import combinations
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent

# --- physical constants (CODATA 2018 / IUPAC) ---------------------------------------
MU0_OVER_4PI = 1e-7            # T^2 m^3 / J
HBAR = 1.054571817e-34         # J s
GAMMA_H = 2.6752218744e8       # rad s^-1 T^-1
K_HH = -MU0_OVER_4PI * GAMMA_H**2 * HBAR / (2 * math.pi) * 1e30   # Hz * A^3  (~ -120 120)

# --- truth -------------------------------------------------------------------------
TRUTH = {
    "model": "rigid, D2 bisector frame, regular hexagonal rings",
    "phi_deg": 37.0,          # inter-ring dihedral (literature range in nematics: ~30-37 deg)
    "Szz": 0.25,
    "Delta": 0.030,           # Sxx - Syy
    "r_CC_ring_A": 1.397,     # aromatic C-C
    "r_CH_A": 1.084,          # C-H
    "r_C1C1p_A": 1.489,       # inter-ring bond
    "sigma_Hz": 0.5,          # noise standard deviation added to every coupling
    "seed": 19980101,
    "K_HH_Hz_A3": K_HH,
}


def proton_positions(phi_deg: float, r_cc: float, r_ch: float, r_inter: float) -> dict[str, np.ndarray]:
    phi = math.radians(phi_deg)
    ez = np.array([0.0, 0.0, 1.0])
    rings = {
        "": (np.array([math.cos(phi / 2), math.sin(phi / 2), 0.0]), -1.0),    # ring A, z < 0
        "'": (np.array([math.cos(phi / 2), -math.sin(phi / 2), 0.0]), +1.0),  # ring B, z > 0
    }
    pos: dict[str, np.ndarray] = {}
    for prime, (u, side) in rings.items():
        c1 = side * (r_inter / 2) * ez
        center = c1 + side * r_cc * ez               # ring centre lies beyond C1 along the axis
        toward_c1 = -side * ez                       # unit vector from centre to C1
        for k in range(1, 6):                        # k = 1..5 -> C2..C6 carry protons
            a = math.radians(60 * k)
            d = math.cos(a) * toward_c1 + math.sin(a) * u
            pos[f"H{k + 1}{prime}"] = center + (r_cc + r_ch) * d
    return pos


def coupling(ri: np.ndarray, rj: np.ndarray, szz: float, delta: float) -> float:
    v = rj - ri
    r = float(np.linalg.norm(v))
    cx, cy, cz = v / r
    return K_HH / r**3 * (szz * (3 * cz**2 - 1) / 2 + delta * (cx**2 - cy**2) / 2)


def main() -> None:
    t = TRUTH
    pos = proton_positions(t["phi_deg"], t["r_CC_ring_A"], t["r_CH_A"], t["r_C1C1p_A"])
    rng = np.random.default_rng(t["seed"])
    # Group symmetry-equivalent pairs: they give ONE measured value in a real spectrum, so they
    # form one observation with a multiplicity (they must not inflate N).
    classes: dict[float, list[tuple[str, str]]] = {}
    for a, b in combinations(sorted(pos, key=lambda s: (s.endswith("'"), s)), 2):
        key = round(coupling(pos[a], pos[b], t["Szz"], t["Delta"]), 6)
        classes.setdefault(key, []).append((a, b))
    rows = []
    for d_true, members in sorted(classes.items(), key=lambda kv: kv[1][0]):
        a, b = members[0]
        rows.append({
            "spin_a": a, "spin_b": b,
            "equivalent_pairs": " ".join(f"{x}-{y}" for x, y in members),
            "multiplicity": len(members),
            "r_A": round(float(np.linalg.norm(pos[b] - pos[a])), 6),
            "D_true_Hz": d_true,
            "D_obs_Hz": round(d_true + rng.normal(0, t["sigma_Hz"]), 3),
            "sigma_Hz": t["sigma_Hz"],
            "observable": "D", "unit": "Hz",
        })
    with open(HERE / "couplings.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    (HERE / "truth.json").write_text(json.dumps(t, indent=2) + "\n")
    print(f"wrote {len(rows)} unique couplings (from {sum(r['multiplicity'] for r in rows)} pairs); K_HH = {K_HH:.3f} Hz A^3")


if __name__ == "__main__":
    main()
