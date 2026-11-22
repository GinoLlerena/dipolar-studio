"""Phase 2 V1.5a gates, frozen before the V1.5 implementation (docs/phase2/v1.5-plan.md).

Every expectation here is written from the plan, the V1.5a ledger
(docs/phase2/verification/gates.md) and V0.3 §7–§8, not from the code it will check.

The report workflow (``tools/validation/verification.py``) is V1.5b's and the release-trigger
guard is V1.5c's. Until they land, their gates are strict xfails: a gate that starts passing
fails the suite (XPASS), so its marker has to be removed in the commit that makes it pass.
"""

from __future__ import annotations

import importlib
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "validation"))


def _verification() -> Any:
    return importlib.import_module("verification")


V15B = pytest.mark.xfail(strict=True, raises=(ModuleNotFoundError, AttributeError, FileNotFoundError), reason="V1.5b")
V15C = pytest.mark.xfail(strict=True, raises=AssertionError, reason="V1.5c lands the release-trigger guard")


def _t(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%MZ").replace(tzinfo=UTC)


# ------------------------------------------------------------- the four-value field (decision 4)
VALUES = ("pending", "synthetic-only", "experimentally supported", "unresolved failure")

#: V0.3 §7 dataset label → (verification value, annotation). Decision 4A.
CROSSWALK = {
    "pending": ("pending", None),
    "partially supported": ("pending", None),
    "experimentally supported": ("experimentally supported", None),
    "unresolved failure": ("unresolved failure", None),
    "explained discrepancy": ("unresolved failure", "explained, reviewed"),
}


@V15B
def test_the_verification_values_are_exactly_four() -> None:
    assert tuple(_verification().VERIFICATION_VALUES) == VALUES


@V15B
@pytest.mark.parametrize(("label", "expected"), sorted(CROSSWALK.items()))
def test_the_crosswalk_maps_every_v03_label(label: str, expected: tuple[str, str | None]) -> None:
    assert tuple(_verification().crosswalk(label)) == expected


@V15B
@pytest.mark.parametrize("label", ["", "supported", "Pending", "synthetic-only", "explained"])
def test_the_crosswalk_refuses_anything_else(label: str) -> None:
    with pytest.raises(ValueError):
        _verification().crosswalk(label)


# --------------------------------------------------------------- the five pages (plan, A2)
PAGES = {
    "benzene.md": "pending",
    "ortho-dichlorobenzene.md": "pending",
    "biphenyl-synthetic.md": "synthetic-only",
    "biphenyl-8cb.md": "pending",
    "dichlorobenzene-synthetic.md": "synthetic-only",
}
FIELD = re.compile(r"^\*\*Verification:?\*\*:?\s*`([^`]+)`", re.MULTILINE)


@V15B
@pytest.mark.parametrize(("page", "expected"), sorted(PAGES.items()))
def test_every_page_carries_exactly_one_verification_field(page: str, expected: str) -> None:
    """Before any experimental comparison: both V0 datasets are pending (P-2: no signed
    spot-check yet), 8CB is pending (AP-DPD), the synthetic pages are synthetic-only."""
    text = (ROOT / "docs" / "phase2" / "verification" / page).read_text(encoding="utf-8")
    found = FIELD.findall(text)
    assert found == [expected], found
    assert _verification().check_page(text) == []


@V15B
def test_a_page_without_a_valid_field_is_refused() -> None:
    v = _verification()
    assert v.check_page("# benzene\n\nNo field here.\n")
    assert v.check_page("**Verification:** `partially supported`\n")
    assert v.check_page("**Verification:** `pending`\n\n**Verification:** `pending`\n")


# ---------------------------------------------------------- the first-fit chronology (A1, §3)
DECISIONS = {str(k): _t("2026-11-21T14:59Z") for k in (*range(1, 12), "5a")}
AMENDMENTS = _t("2026-11-21T15:32Z")


@V15B
def test_the_freeze_holds_when_everything_precedes_the_first_fit() -> None:
    v = _verification()
    subs = [("benzene", _t("2026-11-25T10:00Z"))]
    assert v.freeze_ok(DECISIONS, AMENDMENTS, subs) is True
    assert v.freeze_ok(DECISIONS, AMENDMENTS, []) is True  # no fit yet


@V15B
def test_an_open_decision_blocks_the_freeze() -> None:
    assert _verification().freeze_ok({**DECISIONS, "5a": None}, AMENDMENTS, []) is False


@V15B
def test_a_fit_during_the_freeze_breaks_it() -> None:
    """Approval must be strictly before the first submission; equality is not before."""
    v = _verification()
    assert v.freeze_ok(DECISIONS, AMENDMENTS, [("benzene", _t("2026-11-21T15:00Z"))]) is False
    assert v.freeze_ok(DECISIONS, AMENDMENTS, [("benzene", AMENDMENTS)]) is False


@V15B
def test_the_first_fit_is_the_earliest_across_datasets_and_runners() -> None:
    """Exposure from the other dataset counts (V0.3 §8: any V1 experimental result)."""
    v = _verification()
    subs = [("ortho-dichlorobenzene", _t("2026-11-26T09:00Z")), ("benzene", _t("2026-11-21T15:10Z"))]
    assert v.freeze_ok(DECISIONS, AMENDMENTS, subs) is False


@V15B
@pytest.mark.parametrize(
    ("made", "first_submission", "first_access", "expected"),
    [
        ("2026-11-24T00:00Z", "2026-11-25T00:00Z", None, "pre-fit"),
        ("2026-11-24T00:00Z", None, None, "pre-fit"),
        # From the first submission on, an amendment cannot satisfy the freeze. It is not post hoc
        # only if the ledger establishes that it preceded every result access.
        ("2026-11-25T00:00Z", "2026-11-25T00:00Z", "2026-11-25T06:00Z", "after-submission"),
        ("2026-11-25T03:00Z", "2026-11-25T00:00Z", "2026-11-25T06:00Z", "after-submission"),
        ("2026-11-25T06:00Z", "2026-11-25T00:00Z", "2026-11-25T06:00Z", "post hoc"),
        ("2026-11-26T00:00Z", "2026-11-25T00:00Z", "2026-11-25T06:00Z", "post hoc"),
        # A submission with no recorded access time is ambiguous: treated as post hoc.
        ("2026-11-25T03:00Z", "2026-11-25T00:00Z", "unknown", "post hoc"),
    ],
)
def test_an_amendment_is_classified_by_the_chronology(
    made: str, first_submission: str | None, first_access: str | None, expected: str
) -> None:
    v = _verification()
    access: datetime | str | None = first_access if first_access in (None, "unknown") else _t(str(first_access))
    sub = None if first_submission is None else _t(first_submission)
    assert v.classify_amendment(_t(made), sub, access) == expected


# ------------------------------------------------------ the release-trigger guard (B10, V1.5c)
def _github_filter(pattern: str) -> re.Pattern[str]:
    """GitHub's filter-pattern syntax: * (no /), ** (anything), ? and + after a character,
    [..] classes. Written from the Actions documentation, not from the workflow."""
    out, i = "", 0
    while i < len(pattern):
        ch = pattern[i]
        if pattern.startswith("**", i):
            out += ".*"
            i += 2
            continue
        if ch == "*":
            out += "[^/]*"
        elif ch in "?+":
            out += ch
        elif ch == "[":
            j = pattern.index("]", i)
            out += pattern[i : j + 1]
            i = j
        else:
            out += re.escape(ch)
        i += 1
    return re.compile(out + r"\Z")


def _release_tags() -> list[str]:
    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8"))
    trigger = workflow.get("on", workflow.get(True))  # YAML 1.1 reads a bare `on` as True
    tags: list[str] = trigger["push"]["tags"]
    return tags


def _triggers(tag: str) -> bool:
    patterns = _release_tags()
    hit = False
    for p in patterns:
        if p.startswith("!"):
            if _github_filter(p[1:]).match(tag):
                hit = False
        elif _github_filter(p).match(tag):
            hit = True
    return hit


def test_the_filter_reader_follows_github_syntax() -> None:
    assert _github_filter("v*").match("v1.4-browser")
    assert not _github_filter("v*").match("v1/x")
    assert _github_filter("v[0-9]+.[0-9]+.[0-9]+").match("v0.10.2")
    assert not _github_filter("v[0-9]+.[0-9]+.[0-9]+").match("v0.10.2b1")


@pytest.mark.parametrize("tag", ["v0.1.0b1", "v0.2.0b1", "v0.2.0b2", "v0.2.0a1", "v0.2.0rc1", "v1.0.0", "v0.10.12"])
def test_package_tags_trigger_the_release(tag: str) -> None:
    assert _triggers(tag)


@V15C
@pytest.mark.parametrize(
    "tag",
    [
        "v1.4-browser",
        "v1.5-verification",
        "v0.3-preregistration",
        "v0.1-selection",
        "v1.0",
        "v0.2.0-b1",
        "v0.2.0b",
        "vx.y.z",
        "v0.2.0b1-extra",
    ],
)
def test_milestone_and_malformed_tags_do_not_trigger_the_release(tag: str) -> None:
    assert not _triggers(tag)
