"""Phase 2 V1.5b: the restricted-fit scan tier, frozen before its implementation.

The plan ("Check the staged index and outward artifacts", docs/phase2/v1.5-plan.md) adds to the
staged-index scan "a laptop-only tier sourced from full-precision local fit outputs for cells with
restricted targets, with declared rounding variants and value-free diagnostics", required "after
local results exist", with "an explicit pre-result status before then".

What is frozen here:

- **The source.** The report workflow writes each dataset's full-precision fit values (the
  paper-frame estimates of every fitted condition and each compared cell's discrepancy) to
  ``datasets-local/verification/<dataset>.fit-values.json``, never anywhere else.
- **The variants.** Every fit value is matched as written (its shortest repr) and rounded to 4–8
  significant digits, half-up, half-even and truncated, from both its repr and its exact binary
  value, in any path; and at 3 significant digits in the Phase 2 and validation docs. A literal
  must carry at least the tier's significant digits, as in the existing tiers.
- **When it is required.** The ledger's first-fit row (gates.md §3) decides: while it is
  ``empty`` and no local fit output exists, the status is ``pre-result``; once a fit is logged the
  status is ``results`` and the local outputs must exist and be well formed. Local fit outputs
  without a logged fit are a first-fit-gate problem.
- **Value-free diagnostics.** Problems name the file and the entry, never a value; the status line
  gives counts only. Hits stay ``path:line``.
- **The receipt.** From ``FIT_TIER_SINCE`` on, each scan row of gates.md §6 records the tier's
  status.

All values here are synthetic: no experimental coupling is fitted (the V1.5a first-fit gate).

**Amended in round 83** (A1–A3, B1), before the fixes: a fit is logged in the ledger's
first-fit log (§10), not the §3 row; the staged check reads the staged ledger and refuses a log
that drops a committed row; each logged submission needs its own retained output, bound to it and
covering the roster exactly; diagnostics never repeat a key or file name; every scan receipt row
is well formed, and the first one under the tier is pinned.

**Amended in round 84** (A1–A4, A6), before the fixes: an output is required only for a
submission in the committed log; the record declares every frozen roster cell (the conditions of
the hash-verified couplings) on both tracks, a value or a pending reason each; unexpected file
names are never printed; each record carries its fits' provenance and is one run of a hash-bound
chain with its report. These xfail through ``_r84()`` while ``tools/validation/fit_record.py`` is
absent.

**Pending implementation.** While ``restricted_scan`` has no ``fit_tier`` (or ``verification``
no ``write_fit_values``), these tests xfail through ``_rs()`` and ``_v()`` alone; once those
names exist, any exception fails. The round 83 amendments xfail through ``_r83()`` while
``tools/validation/first_fit_log.py`` is absent.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import math
import re
import subprocess
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "datasets"))
sys.path.insert(0, str(ROOT / "tools" / "validation"))

import restricted_scan  # noqa: E402
import test_v0_preregistration  # noqa: E402
from test_v15_verification import (  # noqa: E402
    BENZENE,
    FOUR,
    ODCB,
    Synthetic,
    _authors_benzene,
    _clock,  # noqa: F401  (autouse: the runner's clock)
    _condition_keys,
    _default_targets,
    _leaks,
    _method,
    _truth,
    _unverified_call,
)

LEDGER = ROOT / "docs" / "phase2" / "verification" / "gates.md"
LEDGER_REL = Path("docs/phase2/verification/gates.md")
FIRST_FIT_ROW = (
    "| First experimental fit submission (UTC, release or commit, protocol revision, dataset, runner role) | empty |"
)
LOGGED_ROW = (
    "| First experimental fit submission (UTC, release or commit, protocol revision, dataset, runner role) "
    "| 2026-11-25T10:00Z, v0.2.0b1, `263f268`, benzene-taggar2006, owner |"
)


def _rs() -> Any:
    """The scanner with its fit tier, or an xfail while (and only while) the tier is not written."""
    if not hasattr(restricted_scan, "fit_tier"):
        pytest.xfail("V1.5b: the restricted-fit scan tier is not written yet")
    return restricted_scan


def _v() -> Any:
    import verification

    if not hasattr(verification, "write_fit_values"):
        pytest.xfail("V1.5b: the report workflow does not write its fit values yet")
    return verification


# ================================================================= the declared variants
X = -0.48736829  # a synthetic fit value
DOCS = ("docs/phase2/x.md", "docs/validation/y.md")


def _hits(path: str, text: str, values: list[float]) -> list[str]:
    rs = _rs()
    return rs.scan([(path, text.encode("utf-8"))], rs.fit_tiers(values), frozenset())


@pytest.mark.parametrize(
    "form",
    [
        "-0.48736829",  # as written
        "0.48736829",
        "0.4873683",  # 7 significant digits
        "0.487368",  # 6
        "0.48737",  # 5, half-up
        "0.48736",  # 5, truncated
        "0.4874",  # 4, half-up
        "0.4873",  # 4, truncated
        "−0.4874",  # U+2212
        "-4.874e-1",
        "4.8737E-01",
        "48.737e-2",
    ],
)
def test_every_declared_rounding_of_a_fit_value_is_found(form: str) -> None:
    for path in ("notes.md", "src/x.py", *DOCS):
        assert _hits(path, f"the fit gave {form} here", [X]) == [f"{path}:1"], (path, form)


def test_half_up_and_half_even_ties_are_both_found() -> None:
    for form in ("0.1235", "0.1234"):  # 0.12345 at four significant digits
        assert _hits("notes.md", f"x {form} y", [0.12345]) == ["notes.md:1"], form


def test_eight_significant_digits_and_the_exact_binary_value() -> None:
    y = 0.1234567891234
    for form in ("0.12345679", "0.12345678", "0.1234568"):
        assert _hits("notes.md", f"x {form} y", [y]) == ["notes.md:1"], form


def test_three_significant_digits_only_in_the_phase2_and_validation_docs() -> None:
    for path in DOCS:
        assert _hits(path, "about 0.487", [X]) == [f"{path}:1"]
    for path in ("notes.md", "src/x.py", "docs/beta/testers.md"):
        assert _hits(path, "about 0.487", [X]) == [], path


@pytest.mark.parametrize("form", ["0.4875", "0.4872", "0.49", "48736", "0.48738", "1.0.4874", "v0.4874x"])
def test_other_numbers_are_not_flagged(form: str) -> None:
    for path in ("notes.md", *DOCS):
        assert _hits(path, f"x {form} y", [X]) == [], (path, form)


def test_small_values_need_their_significant_digits() -> None:
    d = 0.00123456  # a discrepancy
    assert _hits("notes.md", "x 0.001235 y", [d]) == ["notes.md:1"]
    assert _hits("notes.md", "x 0.0012 y", [d]) == []  # two significant digits: below every tier
    assert _hits("docs/phase2/x.md", "x 0.00123 y", [d]) == ["docs/phase2/x.md:1"]


def test_zero_and_whole_values_do_not_flag_everything() -> None:
    assert _hits("notes.md", "0.0000 and 0 and 1.0000 and 2", [0.0, -0.0]) == []
    assert _hits("notes.md", "a 1.000 b", [1.0]) == []  # a whole number has one significant digit


# ============================================================= when the tier is required
LOG_PY = ROOT / "tools" / "validation" / "first_fit_log.py"
PREREG_REL = Path("docs/phase2/v0.3-preregistration.json")
PROTOCOL = "263f26857da15df184c7e662325e39036c307a02bc0042c610d6b8d4dab700b9"
LAST_LOG_ROW = "| 2026-11-22T14:11Z | no-fit attestation | — | — | — | — |"
FREEZE_ROW = "| 2026-11-24T09:00Z | freeze approved | — | — | — | — |"
AT = "2026-11-25T10:00Z"


def _r83() -> Any:
    """Round 83 (A1–A3): the scanner and its gate as amended. An xfail while (and only while) the
    first-fit log's module is not written."""
    rs = _rs()
    if not LOG_PY.is_file():
        pytest.xfail("round 83: tools/validation/first_fit_log.py is not written yet")
    return rs


def _submission(dataset: str = BENZENE, protocol: str = PROTOCOL) -> dict[str, str]:
    return {
        "dataset": dataset,
        "runner": "owner",
        "at": AT,
        "release_or_commit": "v0.2.0b1",
        "protocol_sha256": protocol,
    }


