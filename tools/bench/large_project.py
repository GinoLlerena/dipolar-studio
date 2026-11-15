"""A large synthetic project for performance work (M3 step 4b): an XYZ of two rigid groups joined
by a C–C bond, with `--protons` hydrogens, and a couplings CSV of every proton pair (n(n−1)/2 rows)
with synthetic values. Not a molecule: only the sizes matter.

    python3 tools/bench/large_project.py --protons 448 --out DIR   # 100 128 couplings
"""

from __future__ import annotations

import argparse
import math
import random
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--protons", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    ns = parser.parse_args()
    rng = random.Random(1998)
    n = ns.protons
    atoms = [("C", (0.0, 0.0, -0.75)), ("C", (1.4, 0.0, -1.5)), ("C", (0.0, 0.0, 0.75)), ("C", (1.4, 0.0, 1.5))]
    for k in range(n):  # half on each side of the C1–C1' bond, on spirals 1.2 Å apart at least
        side = -1.0 if k % 2 == 0 else 1.0
        t = k // 2
        r = 2.5 + 0.35 * math.sqrt(t)
        a = 2.4 * t
        atoms.append(("H", (r * math.cos(a), r * math.sin(a), side * (2.5 + 0.03 * t))))
    lines = [f"{e} {x:.6f} {y:.6f} {z:.6f}" for e, (x, y, z) in atoms]
    ns.out.mkdir(parents=True, exist_ok=True)
    (ns.out / "large.xyz").write_text(f"{len(atoms)}\nlarge synthetic\n" + "\n".join(lines) + "\n", encoding="utf-8")
    labels = [f"H{i + 5}" for i in range(n)]  # imported protons are named by atom number
    rows = ["spin_a,spin_b,D_obs_Hz,sigma_Hz"]
    for i in range(n):
        for j in range(i + 1, n):
            rows.append(f"{labels[i]},{labels[j]},{rng.uniform(-50, 50):.3f},1")
    (ns.out / "large.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"{len(atoms)} atoms, {n * (n - 1) // 2} couplings")


if __name__ == "__main__":
    main()
