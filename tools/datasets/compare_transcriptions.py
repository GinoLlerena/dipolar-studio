"""Compare two independent transcriptions of a table, cell by cell (Phase 2 V0.2, decision 4).

    uv run python tools/datasets/compare_transcriptions.py A.csv B.csv [--key table,T_K,coupling]

Each file is a CSV with the same header. Rows are matched by the key columns. Every other column is
compared **as text, exactly** (the printed tokens), so "-12.34" and "-12.340" differ. Exit 0 when
the two agree on every cell and have the same keys; exit 1 otherwise, listing every difference.
This tool holds no data: the transcriptions it compares may be local-only (docs/phase2/v0.1-selection.md §5).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from pathlib import Path

#: The measured columns an ortho-dichlorobenzene transcription must have (V0.2).
ODCB_COLUMNS = ("D_token", "sigma_token", "D_Hz", "sigma_Hz")


def load(
    path: Path, key: tuple[str, ...], required: tuple[str, ...] = ()
) -> tuple[list[str], dict[tuple[str, ...], dict[str, str]]]:
    """Read a transcription strictly. A missing or duplicated header column, a missing key or
    required column, no column beyond the key, a malformed quote, a row of the wrong width or a
    duplicate key is an error (rounds 70 and 71b), never silent agreement."""
    with path.open(encoding="utf-8", newline="") as handle:
        try:
            records = list(csv.reader(handle, strict=True))
        except csv.Error as exc:
            raise ValueError(f"{path}: {exc}") from None
    if not records or not records[0]:
        raise ValueError(f"{path}: no header")
    header = records[0]
    if len(set(header)) != len(header):
        raise ValueError(f"{path}: duplicate header columns")
    missing = [c for c in (*key, *required) if c not in header]
    if missing:
        raise ValueError(f"{path}: the columns {missing} are not in the header")
    if len(header) <= len(key):
        raise ValueError(f"{path}: no column beyond the key")
    rows: dict[tuple[str, ...], dict[str, str]] = {}
    for number, fields in enumerate(records[1:], start=2):
        if len(fields) != len(header):
            raise ValueError(f"{path}: line {number} has {len(fields)} fields, the header {len(header)}")
        row = dict(zip(header, fields, strict=True))
        k = tuple(row[c] for c in key)
        if k in rows:
            raise ValueError(f"{path}: duplicate key {k}")
        rows[k] = row
    if not rows:
        raise ValueError(f"{path}: no rows")
    return header, rows


def compare(
    a: Path, b: Path, key: tuple[str, ...], expect: int | None = None, required: tuple[str, ...] = ()
) -> list[str]:
    header_a, rows_a = load(a, key, required)
    header_b, rows_b = load(b, key, required)
    problems: list[str] = []
    if expect is not None:
        for path, rows in ((a, rows_a), (b, rows_b)):
            if len(rows) != expect:
                problems.append(f"{path.name}: {len(rows)} keys, expected {expect}")
    if header_a != header_b:
        problems.append(f"headers differ: {header_a} vs {header_b}")
    for k in sorted(set(rows_a) - set(rows_b)):
        problems.append(f"only in {a.name}: {k}")
    for k in sorted(set(rows_b) - set(rows_a)):
        problems.append(f"only in {b.name}: {k}")
    for k in sorted(set(rows_a) & set(rows_b)):
        for column in header_a:
            if column in key or column not in rows_b[k]:
                continue
            if rows_a[k][column] != rows_b[k][column]:
                problems.append(f"{k} {column}: {rows_a[k][column]!r} vs {rows_b[k][column]!r}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("a", type=Path)
    parser.add_argument("b", type=Path)
    parser.add_argument("--key", default="table,T_K,coupling")
    parser.add_argument("--expect", type=int, default=None, help="the number of keys each file must have")
    parser.add_argument("--require", default=",".join(ODCB_COLUMNS), help="the columns each file must have")
    ns = parser.parse_args()
    key = tuple(ns.key.split(","))
    required = tuple(c for c in ns.require.split(",") if c)
    try:
        problems = compare(ns.a, ns.b, key, ns.expect, required)
    except ValueError as exc:
        print(f"error: {exc}")
        return 1
    for path in (ns.a, ns.b):
        print(f"{path}: SHA-256 {hashlib.sha256(path.read_bytes()).hexdigest()}")
    if problems:
        print(f"{len(problems)} difference(s):")
        for line in problems:
            print("  " + line)
        return 1
    print("the two transcriptions agree on every cell")
    return 0


if __name__ == "__main__":
    sys.exit(main())
