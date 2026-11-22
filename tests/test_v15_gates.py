"""Phase 2 V1.5a gates, frozen before the V1.5 implementation (docs/phase2/v1.5-plan.md).

Every expectation here is written from the plan, the V1.5a ledger
(docs/phase2/verification/gates.md) and V0.3 §6–§8, not from the code it will check. Round 81
(docs/validation/round81-v1.5a-gates.md) strengthened them.

**Pending implementations.** The report workflow (``tools/validation/verification.py``) is V1.5b's.
While that module does not exist, its gates xfail through ``_verification()``, and through that
alone. Once the module exists, every gate runs, including the page gates, and any exception from
the implementation fails. The release-trigger guard is V1.5c's: while ``release.yml`` still has
the original ``v*`` trigger, the workflow gate xfails. Once the trigger changes, it must be
exactly the approved list. ``pytest -rx`` lists what is still pending, and the V1.5b and V1.5c
exit rows require none.
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
from dipolar_core import fixed
from dipolar_core.forward import design_rows
from dipolar_core.nuclides import dipolar_constant_hz_a3

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "validation"))

import prereg  # noqa: E402
import prereg_labels as pl  # noqa: E402

PREREG = json.loads((ROOT / "docs" / "phase2" / "v0.3-preregistration.json").read_text(encoding="utf-8"))
ORIGINAL_PROTOCOL = "332be1d699421d568655669a9fcaf2fc05667e195795a63913b9a67d22e48ea3"


def _verification() -> Any:
    """The V1.5b module, or an xfail while (and only while) it does not exist."""
    try:
        return importlib.import_module("verification")
    except ModuleNotFoundError as exc:
        if exc.name == "verification":
            pytest.xfail("V1.5b: tools/validation/verification.py is not written yet")
        raise


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
    assert v.check_page(text) == []
    if dataset is not None:
        v03 = [m.groups() for line in lines if (m := V03_LINE.match(line))]
        assert len(v03) == 1, v03
        label, *counts = v03[0]
        roster, compared, agreeing, disagreeing, pending = (int(c) for c in counts)
        mapped, _annotation = v.crosswalk(label)
        assert mapped == value
        assert roster == PREREG["datasets"][dataset]["roster_cells"]
        assert compared == agreeing + disagreeing and roster == compared + pending


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


@pytest.mark.parametrize(
    "line",
    [
        "**V0.3 label:** `partially supported` (roster 15, compared 3, agreeing 3, disagreeing 0, pending 13)",
        "**V0.3 label:** `pending` (roster 15, compared 0, agreeing 0, disagreeing 0, pending 14)",
    ],
)
def test_an_experimental_page_with_inconsistent_v03_counts_is_refused(line: str) -> None:
    text = f"**Verification:** `pending`\n\n{line}\n"
    assert _verification().check_page(text, dataset="benzene-taggar2006")


# ---------------------------------------------------------- the first-fit chronology (A1, §3)
DECISION_KEYS = (*(str(k) for k in range(1, 12)), "5a")


def _ledger(**changes: Any) -> dict[str, Any]:
    ledger: dict[str, Any] = {
        "decisions": {k: _t("2026-11-21T14:59Z") for k in DECISION_KEYS},
        "amendments": {"P-1": _t("2026-11-21T15:32Z"), "P-2": _t("2026-11-21T15:32Z")},
        "freeze_approved": _t("2026-11-24T12:00Z"),
        "submissions": [],
        # None: not recorded; "none-yet": recorded that nobody has seen a result.
        "first_access": "none-yet",
    }
    ledger.update(changes)
    return ledger


def _sub(at: str, dataset: str = "benzene-taggar2006", runner: str = "owner", outcome: str = "succeeded") -> dict:
    return {"dataset": dataset, "runner": runner, "at": _t(at), "outcome": outcome}


def test_the_freeze_holds_when_everything_precedes_the_first_fit() -> None:
    v = _verification()
    assert v.freeze_ok(_ledger()) is True  # no fit yet
    later = [_sub("2026-11-25T10:00Z")]
    assert v.freeze_ok(_ledger(submissions=later, first_access=_t("2026-11-25T11:00Z"))) is True


@pytest.mark.parametrize(
    "name",
    [
        "freeze not approved",
        "a decision missing",
        "a decision open",
        "an amendment missing",
        "a decision after the freeze",
        "a fit before the freeze",
        "a fit at the freeze instant",
        "a failed fit before the freeze",
        "the other dataset first",
        "a participant first",
        "access not recorded after a fit",
        "access before any fit",
    ],
)
def test_the_freeze_is_refused(name: str) -> None:
    decisions = {k: _t("2026-11-21T14:59Z") for k in DECISION_KEYS}
    freeze = _t("2026-11-24T12:00Z")
    access = {"first_access": _t("2026-11-26T00:00Z")}
    early = "2026-11-23T08:00Z"
    cases: dict[str, dict[str, Any]] = {
        "freeze not approved": {"freeze_approved": None},
        "a decision missing": {"decisions": {k: d for k, d in decisions.items() if k != "5a"}},
        "a decision open": {"decisions": {**decisions, "7": None}},
        "an amendment missing": {"amendments": {"P-1": _t("2026-11-21T15:32Z")}},
        "a decision after the freeze": {"decisions": {**decisions, "3": _t("2026-11-24T13:00Z")}},
        "a fit before the freeze": {"submissions": [_sub(early)], **access},
        "a fit at the freeze instant": {"submissions": [{**_sub("2026-11-26T00:00Z"), "at": freeze}], **access},
        "a failed fit before the freeze": {
            "submissions": [_sub("2026-11-26T00:00Z"), _sub(early, outcome="failed")],
            **access,
        },
        "the other dataset first": {
            "submissions": [_sub("2026-11-26T00:00Z"), _sub(early, dataset="odcb-chandrakumar1993")],
            **access,
        },
        "a participant first": {
            "submissions": [_sub("2026-11-26T00:00Z"), _sub(early, runner="participant")],
            **access,
        },
        "access not recorded after a fit": {"submissions": [_sub("2026-11-25T10:00Z")], "first_access": None},
        "access before any fit": {"submissions": [_sub("2026-11-25T10:00Z")], "first_access": _t("2026-11-25T09:00Z")},
    }
    assert _verification().freeze_ok(_ledger(**cases[name])) is False, name


@pytest.mark.parametrize(
    ("made", "first_submission", "first_access", "expected"),
    [
        ("2026-11-24T00:00Z", "2026-11-25T00:00Z", "2026-11-25T06:00Z", "pre-fit"),
        ("2026-11-24T00:00Z", None, "none-yet", "pre-fit"),
        # From the first submission on, an amendment cannot satisfy the freeze. It is not post hoc
        # only if the ledger establishes that it preceded every result access.
        ("2026-11-25T00:00Z", "2026-11-25T00:00Z", "2026-11-25T06:00Z", "after-submission"),
        ("2026-11-25T03:00Z", "2026-11-25T00:00Z", "2026-11-25T06:00Z", "after-submission"),
        ("2026-11-25T03:00Z", "2026-11-25T00:00Z", "none-yet", "after-submission"),
        ("2026-11-25T06:00Z", "2026-11-25T00:00Z", "2026-11-25T06:00Z", "post hoc"),
        ("2026-11-26T00:00Z", "2026-11-25T00:00Z", "2026-11-25T06:00Z", "post hoc"),
        # A submission with no recorded access time is ambiguous: treated as post hoc.
        ("2026-11-25T03:00Z", "2026-11-25T00:00Z", None, "post hoc"),
    ],
)
def test_an_amendment_is_classified_by_the_chronology(
    made: str, first_submission: str | None, first_access: str | None, expected: str
) -> None:
    v = _verification()
    subs = [] if first_submission is None else [_sub(first_submission)]
    access: Any = first_access if first_access in (None, "none-yet") else _t(str(first_access))
    assert v.classify_amendment(_t(made), _ledger(submissions=subs, first_access=access)) == expected


# ------------------------------------------------------------- the exit matrix (A1, plan audit)
#: The exit criteria of the plan's audit table, each needing a test or a named witness.
EXIT_CRITERIA = (
    "V0.1 selection and rights",
    "V0.2 verified corpus",
    "V0.3 frozen criteria and comparison",
    "V1.0 and V1.1 design and fit",
    "V1.2 symmetry and counting",
    "V1.3 application and compatibility",
    "V1.4 browser, robot and AI readiness",
    "Every implemented model has a robot tutorial",
    "V1.5 honest reporting and no tuning",
    "Decision 6 and release",
)


def _row(criterion: str, **changes: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "criterion": criterion,
        "kind": "test",
        "ref": "tests/x.py::test_y",
        "result": "passed",
        "local_only": False,
        "receipt": None,
    }
    row.update(changes)
    return row


def test_a_complete_exit_matrix_passes() -> None:
    rows = [_row(c) for c in EXIT_CRITERIA]
    rows[1] = _row(EXIT_CRITERIA[1], local_only=True, receipt="gates.md §6, 2026-12-01T10:00Z")
    rows[9] = _row(EXIT_CRITERIA[9], kind="witness", ref="owner", receipt="gates.md §7")
    assert _verification().check_exit(rows) == []


@pytest.mark.parametrize(
    "name",
    [
        "a criterion missing",
        "a criterion twice",
        "an unknown criterion",
        "a failed test",
        "a skipped test",
        "missing evidence",
        "a local-only test with no receipt",
        "a witness with no receipt",
        "a row with no reference",
    ],
)
def test_an_exit_matrix_with_a_gap_is_refused(name: str) -> None:
    rows = [_row(c) for c in EXIT_CRITERIA]
    mutate = {
        "a criterion missing": lambda r: r[1:],
        "a criterion twice": lambda r: [*r, _row(EXIT_CRITERIA[0])],
        "an unknown criterion": lambda r: [*r, _row("V1.6 something")],
        "a failed test": lambda r: [_row(EXIT_CRITERIA[0], result="failed"), *r[1:]],
        "a skipped test": lambda r: [_row(EXIT_CRITERIA[0], result="skipped"), *r[1:]],
        "missing evidence": lambda r: [_row(EXIT_CRITERIA[0], result="missing"), *r[1:]],
        "a local-only test with no receipt": lambda r: [_row(EXIT_CRITERIA[0], local_only=True), *r[1:]],
        "a witness with no receipt": lambda r: [_row(EXIT_CRITERIA[0], kind="witness", ref="owner"), *r[1:]],
        "a row with no reference": lambda r: [_row(EXIT_CRITERIA[0], ref=""), *r[1:]],
    }
    assert _verification().check_exit(mutate[name](rows)), name


# ----------------------------------------- the external evidence checklist (A1, decisions 2, 8, 9)
CONDITIONS = [f"c{i:02d}" for i in range(1, 16)]
PUBLISHED_COUNTS = {"compared": 15, "agreeing": 13, "disagreeing": 2, "pending": 0}


def _record(**changes: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "participant": "P-001",
        "eligible": True,
        "release_tag": "v0.2.0b1",
        "commit": "0" * 40,
        "protocol_sha256": "1" * 64,
        "si_sha256_matches": True,
        "geometry_computed": True,  # not copied (guide step 3)
        "spot_check_receipt": True,  # the owner's benzene receipt (A4)
        "conditions": {c: {"numerical_match": True} for c in CONDITIONS},
        "counts": dict(PUBLISHED_COUNTS),
        "published_counts": dict(PUBLISHED_COUNTS),
        "success_claimed": True,
    }
    record.update(changes)
    return record


def test_a_complete_external_record_supports_its_claim() -> None:
    """Decision 2A: reviewed disagreements with the paper (2 here) do not fail it."""
    assert _verification().check_participant(_record(), candidate_tag="v0.2.0b1") == []


@pytest.mark.parametrize(
    "name",
    [
        "ineligible",
        "wrong release",
        "SI hash mismatch",
        "geometry copied",
        "no spot-check receipt",
        "a condition missing",
        "a condition without a numerical match",
        "counts differ",
        "a name in the record",
        "a handle in the record",
        "an email in the record",
        "not an opaque ID",
    ],
)
def test_an_unsupported_success_claim_is_refused(name: str) -> None:
    some = {c: {"numerical_match": True} for c in CONDITIONS}
    mutants: dict[str, dict[str, Any]] = {
        "ineligible": {"eligible": False},
        "wrong release": {"release_tag": "v0.1.0b1"},
        "SI hash mismatch": {"si_sha256_matches": False},
        "geometry copied": {"geometry_computed": False},
        "no spot-check receipt": {"spot_check_receipt": False},
        "a condition missing": {"conditions": {c: m for c, m in some.items() if c != "c07"}},
        "a condition without a numerical match": {"conditions": {**some, "c07": {"numerical_match": False}}},
        "counts differ": {"counts": {**PUBLISHED_COUNTS, "agreeing": 12, "disagreeing": 3}},
        "a name in the record": {"name": "A. Person"},
        "a handle in the record": {"github": "someone"},
        "an email in the record": {"contact": "someone@example.org"},
        "not an opaque ID": {"participant": "Alice"},
    }
    problems = _verification().check_participant(_record(**mutants[name]), candidate_tag="v0.2.0b1")
    assert problems, name


def test_an_attempt_that_claims_nothing_is_recorded_not_refused() -> None:
    """A failed or incomplete attempt is kept in the record (plan): it makes no claim."""
    v = _verification()
    assert v.check_participant(_record(success_claimed=False, si_sha256_matches=False), candidate_tag="v0.2.0b1") == []


# ------------------------------------------- the participant precision rule (plan, guide; A1)
K_HH = dipolar_constant_hz_a3("1H", "1H")
#: A synthetic axial order parameter: not a value from any source.
S_ZZ_SYNTHETIC = -0.0731
OFFSETS_HZ = np.array([0.31, -0.22, 0.12])  # deterministic "noise", so that ν = 2 has a residual


def _benzene_positions(r_cc: float, r_ch: float, twist_deg: float = 0.0) -> np.ndarray:
    """The owner's reference construction: the frozen angles, through cos and sin."""
    angles = PREREG["datasets"]["benzene-taggar2006"]["ring_positions"]
    out = []
    for name in ("H1", "H2", "H3", "H4", "H5", "H6"):
        a = math.radians(angles[name] + twist_deg)
        out.append([(r_cc + r_ch) * math.cos(a), (r_cc + r_ch) * math.sin(a), 0.0])
    return np.array(out)


