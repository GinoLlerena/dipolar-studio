"""Scan git's tracked blobs for restricted values (Phase 2 V0.3, rounds 73–74).

The restricted values are the ortho-dichlorobenzene couplings and digitized targets (© ISMAR) and
the benzene paper's order parameters (© ACS). They live only in ``datasets-local/``; this module
holds none of them, and reports a hit as ``path:line`` without the value.

**What is found.** Every numeric literal is parsed (sign, including U+2212; a decimal point or a
colon; a leading point; an exponent) and compared by value, so trailing zeros, scientific notation
and the colon form all match. A literal must carry at least the tier's number of significant
digits, so short numbers such as ``37`` do not collide with everything. Blobs are decoded as UTF-8,
or as UTF-16/32 by byte-order mark or by their NUL pattern.

**The exceptions** are single lines (by hash) verified to exist in a commit before the first
exposure (2026-11-18), and the ``upload-time`` fields of ``uv.lock``.

**The fit tier** (V1.5b; tests/test_v15_fit_tier.py). After the first experimental fit, the
report workflow's full-precision fit values (``datasets-local/verification/<dataset>.fit-values.json``:
every fitted condition's paper-frame estimates and every compared cell's discrepancy) are restricted
too. Each is matched as written and at 4–8 significant digits (half-up, half-even and truncated,
from its shortest repr and from its exact binary value) in any path, and at 3 significant digits in
the Phase 2 and validation docs. A variant with fewer significant digits than its tier (a whole or
short value such as 1.0 or 0.12) is not matched. The ledger's first-fit row (gates.md §3) decides
whether the tier is required: ``pre-result`` while no submission is logged and no local fit
output exists, ``results`` after; local fit outputs without a logged fit are a first-fit-gate
problem. Round 83: a submission is logged in the ledger's first-fit log (gates.md §10; a filled §3
row also counts), and the staged check judges by the **staged** ledger, whose log must extend the
committed one. Each logged submission needs a complete output bound to it (its exact fields and
revision, one estimate per roster cell), kept across reruns under ``retained/``. Its problems name
the file and the entry, never a value, a key or an unexpected file name.

**What it does not find** (documented limits): values rounded below the tier's digits outside the
Phase 2 and validation docs; values spelled in words, split across lines or in images, PDFs or
compressed files; a value recoverable by arithmetic from other numbers (a fit from its target and
discrepancy, a standard error, a predicted coupling); files outside git's index.
"""

from __future__ import annotations

import argparse
import codecs
import csv
import hashlib
import json
import math
import re
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from decimal import ROUND_DOWN, ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "validation"))
import first_fit_log as ffl  # noqa: E402

FIRST_EXPOSURE = "2026-11-18"
NUMBER = re.compile(r"(?<![\w.:])([-+−]?)(\d+(?:[.:]\d+)?|\.\d+)(?:[eE]([-+]?\d+))?(?![\w]|[.:]\d)")
UPLOAD_TIME = re.compile(r'upload-time = "[^"]*"')

#: Lines that contain a restricted-looking number by coincidence, in files added before the
#: first exposure: a Phase 1 mockup (three lines) and three browser-test lines. Verified by
#: ``verify_allowed``.
ALLOWED_LINES: frozenset[tuple[str, str]] = frozenset(
    {
        ("docs/panel/mockup-workspace.html", "f6c9d66716dd70dd"),
        ("docs/panel/mockup-workspace.html", "2c37a18f8e12753f"),
        ("docs/panel/mockup-workspace.html", "a0126542b63b803e"),
        ("web/e2e/preview.spec.ts", "40fea40b0b94d7d2"),
        ("web/e2e/preview.spec.ts", "0bfa5994ca9f3851"),
        ("web/e2e/tutorial.spec.ts", "2eb42a7874fc674d"),
    }
)


