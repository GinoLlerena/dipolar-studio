"""The V1.5 verification report (docs/phase2/v1.5-plan.md, V1.5b) and the V1.5a gate rules
(docs/phase2/verification/gates.md).

Two kinds of output, through separate paths (V0.3 §6):

- **local detail** (``run_report``, ``write_local``): per-cell targets, fits, signed discrepancies
  and margins, and per-condition diagnostics. It is written only under ``datasets-local/``.
- **shared output** (``shared_output``, ``page_lines``): per track, each label with its counts,
  the drop-one labels, fragility, the notes and the protocol revision. No per-cell value.

The comparison follows the plan's frozen procedure: verify the inputs against their frozen
hashes and bind them to the frozen roster; fit one condition at a time through the registry's
fixed-geometry path; convert to the paper's frame with the full covariance; classify with P-2's
gating (``pr.classify_gated``) and aggregate with ``pr.dataset_report``. The authors'
analysis track stays pending until its four inputs are documented (V0.3 §6).

The first-fit gate: ``run_report`` refuses to fit without the owner's submission record for this
dataset at this protocol revision, made before the submission (V1.5a).

Run by the owner, on the owner's machine (it prints only the shared output)::

    uv run --locked python tools/validation/verification.py --dataset benzene-taggar2006 \\
        --submission datasets-local/benzene-taggar2006-targets/submission.json \\
        [--receipt datasets-local/benzene-taggar2006-targets/spot-check-receipt.json] \\
        [--reviews datasets-local/benzene-taggar2006-targets/reviews.json] \\
        --out datasets-local/benzene-taggar2006-targets/verification-v1.5.md
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

import first_fit_log as ffl
import numpy as np
import prereg as pr
import prereg_labels as pl

# =========================================================== the V1.5a gate rules (gates.md)
#: The four-value Verification field (decision 4).
VERIFICATION_VALUES = ("pending", "synthetic-only", "experimentally supported", "unresolved failure")
#: V0.3 §7 dataset label → (verification value, annotation). Decision 4A.
_CROSSWALK: dict[str, tuple[str, str | None]] = {
    "pending": ("pending", None),
    "partially supported": ("pending", None),
    "experimentally supported": ("experimentally supported", None),
    "unresolved failure": ("unresolved failure", None),
    "explained discrepancy": ("unresolved failure", "explained, reviewed"),
}


def crosswalk(label: str) -> tuple[str, str | None]:
    """The Verification value and annotation for a V0.3 dataset label; any other label is refused."""
    if label not in _CROSSWALK:
        raise ValueError(f"not a V0.3 dataset label: {label!r}")
    return _CROSSWALK[label]


_FIELD = re.compile(r"^\*\*Verification:\*\* `([^`]+)`$")
_V03 = re.compile(
    r"^\*\*V0\.3 label:\*\* `([^`]+)` \(roster (\d+), compared (\d+), agreeing (\d+), "
    r"disagreeing (\d+), pending (\d+)\)$"
)


def _allowed_labels(compared: int, disagreeing: int, pending: int) -> set[str]:
    """The labels V0.3 §7 allows for these counts (a disagreement's review state is not in them)."""
    if disagreeing:
        return {"unresolved failure", "explained discrepancy"}
    if compared == 0:
        return {"pending"}
    return {"partially supported"} if pending else {"experimentally supported"}


def check_page(text: str, dataset: str | None = None) -> list[str]:
    """A report page's problems: exactly one Verification field with an allowed value, outside any
    code fence; for an experimental dataset exactly one V0.3 label line whose counts add up to the
    frozen roster, whose label the counts allow, and which the field crosswalks to; for any other
    page, no V0.3 line."""
    problems: list[str] = []
    prose: list[str] = []
    fenced = False
    for line in text.splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
            continue
        if fenced:
            if line.lstrip().startswith(("**Verification", "**V0.3")):
                problems.append("a field line inside a code fence")
            continue
        prose.append(line)
    fields = [line for line in prose if line.startswith("**Verification")]
    match = _FIELD.match(fields[0]) if len(fields) == 1 else None
    if len(fields) != 1:
        problems.append(f"{len(fields)} Verification lines, not one")
    elif match is None or match.group(1) not in VERIFICATION_VALUES:
        problems.append("the Verification field is not one of the four values")
    v03 = [line for line in prose if line.startswith("**V0.3 label")]
    if dataset is None:
        if v03:
            problems.append("a V0.3 label line on a page without an experimental comparison")
        return problems
    if len(v03) != 1 or (m := _V03.match(v03[0])) is None:
        problems.append(f"{len(v03)} V0.3 label lines, not one well-formed line")
        return problems
    label, *counts = m.groups()
    roster, compared, agreeing, disagreeing, pending = (int(c) for c in counts)
    if label not in _CROSSWALK:
        return [*problems, "the V0.3 label is not a dataset label"]
    if match is not None and crosswalk(label)[0] != match.group(1):
        problems.append("the Verification field is not the label's crosswalk")
    if roster != pr.load()["datasets"][dataset]["roster_cells"]:
        problems.append("the roster is not the frozen roster")
    if compared != agreeing + disagreeing or roster != compared + pending:
        problems.append("the counts do not add up")
    if label not in _allowed_labels(compared, disagreeing, pending):
        problems.append("the counts do not allow the label")
    return problems


# ------------------------------------------------------------- the first-fit chronology (§3)
DECISION_KEYS = (*(str(k) for k in range(1, 12)), "5a")
AMENDMENT_KEYS = ("P-1", "P-2")
DATASETS = ("benzene-taggar2006", "odcb-chandrakumar1993")
RUNNERS = ("owner", "participant", "agent")
OUTCOMES = ("succeeded", "failed")
SUBMISSION_FIELDS = frozenset({"dataset", "runner", "at", "outcome", "release_or_commit", "protocol_sha256"})


def _is_time(t: object) -> bool:
    return isinstance(t, datetime) and t.tzinfo is not None


def _submissions_ok(submissions: Sequence[Mapping[str, Any]]) -> bool:
    for s in submissions:
        if set(s) != SUBMISSION_FIELDS or not _is_time(s["at"]):
            return False
        if s["dataset"] not in DATASETS or s["runner"] not in RUNNERS or s["outcome"] not in OUTCOMES:
            return False
        if not s["release_or_commit"] or not isinstance(s["protocol_sha256"], str):
            return False
    return True


def _first_submission(ledger: Mapping[str, Any]) -> datetime | None:
    """The earliest submission, whatever its dataset, runner, outcome or place in the list."""
    return min((s["at"] for s in ledger["submissions"]), default=None)


def freeze_ok(ledger: Mapping[str, Any]) -> bool:
    """The V1.5a freeze holds: the no-fit attestation and every decision and amendment approval
    precede the freeze approval, every submission is fully recorded and strictly after it, and
    once anything is submitted the first result access is recorded and not before it."""
    freeze, attestation = ledger.get("freeze_approved"), ledger.get("attestation")
    if not _is_time(freeze) or not _is_time(attestation) or attestation > freeze:
        return False
    decisions, amendments = ledger["decisions"], ledger["amendments"]
    if set(decisions) != set(DECISION_KEYS) or set(amendments) != set(AMENDMENT_KEYS):
        return False
    if any(not _is_time(t) or t > freeze for t in [*decisions.values(), *amendments.values()]):
        return False
    if not _submissions_ok(ledger["submissions"]):
        return False
    first = _first_submission(ledger)
    if first is None:
        return True
    if not first > freeze:
        return False
    access = ledger.get("first_access")
    if access is None:
        return False
    return access == "none-yet" or (_is_time(access) and access >= first)


def classify_amendment(made: datetime, ledger: Mapping[str, Any]) -> str:
    """``pre-fit`` before the first submission; ``after-submission`` from then on while the ledger
    establishes that no result had been accessed; otherwise (at or after first access, or access
    not recorded) ``post hoc``."""
    first = _first_submission(ledger)
    if first is None or made < first:
        return "pre-fit"
    access = ledger.get("first_access")
    if access == "none-yet" or (_is_time(access) and made < access):
        return "after-submission"
    return "post hoc"


# --------------------------------------------------------------- the exit matrix (§7)
EXIT_REQUIREMENTS: dict[str, dict[str, tuple[str, ...]]] = {
    "V0.1 selection and rights": {"tests": ("tests/test_v0_corpus.py",), "receipts": ("staged-index scans",)},
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
_EXIT_FIELDS = frozenset({"criterion", "tests", "receipts"})


def check_exit(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    """The exit matrix's gaps: every criterion exactly once, each of its tests ``passed`` (a skip
    or an xfail is not a pass), and each of its receipts recorded and non-empty."""
    problems = []
    named = Counter(str(r.get("criterion")) for r in rows)
    if set(named) != set(EXIT_REQUIREMENTS) or any(n != 1 for n in named.values()):
        problems.append("the rows are not the exit criteria, each once")
    for row in rows:
        if set(row) != _EXIT_FIELDS:
            problems.append(f"{row.get('criterion')!r}: fields other than criterion, tests and receipts")
            continue
        required = EXIT_REQUIREMENTS.get(row["criterion"])
        if required is None:
            continue
        for test in required["tests"]:
            if row["tests"].get(test) != "passed":
                problems.append(f"{row['criterion']}: {test} has not passed")
        for receipt in required["receipts"]:
            if not row["receipts"].get(receipt):
                problems.append(f"{row['criterion']}: no receipt for {receipt}")
    return problems


# ------------------------------------------- the external evidence checklist (§8, decision 9)
_RECORD_FIELDS = frozenset(
    {
        "participant",
        "eligible",
        "release_tag",
        "commit",
        "protocol_sha256",
        "si_sha256_matches",
        "geometry_computed",
        "conditions",
        "counts",
        "success_claimed",
    }
)
_COUNT_FIELDS = frozenset({"compared", "agreeing", "disagreeing", "pending"})
_PARTICIPANT_ID = re.compile(r"P-\d{3}")


def check_participant(record: Mapping[str, Any], *, trusted: Mapping[str, Any]) -> list[str]:
    """An outside record's problems. The closed fields apply at every level, to every attempt; a
    success claim must match what the owner supplies (``trusted``): the release, commit and
    protocol revision, the full roster each with a numerical match, the owner's signed benzene
    receipt, and the published counts, which must be complete and consistent."""
    problems = []
    if set(record) - _RECORD_FIELDS:
        problems.append("fields outside the closed record")
    conditions = record.get("conditions", {})
    if not isinstance(conditions, Mapping) or any(
        not isinstance(c, Mapping) or set(c) != {"numerical_match"} for c in conditions.values()
    ):
        problems.append("condition entries outside the closed fields")
    counts = record.get("counts", {})
    if not isinstance(counts, Mapping) or set(counts) - _COUNT_FIELDS:
        problems.append("count entries outside the closed fields")
    if not _PARTICIPANT_ID.fullmatch(str(record.get("participant"))):
        problems.append("the participant is not an opaque ID")
    if problems or not record.get("success_claimed"):
        return problems
    for flag in ("eligible", "si_sha256_matches", "geometry_computed"):
        if record.get(flag) is not True:
            problems.append(f"{flag} is not true")
    for key in ("release_tag", "commit", "protocol_sha256"):
        if record.get(key) != trusted[key]:
            problems.append(f"{key} is not the owner's")
    if not trusted.get("spot_check_receipt_sha256"):
        problems.append("the owner's benzene spot-check receipt is not signed")
    if sorted(conditions) != sorted(trusted["roster"]) or not all(
        c["numerical_match"] is True for c in conditions.values()
    ):
        problems.append("the conditions are not the full roster, each with a numerical match")
    published = trusted["published_counts"]
    if (
        published["compared"] != len(trusted["roster"])
        or published["pending"] != 0
        or published["compared"] != published["agreeing"] + published["disagreeing"]
    ):
        problems.append("the published counts are not complete")
    if dict(counts) != dict(published):
        problems.append("the counts are not the published counts")
    return problems


# ======================================================================= the report workflow
#: A registry client: an operation's result, or ``RegistryError``.
Call = Callable[[str, dict[str, Any] | None], dict[str, Any]]
FIXED_MODEL = {"kind": "fixed", "order": "point-group", "frame": "symmetry"}
# ------------------------------------------------------- the runner's authorization (round 83, A1)
#: Who may run a comparison: the owner, or an outside participant (plan, V1.5d). An agent may not.
AUTHORIZED_RUNNERS = ("owner", "participant")


def _now() -> datetime:
    """The runner's clock, in UTC."""
    return datetime.now(UTC)


def chronology(entries: Sequence[ffl.Entry]) -> dict[str, Any]:
    """The first-fit log as ``freeze_ok`` reads it. Each decision and amendment counts at its
    latest approval or change; every submission counts as an attempt, whatever its outcome."""

    def times(event: str) -> list[datetime]:
        return [e.at for e in entries if e.event == event]

    decided = times("decisions approved") + times("decision changed")
    amended = times("amendments approved")
    attested, frozen, accessed = times("no-fit attestation"), times("freeze approved"), times("first access")
    return {
        "attestation": attested[0] if attested else None,
        "freeze_approved": frozen[0] if frozen else None,
        "decisions": dict.fromkeys(DECISION_KEYS, max(decided)) if decided else {},
        "amendments": dict.fromkeys(AMENDMENT_KEYS, max(amended)) if amended else {},
        "submissions": [
            {
                "dataset": e.dataset,
                "runner": e.runner,
                "at": e.at,
                "outcome": "succeeded",
                "release_or_commit": e.release_or_commit,
                "protocol_sha256": e.protocol_sha256,
            }
            for e in ffl.submissions(entries)
        ],
        "first_access": accessed[0] if accessed else "none-yet",
    }


def authorize(submission: object, ledger: str, *, now: datetime) -> list[str]:
    """Why ``submission`` may not be fitted, judged by the ledger's first-fit log (gates.md §10);
    an empty list when it may. Value-free."""
    try:
        entries = ffl.parse(ledger)
    except ValueError as exc:
        return [f"the ledger's first-fit log cannot be read: {exc}"]
    problems = []
    if not any(e.event == "freeze approved" for e in entries):
        problems.append("the first-fit log has no 'freeze approved' row: no fit is authorized before the freeze")
    elif not freeze_ok(chronology(entries)):
        problems.append("the first-fit log's chronology does not hold (freeze_ok)")
    if (
        not isinstance(submission, Mapping)
        or set(submission) != REPORT_SUBMISSION_FIELDS
        or not _is_time(submission.get("at"))
    ):
        return [
            *problems,
            "no submission record with exactly the fields " + ", ".join(sorted(REPORT_SUBMISSION_FIELDS)),
        ]
    if submission["runner"] not in AUTHORIZED_RUNNERS:
        problems.append("only the owner or a participant may run a comparison")
    at = submission["at"].astimezone(UTC)
    if at > now:
        problems.append("the submission time is in the future")
    logged = {(e.dataset, e.runner, e.at, e.release_or_commit, e.protocol_sha256) for e in ffl.submissions(entries)}
    key = (
        submission["dataset"],
        submission["runner"],
        at,
        submission["release_or_commit"],
        submission["protocol_sha256"],
    )
    if key not in logged:
        problems.append("the submission is not logged in the first-fit log with exactly these fields")
    return problems


def committed_ledger(root: Path) -> str | None:
    """The ledger as committed at ``HEAD`` (what the owner logged and committed), or None."""
    shown = subprocess.run(["git", "show", f"HEAD:{ffl.LEDGER}"], cwd=root, capture_output=True)
    return shown.stdout.decode("utf-8") if shown.returncode == 0 else None


TRACKS = ("independent", "reproduction")
#: The fitted V1 components, in the order the conversion matrix takes them (V0.3 §5).
_V1_NAMES = ("Szz", "Sxx-Syy")
#: s5 = b / ORTHO_SCALE: the named components' scale in the orthonormal basis b (V0.3 §3, J).
_J = (1 / math.sqrt(1.5), math.sqrt(2.0))
REPORT_SUBMISSION_FIELDS = frozenset({"dataset", "runner", "at", "release_or_commit", "protocol_sha256"})
REVIEW_KEY_FIELDS = ("dataset", "track", "condition", "component", "protocol_sha256")
UNAVAILABLE, BLOCKED, COMPLETE = "local evidence unavailable", "blocked", "complete"


class RegistryError(RuntimeError):
    """An operation failed: named by operation and error code, never by the values it carried."""

    def __init__(self, operation: str, code: str) -> None:
        super().__init__(f"{operation} failed: {code}")
        self.operation, self.code = operation, code


def local_call() -> Call:
    """The in-process Python adapter over a fresh session, as a script principal."""
    from dipolar_app.client import LocalClient
    from dipolar_app.jobs import JobRunner
    from dipolar_app.operations import build_registry
    from dipolar_app.policy import Principal, Tier
    from dipolar_app.registry import CONTRACT_VERSION
    from dipolar_app.session import Session

    session = Session(None, contract_version=CONTRACT_VERSION)
    JobRunner(session, mode="thread")
    client = LocalClient(
        build_registry(), session, Principal(actor="script:verification", tier=Tier.APPLY, human=False)
    )

    def call(name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
        envelope = client.call(name, args or {})
        if not envelope["ok"]:
            raise RegistryError(name, str(envelope["error"]["code"]))
        result: dict[str, Any] = envelope["result"]
        return result

    return call


# ------------------------------------------------------------------------- the inputs
def _paths(dataset: str, p: Mapping[str, Any]) -> dict[str, str]:
    d = p["datasets"][dataset]
    return {"couplings": d["couplings"]["path"], "targets": d["targets"]["path"]}


def check_inputs(dataset: str, *, prereg: Mapping[str, Any], root: Path) -> list[str]:
    """The inputs' problems, by path: absent, or not at the frozen SHA-256."""
    problems = []
    for which, rel in _paths(dataset, prereg).items():
        path = root / rel
        if not path.is_file():
            problems.append(f"{rel}: absent")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != prereg["datasets"][dataset][which]["sha256"]:
            problems.append(f"{rel}: the SHA-256 is not the frozen one")
    return problems


def _verified_rows(dataset: str, which: str, p: Mapping[str, Any], root: Path) -> tuple[str, list[dict[str, str]]]:
    rel = p["datasets"][dataset][which]["path"]
    path = root / rel
    if not path.is_file():
        raise FileNotFoundError(rel)
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != p["datasets"][dataset][which]["sha256"]:
        raise ValueError(f"{rel}: the SHA-256 is not the frozen one")
    return rel, list(csv.DictReader(data.decode("utf-8").splitlines()))


def _number(text: str | None, where: str, *, positive: bool = False) -> float:
    """A finite number (positive, for σ and precision). The message names the place, never the text."""
    try:
        x = float((text or "").strip().replace("−", "-"))
    except ValueError:
        raise ValueError(f"{where}: not a number") from None
    if not math.isfinite(x) or (positive and x <= 0):
        raise ValueError(f"{where}: not a {'positive, ' if positive else ''}finite number")
    return x


def _columns(rows: list[dict[str, str]], rel: str, needed: Iterable[str]) -> None:
    missing = [c for c in needed if not rows or c not in rows[0]]
    if missing:
        raise ValueError(f"{rel}: missing columns {missing}")


def _condition_columns(dataset: str, p: Mapping[str, Any]) -> tuple[str, str]:
    return ("run", "sample") if p["datasets"][dataset]["targets"]["form"] == "table" else ("table", "T_K")


def read_couplings(dataset: str, *, prereg: Mapping[str, Any], root: Path) -> dict[str, dict[str, tuple[float, float]]]:
    """condition → {orbit key: (D, σ)} in Hz, hash-verified and bound to the frozen roster: each
    frozen condition has exactly the frozen orbit keys once, D signed and finite, σ positive. The
    couplings enter as printed: no sign change, no factor of two, no J subtracted."""
    d = prereg["datasets"][dataset]
    rel, rows = _verified_rows(dataset, "couplings", prereg, root)
    a, b = _condition_columns(dataset, prereg)
    d_col = "D_obs_Hz" if d["targets"]["form"] == "table" else "D_Hz"
    _columns(rows, rel, (a, b, "coupling", d_col, "sigma_Hz"))
    out: dict[str, dict[str, tuple[float, float]]] = {}
    for n, row in enumerate(rows, start=2):
        key, orbit = f"{row[a]}/{row[b]}", row["coupling"]
        if orbit not in d["orbits"]:
            raise ValueError(f"{rel}:{n}: an unknown coupling key")
        if orbit in out.setdefault(key, {}):
            raise ValueError(f"{rel}:{n}: the condition's coupling is repeated")
        where = f"{rel}:{n}"
        out[key][orbit] = (
            _number(row[d_col], f"{where} {d_col}"),
            _number(row["sigma_Hz"], f"{where} sigma_Hz", positive=True),
        )
    roster = prereg_conditions(dataset, prereg, root)
    if sorted(out) != roster:
        raise ValueError(f"{rel}: the conditions are not the frozen roster")
    for key, couplings in out.items():
        if set(couplings) != set(d["orbits"]):
            raise ValueError(f"{rel}: condition {key} does not have every frozen orbit")
    return {key: {orbit: out[key][orbit] for orbit in d["orbits"]} for key in roster}


def prereg_conditions(dataset: str, p: Mapping[str, Any], root: Path) -> list[str]:
    """The frozen conditions, sorted, from the hash-verified couplings file (``pr.frozen_roster``)."""
    return sorted({c for c, _ in pr.frozen_roster(dataset, dict(p), root)})


def read_targets(
    dataset: str, *, prereg: Mapping[str, Any], root: Path
) -> dict[tuple[str, str], tuple[float, float] | None]:
    """(condition, estimand) → (value, precision), or None for a pending target; hash-verified and
    covering the frozen roster exactly once. Benzene's precision is the printed σ; o-DCB's the
    digitization precision."""
    d = prereg["datasets"][dataset]
    rel, rows = _verified_rows(dataset, "targets", prereg, root)
    a, b = _condition_columns(dataset, prereg)
    out: dict[tuple[str, str], tuple[float, float] | None] = {}
    table = d["targets"]["form"] == "table"
    _columns(rows, rel, (a, b, "S_zz", "sigma") if table else (a, b, "component", "value", "precision", "status"))
    for n, row in enumerate(rows, start=2):
        where = f"{rel}:{n}"
        component = "S_zz" if table else row["component"]
        key = (f"{row[a]}/{row[b]}", component)
        if component not in d["estimands"]:
            raise ValueError(f"{where}: an unknown estimand")
        if key in out:
            raise ValueError(f"{where}: the cell is repeated")
        if table:
            out[key] = (_number(row["S_zz"], f"{where} S_zz"), _number(row["sigma"], f"{where} sigma", positive=True))
        elif row["status"] == "target":
            out[key] = (
                _number(row["value"], f"{where} value"),
                _number(row["precision"], f"{where} precision", positive=True),
            )
        elif row["status"] == "pending":
            out[key] = None
        else:
            raise ValueError(f"{where}: an unknown target status")
    roster = pr.frozen_roster(dataset, dict(prereg), root)
    if set(out) != set(roster):
        raise ValueError(f"{rel}: the target cells are not the frozen roster")
    return {k: out[k] for k in roster}


# ---------------------------------------------------------------- geometry and the fit
def declared_geometry(dataset: str, p: Mapping[str, Any]) -> tuple[list[str], np.ndarray, dict[str, int]]:
    """The declared geometry (V0.3 §2) in the paper's frame, z normal to the ring: six carbons on a
    regular hexagon of side r_CC, and each named proton radially on its carbon at r_CC + r_CH. For
    o-DCB (the benzene-based idealization) chlorine enters no coupling and is not placed."""
    g, d = p["geometry"], p["datasets"][dataset]
    r_cc, r_h = g["r_cc_angstrom"], g["r_cc_angstrom"] + g["r_ch_angstrom"]
    elements = ["C"] * 6
    rows = [[r_cc * math.cos(math.radians(60 * k)), r_cc * math.sin(math.radians(60 * k)), 0.0] for k in range(6)]
    index = {}
    for name, deg in d["ring_positions"].items():
        a = math.radians(deg)
        index[name] = len(elements)
        elements.append("H")
        rows.append([r_h * math.cos(a), r_h * math.sin(a), 0.0])
    return elements, np.array(rows), index


def symmetry_declaration(dataset: str, p: Mapping[str, Any]) -> dict[str, Any]:
    """The point group with V1's axes as rows in the paper's coordinates (the frozen frame map)."""
    d = p["datasets"][dataset]
    return {"point_group": d["point_group"], "axes": [[float(x) for x in row] for row in d["frame_map_matrix"]]}


def fit_condition(
    call: Call, dataset: str, p: Mapping[str, Any], observations: Mapping[str, tuple[float, float]]
) -> dict[str, Any]:
    """One condition through the registry's fixed-geometry path (plan, step 2): ``project.import_xyz``,
    ``molecule.set_symmetry``, ``model.set``, ``couplings.reconcile`` and ``couplings.import`` with
    the confirmed mapping, ``fit.run``, ``job.wait``, ``run.get``. Returns the run's wire result."""
    d = p["datasets"][dataset]
    if set(observations) != set(d["orbits"]):
        raise ValueError("the observations are not the frozen orbits")
    elements, xyz, index = declared_geometry(dataset, p)
    text = "\n".join(
        [str(len(elements)), f"{dataset}: the declared geometry"]
        + [f"{e} {x!r} {y!r} {z!r}" for e, (x, y, z) in zip(elements, xyz.tolist(), strict=True)]
    )
    lines = ["spin_a,spin_b,D_obs_Hz,sigma_Hz"]
    for orbit, (a, b) in d["orbits"].items():
        value, sigma = observations[orbit]
        lines.append(f"{a},{b},{value!r},{sigma!r}")
    couplings = "\n".join(lines) + "\n"

    revision = call("render.describe_view", None)["science_revision"]
    revision = call("project.import_xyz", {"xyz": text + "\n", "name": dataset, "expected_science_revision": revision})[
        "science_revision"
    ]
    revision = call(
        "molecule.set_symmetry",
        {"symmetry": symmetry_declaration(dataset, p), "expected_science_revision": revision},
    )["science_revision"]
    revision = call("model.set", {**FIXED_MODEL, "expected_science_revision": revision})["science_revision"]
    spin_of_atom = {s["atom"]: s["id"] for s in call("project.describe", None)["spins"]}
    names = sorted({name for pair in d["orbits"].values() for name in pair})
    mapping = {name: spin_of_atom[index[name]] for name in names}
    diff = call("couplings.reconcile", {"csv": couplings, "mapping": mapping})
    if not diff["complete"]:
        raise RegistryError("couplings.reconcile", "INCOMPLETE_MAPPING")
    revision = call(
        "couplings.import", {"csv": couplings, "confirmed_mapping": mapping, "expected_science_revision": revision}
    )["science_revision"]
    job = call("fit.run", {"expected_science_revision": revision})["job"]
    while True:
        waited = call("job.wait", {"job_id": job["id"], "timeout_s": 30})
        if waited["finished"]:
            break
    if waited["job"]["status"] != "succeeded":
        raise RegistryError("fit.run", str((waited["job"].get("error") or {}).get("code", "FAILED")))
    result: dict[str, Any] = call("run.get", {"run_id": waited["job"]["run_id"]})["result"]
    if result["model"]["kind"] != "fixed" or result["n_obs"] != len(d["orbits"]):
        raise RegistryError("run.get", "NOT_THE_FIXED_FIT")
    if result["provenance"]["fit_version"] != p["model"]["fixed_fit_version"]:
        raise RegistryError("run.get", "NOT_THE_FROZEN_FIT_VERSION")
    return result


@dataclass(frozen=True)
class PaperFit:
    """One condition's fit in the paper's frame. Every error is conditional on σ as printed."""

    rank_verified: bool
    estimates: Mapping[str, float | None]
    covariance: tuple[tuple[float, ...], ...] | None = None
    se: Mapping[str, float] | None = None
    scaled_se: Mapping[str, float] | None = None  # descriptive: se·√(χ²/ν)
    chi2: float | None = None
    nu: int | None = None
    p_value: float | None = None
    adequacy: str | None = None
    ratio_residuals: tuple[float, ...] = field(default=())


def paper_covariance(
    dataset: str, p: Mapping[str, Any], covariance_b: Mapping[str, Any] | None
) -> tuple[tuple[float, ...], ...] | None:
    """Σ_paper = M J Σ_b J Mᵀ (V0.3 §3): the wire's matrix is in its own basis (``basis_b``), so the
    full orthonormal Σ_b = C Σ Cᵀ is rebuilt first, then its named block is taken."""
    if covariance_b is None:
        return None
    k = len(p["datasets"][dataset]["estimands"])
    c = np.array(covariance_b["basis_b"], dtype=float).T
    full = c @ np.array(covariance_b["matrix"], dtype=float) @ c.T
    j = np.diag(_J[:k])
    m = np.array(p["datasets"][dataset]["conversion_matrix"], dtype=float)
    out = m @ j @ full[:k, :k] @ j @ m.T
    return tuple(tuple(float(x) for x in row) for row in out)


def paper_fit(dataset: str, p: Mapping[str, Any], result: Mapping[str, Any]) -> PaperFit:
    """The wire result in the paper's frame: estimates through the conversion matrix, the full
    covariance, the conditional and the scaled standard errors, adequacy and ratio residuals. An
    unverified rank estimates no named component (V1.0 D-8)."""
    estimands = list(p["datasets"][dataset]["estimands"])
    adequacy = result["adequacy"]
    chi2, nu = float(adequacy["chi2"]), int(adequacy["nu"])
    rows = result["rows"]
    observed = [r["observed"]["value"] for r in rows]
    predicted = [r["predicted"]["value"] for r in rows]
    ratios = (
        tuple(float(observed[i] / observed[0] - predicted[i] / predicted[0]) for i in range(1, len(rows)))
        if observed and observed[0] and predicted[0]
        else ()
    )
    common = {
        "chi2": chi2,
        "nu": nu,
        "p_value": adequacy["p_value"],
        "adequacy": adequacy["status"],
        "ratio_residuals": ratios,
    }
    by_name = {c["name"]: c for c in result["components"]}
    v1 = [by_name.get(name, {}) for name in _V1_NAMES[: len(estimands)]]
    if not result["rank"]["verified"] or any(c.get("status") != "estimated" or c.get("estimate") is None for c in v1):
        return PaperFit(rank_verified=False, estimates=dict.fromkeys(estimands), **common)
    m = np.array(p["datasets"][dataset]["conversion_matrix"], dtype=float)
    est = m @ np.array([float(c["estimate"]) for c in v1])
    covariance = paper_covariance(dataset, p, result["covariance_b"])
    if covariance is None:
        raise ValueError("a verified rank without a covariance")
    se = {e: math.sqrt(covariance[i][i]) for i, e in enumerate(estimands)}
    scaled = {e: s * math.sqrt(chi2 / nu) for e, s in se.items()} if nu > 0 else None
    return PaperFit(
        rank_verified=True,
        estimates={e: float(est[i]) for i, e in enumerate(estimands)},
        covariance=covariance,
        se=se,
        scaled_se=scaled,
        **common,
    )


# ------------------------------------------------------------------- the comparison
def _roster_of(dataset: str, p: Mapping[str, Any], targets: Mapping[tuple[str, str], Any]) -> list[tuple[str, str]]:
    estimands = list(p["datasets"][dataset]["estimands"])
    conditions = sorted({c for c, _ in targets})
    roster = [(c, e) for c in conditions for e in estimands]
    if set(roster) != set(targets) or len(conditions) != p["datasets"][dataset]["conditions"]:
        raise ValueError("the targets are not a full roster")
    return roster


def independent_cells(
    dataset: str,
    p: Mapping[str, Any],
    fits: Mapping[str, PaperFit],
    targets: Mapping[tuple[str, str], tuple[float, float] | None],
    *,
    receipt: Mapping[str, str] | None,
    reviewed: Iterable[tuple[str, str]] = (),
) -> list[pl.Cell]:
    """The independent-support cells in roster order, through ``pr.classify_gated`` (P-2):
    the anisotropy's margin uses the same condition's published S_zz."""
    roster = _roster_of(dataset, p, targets)
    if set(fits) != {c for c, _ in roster}:
        raise ValueError("the fits are not the roster's conditions")
    done = set(reviewed)
    cells = []
    for condition, component in roster:
        fit = fits[condition]
        zz = targets.get((condition, "S_zz"))
        cells.append(
            pr.classify_gated(
                condition,
                component,
                dataset=dataset,
                receipt=dict(receipt) if receipt is not None else None,
                prereg=dict(p),
                rank_verified=fit.rank_verified,
                target=targets[(condition, component)],
                s=fit.estimates.get(component),
                s_zz_pub=None if component == "S_zz" or zz is None else zz[0],
                reviewed=(condition, component) in done,
            )
        )
    return cells


def _review_key(entry: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(str(entry[f]) for f in REVIEW_KEY_FIELDS)


def review_coverage(
    disagreeing: Iterable[Mapping[str, Any]], annex: Iterable[Mapping[str, Any]], receipts: Iterable[Mapping[str, Any]]
) -> list[str]:
    """Exact one-to-one coverage of the disagreeing (dataset, track, condition, component,
    protocol) keys by the local annex and by the linked public review receipts: missing,
    duplicate, stale or unrelated entries, and entries with other fields, are problems."""
    want = {_review_key(k) for k in disagreeing}
    problems = []
    for name, entries in (("annex", list(annex)), ("receipts", list(receipts))):
        if any(set(e) != set(REVIEW_KEY_FIELDS) for e in entries):
            problems.append(f"{name}: an entry with fields other than {list(REVIEW_KEY_FIELDS)}")
            continue
        counts = Counter(_review_key(e) for e in entries)
        problems += [f"{name}: {k[2]} {k[3]} ({k[1]}) is listed twice" for k, n in counts.items() if n > 1]
        problems += [f"{name}: no entry for {k[2]} {k[3]} ({k[1]})" for k in sorted(want - set(counts))]
        problems += [
            f"{name}: {k[2]} {k[3]} ({k[1]}) is stale or not a disagreement" for k in sorted(set(counts) - want)
        ]
    return problems


def _check_submission(submission: object, dataset: str, protocol: str) -> dict[str, Any]:
    if not isinstance(submission, Mapping) or set(submission) != REPORT_SUBMISSION_FIELDS:
        raise ValueError("no submission record with exactly the fields " + ", ".join(sorted(REPORT_SUBMISSION_FIELDS)))
    at = submission["at"]
    if submission["dataset"] != dataset or submission["protocol_sha256"] != protocol:
        raise ValueError("the submission record is not for this dataset at this protocol revision")
    if submission["runner"] not in RUNNERS or not _is_time(at):
        raise ValueError("the submission record's runner or UTC time is not valid")
    if not isinstance(submission["release_or_commit"], str) or not submission["release_or_commit"].strip():
        raise ValueError("the submission record names no release or commit")
    stamp = at.astimezone(UTC)
    text = stamp.strftime("%Y-%m-%dT%H:%MZ") if not (stamp.second or stamp.microsecond) else stamp.isoformat()
    return {**submission, "at": text}


def _cell_detail(
    cell: pl.Cell, fit: PaperFit, target: tuple[float, float] | None, zz: tuple[float, float] | None
) -> dict[str, Any]:
    """The local per-cell record: the target (None when absent or withheld), the fit, the signed
    discrepancy and the margin, beside the verdict."""
    s = fit.estimates.get(cell.component)
    out: dict[str, Any] = {
        "condition": cell.condition,
        "component": cell.component,
        "status": cell.status,
        "reason": cell.reason,
        "reviewed": cell.reviewed,
        "fit": s,
        "target": None,
        "precision": None,
        "discrepancy": None,
        "margin": None,
    }
    if target is None or cell.reason == "no-target":
        return out
    value, precision = target
    out.update(target=value, precision=precision)
    scale = abs(value) if cell.component == "S_zz" else (abs(zz[0]) if zz is not None else None)
    if s is not None:
        out["discrepancy"] = s - value
    if scale is not None:
        out["margin"] = pl.RELATIVE_TOLERANCE * scale + pl.PRECISION_FACTOR * precision
    return out


def run_report(
    dataset: str,
    *,
    call: Call,
    prereg: Mapping[str, Any],
    root: Path,
    submission: Mapping[str, Any] | None,
    receipt: Mapping[str, str] | None = None,
    reviews: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
) -> dict[str, Any]:
    """The local report of one dataset. Absent inputs: ``local evidence unavailable``; changed or
    malformed inputs, or a protocol that fails its closed schema or ``prereg.validate``:
    ``blocked``; neither fits anything nor makes a label. The command (``main``) runs it only for
    a submission that ``authorize`` accepts against the committed first-fit log (round 83, A1);
    any other caller is responsible for the same check."""
    p = dict(prereg)
    protocol = _protocol(p)
    base: dict[str, Any] = {"dataset": dataset, "protocol_sha256": protocol}
    base["submission"] = _check_submission(submission, dataset, protocol)
    invalid = check_protocol(p)  # round 83 (A6): before anything is read or fitted
    if invalid:
        return {**base, "status": BLOCKED, "problems": invalid}
    missing = [rel for rel in _paths(dataset, p).values() if not (root / rel).is_file()]
    if missing:
        return {**base, "status": UNAVAILABLE, "missing": missing}
    problems = check_inputs(dataset, prereg=p, root=root)
    if problems:
        return {**base, "status": BLOCKED, "problems": problems}
    try:
        observed = read_couplings(dataset, prereg=p, root=root)
        targets = read_targets(dataset, prereg=p, root=root)
    except ValueError as exc:
        return {**base, "status": BLOCKED, "problems": [str(exc)]}

    results = {condition: fit_condition(call, dataset, p, obs) for condition, obs in observed.items()}
    fits = {condition: paper_fit(dataset, p, result) for condition, result in results.items()}
    first = independent_cells(dataset, p, fits, targets, receipt=receipt)
    disagreeing = [
        dict(zip(REVIEW_KEY_FIELDS, (dataset, "independent", c.condition, c.component, protocol), strict=True))
        for c in first
        if c.status == "disagrees"
    ]
    review_problems: list[str] = []
    if disagreeing or reviews:
        review_problems = review_coverage(
            disagreeing, (reviews or {}).get("annex", []), (reviews or {}).get("receipts", [])
        )
    reviewed = [] if review_problems else [(k["condition"], k["component"]) for k in disagreeing]
    independent = independent_cells(dataset, p, fits, targets, receipt=receipt, reviewed=reviewed)
    reproduction = [
        pl.classify_reproduction(
            c, e, mode="pending", rank_verified=fits[c].rank_verified, s=fits[c].estimates.get(e), target=None
        )
        for c, e in _roster_of(dataset, p, targets)
    ]
    signed = pr.spot_check_signed(dataset, dict(receipt) if receipt is not None else None, p)
    shown = targets if signed else dict.fromkeys(targets)
    return {
        **base,
        "status": COMPLETE,
        "spot_check_signed": signed,
        "tracks": {
            "independent": pr.dataset_report(dataset, independent, p, root),
            "reproduction": pr.dataset_report(dataset, reproduction, p, root),
        },
        "track_labels": {
            "independent": p["criteria"]["independent"]["label"],
            "reproduction": pl.reproduction_track_label("pending"),
        },
        "cells": {
            "independent": [
                _cell_detail(c, fits[c.condition], shown[(c.condition, c.component)], shown.get((c.condition, "S_zz")))
                for c in independent
            ],
            "reproduction": [
                {"condition": c.condition, "component": c.component, "status": c.status, "reason": c.reason}
                for c in reproduction
            ],
        },
        "conditions": {
            condition: {
                "rank_verified": f.rank_verified,
                "estimates": dict(f.estimates),
                "se": dict(f.se) if f.se is not None else None,
                "scaled_se": dict(f.scaled_se) if f.scaled_se is not None else None,
                "covariance": f.covariance,
                "chi2": f.chi2,
                "nu": f.nu,
                "p_value": f.p_value,
                "adequacy": f.adequacy,
                "ratio_residuals": list(f.ratio_residuals),
                "provenance": _provenance(results[condition]),
            }
            for condition, f in fits.items()
        },
        "provenance": {"flags": p["datasets"][dataset]["flags"], "versions": _versions()},
        "notes": pr.label_notes(dataset, receipt=dict(receipt) if receipt is not None else None, prereg=p),
        "review_problems": review_problems,
    }


SCHEMA_PATH = Path(__file__).resolve().parents[2] / "docs" / "phase2" / "v0.3-preregistration.schema.json"


def check_protocol(p: Mapping[str, Any]) -> list[str]:
    """The protocol's closed schema and its cross-field invariants (``prereg.validate``), as
    value-free problems: a changed protocol is refused before any fit (round 83, A6)."""
    import jsonschema

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    problems = [
        "the protocol does not satisfy its closed schema at /" + "/".join(str(x) for x in error.absolute_path)
        for error in jsonschema.Draft202012Validator(schema).iter_errors(dict(p))
    ]
    return problems or [f"the protocol fails a cross-field check ({x})" for x in pr.validate(dict(p))]


def _provenance(result: Mapping[str, Any]) -> dict[str, Any]:
    """What identifies one fit (round 83, A6): its model, frame and estimand, the science hash, the
    fit version and numerical context, the symmetry, and its assumptions and warnings. Local only."""
    return {
        "model": result["model"],
        "frame": result["frame"],
        "estimand": result["estimand"],
        "science_hash": result["science_hash"],
        "fit_version": result["provenance"]["fit_version"],
        "numerical_context": result["provenance"]["numerical_context"],
        "symmetry": result["symmetry"],
        "assumptions": list(result["assumptions"]),
        "warnings": list(result["warnings"]),
    }


def _versions() -> dict[str, str]:
    from importlib.metadata import PackageNotFoundError, version

    out = {}
    for name in ("dipolar-core", "dipolar-app"):
        try:
            out[name] = version(name)
        except PackageNotFoundError:
            out[name] = "not installed"
    return out


def _protocol(p: Mapping[str, Any]) -> str:
    return pr.protocol_sha256(dict(p))


# ------------------------------------------------------------------------- the outputs
def shared_output(report: Mapping[str, Any]) -> dict[str, Any]:
    """What may leave the machine: per track the labels with their counts, the drop-one labels
    and fragility, the notes, the Verification value and the protocol revision. No per-cell value,
    fit, discrepancy, margin or diagnostic."""
    base = {"dataset": report["dataset"], "protocol_sha256": report["protocol_sha256"], "status": report["status"]}
    if report["status"] != COMPLETE:
        return base
    tracks = {}
    for name in TRACKS:
        shared = pr.shareable(report["tracks"][name])
        tracks[name] = {"label": report["track_labels"][name], "labels": shared["labels"], "fragile": shared["fragile"]}
    value, annotation = crosswalk(report["tracks"]["independent"]["full"].name)
    return {
        **base,
        "verification": value,
        "annotation": annotation,
        "tracks": tracks,
        "notes": list(report["notes"]),
        "spot_check_signed": bool(report["spot_check_signed"]),
    }


def page_lines(shared: Mapping[str, Any]) -> list[str]:
    """The page's Verification field and its V0.3 label line (the primary, full-data label)."""
    if shared.get("status") != COMPLETE:
        raise ValueError(f"no page lines for a report that is {shared.get('status')!r}")
    full = shared["tracks"]["independent"]["labels"]["full"]
    return [
        f"**Verification:** `{shared['verification']}`",
        f"**V0.3 label:** `{full['name']}` (roster {full['roster']}, compared {full['compared']}, "
        f"agreeing {full['agreeing']}, disagreeing {full['disagreeing']}, pending {full['pending']})",
    ]


def _local_path(path: Path, root: Path) -> Path:
    """``root/path`` when ``path`` lies under the checkout's own ``datasets-local/`` directory: no
    absolute path, no ``..``, and no link at any directory along it (round 83, A3: a linked
    directory can lead outside, wherever it resolves)."""
    parts = PurePosixPath(path.as_posix()).parts
    if path.is_absolute() or not parts or parts[0] != "datasets-local" or ".." in parts or len(parts) < 2:
        raise ValueError("local detail is written only under datasets-local/")
    current = root
    for part in parts[:-1]:
        current = current / part
        if current.is_symlink() or (current.exists() and not current.is_dir()):
            raise ValueError("local detail is written only into real directories under datasets-local/, not links")
    return root / path


def _write_local_text(path: Path, root: Path, text: str) -> Path:
    """Write ``text`` to the local ``path`` atomically: a new file renamed over the destination, so
    a link at the destination is replaced, never followed (round 83, A3)."""
    target = _local_path(path, root)
    current = root
    for part in PurePosixPath(path.as_posix()).parts[:-1]:
        current = current / part
        if not current.exists():
            current.mkdir()
    _local_path(path, root)  # again, now that the directories exist
    fd, temporary = tempfile.mkstemp(dir=target.parent, prefix=".tmp-", suffix=".part")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(temporary, target)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    return target


def _md(x: object) -> str:
    return "—" if x is None else repr(x) if isinstance(x, float) else str(x)


def write_local(report: Mapping[str, Any], path: Path, *, root: Path) -> Path:
    """The local detail as Markdown, under ``datasets-local/`` only (never tracked, never shared)."""
    _local_path(path, root)
    lines = [
        f"# Verification report (local): {report['dataset']}",
        "",
        "Local detail: restricted. Do not share, commit or quote (V0.3 §6).",
        "",
        f"- Protocol revision: `{report['protocol_sha256']}`",
        f"- Submission: `{json.dumps(report['submission'], sort_keys=True, default=str)}`",
        f"- Status: {report['status']}",
    ]
    if report["status"] != COMPLETE:
        lines += [f"- {x}" for x in [*report.get("missing", []), *report.get("problems", [])]]
    else:
        lines += [f"- Spot-check signed: {report['spot_check_signed']}", *[f"- Note: {n}" for n in report["notes"]]]
        lines.append(f"- Provenance: {json.dumps(report['provenance'], sort_keys=True)}")
        lines += [f"- Review problem: {x}" for x in report["review_problems"]]
        for name in TRACKS:
            lines += ["", f"## {report['track_labels'][name]}", ""]
            for key, label in report["tracks"][name].items():
                if isinstance(label, pl.Label):
                    lines.append(
                        f"- {key}: {label.name} (roster {label.roster}, compared {label.compared}, agreeing "
                        f"{label.agreeing}, disagreeing {label.disagreeing}, pending {label.pending})"
                    )
            lines.append(f"- fragile: {report['tracks'][name]['fragile']}")
        lines += ["", "## Cells (independent support)", ""]
        heads = [
            "condition",
            "component",
            "status",
            "reason",
            "reviewed",
            "target",
            "precision",
            "fit",
            "discrepancy",
            "margin",
        ]
        lines += ["| " + " | ".join(heads) + " |", "|" + "---|" * len(heads)]
        lines += ["| " + " | ".join(_md(c[h]) for h in heads) + " |" for c in report["cells"]["independent"]]
        lines += ["", "## Conditions (conditional on σ as printed; not part of any label)", ""]
        for condition, c in report["conditions"].items():
            lines.append(f"- {condition}: " + json.dumps(c, sort_keys=True, default=str))
    return _write_local_text(path, root, "\n".join(lines) + "\n")


#: The restricted-fit scan tier's source (tools/datasets/restricted_scan.py, FIT_DIR and FIT_SUFFIX).
FIT_DIR = "datasets-local/verification"
FIT_SUFFIX = ".fit-values.json"


def fit_values(report: Mapping[str, Any]) -> dict[str, Any]:
    """The full-precision fit values of a complete report, for the restricted-fit scan tier: every
    fitted condition's paper-frame estimates and every compared cell's discrepancy. Local only."""
    if report.get("status") != COMPLETE:
        raise ValueError(f"no fit values for a report that is {report.get('status')!r}")
    values = [
        {"condition": condition, "component": component, "quantity": "estimate", "value": float(x)}
        for condition, f in report["conditions"].items()
        for component, x in f["estimates"].items()
        if x is not None
    ]
    values += [
        {"condition": c["condition"], "component": c["component"], "quantity": "discrepancy", "value": float(d)}
        for c in report["cells"]["independent"]
        if (d := c["discrepancy"]) is not None
    ]
    return {
        "dataset": report["dataset"],
        "protocol_sha256": report["protocol_sha256"],
        "submission": dict(report["submission"]),
        "values": values,
    }


def write_fit_values(report: Mapping[str, Any], *, root: Path) -> Path:
    """``datasets-local/verification/<dataset>.fit-values.json`` (never tracked, never shared)."""
    record = fit_values(report)
    path = Path(FIT_DIR) / f"{record['dataset']}{FIT_SUFFIX}"
    target = _local_path(path, root)
    if target.is_file() and not target.is_symlink():
        # Round 83 (A2): a rerun keeps the earlier output, as retained/<dataset>.<n>.fit-values.json.
        kept = Path(FIT_DIR) / "retained"
        folder = _local_path(kept / "x", root).parent
        taken = [
            int(m.group(1)) for p in (folder.glob("*") if folder.is_dir() else []) if (m := _retained(p.name, record))
        ]
        _write_local_text(
            kept / f"{record['dataset']}.{max(taken, default=0) + 1}{FIT_SUFFIX}",
            root,
            target.read_text(encoding="utf-8"),
        )
    return _write_local_text(path, root, json.dumps(record, indent=1, allow_nan=False) + "\n")


def _retained(name: str, record: Mapping[str, Any]) -> re.Match[str] | None:
    return re.fullmatch(re.escape(str(record["dataset"])) + r"\.([1-9][0-9]*)" + re.escape(FIT_SUFFIX), name)


# --------------------------------------------------------------------------- the command
def _load_json(path: str | None) -> Any:
    return None if path is None else json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="The V1.5 verification report (owner-local).")
    parser.add_argument("--dataset", required=True, choices=DATASETS)
    parser.add_argument("--submission", required=True, help="the first-fit record (JSON; 'at' as ISO UTC)")
    parser.add_argument("--receipt", help="the signed spot-check receipt (JSON)")
    parser.add_argument("--reviews", help="the review keys: {'annex': [...], 'receipts': [...]} (JSON)")
    parser.add_argument("--out", required=True, help="the local detail, under datasets-local/")
    ns = parser.parse_args(argv)
    root = pr.ROOT
    out = Path(ns.out)
    _local_path(out, root)  # refuse a shared destination before any work
    submission = _load_json(ns.submission)
    if isinstance(submission, dict) and isinstance(submission.get("at"), str):
        submission["at"] = datetime.fromisoformat(submission["at"].replace("Z", "+00:00"))
    # Round 83 (A1): fit only a submission the owner logged and committed after the freeze.
    ledger = committed_ledger(root)
    refused = ["the ledger is not committed in this checkout"] if ledger is None else []
    refused = refused or authorize(submission, ledger or "", now=_now())
    if refused:
        print("Not authorized to fit (docs/phase2/verification/gates.md §10):", file=sys.stderr)
        for reason in refused:
            print(f"- {reason}", file=sys.stderr)
        return 2
    report = run_report(
        ns.dataset,
        call=local_call(),
        prereg=pr.load(),
        root=root,
        submission=submission,
        receipt=_load_json(ns.receipt),
        reviews=_load_json(ns.reviews),
    )
    write_local(report, out, root=root)
    if report["status"] == COMPLETE:
        write_fit_values(report, root=root)  # the restricted-fit scan tier's source
    print(json.dumps(shared_output(report), indent=2, ensure_ascii=False))
    return 0 if report["status"] == COMPLETE else 1


if __name__ == "__main__":
    sys.exit(main())
