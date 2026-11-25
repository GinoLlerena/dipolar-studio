"""Phase 2 V1.5c gates: the benzene guide and the ``v0.2.0b1`` candidate (docs/phase2/v1.5-plan.md,
V1.5c row and "Pre-release and commands"; ledger decisions 6, 8, 9 and 10, §8).

They are frozen before the V1.5c implementation. A gate that the candidate does not meet yet is a
strict xfail (``_v15c``); the implementation commit removes each marker, so an unexpected pass
or a later regression fails. The release-trigger gate itself is frozen in
``tests/test_v15_gates.py`` (B10).

What is checked:

- **Versions:** both packages, both ``__version__`` values and the lockfile name ``0.2.0b1``,
  and ``dipolar --version`` names both packages and the contract.
- **Release notes:** the version, both wheels, the contract, D-1 (fresh directories,
  export/import), the fixed-geometry workflow, each report page's verification status, the
  holdout status, the credits, and links pinned to the tag.
- **The historical beta guide** stays pinned to ``v0.1.0b1`` (decision 7A).
- **The benzene guide** (``docs/phase2/reproduce-benzene.md``): the SI hash, the geometry and
  symmetry provenance, the copy probe, the full roster, the orbit mapping, the precision rule,
  the contract and wheel versions, the ``run.get`` snippet, eligibility, and disclosure. It
  quotes no coupling from the corpus.
- **The worksheet:** blank, the closed record fields, no personal fields.
- **The workflows:** the preserved release checks, a literal CLI/package version check, the wheel
  manifest check, and a synthetic D6h rehearsal on the installed wheels from outside the
  checkout, in both the release workflow and the CI packaged job.
- **Exclusion:** the source archive and the wheels carry no third-party or local data.
"""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import io
import json
import re
import subprocess
import sys
import tarfile
import tomllib
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "validation"))

import verification  # noqa: E402

VERSION = "0.2.0b1"
TAG = f"v{VERSION}"
REPO = "https://github.com/GinoLlerena/dipolar-studio"
PREREG = json.loads((ROOT / "docs" / "phase2" / "v0.3-preregistration.json").read_text(encoding="utf-8"))
BENZENE = PREREG["datasets"]["benzene-taggar2006"]
SOURCES = json.loads((ROOT / "docs" / "phase2" / "v0-sources.json").read_text(encoding="utf-8"))
CORPUS = ROOT / "datasets" / "benzene-zli1132-taggar2006" / "couplings.csv"
GUIDE = ROOT / "docs" / "phase2" / "reproduce-benzene.md"
WORKSHEET = ROOT / "docs" / "phase2" / "reproduce-benzene-worksheet.md"
NOTES = ROOT / "docs" / "release-notes" / f"{VERSION}.md"
WHEELS = (f"dipolar_core-{VERSION}-py3-none-any.whl", f"dipolar_app-{VERSION}-py3-none-any.whl")
#: The 0.1.0b1 release notes as tagged: the historical release text is not edited (decision 7A).
NOTES_0_1_SHA256 = "7f5f169654962d63113e7914f4058011722bccd93a85dea7c43da1aede0b6bd3"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    """The body under the first heading that starts with ``heading``, up to the next heading of
    the same or a higher level."""
    m = re.search(rf"^(#+) {re.escape(heading)}.*$", text, flags=re.M)
    assert m is not None, f"no section {heading!r}"
    level = len(m.group(1))
    rest = text[m.end() :]
    end = re.search(rf"^#{{1,{level}}} ", rest, flags=re.M)
    return rest[: end.start()] if end else rest


def _links(text: str) -> list[str]:
    return re.findall(r"\]\(([^)\s]+)\)", text)


def _cli_version() -> str:
    from dipolar_app.cli import _version

    return _version()


def _roster() -> list[tuple[str, str]]:
    """The benzene conditions, as (run, sample), in the corpus's order."""
    with CORPUS.open(encoding="utf-8") as handle:
        seen = dict.fromkeys((r["run"], r["sample"]) for r in csv.DictReader(handle))
    return list(seen)