@dataclass(frozen=True)
class Tier:
    values: frozenset[Decimal]  # absolute values, normalized
    min_sig: int
    prefixes: tuple[str, ...] | None  # None: every path


def line_hash(line: str) -> str:
    return hashlib.sha256(line.rstrip().encode("utf-8")).hexdigest()[:16]


def _norm(value: Decimal) -> Decimal:
    return abs(value).normalize()


def numbers(line: str) -> Iterable[tuple[Decimal, int]]:
    """(absolute value, significant digits) of each numeric literal in a line."""
    for m in NUMBER.finditer(line):
        mantissa = m.group(2).replace(":", ".")
        digits = mantissa.replace(".", "").lstrip("0")
        try:
            value = Decimal(mantissa).scaleb(int(m.group(3) or 0))
        except InvalidOperation:
            continue
        yield _norm(value), len(digits)


def decode(data: bytes) -> str | None:
    """Text of a blob, or None for binary data."""
    for bom, encoding in (
        (codecs.BOM_UTF32_LE, "utf-32"),
        (codecs.BOM_UTF32_BE, "utf-32"),
        (codecs.BOM_UTF16_LE, "utf-16"),
        (codecs.BOM_UTF16_BE, "utf-16"),
    ):
        if data.startswith(bom):
            return data.decode(encoding, errors="replace")
    if b"\x00" not in data:
        return data.decode("utf-8", errors="replace")
    for encoding in ("utf-16-le", "utf-16-be", "utf-32-le", "utf-32-be"):
        try:
            text = data.decode(encoding)
        except UnicodeDecodeError:
            continue
        ascii_text = sum(c.isascii() and (c.isprintable() or c in "\n\r\t") for c in text)
        if text and ascii_text / len(text) > 0.9:
            return text
    return None


def scan(blobs: Iterable[tuple[str, bytes]], tiers: list[Tier], allowed: frozenset[tuple[str, str]]) -> list[str]:
    """``path:line`` for each line holding a restricted value (once per line)."""
    hits = []
    for path, data in blobs:
        text = decode(data)
        if text is None:
            continue
        if path.endswith("uv.lock"):
            text = UPLOAD_TIME.sub('upload-time = ""', text)
        active = [t for t in tiers if t.prefixes is None or path.startswith(t.prefixes)]
        for number, line in enumerate(text.splitlines(), start=1):
            if (path, line_hash(line)) in allowed:
                continue
            if any(v in t.values and sig >= t.min_sig for v, sig in numbers(line) for t in active):
                hits.append(f"{path}:{number}")
    return hits


def index_blobs(root: Path) -> list[tuple[str, bytes]]:
    """Every regular file blob in git's index (what would be committed), with its bytes."""
    listing = subprocess.run(["git", "ls-files", "-s", "-z"], cwd=root, capture_output=True, check=True).stdout
    entries = []
    for record in listing.decode().split("\0"):
        if not record:
            continue
        meta, path = record.split("\t", 1)
        mode, sha, _stage = meta.split()
        if mode in ("100644", "100755"):
            entries.append((path, sha))
    batch = subprocess.run(
        ["git", "cat-file", "--batch"],
        cwd=root,
        input="".join(f"{sha}\n" for _, sha in entries).encode(),
        capture_output=True,
        check=True,
    ).stdout
    blobs, pos = [], 0
    for path, _ in entries:
        header_end = batch.index(b"\n", pos)
        size = int(batch[pos:header_end].split()[2])
        start = header_end + 1
        blobs.append((path, batch[start : start + size]))
        pos = start + size + 1
    return blobs


def restricted_files(root: Path) -> tuple[Path, Path, Path]:
    local = root / "datasets-local"
    return (
        local / "odcb-chandrakumar1993" / "couplings.csv",
        local / "odcb-chandrakumar1993" / "targets.csv",
        local / "benzene-taggar2006-targets" / "targets.csv",
    )


