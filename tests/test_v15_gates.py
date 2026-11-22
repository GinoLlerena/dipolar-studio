"""Phase 2 V1.5a gates, frozen before the V1.5 implementation (docs/phase2/v1.5-plan.md).

Every expectation here is written from the plan, the V1.5a ledger
(docs/phase2/verification/gates.md) and V0.3 §6–§8, not from the code it will check. Rounds 81
and 82 (docs/validation/round81-v1.5a-gates.md) strengthened them.

**Pending implementations.** The report workflow (``tools/validation/verification.py``) is V1.5b's.
While that module's file does not exist, its gates xfail through ``_verification()``, and
through that alone. Once the file exists, every gate runs, the page gates included, and any
exception from the implementation fails, an import error included (round 82). The
release-trigger guard is V1.5c's: while ``release.yml`` keeps exactly the original ``v*``
trigger, the workflow gate xfails. Once it changes, the whole trigger must be the approved one.
``pytest -rx`` lists what is still pending, and the exit matrix requires none.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import math
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import yaml
from dipolar_core import fixed, symmetry
from dipolar_core.nuclides import dipolar_constant_hz_a3

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "validation"))

import prereg  # noqa: E402
import prereg_labels as pl  # noqa: E402

PREREG = json.loads((ROOT / "docs" / "phase2" / "v0.3-preregistration.json").read_text(encoding="utf-8"))
ORIGINAL_PROTOCOL = "332be1d699421d568655669a9fcaf2fc05667e195795a63913b9a67d22e48ea3"


VERIFICATION_PY = ROOT / "tools" / "validation" / "verification.py"


def _verification() -> Any:
    """The V1.5b module, or an xfail while (and only while) its file does not exist."""
    if not VERIFICATION_PY.is_file():
        pytest.xfail("V1.5b: tools/validation/verification.py is not written yet")
    return importlib.import_module("verification")


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


def test_the_verification_values_are_exactly_four() -> None:
    assert tuple(_verification().VERIFICATION_VALUES) == VALUES


@pytest.mark.parametrize(("label", "expected"), sorted(CROSSWALK.items()))
def test_the_crosswalk_maps_every_v03_label(label: str, expected: tuple[str, str | None]) -> None:
    assert tuple(_verification().crosswalk(label)) == expected


@pytest.mark.parametrize("label", ["", "supported", "Pending", "synthetic-only", "explained"])
def test_the_crosswalk_refuses_anything_else(label: str) -> None:
    with pytest.raises(ValueError):
        _verification().crosswalk(label)


def _without(d: dict[str, Any], key: str) -> dict[str, Any]:
    return {k: v for k, v in d.items() if k != key}


# --------------------------------------------------------------- the five pages (plan, A2)
PAGES = {
    "benzene.md": ("pending", "benzene-taggar2006"),
    "ortho-dichlorobenzene.md": ("pending", "odcb-chandrakumar1993"),
    "biphenyl-synthetic.md": ("synthetic-only", None),
    "biphenyl-8cb.md": ("pending", None),
    "dichlorobenzene-synthetic.md": ("synthetic-only", None),
}
#: The field, as the pages write it: a line of its own, outside any code fence.
FIELD_LINE = re.compile(r"^\*\*Verification:\*\* `([^`]+)`$")
#: The experimental pages print the V0.3 label and its counts beside the field (plan, pages).
V03_LINE = re.compile(
    r"^\*\*V0\.3 label:\*\* `([^`]+)` \(roster (\d+), compared (\d+), agreeing (\d+), "
    r"disagreeing (\d+), pending (\d+)\)$"
)
GATES_MD = ROOT / "docs" / "phase2" / "verification" / "gates.md"


def _spot_check_signed(dataset: str) -> bool:
    """A signed spot-check is recorded in the ledger as a line of its own (round 82, A3)."""
    text = GATES_MD.read_text(encoding="utf-8")
    return bool(re.search(rf"^- \*\*Spot-check receipt signed:\*\* `{re.escape(dataset)}`", text, re.MULTILINE))


def _prose_lines(text: str) -> list[str]:
    """The lines outside fenced code blocks."""
    out, fenced = [], False
    for line in text.splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
            continue
        if not fenced:
            out.append(line)
    return out


def _v03_label_for(compared: int, agreeing: int, disagreeing: int, pending: int) -> set[str]:
    """The labels V0.3 §7 allows for these counts (a disagreement's review state is not in them)."""
    if disagreeing:
        return {"unresolved failure", "explained discrepancy"}
    if compared == 0:
        return {"pending"}
    return {"partially supported"} if pending else {"experimentally supported"}


@pytest.mark.parametrize(("page", "expected"), sorted(PAGES.items()))
def test_every_page_carries_exactly_one_verification_field(page: str, expected: tuple[str, str | None]) -> None:
    """Before any experimental comparison: both V0 datasets are pending (P-2: no signed
    spot-check yet), 8CB is pending (AP-DPD), and the synthetic pages are synthetic-only."""
    v = _verification()
    value, dataset = expected
    text = (ROOT / "docs" / "phase2" / "verification" / page).read_text(encoding="utf-8")
    lines = _prose_lines(text)
    fields = [m.group(1) for line in lines if (m := FIELD_LINE.match(line))]
    assert fields == [value], fields
    assert not [line for line in lines if line.startswith("**Verification") and not FIELD_LINE.match(line)]
    assert v.check_page(text, dataset=dataset) == []
    v03 = [m.groups() for line in lines if (m := V03_LINE.match(line))]
    if dataset is None:
        assert v03 == []
        return
    assert len(v03) == 1 and len([ln for ln in lines if ln.startswith("**V0.3 label")]) == 1, v03
    label, *counts = v03[0]
    roster, compared, agreeing, disagreeing, pending = (int(c) for c in counts)
    mapped, _annotation = v.crosswalk(label)
    assert mapped == value
    assert roster == PREREG["datasets"][dataset]["roster_cells"]
    assert compared == agreeing + disagreeing and roster == compared + pending
    assert label in _v03_label_for(compared, agreeing, disagreeing, pending)
    if not _spot_check_signed(dataset):
        assert compared == 0  # P-2: every target withheld


PAGE_MUTANTS = {
    "no field": "# benzene\n\nNo field here.\n",
    "invalid value": "**Verification:** `partially supported`\n",
    "two valid fields": "**Verification:** `pending`\n\n**Verification:** `pending`\n",
    "valid beside a malformed duplicate": "**Verification:** `pending`\n\n**Verification:** pending, maybe\n",
    "only inside a code fence": "# benzene\n\n```\n**Verification:** `pending`\n```\n",
    "valid outside, another inside a fence": "**Verification:** `pending`\n\n```md\n**Verification:** `pending`\n```\n",
}


@pytest.mark.parametrize("name", sorted(PAGE_MUTANTS))
def test_a_page_without_exactly_one_valid_field_is_refused(name: str) -> None:
    assert _verification().check_page(PAGE_MUTANTS[name]), name


EXPERIMENTAL_MUTANTS = {
    "no V0.3 line": "**Verification:** `pending`\n",
    "V0.3 line only in a fence": (
        "**Verification:** `pending`\n\n```\n**V0.3 label:** `pending` (roster 15, compared 0, agreeing 0, "
        "disagreeing 0, pending 15)\n```\n"
    ),
    "two V0.3 lines": (
        "**Verification:** `pending`\n\n"
        "**V0.3 label:** `pending` (roster 15, compared 0, agreeing 0, disagreeing 0, pending 15)\n\n"
        "**V0.3 label:** `pending` (roster 15, compared 0, agreeing 0, disagreeing 0, pending 15)\n"
    ),
    "counts do not add up": (
        "**Verification:** `pending`\n\n"
        "**V0.3 label:** `partially supported` (roster 15, compared 3, agreeing 3, disagreeing 0, pending 13)\n"
    ),
    "wrong roster": (
        "**Verification:** `pending`\n\n"
        "**V0.3 label:** `pending` (roster 14, compared 0, agreeing 0, disagreeing 0, pending 14)\n"
    ),
    "label contradicts full agreement": (
        "**Verification:** `pending`\n\n"
        "**V0.3 label:** `pending` (roster 15, compared 15, agreeing 15, disagreeing 0, pending 0)\n"
    ),
    "label contradicts a disagreement": (
        "**Verification:** `pending`\n\n"
        "**V0.3 label:** `partially supported` (roster 15, compared 2, agreeing 1, disagreeing 1, pending 13)\n"
    ),
    "field contradicts the label": (
        "**Verification:** `experimentally supported`\n\n"
        "**V0.3 label:** `pending` (roster 15, compared 0, agreeing 0, disagreeing 0, pending 15)\n"
    ),
}


@pytest.mark.parametrize("name", sorted(EXPERIMENTAL_MUTANTS))
def test_an_inconsistent_experimental_page_is_refused(name: str) -> None:
    assert _verification().check_page(EXPERIMENTAL_MUTANTS[name], dataset="benzene-taggar2006"), name


def test_a_consistent_experimental_page_passes() -> None:
    text = (
        "**Verification:** `pending`\n\n"
        "**V0.3 label:** `partially supported` (roster 15, compared 3, agreeing 3, disagreeing 0, pending 12)\n"
    )
    assert _verification().check_page(text, dataset="benzene-taggar2006") == []


def test_a_synthetic_page_has_no_v03_line() -> None:
    text = (
        "**Verification:** `synthetic-only`\n\n"
        "**V0.3 label:** `pending` (roster 15, compared 0, agreeing 0, disagreeing 0, pending 15)\n"
    )
    assert _verification().check_page(text, dataset=None)


# ---------------------------------------------------------- the first-fit chronology (A1, §3)
DECISION_KEYS = (*(str(k) for k in range(1, 12)), "5a")
DATASETS = ("benzene-taggar2006", "odcb-chandrakumar1993")
RUNNERS = ("owner", "participant", "agent")


def _ledger(**changes: Any) -> dict[str, Any]:
    ledger: dict[str, Any] = {
        "decisions": {k: _t("2026-11-21T14:59Z") for k in DECISION_KEYS},
        "amendments": {"P-1": _t("2026-11-21T15:32Z"), "P-2": _t("2026-11-21T15:32Z")},
        "attestation": _t("2026-11-22T14:11Z"),  # the owner's signed no-fit attestation
        "freeze_approved": _t("2026-11-24T12:00Z"),
        "submissions": [],
        # None: not recorded; "none-yet": recorded that nobody has seen a result.
        "first_access": "none-yet",
    }
    ledger.update(changes)
    return ledger


def _sub(
    at: str, dataset: str = "benzene-taggar2006", runner: str = "owner", outcome: str = "succeeded"
) -> dict[str, Any]:
    """One submission with its full provenance (plan, first-fit gate)."""
    return {
        "dataset": dataset,
        "runner": runner,
        "at": _t(at),
        "outcome": outcome,
        "release_or_commit": "v0.2.0b1",
        "protocol_sha256": "a" * 64,
    }


def test_the_freeze_holds_when_everything_precedes_the_first_fit() -> None:
    v = _verification()
    assert v.freeze_ok(_ledger()) is True  # no fit yet
    later = [_sub("2026-11-25T10:00Z")]
    assert v.freeze_ok(_ledger(submissions=later, first_access=_t("2026-11-25T11:00Z"))) is True
    assert v.freeze_ok(_ledger(submissions=later, first_access="none-yet")) is True


FREEZE_REFUSALS: dict[str, dict[str, Any]] = {
    "freeze not approved": {"freeze_approved": None},
    "attestation not signed": {"attestation": None},
    "attestation after the freeze": {"attestation": _t("2026-11-24T13:00Z")},
    "a decision missing": {"decisions": _without({k: _t("2026-11-21T14:59Z") for k in DECISION_KEYS}, "5a")},
    "a decision open": {"decisions": {**{k: _t("2026-11-21T14:59Z") for k in DECISION_KEYS}, "7": None}},
    "an extra decision": {
        "decisions": {**{k: _t("2026-11-21T14:59Z") for k in DECISION_KEYS}, "12": _t("2026-11-21T15:00Z")}
    },
    "a decision after the freeze": {
        "decisions": {**{k: _t("2026-11-21T14:59Z") for k in DECISION_KEYS}, "3": _t("2026-11-24T13:00Z")}
    },
    "an amendment missing": {"amendments": {"P-1": _t("2026-11-21T15:32Z")}},
    "an amendment approval missing": {"amendments": {"P-1": _t("2026-11-21T15:32Z"), "P-2": None}},
    "an amendment approved after the freeze": {
        "amendments": {"P-1": _t("2026-11-21T15:32Z"), "P-2": _t("2026-11-24T13:00Z")}
    },
    "an amendment approved after the first fit": {
        "amendments": {"P-1": _t("2026-11-21T15:32Z"), "P-2": _t("2026-11-26T00:00Z")},
        "submissions": [_sub("2026-11-25T10:00Z")],
        "first_access": "none-yet",
    },
    "a fit before the freeze": {"submissions": [_sub("2026-11-23T08:00Z")], "first_access": "none-yet"},
    "a fit at the freeze instant": {
        "submissions": [{**_sub("2026-11-26T00:00Z"), "at": _t("2026-11-24T12:00Z")}],
        "first_access": "none-yet",
    },
    "a failed fit before the freeze": {
        "submissions": [_sub("2026-11-26T00:00Z"), _sub("2026-11-23T08:00Z", outcome="failed")],
        "first_access": "none-yet",
    },
    "the other dataset first": {
        "submissions": [_sub("2026-11-26T00:00Z"), _sub("2026-11-23T08:00Z", dataset="odcb-chandrakumar1993")],
        "first_access": "none-yet",
    },
    "a participant first": {
        "submissions": [_sub("2026-11-26T00:00Z"), _sub("2026-11-23T08:00Z", runner="participant")],
        "first_access": "none-yet",
    },
    "access not recorded after a fit": {"submissions": [_sub("2026-11-25T10:00Z")], "first_access": None},
    "access before any fit": {"submissions": [_sub("2026-11-25T10:00Z")], "first_access": _t("2026-11-25T09:00Z")},
    "a submission without provenance": {
        "submissions": [_without(_sub("2026-11-25T10:00Z"), "protocol_sha256")],
        "first_access": "none-yet",
    },
    "a submission of an unknown dataset": {
        "submissions": [_sub("2026-11-25T10:00Z", dataset="tfb")],
        "first_access": "none-yet",
    },
    "a submission by an unknown runner": {
        "submissions": [_sub("2026-11-25T10:00Z", runner="someone")],
        "first_access": "none-yet",
    },
    "a submission with an unknown outcome": {
        "submissions": [_sub("2026-11-25T10:00Z", outcome="maybe")],
        "first_access": "none-yet",
    },
}


@pytest.mark.parametrize("name", sorted(FREEZE_REFUSALS))
def test_the_freeze_is_refused(name: str) -> None:
    assert _verification().freeze_ok(_ledger(**FREEZE_REFUSALS[name])) is False, name


@pytest.mark.parametrize(
    ("made", "submissions", "first_access", "expected"),
    [
        ("2026-11-24T00:00Z", ["2026-11-25T00:00Z"], "2026-11-25T06:00Z", "pre-fit"),
        ("2026-11-24T00:00Z", [], "none-yet", "pre-fit"),
        # From the first submission on, an amendment cannot satisfy the freeze. It is not post hoc
        # only if the ledger establishes that it preceded every result access.
        ("2026-11-25T00:00Z", ["2026-11-25T00:00Z"], "2026-11-25T06:00Z", "after-submission"),
        ("2026-11-25T03:00Z", ["2026-11-25T00:00Z"], "2026-11-25T06:00Z", "after-submission"),
        ("2026-11-25T03:00Z", ["2026-11-25T00:00Z"], "none-yet", "after-submission"),
        ("2026-11-25T06:00Z", ["2026-11-25T00:00Z"], "2026-11-25T06:00Z", "post hoc"),
        ("2026-11-26T00:00Z", ["2026-11-25T00:00Z"], "2026-11-25T06:00Z", "post hoc"),
        # A submission with no recorded access time is ambiguous: treated as post hoc.
        ("2026-11-25T03:00Z", ["2026-11-25T00:00Z"], None, "post hoc"),
        # Unordered records: the earliest submission counts, wherever it is listed (round 82).
        ("2026-11-24T00:00Z", ["2026-11-26T00:00Z", "2026-11-23T00:00Z"], "none-yet", "after-submission"),
        ("2026-11-24T00:00Z", ["2026-11-26T00:00Z", "2026-11-23T00:00Z"], None, "post hoc"),
    ],
)
def test_an_amendment_is_classified_by_the_chronology(
    made: str, submissions: list[str], first_access: str | None, expected: str
) -> None:
    v = _verification()
    subs = [_sub(at, runner="participant" if i else "owner") for i, at in enumerate(submissions)]
    access: Any = first_access if first_access in (None, "none-yet") else _t(str(first_access))
    assert v.classify_amendment(_t(made), _ledger(submissions=subs, first_access=access)) == expected


# ------------------------------------------------------------- the exit matrix (A1, plan audit)
#: Each exit criterion of the plan's audit table with the evidence it requires (ledger §7): the
#: tests that must have passed (not skipped, not xfailed), and the receipts (local evidence and
#: named witnesses) that must be recorded. Round 82, A1: bound per criterion.
EXIT_REQUIREMENTS: dict[str, dict[str, tuple[str, ...]]] = {
    "V0.1 selection and rights": {
        "tests": ("tests/test_v0_corpus.py",),
        "receipts": ("staged-index scans",),
    },
    "V0.2 verified corpus": {
        "tests": ("tests/test_v0_corpus.py",),
        "receipts": ("benzene spot-check", "ortho-dichlorobenzene spot-check"),
    },
    "V0.3 frozen criteria and comparison": {
        "tests": (
            "tests/test_v0_preregistration.py",
            "tests/test_prereg_labels.py",
            "tests/test_digitize_figure.py",
            "tests/test_v15_gates.py",
        ),
        "receipts": ("local digests",),
    },
    "V1.0 and V1.1 design and fit": {"tests": ("tests/test_core_fixed.py",), "receipts": ()},
    "V1.2 symmetry and counting": {"tests": ("tests/test_core_symmetry.py",), "receipts": ()},
    "V1.3 application and compatibility": {
        "tests": ("packages/dipolar-app/tests/test_app_v13_fixed.py",),
        "receipts": (),
    },
    "V1.4 browser, robot and AI readiness": {
        "tests": ("packages/dipolar-app/tests/test_app_v14_browser.py", "web/e2e/fixed-tutorial.spec.ts"),
        "receipts": (),
    },
    "Every implemented model has a robot tutorial": {
        "tests": ("robot --scenario tutorial", "robot --scenario fixed-tutorial", "robot --scenario jump4-tutorial"),
        "receipts": (),
    },
    "V1.5 honest reporting and no tuning": {
        "tests": ("tests/test_v15_gates.py", "tests/test_v15_verification.py"),
        "receipts": ("discrepancy review", "local annex coverage", "restricted-fit scan"),
    },
    "Decision 6 and release": {
        "tests": ("tests/test_v15_gates.py::test_the_release_workflow_uses_exactly_the_approved_trigger",),
        "receipts": ("published pre-release", "external record", "owner sign-off"),
    },
}


def _complete_rows() -> list[dict[str, Any]]:
    return [
        {
            "criterion": c,
            "tests": {t: "passed" for t in req["tests"]},
            "receipts": {r: f"gates.md §6, {c}: {r}" for r in req["receipts"]},
        }
        for c, req in EXIT_REQUIREMENTS.items()
    ]


def test_the_exit_requirements_are_the_frozen_ones() -> None:
    v = _verification()
    assert {c: {k: tuple(x) for k, x in r.items()} for c, r in v.EXIT_REQUIREMENTS.items()} == EXIT_REQUIREMENTS


def test_a_complete_exit_matrix_passes() -> None:
    assert _verification().check_exit(_complete_rows()) == []


def _mutate_exit(name: str) -> list[dict[str, Any]]:
    rows = _complete_rows()
    first = rows[0]
    v02 = rows[1]
    if name == "a criterion missing":
        return rows[1:]
    if name == "a criterion twice":
        return [*rows, _complete_rows()[0]]
    if name == "an unknown criterion":
        return [*rows, {"criterion": "V1.6 something", "tests": {}, "receipts": {}}]
    if name == "a failed test":
        first["tests"]["tests/test_v0_corpus.py"] = "failed"
    elif name == "a skipped test":
        first["tests"]["tests/test_v0_corpus.py"] = "skipped"
    elif name == "an xfailed test":
        rows[9]["tests"] = {t: "xfailed" for t in rows[9]["tests"]}
    elif name == "a required test missing":
        first["tests"] = {}
    elif name == "placeholder references only":
        for r in rows:
            r["tests"] = {"tests/x.py::test_y": "passed"}
    elif name == "a receipt missing":
        del v02["receipts"]["benzene spot-check"]
    elif name == "an empty receipt":
        v02["receipts"]["benzene spot-check"] = ""
    elif name == "all CI, no local receipt":
        for r in rows:
            r["receipts"] = {}
    elif name == "an unknown field":
        first["note"] = "trust me"
    return rows


@pytest.mark.parametrize(
    "name",
    [
        "a criterion missing",
        "a criterion twice",
        "an unknown criterion",
        "a failed test",
        "a skipped test",
        "an xfailed test",
        "a required test missing",
        "placeholder references only",
        "a receipt missing",
        "an empty receipt",
        "all CI, no local receipt",
        "an unknown field",
    ],
)
def test_an_exit_matrix_with_a_gap_is_refused(name: str) -> None:
    assert _verification().check_exit(_mutate_exit(name)), name


# ----------------------------------------- the external evidence checklist (A1, decisions 2, 8, 9)
ROSTER = [f"c{i:02d}" for i in range(1, 16)]
#: What the owner supplies, independently of the participant (round 82, A1).
TRUSTED: dict[str, Any] = {
    "release_tag": "v0.2.0b1",
    "commit": "0123456789abcdef0123456789abcdef01234567",
    "protocol_sha256": "a27e0921851193ff1f3845d1bee4ccf42a8f21e4173cbf63d7df6d598fc6a4c5",
    "roster": ROSTER,
    "spot_check_receipt_sha256": "c" * 64,  # the owner's signed benzene receipt (A4)
    "published_counts": {"compared": 15, "agreeing": 13, "disagreeing": 2, "pending": 0},
}


def _record(**changes: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "participant": "P-001",
        "eligible": True,
        "release_tag": TRUSTED["release_tag"],
        "commit": TRUSTED["commit"],
        "protocol_sha256": TRUSTED["protocol_sha256"],
        "si_sha256_matches": True,
        "geometry_computed": True,  # not copied (guide step 3)
        "conditions": {c: {"numerical_match": True} for c in ROSTER},
        "counts": dict(TRUSTED["published_counts"]),
        "success_claimed": True,
    }
    record.update(changes)
    return record


def test_a_complete_external_record_supports_its_claim() -> None:
    """Decision 2A: reviewed disagreements with the paper (2 here) do not fail it."""
    assert _verification().check_participant(_record(), trusted=TRUSTED) == []


ALL_MATCH = {c: {"numerical_match": True} for c in ROSTER}
CLAIM_MUTANTS: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {
    # name: (record changes, trusted changes)
    "ineligible": ({"eligible": False}, {}),
    "wrong release": ({"release_tag": "v0.1.0b1"}, {}),
    "bogus commit": ({"commit": "f" * 40}, {}),
    "bogus protocol revision": ({"protocol_sha256": "1" * 64}, {}),
    "SI hash mismatch": ({"si_sha256_matches": False}, {}),
    "geometry copied": ({"geometry_computed": False}, {}),
    "no signed spot-check receipt": ({}, {"spot_check_receipt_sha256": None}),
    "a condition missing": ({"conditions": _without(ALL_MATCH, "c07")}, {}),
    "unrelated condition keys": ({"conditions": {f"x{i}": {"numerical_match": True} for i in range(15)}}, {}),
    "an extra condition": ({"conditions": {**ALL_MATCH, "c16": {"numerical_match": True}}}, {}),
    "a condition without a numerical match": ({"conditions": {**ALL_MATCH, "c07": {"numerical_match": False}}}, {}),
    "counts differ": ({"counts": {"compared": 15, "agreeing": 12, "disagreeing": 3, "pending": 0}}, {}),
    "matching counts, nothing compared": (
        {"counts": {"compared": 0, "agreeing": 0, "disagreeing": 0, "pending": 15}},
        {"published_counts": {"compared": 0, "agreeing": 0, "disagreeing": 0, "pending": 15}},
    ),
    "published counts inconsistent": (
        {"counts": {"compared": 15, "agreeing": 13, "disagreeing": 1, "pending": 0}},
        {"published_counts": {"compared": 15, "agreeing": 13, "disagreeing": 1, "pending": 0}},
    ),
    "not an opaque ID": ({"participant": "Alice"}, {}),
}


@pytest.mark.parametrize("name", sorted(CLAIM_MUTANTS))
def test_an_unsupported_success_claim_is_refused(name: str) -> None:
    record, trusted = CLAIM_MUTANTS[name]
    assert _verification().check_participant(_record(**record), trusted={**TRUSTED, **trusted}), name


PERSONAL_MUTANTS: dict[str, dict[str, Any]] = {
    "a name at the top": {"name": "A. Person"},
    "a handle at the top": {"github": "someone"},
    "an e-mail address in a value": {"note": "write to someone@example.org"},
    "a nested personal field": {"conditions": {**ALL_MATCH, "c01": {"numerical_match": True, "by": "A. Person"}}},
    "a nested field in the counts": {"counts": {**TRUSTED["published_counts"], "reported_by": "someone"}},
}


@pytest.mark.parametrize("claimed", [True, False])
@pytest.mark.parametrize("name", sorted(PERSONAL_MUTANTS))
def test_a_record_outside_the_closed_fields_is_refused(name: str, claimed: bool) -> None:
    """Decision 9: a closed allowlist at every level, failed and incomplete attempts included."""
    record = _record(success_claimed=claimed, **PERSONAL_MUTANTS[name])
    assert _verification().check_participant(record, trusted=TRUSTED), name


def test_an_attempt_that_claims_nothing_is_recorded_not_refused() -> None:
    """A failed or incomplete attempt is kept in the record (plan): it makes no claim."""
    v = _verification()
    failed = _record(success_claimed=False, si_sha256_matches=False, conditions={})
    assert v.check_participant(failed, trusted=TRUSTED) == []


# ------------------------------------------- the participant precision rule (plan, guide; A1)
K_HH = dipolar_constant_hz_a3("1H", "1H")
#: A synthetic axial order parameter: not a value from any source.
S_ZZ_SYNTHETIC = -0.0731
OFFSETS_HZ = np.array([0.31, -0.22, 0.12])  # deterministic "noise", so that ν = 2 has a residual
#: A participant's input frame need not be centred: rounding happens in the input XYZ frame.
ORIGIN = np.array([1.234567891234, -2.5, 0.75])
ELEMENTS = ["C"] * 6 + ["H"] * 6
PAIRS = [(6, 7), (6, 8), (6, 9)]  # H1–H2, H1–H3, H1–H4: D12, D13, D14 (guide step 3)


def _owner_xyz(twist_deg: float = 0.0) -> np.ndarray:
    """The owner's reference construction: the frozen angles and radii, through cos and sin."""
    g, angles = PREREG["geometry"], PREREG["datasets"]["benzene-taggar2006"]["ring_positions"]
    rows = []
    for radius in (g["r_cc_angstrom"], g["r_cc_angstrom"] + g["r_ch_angstrom"]):
        for name in ("H1", "H2", "H3", "H4", "H5", "H6"):
            a = math.radians(angles[name] + twist_deg)
            rows.append([radius * math.cos(a), radius * math.sin(a), 0.0])
    return np.array(rows) + ORIGIN


def _participant_xyz(twist_deg: float, r_cc_offset: float = 0.0) -> np.ndarray:
    """A participant's independent construction: exact multiples of 1/2 and √3/2, at 0° or 30°."""
    g, h = PREREG["geometry"], math.sqrt(3.0) / 2
    units = {
        0.0: [(1, 0), (0.5, h), (-0.5, h), (-1, 0), (-0.5, -h), (0.5, -h)],
        30.0: [(h, 0.5), (0, 1), (-h, 0.5), (-h, -0.5), (0, -1), (h, -0.5)],
    }[twist_deg]
    r_cc = g["r_cc_angstrom"] + r_cc_offset
    rows = [[r * c, r * s, 0.0] for r in (r_cc, r_cc + g["r_ch_angstrom"]) for c, s in units]
    return np.array(rows) + ORIGIN


def _axes(twist_deg: float) -> np.ndarray:
    """The declared D6h axes: z normal to the ring, x through H1 (a C2' axis)."""
    a = math.radians(twist_deg)
    return np.array([[math.cos(a), math.sin(a), 0.0], [-math.sin(a), math.cos(a), 0.0], [0.0, 0.0, 1.0]])


def _couplings() -> np.ndarray:
    """From the scalar law on the frozen geometry, independent of the engine: in-plane pairs see
    u·S·u = −S_zz/2 for an axial S; the H–H distances are R, R√3 and 2R."""
    big_r = PREREG["geometry"]["r_cc_angstrom"] + PREREG["geometry"]["r_ch_angstrom"]
    r = np.array([big_r, big_r * math.sqrt(3.0), 2 * big_r])
    out: np.ndarray = K_HH * (-S_ZZ_SYNTHETIC / 2) / r**3 + OFFSETS_HZ
    return out


def _fit_szz(xyz: np.ndarray, twist_deg: float) -> float:
    """The production path: symmetry.validate (D6h averaging), fixed_rows, fit_fixed."""
    validated = symmetry.validate(xyz, ELEMENTS, [None] * 12, symmetry.Declaration("D6h", _axes(twist_deg), 0.01))
    rows = symmetry.fixed_rows(validated, PAIRS, K_HH)
    res = fixed.fit_fixed(rows.design_s5, _couplings(), np.full(3, 0.3), subspace=rows.subspace)
    (szz,) = [c for c in res.components if c.name == "Szz"]
    assert res.rank_verified and szz.status == "estimated" and szz.estimate is not None
    return float(szz.estimate)


def _numerical_match(participant: float, reference: float, decimals: int, allowance: float) -> bool | None:
    """The rule (ledger §8): 1e-8 absolute at 12+ decimals; at 8–11 add the owner's rounding
    allowance; below 8, regenerate (None)."""
    if decimals < 8:
        return None
    return abs(participant - reference) <= 1e-8 + (0.0 if decimals >= 12 else allowance)


@pytest.mark.parametrize("decimals", [8, 9, 10, 11, 12, 13, 15])
@pytest.mark.parametrize("twist", [0.0, 30.0])
def test_the_precision_rule_accepts_an_independent_geometry(decimals: int, twist: float) -> None:
    """Synthetic evidence, run in CI on Linux and Windows and on the owner's macOS. The owner's
    reference is the full-precision construction. The allowance rounds the owner's coordinates in
    the participant's declared frame. The participant builds the geometry independently."""
    reference = _fit_szz(_owner_xyz(), 0.0)
    assert abs(reference - S_ZZ_SYNTHETIC) < 1e-2
    allowance = abs(_fit_szz(np.round(_owner_xyz(twist), decimals), twist) - reference)
    participant = _fit_szz(np.round(_participant_xyz(twist), decimals), twist)
    assert _numerical_match(participant, reference, decimals, allowance) is True
    # Measured: through the D6h averaging the miss stays below the 1e-8 tolerance even at 8
    # decimals (round 82's bound: < 8.6e-9 for |Szz| ≤ 1 with round-to-nearest).
    assert abs(participant - reference) < 8.6e-9


@pytest.mark.parametrize("decimals", [8, 12, 15])
def test_the_precision_rule_refuses_a_wrong_geometry(decimals: int) -> None:
    reference = _fit_szz(_owner_xyz(), 0.0)
    allowance = abs(_fit_szz(np.round(_owner_xyz(), decimals), 0.0) - reference)
    wrong = _fit_szz(np.round(_participant_xyz(0.0, r_cc_offset=1e-4), decimals), 0.0)
    assert _numerical_match(wrong, reference, decimals, allowance) is False


@pytest.mark.parametrize("decimals", [8, 11])
def test_the_allowance_boundary_is_inclusive(decimals: int) -> None:
    reference, allowance = 0.0, 3e-9  # 0, so that the differences are exact
    edge = reference + (1e-8 + allowance)
    assert _numerical_match(edge, reference, decimals, allowance) is True
    assert _numerical_match(float(np.nextafter(edge, 1.0)), reference, decimals, allowance) is False
    assert _numerical_match(reference + 1e-8, reference, 12, allowance) is True
    assert _numerical_match(float(np.nextafter(reference + 1e-8, 1.0)), reference, 12, allowance) is False


def test_the_precision_rule_asks_for_more_decimals_below_eight() -> None:
    assert _numerical_match(0.0, 0.0, 7, 0.0) is None


# ------------------------------------------- V0.3 amendments P-1 and P-2 in the JSON (A7)
REPORTING = {
    "disclosure": {
        "amendment": "P-1",
        "shared": "prereg.shareable",
        "discrepancy_entry_requires": "a reviewed README entry for the cell",
        "discrepancy_entry_names": ["dataset", "track", "condition", "estimand", "protocol_sha256"],
        "discrepancy_entry_context": [
            "estimand",
            "frame and observable convention",
            "geometry",
            "vibrational corrections",
            "solvent and sample",
            "suspected cause",
        ],
        "discrepancy_entry_excludes": ["target", "fit", "signed difference", "margin", "ratio"],
    },
    "spot_check_gating": {
        "amendment": "P-2",
        "rule": (
            "targets absent (no-target) until the dataset's spot-check receipt is signed, "
            "bound to the checked file's SHA-256"
        ),
        "tracks": ["independent", "reproduction"],
        "keeps_precedence": "rank-unverified",
        "checked_artifact": {"benzene-taggar2006": "targets", "odcb-chandrakumar1993": "couplings"},
        "open_note": "the owner's spot-check of this transcription is open",
        "open_note_datasets": ["odcb-chandrakumar1993"],
    },
}


def _hash(p: dict[str, Any]) -> str:
    payload = {k: v for k, v in p.items() if k != "amendments"}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def test_the_amendments_are_closed_fields_that_change_the_protocol_revision() -> None:
    assert PREREG.get("reporting") == REPORTING
    original = {k: v for k, v in PREREG.items() if k != "reporting"}
    after_p1 = {**original, "reporting": {"disclosure": REPORTING["disclosure"]}}
    assert _hash(original) == ORIGINAL_PROTOCOL
    p1, p2 = PREREG["amendments"]
    assert (p1["protocol_before_sha256"], p1["protocol_after_sha256"]) == (ORIGINAL_PROTOCOL, _hash(after_p1))
    assert (p2["protocol_before_sha256"], p2["protocol_after_sha256"]) == (_hash(after_p1), _hash(PREREG))
    assert prereg.protocol_sha256(PREREG) == _hash(PREREG) != ORIGINAL_PROTOCOL
    assert not (p1["post_hoc"] or p2["post_hoc"])


def test_the_schema_closes_the_reporting_fields() -> None:
    import jsonschema

    schema = json.loads((ROOT / "docs" / "phase2" / "v0.3-preregistration.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(PREREG, schema, cls=jsonschema.Draft202012Validator)
    gating = REPORTING["spot_check_gating"]
    for bad in (
        {**PREREG, "reporting": {**REPORTING, "extra": 1}},
        {**PREREG, "reporting": {"disclosure": REPORTING["disclosure"]}},
        {**PREREG, "reporting": {**REPORTING, "spot_check_gating": {**gating, "tracks": ["independent"]}}},
        {
            **PREREG,
            "reporting": {**REPORTING, "disclosure": _without(REPORTING["disclosure"], "discrepancy_entry_requires")},
        },
        {
            **PREREG,
            "reporting": {
                **REPORTING,
                "spot_check_gating": {
                    **gating,
                    "checked_artifact": {"benzene-taggar2006": "couplings", "odcb-chandrakumar1993": "couplings"},
                },
            },
        },
    ):
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(bad, schema, cls=jsonschema.Draft202012Validator)


def _receipt(dataset: str) -> dict[str, str]:
    """A signed receipt for the artifact P-2 names for the dataset, at its frozen digest."""
    artifact = REPORTING["spot_check_gating"]["checked_artifact"][dataset]
    return {"dataset": dataset, "artifact": artifact, "sha256": PREREG["datasets"][dataset][artifact]["sha256"]}


def _classify(dataset: str, receipt: dict[str, str] | None, component: str = "S_zz", **kw: Any) -> pl.Cell:
    args: dict[str, Any] = {"rank_verified": True, "target": (-0.1, 0.001), "s": -0.1, "s_zz_pub": -0.1}
    args.update(kw)
    return prereg.classify_gated("c1", component, dataset=dataset, receipt=receipt, prereg=PREREG, **args)


@pytest.mark.parametrize("dataset", ["benzene-taggar2006", "odcb-chandrakumar1993"])
def test_targets_are_withheld_before_classification_until_the_spot_check_is_signed(dataset: str) -> None:
    signed = _receipt(dataset)
    assert _classify(dataset, signed).status == "agrees"
    for receipt in (
        None,
        {**signed, "sha256": "b" * 64},  # another digest
        {**signed, "sha256": ""},  # empty
        {**signed, "dataset": "tfb"},  # another dataset
        {**signed, "artifact": "couplings" if signed["artifact"] == "targets" else "targets"},
        {**signed, "extra": "x"},
        _receipt("odcb-chandrakumar1993" if dataset == "benzene-taggar2006" else "benzene-taggar2006"),
    ):
        cell = _classify(dataset, receipt)
        assert (cell.status, cell.reason) == ("pending", "no-target"), receipt
        # The anisotropy loses both its target and the axial scale: no-target, not s_zz-target-pending.
        aniso = _classify(dataset, receipt, component="S_xx-S_yy", s_zz_pub=None)
        assert (aniso.status, aniso.reason) == ("pending", "no-target"), receipt
        # rank-unverified keeps its precedence.
        assert _classify(dataset, receipt, rank_verified=False).reason == "rank-unverified"


def test_the_original_protocol_has_no_gating() -> None:
    original = {k: v for k, v in PREREG.items() if k != "reporting"}
    cell = prereg.classify_gated(
        "c1",
        "S_zz",
        dataset="benzene-taggar2006",
        receipt=None,
        prereg=original,
        rank_verified=True,
        target=(-0.1, 0.001),
        s=-0.1,
    )
    assert cell.status == "agrees"


def test_the_odcb_note_stays_while_its_spot_check_is_open() -> None:
    note = REPORTING["spot_check_gating"]["open_note"]
    odcb = "odcb-chandrakumar1993"
    assert note in prereg.label_notes(odcb, receipt=None, prereg=PREREG)
    assert note not in prereg.label_notes(odcb, receipt=_receipt(odcb), prereg=PREREG)
    assert note not in prereg.label_notes("benzene-taggar2006", receipt=None, prereg=PREREG)
    for dataset in ("benzene-taggar2006", odcb):
        assert "development data, no independent holdout" in prereg.label_notes(dataset, receipt=None, prereg=PREREG)


# ------------------------------------------------------ the release-trigger guard (B10, V1.5c)
#: The approved package-only filters (plan, "Pre-release and commands").
APPROVED_FILTERS = [
    "v[0-9]+.[0-9]+.[0-9]+",
    "v[0-9]+.[0-9]+.[0-9]+[ab][0-9]+",
    "v[0-9]+.[0-9]+.[0-9]+rc[0-9]+",
]
PACKAGE_TAGS = ["v0.1.0b1", "v0.2.0b1", "v0.2.0b2", "v0.2.0a1", "v0.2.0rc1", "v1.0.0", "v0.10.12"]
OTHER_TAGS = [
    "v1.4-browser",
    "v1.5-verification",
    "v0.3-preregistration",
    "v0.1-selection",
    "v1.0",
    "v0.2.0-b1",
    "v0.2.0b",
    "vx.y.z",
    "v0.2.0b1-extra",
    "v9.9-not-a-package",
]


def _github_filter(pattern: str) -> re.Pattern[str]:
    """GitHub's filter-pattern syntax, from the Actions documentation: ``*`` (no ``/``), ``**``
    (anything), ``?`` and ``+`` after a character or class, ``[..]`` classes with ranges, and
    ``\\`` escaping the next character. Anything else special is refused."""
    out, i = "", 0
    while i < len(pattern):
        ch = pattern[i]
        if pattern.startswith("**", i):
            out += ".*"
            i += 2
            continue
        if ch == "\\":
            if i + 1 == len(pattern):
                raise ValueError("a trailing escape")
            out += re.escape(pattern[i + 1])
            i += 2
            continue
        if ch == "*":
            out += "[^/]*"
        elif ch in "?+":
            if not out:
                raise ValueError(f"{ch!r} with nothing before it")
            out += ch
        elif ch == "[":
            j = pattern.find("]", i)
            body = pattern[i + 1 : j]
            if j < 0 or not body or not re.fullmatch(r"(?:[A-Za-z0-9]-[A-Za-z0-9]|[A-Za-z0-9._-])+", body):
                raise ValueError(f"an unsupported class in {pattern!r}")
            out += "[" + body + "]"
            i = j
        elif ch in "!(){}|^$":
            raise ValueError(f"unsupported filter syntax {ch!r} in {pattern!r}")
        else:
            out += re.escape(ch)
        i += 1
    return re.compile(out + r"\Z")


def _triggers(tag: str, patterns: list[str]) -> bool:
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
    assert _github_filter(r"v1\+").match("v1+") and not _github_filter(r"v1\+").match("v11")
    assert not _github_filter("v1.0").match("v1x0")
    for bad in ("v(1|2)", "+v", "v[", "v[^0]", "v\\"):
        with pytest.raises(ValueError):
            _github_filter(bad)


@pytest.mark.parametrize("tag", PACKAGE_TAGS)
def test_the_approved_filters_route_package_tags(tag: str) -> None:
    assert _triggers(tag, APPROVED_FILTERS)


@pytest.mark.parametrize("tag", OTHER_TAGS)
def test_the_approved_filters_refuse_other_tags(tag: str) -> None:
    assert not _triggers(tag, APPROVED_FILTERS)


def _workflow_trigger() -> Any:
    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8"))
    return workflow.get("on", workflow.get(True))  # YAML 1.1 reads a bare `on` as True


def test_the_release_workflow_uses_exactly_the_approved_trigger() -> None:
    """The whole event mapping, not only the tag list (round 82, A5): no branch push, no `create`,
    no other event. The xfail holds only for the exact original trigger. The exit matrix requires
    this test to have passed (Decision 6 and release), so a return to `v*` fails the V1.5c exit."""
    trigger = _workflow_trigger()
    if trigger == {"push": {"tags": ["v*"]}}:
        pytest.xfail("V1.5c lands the release-trigger guard")
    assert trigger == {"push": {"tags": APPROVED_FILTERS}}
    assert all(_triggers(t, APPROVED_FILTERS) for t in PACKAGE_TAGS)
    assert not any(_triggers(t, APPROVED_FILTERS) for t in OTHER_TAGS)


@pytest.mark.parametrize(
    "trigger",
    [
        {"push": {"tags": [*APPROVED_FILTERS, "v9*"]}},
        {"push": {"tags": APPROVED_FILTERS, "branches": ["main"]}},
        {"push": {"tags": APPROVED_FILTERS}, "create": None},
        {"push": {"tags": APPROVED_FILTERS}, "workflow_dispatch": None},
        {"push": {"tags": ["v*"]}, "create": None},
    ],
)
def test_a_trigger_with_another_route_is_refused(trigger: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys.modules[__name__], "_workflow_trigger", lambda: trigger)
    with pytest.raises(AssertionError):
        test_the_release_workflow_uses_exactly_the_approved_trigger()
