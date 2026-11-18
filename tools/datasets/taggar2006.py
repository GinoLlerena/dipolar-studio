"""Parse the benzene couplings of Taggar et al. (2006), Supporting Information (Phase 2, V0.2).

    uv run python tools/datasets/taggar2006.py --write   # rebuild couplings.csv from the source
    uv run python tools/datasets/taggar2006.py --check   # CI: the source's hash and the CSV are current

The source is the plain-text Supporting Information of A. S. Taggar, C. J. Campbell, A. Yethiraj
and E. E. Burnell, J. Phys. Chem. B 110, 1363–1368 (2006), DOI 10.1021/jp052592j.s001 (ACS
Figshare, CC BY-NC 4.0). It is kept byte for byte in ``source/`` and checked by SHA-256.

Only the **benzene** section is parsed: 15 conditions × (D12, D13, D14). Each value is printed
with its uncertainty in the last digits: a (synthetic) token ``-123.456(12)`` reads D = -123.456 Hz,
sigma = 0.012 Hz. The values are kept exactly as printed (``D_token``), and nothing is converted
(no J subtracted, no factor 2): they are the source's effective D (docs/phase2/v0.1-selection.md).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import re
import sys
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATASET = ROOT / "datasets" / "benzene-zli1132-taggar2006"
SOURCE = DATASET / "source" / "jp052592j_si_001.txt"
OUTPUT = DATASET / "couplings.csv"
SOURCE_SHA256 = "a52e77b8061b010607d486548c62abb4f9a8f93dad3e4a2a4ff78f65e119dd29"

#: The benzene protons are H1–H6 around the ring; the source's columns are D12, D13 and D14.
PAIRS = {"D12": ("H1", "H2", "ortho"), "D13": ("H1", "H3", "meta"), "D14": ("H1", "H4", "para")}
#: Mixed-sample compositions (mol % benzene/tfb/tcb/tbb), from the paper's Tables 1–2 footnotes.
MIXED = {
    "mix1": "3.65/2.70/4.29/2.77",
    "mix2.1": "2.129/0.000/1.984/0.000",
    "mix2.2": "1.748/1.669/0.885/0.510",
    "mix2.3": "2.846/0.000/1.060/0.000",
}
COLUMNS = (
    "run",
    "sample",
    "benzene_mol_percent",
    "co_solutes_mol_percent",
    "coupling",
    "class",
    "spin_a",
    "spin_b",
    "D_token",
    "D_obs_Hz",
    "sigma_Hz",
)
_VALUE = re.compile(r"^(-?\d+\.(\d+))\((\d+)\)$")
EXPECTED_CONDITIONS = 15


def _value(token: str) -> tuple[str, str]:
    """``-123.456(12)`` → ("-123.456", "0.012"): the uncertainty is in units of the last digit."""
    match = _VALUE.match(token)
    if match is None:
        raise ValueError(f"unexpected value token {token!r}")
    value, decimals, error = match.group(1), len(match.group(2)), int(match.group(3))
    sigma = Decimal(error).scaleb(-decimals)
    return value, format(sigma, "f")


def parse(text: str) -> list[dict[str, str]]:
    sections = re.split(r"^:{5,}\s*$", text, flags=re.MULTILINE)
    benzene = next(
        (sections[i + 1] for i, s in enumerate(sections[:-1]) if s.strip() == "DipolarCouplings for benzene"), None
    )
    if benzene is None:
        raise ValueError("no benzene section")
    rows: list[dict[str, str]] = []
    run = ""
    for raw in benzene.splitlines():
        line = raw.strip()
        if not line or line.startswith("mol %"):
            continue
        if line.startswith("Run "):
            run = line.split()[1]
            continue
        sample, *tokens = line.split()
        if len(tokens) != 3:
            raise ValueError(f"expected three couplings in {line!r}")
        mixed = sample in MIXED
        if not mixed:
            float(sample)  # a concentration in mol %
        parts = MIXED[sample].split("/") if mixed else [sample]
        co_solutes = "tfb/tcb/tbb " + "/".join(parts[1:]) if mixed else ""
        for name, token in zip(("D12", "D13", "D14"), tokens, strict=True):
            value, sigma = _value(token)
            a, b, kind = PAIRS[name]
            rows.append(
                {
                    "run": run,
                    "sample": sample,
                    "benzene_mol_percent": parts[0],
                    "co_solutes_mol_percent": co_solutes,
                    "coupling": name,
                    "class": kind,
                    "spin_a": a,
                    "spin_b": b,
                    "D_token": token,
                    "D_obs_Hz": value,
                    "sigma_Hz": sigma,
                }
            )
    conditions = {(r["run"], r["sample"]) for r in rows}
    if len(conditions) != EXPECTED_CONDITIONS or len(rows) != 3 * EXPECTED_CONDITIONS:
        raise ValueError(f"expected {EXPECTED_CONDITIONS} conditions, found {len(conditions)}")
    return rows


def render(rows: list[dict[str, str]]) -> str:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def source_text() -> str:
    data = SOURCE.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != SOURCE_SHA256:
        raise ValueError(f"the source file changed: SHA-256 {digest}, expected {SOURCE_SHA256}")
    return data.decode("ascii")


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    ns = parser.parse_args()
    text = render(parse(source_text()))
    if ns.write:
        OUTPUT.write_text(text, encoding="utf-8")
        print(f"wrote {OUTPUT.relative_to(ROOT)}")
        return 0
    if OUTPUT.read_text(encoding="utf-8") != text:
        print(f"{OUTPUT.relative_to(ROOT)} is not current: run --write", file=sys.stderr)
        return 1
    print(f"ok  {OUTPUT.relative_to(ROOT)} matches the source")
    return 0


if __name__ == "__main__":
    sys.exit(main())