def _module(path: Path) -> ModuleType:
    if not path.exists():
        pytest.fail(f"{path.relative_to(ROOT)} does not exist")
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ================================================================================== versions
def _pyproject_version(package: str) -> str:
    return str(tomllib.loads(_text(ROOT / "packages" / package / "pyproject.toml"))["project"]["version"])


def _module_version(package: str) -> str:
    source = _text(ROOT / "packages" / package / "src" / package.replace("-", "_") / "__init__.py")
    m = re.search(r'^__version__ = "([^"]+)"$', source, flags=re.M)
    assert m is not None
    return m.group(1)


def _lock_version(package: str) -> str:
    lock = tomllib.loads(_text(ROOT / "uv.lock"))
    (entry,) = [p for p in lock["package"] if p["name"] == package]
    return str(entry["version"])


def test_both_packages_the_lockfile_and_the_modules_are_the_candidate() -> None:
    for package in ("dipolar-core", "dipolar-app"):
        assert _pyproject_version(package) == VERSION
        assert _module_version(package) == VERSION
        assert _lock_version(package) == VERSION


def test_the_cli_names_both_packages_and_the_contract() -> None:
    """``dipolar --version``: both package versions and the contract, literally (bug reports and
    the guide's version check depend on it)."""
    import dipolar_app
    import dipolar_core
    from dipolar_app.registry import CONTRACT_VERSION

    expected = (
        f"dipolar {dipolar_app.__version__} (dipolar-core {dipolar_core.__version__}, contract {CONTRACT_VERSION})"
    )
    assert _cli_version() == expected


# ============================================================================= release notes
def test_the_release_notes_state_what_the_plan_requires() -> None:
    from dipolar_app.registry import CONTRACT_VERSION

    text = _text(NOTES)
    assert text.splitlines()[0] == f"# Dipolar Studio {VERSION} (beta)"
    install = _section(text, "Install")
    assert f"pip install {WHEELS[0]} {WHEELS[1]}" in install
    assert f"contract {CONTRACT_VERSION}" in text
    upgrade = _section(text, "Projects from 0.1")
    for phrase in ("written by Dipolar Studio 0.1", "project.export", "new directory", "not changed"):
        assert phrase in upgrade, phrase
    assert "fixed geometry" in _section(text, "What is new").lower()
    status = _section(text, "Verification status")
    assert "no independent holdout" in status
    assert "outside reproduction" in status.lower()
    assert "Gino Llerena and Marco Idrogo" in text and "Dr. Jaime Avalos" in text
    assert re.search(r"sole author of Dipolar Studio", text)


def test_the_release_notes_print_each_pages_verification_field() -> None:
    """Each report page's current field, as the page prints it (decision 4): the notes may not
    claim more than the pages."""
    status = _section(_text(NOTES), "Verification status")
    pages = sorted((ROOT / "docs" / "phase2" / "verification").glob("*.md"))
    pages = [p for p in pages if p.name != "gates.md"]
    assert len(pages) == 5
    for page in pages:
        field = re.search(r"^\*\*Verification:\*\* `([^`]+)`$", _text(page), flags=re.M)
        assert field is not None, page.name
        url = f"{REPO}/blob/{TAG}/docs/phase2/verification/{page.name}"
        rows = [line for line in status.splitlines() if url in line]
        assert len(rows) == 1, page.name
        assert f"`{field.group(1)}`" in rows[0], page.name


def test_the_release_notes_links_are_absolute_and_pinned_to_the_tag() -> None:
    """The notes are the GitHub release text (release.yml): a relative link breaks there, and a
    link to ``main`` would follow later changes."""
    links = _links(_text(NOTES))
    assert links
    assert f"{REPO}/blob/{TAG}/docs/phase2/reproduce-benzene.md" in links
    for link in links:
        assert link.startswith("https://"), link
        if link.startswith(REPO + "/blob/") or link.startswith(REPO + "/tree/"):
            rest = link.split("/", 7)[7]  # after .../blob/<ref>/
            ref, path = link.split("/")[6], rest
            assert ref == TAG, link
            assert (ROOT / path.split("#")[0]).exists(), link


