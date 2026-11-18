"""The Phase 2 V0 corpus (V0.2): the benzene dataset of Taggar et al. (2006) and the rules that
keep third-party data out of what ships.

The benzene tests skip if the dataset has been removed (datasets/README.md). The local-only
ortho-dichlorobenzene transcription is never in the repository: a test checks that git ignores it.
"""

from __future__ import annotations

import csv
import hashlib
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BENZENE = ROOT / "datasets" / "benzene-zli1132-taggar2006"
sys.path.insert(0, str(ROOT / "tools" / "datasets"))

needs_benzene = pytest.mark.skipif(not BENZENE.exists(), reason="the third-party benzene dataset is not present")


@needs_benzene
def test_the_dataset_is_complete_when_present() -> None:
    """Skip only when the whole directory is removed: a partial removal is an error (round 71b)."""
    for name in ("README.md", "couplings.csv", "source/jp052592j_si_001.txt"):
        assert (BENZENE / name).is_file(), f"{name} is missing from {BENZENE.name}"


def _rows() -> list[dict[str, str]]:
    with (BENZENE / "couplings.csv").open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


@needs_benzene
def test_the_source_is_the_published_file() -> None:
    import taggar2006

    data = (BENZENE / "source" / "jp052592j_si_001.txt").read_bytes()
    assert hashlib.sha256(data).hexdigest() == taggar2006.SOURCE_SHA256
    assert len(data) == 2115


@needs_benzene
def test_the_csv_is_exactly_what_the_parser_produces() -> None:
    import taggar2006

    expected = taggar2006.render(taggar2006.parse(taggar2006.source_text()))
    assert (BENZENE / "couplings.csv").read_text(encoding="utf-8") == expected


@needs_benzene
def test_fifteen_conditions_of_three_couplings() -> None:
    rows = _rows()
    assert len(rows) == 45
    conditions: dict[tuple[str, str], list[str]] = {}
    for row in rows:
        conditions.setdefault((row["run"], row["sample"]), []).append(row["coupling"])
    assert len(conditions) == 15
    assert all(sorted(c) == ["D12", "D13", "D14"] for c in conditions.values())
    assert sum(1 for run, _ in conditions if run == "1") == 7
    assert sum(1 for run, _ in conditions if run == "2") == 8


@needs_benzene
def test_each_token_reads_as_value_and_last_digit_uncertainty() -> None:
    for row in _rows():
        value, error = row["D_token"].rstrip(")").split("(")
        decimals = len(value.split(".")[1])
        assert row["D_obs_Hz"] == value
        assert Decimal(row["sigma_Hz"]) == Decimal(int(error)).scaleb(-decimals)
        assert Decimal(row["sigma_Hz"]) > 0


@needs_benzene
def test_the_pairs_are_one_per_d6h_orbit() -> None:
    pairs = {(row["coupling"], row["class"], row["spin_a"], row["spin_b"]) for row in _rows()}
    assert pairs == {("D12", "ortho", "H1", "H2"), ("D13", "meta", "H1", "H3"), ("D14", "para", "H1", "H4")}


@needs_benzene
def test_a_changed_token_is_refused() -> None:
    """A token that loses its uncertainty is refused; the token is taken from the source itself."""
    import re

    import taggar2006

    text = taggar2006.source_text()
    token = re.search(r"-?\d+\.\d+\(\d+\)", text.split("DipolarCouplings for benzene")[1])
    assert token is not None
    with pytest.raises(ValueError):
        taggar2006.parse(text.replace(token.group(0), token.group(0).split("(")[0], 1))


@needs_benzene
def test_the_csv_agrees_with_an_independent_reading_of_the_source() -> None:
    """A second, independent reading of the SI (whole-line regular expressions, keyed by run,
    sample and published column) must give the same 45 tokens as the CSV. A parser that swapped
    two columns or two samples would pass the semantic tests above but not this one."""
    import re

    text = (BENZENE / "source" / "jp052592j_si_001.txt").read_text(encoding="ascii")
    benzene = text.split("DipolarCouplings for benzene")[1].split("DipolarCouplings")[0]
    expected: dict[tuple[str, str, str], str] = {}
    run = ""
    for line in benzene.splitlines():
        heading = re.fullmatch(r"\s*Run (\d)\s*", line)
        if heading:
            run = heading.group(1)
            continue
        row = re.fullmatch(r"\s*(\S+)\s+(-\d+\.\d+\(\d+\))\s+(-\d+\.\d+\(\d+\))\s+(-\d+\.\d+\(\d+\))\s*", line)
        if row:
            for column, token in zip(("D12", "D13", "D14"), row.groups()[1:], strict=True):
                expected[(run, row.group(1), column)] = token
    got = {(r["run"], r["sample"], r["coupling"]): r["D_token"] for r in _rows()}
    assert len(expected) == 45 and got == expected


@needs_benzene
def test_the_mixed_compositions_are_the_papers_footnotes() -> None:
    """Taggar et al., Tables 1–2 footnotes (mol % benzene / tfb / tcb / tbb)."""
    footnotes = {
        "mix1": ("3.65", "tfb/tcb/tbb 2.70/4.29/2.77"),
        "mix2.1": ("2.129", "tfb/tcb/tbb 0.000/1.984/0.000"),
        "mix2.2": ("1.748", "tfb/tcb/tbb 1.669/0.885/0.510"),
        "mix2.3": ("2.846", "tfb/tcb/tbb 0.000/1.060/0.000"),
    }
    for row in _rows():
        if row["sample"] in footnotes:
            assert (row["benzene_mol_percent"], row["co_solutes_mol_percent"]) == footnotes[row["sample"]]
        else:
            assert row["benzene_mol_percent"] == row["sample"] and row["co_solutes_mol_percent"] == ""
    assert {r["sample"] for r in _rows()} >= set(footnotes)


