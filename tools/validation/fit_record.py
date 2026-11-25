"""The fit-values record: its format, and its value-free checks (round 84, A2, A4, A6).

The report workflow (``verification.write_fit_values``) writes one record per run, at
``datasets-local/verification/<dataset>.fit-values.json``; a rerun keeps the record it replaces
as ``retained/<dataset>.<n>.fit-values.json`` and each run's local report as
``reports/<dataset>.<run>.md``. The restricted-fit scan tier (``tools/datasets/restricted_scan.py``)
checks every record with ``check`` and every dataset's chain of runs with ``chain``. Standard
library only.

**The declarations (A2, A4).** The record declares every cell of the frozen roster (the conditions
of the hash-verified couplings file, times the estimands) on both tracks: an estimate and a
discrepancy each, as a finite value or as the cell's pending reason. A missing, invented or
repeated cell, a value with a reason or neither, an unknown reason, or a discrepancy without its
estimate is a problem. A rank-pending cell is declared ``rank-unverified``, and a pending
authors'-analysis track ``inputs-undocumented`` throughout.

**Pending reasons that hold (round 85).** A discrepancy is pending only for its estimate's own
reason or, beside an estimate value, for ``no-target``; a rank-pending condition is pending for
every component; and on each track the ``no-target`` cells are either every estimated cell (all
targets withheld: P-2, the spot-check unsigned) or exactly the estimated cells whose target the
hash-verified targets file marks pending (``pending_targets``), the same choice on both tracks.
Round 86: the record declares that choice (``spot_check_signed``, as its report states): signed,
exactly the pending cells; unsigned, every target withheld.

**The provenance (A6).** The package versions, the protocol flags, the method of the authors'
analysis, and each fitted condition's fit provenance per track (its science hash among them).

**The chain (A6).** Each record has its run number, the SHA-256 of the record it replaced (None
for the first run) and the SHA-256 of its run's local report. Deleting, editing or renumbering
any run's record or report breaks the chain.

Every problem is value-free: it names the record's place and what is wrong, never a value, a
condition or a file's content.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

DIR = "datasets-local/verification"
SUFFIX = ".fit-values.json"
RETAINED = "retained"
REPORTS = "reports"
PREREG = "docs/phase2/v0.3-preregistration.json"
DATASETS = ("benzene-taggar2006", "odcb-chandrakumar1993")

#: (estimate, discrepancy) quantities per track.
TRACKS: dict[str, tuple[str, str]] = {
    "independent": ("estimate", "discrepancy"),
    "reproduction": ("reproduction estimate", "reproduction discrepancy"),
}
QUANTITIES = tuple(q for pair in TRACKS.values() for q in pair)
#: The pending reasons of prereg_labels, in precedence order.
REASONS = ("inputs-undocumented", "rank-unverified", "no-target", "no-precision")
#: Why a track can have no estimate for a cell.
ESTIMATE_REASONS = {"independent": ("rank-unverified",), "reproduction": ("inputs-undocumented", "rank-unverified")}
MODES = ("reproduction", "fallback", "pending")

RECORD_FIELDS = frozenset(
    {
        "dataset",
        "protocol_sha256",
        "submission",
        "run",
        "previous_sha256",
        "report_sha256",
        "spot_check_signed",
        "provenance",
        "values",
    }
)
#: The local report's line that states the run's spot-check state (round 86); the record's
#: ``spot_check_signed`` must match it.
SIGNED_LINE = "- Spot-check signed: "
UNEXPECTED = "(a file with an unexpected name)"
ENTRY_FIELDS = frozenset({"condition", "component", "quantity", "value", "reason"})
PROVENANCE_FIELDS = frozenset({"versions", "flags", "method", "fits"})
_SHA = re.compile(r"[0-9a-f]{64}")

Roster = tuple[tuple[str, ...], tuple[str, ...]]  # (conditions, estimands)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _dataset(root: Path, dataset: str, prereg: Mapping[str, Any] | None) -> Any:
    p = json.loads((root / PREREG).read_text(encoding="utf-8")) if prereg is None else prereg
    return p["datasets"][dataset]


def roster(root: Path, dataset: str, prereg: Mapping[str, Any] | None = None) -> Roster:
    """The frozen roster of ``dataset``: the conditions of its couplings file, read after its
    SHA-256 is verified against the preregistration (``prereg``: the staged one, for a receipt;
    round 86), by default the one at ``root``, and its estimands. Raises ValueError (value-free)
    when either cannot be read or does not verify."""
    try:
        d = _dataset(root, dataset, prereg)
        rel, frozen = d["couplings"]["path"], d["couplings"]["sha256"]
        count, estimands = int(d["conditions"]), tuple(str(e) for e in d["estimands"])
    except (OSError, ValueError, KeyError, TypeError):
        raise ValueError(f"{PREREG}: the roster of {dataset} cannot be read") from None
    path = root / rel
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"{dataset}: the couplings file is absent, so the frozen roster cannot be read")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != frozen:
        raise ValueError(f"{dataset}: the couplings file is not at its frozen SHA-256")
    try:
        rows = list(csv.DictReader(io.StringIO(data.decode("utf-8"))))
        key = ("run", "sample") if rows and "run" in rows[0] else ("table", "T_K")
        conditions = tuple(sorted({f"{r[key[0]]}/{r[key[1]]}" for r in rows}))
    except (UnicodeDecodeError, KeyError, csv.Error):
        raise ValueError(f"{dataset}: the couplings file cannot be read") from None
    if len(conditions) != count:
        raise ValueError(f"{dataset}: the couplings file does not have the frozen number of conditions")
    return conditions, estimands


def pending_targets(root: Path, dataset: str, prereg: Mapping[str, Any] | None = None) -> frozenset[tuple[str, str]]:
    """The cells whose target the dataset's targets file marks pending, read after its SHA-256 is
    verified against the preregistration (as for ``roster``; round 85). Only the keys and the
    status column are read. A printed table has no pending target. Raises ValueError
    (value-free)."""
    try:
        d = _dataset(root, dataset, prereg)
        rel, frozen, form = d["targets"]["path"], d["targets"]["sha256"], d["targets"]["form"]
    except (OSError, ValueError, KeyError, TypeError):
        raise ValueError(f"{PREREG}: the targets of {dataset} cannot be read") from None
    path = root / rel
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"{dataset}: the targets file is absent, so its pending targets cannot be read")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != frozen:
        raise ValueError(f"{dataset}: the targets file is not at its frozen SHA-256")
    if form == "table":
        return frozenset()
    try:
        rows = list(csv.DictReader(io.StringIO(data.decode("utf-8"))))
        return frozenset((f"{r['table']}/{r['T_K']}", r["component"]) for r in rows if r["status"] == "pending")
    except (UnicodeDecodeError, KeyError, TypeError, csv.Error):
        raise ValueError(f"{dataset}: the targets file's pending targets cannot be read") from None


def _value(x: object) -> bool:
    return isinstance(x, int | float) and not isinstance(x, bool) and math.isfinite(x)


def entry_problem(entry: object) -> str | None:
    """Why one declaration is malformed (value-free), or None."""
    if not isinstance(entry, Mapping) or set(entry) != ENTRY_FIELDS:
        return f"does not have exactly the fields {sorted(ENTRY_FIELDS)}"
    if entry["quantity"] not in QUANTITIES:
        return "has an unknown quantity"
    if not all(isinstance(entry[k], str) for k in ("condition", "component")):
        return "names no cell"
    value, reason = entry["value"], entry["reason"]
    if value is not None and not _value(value):
        return "has no finite numeric value"
    if (value is None) == (reason is None):
        return "gives a value and a reason, or neither"
    if reason is not None and reason not in REASONS:
        return "gives an unknown pending reason"
    return None


def declarations(entries: Sequence[Mapping[str, Any]], frozen: Roster) -> list[str]:
    """Value-free problems of the well-formed declarations against the frozen roster."""
    conditions, estimands = frozen
    cells = {(c, e) for c in conditions for e in estimands}
    problems = []
    for track, (estimate, discrepancy) in TRACKS.items():
        declared: dict[str, dict[tuple[str, str], Mapping[str, Any]]] = {}
        for quantity in (estimate, discrepancy):
            mine = [e for e in entries if e["quantity"] == quantity]
            keys = [(e["condition"], e["component"]) for e in mine]
            if any(n > 1 for n in Counter(keys).values()):
                problems.append(f"a {quantity} is declared twice for one cell")
            if set(keys) != cells:
                problems.append(f"the {quantity} declarations are not exactly the frozen roster's cells")
            declared[quantity] = {(e["condition"], e["component"]): e for e in mine}
        for cell, d in declared[discrepancy].items():
            est = declared[estimate].get(cell)
            if d["value"] is not None and (est is None or est["value"] is None):
                problems.append(f"a {discrepancy} value has no {estimate} value")
                break
        if any(e["reason"] not in (None, *ESTIMATE_REASONS[track]) for e in declared[estimate].values()):
            problems.append(f"a {estimate} is pending for a reason a fit cannot have on this track")
        if track == "reproduction":
            undocumented = [
                e["reason"] == "inputs-undocumented" for q in (estimate, discrepancy) for e in declared[q].values()
            ]
            if any(undocumented) and not all(undocumented):
                problems.append("the authors'-analysis track is pending for undocumented inputs in part only")
    return problems


def consistency(
    entries: Sequence[Mapping[str, Any]],
    pending: frozenset[tuple[str, str]] | None,
    signed: object = None,
) -> list[str]:
    """Value-free problems of pending reasons that cannot hold together (round 85). ``pending``:
    the targets file's pending cells, or None when they cannot be read (that rule is skipped; the
    reader's problem is reported). ``signed``: the record's declared spot-check state (round 86):
    signed, the no-target cells are exactly the pending ones; unsigned, every target is withheld."""
    problems = []
    declared = signed
    withheld: list[bool] = []
    exact: list[bool] = []
    for estimate, discrepancy in TRACKS.values():
        est = {(e["condition"], e["component"]): e for e in entries if e["quantity"] == estimate}
        gap = {(e["condition"], e["component"]): e for e in entries if e["quantity"] == discrepancy}
        for cell, e in est.items():
            d = gap.get(cell)
            if d is None or d["value"] is not None:
                continue
            if e["value"] is None and d["reason"] != e["reason"]:
                problems.append(f"a {discrepancy} is pending for another reason than its {estimate}")
                break
            if e["value"] is not None and d["reason"] != "no-target":
                problems.append(
                    f"a {discrepancy} beside a {estimate} value is pending for a reason other than no target"
                )
                break
        ranked: dict[str, set[bool]] = {}
        for (condition, _), e in est.items():
            ranked.setdefault(condition, set()).add(e["reason"] == "rank-unverified")
        if any(len(flags) > 1 for flags in ranked.values()):
            problems.append(f"a condition's {estimate} is rank-pending for some components only")
        estimated = {cell for cell, e in est.items() if e["value"] is not None}
        none = {cell for cell in estimated if cell in gap and gap[cell]["reason"] == "no-target"}
        if estimated:
            withheld.append(none == estimated)
            exact.append(pending is not None and none == estimated & pending)
    # Round 86: the declared state decides, for both tracks alike (it replaces round 85's rule of
    # "withheld or exactly the pending cells", which the declaration makes stricter).
    if withheld and declared is True and pending is not None and not all(exact):
        problems.append("a signed run's no-target declarations are not exactly the targets file's pending cells")
    elif withheld and declared is False and not all(withheld):
        problems.append("a run before the spot-check was signed does not withhold every target")
    return problems


def _fitted(entries: Sequence[Mapping[str, Any]]) -> bool:
    """Whether the authors' analysis was fitted (its track is not pending for its inputs)."""
    return not any(e["quantity"] == "reproduction estimate" and e["reason"] == "inputs-undocumented" for e in entries)


