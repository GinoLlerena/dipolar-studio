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


# ---- Round 74 (A1, A2, A5): the report entry point binds the frozen roster -------------------------

sys.path.insert(0, str(ROOT / "tools" / "validation"))
import prereg  # noqa: E402


def test_cells_with_an_unknown_status_are_refused() -> None:
    with pytest.raises(ValueError):
        pl.Cell("c0", "S_zz", "maybe")  # type: ignore[arg-type]


def test_sensitivity_needs_its_conditions() -> None:
    with pytest.raises(ValueError):
        pl.sensitivity(_cells({}), ROSTER, drop=[])
    with pytest.raises(ValueError):
        pl.sensitivity(_cells({}), ROSTER, drop=["c9"])  # not in the roster


def test_the_benzene_roster_comes_from_the_hash_verified_couplings() -> None:
    roster = prereg.frozen_roster("benzene-taggar2006")
    assert len(roster) == 15 and all(comp == "S_zz" for _, comp in roster)
    assert ("1/mix1", "S_zz") in roster and ("2/0.55", "S_zz") in roster


def test_a_tampered_input_is_refused(tmp_path: Path) -> None:
    fake = tmp_path / "datasets" / "benzene-zli1132-taggar2006"
    fake.mkdir(parents=True)
    (fake / "couplings.csv").write_text("run,sample\n1,x\n", encoding="utf-8")
    with pytest.raises(ValueError, match="SHA-256"):
        prereg.frozen_roster("benzene-taggar2006", root=tmp_path)


def test_the_report_refuses_a_reduced_roster_and_names_its_protocol() -> None:
    roster = prereg.frozen_roster("benzene-taggar2006")
    with pytest.raises(ValueError):
        prereg.dataset_report("benzene-taggar2006", [pl.Cell(roster[0][0], "S_zz", "agrees")])
    report = prereg.dataset_report("benzene-taggar2006", [pl.Cell(c, k, "agrees") for c, k in roster])
    assert report["full"].name == "experimentally supported" and report["full"].agreeing == 15
    assert report["protocol_sha256"] == prereg.protocol_sha256(prereg.load())


def test_the_odcb_report_always_carries_both_drop_one_labels() -> None:
    try:
        roster = prereg.frozen_roster("odcb-chandrakumar1993")
    except FileNotFoundError:
        pytest.skip("the local ortho-dichlorobenzene files are not present")
    report = prereg.dataset_report("odcb-chandrakumar1993", [pl.Cell(c, k, "agrees") for c, k in roster])
    assert {"without II/300", "without II/302"} <= set(report)
    assert report["without II/300"].roster == 42 and report["fragile"] is False


def test_the_protocol_hash_excludes_only_the_amendment_ledger() -> None:
    p = prereg.load()
    base = prereg.protocol_sha256(p)
    assert prereg.protocol_sha256({**p, "amendments": [{"any": "entry"}]}) == base
    assert prereg.protocol_sha256({**p, "frozen_on": "2026-11-20"}) != base


def test_the_cross_field_validator() -> None:
    p = prereg.load()
    assert prereg.validate(p) == []
    odcb = p["datasets"]["odcb-chandrakumar1993"]
    for bad in (
        {**odcb, "roster_cells": 43},
        {**odcb, "estimands": ["S_zz", "S_zz"]},
        {**odcb, "conversion_matrix": [[1.0, 2.0, 3.0]]},
        {**odcb, "targets": {**odcb["targets"], "path": "datasets-local/../escape.csv"}},
    ):
        assert prereg.validate({**p, "datasets": {**p["datasets"], "odcb-chandrakumar1993": bad}}) != []


def test_the_shareable_summary_holds_labels_and_counts_only() -> None:
    """A5: per-cell targets, fits and signed discrepancies stay local; a reader could otherwise
    recover a restricted target by subtraction."""
    roster = prereg.frozen_roster("benzene-taggar2006")
    report = prereg.dataset_report("benzene-taggar2006", [pl.Cell(c, k, "agrees") for c, k in roster])
    shared = prereg.shareable(report)
    assert set(shared) == {"dataset", "protocol_sha256", "labels", "fragile"}
    for label in shared["labels"].values():
        assert set(label) == {"name", "roster", "compared", "agreeing", "disagreeing", "pending"}