def _log_row(s: dict[str, str]) -> str:
    cells = [s["at"], "submission", s["dataset"], s["runner"], s["release_or_commit"], s["protocol_sha256"]]
    return "| " + " | ".join(cells) + " |"


def _ledger(*submissions: dict[str, str]) -> str:
    text = LEDGER.read_text(encoding="utf-8")
    if not submissions:
        return text
    return text.replace(LAST_LOG_ROW, "\n".join([LAST_LOG_ROW, FREEZE_ROW, *(_log_row(s) for s in submissions)]))


def test_the_real_ledger_has_no_logged_fit_yet() -> None:
    rs = _r83()
    text = LEDGER.read_text(encoding="utf-8")
    assert FIRST_FIT_ROW in text.splitlines()
    assert rs.first_fit_logged(text) is False
    assert rs.first_fit_logged(_ledger(_submission())) is True
    # The §3 row is no longer how a fit is logged, but a filled one still counts as logged.
    assert rs.first_fit_logged(text.replace(FIRST_FIT_ROW, LOGGED_ROW)) is True


@pytest.mark.parametrize("change", ["the row missing", "the row twice", "the value blank", "the log malformed"])
def test_an_unreadable_first_fit_record_is_refused(change: str) -> None:
    rs = _r83()
    text = LEDGER.read_text(encoding="utf-8")
    if change == "the row missing":
        text = text.replace(FIRST_FIT_ROW + "\n", "")
    elif change == "the row twice":
        text = text.replace(FIRST_FIT_ROW, FIRST_FIT_ROW + "\n" + LOGGED_ROW)
    elif change == "the value blank":
        text = text.replace(FIRST_FIT_ROW, FIRST_FIT_ROW.replace("| empty |", "|  |"))
    else:
        text = text.replace(LAST_LOG_ROW, LAST_LOG_ROW + "\n| 2026-11-01T00:00Z | freeze approved | — | — | — | — |")
    with pytest.raises(ValueError):
        rs.first_fit_logged(text)


def _root(tmp_path: Path, *, logged: bool, protocol: str = PROTOCOL) -> Path:
    """A checkout with the ledger (logging one benzene submission, or none) and a copy of the
    preregistration bound to synthetic couplings for both datasets: the roster the scan reads
    (round 84, A2)."""
    ledger = _ledger(_submission(protocol=protocol)) if logged else _ledger()
    (tmp_path / LEDGER_REL).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / LEDGER_REL).write_text(ledger, encoding="utf-8")
    prereg = json.loads((ROOT / PREREG_REL).read_text(encoding="utf-8"))
    for dataset in (BENZENE, ODCB):
        if not (tmp_path / prereg["datasets"][dataset]["couplings"]["path"]).is_file():
            prereg["datasets"][dataset] = Synthetic(tmp_path, dataset).prereg["datasets"][dataset]
    _write_prereg(tmp_path, prereg)
    return tmp_path


def _write_prereg(root: Path, prereg: dict[str, Any]) -> None:
    (root / PREREG_REL).parent.mkdir(parents=True, exist_ok=True)
    (root / PREREG_REL).write_text(json.dumps(prereg, indent=1), encoding="utf-8")


VALUES = [-0.48736829, 0.0612349871, 0.00123456]


def _conditions(dataset: str) -> int:
    return int(json.loads((ROOT / PREREG_REL).read_text(encoding="utf-8"))["datasets"][dataset]["conditions"])


def _estimands(dataset: str) -> list[str]:
    return list(json.loads((ROOT / PREREG_REL).read_text(encoding="utf-8"))["datasets"][dataset]["estimands"])


# Round 84 (A2, A6), amended before the fix: the record declares every roster cell of the frozen
# roster (the conditions of the hash-verified couplings) on both tracks, an estimate and a
# discrepancy each, as a value or as the cell's pending reason; it carries each fit's provenance;
# and it is one run of a chain: its run number, the SHA-256 of the record it replaced, and the
# SHA-256 of that run's local report, kept as reports/<dataset>.<run>.md.
R84_PY = ROOT / "tools" / "validation" / "fit_record.py"
REPORT_TEXT = "# Verification report (local): synthetic\n"
QUANTITIES = ("estimate", "discrepancy", "reproduction estimate", "reproduction discrepancy")


def _r84() -> Any:
    rs = _r83()
    if not R84_PY.is_file():
        pytest.xfail("round 84: the fixes are not written yet")
    return rs


def _declared(
    condition: str, component: str, quantity: str, value: float | None, reason: str | None = None
) -> dict[str, Any]:
    return {"condition": condition, "component": component, "quantity": quantity, "value": value, "reason": reason}


def _fit_provenance(n: int) -> dict[str, Any]:
    return {"science_hash": f"{n:064x}", "fit_version": "synthetic", "model": {"kind": "fixed"}}


def _record(
    dataset: str = BENZENE,
    values: list[float] = VALUES,
    protocol: str = PROTOCOL,
    *,
    run: int = 1,
    previous: str | None = None,
) -> dict[str, Any]:
    """A complete record bound to the logged submission: an estimate for every roster cell (the
    given values first, then fillers), a discrepancy for every cell (the last given value first,
    then fillers: a signed run with every target present; amended in round 85, when a no-target
    declaration became checkable), and a pending authors'-analysis track."""
    *estimates, discrepancy = values
    conditions = _condition_keys(dataset)
    cells = [(c, e) for c in conditions for e in _estimands(dataset)]
    fill = [0.2 + 0.0731 * k for k in range(len(cells))]
    given = estimates + fill[len(estimates) :]
    entries = [_declared(c, e, "estimate", given[k]) for k, (c, e) in enumerate(cells)]
    gaps = [discrepancy] + [0.0013 + 0.000173 * k for k in range(1, len(cells))]
    entries += [_declared(c, e, "discrepancy", gaps[k]) for k, (c, e) in enumerate(cells)]
    for q in ("reproduction estimate", "reproduction discrepancy"):
        entries += [_declared(c, e, q, None, "inputs-undocumented") for c, e in cells]
    return {
        "dataset": dataset,
        "protocol_sha256": protocol,
        "submission": _submission(dataset, protocol),
        "run": run,
        "previous_sha256": previous,
        "report_sha256": hashlib.sha256(REPORT_TEXT.encode()).hexdigest(),
        "provenance": {
            "versions": {"dipolar-core": "synthetic", "dipolar-app": "synthetic"},
            "flags": [],
            "method": {"mode": "pending", "documented": [], "geometry": None, "weights": None, "sources": {}},
            "fits": {"independent": {c: _fit_provenance(i) for i, c in enumerate(conditions)}, "reproduction": {}},
        },
        "values": entries,
    }


def _count(dataset: str) -> int:
    return 2 * _conditions(dataset) * len(_estimands(dataset))


def _fit_file(root: Path, record: Any, name: str = f"{BENZENE}.fit-values.json", raw: str | None = None) -> Path:
    """Write a fit output, and the local report of its run when the record names one."""
    path = root / "datasets-local" / "verification" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(raw if raw is not None else json.dumps(record), encoding="utf-8")
    if isinstance(record, dict) and isinstance(record.get("run"), int) and record.get("dataset") in (BENZENE, ODCB):
        report = root / "datasets-local" / "verification" / "reports" / f"{record['dataset']}.{record['run']}.md"
        report.parent.mkdir(parents=True, exist_ok=True)
        if not report.exists():
            report.write_text(REPORT_TEXT, encoding="utf-8")
    return path


def _sha_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _digits_free(texts: list[str], values: list[float] = VALUES) -> bool:
    """No value in any rendering, and no run of four or more digits outside the file names."""
    plain = [t.replace(BENZENE, "").replace(ODCB, "") for t in texts]
    return _leaks("\n".join(plain), values) == [] and not any(re.search(r"\d{4,}", t) for t in plain)


