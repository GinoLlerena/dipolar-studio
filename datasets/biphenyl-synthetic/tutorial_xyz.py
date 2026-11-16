"""The synthetic biphenyl as an XYZ file and a plain couplings file, for the robot tutorial
(M3 step 4b).

The geometry is the generator's own (generate.py: regular hexagonal rings, the stated bond
lengths, the true torsion φ = 37°, the bisector frame), so it is independent of the engine. Atoms
are written as a user's file would have them: element symbols only, carbons first.

  index 0–5    C1 … C6   (ring A; C1 bonded to C1')
  index 6–11   C1' … C6' (ring B)
  index 12–16  H2 … H6
  index 17–21  H2' … H6'

Imported without labels, the protons are named by their atom number (H13 … H22), so the
couplings file's labels (H2 … H6') must be mapped by the user: the tutorial's "confirm mapping"
step. The fitted torsion is the dihedral C2–C1–C1'–C2' (atoms 1, 0, 6, 7), which is −φ in this
frame (IUPAC τ = −φ, see dipolar_core.biphenyl).

The couplings file (tutorial-couplings.csv) is couplings.csv without its symmetry classes: each
measured value is assigned to the first pair of its class only, so there are 14 independent
observations, as many as measured values. The classes are D2 equivalences of the template's
model; an imported geometry is fitted with order c2z or c1, under which pairs across the two
rings are not equivalent, so importing the classes is refused (as it should be), and listing every
member as its own observation would count one measurement several times.

Usage:  python3 tutorial_xyz.py   (numpy only; writes biphenyl.xyz and tutorial-couplings.csv)
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

import numpy as np
from generate import TRUTH, proton_positions

HERE = Path(__file__).parent


def carbon_positions(phi_deg: float, r_cc: float, r_inter: float) -> dict[str, np.ndarray]:
    """C1 … C6 of each ring, on the same construction as generate.proton_positions."""
    phi = math.radians(phi_deg)
    ez = np.array([0.0, 0.0, 1.0])
    rings = {
        "": (np.array([math.cos(phi / 2), math.sin(phi / 2), 0.0]), -1.0),
        "'": (np.array([math.cos(phi / 2), -math.sin(phi / 2), 0.0]), +1.0),
    }
    pos: dict[str, np.ndarray] = {}
    for prime, (u, side) in rings.items():
        center = side * (r_inter / 2) * ez + side * r_cc * ez
        toward_c1 = -side * ez
        for k in range(6):
            a = math.radians(60 * k)
            pos[f"C{k + 1}{prime}"] = center + r_cc * (math.cos(a) * toward_c1 + math.sin(a) * u)
    return pos


def main() -> None:
    t = TRUTH
    carbons = carbon_positions(t["phi_deg"], t["r_CC_ring_A"], t["r_C1C1p_A"])
    protons = proton_positions(t["phi_deg"], t["r_CC_ring_A"], t["r_CH_A"], t["r_C1C1p_A"])
    order = [f"C{k}" for k in range(1, 7)] + [f"C{k}'" for k in range(1, 7)]
    order += [f"H{k}" for k in range(2, 7)] + [f"H{k}'" for k in range(2, 7)]
    every = {**carbons, **protons}
    lines = [f"{name[0]} {p[0]:.6f} {p[1]:.6f} {p[2]:.6f}" for name, p in ((n, every[n]) for n in order)]
    comment = f"synthetic biphenyl, phi = {t['phi_deg']} deg; atoms: {' '.join(order)}"
    (HERE / "biphenyl.xyz").write_text(f"{len(lines)}\n{comment}\n" + "\n".join(lines) + "\n", encoding="utf-8")
    with open(HERE / "couplings.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    with open(HERE / "tutorial-couplings.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["spin_a", "spin_b", "D_obs_Hz", "sigma_Hz"])
        for row in rows:
            w.writerow([row["spin_a"], row["spin_b"], row["D_obs_Hz"], row["sigma_Hz"]])
    print(f"wrote biphenyl.xyz ({len(lines)} atoms) and tutorial-couplings.csv ({len(rows)} couplings)")


if __name__ == "__main__":
    main()
