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
revision), kept across reruns under ``retained/``. Its problems name the file and the entry,
never a value, a key or an unexpected file name.

Round 84: an output is required only for a submission in the **committed** log (A1), so the
commit that logs a submission passes before its fit is run; outputs bound to a staged
submission are accepted. A record declares every cell of the frozen roster on both tracks and
carries its fits' provenance (A2, A4, A6; ``tools/validation/fit_record.py``), and each dataset's
records and reports form one hash-bound chain of runs (A6). A file name the scan does not expect
is never printed, whatever its characters (A3).

Round 85: a record's pending reasons must hold together, and its no-target cells must be either
every estimated cell (targets withheld) or exactly the cells the hash-verified targets file marks
pending (``fit_record.consistency``). A results scan receipt records each dataset's number of fit
outputs (``receipt_status``), and a later scan with fewer is a problem, so an earlier run restored
in place of later ones is found.

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
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from decimal import ROUND_DOWN, ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "validation"))
import first_fit_log as ffl  # noqa: E402
import fit_record as fr  # noqa: E402

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
FIT_QUANTITIES = fr.QUANTITIES
FIT_ENTRY_FIELDS = fr.ENTRY_FIELDS
FIT_RECORD_FIELDS = fr.RECORD_FIELDS
#: What a problem says in place of a file name the scan does not expect (round 84, A3).
UNEXPECTED_NAME = "(a file with an unexpected name)"
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
    outputs: dict[str, int] = field(default_factory=dict)  # per dataset (round 85: the receipt)


#: A results receipt's record of each dataset's number of fit outputs (round 85, the rollback anchor).
_RESULTS_RECEIPT = re.compile(
    r"passed, not skipped; fit tier: results \(files: " + ", ".join(rf"{re.escape(d)} (\d+)" for d in FIT_DATASETS) + r"\)"
)
#: The receipt a commit message records (Decision 11B); the next commit carries it into §6 (round 87),
#: with its own time and status (round 90: the tree alone let a row lower the results floor).
_LAST_RECEIPT = re.compile(r"Scan receipt \(Decision 11B\): tree ([0-9a-f]{40})")
_FULL_RECEIPT = re.compile(
    r"Scan receipt \(Decision 11B\): tree ([0-9a-f]{40}) at (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}Z): (.+?)\.(?: |$)"
)
#: A §6 scan receipt row (round 86: a staged ledger may not drop or change a committed one).
_RECEIPT_ROW = re.compile(r"\| \d{4}-\d{2}-\d{2}T\d{2}:\d{2}Z \| `[0-9a-f]{40}` .*")


def receipt_status(fit: FitTier) -> str:
    """The fit tier's status as a §6 scan receipt records it: for results, each dataset's number of
    fit outputs (round 85). Counts only, never a value."""
    if fit.status == PRE_RESULT:
        return "fit tier: pre-result"
    return "fit tier: results (files: " + ", ".join(f"{d} {fit.outputs.get(d, 0)}" for d in FIT_DATASETS) + ")"


def _receipted(ledger: str) -> dict[str, int]:
    """The largest number of each dataset's fit outputs that a §6 scan receipt recorded."""
    floor = dict.fromkeys(FIT_DATASETS, 0)
    for m in _RESULTS_RECEIPT.finditer(re.sub(r"\s+", " ", ledger)):  # round 87: across line breaks
        for dataset, n in zip(FIT_DATASETS, m.groups(), strict=True):
            floor[dataset] = max(floor[dataset], int(n))
    return floor


_STAMP = "%Y-%m-%dT%H:%MZ"
_RETAINED_NAME = re.compile(r"(.+)\.([1-9][0-9]*)" + re.escape(FIT_SUFFIX))


def _logged_record(entry: ffl.Entry) -> dict[str, str | None]:
    return {
        "dataset": entry.dataset,
        "runner": entry.runner,
        "at": entry.at.strftime(_STAMP),
        "release_or_commit": entry.release_or_commit,
        "protocol_sha256": entry.protocol_sha256,
    }


def _expected_name(name: str, retained: bool) -> tuple[str, int] | None:
    """The dataset a fit output's file name declares, and its retained number (0 for the current
    output); None for an unexpected name."""
    for dataset in FIT_DATASETS:
        if not retained and name == f"{dataset}{FIT_SUFFIX}":
            return dataset, 0
        m = _RETAINED_NAME.fullmatch(name)
        if retained and m and m.group(1) == dataset:
            return dataset, int(m.group(2))
    return None