def _participant_positions(r_cc: float, r_ch: float) -> np.ndarray:
    """A participant's independent construction (no twist): exact multiples of 1/2 and √3/2."""
    r, h = r_cc + r_ch, math.sqrt(3.0) / 2
    unit = [(1, 0), (0.5, h), (-0.5, h), (-1, 0), (-0.5, -h), (0.5, -h)]
    return np.array([[r * c, r * s, 0.0] for c, s in unit])


PAIRS = [(0, 1), (0, 2), (0, 3)]  # D12, D13, D14: one representative per orbit (guide step 3)


def _couplings() -> np.ndarray:
    """From the scalar law: in-plane pairs see u·S·u = −S_zz/2 for an axial S."""
    pos = _benzene_positions(PREREG["geometry"]["r_cc_angstrom"], PREREG["geometry"]["r_ch_angstrom"])
    r = np.array([np.linalg.norm(pos[j] - pos[i]) for i, j in PAIRS])
    out: np.ndarray = K_HH * (-S_ZZ_SYNTHETIC / 2) / r**3 + OFFSETS_HZ
    return out


def _fit_szz(pos: np.ndarray) -> float:
    res = fixed.fit_fixed(design_rows(pos, PAIRS, K_HH), _couplings(), np.full(3, 0.3), subspace=fixed.SUBSPACES["D6h"])
    (szz,) = [c for c in res.components if c.name == "Szz"]
    assert res.rank_verified and szz.status == "estimated" and szz.estimate is not None
    return float(szz.estimate)