def _in_git_checkout() -> bool:
    try:
        out = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=ROOT, capture_output=True, text=True)
    except OSError:
        return False
    return out.returncode == 0 and out.stdout.strip() == "true"


needs_git = pytest.mark.skipif(not _in_git_checkout(), reason="not a git checkout")


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


@needs_git
@needs_benzene
def test_the_dataset_stays_out_of_source_archives() -> None:
    files = sorted(p.relative_to(ROOT).as_posix() for p in BENZENE.rglob("*") if p.is_file())
    out = _git("check-attr", "export-ignore", "--", *files)
    assert out.returncode == 0, out.stderr
    values = [line.rsplit(": ", 1)[1] for line in out.stdout.splitlines()]
    assert len(values) == len(files) and all(v == "set" for v in values), out.stdout


@needs_git
def test_local_only_data_are_ignored_by_the_repository_rules() -> None:
    """The ortho-dichlorobenzene transcription (© ISMAR) lives in datasets-local/, never in git.
    The committed .gitignore rule must ignore it (a CSV and a Markdown file alike), not some
    unrelated pattern, and nothing under it may be tracked."""
    for probe in (
        "datasets-local/odcb-chandrakumar1993/couplings.csv",
        "datasets-local/odcb-chandrakumar1993/README.md",
    ):
        out = _git("check-ignore", "-v", "--no-index", probe)
        assert out.returncode == 0, f"{probe} is not ignored by git"
        # "<source>:<line>:<pattern>\t<path>": the matching rule must be the root .gitignore's
        # directory rule itself, not any pattern that happens to match (round 71b: "*.*" passed).
        rule, _, path = out.stdout.rstrip("\n").partition("\t")
        source, _, rest = rule.partition(":")
        pattern = rest.partition(":")[2]
        assert (source, pattern, path) == (".gitignore", "datasets-local/", probe), out.stdout
    tracked = _git("ls-files", "datasets-local")
    assert tracked.returncode == 0 and not tracked.stdout


def test_the_comparison_finds_every_kind_of_difference(tmp_path: Path) -> None:
    """The transcription comparison (decision 4) compares printed tokens exactly, and reports
    missing rows and differing cells. The values here are synthetic."""
    import compare_transcriptions

    header = "table,T_K,coupling,D_token,sigma_token,D_Hz,sigma_Hz\n"
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    a.write_text(header + "I,100,X,-1.25,0.05,-1.25,0.05\nI,105,X,-2.50,0.05,-2.50,0.05\n", encoding="utf-8")
    b.write_text(header + "I,100,X,-1.25,0.05,-1.25,0.050\nII,110,X,-3.75,0.10,-3.75,0.10\n", encoding="utf-8")
    key = ("table", "T_K", "coupling")
    problems = compare_transcriptions.compare(a, b, key)
    assert any("only in a.csv" in p and "105" in p for p in problems)
    assert any("only in b.csv" in p and "110" in p for p in problems)
    assert any("sigma_Hz" in p and "'0.05' vs '0.050'" in p for p in problems)
    assert compare_transcriptions.compare(a, a, key) == []
    assert compare_transcriptions.compare(a, a, key, expect=3) != []  # the wrong number of keys


def test_the_comparison_refuses_malformed_files(tmp_path: Path) -> None:
    """Empty files, truncated rows and surplus fields are errors, not agreement."""
    import compare_transcriptions

    header = "table,T_K,coupling,D_token,sigma_token,D_Hz,sigma_Hz\n"
    key = ("table", "T_K", "coupling")
    empty = tmp_path / "empty.csv"
    empty.write_text("", encoding="utf-8")
    short = tmp_path / "short.csv"
    short.write_text(header + "I,100,X,-1.25\n", encoding="utf-8")
    surplus = tmp_path / "surplus.csv"
    surplus.write_text(header + "I,100,X,-1.25,0.05,-1.25,0.05,extra\n", encoding="utf-8")
    for bad in (empty, short, surplus):
        with pytest.raises(ValueError):
            compare_transcriptions.compare(bad, bad, key)


def test_the_comparison_refuses_duplicate_headers_bad_quoting_and_key_only_files(tmp_path: Path) -> None:
    """Round 71b: a duplicate column could hide a cell, an unclosed quote could swallow rows, and
    a file of key columns only compares nothing."""
    import compare_transcriptions

    key = ("table", "T_K", "coupling")
    duplicate = tmp_path / "duplicate.csv"
    duplicate.write_text("table,T_K,coupling,D_token,D_token\nI,100,X,-1.25,-9.99\n", encoding="utf-8")
    unclosed = tmp_path / "unclosed.csv"
    unclosed.write_text('table,T_K,coupling,D_token\nI,100,X,"-1.25\nI,105,X,-2.50\n', encoding="utf-8")
    keys_only = tmp_path / "keys.csv"
    keys_only.write_text("table,T_K,coupling\nI,100,X\n", encoding="utf-8")
    for bad in (duplicate, unclosed, keys_only):
        with pytest.raises(ValueError):
            compare_transcriptions.compare(bad, bad, key)
    good = tmp_path / "good.csv"
    good.write_text("table,T_K,coupling,D_token\nI,100,X,-1.25\n", encoding="utf-8")
    with pytest.raises(ValueError, match="sigma_token"):
        compare_transcriptions.compare(good, good, key, required=compare_transcriptions.ODCB_COLUMNS)