def test_the_install_instructions_name_the_candidate_wheels() -> None:
    for path in (ROOT / "README.md", ROOT / "docs" / "user" / "getting-started.md"):
        assert f"pip install {WHEELS[0]} {WHEELS[1]}" in _text(path), path.name


# ======================================================== the historical beta guide (decision 7A)
def test_the_0_1_release_notes_are_unchanged() -> None:
    notes = (ROOT / "docs" / "release-notes" / "0.1.0b1.md").read_bytes()
    assert hashlib.sha256(notes).hexdigest() == NOTES_0_1_SHA256


def test_the_testers_guide_stays_pinned_to_0_1() -> None:
    """The 8CB testers use ``v0.1.0b1`` and its guide: every link into the repository is pinned
    to that tag, so updating ``main`` for 0.2 does not change what a 0.1 tester reads."""
    text = _text(ROOT / "docs" / "beta" / "testers.md")
    assert text.splitlines()[0].startswith("# Dipolar Studio 0.1.0b1")
    assert "dipolar 0.1.0b1" in text
    for link in _links(text):
        if link.startswith("#"):
            continue
        assert link.startswith(("https://", "http://")), link
        if link.startswith(REPO + "/blob/") or link.startswith(REPO + "/tree/"):
            assert link.split("/")[6] == "v0.1.0b1", link


# ========================================================================= the benzene guide
def _guide() -> str:
    if not GUIDE.exists():
        pytest.fail("docs/phase2/reproduce-benzene.md does not exist")
    return _text(GUIDE)


def test_the_guide_checks_the_source_bytes() -> None:
    """Decision 10: the original SI bytes, checked by SHA-256 before anything is parsed."""
    (si,) = [s for s in SOURCES["obtained"] if s["local_filename"] == "jp052592j_si_001.txt"]
    text = _guide()
    assert f"`{si['sha256']}`" in text
    assert f"{si['byte_size']} bytes" in text
    assert si["landing_page_url"] in _links(text)
    assert "https://doi.org/10.1021/jp052592j" in _links(text)
    assert "shasum -a 256" in text and "Get-FileHash" in text
    mismatch = _section(text, "If the hash does not match")
    assert "stop" in mismatch.lower() and "do not parse or fit" in mismatch.lower()


def test_the_guide_gives_the_frozen_geometry_and_symmetry() -> None:
    text = _guide()
    g = PREREG["geometry"]
    assert f"r_e(CC) = {g['r_cc_angstrom']} Å" in text
    assert f"r_e(CH) = {g['r_ch_angstrom']} Å" in text
    angles = {h: int(d) for h, d in re.findall(r"^\| `(H\d)` \| `C\d` \| (\d+)° \|$", text, flags=re.M)}
    assert angles == BENZENE["ring_positions"]
    assert "D6h" in text and "normal to the ring" in text
    axes = dict(re.findall(r"^\| (x′|y′|z′) \| `([-0-9. ]+)` \|$", text, flags=re.M))
    assert [[float(v) for v in axes[k].split()] for k in ("x′", "y′", "z′")] == BENZENE["frame_map_matrix"]


def test_the_guide_states_the_copy_probe() -> None:
    probe = _section(_guide(), "What counts as copying")
    for phrase in (
        "datasets/benzene-zli1132-taggar2006/",
        "XYZ file from the repository",
        "JSON-to-XYZ",
        "prepared CSV",
        "project file",
        "symmetry declaration",
    ):
        assert phrase in probe, phrase


def test_the_guide_lists_the_full_roster_and_the_orbits() -> None:
    text = _guide()
    rows = re.findall(r"^\| ([12]) \| `([^`]+)` \| +\|", _section(text, "The 15 conditions"), flags=re.M)
    assert rows == _roster()
    assert len(rows) == BENZENE["conditions"] == 15
    orbits = {
        d: [a, b]
        for d, _, a, b in re.findall(r"^\| (D1[234]) \| (ortho|meta|para) \| `(H\d)` \| `(H\d)` \|$", text, flags=re.M)
    }
    assert orbits == BENZENE["orbits"]
    assert "spin_a,spin_b,D_obs_Hz,sigma_Hz" in text
    assert "a fresh project directory for each condition" in text


