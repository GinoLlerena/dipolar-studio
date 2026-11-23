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

**Pending implementation.** While ``restricted_scan`` has no ``fit_tier`` (or ``verification``
no ``write_fit_values``), these tests xfail through ``_rs()`` and ``_v()`` alone; once those
names exist, any exception fails. The round 83 amendments xfail through ``_r83()`` while
``tools/validation/first_fit_log.py`` is absent.
"""

from __future__ import annotations

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
from test_v15_verification import BENZENE, ODCB, Synthetic, _condition_keys, _leaks  # noqa: E402

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
    ledger = _ledger(_submission(protocol=protocol)) if logged else _ledger()
    (tmp_path / LEDGER_REL).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / LEDGER_REL).write_text(ledger, encoding="utf-8")
    (tmp_path / PREREG_REL).write_bytes((ROOT / PREREG_REL).read_bytes())
    return tmp_path


VALUES = [-0.48736829, 0.0612349871, 0.00123456]


def _conditions(dataset: str) -> int:
    return int(json.loads((ROOT / PREREG_REL).read_text(encoding="utf-8"))["datasets"][dataset]["conditions"])


def _estimands(dataset: str) -> list[str]:
    return list(json.loads((ROOT / PREREG_REL).read_text(encoding="utf-8"))["datasets"][dataset]["estimands"])


def _record(dataset: str = BENZENE, values: list[float] = VALUES, protocol: str = PROTOCOL) -> dict[str, Any]:
    """A complete record bound to the logged submission: one estimate for every roster cell (the
    given values first, then fillers) and one discrepancy, the last given value."""
    *estimates, discrepancy = values
    cells = [(f"c{i:02d}", e) for i in range(_conditions(dataset)) for e in _estimands(dataset)]
    fill = [0.2 + 0.0731 * k for k in range(len(cells))]
    entries = [
        {"condition": c, "component": e, "quantity": "estimate", "value": (estimates + fill[len(estimates) :])[k]}
        for k, (c, e) in enumerate(cells)
    ]
    entries.append({**entries[0], "quantity": "discrepancy", "value": discrepancy})
    return {
        "dataset": dataset,
        "protocol_sha256": protocol,
        "submission": _submission(dataset, protocol),
        "values": entries,
    }


def _count(dataset: str) -> int:
    return _conditions(dataset) * len(_estimands(dataset)) + 1


def _fit_file(root: Path, record: Any, name: str = f"{BENZENE}.fit-values.json", raw: str | None = None) -> Path:
    path = root / "datasets-local" / "verification" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(raw if raw is not None else json.dumps(record), encoding="utf-8")
    return path


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
    rs = _r83()
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
    rs = _r83()
    ledger = _ledger(_submission(BENZENE), _submission(ODCB))
    (tmp_path / LEDGER_REL).parent.mkdir(parents=True)
    (tmp_path / LEDGER_REL).write_text(ledger, encoding="utf-8")
    (tmp_path / PREREG_REL).write_bytes((ROOT / PREREG_REL).read_bytes())
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
    rs = _r83()
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


MALFORMED: dict[str, Any] = {
    "not JSON": "{0.4873683",
    "a list": [0.48736829],
    "no values": {k: v for k, v in _record().items() if k != "values"},
    "no entries": _with(values=[]),
    "an entry without its value": _with(values=[{"condition": "c00", "component": "S_zz", "quantity": "estimate"}]),
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
    "an extra condition": _extra_entry({"condition": "c99", "component": "S_zz", "quantity": "estimate", "value": 0.3}),
    "an unknown component": _extra_entry(
        {"condition": "c00", "component": "S_xy", "quantity": "estimate", "value": 0.3}
    ),
    "a discrepancy without its estimate": _extra_entry(
        {"condition": "c98", "component": "S_zz", "quantity": "discrepancy", "value": 0.3}
    ),
}


@pytest.mark.parametrize("name", list(MALFORMED))
def test_a_malformed_fit_output_is_a_value_free_problem(tmp_path: Path, name: str) -> None:
    rs = _r83()
    root = _root(tmp_path, logged=True)
    bad = MALFORMED[name]
    path = _fit_file(root, bad, raw=bad if isinstance(bad, str) else None)
    fit = rs.fit_tier(root)
    assert fit.problems, name
    assert any(path.name in p for p in fit.problems), fit.problems
    assert _digits_free([*fit.problems, rs.status_line(fit)]), fit.problems


def test_the_well_formed_entries_of_a_damaged_file_are_still_scanned(tmp_path: Path) -> None:
    rs = _r83()
    root = _root(tmp_path, logged=True)
    _fit_file(root, _extra_entry({"condition": "c00", "component": "S_zz", "quantity": "estimate", "value": "x"}))
    fit = rs.fit_tier(root)
    assert fit.problems and fit.values == _count(BENZENE)
    assert rs.scan([("notes.md", b"0.4874\n")], fit.tiers, frozenset()) == ["notes.md:1"]


def test_an_unexpected_file_name_is_not_printed(tmp_path: Path) -> None:
    """A3: a file name can carry a value; the diagnostic does not repeat it."""
    rs = _r83()
    root = _root(tmp_path, logged=True)
    _fit_file(root, _record())
    _fit_file(root, _record(), name="benzene 0.48736829.fit-values.json")
    fit = rs.fit_tier(root)
    assert fit.problems and _digits_free(fit.problems)


def test_a_rerun_keeps_the_earlier_output(tmp_path: Path) -> None:
    """A2: a retained output still binds its submission and is still scanned."""
    rs = _r83()
    root = _root(tmp_path, logged=True)
    _fit_file(root, _record(), name=f"retained/{BENZENE}.1.fit-values.json")
    fit = rs.fit_tier(root)
    assert (fit.problems, fit.files, fit.values) == ([], 1, _count(BENZENE))
    _fit_file(root, _record(BENZENE, [0.3333777, 0.25, 0.0011]))
    both = rs.fit_tier(root)
    assert (both.problems, both.files) == ([], 2)
    assert rs.scan([("notes.md", b"0.4874\n")], both.tiers, frozenset()) == ["notes.md:1"]  # the earlier run


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
    rs = _r83()
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
    rs = _r83()
    root = _repo(tmp_path, logged=True, staged="clean\n")  # logged, but no local fit output
    problems = rs.check_staged(root)
    assert problems and any("datasets-local/verification" in p for p in problems)


def test_the_staged_check_reads_the_staged_ledger(tmp_path: Path) -> None:
    """A1: the receipt binds the ledger that is staged, not the working copy's."""
    rs = _r83()
    root = _repo(tmp_path, logged=True, staged="clean\n")  # the staged ledger logs a fit
    (root / LEDGER_REL).write_text(_ledger(), encoding="utf-8")  # the working copy does not
    problems = rs.check_staged(root)
    assert any("datasets-local/verification" in p for p in problems)