class _Rosters:
    """Each dataset's frozen roster and pending targets, read once when an output of it is checked."""

    def __init__(self, root: Path, prereg: dict[str, Any] | None = None) -> None:
        self.root, self.prereg = root, prereg
        self.read: dict[str, fr.Roster | None] = {}
        self.pending: dict[str, frozenset[tuple[str, str]] | None] = {}
        self.problems: list[str] = []
        self.revisions: set[tuple[str, str, str]] | None = None

    def targets_sha(self, dataset: str) -> object:
        """The targets file's frozen SHA-256 in the judged preregistration, or None."""
        try:
            return fr._dataset(self.root, dataset, self.prereg)["targets"]["sha256"]
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def earlier(self) -> set[tuple[str, str, str]]:
        """(protocol revision, dataset, targets SHA-256) of every committed revision of the
        preregistration (round 87: a run is judged by the targets of its own revision)."""
        if self.revisions is None:
            self.revisions = set()
            log = subprocess.run(["git", "log", "--format=%H", "--", PREREG], cwd=self.root, capture_output=True)
            for commit in log.stdout.decode("ascii", errors="replace").split() if log.returncode == 0 else []:
                text = _git_show(self.root, f"{commit}:{PREREG}")
                try:
                    data = json.loads(text or "")
                    revision = fr.protocol_sha256(data)
                    for d, entry in data["datasets"].items():
                        self.revisions.add((revision, str(d), str(entry["targets"]["sha256"])))
                except (ValueError, KeyError, TypeError, AttributeError):
                    continue
        return self.revisions

    def targets(self, dataset: str) -> frozenset[tuple[str, str]] | None:
        if dataset not in self.pending:
            try:
                self.pending[dataset] = fr.pending_targets(self.root, dataset, self.prereg)
            except ValueError as exc:
                self.pending[dataset] = None
                self.problems.append(str(exc))
        return self.pending[dataset]

    def __call__(self, dataset: str | None) -> fr.Roster | None:
        if dataset is None:
            return None
        if dataset not in self.read:
            try:
                self.read[dataset] = fr.roster(self.root, dataset, self.prereg)
            except ValueError as exc:
                self.read[dataset] = None
                self.problems.append(str(exc))
        roster: fr.Roster | None = self.read[dataset]
        return roster


def _fit_entries(
    path: Path,
    rel: str,
    dataset: str | None,
    rosters: _Rosters,
    logged: list[dict[str, str | None]],
) -> tuple[list[float], list[str], dict[str, Any] | None, dict[str, Any] | None]:
    """One fit output: its finite values (all scanned), value-free problems, the logged
    submission it binds completely (None when it binds none), and the record read."""
    try:
        record: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        return [], [f"{rel}: not a readable JSON fit-values record"], None, None
    if not isinstance(record, dict):
        return [], [f"{rel}: not a fit-values record (an object with {sorted(FIT_RECORD_FIELDS)})"], None, None
    problems = []
    if set(record) - FIT_RECORD_FIELDS:
        problems.append(f"{rel}: unknown fields")
    if FIT_RECORD_FIELDS - set(record):
        problems.append(f"{rel}: missing fields (a record has {sorted(FIT_RECORD_FIELDS)})")
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
        return [], [*problems, f"{rel}: no fit values"], None, record
    values, good = [], []
    for i, entry in enumerate(entries):
        value = entry.get("value") if isinstance(entry, dict) else None
        if isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value):
            values.append(float(value))
        problem = fr.entry_problem(entry)
        if problem is None:
            good.append(entry)
        else:
            problems.append(f"{rel}: entry {i} {problem}")
    frozen = rosters(dataset) if dataset == record.get("dataset") else None
    if dataset is not None and frozen is None and dataset == record.get("dataset"):
        problems.append(f"{rel}: the frozen roster cannot be read, so its declarations cannot be checked")
    pending = None
    if frozen is not None and dataset is not None:
        declared, named = fr.pending_cells(record), record.get("targets_sha256")
        if named == rosters.targets_sha(dataset):  # the current targets file: read and checked
            pending = rosters.targets(dataset)
            if pending is None:
                problems.append(
                    f"{rel}: the targets file's pending cells cannot be read, so its no-target cells cannot be checked"
                )
            elif declared is not None and declared != pending:
                problems.append(f"{rel}: its pending targets are not the targets file's")
        elif (record.get("protocol_sha256"), dataset, named) in rosters.earlier():
            pending = declared  # round 87: an earlier revision's file, at the run's own declaration
        else:
            problems.append(f"{rel}: it names a targets file of no committed revision of the preregistration")
    problems += [f"{rel}: {p}" for p in fr.check(record, good, frozen, pending)]
    return values, problems, (submission if bound and not problems else None), record