def provenance(record: Mapping[str, Any], entries: Sequence[Mapping[str, Any]], frozen: Roster) -> list[str]:
    """Value-free problems of the record's provenance: the versions, the flags, the method, and
    one fit provenance (with its science hash and fit version) for every fitted condition."""
    p = record.get("provenance")
    if not isinstance(p, Mapping) or set(p) != PROVENANCE_FIELDS:
        return [f"no provenance with exactly the fields {sorted(PROVENANCE_FIELDS)}"]
    problems = []
    versions = p["versions"]
    if not isinstance(versions, Mapping) or not versions or not all(isinstance(x, str) for x in versions.values()):
        problems.append("the provenance names no package versions")
    method = p["method"]
    if not isinstance(method, Mapping) or method.get("mode") not in MODES:
        problems.append("the provenance names no method of the authors' analysis")
    elif (method["mode"] != "pending") != _fitted(entries):
        problems.append("the provenance's method does not match the authors'-analysis declarations")
    fits = p["fits"]
    if not isinstance(fits, Mapping) or set(fits) != set(TRACKS):
        return [*problems, "the provenance does not give the fits of both tracks"]
    conditions = set(frozen[0])
    expected = {"independent": conditions, "reproduction": conditions if _fitted(entries) else set()}
    for track, want in expected.items():
        given = fits[track]
        if not isinstance(given, Mapping) or set(given) != want:
            problems.append(f"the {track} fits' provenance is not exactly the fitted conditions")
            continue
        if not all(
            isinstance(f, Mapping) and all(isinstance(f.get(k), str) and f[k] for k in ("science_hash", "fit_version"))
            for f in given.values()
        ):
            problems.append(f"a {track} fit's provenance has no science hash or fit version")
    return problems