def test_the_staged_log_must_extend_the_committed_one(tmp_path: Path) -> None:
    """A1: once a submission is committed, removing it from the log is refused, whatever the
    local outputs are."""
    rs = _r83()
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
    rs = _r83()
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
    rs = _r83()
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
RECEIPT = re.compile(
    r"\| (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}Z) \| `[0-9a-f]{40}` \(commit `[0-9a-f]{7}`\) "
    r"\| (passed, not skipped(?:; fit tier: (?:pre-result|results))?) \| Claude \|"
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
            assert re.fullmatch(r"passed, not skipped; fit tier: (pre-result|results)", scan), (at, scan)
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
        submission=syn.submission(),
        receipt=syn.receipt(),
    )
    assert report["status"] == "complete"
    return report, syn


def test_the_workflow_writes_every_fit_value_at_full_precision(tmp_path: Path) -> None:
    v = _v()
    rs = _r83()
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
    assert got == {**estimates, **discrepancies}  # exact floats: full precision

    path = v.write_fit_values(report, root=tmp_path)
    assert path == tmp_path / rs.FIT_DIR / f"{BENZENE}{rs.FIT_SUFFIX}"
    assert json.loads(path.read_text(encoding="utf-8")) == record

    _root(tmp_path, logged=True, protocol=syn.protocol)
    fit = rs.fit_tier(tmp_path)
    assert (fit.status, fit.problems, fit.files, fit.values) == ("results", [], 1, 30)
    some = next(iter(estimates.values()))
    rounded = f"{Decimal(repr(some)).quantize(Decimal('0.000001')):f}"  # six decimals: five significant digits
    assert rs.scan([("notes.md", f"S = {rounded}\n".encode())], fit.tiers, frozenset()) == ["notes.md:1"]

    # A2: a rerun retains the earlier output beside the new one.
    again = v.write_fit_values(report, root=tmp_path)
    assert again == path
    retained = sorted((tmp_path / rs.FIT_DIR / "retained").glob(f"*{rs.FIT_SUFFIX}"))
    assert [p.name for p in retained] == [f"{BENZENE}.1{rs.FIT_SUFFIX}"]
    assert rs.fit_tier(tmp_path).files == 2


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
    values = [e["value"] for e in json.loads(path.read_text(encoding="utf-8"))["values"]]
    assert len(values) == 30
    assert _leaks(shared, values) == []