def test_before_any_result_the_status_is_pre_result(tmp_path: Path) -> None:
    rs = _r83()
    fit = rs.fit_tier(_root(tmp_path, logged=False))
    assert (fit.status, fit.tiers, fit.problems, fit.files, fit.values) == ("pre-result", [], [], 0, 0)
    assert rs.status_line(fit).startswith("fit tier: pre-result")
    # Other local files (the Markdown report, the inputs) are not fit outputs.
    (tmp_path / "datasets-local" / "verification").mkdir(parents=True)
    (tmp_path / "datasets-local" / "verification" / "benzene-report.md").write_text("0.4874\n", encoding="utf-8")
    assert rs.fit_tier(tmp_path).status == "pre-result"


def test_after_a_logged_fit_the_local_outputs_are_scanned(tmp_path: Path) -> None:
    rs = _r84()
    root = _root(tmp_path, logged=True)
    _fit_file(root, _record())
    fit = rs.fit_tier(root)
    assert (fit.status, fit.problems, fit.files, fit.values) == ("results", [], 1, _count(BENZENE))
    line = rs.status_line(fit)
    assert line.startswith("fit tier: results") and _digits_free([line])
    assert rs.scan([("notes.md", b"S = 0.4874\n")], fit.tiers, frozenset()) == ["notes.md:1"]
    assert rs.scan([("notes.md", b"d = 0.001235\n")], fit.tiers, frozenset()) == ["notes.md:1"]


def test_each_logged_submission_needs_its_own_output(tmp_path: Path) -> None:
    """A2: logging two datasets and supplying one leaves the other missing; an output of an
    unlogged dataset satisfies nothing."""
    rs = _r84()
    _root(tmp_path, logged=False)  # the synthetic roster (corrected after the round 84 gate)
    (tmp_path / LEDGER_REL).write_text(_ledger(_submission(BENZENE), _submission(ODCB)), encoding="utf-8")
    _fit_file(tmp_path, _record(ODCB, [0.7123456, -0.0312345, 0.0004567]), name=f"{ODCB}.fit-values.json")
    fit = rs.fit_tier(tmp_path)
    assert fit.status == "results" and fit.problems
    assert _digits_free(fit.problems)
    _fit_file(tmp_path, _record())
    both = rs.fit_tier(tmp_path)
    assert (both.problems, both.files, both.values) == ([], 2, _count(BENZENE) + _count(ODCB))
    assert rs.scan([("notes.md", b"0.71235\n")], both.tiers, frozenset()) == ["notes.md:1"]
    (tmp_path / "datasets-local" / "verification" / f"{BENZENE}.fit-values.json").unlink()
    assert rs.fit_tier(tmp_path).problems  # deleting one dataset's output fails the check


def test_a_logged_fit_without_local_outputs_is_a_problem(tmp_path: Path) -> None:
    rs = _r83()
    fit = rs.fit_tier(_root(tmp_path, logged=True))
    assert fit.status == "results" and fit.problems
    assert any("datasets-local/verification" in p for p in fit.problems)


def test_a_filled_section_3_row_without_a_logged_submission_is_a_problem(tmp_path: Path) -> None:
    rs = _r83()
    root = _root(tmp_path, logged=False)
    (root / LEDGER_REL).write_text(_ledger().replace(FIRST_FIT_ROW, LOGGED_ROW), encoding="utf-8")
    fit = rs.fit_tier(root)
    assert fit.status == "results" and fit.problems


def test_local_outputs_without_a_logged_fit_are_a_first_fit_gate_problem(tmp_path: Path) -> None:
    rs = _r84()
    root = _root(tmp_path, logged=False)
    _fit_file(root, _record())
    fit = rs.fit_tier(root)
    assert fit.problems and any("first-fit log" in p for p in fit.problems)
    assert fit.tiers  # the values are still scanned
    assert _digits_free(fit.problems)


def test_a_missing_ledger_is_a_problem(tmp_path: Path) -> None:
    rs = _r83()
    fit = rs.fit_tier(tmp_path)
    assert fit.status == "results"  # unknown: required
    assert fit.problems and any("gates.md" in p for p in fit.problems)


C0 = _condition_keys(BENZENE)[0]


def _entry(**changes: Any) -> dict[str, Any]:
    record = _record()
    record["values"][0].update(changes)
    return record


def _without_cell() -> dict[str, Any]:
    record = _record()
    del record["values"][1]
    return record


def _with(**changes: Any) -> dict[str, Any]:
    return {**_record(), **changes}


def _extra_entry(entry: dict[str, Any]) -> dict[str, Any]:
    record = _record()
    record["values"].append(entry)
    return record


def _without(quantity: str) -> dict[str, Any]:
    """One roster cell's declaration of ``quantity`` removed (round 84, A2)."""
    record = _record()
    k = next(i for i, e in enumerate(record["values"]) if e["quantity"] == quantity and e["condition"] != C0)
    del record["values"][k]
    return record


def _renamed(condition: str, *, provenance: bool = True) -> dict[str, Any]:
    """A frozen condition replaced by an invented one everywhere in the record, or in its
    declarations only (round 84, A2)."""
    record = _record()
    for e in record["values"]:
        if e["condition"] == C0:
            e["condition"] = condition
    if provenance:
        fits = record["provenance"]["fits"]["independent"]
        fits[condition] = fits.pop(C0)
    return record


def _changed(change: Any) -> dict[str, Any]:
    record = _record()
    change(record)
    return record


MALFORMED: dict[str, Any] = {
    "not JSON": "{0.4873683",
    "a list": [0.48736829],
    "no values": {k: v for k, v in _record().items() if k != "values"},
    "no entries": _with(values=[]),
    "an entry without its value": _with(values=[{"condition": C0, "component": "S_zz", "quantity": "estimate"}]),
    "a value as text": _entry(value="0.48736829"),
    "a non-finite value": _entry(value=math.nan),
    "a boolean value": _entry(value=True),
    "an unknown quantity": _entry(quantity="guess"),
    "an unknown dataset": _with(dataset="tfb"),
    "another dataset's file": _record(ODCB),
    "an unknown field": _with(note="0.48736829"),
    "an unknown field named by a value": _with(**{"0.48736829": 1}),
    # Round 83, A2: bound to the logged submission, with exact coverage.
    "no submission": {k: v for k, v in _record().items() if k != "submission"},
    "an unlogged submission": _with(submission={**_submission(), "at": "2026-11-25T11:00Z"}),
    "a blank protocol revision": _with(protocol_sha256=""),
    "another protocol revision": _record(protocol="0" * 64),
    "a missing cell": _without_cell(),
    "a repeated cell": _extra_entry({**_record()["values"][1]}),
    "an extra condition": _extra_entry(_declared("c99", "S_zz", "estimate", 0.3)),
    "an unknown component": _extra_entry(_declared(C0, "S_xy", "estimate", 0.3)),
    "a discrepancy without its estimate": _extra_entry(_declared("c98", "S_zz", "discrepancy", 0.3)),
    # Round 84, A2: the frozen roster's own keys, every cell declared on both tracks.
    "an invented condition": _renamed("9/s99"),
    "an invented condition in the declarations only": _renamed("9/s99", provenance=False),  # mutation
    "an estimate undeclared": _without("estimate"),
    "a discrepancy undeclared": _without("discrepancy"),
    "a reproduction estimate undeclared": _without("reproduction estimate"),
    "a reproduction discrepancy undeclared": _without("reproduction discrepancy"),
    "a value and a reason": _entry(reason="rank-unverified"),
    "neither a value nor a reason": _entry(value=None),
    "an unknown reason": _changed(lambda r: r["values"][-1].update(reason="not wanted")),
    "an unknown reason for a discrepancy": _changed(  # added for a surviving mutant
        lambda r: next(e for e in r["values"] if e["quantity"] == "discrepancy").update(value=None, reason="not wanted")
    ),
    "a discrepancy value without an estimate value": _changed(
        lambda r: r["values"][0].update(value=None, reason="rank-unverified")
    ),
    "an independent estimate declared undocumented": _changed(
        lambda r: r["values"][3].update(value=None, reason="inputs-undocumented")
    ),
    "a reproduction track pending in part": _changed(
        lambda r: next(e for e in r["values"] if e["quantity"] == "reproduction estimate").update(
            reason="rank-unverified"
        )
    ),
    # Round 84, A6: each fit's provenance, and the run's place in its chain.
    "no provenance": {k: v for k, v in _record().items() if k != "provenance"},
    "a fit without its provenance": _changed(lambda r: r["provenance"]["fits"]["independent"].pop(C0)),
    "a fit without its science hash": _changed(
        lambda r: r["provenance"]["fits"]["independent"][C0].pop("science_hash")
    ),
    "a provenance without its versions": _changed(lambda r: r["provenance"].pop("versions")),
    "a provenance without its method": _changed(lambda r: r["provenance"].pop("method")),
    "authors' fits on a pending track": _changed(
        lambda r: r["provenance"]["fits"].update(reproduction={C0: _fit_provenance(0)})
    ),
    "no run number": {k: v for k, v in _record().items() if k != "run"},
    "a run number that is not a count": _with(run=0),
    "a first run with a predecessor": _with(previous_sha256="1" * 64),
    "no report hash": _with(report_sha256=None),
    "a report hash that is not its report's": _with(report_sha256="2" * 64),
}