def test_the_guides_token_example_is_decoded_right_and_is_not_from_the_corpus() -> None:
    """σ is the printed uncertainty in the last printed digits. The example is invented: the guide
    quotes no corpus value (a prepared value counts as copying)."""
    text = _guide()
    example = re.search(r"`(-?\d+\.(\d+))\((\d+)\)` means D = (−?\d+\.\d+) Hz and σ = (\d+\.\d+) Hz", text)
    assert example is not None
    value, decimals, digits, d, sigma = example.groups()
    assert d.replace("−", "-") == value
    assert float(sigma) == int(digits) * 10 ** -len(decimals)
    with CORPUS.open(encoding="utf-8") as handle:
        corpus = list(csv.DictReader(handle))
    for row in corpus:
        assert row["D_token"] not in text
        assert row["D_obs_Hz"].lstrip("-") not in text


def test_the_guide_states_the_precision_rule() -> None:
    rule = _section(_guide(), "Coordinate precision")
    for phrase in ("12 or more decimal places", "8 to 11 decimal places", "fewer than 8", "1e-8", "input XYZ frame"):
        assert phrase in rule, phrase


def test_the_guide_names_the_release_and_its_versions() -> None:
    from dipolar_app.registry import CONTRACT_VERSION

    text = _guide()
    assert f"`dipolar {VERSION} (dipolar-core {VERSION}, contract {CONTRACT_VERSION})`" in text
    for wheel in WHEELS:
        assert wheel in text
    assert f"{REPO}/releases/tag/{TAG}" in _links(text)
    assert "fresh Python 3.12" in text