def _numerical_match(participant: float, reference: float, decimals: int, allowance: float) -> bool | None:
    """The plan's rule: 1e-8 absolute at 12+ decimals; at 8–11 add the owner's rounding allowance;
    below 8, regenerate (None)."""
    if decimals < 8:
        return None
    return abs(participant - reference) <= 1e-8 + (0.0 if decimals >= 12 else allowance)


@pytest.mark.parametrize("decimals", [8, 9, 10, 11, 12, 13, 15])
@pytest.mark.parametrize("twist", [0.0, 30.0])
def test_the_precision_rule_accepts_an_independent_geometry(decimals: int, twist: float) -> None:
    """Synthetic evidence for the full-precision rule, run on every CI platform (Linux, Windows) and
    the owner's macOS. The participant's x axis may differ (twist): D6h fixes only z."""
    g = PREREG["geometry"]
    reference_pos = _benzene_positions(g["r_cc_angstrom"], g["r_ch_angstrom"])
    reference = _fit_szz(reference_pos)
    assert abs(reference - S_ZZ_SYNTHETIC) < 1e-2
    declared = _benzene_positions(g["r_cc_angstrom"], g["r_ch_angstrom"], twist)  # in the declared axes
    allowance = abs(_fit_szz(np.round(declared, decimals)) - reference)
    built = _participant_positions(g["r_cc_angstrom"], g["r_ch_angstrom"]) if twist == 0.0 else declared
    participant = _fit_szz(np.round(built, decimals))
    assert _numerical_match(participant, reference, decimals, allowance) is True
    if decimals >= 12:
        assert abs(participant - reference) <= 1e-8