def check(
    record: Mapping[str, Any],
    entries: Sequence[Mapping[str, Any]],
    frozen: Roster | None,
    pending: frozenset[tuple[str, str]] | None = None,
) -> list[str]:
    """Value-free problems of a record whose fields and entries were read (``entries``: its
    well-formed declarations): the run fields, the declarations, their pending reasons (against
    the targets file's ``pending`` cells) and the provenance."""
    problems = []
    run = record.get("run")
    if isinstance(run, bool) or not isinstance(run, int) or run < 1:
        problems.append("no run number (a count from 1)")
    previous = record.get("previous_sha256")
    if previous is not None and not (isinstance(previous, str) and _SHA.fullmatch(previous)):
        problems.append("the previous record's SHA-256 is malformed")
    elif run == 1 and previous is not None:
        problems.append("a first run names a previous record")
    elif isinstance(run, int) and run > 1 and previous is None:
        problems.append("a later run names no previous record")
    report = record.get("report_sha256")
    if not (isinstance(report, str) and _SHA.fullmatch(report)):
        problems.append("no SHA-256 of its run's local report")
    if not isinstance(record.get("spot_check_signed"), bool):
        problems.append("no declared spot-check state (true or false)")
    if frozen is not None:
        problems += declarations(entries, frozen)
        problems += consistency(entries, pending, record.get("spot_check_signed"))
        problems += provenance(record, entries, frozen)
    return problems