def test_the_guide_saves_run_get_and_reads_szz() -> None:
    (block,) = [b for b in re.findall(r"```python\n(.*?)```", _guide(), flags=re.S) if "Studio.connect" in b]
    code = [line for line in block.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    assert re.fullmatch(r'PROJECT_DIR = "[^"]+"(  #.*)?', code[0]), code[0]
    assert re.fullmatch(r'OUT = "[^"]+"(  #.*)?', code[1]), code[1]
    for needle in ('"run.get"', '"Szz"', '["rank"]["verified"]', '"estimated"', "json.dumps"):
        assert needle in block, needle


def test_the_guide_states_eligibility_order_and_disclosure() -> None:
    text = _guide()
    who = _section(text, "Who can take part")
    for phrase in ("1998", "advisor", "Dipolar Studio contributors", "advance access"):
        assert phrase in who, phrase
    compare = _section(text, "Step 4")
    assert "spot-check" in compare and "published counts" in compare
    assert f"{REPO}/blob/main/docs/phase2/verification/benzene.md" in _links(compare)
    keep = _section(text, "What stays on your computer")
    for phrase in ("targets", "margins", "signed differences", "screenshots", "raw reports"):
        assert phrase in keep, phrase
    assert "opaque participant ID" in text
    assert "do not post" in text.lower()


def test_the_guides_relative_links_resolve_and_link_the_worksheet() -> None:
    links = _links(_guide())
    assert "reproduce-benzene-worksheet.md" in links
    for link in links:
        if link.startswith(("https://", "http://", "#")):
            continue
        assert (GUIDE.parent / link.split("#")[0]).resolve().exists(), link


# ============================================================================== the worksheet
def _worksheet() -> str:
    if not WORKSHEET.exists():
        pytest.fail("docs/phase2/reproduce-benzene-worksheet.md does not exist")
    return _text(WORKSHEET)


def _rows(text: str) -> list[list[str]]:
    return [
        [c.strip() for c in line.strip()[1:-1].split("|")]
        for line in text.splitlines()
        if line.startswith("|") and not re.fullmatch(r"\|[-| :]+\|", line.strip())
    ]


def test_the_worksheet_carries_the_closed_record_fields() -> None:
    text = _worksheet()
    keyed = {r[1] for r in _rows(text) if len(r) >= 3}
    for key in sorted(verification._RECORD_FIELDS - {"conditions", "counts"} | verification._COUNT_FIELDS):
        assert f"`{key}`" in keyed, key  # a row of its own, not only a mention (gate correction)
    for heading in (
        "Source",
        "Release",
        "Conditions",
        "Geometry",
        "Symmetry",
        "Observables and σ",
        "Numerical match",
        "Comparison counts",
    ):
        assert re.search(rf"^## {heading}", text, flags=re.M), heading


def test_the_worksheet_is_blank_and_asks_for_nothing_personal() -> None:
    text = _worksheet()
    rows = _rows(text)
    keyed = [r for r in rows if len(r) >= 3 and re.fullmatch(r"`[a-z_0-9]+`", r[1])]
    assert keyed and all(r[-1] == "" for r in keyed)
    conditions = [r for r in _rows(_section(text, "Conditions")) if r[0] in ("1", "2")]
    assert [(r[0], r[1].strip("`")) for r in conditions] == _roster()
    assert all(c == "" for r in conditions for c in r[2:])
    for r in rows:
        assert not re.search(r"(?i)\b(name|e-?mail|handle|contact|github|phone|address)\b", r[0]), r


# ================================================================================ workflows
def _steps(path: Path, job: str) -> list[dict[str, Any]]:
    workflow = yaml.safe_load(_text(path))
    steps: list[dict[str, Any]] = workflow["jobs"][job]["steps"]
    return steps


def _runs(path: Path, job: str) -> str:
    return "\n".join(str(s.get("run", "")) for s in _steps(path, job))


RELEASE = ROOT / ".github" / "workflows" / "release.yml"
CI = ROOT / ".github" / "workflows" / "ci.yml"


def test_the_release_workflow_keeps_its_checks() -> None:
    """The plan: keep the literal package/tag equality and release-notes checks, the
    source-archive exclusion, the installed-wheel smoke and the draft prerelease."""
    runs = _runs(RELEASE, "draft")
    for needle in (
        'grep -Fqx "version = \\"$version\\"" packages/dipolar-app/pyproject.toml',
        'grep -Fqx "version = \\"$version\\"" packages/dipolar-core/pyproject.toml',
        'test -f "docs/release-notes/$version.md"',
        "git archive --format=tar",
        "tools/package/smoke.py --guide docs/user/getting-started.md",
        "--draft $prerelease",
        'case "$VERSION" in *a*|*b*|*rc*) prerelease="--prerelease"',
    ):
        assert needle in runs, needle


def test_the_archive_check_covers_every_export_ignored_path() -> None:
    ignored = {
        line.split()[0].removesuffix("/**").removeprefix("datasets/")
        for line in _text(ROOT / ".gitattributes").splitlines()
        if line.strip() and not line.startswith("#") and "export-ignore" in line.split()[1:]
    }
    m = re.search(r'grep -qE "([^"]+)" "\$RUNNER_TEMP/source.list"', _runs(RELEASE, "draft"))
    assert m is not None
    alternatives = set(m.group(1).split("|"))
    assert ignored <= alternatives and "datasets-local/" in alternatives


def test_the_release_workflow_checks_the_installed_version_literally() -> None:
    runs = _runs(RELEASE, "draft")
    installed = 'test "$("$RUNNER_TEMP/pkg/bin/dipolar" --version)"'
    assert f'{installed} = "dipolar $VERSION (dipolar-core $VERSION, contract $contract)"' in runs


@pytest.mark.parametrize(("path", "job"), [(RELEASE, "draft"), (CI, "packaged")])
def test_the_d6h_rehearsal_runs_on_the_installed_wheels_outside_the_checkout(path: Path, job: str) -> None:
    (step,) = [s for s in _steps(path, job) if "rehearse_d6h.py" in str(s.get("run", ""))]
    run = str(step["run"])
    assert 'cd "$RUNNER_TEMP"' in run
    assert '"$RUNNER_TEMP/pkg/bin/python" -I "$GITHUB_WORKSPACE/tools/package/rehearse_d6h.py"' in run
    assert '--guide "$GITHUB_WORKSPACE/docs/phase2/reproduce-benzene.md"' in run
    assert '--prereg "$GITHUB_WORKSPACE/docs/phase2/v0.3-preregistration.json"' in run


def test_the_build_checks_every_wheels_manifest() -> None:
    assert "python3 tools/package/check_wheels.py dist/packages/*.whl" in _text(ROOT / "tools" / "package" / "build.sh")


# ================================================================================ exclusion
def test_the_source_archive_leaves_out_third_party_and_local_data() -> None:
    try:
        tar = subprocess.run(
            ["git", "archive", "--format=tar", "HEAD"], cwd=ROOT, capture_output=True, check=True
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout")
    names = tarfile.open(fileobj=io.BytesIO(tar)).getnames()
    assert names
    for name in names:
        assert not name.startswith(
            ("datasets/biphenyl-8CB-dipietro2013", "datasets/benzene-zli1132-taggar2006", "datasets-local")
        ), name


CHECK_WHEELS = ROOT / "tools" / "package" / "check_wheels.py"


@pytest.mark.parametrize(
    "name",
    [
        "datasets/benzene-zli1132-taggar2006/couplings.csv",
        "dipolar_app/datasets-local/x.json",
        "dipolar_app/static/biphenyl-8CB-dipietro2013.csv",
        "dipolar_app/data/jp052592j_si_001.txt",
        "dipolar_app/data/Taggar_targets.csv",
        "dipolar_app/data/odcb-chandrakumar1993.csv",
        "dipolar_core/__pycache__/fixed.cpython-312.pyc",
    ],
)
def test_the_wheel_check_refuses_excluded_data(name: str) -> None:
    check = _module(CHECK_WHEELS)
    clean = ["dipolar_app/__init__.py", "dipolar_app/examples/biphenyl-synthetic.json", "dipolar_app/static/index.html"]
    assert check.problems(clean) == []
    assert check.problems([*clean, name]) != []


# ============================================================ the installed-wheel rehearsal
REHEARSAL = ROOT / "tools" / "package" / "rehearse_d6h.py"


def test_the_rehearsal_geometry_follows_the_guide() -> None:
    r = _module(REHEARSAL)
    big = PREREG["geometry"]["r_cc_angstrom"] + PREREG["geometry"]["r_ch_angstrom"]
    elements, rows = r.geometry(PREREG, decimals=12)
    assert elements == ["C"] * 6 + ["H"] * 6
    h = [rows[6 + k] for k in range(6)]
    assert abs(((h[0][0] - h[1][0]) ** 2 + (h[0][1] - h[1][1]) ** 2) ** 0.5 - big) < 1e-11
    assert all(z == 0 for _, _, z in rows)
    lines = r.xyz_text(elements, rows, decimals=12).splitlines()
    assert lines[0] == "12" and len(lines) == 14
    for line in lines[2:]:
        assert all(re.fullmatch(r"-?\d+\.\d{12}", v) for v in line.split()[1:]), line


def test_the_rehearsal_match_rule_is_the_ledgers() -> None:
    r = _module(REHEARSAL)
    assert r.matches(0.1, 0.1 + 1e-8 * 0.99) and not r.matches(0.1, 0.1 + 2e-8)


def test_the_rehearsal_passes_from_outside_the_checkout(tmp_path: Path) -> None:
    """The synthetic D6h fit through ``dipolar serve`` and the guide's own ``run.get`` snippet,
    run with ``-I`` from a directory outside the checkout (the CI packaged job and the release
    workflow run it on the installed wheels)."""
    if not REHEARSAL.exists():
        pytest.fail("tools/package/rehearse_d6h.py does not exist")
    out = subprocess.run(
        [
            sys.executable,
            "-I",
            str(REHEARSAL),
            "--guide",
            str(GUIDE),
            "--prereg",
            str(ROOT / "docs" / "phase2" / "v0.3-preregistration.json"),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert out.returncode == 0, out.stdout + out.stderr
    assert "ok  synthetic D6h: S_zz recovered" in out.stdout
