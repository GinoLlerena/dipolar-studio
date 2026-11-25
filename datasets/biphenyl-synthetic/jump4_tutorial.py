"""Synthetic biphenyl couplings under the symmetric four-site jump, for the jump4 robot tutorial
(Phase 2 V1.5b; ``robot.py --scenario jump4-tutorial``).

Each value is the independent reference's explicit four-conformer average
(``tools/reference/biphenyl_reference.design_jump_explicit``: conformers at +φ, −φ, 180−φ and
180+φ, each tensor diagonal in its own acute-bisector frame) at the generator's truth
(``truth.json``: φ, S_zz, Δ), for the first pair of each symmetry class of ``couplings.csv``. No
noise is added; values are written at 0.001 Hz, with that file's σ. The format is the example's
couplings format (spin labels, the class and its multiplicity, D and σ in Hz), so the file
reconciles with the synthetic example project as a user's file would.

The truth was generated with the rigid model, so these couplings are not ``couplings.csv``: they
are what the same molecule would give if its rings jumped between the four conformers. A
four-site-jump fit recovers the truth; a rigid fit of them is a different model.

Usage:  python3 jump4_tutorial.py   (numpy only; writes jump4-couplings.csv)
"""

from __future__ import annotations

import csv
import io
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tools" / "reference"))

import biphenyl_reference as R  # noqa: E402

COLUMNS = ["spin_a", "spin_b", "equivalent_pairs", "multiplicity", "D_obs_Hz", "sigma_Hz"]


def rows() -> list[dict[str, str]]:
    truth = json.loads((HERE / "truth.json").read_text(encoding="utf-8"))
    with (HERE / "couplings.csv").open(encoding="utf-8", newline="") as handle:
        source = list(csv.DictReader(handle))
    pairs = [(r["spin_a"], r["spin_b"]) for r in source]
    d = R.design_jump_explicit(truth["phi_deg"], pairs) @ np.array([truth["Szz"], truth["Delta"]])
    return [
        {
            "spin_a": r["spin_a"],
            "spin_b": r["spin_b"],
            "equivalent_pairs": r["equivalent_pairs"],
            "multiplicity": r["multiplicity"],
            "D_obs_Hz": f"{value:.3f}",
            "sigma_Hz": r["sigma_Hz"],
        }
        for r, value in zip(source, d, strict=True)
    ]


def write(path: Path) -> None:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows())
    path.write_text(out.getvalue(), encoding="utf-8", newline="\n")  # LF on every platform


if __name__ == "__main__":
    write(HERE / "jump4-couplings.csv")