@pytest.mark.parametrize("decimals", [8, 12, 15])
def test_the_precision_rule_refuses_a_wrong_geometry(decimals: int) -> None:
    g = PREREG["geometry"]
    reference = _fit_szz(_benzene_positions(g["r_cc_angstrom"], g["r_ch_angstrom"]))
    wrong = np.round(_benzene_positions(g["r_cc_angstrom"] + 1e-4, g["r_ch_angstrom"]), decimals)
    rounded = np.round(_benzene_positions(g["r_cc_angstrom"], g["r_ch_angstrom"]), decimals)
    allowance = abs(_fit_szz(rounded) - reference)
    assert _numerical_match(_fit_szz(wrong), reference, decimals, allowance) is False


def test_the_precision_rule_asks_for_more_decimals_below_eight() -> None:
    assert _numerical_match(0.0, 0.0, 7, 0.0) is None


# ------------------------------------------- V0.3 amendments P-1 and P-2 in the JSON (A7)
REPORTING = {
    "disclosure": {
        "amendment": "P-1",
        "shared": "prereg.shareable",
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
    for bad in (
        {**PREREG, "reporting": {**REPORTING, "extra": 1}},
        {**PREREG, "reporting": {"disclosure": REPORTING["disclosure"]}},
        {
            **PREREG,
            "reporting": {
                **REPORTING,
                "spot_check_gating": {**REPORTING["spot_check_gating"], "tracks": ["independent"]},
            },
        },
    ):
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(bad, schema, cls=jsonschema.Draft202012Validator)


def test_the_runner_withholds_targets_until_the_spot_check_is_signed() -> None:
    cells = [
        pl.Cell("c1", "S_zz", "agrees"),
        pl.Cell("c2", "S_zz", "disagrees", reviewed=True),
        pl.Cell("c3", "S_zz", "pending", "rank-unverified"),
        pl.Cell("c4", "S_zz", "pending", "no-target"),
    ]
    checked = "a" * 64
    gated = prereg.spot_check_gate(cells, receipt_sha256=None, checked_sha256=checked, prereg=PREREG)
    assert [(c.status, c.reason) for c in gated] == [
        ("pending", "no-target"),
        ("pending", "no-target"),
        ("pending", "rank-unverified"),
        ("pending", "no-target"),
    ]
    stale = prereg.spot_check_gate(cells, receipt_sha256="b" * 64, checked_sha256=checked, prereg=PREREG)
    assert [c.status for c in stale] == ["pending"] * 4
    assert prereg.spot_check_gate(cells, receipt_sha256=checked, checked_sha256=checked, prereg=PREREG) == cells
    # The original protocol had no gating: a report made under it is unchanged.
    original = {k: v for k, v in PREREG.items() if k != "reporting"}
    assert prereg.spot_check_gate(cells, receipt_sha256=None, checked_sha256=checked, prereg=original) == cells


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


def _workflow_filters() -> list[str]:
    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8"))
    trigger = workflow.get("on", workflow.get(True))  # YAML 1.1 reads a bare `on` as True
    tags: list[str] = trigger["push"]["tags"]
    return tags


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


def test_the_release_workflow_uses_exactly_the_approved_filters() -> None:
    filters = _workflow_filters()
    if filters == ["v*"]:
        pytest.xfail("V1.5c lands the release-trigger guard")
    assert filters == APPROVED_FILTERS
    assert all(_triggers(t, filters) for t in PACKAGE_TAGS)
    assert not any(_triggers(t, filters) for t in OTHER_TAGS)