def restricted_tiers(root: Path) -> list[Tier]:
    """Everywhere: the printed couplings (four or more significant digits) and every target as
    written and at four decimals. In the Phase 2 and validation docs, also the targets at three
    decimals, the likeliest form of a leak in a write-up."""
    couplings, odcb_targets, benzene_targets = restricted_files(root)
    everywhere: set[Decimal] = set()
    with couplings.open(encoding="utf-8", newline="") as handle:
        for r in csv.DictReader(handle):
            token = r["D_token"].replace(":", ".")
            if len(token.lstrip("-").replace(".", "").lstrip("0")) >= 4:
                everywhere.add(_norm(Decimal(token)))
    targets: list[Decimal] = []
    for path, columns in ((odcb_targets, ("value", "fig2_value")), (benzene_targets, ("S_zz",))):
        with path.open(encoding="utf-8", newline="") as handle:
            targets += [Decimal(r[c]) for r in csv.DictReader(handle) for c in columns if r[c]]
    for v in targets:
        everywhere |= {_norm(v), _norm(v.quantize(Decimal("0.0001")))}
    docs = {_norm(v.quantize(Decimal("0.001"))) for v in targets}
    return [Tier(frozenset(everywhere), 4, None), Tier(frozenset(docs), 3, ("docs/phase2/", "docs/validation/"))]


