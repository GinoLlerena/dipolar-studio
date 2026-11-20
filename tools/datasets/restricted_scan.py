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

**What it does not find** (documented limits): values rounded below the tier's digits outside the
Phase 2 and validation docs; values spelled in words, split across lines or in images, PDFs or
compressed files; a value recoverable by arithmetic from other numbers; files outside git's index.
"""

from __future__ import annotations

import codecs
import csv
import hashlib
import re
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

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