@pytest.mark.parametrize("name", list(MALFORMED))
def test_a_malformed_fit_output_is_a_value_free_problem(tmp_path: Path, name: str) -> None:
    rs = _r84()
    root = _root(tmp_path, logged=True)
    bad = MALFORMED[name]
    path = _fit_file(root, bad, raw=bad if isinstance(bad, str) else None)
    fit = rs.fit_tier(root)
    assert fit.problems, name
    assert any(path.name in p for p in fit.problems), fit.problems
    assert _digits_free([*fit.problems, rs.status_line(fit)]), fit.problems


def test_the_well_formed_entries_of_a_damaged_file_are_still_scanned(tmp_path: Path) -> None:
    rs = _r84()
    root = _root(tmp_path, logged=True)
    _fit_file(root, _extra_entry({**_declared(C0, "S_zz", "estimate", None), "value": "x"}))
    fit = rs.fit_tier(root)
    assert fit.problems and fit.values == _count(BENZENE)
    assert rs.scan([("notes.md", b"0.4874\n")], fit.tiers, frozenset()) == ["notes.md:1"]


def test_an_unexpected_file_name_is_not_printed(tmp_path: Path) -> None:
    """A3: a file name can carry a value; the diagnostic does not repeat it."""
    rs = _r84()
    root = _root(tmp_path, logged=True)
    _fit_file(root, _record())
    _fit_file(root, _record(), name="benzene 0.48736829.fit-values.json")
    fit = rs.fit_tier(root)
    assert fit.problems and _digits_free(fit.problems)