def verify_allowed(root: Path) -> list[str]:
    """Each allowed line must exist in its file in the last commit before the first exposure."""
    commit = subprocess.run(
        ["git", "rev-list", "-1", f"--before={FIRST_EXPOSURE}T00:00:00", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    problems = []
    for path, digest in sorted(ALLOWED_LINES):
        shown = subprocess.run(["git", "show", f"{commit}:{path}"], cwd=root, capture_output=True, text=True)
        if shown.returncode != 0 or digest not in {line_hash(line) for line in shown.stdout.splitlines()}:
            problems.append(f"{path}: an allowed line is not in {commit[:7]}, before {FIRST_EXPOSURE}")
    return problems


# --------------------------------------------------------------------------- the fit tier (V1.5b)
FIT_DIR = "datasets-local/verification"
FIT_SUFFIX = ".fit-values.json"
#: The first scan receipt (gates.md §6) that records the fit tier's status.
FIT_TIER_SINCE = "2026-11-23T14:30Z"
LEDGER = "docs/phase2/verification/gates.md"
FIRST_FIT_FIELD = "| First experimental fit submission ("
FIT_DATASETS = ("benzene-taggar2006", "odcb-chandrakumar1993")
FIT_QUANTITIES = ("estimate", "discrepancy")
FIT_ENTRY_FIELDS = frozenset({"condition", "component", "quantity", "value"})
FIT_RECORD_FIELDS = frozenset({"dataset", "protocol_sha256", "submission", "values"})
PREREG = "docs/phase2/v0.3-preregistration.json"
#: The declared variants: significant digits matched in any path, and in the docs only.
FIT_DIGITS_EVERYWHERE = (4, 5, 6, 7, 8)
FIT_DIGITS_DOCS = (3,)
DOCS_PREFIXES = ("docs/phase2/", "docs/validation/")
_ROUNDINGS = (ROUND_HALF_UP, ROUND_HALF_EVEN, ROUND_DOWN)
PRE_RESULT, RESULTS = "pre-result", "results"


def _significant(value: Decimal) -> int:
    return len(value.normalize().as_tuple().digits) if value != 0 else 0


def _rounded(value: Decimal, digits: int) -> set[Decimal]:
    exponent = value.adjusted() - digits + 1
    return {_norm(value.quantize(Decimal(1).scaleb(exponent), rounding=r)) for r in _ROUNDINGS}


def fit_tiers(values: Iterable[float]) -> list[Tier]:
    """The fit tier's two tiers for the given full-precision values (see the module docstring)."""
    everywhere: set[Decimal] = set()
    docs: set[Decimal] = set()
    for x in values:
        if not math.isfinite(x) or x == 0:
            continue
        for exact in {Decimal(repr(x)), Decimal(x)}:
            if exact == Decimal(repr(x)):
                everywhere.add(_norm(exact))
            for n in FIT_DIGITS_EVERYWHERE:
                everywhere |= _rounded(exact, n)
            for n in FIT_DIGITS_DOCS:
                docs |= _rounded(exact, n)
    return [
        Tier(frozenset(v for v in everywhere if _significant(v) >= 4), 4, None),
        Tier(frozenset(v for v in docs if _significant(v) >= 3), 3, DOCS_PREFIXES),
    ]


def _section3_logged(ledger: str) -> bool:
    """Whether the §3 first-fit row records a submission (anything but ``empty``)."""
    rows = [line for line in ledger.splitlines() if line.startswith(FIRST_FIT_FIELD)]
    if len(rows) != 1:
        raise ValueError(f"the ledger has {len(rows)} first-fit rows in §3, not one")
    cells = [c.strip() for c in rows[0].strip().strip("|").split("|")]
    if len(cells) != 2 or not cells[1]:
        raise ValueError("the ledger's §3 first-fit row has no value")
    return cells[1] != "empty"


def first_fit_logged(ledger: str) -> bool:
    """Whether a first fit is logged: a submission in the §10 first-fit log (round 83, A1), or a
    filled §3 row. Raises ValueError when either is unreadable."""
    return _section3_logged(ledger) | bool(ffl.submissions(ffl.parse(ledger)))


@dataclass(frozen=True)
class FitTier:
    status: str  # PRE_RESULT or RESULTS
    tiers: list[Tier] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    files: int = 0
    values: int = 0


_SAFE_NAME = re.compile(r"[A-Za-z0-9._-]+")
_STAMP = "%Y-%m-%dT%H:%MZ"


def _logged_record(entry: ffl.Entry) -> dict[str, str | None]:
    return {
        "dataset": entry.dataset,
        "runner": entry.runner,
        "at": entry.at.strftime(_STAMP),
        "release_or_commit": entry.release_or_commit,
        "protocol_sha256": entry.protocol_sha256,
    }


def _expected_name(name: str, retained: bool) -> str | None:
    """The dataset a fit output's file name declares, or None for an unexpected name."""
    for dataset in FIT_DATASETS:
        if not retained and name == f"{dataset}{FIT_SUFFIX}":
            return dataset
        if retained and re.fullmatch(re.escape(dataset) + r"\.[1-9][0-9]*" + re.escape(FIT_SUFFIX), name):
            return dataset
    return None


def _coverage(entries: list[dict[str, Any]], roster: tuple[int, tuple[str, ...]] | None) -> list[str]:
    """Value-free coverage problems: one estimate for every roster cell, no repeats, and a
    discrepancy only for an estimated cell."""
    keys = [(e["condition"], e["component"]) for e in entries if e.get("quantity") == "estimate"]
    gaps = [(e["condition"], e["component"]) for e in entries if e.get("quantity") == "discrepancy"]
    problems = []
    if len(set(keys)) != len(keys) or len(set(gaps)) != len(gaps):
        problems.append("a cell is repeated")
    if not set(gaps) <= set(keys):
        problems.append("a discrepancy has no estimate")
    if roster is None:
        return problems
    conditions, estimands = roster
    by_condition: dict[str, set[str]] = {}
    for condition, component in keys:
        by_condition.setdefault(condition, set()).add(component)
    if len(by_condition) != conditions or any(c != set(estimands) for c in by_condition.values()):
        problems.append("the estimates do not cover the roster exactly")
    return problems


def _fit_entries(
    path: Path,
    rel: str,
    dataset: str | None,
    roster: dict[str, tuple[int, tuple[str, ...]]],
    logged: list[dict[str, str | None]],
) -> tuple[list[float], list[str], dict[str, Any] | None]:
    """One fit output: its well-formed values, value-free problems, and the logged submission it
    binds completely (None when it binds none)."""
    try:
        record: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        return [], [f"{rel}: not a readable JSON fit-values record"], None
    if not isinstance(record, dict):
        return [], [f"{rel}: not a fit-values record (an object with {sorted(FIT_RECORD_FIELDS)})"], None
    problems = []
    if set(record) - FIT_RECORD_FIELDS:
        problems.append(f"{rel}: unknown fields")
    if record.get("dataset") not in FIT_DATASETS:
        problems.append(f"{rel}: the dataset is not one of {list(FIT_DATASETS)}")
    elif record["dataset"] != dataset:
        problems.append(f"{rel}: the record is of another dataset than its file name")
    protocol = record.get("protocol_sha256")
    if not isinstance(protocol, str) or not re.fullmatch(r"[0-9a-f]{64}", protocol):
        problems.append(f"{rel}: no protocol revision")
    submission = record.get("submission")
    bound = (
        isinstance(submission, dict)
        and submission in logged
        and submission.get("dataset") == record.get("dataset")
        and submission.get("protocol_sha256") == protocol
    )
    if not bound:
        problems.append(f"{rel}: not bound to a submission of the first-fit log (gates.md §10) at its revision")
    entries = record.get("values")
    if not isinstance(entries, list) or not entries:
        return [], [*problems, f"{rel}: no fit values"], None
    values, good = [], []
    for i, entry in enumerate(entries):
        value = entry.get("value") if isinstance(entry, dict) else None
        if not isinstance(entry, dict) or set(entry) != FIT_ENTRY_FIELDS:
            problems.append(f"{rel}: entry {i} does not have exactly the fields {sorted(FIT_ENTRY_FIELDS)}")
        elif entry["quantity"] not in FIT_QUANTITIES:
            problems.append(f"{rel}: entry {i} has an unknown quantity")
        elif not all(isinstance(entry[k], str) for k in ("condition", "component")):
            problems.append(f"{rel}: entry {i} names no cell")
        else:
            good.append(entry)
        if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
            problems.append(f"{rel}: entry {i} has no finite numeric value")
            continue
        values.append(float(value))
    problems += [f"{rel}: {p}" for p in _coverage(good, roster.get(dataset or ""))]
    return values, problems, (submission if bound and not problems else None)


def _roster(root: Path) -> tuple[dict[str, tuple[int, tuple[str, ...]]], list[str]]:
    try:
        datasets = json.loads((root / PREREG).read_text(encoding="utf-8"))["datasets"]
        return {k: (int(datasets[k]["conditions"]), tuple(datasets[k]["estimands"])) for k in FIT_DATASETS}, []
    except (OSError, ValueError, KeyError, TypeError):
        return {}, [f"{PREREG}: the roster cannot be read"]


def fit_tier(root: Path, ledger: str | None = None) -> FitTier:
    """The fit tier of the checkout at ``root``: its status, tiers and value-free problems.
    ``ledger`` is the ledger's text to judge by (the staged one, for a receipt); by default the
    working copy's."""
    problems: list[str] = []
    logged_entries: list[ffl.Entry] = []
    try:
        text = (root / LEDGER).read_text(encoding="utf-8") if ledger is None else ledger
        section3 = _section3_logged(text)
        logged_entries = ffl.submissions(ffl.parse(text))
        logged = section3 or bool(logged_entries)
        if section3 and not logged_entries:
            problems.append(f"{LEDGER}: §3 records a first fit that the first-fit log (§10) does not")
    except (OSError, ValueError) as exc:
        problems.append(f"{LEDGER}: the first-fit record cannot be read ({type(exc).__name__})")
        logged = True  # unknown: require the tier
    roster, roster_problems = _roster(root)
    logged_records = [_logged_record(e) for e in logged_entries]
    folder = root / FIT_DIR
    found = [(p, False) for p in sorted(folder.glob(f"*{FIT_SUFFIX}"))] if folder.is_dir() else []
    kept = folder / "retained"
    found += [(p, True) for p in sorted(kept.glob(f"*{FIT_SUFFIX}"))] if kept.is_dir() else []
    values: list[float] = []
    satisfied: list[dict[str, Any]] = []
    for path, retained in found:
        place = f"{FIT_DIR}/retained" if retained else FIT_DIR
        if _SAFE_NAME.fullmatch(path.name):
            rel = f"{place}/{path.name}"
        else:
            rel = f"{place}/(a file with an unexpected name)"
        dataset = _expected_name(path.name, retained)
        if dataset is None:
            problems.append(f"{rel}: not named <dataset>{FIT_SUFFIX} (or <dataset>.<n>{FIT_SUFFIX} when retained)")
        got, bad, bound = _fit_entries(path, rel, dataset, roster, logged_records)
        values += got
        problems += bad
        if bound is not None:
            satisfied.append(bound)
    if found or logged:
        problems += roster_problems
    for n, record in enumerate(logged_records, start=1):
        if record not in satisfied:
            problems.append(
                f"the logged {record['dataset']} submission number {n} has no complete fit output under "
                f"{FIT_DIR}/: run the report workflow"
            )
    if logged and not logged_records and not found:
        problems.append(f"a first fit is logged but {FIT_DIR}/ holds no *{FIT_SUFFIX}: run the report workflow")
    if found and not logged_records:
        problems.append(f"{FIT_DIR}/ holds fit outputs but the first-fit log ({LEDGER} §10) has no submission")
    status = RESULTS if logged or found else PRE_RESULT
    tiers = fit_tiers(values) if values else []
    return FitTier(status, tiers, problems, len(found), len(values))


def status_line(fit: FitTier) -> str:
    """The tier's status for the scan receipt: counts only, never a value."""
    if fit.status == PRE_RESULT:
        return "fit tier: pre-result (no experimental fit is logged and no local fit output exists)"
    files = "file" if fit.files == 1 else "files"
    return f"fit tier: results ({fit.files} {files}, {fit.values} values, {len(fit.problems)} problems)"


def _git_show(root: Path, spec: str) -> str | None:
    shown = subprocess.run(["git", "show", spec], cwd=root, capture_output=True)
    return shown.stdout.decode("utf-8", errors="replace") if shown.returncode == 0 else None


def check_staged(root: Path) -> list[str]:
    """The whole staged-index check: the fit tier judged by the **staged** ledger, whose first-fit
    log must extend the committed one (round 83, A1), then ``path:line`` hits of every tier (the
    inputs' and the fit values'). Value-free."""
    staged = _git_show(root, f":{LEDGER}")
    problems = [] if staged is not None else [f"{LEDGER}: not in git's index"]
    committed = _git_show(root, f"HEAD:{LEDGER}")
    if staged is not None and committed is not None:
        try:
            old = ffl.parse(committed)
        except ValueError:
            old = []  # a commit from before the log
        try:
            if not ffl.extends(old, ffl.parse(staged)):
                problems.append(f"{LEDGER}: the staged first-fit log drops or changes a committed row")
        except ValueError:
            pass  # reported by the fit tier below
    fit = fit_tier(root, ledger=staged if staged is not None else "")
    hits = scan(index_blobs(root), restricted_tiers(root) + fit.tiers, ALLOWED_LINES)
    return [*problems, *fit.problems, *hits]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="The restricted-fit scan tier's status (value-free).")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    ns = parser.parse_args(argv)
    fit = fit_tier(ns.root, ledger=_git_show(ns.root, f":{LEDGER}"))  # the staged ledger, as receipted
    print(status_line(fit))
    for problem in fit.problems:
        print(f"- {problem}")
    return 1 if fit.problems else 0


if __name__ == "__main__":
    sys.exit(main())