def _submissions(text: str | None) -> list[ffl.Entry]:
    """The submissions of a ledger's first-fit log; none for a ledger without a readable log (a
    commit from before the log, or no commit)."""
    try:
        return ffl.submissions(ffl.parse(text or ""))
    except ValueError:
        return []


def fit_tier(
    root: Path,
    ledger: str | None = None,
    committed: str | None = None,
    *,
    prereg: str | None = None,
    anchors: Sequence[str] = (),
) -> FitTier:
    """The fit tier of the checkout at ``root``: its status, tiers and value-free problems.
    ``ledger`` is the ledger's text to judge by (the staged one, for a receipt); by default the
    working copy's. ``committed`` is the committed ledger's text (round 84, A1): only its
    submissions need an output; by default those of ``ledger``. Round 86: ``prereg`` is the
    preregistration's text to read the roster through (the staged one, for a receipt), by default
    the working copy's; ``anchors`` are further texts whose results receipts set the floor of
    outputs (the committed ledger and the last commit message)."""
    problems: list[str] = []
    prereg_data: dict[str, Any] | None = None
    if prereg is not None:
        try:
            prereg_data = json.loads(prereg)
        except ValueError:
            prereg_data = {}  # unreadable: every roster read reports it
        if not isinstance(prereg_data, dict):
            prereg_data = {}  # round 87: null, a list or a string is unreadable too, never "the working copy"
    logged_entries: list[ffl.Entry] = []
    ledger_text: str | None = None
    try:
        text = (root / LEDGER).read_text(encoding="utf-8") if ledger is None else ledger
        ledger_text = text
        section3 = _section3_logged(text)
        logged_entries = ffl.submissions(ffl.parse(text))
        logged = section3 or bool(logged_entries)
        if section3 and not logged_entries:
            problems.append(f"{LEDGER}: §3 records a first fit that the first-fit log (§10) does not")
    except (OSError, ValueError) as exc:
        problems.append(f"{LEDGER}: the first-fit record cannot be read ({type(exc).__name__})")
        logged = True  # unknown: require the tier
    required_entries = logged_entries if committed is None else _submissions(committed)
    rosters = _Rosters(root, prereg_data)
    logged_records = [_logged_record(e) for e in logged_entries]
    required = [_logged_record(e) for e in required_entries]
    folder = root / FIT_DIR
    found = [(p, False) for p in sorted(folder.glob(f"*{FIT_SUFFIX}"))] if folder.is_dir() else []
    kept = folder / fr.RETAINED
    found += [(p, True) for p in sorted(kept.glob(f"*{FIT_SUFFIX}"))] if kept.is_dir() else []
    values: list[float] = []
    satisfied: list[dict[str, Any]] = []
    current: dict[str, dict[str, Any]] = {}
    retained: dict[str, dict[int, tuple[dict[str, Any], str]]] = {}
    in_sequence: dict[str, int] = {}  # round 86: retained numbers above this count are never printed
    odd = [(p, r) for p, r in found if not p.is_file() or p.is_symlink()]
    found = [(p, r) for p, r in found if (p, r) not in odd]
    for _, is_retained in odd:  # round 87: neither read nor named
        place = f"{FIT_DIR}/{fr.RETAINED}" if is_retained else FIT_DIR
        problems.append(f"{place}/{UNEXPECTED_NAME}: not a regular file")
    for path, is_retained in found:
        named = _expected_name(path.name, is_retained)
        if is_retained and named is not None:
            in_sequence[named[0]] = in_sequence.get(named[0], 0) + 1
    for path, is_retained in found:
        place = f"{FIT_DIR}/{fr.RETAINED}" if is_retained else FIT_DIR
        expected = _expected_name(path.name, is_retained)
        printable = expected is not None and expected[1] <= in_sequence.get(expected[0], 0)
        rel = f"{place}/{path.name}" if printable else f"{place}/{UNEXPECTED_NAME}"
        if expected is None:
            problems.append(f"{rel}: not named <dataset>{FIT_SUFFIX} (or <dataset>.<n>{FIT_SUFFIX} when retained)")
        if path.is_symlink():
            problems.append(f"{rel}: a link, not a file")
        dataset = expected[0] if expected is not None else None
        got, bad, bound, record = _fit_entries(path, rel, dataset, rosters, logged_records)
        values += got
        problems += bad
        if bound is not None:
            satisfied.append(bound)
        if expected is not None:
            read = record if isinstance(record, dict) else {}
            if is_retained:
                retained.setdefault(expected[0], {})[expected[1]] = (read, fr.sha256(path))
            else:
                current[expected[0]] = read
    for dataset in sorted(set(current) | set(retained)):
        problems += fr.chain(root, dataset, current.get(dataset), retained.get(dataset, {}))
    outputs = {d: (d in current) + len(retained.get(d, {})) for d in FIT_DATASETS}
    if ledger_text is not None:
        for dataset, floor in _receipted(" ".join([ledger_text, *anchors])).items():
            if outputs[dataset] < floor:
                problems.append(
                    f"{FIT_DIR}: fewer {dataset} fit outputs than the latest scan receipt (§6) recorded: an output "
                    "was removed or an earlier run restored"
                )
    problems += rosters.problems
    for n, record in enumerate(required, start=1):
        if record not in satisfied:
            problems.append(
                f"the committed {record['dataset']} submission number {n} has no complete fit output under "
                f"{FIT_DIR}/: run the report workflow"
            )
    if logged and not logged_records and not found:
        problems.append(f"a first fit is logged but {FIT_DIR}/ holds no *{FIT_SUFFIX}: run the report workflow")
    if found and not logged_records:
        problems.append(f"{FIT_DIR}/ holds fit outputs but the first-fit log ({LEDGER} §10) has no submission")
    status = RESULTS if logged or found else PRE_RESULT
    tiers = fit_tiers(values) if values else []
    return FitTier(status, tiers, problems, len(found), len(values), outputs)


