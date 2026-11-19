"""The V0.3 preregistration (docs/phase2/v0.3-preregistration.json) is consistent with the code
it freezes, and its frame conversions are right. No experimental value is fitted here: the
tests use synthetic tensors on the declared geometry.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pytest
from dipolar_core import fixed
from dipolar_core.forward import design_rows
from dipolar_core.nuclides import TABLE_VERSION, dipolar_constant_hz_a3

ROOT = Path(__file__).resolve().parents[1]
PREREG = json.loads((ROOT / "docs" / "phase2" / "v0.3-preregistration.json").read_text(encoding="utf-8"))
K = dipolar_constant_hz_a3("1H", "1H")


def _ring(angles_deg: list[float]) -> np.ndarray:
    """Protons of the declared regular hexagon at the given ring angles, in the ring's plane."""
    g = PREREG["geometry"]
    radius = g["r_cc_angstrom"] + g["r_ch_angstrom"]
    a = np.radians(angles_deg)
    return np.column_stack([radius * np.cos(a), radius * np.sin(a), np.zeros(len(a))])


def test_the_frozen_model_is_the_code_in_use() -> None:
    model = PREREG["model"]
    assert model["fixed_fit_version"] == fixed.FIXED_FIT_VERSION
    assert model["adequacy_alpha"] == fixed.ADEQUACY_ALPHA
    assert model["weak_rtol"] == fixed.WEAK_RTOL
    assert model["nuclide_table"] == TABLE_VERSION
    assert PREREG["error_model"]["covariance"] is None
    assert PREREG["criteria"]["independent"]["relative_tolerance"] == 0.05


def test_the_declared_geometry_and_the_benzene_fit() -> None:
    """Gauss & Stanton's r_e: the ortho H–H distance is r_CC + r_CH. A synthetic axial tensor on it
    is recovered by the D6h fit from the three declared pair orbits."""
    benzene = PREREG["datasets"]["benzene-taggar2006"]
    h = _ring([0, 60, 120, 180, 240, 300])
    assert np.linalg.norm(h[0] - h[1]) == pytest.approx(2.4716, abs=1e-12)
    index = {f"H{i + 1}": i for i in range(6)}
    pairs = [(index[a], index[b]) for a, b in benzene["orbits"].values()]
    s_true = np.array([-0.25, 0.0, 0.0, 0.0, 0.0])
    a5 = design_rows(h, pairs, K)
    res = fixed.fit_fixed(a5, a5 @ s_true, np.full(3, 0.01), fixed.SUBSPACES["D6h"])
    assert res.rank_verified and res.nu == benzene["nu"] == 2
    assert res.s5[0] == pytest.approx(-0.25, abs=1e-12)


def test_the_odcb_frame_map_and_conversion() -> None:
    """o-Dichlorobenzene in the paper's frame (z normal, y the in-plane C2 axis, x ∥ H2–H3): H1–H4
    on carbons 3–6 at ring angles 0°, 60°, 120°, 180°. Couplings from a synthetic paper-frame
    tensor, fitted in the V1 C2v frame after the declared map, convert back exactly."""
    odcb = PREREG["datasets"]["odcb-chandrakumar1993"]
    paper = _ring([0, 60, 120, 180])
    assert abs(paper[1, 1] - paper[2, 1]) < 1e-12  # H2–H3 is parallel to x
    v1 = paper[:, [2, 0, 1]]  # (x, y, z)_V1 = (z, x, y)_paper
    index = {f"H{i + 1}": i for i in range(4)}
    pairs = [(index[a], index[b]) for a, b in odcb["orbits"].values()]
    s_xx, s_yy = 0.03, 0.15  # the paper frame's in-plane order parameters
    s_zz = -(s_xx + s_yy)
    paper_s5 = np.array([s_zz, s_xx - s_yy, 0.0, 0.0, 0.0])
    d = design_rows(paper, pairs, K) @ paper_s5
    res = fixed.fit_fixed(design_rows(v1, pairs, K), d, np.full(4, 0.01), fixed.SUBSPACES["C2v"])
    assert res.rank_verified and res.nu == odcb["nu"] == 2
    a, c = res.s5[0], res.s5[1]
    assert (c - a) / 2 == pytest.approx(s_zz, abs=1e-12)  # S_zz, paper
    assert -(3 * a + c) / 2 == pytest.approx(s_xx - s_yy, abs=1e-12)  # S_xx − S_yy, paper


def test_the_benzene_conditions_and_targets_match_when_present() -> None:
    benzene = PREREG["datasets"]["benzene-taggar2006"]
    path = ROOT / benzene["couplings"]
    if not path.exists():
        pytest.skip("the benzene dataset is not present")
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    conditions = {(r["run"], r["sample"]) for r in rows}
    assert len(conditions) == benzene["conditions"] and len(rows) == 3 * benzene["conditions"]
    assert all(c in {f"{run}/{sample}" for run, sample in conditions} for c in benzene["flags"]["co_solutes"])
    targets = ROOT / benzene["targets"]["local_path"]
    if targets.exists():  # local only (© ACS)
        assert hashlib.sha256(targets.read_bytes()).hexdigest() == benzene["targets"]["sha256"]
        with targets.open(encoding="utf-8", newline="") as handle:
            assert {(r["run"], r["sample"]) for r in csv.DictReader(handle)} == conditions


def test_the_local_odcb_files_match_their_frozen_hashes_when_present() -> None:
    odcb = PREREG["datasets"]["odcb-chandrakumar1993"]
    targets = ROOT / odcb["targets"]["local_path"]
    if not targets.exists():
        pytest.skip("the local ortho-dichlorobenzene targets are not present (© ISMAR, local only)")
    assert hashlib.sha256(targets.read_bytes()).hexdigest() == odcb["targets"]["sha256"]
    with targets.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == odcb["targets"]["count"] == 2 * odcb["conditions"]
    assert sum(r["status"] == "pending" for r in rows) == odcb["targets"]["pending"]


def test_the_preregistration_holds_hashes_not_values() -> None:
    """Targets are referenced by path and SHA-256; no number that looks like an order parameter or
    a coupling appears in the JSON outside the frozen settings."""
    text = (ROOT / "docs" / "phase2" / "v0.3-preregistration.json").read_text(encoding="utf-8")
    for dataset in PREREG["datasets"].values():
        assert len(dataset["targets"]["sha256"]) == 64
        assert dataset["targets"]["local_path"].startswith("datasets-local/")
    import re

    numbers = {float(m) for m in re.findall(r"(?<![\w.])-?\d+\.\d+(?![\w.])", text)}
    allowed = {0.001, 1.3914, 1.0802, 0.05}
    assert numbers <= allowed, sorted(numbers - allowed)
    assert math.isclose(PREREG["geometry"]["r_cc_angstrom"] + PREREG["geometry"]["r_ch_angstrom"], 2.4716)
