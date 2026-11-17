"""The beta's documents (beta step B4): the issue forms are valid, every relative link in the
user-facing documents resolves, the release notes match the version, and the testers' guide
quotes the frozen 8CB reference values."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
FORMS = sorted((ROOT / ".github" / "ISSUE_TEMPLATE").glob("*.yml"))
USER_DOCS = [
    ROOT / "README.md",
    *sorted((ROOT / "docs" / "user").glob("*.md")),
    *sorted((ROOT / "docs" / "beta").glob("*.md")),
    *sorted((ROOT / "docs" / "release-notes").glob("*.md")),
    ROOT / "docs" / "notebooks" / "README.md",
]
DIPIETRO = ROOT / "datasets" / "biphenyl-8CB-dipietro2013"


@pytest.mark.parametrize("path", [p for p in FORMS if p.name != "config.yml"], ids=lambda p: p.name)
def test_issue_forms_are_valid(path: Path) -> None:
    form = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert form["name"] and form["description"] and isinstance(form["body"], list)
    ids = [item["id"] for item in form["body"] if item["type"] != "markdown"]
    assert len(ids) == len(set(ids)), "field ids must be unique"
    for item in form["body"]:
        assert item["type"] in {"markdown", "input", "textarea", "dropdown", "checkboxes"}
        if item["type"] == "markdown":
            continue
        assert str(item["attributes"].get("label", "")).strip(), f"{item['id']} has no label"  # round 61
        if item["type"] == "dropdown":
            options = item["attributes"]["options"]
            assert options and len(options) == len(set(options)), item["id"]
            assert isinstance(item["attributes"].get("multiple", False), bool), item["id"]
        if "validations" in item:
            assert isinstance(item["validations"].get("required", False), bool), item["id"]


def test_the_bug_form_asks_for_the_severity_and_the_version() -> None:
    form = yaml.safe_load((ROOT / ".github" / "ISSUE_TEMPLATE" / "bug.yml").read_text(encoding="utf-8"))
    fields = {item.get("id"): item for item in form["body"]}
    assert [o.split(":")[0] for o in fields["severity"]["attributes"]["options"]] == ["S1", "S2", "S3"]
    assert fields["severity"]["validations"]["required"] and fields["version"]["validations"]["required"]


def test_the_issue_config_is_valid() -> None:
    config = yaml.safe_load((ROOT / ".github" / "ISSUE_TEMPLATE" / "config.yml").read_text(encoding="utf-8"))
    assert all(link["url"].startswith("https://") for link in config["contact_links"])


def link_targets(text: str) -> list[str]:
    """The destinations of Markdown links: inline (with or without a title, or in angle
    brackets) and reference definitions (round 61: titled and reference links were missed)."""
    targets = re.findall(r"\]\(\s*<([^>]+)>", text)  # [x](<a b.md>)
    targets += re.findall(r"\]\(\s*([^)<\s]+)(?:\s+\"[^\"]*\")?\s*\)", text)  # [x](a.md) and [x](a.md "t")
    targets += re.findall(r"^\s*\[[^\]]+\]:\s*<?([^\s>]+)>?", text, flags=re.M)  # [x]: a.md
    return targets


def test_link_targets_are_all_found() -> None:
    text = '[a](a.md) [b](b.md "title") [c](<c d.md>) [e][ref]\n\n[ref]: e.md "t"\n'
    assert sorted(link_targets(text)) == ["a.md", "b.md", "c d.md", "e.md"]


@pytest.mark.parametrize("path", USER_DOCS, ids=lambda p: str(p.relative_to(ROOT)))
def test_relative_links_resolve(path: Path) -> None:
    for target in link_targets(path.read_text(encoding="utf-8")):
        if re.match(r"[a-z]+:", target) or target.startswith("#"):
            continue  # external, or an anchor in the same page
        file = (path.parent / target.split("#", 1)[0]).resolve()
        assert file.exists(), f"{path.relative_to(ROOT)} links to a missing {target}"


def test_the_release_notes_name_this_version() -> None:
    import dipolar_app

    notes = ROOT / "docs" / "release-notes" / f"{dipolar_app.__version__}.md"
    assert notes.exists(), f"no release notes for {dipolar_app.__version__}"
    text = notes.read_text(encoding="utf-8")
    assert dipolar_app.__version__ in text.splitlines()[0]
    assert f"dipolar_app-{dipolar_app.__version__}-py3-none-any.whl" in text


@pytest.mark.skipif(not (DIPIETRO / "expected").exists(), reason="the third-party 8CB dataset is not present")
def test_the_testers_guide_quotes_the_frozen_8cb_fits() -> None:
    """The values a tester compares with are the frozen reference fits, to their printed digits."""
    expected = json.loads((DIPIETRO / "expected" / "T0.930.json").read_text(encoding="utf-8"))["expected"]
    guide = (ROOT / "docs" / "beta" / "testers.md").read_text(encoding="utf-8")
    table = dict(re.findall(r"^\| (φ|S_zz|Δ) \| ([0-9.]+)°? \|$", guide, flags=re.M))
    unweighted = expected["unweighted"]
    assert abs(float(table["φ"]) - unweighted["phi_deg"]) <= 5e-4
    assert abs(float(table["S_zz"]) - unweighted["Szz"]) <= 5e-6
    assert abs(float(table["Δ"]) - unweighted["Delta"]) <= 5e-6
    weighted = expected["weighted"]
    quoted = re.search(r"φ = ([0-9.]+)°, S_zz = ([0-9.]+), Δ = ([0-9.]+)", guide)
    assert quoted is not None
    phi, szz, delta = (float(v) for v in quoted.groups())
    assert abs(phi - weighted["phi_deg"]) <= 5e-4
    assert abs(szz - weighted["Szz"]) <= 5e-6 and abs(delta - weighted["Delta"]) <= 5e-6


@pytest.mark.skipif(not (DIPIETRO / "couplings.csv").exists(), reason="the third-party 8CB dataset is not present")
def test_the_testers_guide_pairs_are_the_datasets() -> None:
    """The guide's thesis-label → pair table is the repository's mapping (round 61: a changed pair
    passed every test)."""
    import csv

    with (DIPIETRO / "couplings.csv").open(encoding="utf-8") as handle:
        mapping = {r["thesis_label"]: (r["spin_a"], r["spin_b"]) for r in csv.DictReader(handle)}
    guide = (ROOT / "docs" / "beta" / "testers.md").read_text(encoding="utf-8")
    rows = re.findall(r"^\| (D[^|]+?) \| `([^`]+)` \| `([^`]+)` \|$", guide, flags=re.M)
    table = {label.replace("′", "'"): (a, b) for label, a, b in rows}
    assert table == mapping


def test_third_party_data_stay_out_of_source_archives() -> None:
    """GitHub attaches the tag's source archives to a release: the 8CB dataset is export-ignored
    (round 61), so no archive carries its couplings."""
    import subprocess

    files = sorted(p.relative_to(ROOT).as_posix() for p in DIPIETRO.rglob("*") if p.is_file())
    if not files:
        pytest.skip("the third-party 8CB dataset is not present")
    try:
        out = subprocess.run(
            ["git", "check-attr", "export-ignore", "--", *files], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout")
    values = [line.rsplit(": ", 1)[1] for line in out.splitlines()]
    assert values and all(v == "set" for v in values), out