@pytest.mark.parametrize(
    "name",
    [
        "benzene-0.48736829.fit-values.json",
        "retained/benzene-taggar2006.0.48736829.fit-values.json",
        "retained/0.4873683.fit-values.json",
    ],
)
def test_no_unexpected_file_name_is_printed_by_the_scan(
    tmp_path: Path, name: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Round 84 (A3): a name of safe characters that the scan does not expect is not printed
    either, by the tier or by the command."""
    rs = _r84()
    root = _root(tmp_path, logged=True)
    _fit_file(root, _record())
    _fit_file(root, _record(), name=name)
    fit = rs.fit_tier(root)
    assert fit.problems and _digits_free(fit.problems)
    _git(root, "init", "-q")
    _git(root, "add", str(LEDGER_REL))
    assert rs.main(["--root", str(root)]) == 1
    out = capsys.readouterr()
    assert _digits_free([out.out, out.err]) and "0.487" not in out.out + out.err


def test_the_roster_comes_from_the_hash_verified_couplings(tmp_path: Path) -> None:
    """Round 84 (A2; added for a surviving mutant): couplings changed after the freeze give no
    roster, so the record's declarations cannot be checked and the record binds nothing."""
    rs = _r84()
    root = _root(tmp_path, logged=True)
    path = _fit_file(root, _record())
    assert rs.fit_tier(root).problems == []
    prereg = json.loads((root / PREREG_REL).read_text(encoding="utf-8"))
    couplings = root / prereg["datasets"][BENZENE]["couplings"]["path"]
    couplings.write_text(couplings.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    fit = rs.fit_tier(root)
    assert any(path.name in p and "roster" in p for p in fit.problems)
    assert _digits_free(fit.problems)


def _chain(root: Path, runs: int, dataset: str = BENZENE) -> list[Path]:
    """``runs`` runs of one submission: retained/<dataset>.<n> for the earlier ones, each bound to
    its predecessor by hash, and the current output."""
    paths, previous = [], None
    for n in range(1, runs + 1):
        name = f"{dataset}.fit-values.json" if n == runs else f"retained/{dataset}.{n}.fit-values.json"
        values = [VALUES[0] + 0.0101 * n, *VALUES[1:]]
        path = _fit_file(root, _record(dataset, values, run=n, previous=previous), name=name)
        previous = _sha_of(path)
        paths.append(path)
    return paths


def test_a_rerun_keeps_the_earlier_output(tmp_path: Path) -> None:
    """A2 (round 83), amended for round 84 (A6): a retained output still binds its submission and
    is still scanned, and the chain of runs is whole."""
    rs = _r84()
    root = _root(tmp_path, logged=True)
    _chain(root, 1)
    fit = rs.fit_tier(root)
    assert (fit.problems, fit.files, fit.values) == ([], 1, _count(BENZENE))
    for p in (root / "datasets-local" / "verification").rglob("*.json"):
        p.unlink()
    _chain(root, 3)
    both = rs.fit_tier(root)
    assert (both.problems, both.files) == ([], 3)
    assert rs.scan([("notes.md", b"0.4773\n")], both.tiers, frozenset()) == ["notes.md:1"]  # the first run


CHAIN_BREAKS = [
    "a retained output deleted",
    "the last retained output deleted",
    "the current output deleted",
    "a retained output edited",
    "a run's report deleted",
    "a run's report edited",
    "a retained output renumbered",
    "a run number out of place",
]


@pytest.mark.parametrize("name", CHAIN_BREAKS)
def test_a_broken_chain_of_runs_is_a_problem(tmp_path: Path, name: str) -> None:
    """Round 84 (A6): deleting, editing or renumbering any run's output or report is found."""
    rs = _r84()
    root = _root(tmp_path, logged=True)
    first, second, current = _chain(root, 3)
    reports = root / "datasets-local" / "verification" / "reports"
    if name == "a retained output deleted":
        first.unlink()
    elif name == "the last retained output deleted":
        second.unlink()
    elif name == "the current output deleted":
        current.unlink()
    elif name == "a retained output edited":
        first.write_text(first.read_text(encoding="utf-8").replace("synthetic", "edited"), encoding="utf-8")
    elif name == "a run's report deleted":
        (reports / f"{BENZENE}.1.md").unlink()
    elif name == "a run's report edited":
        (reports / f"{BENZENE}.2.md").write_text(REPORT_TEXT + "edited\n", encoding="utf-8")
    elif name == "a retained output renumbered":
        second.rename(second.with_name(f"{BENZENE}.3.fit-values.json"))
    else:
        record = json.loads(current.read_text(encoding="utf-8"))
        current.write_text(json.dumps({**record, "run": 4}), encoding="utf-8")
    fit = rs.fit_tier(root)
    assert fit.problems, name
    assert _digits_free([*fit.problems, rs.status_line(fit)]), fit.problems


# ================================================================ the staged-index entry
def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@invalid", *args],
        cwd=root,
        check=True,
        capture_output=True,
    )


def _restricted_inputs(root: Path) -> None:
    """Synthetic stand-ins for the three local restricted files, in their real columns."""
    couplings, odcb_targets, benzene_targets = restricted_scan.restricted_files(root)
    couplings.parent.mkdir(parents=True, exist_ok=True)
    benzene_targets.parent.mkdir(parents=True, exist_ok=True)
    couplings.write_text("D_token\n917.64\n", encoding="utf-8")
    odcb_targets.write_text("value,fig2_value\n0.31415,\n", encoding="utf-8")
    benzene_targets.write_text("S_zz\n-0.27182\n", encoding="utf-8")


def _repo(tmp_path: Path, *, logged: bool, staged: str) -> Path:
    root = _root(tmp_path, logged=logged)
    _restricted_inputs(root)
    _git(root, "init", "-q")
    (root / "notes.md").write_text(staged, encoding="utf-8")
    _git(root, "add", "notes.md", str(LEDGER_REL))
    return root


def test_the_staged_index_check_includes_the_fit_tier(tmp_path: Path) -> None:
    rs = _r84()
    root = _repo(tmp_path, logged=True, staged="clean\nthe fit was 0.4874\n")
    _fit_file(root, _record())
    assert rs.check_staged(root) == ["notes.md:2"]


def test_the_staged_index_check_keeps_the_input_tiers(tmp_path: Path) -> None:
    rs = _r83()
    root = _repo(tmp_path, logged=False, staged="a target -0.27182\n")
    assert rs.check_staged(root) == ["notes.md:1"]


def test_before_any_result_the_check_has_no_fit_source(tmp_path: Path) -> None:
    rs = _r83()
    root = _repo(tmp_path, logged=False, staged="0.4874\n")
    assert rs.check_staged(root) == []


def test_the_staged_index_check_fails_on_a_tier_problem(tmp_path: Path) -> None:
    """Amended for round 84 (A1): the submission is committed, and its output is missing."""
    rs = _r83()
    root = _repo(tmp_path, logged=True, staged="clean\n")
    _git(root, "commit", "-q", "-m", "a logged fit")  # logged and committed, but no local fit output
    problems = rs.check_staged(root)
    assert problems and any("datasets-local/verification" in p for p in problems)


def test_the_staged_check_reads_the_staged_ledger(tmp_path: Path) -> None:
    """A1: the receipt binds the ledger that is staged, not the working copy's. Amended for round
    84: an output bound to the staged submission is not an output without a submission."""
    rs = _r84()
    root = _repo(tmp_path, logged=True, staged="clean\n")  # the staged ledger logs a fit
    _fit_file(root, _record())
    (root / LEDGER_REL).write_text(_ledger(), encoding="utf-8")  # the working copy does not
    assert rs.check_staged(root) == []


def test_a_staged_submission_needs_its_output_only_once_committed(tmp_path: Path) -> None:
    """Round 84 (A1): the commit that logs a submission passes before its fit is run (the runner
    fits only a committed submission); from then on, its output is required."""
    rs = _r84()
    root = _repo(tmp_path, logged=False, staged="clean\n")
    _git(root, "commit", "-q", "-m", "the ledger before the submission")
    (root / LEDGER_REL).write_text(_ledger(_submission()), encoding="utf-8")
    _git(root, "add", str(LEDGER_REL))
    assert rs.check_staged(root) == []
    assert rs.main(["--root", str(root)]) == 0
    _git(root, "commit", "-q", "-m", "log the submission")
    assert any("datasets-local/verification" in p for p in rs.check_staged(root))
    assert rs.main(["--root", str(root)]) == 1
    _fit_file(root, _record())
    assert rs.check_staged(root) == []


def test_the_owner_logs_commits_runs_and_reruns_in_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Round 84 (A1, A2, A6), end to end: the logging commit passes, the runner then fits the
    committed submission, and every later commit passes with its outputs, across a rerun with
    another method; each run keeps its record, provenance and report."""
    v = _v()
    rs = _r84()
    root = _repo(tmp_path, logged=False, staged="clean\n")
    syn, _, _ = _authors_benzene(root)
    _write_prereg(root, syn.prereg)
    _git(root, "commit", "-q", "-m", "the ledger before the submission")
    (root / LEDGER_REL).write_text(_ledger(_submission(protocol=syn.protocol)), encoding="utf-8")
    _git(root, "add", str(LEDGER_REL))
    assert rs.check_staged(root) == []
    _git(root, "commit", "-q", "-m", "log the submission")

    monkeypatch.setattr(v.pr, "ROOT", root)
    monkeypatch.setattr(v.pr, "load", lambda: syn.prereg)
    submission = {**syn.submission(), "at": syn.submission()["at"].isoformat()}
    (root / "submission.json").write_text(json.dumps(submission), encoding="utf-8")
    (root / "receipt.json").write_text(json.dumps(syn.receipt()), encoding="utf-8")
    for n, documented in enumerate((FOUR, ["geometry"]), start=1):
        (root / "method.json").write_text(json.dumps(_method(syn, documented)), encoding="utf-8")
        args = ["--dataset", BENZENE, "--submission", str(root / "submission.json")]
        args += ["--receipt", str(root / "receipt.json"), "--method", str(root / "method.json")]
        assert v.main([*args, "--out", "datasets-local/verification/benzene-report.md"]) == 0, n
        assert rs.check_staged(root) == [], n
    capsys.readouterr()

    folder = root / rs.FIT_DIR
    first = json.loads((folder / "retained" / f"{BENZENE}{'.1'}{rs.FIT_SUFFIX}").read_text(encoding="utf-8"))
    second = json.loads((folder / f"{BENZENE}{rs.FIT_SUFFIX}").read_text(encoding="utf-8"))
    assert (first["run"], second["run"]) == (1, 2)
    assert first["previous_sha256"] is None
    assert second["previous_sha256"] == _sha_of(folder / "retained" / f"{BENZENE}.1{rs.FIT_SUFFIX}")
    assert [r["provenance"]["method"]["mode"] for r in (first, second)] == ["reproduction", "fallback"]
    for r in (first, second):
        report = folder / "reports" / f"{BENZENE}.{r['run']}.md"
        assert _sha_of(report) == r["report_sha256"]
        assert r["provenance"]["method"]["mode"] in report.read_text(encoding="utf-8")
        fits = r["provenance"]["fits"]
        assert set(fits["independent"]) == set(fits["reproduction"]) == set(_condition_keys(BENZENE))
        assert all(f["science_hash"] for t in fits.values() for f in t.values())
    (folder / "retained" / f"{BENZENE}.1{rs.FIT_SUFFIX}").unlink()
    assert rs.check_staged(root)  # a deleted retained output is found


def test_the_staged_log_must_extend_the_committed_one(tmp_path: Path) -> None:
    """A1: once a submission is committed, removing it from the log is refused, whatever the
    local outputs are."""
    rs = _r84()
    root = _repo(tmp_path, logged=True, staged="clean\n")
    _fit_file(root, _record())
    _git(root, "commit", "-q", "-m", "a logged fit")
    assert rs.check_staged(root) == []
    (root / LEDGER_REL).write_text(_ledger(), encoding="utf-8")
    _git(root, "add", str(LEDGER_REL))
    problems = rs.check_staged(root)
    assert problems and any("first-fit log" in p for p in problems)


def test_an_edited_committed_log_row_is_refused(tmp_path: Path) -> None:
    """A1 (added for a surviving mutant): an edited row, with every submission and output intact,
    is refused by the extension check alone."""
    rs = _r84()
    root = _repo(tmp_path, logged=True, staged="clean\n")
    _fit_file(root, _record())
    _git(root, "commit", "-q", "-m", "a logged fit")
    edited = _ledger(_submission()).replace(FREEZE_ROW, FREEZE_ROW.replace("09:00Z", "09:30Z"))
    (root / LEDGER_REL).write_text(edited, encoding="utf-8")
    _git(root, "add", str(LEDGER_REL))
    assert any("drops or changes a committed row" in p for p in rs.check_staged(root))


def test_a_record_at_another_revision_than_its_submission_is_refused(tmp_path: Path) -> None:
    """A2 (added for a surviving mutant): the logged submission is bound, but the record's own
    revision differs."""
    rs = _r84()
    root = _root(tmp_path, logged=True)
    _fit_file(root, {**_record(), "protocol_sha256": "0" * 64})
    assert rs.fit_tier(root).problems


def test_the_decision_11_entry_point_runs_the_full_check() -> None:
    """The operator's command (pytest -k no_restricted_value_is_in_a_tracked_blob) runs the whole
    staged check, fit tier included."""
    _rs()
    source = inspect.getsource(test_v0_preregistration.test_no_restricted_value_is_in_a_tracked_blob)
    assert "rs.check_staged(ROOT)" in source


# ============================================================================ receipts
#: Round 85: a results receipt records how many fit outputs each dataset had (the rollback anchor).
RESULTS_STATUS = r"results \(files: benzene-taggar2006 \d+, odcb-chandrakumar1993 \d+\)"
RECEIPT = re.compile(
    r"\| (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}Z) \| `[0-9a-f]{40}` \(commit `[0-9a-f]{7}`\) "
    r"\| (passed, not skipped(?:; fit tier: (?:pre-result|" + RESULTS_STATUS + r"))?) \| Claude \|"
)


def _scan_rows(text: str) -> list[tuple[str, str]]:
    """The §6 scan receipts. Round 83 (B1): every row of the receipt table must be well formed."""
    section = text.split("## 6. Later entries", 1)[1].split("\n## ", 1)[0]
    table = section.split("| UTC | Staged tree | Scan | Operator |", 1)[1].split("\n\n", 1)[0]
    rows = []
    for line in table.strip().splitlines()[1:]:
        match = RECEIPT.fullmatch(line.strip())
        assert match, line
        rows.append((match.group(1), match.group(2)))
    return rows


def test_scan_receipts_record_the_fit_tier_status() -> None:
    rs = _rs()
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}Z", rs.FIT_TIER_SINCE)
    assert rs.FIT_TIER_SINCE >= "2026-11-23T00:00Z"
    rows = _scan_rows(LEDGER.read_text(encoding="utf-8"))
    assert len(rows) >= 9
    # Round 83 (B1): the first receipt made under the tier exists and records its status, so a
    # cutoff moved into the future fails here.
    assert ("2026-11-23T14:32Z", "passed, not skipped; fit tier: pre-result") in rows
    assert rs.FIT_TIER_SINCE <= "2026-11-23T14:32Z"
    for at, scan in rows:
        if at >= rs.FIT_TIER_SINCE:
            assert re.fullmatch(r"passed, not skipped; fit tier: (pre-result|" + RESULTS_STATUS + ")", scan), (at, scan)
        else:
            assert scan == "passed, not skipped", (at, scan)


def test_a_malformed_receipt_row_is_refused() -> None:
    text = LEDGER.read_text(encoding="utf-8")
    row = (
        "| 2026-11-22T22:16Z | `21e153040a21075f1627543d70a9178cc2dbc0d9` (commit `0795f47`) "
        "| passed, not skipped | Claude |"
    )
    assert row in text
    for bad in (row.replace("passed, not skipped", "passed"), row.replace("Claude", "someone"), row[:-2]):
        with pytest.raises(AssertionError):
            _scan_rows(text.replace(row, bad))


# ============================================================ the workflow's local source
def _sentinel_report(tmp_path: Path, v: Any) -> tuple[dict[str, Any], Synthetic]:
    truths = {k: {"S_zz": -0.0731987654321 - 1.234567e-4 * i} for i, k in enumerate(_condition_keys(BENZENE))}
    targets = {(k, "S_zz"): (t["S_zz"] + 0.00198765, 0.000431) for k, t in truths.items()}
    syn = Synthetic(tmp_path, BENZENE, truths=truths, targets=targets)
    report: dict[str, Any] = v.run_report(
        BENZENE,
        call=v.local_call(),
        prereg=syn.prereg,
        root=tmp_path,
        submission=syn.logged(),
        receipt=syn.receipt(),
    )
    assert report["status"] == "complete"
    return report, syn


def test_the_workflow_writes_every_fit_value_at_full_precision(tmp_path: Path) -> None:
    """Amended for round 84 (A2, A6): the record declares every roster cell on both tracks, and
    the written record adds its run, its predecessor's hash and its report's hash."""
    v = _v()
    rs = _r84()
    report, syn = _sentinel_report(tmp_path, v)
    record = v.fit_values(report)
    assert (record["dataset"], record["protocol_sha256"]) == (BENZENE, report["protocol_sha256"])
    assert record["submission"] == report["submission"] == _submission(protocol=syn.protocol)
    estimates = {
        (c, e, "estimate"): x
        for c, f in report["conditions"].items()
        for e, x in f["estimates"].items()
        if x is not None
    }
    discrepancies = {
        (c["condition"], c["component"], "discrepancy"): c["discrepancy"]
        for c in report["cells"]["independent"]
        if c["discrepancy"] is not None
    }
    assert len(estimates) == 15 and len(discrepancies) == 15
    got = {(e["condition"], e["component"], e["quantity"]): e["value"] for e in record["values"]}
    assert {k: x for k, x in got.items() if x is not None} == {**estimates, **discrepancies}  # exact floats
    roster = {(c, "S_zz") for c in _condition_keys(BENZENE)}
    for q in QUANTITIES:
        assert sorted((e["condition"], e["component"]) for e in record["values"] if e["quantity"] == q) == sorted(
            roster
        ), q
    pending = [e for e in record["values"] if e["quantity"].startswith("reproduction")]
    assert {(e["value"], e["reason"]) for e in pending} == {(None, "inputs-undocumented")}
    assert record["provenance"]["fits"]["independent"] == {c: f["provenance"] for c, f in report["conditions"].items()}
    assert record["provenance"]["versions"] == report["provenance"]["versions"]
    assert record["provenance"]["method"] == report["reproduction"]

    path = v.write_fit_values(report, root=tmp_path)
    assert path == tmp_path / rs.FIT_DIR / f"{BENZENE}{rs.FIT_SUFFIX}"
    written = json.loads(path.read_text(encoding="utf-8"))
    assert written == {
        **record,
        "run": 1,
        "previous_sha256": None,
        "report_sha256": _sha_of(tmp_path / rs.FIT_DIR / "reports" / f"{BENZENE}.1.md"),
    }

    _root(tmp_path, logged=True, protocol=syn.protocol)
    _write_prereg(tmp_path, syn.prereg)
    fit = rs.fit_tier(tmp_path)
    assert (fit.status, fit.problems, fit.files, fit.values) == ("results", [], 1, 30)
    some = next(iter(estimates.values()))
    rounded = f"{Decimal(repr(some)).quantize(Decimal('0.000001')):f}"  # six decimals: five significant digits
    assert rs.scan([("notes.md", f"S = {rounded}\n".encode())], fit.tiers, frozenset()) == ["notes.md:1"]

    # A2 (round 83): a rerun retains the earlier output beside the new one; A6: bound by hash.
    again = v.write_fit_values(report, root=tmp_path)
    assert again == path
    retained = sorted((tmp_path / rs.FIT_DIR / "retained").glob(f"*{rs.FIT_SUFFIX}"))
    assert [p.name for p in retained] == [f"{BENZENE}.1{rs.FIT_SUFFIX}"]
    assert json.loads(retained[0].read_text(encoding="utf-8")) == written
    assert json.loads(path.read_text(encoding="utf-8"))["previous_sha256"] == _sha_of(retained[0])
    second = rs.fit_tier(tmp_path)
    assert (second.problems, second.files) == ([], 2)


def test_a_rank_pending_cell_is_declared_and_passes_the_scan(tmp_path: Path) -> None:
    """Round 84 (A4): a fit whose rank is not verified estimates no named component; the record
    declares its cells rank-unverified, on either track, and the scan accepts it."""
    v = _v()
    rs = _r84()
    syn, _, _ = _authors_benzene(tmp_path)
    for independent in (False, True):
        call = v.local_call()
        report = v.run_report(
            BENZENE,
            call=_unverified_call(call) if independent else _AuthorsUnverified(call),
            prereg=syn.prereg,
            root=tmp_path,
            submission=syn.logged(),
            receipt=syn.receipt(),
            method=_method(syn),
        )
        track = "independent" if independent else "reproduction"
        assert {(c["status"], c["reason"]) for c in report["cells"][track]} == {("pending", "rank-unverified")}
        record = v.fit_values(report)
        prefix = "" if independent else "reproduction "
        mine = [e for e in record["values"] if e["quantity"] in (prefix + "estimate", prefix + "discrepancy")]
        assert len(mine) == 30 and {(e["value"], e["reason"]) for e in mine} == {(None, "rank-unverified")}
        v.write_fit_values(report, root=tmp_path)
    _root(tmp_path, logged=True, protocol=syn.protocol)
    _write_prereg(tmp_path, syn.prereg)
    fit = rs.fit_tier(tmp_path)
    assert (fit.problems, fit.files) == ([], 2)


class _AuthorsUnverified:
    """A registry client whose second fit of each condition (the authors' analysis, which
    ``run_report`` runs after every independent fit) has an unverified rank."""

    def __init__(self, call: Any) -> None:
        self.call, self.wrapped, self.fits = call, _unverified_call(call), 0

    def __call__(self, name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
        if name == "fit.run":
            self.fits += 1
        out: dict[str, Any] = (self.wrapped if self.fits > 15 else self.call)(name, args)
        return out


@pytest.mark.parametrize("status", ["local evidence unavailable", "blocked"])
def test_no_fit_values_without_a_complete_report(tmp_path: Path, status: str) -> None:
    v = _v()
    with pytest.raises(ValueError):
        v.write_fit_values({"dataset": BENZENE, "protocol_sha256": "ab" * 32, "status": status}, root=tmp_path)
    assert not (tmp_path / "datasets-local").exists()


def test_the_command_writes_the_fit_values_and_shares_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    v = _v()
    rs = _r83()
    truths = {k: {"S_zz": -0.0731987654321 - 1.234567e-4 * i} for i, k in enumerate(_condition_keys(BENZENE))}
    syn = Synthetic(tmp_path, BENZENE, truths=truths)
    # Round 83 (A1): the command fits only a submission logged in the committed ledger.
    _root(tmp_path, logged=True, protocol=syn.protocol)
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", str(LEDGER_REL))
    _git(tmp_path, "commit", "-q", "-m", "ledger")
    monkeypatch.setattr(v.pr, "ROOT", tmp_path)
    monkeypatch.setattr(v.pr, "load", lambda: syn.prereg)
    monkeypatch.setattr(v, "_now", lambda: datetime(2026, 11, 25, 12, 0, tzinfo=UTC))
    submission = {**syn.submission(), "at": datetime(2026, 11, 25, 10, 0, tzinfo=UTC).isoformat()}
    (tmp_path / "submission.json").write_text(json.dumps(submission), encoding="utf-8")
    (tmp_path / "receipt.json").write_text(json.dumps(syn.receipt()), encoding="utf-8")
    code = v.main(
        [
            "--dataset",
            BENZENE,
            "--submission",
            str(tmp_path / "submission.json"),
            "--receipt",
            str(tmp_path / "receipt.json"),
            "--out",
            "datasets-local/verification/benzene-report.md",
        ]
    )
    shared = capsys.readouterr().out
    assert code == 0
    path = tmp_path / rs.FIT_DIR / f"{BENZENE}{rs.FIT_SUFFIX}"
    values = [e["value"] for e in json.loads(path.read_text(encoding="utf-8"))["values"] if e["value"] is not None]
    assert len(values) == 30
    assert _leaks(shared, values) == []


# ===================== round 83 (A4): the authors'-analysis values are scanned too, frozen before
# the fix. A report that runs the reproduction track writes its estimates and discrepancies as
# "reproduction estimate" and "reproduction discrepancy" entries. They cover the roster exactly
# when present, and a reproduction discrepancy needs its reproduction estimate.
R83B_PY = ROOT / "tools" / "validation" / "evidence.py"


def _r83b() -> Any:
    rs = _r83()
    if not R83B_PY.is_file():
        pytest.xfail("round 83 (A4, A5): the fixes are not written yet")
    return rs


def _reproduced(drop: int | None = None, orphan: bool = False) -> dict[str, Any]:
    """Amended for round 84 (A2): the authors'-analysis track run in the fallback mode, every
    roster cell declared with its discrepancy (amended in round 85: every target present)."""
    record = _record()
    record["values"] = [e for e in record["values"] if not e["quantity"].startswith("reproduction")]
    estimates = [e for e in record["values"] if e["quantity"] == "estimate"]
    extra = [{**e, "quantity": "reproduction estimate", "value": e["value"] + 0.0101} for e in estimates]
    extra += [
        _declared(e["condition"], e["component"], "reproduction discrepancy", 0.00277341 + 0.000191 * k)
        for k, e in enumerate(estimates)
    ]
    if drop is not None:
        del extra[drop]
    if orphan:
        extra.append(_declared("c97", "S_zz", "reproduction discrepancy", 0.3))
    record["values"] += extra
    conditions = _condition_keys(BENZENE)
    record["provenance"]["method"] = {
        "mode": "fallback",
        "documented": ["geometry"],
        "geometry": {"r_cc_angstrom": 1.397, "r_ch_angstrom": 1.089},
        "weights": "1/sigma^2",
        "sources": {"geometry": "synthetic"},
    }
    record["provenance"]["fits"]["reproduction"] = {c: _fit_provenance(100 + i) for i, c in enumerate(conditions)}
    return record


def test_reproduction_values_are_part_of_the_fit_tier(tmp_path: Path) -> None:
    rs = _r84()
    root = _root(tmp_path, logged=True)
    _fit_file(root, _reproduced())
    fit = rs.fit_tier(root)
    assert (fit.status, fit.problems, fit.values) == ("results", [], 2 * _count(BENZENE))
    assert rs.scan([("notes.md", b"d = 0.002773\n")], fit.tiers, frozenset()) == ["notes.md:1"]


@pytest.mark.parametrize("name", ["a missing reproduction cell", "a reproduction discrepancy without its estimate"])
def test_reproduction_values_must_cover_the_roster(tmp_path: Path, name: str) -> None:
    rs = _r84()
    root = _root(tmp_path, logged=True)
    path = _fit_file(root, _reproduced(drop=3) if name.startswith("a missing") else _reproduced(orphan=True))
    fit = rs.fit_tier(root)
    assert fit.problems and any(path.name in p for p in fit.problems), name
    assert _digits_free([*fit.problems, rs.status_line(fit)])


def test_a_removed_reproduction_discrepancy_is_a_problem_not_a_gap(tmp_path: Path) -> None:
    """Round 84 (A2): Sol's probe. Without its declaration the record fails; with it, the value is
    in the tier and found in a blob."""
    rs = _r84()
    root = _root(tmp_path, logged=True)
    record = _reproduced()
    _fit_file(root, record)
    whole = rs.fit_tier(root)
    assert whole.problems == []
    assert rs.scan([("notes.md", b"0.002773\n")], whole.tiers, frozenset()) == ["notes.md:1"]
    record["values"] = [e for e in record["values"] if e["value"] != 0.00277341]
    _fit_file(root, record)
    assert rs.fit_tier(root).problems


# ====================== round 85: two holes found by the first, interrupted round 85 attempt, frozen
# before the fix. (1) A false pending declaration: a discrepancy value declared ``no-target`` leaves
# the tier. A cell's discrepancy is pending only for its estimate's own reason, or for no target;
# no target means either every target withheld (the spot-check unsigned, P-2) or exactly the
# cells whose target the hash-verified targets file marks pending. (2) A rollback: an earlier,
# self-consistent chain restored. Each results receipt in §6 records every dataset's number of fit
# outputs, and a later scan with fewer is a problem.
def _r85() -> Any:
    rs = _r84()
    import fit_record

    if not hasattr(fit_record, "pending_targets"):
        pytest.xfail("round 85: the fixes are not written yet")
    return rs


def _discrepancies(record: dict[str, Any], quantity: str = "discrepancy") -> list[dict[str, Any]]:
    return [e for e in record["values"] if e["quantity"] == quantity]


def _hidden() -> dict[str, Any]:
    record = _record()
    _discrepancies(record)[2].update(value=None, reason="no-target")
    return record


def _withheld(record: dict[str, Any], *quantities: str) -> dict[str, Any]:
    for q in quantities:
        for e in _discrepancies(record, q):
            e.update(value=None, reason="no-target")
    return record


def _rank_pending(record: dict[str, Any], condition: str, components: list[str], reason: str) -> dict[str, Any]:
    for e in record["values"]:
        if e["condition"] == condition and e["component"] in components and e["quantity"] == "estimate":
            e.update(value=None, reason="rank-unverified")
        if e["condition"] == condition and e["component"] in components and e["quantity"] == "discrepancy":
            e.update(value=None, reason=reason)
    return record


O0 = _condition_keys(ODCB)[0]
FALSE_PENDING: dict[str, Any] = {
    "a discrepancy value declared no-target": (BENZENE, _hidden),
    "a discrepancy pending for rank beside an estimate value": (
        BENZENE,
        lambda: _changed(lambda r: _discrepancies(r)[1].update(value=None, reason="rank-unverified")),
    ),
    "a rank-pending estimate with a discrepancy pending for no target": (
        BENZENE,
        lambda: _rank_pending(_record(), C0, ["S_zz"], "no-target"),
    ),
    "a condition rank-pending for one component only": (
        ODCB,
        lambda: _rank_pending(_record(ODCB), O0, ["S_zz"], "rank-unverified"),
    ),
    "one track withheld, the other not": (BENZENE, lambda: _withheld(_reproduced(), "reproduction discrepancy")),
}


@pytest.mark.parametrize("name", list(FALSE_PENDING))
def test_a_false_pending_declaration_is_a_problem(tmp_path: Path, name: str) -> None:
    rs = _r85()
    dataset, make = FALSE_PENDING[name]
    root = _root(tmp_path, logged=False)
    (root / LEDGER_REL).write_text(_ledger(_submission(dataset)), encoding="utf-8")
    path = _fit_file(root, make(), name=f"{dataset}.fit-values.json")
    fit = rs.fit_tier(root)
    assert any(path.name in p for p in fit.problems), (name, fit.problems)
    assert _digits_free([*fit.problems, rs.status_line(fit)]), fit.problems


def test_withheld_targets_and_rank_pending_conditions_are_accepted(tmp_path: Path) -> None:
    """The consistent pending declarations pass: every target withheld on both tracks, and a whole
    condition rank-pending with its discrepancies pending for the same reason."""
    rs = _r85()
    root = _root(tmp_path, logged=True)
    _fit_file(root, _withheld(_reproduced(), "discrepancy", "reproduction discrepancy"))
    assert rs.fit_tier(root).problems == []
    _fit_file(root, _rank_pending(_record(), C0, ["S_zz"], "rank-unverified"))
    assert rs.fit_tier(root).problems == []


def _odcb_root(tmp_path: Path, pending: list[tuple[str, str]]) -> tuple[Path, Synthetic]:
    """A checkout whose o-DCB targets file marks the given cells pending, with its submission logged."""
    root = _root(tmp_path, logged=False)
    truths = {k: _truth(ODCB, i) for i, k in enumerate(_condition_keys(ODCB))}
    targets: dict[tuple[str, str], tuple[float, float] | None] = dict(_default_targets(ODCB, truths))
    for cell in pending:
        targets[cell] = None
    syn = Synthetic(root, ODCB, truths=truths, targets=targets)
    prereg = json.loads((root / PREREG_REL).read_text(encoding="utf-8"))
    prereg["datasets"][ODCB] = syn.prereg["datasets"][ODCB]
    _write_prereg(root, prereg)
    (root / LEDGER_REL).write_text(_ledger(_submission(ODCB, syn.protocol)), encoding="utf-8")
    return root, syn


def test_no_target_is_exactly_the_targets_files_pending_cells(tmp_path: Path) -> None:
    """A signed run declares no-target for exactly the cells the targets file marks pending."""
    rs = _r85()
    anisotropy = _estimands(ODCB)[1]
    o1 = _condition_keys(ODCB)[1]
    pending = [(O0, "S_zz"), (o1, anisotropy)]
    root, syn = _odcb_root(tmp_path, pending)
    record = _record(ODCB, protocol=syn.protocol)
    for e in _discrepancies(record):
        if (e["condition"], e["component"]) in pending:
            e.update(value=None, reason="no-target")
    path = _fit_file(root, record, name=f"{ODCB}.fit-values.json")
    assert rs.fit_tier(root).problems == []
    for change in ("a pending target with a discrepancy", "another cell without a target"):
        bad = json.loads(json.dumps(record))
        for e in _discrepancies(bad):
            cell = (e["condition"], e["component"])
            if change.startswith("a pending") and cell == pending[0]:
                e.update(value=0.0011, reason=None)
            if change.startswith("another") and cell == (o1, "S_zz"):
                e.update(value=None, reason="no-target")
        _fit_file(root, bad, name=f"{ODCB}.fit-values.json")
        fit = rs.fit_tier(root)
        assert any(path.name in p for p in fit.problems), change
        assert _digits_free(fit.problems)
    (
        root / json.loads((root / PREREG_REL).read_text(encoding="utf-8"))["datasets"][ODCB]["targets"]["path"]
    ).write_text("edited\n", encoding="utf-8")
    _fit_file(root, record, name=f"{ODCB}.fit-values.json")
    assert any("target" in p for p in rs.fit_tier(root).problems)  # the pending cells cannot be read


def test_the_workflow_declares_pending_targets_the_scan_accepts(tmp_path: Path) -> None:
    """End to end, on o-DCB with a pending S_zz target (its anisotropy then waits for it) and a
    pending anisotropy target: signed and unsigned runs both pass the scan."""
    v = _v()
    rs = _r85()
    anisotropy = _estimands(ODCB)[1]
    o1 = _condition_keys(ODCB)[1]
    root, syn = _odcb_root(tmp_path, [(O0, "S_zz"), (o1, anisotropy)])
    ledger = (root / LEDGER_REL).read_text(encoding="utf-8")
    for receipt in (syn.receipt(), None):
        report = v.run_report(
            ODCB, call=v.local_call(), prereg=syn.prereg, root=root, submission=syn.logged(), receipt=receipt
        )
        reasons = {(c["condition"], c["component"]): c["reason"] for c in report["cells"]["independent"]}
        if receipt is not None:
            assert reasons[(O0, "S_zz")] == "no-target" and reasons[(O0, anisotropy)] == "s_zz-target-pending"
        v.write_fit_values(report, root=root)
    (root / LEDGER_REL).write_text(ledger, encoding="utf-8")
    fit = rs.fit_tier(root)
    assert (fit.problems, fit.files) == ([], 2)


def _with_receipt(text: str, benzene: int, odcb: int) -> str:
    """The ledger with a results scan receipt appended to §6, recording the outputs' numbers."""
    row = (
        f"| 2026-11-25T11:00Z | `{'a' * 40}` (commit `aaaaaaa`) | passed, not skipped; fit tier: results "
        f"(files: {BENZENE} {benzene}, {ODCB} {odcb}) | Claude |"
    )
    marker = "\n\nEach receipt is first recorded"
    assert text.count(marker) == 1
    return text.replace(marker, "\n" + row + marker)


def test_the_receipt_records_each_datasets_outputs(tmp_path: Path) -> None:
    rs = _r85()
    root = _root(tmp_path, logged=True)
    assert rs.receipt_status(rs.fit_tier(_root(tmp_path / "none", logged=False))) == "fit tier: pre-result"
    _chain(root, 3)
    status = rs.receipt_status(rs.fit_tier(root))
    assert status == f"fit tier: results (files: {BENZENE} 3, {ODCB} 0)"
    assert re.fullmatch(RESULTS_STATUS, status.removeprefix("fit tier: "))
    text = _with_receipt(_ledger(_submission()), 3, 0)
    assert _scan_rows(text)[-1][1] == f"passed, not skipped; {status}"


ROLLBACKS = ["an earlier run restored", "an earlier run restored beside a new o-DCB run", "the outputs removed"]


@pytest.mark.parametrize("name", ROLLBACKS)
def test_a_rollback_below_the_last_receipt_is_a_problem(tmp_path: Path, name: str) -> None:
    """A chain that checks out on its own, but holds fewer outputs than the last receipt
    recorded, is a problem; the same chain before any such receipt is not."""
    rs = _r85()
    root = _root(tmp_path, logged=True)
    first, second, current = _chain(root, 3)
    (root / LEDGER_REL).write_text(_with_receipt(_ledger(_submission(), _submission(ODCB)), 3, 0), encoding="utf-8")
    fit = rs.fit_tier(root)
    assert not any("receipt" in p for p in fit.problems), fit.problems
    reports = root / "datasets-local" / "verification" / "reports"
    record = first.read_text(encoding="utf-8")
    for path in (second, current, first, reports / f"{BENZENE}.2.md", reports / f"{BENZENE}.3.md"):
        path.unlink()
    if name != "the outputs removed":
        current.write_text(record, encoding="utf-8")  # run 1 again: a whole, consistent chain
    if name.endswith("new o-DCB run"):
        _chain(root, 1, ODCB)
    fit = rs.fit_tier(root)
    assert not any("chain" in p or "previous" in p for p in fit.problems) or name == "the outputs removed"
    assert any("receipt" in p for p in fit.problems), (name, fit.problems)
    assert _digits_free(fit.problems)
