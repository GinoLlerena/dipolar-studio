"""Read the published benzene order parameters of Taggar et al. (2006), Tables 1–2 (Phase 2 V0.3).

    uv run --group datasets python tools/datasets/taggar2006_targets.py \\
        --pdf datasets-local/sources/taggar-2006.pdf --out datasets-local/benzene-taggar2006-targets/targets.csv

The paper is © 2006 American Chemical Society: its values are comparison targets used locally and
are **never committed** (docs/phase2/v0.1-selection.md §5). This tool holds no data.

Two independent extraction implementations of the PDF's one text layer must agree token for
token (decision 4, applied to a text layer; the owner's spot-check against the rendered page is
kept, since both read the same layer):
- **A**, pypdf's text flow, parsed row by row ("benzene <sample> <S_zz token> …");
- **B**, pdfminer's positioned text lines, joined by baseline: each S_zz token is paired with the
  "benzene" label and the sample on the same line of the table.
Each table's rows are mapped to the Supporting Information's conditions (Table 1 is run 1, Table
2 is run 2; "mix 1" is the SI's ``mix1``). The tool exits 1 on any disagreement.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import logging
import re
import sys
from decimal import Decimal
from pathlib import Path

PDF_SHA256 = "14d7adc3ca88d9041c8f1bb24610755eaa9899df858a7e3e3dfb0aa9ff0928d5"
#: Table 1 is on the PDF's page 2 (run 1), Table 2 on page 3 (run 2).
TABLES = {"1": (2, "TABLE 1"), "2": (3, "TABLE 2")}
TOKEN = r"-?\d\.\d+\(\d+\)"
SAMPLE = r"(?:mix ?\d(?:\.\d)?|\d+\.\d+)"
EXPECTED = {"1": 7, "2": 8}


def _sample(label: str) -> str:
    return label.replace(" ", "")


def reading_a(pdf: Path) -> dict[tuple[str, str], str]:
    from pypdf import PdfReader

    reader = PdfReader(str(pdf))
    out: dict[tuple[str, str], str] = {}
    for run, (page, title) in TABLES.items():
        text = reader.pages[page - 1].extract_text()
        body = text[text.index(title) :].split(" Column A shows")[0]
        for line in body.splitlines():
            m = re.fullmatch(rf"benzene ({SAMPLE}) ({TOKEN}) {TOKEN}", line.strip())
            if m:
                out[(run, _sample(m.group(1)))] = m.group(2)
    return out


def reading_b(pdf: Path) -> dict[tuple[str, str], str]:
    from pdfminer.high_level import extract_pages
    from pdfminer.layout import LTTextContainer, LTTextLine

    out: dict[tuple[str, str], str] = {}
    for run, (page, title) in TABLES.items():
        lines: list[tuple[float, float, str]] = []
        for layout in extract_pages(str(pdf), page_numbers=[page - 1]):
            for element in layout:
                if isinstance(element, LTTextContainer):
                    for line in element:
                        if isinstance(line, LTTextLine):
                            lines.append((line.y0, line.x0, line.get_text().strip()))
        top = max(y for y, _, t in lines if t.startswith(title))
        foot = max(y for y, _, t in lines if t.startswith("a Column A") and y < top)
        rows = [(y, x, t) for y, x, t in lines if foot < y < top]
        labels = [(y, x) for y, x, t in rows if t == "benzene"]
        for y, x, t in rows:
            if not re.fullmatch(TOKEN, t):
                continue
            same = sorted((x2, t2) for y2, x2, t2 in rows if abs(y2 - y) < 2.0 and x2 < x)
            if not any(abs(y2 - y) < 2.0 for y2, _ in labels) or len(same) < 2:
                continue
            first_token = min(x2 for y2, x2, t2 in rows if abs(y2 - y) < 2.0 and re.fullmatch(TOKEN, t2))
            if x != first_token:
                continue  # the Hsol/kBT column
            sample = [t2 for _, t2 in same if re.fullmatch(SAMPLE, t2)]
            if len(sample) == 1:
                out[(run, _sample(sample[0]))] = t
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if hashlib.sha256(args.pdf.read_bytes()).hexdigest() != PDF_SHA256:
        print("the PDF is not the recorded file", file=sys.stderr)
        return 1
    logging.disable(logging.WARNING)  # font-encoding notices from both readers
    a, b = reading_a(args.pdf), reading_b(args.pdf)
    counts = {run: sum(k[0] == run for k in a) for run in TABLES}
    if a != b or counts != EXPECTED:
        only = sorted(set(a) ^ set(b))
        diff = sorted(k for k in set(a) & set(b) if a[k] != b[k])
        print(f"readings disagree: counts {counts}, keys only in one {only}, cells differ {diff}", file=sys.stderr)
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["run", "sample", "S_zz_token", "S_zz", "sigma"])
        for (run, sample), token in sorted(a.items()):
            value, err = token.rstrip(")").split("(")
            decimals = len(value.split(".")[1])
            writer.writerow([run, sample, token, value, str(Decimal(int(err)).scaleb(-decimals))])
    digest = hashlib.sha256(args.out.read_bytes()).hexdigest()
    print(f"{len(a)} targets, both readings identical; written to {args.out}; sha256 {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