def status_line(fit: FitTier) -> str:
    """The tier's status for the scan receipt: counts only, never a value."""
    if fit.status == PRE_RESULT:
        return "fit tier: pre-result (no experimental fit is logged and no local fit output exists)"
    files = "file" if fit.files == 1 else "files"
    return f"fit tier: results ({fit.files} {files}, {fit.values} values, {len(fit.problems)} problems)"


def _git_show(root: Path, spec: str) -> str | None:
    shown = subprocess.run(["git", "show", spec], cwd=root, capture_output=True)
    return shown.stdout.decode("utf-8", errors="replace") if shown.returncode == 0 else None


def _staged(root: Path) -> tuple[list[str], FitTier]:
    """The staged checks and the fit tier judged by the **staged** ledger and preregistration
    (rounds 83 and 86). The staged first-fit log must extend the committed one, and the staged
    ledger must keep every committed scan receipt row. The committed ledger and the last commit
    message also set the receipt floor."""
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
        rows = {line.strip() for line in staged.splitlines()}
        if any(_RECEIPT_ROW.fullmatch(x.strip()) and x.strip() not in rows for x in committed.splitlines()):
            problems.append(f"{LEDGER}: the staged ledger drops or changes a committed scan receipt (§6)")
    message = subprocess.run(["git", "log", "-1", "--format=%B", "HEAD"], cwd=root, capture_output=True)
    last = message.stdout.decode("utf-8", errors="replace") if message.returncode == 0 else ""
    anchors = [committed or "", last]
    flat = re.sub(r"\s+", " ", last)
    receipt, full = _LAST_RECEIPT.search(flat), _FULL_RECEIPT.search(flat)
    if receipt and staged is not None:
        if full:
            tree, at, status = full.groups()
            row = re.compile(rf"\| {re.escape(at)} \| `{tree}` [^|]*\| {re.escape(status)} \| [^|]+ \|")
            carried = any(row.fullmatch(re.sub(r"\s+", " ", x.strip())) for x in staged.splitlines())
        else:
            carried = f"`{receipt.group(1)}`" in staged
        if not carried:
            problems.append(f"{LEDGER}: the last commit's scan receipt is not carried into §6 with its time and status")
    prereg = _git_show(root, f":{PREREG}")
    fit = fit_tier(
        root,
        ledger=staged if staged is not None else "",
        committed=committed or "",
        prereg=prereg if prereg is not None else "",
        anchors=anchors,
    )
    return [*problems, *fit.problems], fit


def check_staged(root: Path) -> list[str]:
    """The whole staged-index check: the staged checks and the fit tier (``_staged``), then
    ``path:line`` hits of every tier (the inputs' and the fit values'). Value-free."""
    problems, fit = _staged(root)
    hits = scan(index_blobs(root), restricted_tiers(root) + fit.tiers, ALLOWED_LINES)
    return [*problems, *hits]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="The restricted-fit scan tier's status (value-free).")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    ns = parser.parse_args(argv)
    problems, fit = _staged(ns.root)  # judged as receipted: the staged ledger and preregistration
    print(status_line(fit))
    print(f"receipt: {receipt_status(fit)}")
    for problem in problems:
        print(f"- {problem}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
