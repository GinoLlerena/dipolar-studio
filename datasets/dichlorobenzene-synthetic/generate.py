"""Synthetic 1,4-dichlorobenzene: the fixed-geometry tutorial's known-answer dataset (Phase 2 V1.4).

This is a test fixture, NOT experimental data. Every coupling is computed from a stated geometry
and order tensor, then perturbed with seeded Gaussian noise. It is independent of the engine: NumPy
only, with its own reference fit.

Geometry (a regular hexagonal ring in the xy plane, centred on the origin):
  C1 … C6   at angles 0°, 60°, …, 300° on a circle of radius r_CC (C1 on +x);
  Cl1, Cl4  on C1 and C4, at r_CC + r_CCl from the centre (on the x axis);
  H2 … H6   on C2, C3, C5, C6, at r_CC + r_CH from the centre.
The molecule is D2h. Its symmetry frame is the input frame: x along Cl–Cl, z normal to the ring.

Order tensor (diagonal in that frame, traceless): Sxx (Cl–Cl axis), Syy (in plane), and
Szz = −Sxx − Syy (the ring normal). D2h leaves two free components.

Coupling: D_ij = K_HH / r³ · Σ_ab S_ab c_a c_b, with c the unit vector from i to j and
K_HH = −(μ0/4π) γ_H² ħ / (2π), in Hz·Å³ (≈ −120 120).

The four protons give three pair orbits (each of two symmetry-copied pairs):
  ortho  H2–H3 (and H5–H6), along x: D = K Sxx / r³;
  meta   H2–H6 (and H3–H5), along y: D = K Syy / r³;
  para   H2–H5 (and H3–H6): a combination of both.
So N = 3 observations of d = 2 free components: ν = 1.

The files, as a user would have them:
- ``dichlorobenzene.xyz``: element symbols only; the comment line lists the atom names. Imported,
  the protons are named by atom number (H9 … H12), so the couplings file's labels must be mapped:
  the tutorial's "confirm mapping" step.
- ``couplings.csv``: one row per pair orbit, its class written out (``equivalent_pairs``) and its
  multiplicity, D and σ in Hz.

Usage:  python3 generate.py   (NumPy only; writes the XYZ, the CSV and truth.json)
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent

# --- physical constants (CODATA 2018), as datasets/biphenyl-synthetic/generate.py -------------
MU0_OVER_4PI = 1e-7  # T² m³ / J
HBAR = 1.054571817e-34  # J s
GAMMA_H = 2.6752218744e8  # rad s⁻¹ T⁻¹
K_HH = -MU0_OVER_4PI * GAMMA_H**2 * HBAR / (2 * math.pi) * 1e30  # Hz Å³

TRUTH = {
    "model": "fixed geometry, D2h, symmetry frame = input frame (x along Cl–Cl, z normal to the ring)",
    "Sxx": 0.22,
    "Syy": -0.06,
    "r_CC_A": 1.395,
    "r_CH_A": 1.080,
    "r_CCl_A": 1.740,
    "sigma_Hz": 0.3,
    "seed": 20261120,
    "K_HH_Hz_A3": K_HH,
}

#: The atoms in file order: carbons, chlorines, then hydrogens (as a user's file might list them).
NAMES = ["C1", "C2", "C3", "C4", "C5", "C6", "Cl1", "Cl4", "H2", "H3", "H5", "H6"]
#: The observed pair orbits: the first pair of each, then its symmetry copy.
ORBITS = [
    ("ortho", ("H2", "H3"), ("H5", "H6")),
    ("meta", ("H2", "H6"), ("H3", "H5")),
    ("para", ("H2", "H5"), ("H3", "H6")),
]


def positions(t: dict[str, float]) -> dict[str, np.ndarray]:
    pos: dict[str, np.ndarray] = {}
    for k in range(6):
        a = math.radians(60 * k)
        u = np.array([math.cos(a), math.sin(a), 0.0])
        pos[f"C{k + 1}"] = t["r_CC_A"] * u
        if k in (0, 3):
            pos[f"Cl{k + 1}"] = (t["r_CC_A"] + t["r_CCl_A"]) * u
        else:
            pos[f"H{k + 1}"] = (t["r_CC_A"] + t["r_CH_A"]) * u
    # The geometry is the file's: rounded as written (6 decimals, no negative zero).
    return {name: np.round(p, 6) + 0.0 for name, p in pos.items()}


def order_matrix(t: dict[str, float]) -> np.ndarray:
    return np.diag([t["Sxx"], t["Syy"], -t["Sxx"] - t["Syy"]])


def coupling(pos: dict[str, np.ndarray], a: str, b: str, s: np.ndarray) -> float:
    v = pos[b] - pos[a]
    r = float(np.linalg.norm(v))
    c = v / r
    return float(K_HH / r**3 * c @ s @ c)


def design(pos: dict[str, np.ndarray], a: str, b: str) -> np.ndarray:
    """The row of D in the free components (Sxx, Syy), with Szz = −Sxx − Syy."""
    v = pos[b] - pos[a]
    r = float(np.linalg.norm(v))
    c = v / r
    return K_HH / r**3 * np.array([c[0] ** 2 - c[2] ** 2, c[1] ** 2 - c[2] ** 2])


def reference_fit(pos: dict[str, np.ndarray], y: np.ndarray, sigma: float) -> dict[str, object]:
    """Weighted linear least squares in (Sxx, Syy): the estimate, its covariance and χ²."""
    a = np.array([design(pos, *pair) for _, pair, _ in ORBITS]) / sigma
    w = y / sigma
    est, *_ = np.linalg.lstsq(a, w, rcond=None)
    cov = np.linalg.inv(a.T @ a)
    chi2 = float(np.sum((w - a @ est) ** 2))
    return {
        "Sxx": float(est[0]),
        "Syy": float(est[1]),
        "Szz": float(-est[0] - est[1]),
        "covariance_Sxx_Syy": cov.tolist(),
        "chi2": chi2,
        "nu": len(y) - 2,
    }


def main() -> None:
    t = TRUTH
    pos = positions(t)
    s = order_matrix(t)
    noiseless = np.array([coupling(pos, *pair, s) for _, pair, _ in ORBITS])
    # The copy has the same coupling as the first pair of its orbit (a check of the geometry).
    for (_, pair, copy), d in zip(ORBITS, noiseless, strict=True):
        assert abs(coupling(pos, *copy, s) - d) < 1e-9
    rng = np.random.default_rng(t["seed"])
    noisy = noiseless + rng.normal(0.0, t["sigma_Hz"], size=len(ORBITS))
    observed = np.round(noisy, 3)

    lines = [str(len(NAMES)), "synthetic 1,4-dichlorobenzene (D2h); atoms: " + " ".join(NAMES)]
    for name in NAMES:
        x, y, z = (float(v) for v in pos[name])
        lines.append(f"{''.join(ch for ch in name if ch.isalpha())} {x:.6f} {y:.6f} {z:.6f}")
    (HERE / "dichlorobenzene.xyz").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    with (HERE / "couplings.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(["spin_a", "spin_b", "equivalent_pairs", "multiplicity", "D_obs_Hz", "sigma_Hz"])
        for (_, (a, b), (c, d)), value in zip(ORBITS, observed, strict=True):
            writer.writerow([a, b, f"{a}-{b} {c}-{d}", 2, f"{value:.3f}", t["sigma_Hz"]])

    truth = {
        "truth": t,
        "orbits": [{"name": n, "pairs": [list(p), list(c)]} for n, p, c in ORBITS],
        "noiseless_Hz": noiseless.tolist(),
        "observed_Hz": observed.tolist(),
        "reference_fit_noisy": reference_fit(pos, observed, t["sigma_Hz"]),
        "reference_fit_noiseless": reference_fit(pos, noiseless, t["sigma_Hz"]),
    }
    (HERE / "truth.json").write_text(json.dumps(truth, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
