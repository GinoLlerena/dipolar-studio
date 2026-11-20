"""The V0.3 label rules (round 73, A1), frozen before the V1.5 report uses them.

``tools/validation/prereg_labels.py`` turns per-cell comparisons into the preregistered labels.
Every expectation here is written from docs/phase2/v0.3-preregistration.md §6–§7, not from the
module.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "validation"))

import prereg_labels as pl  # noqa: E402

ROSTER = [(f"c{i}", comp) for i in range(4) for comp in ("S_zz", "S_xx-S_yy")]


def _cells(statuses: dict[tuple[str, str], str], reviewed: frozenset[tuple[str, str]] = frozenset()) -> list[pl.Cell]:
    return [
        pl.Cell(cond, comp, statuses.get((cond, comp), "agrees"), reviewed=(cond, comp) in reviewed)
        for cond, comp in ROSTER
    ]


def test_the_independent_criterion() -> None:
    """|S − S_pub| ≤ 0.05·|S_pub| + 2p for S_zz; the anisotropy's margin uses |S_zz,pub|."""
    # Synthetic magnitudes far from any dataset's, so no value here can match a restricted one.
    assert pl.agrees_independent("S_zz", -0.3800, -0.4000, 0.0003)  # 0.0200 ≤ 0.0206
    assert not pl.agrees_independent("S_zz", -0.3790, -0.4000, 0.0003)  # 0.0210 > 0.0206
    assert pl.agrees_independent("S_xx-S_yy", 0.2800, 0.3000, 0.0003, s_zz_pub=-0.4000)  # 0.0200 ≤ 0.0206
    assert not pl.agrees_independent("S_xx-S_yy", 0.2790, 0.3000, 0.0003, s_zz_pub=-0.4000)
    with pytest.raises(ValueError):
        pl.agrees_independent("S_xx-S_yy", 0.28, 0.30, 0.0003)  # the margin needs S_zz,pub


def test_eligibility_reasons() -> None:
    """A cell is compared only with a verified rank, a target, and (for the anisotropy) the
    published S_zz its margin needs; otherwise it is pending with the reason."""
    c = pl.classify("x", "S_zz", rank_verified=False, target=(-0.2, 0.0003), s=-0.2)
    assert (c.status, c.reason) == ("pending", "rank-unverified")
    c = pl.classify("x", "S_zz", rank_verified=True, target=None, s=-0.2)
    assert (c.status, c.reason) == ("pending", "no-target")
    c = pl.classify("x", "S_xx-S_yy", rank_verified=True, target=(0.08, 0.0003), s=0.08, s_zz_pub=None)
    assert (c.status, c.reason) == ("pending", "s_zz-target-pending")
    c = pl.classify("x", "S_xx-S_yy", rank_verified=True, target=(0.08, 0.0003), s=0.08, s_zz_pub=-0.2)
    assert c.status == "agrees"
    c = pl.classify("x", "S_zz", rank_verified=True, target=(-0.2, 0.0003), s=-0.15)
    assert c.status == "disagrees"


def test_label_precedence_and_counts() -> None:
    full = pl.dataset_label(_cells({}), ROSTER)
    assert full.name == "experimentally supported" and (full.compared, full.agreeing, full.pending) == (8, 8, 0)

    partial = pl.dataset_label(_cells({("c0", "S_zz"): "pending"}), ROSTER)
    assert partial.name == "partially supported" and (partial.compared, partial.pending) == (7, 1)

    one_of_many = pl.dataset_label(_cells({k: "pending" for k in ROSTER[1:]}), ROSTER)
    assert one_of_many.name == "partially supported" and one_of_many.compared == 1  # never "supported"

    nothing = pl.dataset_label(_cells({k: "pending" for k in ROSTER}), ROSTER)
    assert nothing.name == "pending"

    failure = pl.dataset_label(_cells({("c1", "S_zz"): "disagrees"}), ROSTER)
    assert failure.name == "unresolved failure" and failure.disagreeing == 1

    explained = pl.dataset_label(_cells({("c1", "S_zz"): "disagrees"}, frozenset({("c1", "S_zz")})), ROSTER)
    assert explained.name == "explained discrepancy"

    mixed = pl.dataset_label(
        _cells({("c1", "S_zz"): "disagrees", ("c2", "S_zz"): "disagrees"}, frozenset({("c1", "S_zz")})), ROSTER
    )
    assert mixed.name == "unresolved failure"  # an unreviewed disagreement takes precedence


def test_the_roster_is_enforced() -> None:
    """Every frozen (condition, component) must have exactly one cell: none missing, none extra."""
    with pytest.raises(ValueError):
        pl.dataset_label(_cells({})[1:], ROSTER)
    with pytest.raises(ValueError):
        pl.dataset_label([*_cells({}), pl.Cell("c9", "S_zz", "agrees")], ROSTER)
    with pytest.raises(ValueError):
        pl.dataset_label([*_cells({}), _cells({})[0]], ROSTER)


def test_the_sensitivity_recomputes_without_one_condition() -> None:
    """The full-data label stays primary; each drop-one label is reported with its counts."""
    cells = _cells({("c2", "S_zz"): "disagrees"})
    report = pl.sensitivity(cells, ROSTER, drop=["c2", "c3"])
    assert report["full"].name == "unresolved failure"
    assert report["without c2"].name == "experimentally supported" and report["without c2"].compared == 6
    assert report["without c3"].name == "unresolved failure"
    assert report["fragile"] is True
    steady = pl.sensitivity(_cells({}), ROSTER, drop=["c2", "c3"])
    assert steady["fragile"] is False


def test_the_rules_are_the_preregistered_ones() -> None:
    """Added in the round 73 fix commit: the module's constants and precedence are the JSON's."""
    import json

    prereg = json.loads((ROOT / "docs" / "phase2" / "v0.3-preregistration.json").read_text(encoding="utf-8"))
    criteria = prereg["criteria"]
    assert pl.RELATIVE_TOLERANCE == criteria["independent"]["relative_tolerance"]
    assert pl.PRECISION_FACTOR == criteria["independent"]["precision_factor"]
    assert list(pl.PRECEDENCE) == criteria["label_precedence"]