def chain(
    root: Path, dataset: str, current: Mapping[str, Any] | None, retained: Mapping[int, tuple[Mapping[str, Any], str]]
) -> list[str]:
    """Value-free problems of one dataset's chain of runs: the retained records numbered 1..N
    with run numbers to match, the current record run N + 1, each naming its predecessor's
    SHA-256, and each run's report present at its SHA-256. ``retained`` maps n to the record
    read from retained/<dataset>.<n> and that file's SHA-256."""
    problems = []
    n = max(retained, default=0)
    count = len(retained)  # round 86: a number above the count is outside the sequence, never printed
    if sorted(retained) != list(range(1, n + 1)):
        problems.append(f"{DIR}/{RETAINED}: the retained {dataset} outputs are not numbered from 1 without a gap")
    if retained and current is None:
        problems.append(f"{DIR}: retained {dataset} outputs but no current one")
    runs: list[tuple[str, Mapping[str, Any], int]] = [
        (f"{DIR}/{RETAINED}/{dataset}.{k}{SUFFIX}" if k <= count else f"{DIR}/{RETAINED}/{UNEXPECTED}", r, k)
        for k, (r, _) in sorted(retained.items())
    ]
    if current is not None:
        runs.append((f"{DIR}/{dataset}{SUFFIX}", current, n + 1))
    for place, record, number in runs:
        if record.get("run") != number:
            problems.append(f"{place}: its run number is not its place in the chain")
        if number > 1:
            before = retained.get(number - 1)
            if before is None or record.get("previous_sha256") != before[1]:
                problems.append(f"{place}: the previous run's output is missing or changed")
        run = record.get("run")
        if isinstance(run, int) and not isinstance(run, bool) and run >= 1:
            report = root / DIR / REPORTS / f"{dataset}.{run}.md"
            if not report.is_file() or report.is_symlink():
                problems.append(f"{place}: its run's local report is missing")
            elif sha256(report) != record.get("report_sha256"):
                problems.append(f"{place}: its run's local report is changed")
            elif _signed_line(report) != record.get("spot_check_signed"):
                problems.append(f"{place}: its declared spot-check signed state is not its report's")
    return problems


def _signed_line(report: Path) -> bool | None:
    """The spot-check state the report states on its one ``SIGNED_LINE``, or None."""
    try:
        lines = [x for x in report.read_text(encoding="utf-8").splitlines() if x.startswith(SIGNED_LINE)]
    except UnicodeDecodeError:
        return None
    states = {"True": True, "False": False}
    return states.get(lines[0][len(SIGNED_LINE) :]) if len(lines) == 1 else None
