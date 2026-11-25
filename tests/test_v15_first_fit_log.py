"""Round 83, A1 (and A6 at the runner): the first-fit log and the runner's authorization, frozen
before their implementation.

The finding: the runner validated a submission's shape without checking the freeze or the
owner's authorization, and the scanner's trigger was a single §3 row that could be read from the
working copy. What is frozen here:

- **The log** (``docs/phase2/verification/gates.md`` §10) is a table parsed by
  ``tools/validation/first_fit_log.py``: rows in time order, known events, the submission's
  fields, single events at most once, ``first access`` only after a submission. A malformed log
  is refused with a value-free message. ``extends(old, new)`` holds only when ``new`` keeps every
  row of ``old``, in order, and only adds rows after them.
- **The runner's authorization** (``verification.authorize``): a fit needs a ``freeze approved``
  row, a chronology that ``freeze_ok`` accepts, a runner who is the owner or a participant, a
  submission logged with exactly the runner's fields, and a submission time not in the future.
- **The command** reads the ledger as committed (``git show HEAD:…``) and fits nothing, writing
  nothing, unless the submission is authorized.

All values are synthetic; no experimental coupling is fitted.

**Pending implementation.** These tests xfail while (and only while)
``tools/validation/first_fit_log.py`` does not exist.
"""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "validation"))

from test_v15_verification import BENZENE, Synthetic, _condition_keys, _leaks, _never  # noqa: E402

LOG_PY = ROOT / "tools" / "validation" / "first_fit_log.py"
LEDGER = ROOT / "docs" / "phase2" / "verification" / "gates.md"
LEDGER_REL = Path("docs/phase2/verification/gates.md")
PROTOCOL = "263f26857da15df184c7e662325e39036c307a02bc0042c610d6b8d4dab700b9"


def _log() -> Any:
    if not LOG_PY.is_file():
        pytest.xfail("round 83: tools/validation/first_fit_log.py is not written yet")
    return importlib.import_module("first_fit_log")


def _v() -> Any:
    _log()
    return importlib.import_module("verification")


def _row(at: str, event: str, *cells: str) -> str:
    rest = list(cells) or ["—"] * 4
    return "| " + " | ".join([at, event, *rest]) + " |"


def _submission_row(at: str, protocol: str = PROTOCOL, runner: str = "owner", dataset: str = BENZENE) -> str:
    return _row(at, "submission", dataset, runner, "v0.2.0b1", protocol)


def _with_rows(*rows: str) -> str:
    """The real ledger with rows appended to its first-fit log table."""
    text = LEDGER.read_text(encoding="utf-8")
    last = "| 2026-11-22T14:11Z | no-fit attestation | — | — | — | — |"
    assert text.count(last) == 1
    return text.replace(last, "\n".join([last, *rows]))


FREEZE = _row("2026-11-24T09:00Z", "freeze approved")


# =========================================================================== the log
def test_the_real_log_parses_and_has_no_submission() -> None:
    log = _log()
    entries = log.parse(LEDGER.read_text(encoding="utf-8"))
    assert [e.event for e in entries] == [
        "decisions approved",
        "amendments approved",
        "decision changed",
        "no-fit attestation",
    ]
    assert entries[0].at == datetime(2026, 11, 21, 14, 59, tzinfo=UTC)
    assert log.submissions(entries) == []
    assert all(e.dataset is None and e.protocol_sha256 is None for e in entries)


def test_a_submission_row_is_read_with_its_fields() -> None:
    log = _log()
    entries = log.parse(_with_rows(FREEZE, _submission_row("2026-11-25T10:00Z")))
    (s,) = log.submissions(entries)
    assert (s.at, s.dataset, s.runner, s.release_or_commit, s.protocol_sha256) == (
        datetime(2026, 11, 25, 10, 0, tzinfo=UTC),
        BENZENE,
        "owner",
        "v0.2.0b1",
        PROTOCOL,
    )
    # Backticks around the revision are allowed (they are Markdown, not data).
    again = log.parse(_with_rows(FREEZE, _submission_row("2026-11-25T10:00Z", protocol=f"`{PROTOCOL}`")))
    assert log.submissions(again)[0].protocol_sha256 == PROTOCOL


MALFORMED_LOGS = {
    "a malformed time": _row("2026-11-25 10:00", "freeze approved"),
    "seconds in the time": _row("2026-11-25T10:00:00Z", "freeze approved"),
    "an unknown event": _row("2026-11-25T10:00Z", "fit approved"),
    "out of order": _row("2026-11-20T10:00Z", "freeze approved"),
    "a submission of an unknown dataset": _submission_row("2026-11-25T10:00Z", dataset="tfb"),
    "a submission by an unknown runner": _submission_row("2026-11-25T10:00Z", runner="someone"),
    "a short protocol revision": _submission_row("2026-11-25T10:00Z", protocol="263f268"),
    "a submission without a release": _row("2026-11-25T10:00Z", "submission", BENZENE, "owner", "—", PROTOCOL),
    "a non-submission with fields": _row("2026-11-25T10:00Z", "freeze approved", BENZENE, "—", "—", "—"),
    "a freeze twice": FREEZE + "\n" + _row("2026-11-24T10:00Z", "freeze approved"),
    "first access before any submission": _row("2026-11-25T10:00Z", "first access"),
    "a row with a missing cell": "| 2026-11-25T10:00Z | freeze approved | — | — | — |",
}


@pytest.mark.parametrize("name", list(MALFORMED_LOGS))
def test_a_malformed_log_is_refused(name: str) -> None:
    log = _log()
    with pytest.raises(ValueError) as info:
        log.parse(_with_rows(MALFORMED_LOGS[name]))
    assert PROTOCOL not in str(info.value)


def test_the_log_section_must_exist_once() -> None:
    log = _log()
    text = LEDGER.read_text(encoding="utf-8")
    with pytest.raises(ValueError):
        log.parse(text.replace("## 10. First-fit log", "## 10. Something else"))
    with pytest.raises(ValueError):
        log.parse(text + "\n## 10. First-fit log\n")


def test_a_later_log_must_extend_the_earlier_one() -> None:
    log = _log()
    old = log.parse(_with_rows(FREEZE))
    new = log.parse(_with_rows(FREEZE, _submission_row("2026-11-25T10:00Z")))
    assert log.extends(old, new) is True
    assert log.extends(old, old) is True
    assert log.extends(new, old) is False  # a removed row
    edited = log.parse(_with_rows(_row("2026-11-24T09:30Z", "freeze approved")))
    assert log.extends(old, edited) is False  # a changed row


# ================================================================ the authorization
def _record(at: datetime = datetime(2026, 11, 25, 10, 0, tzinfo=UTC), **changes: Any) -> dict[str, Any]:
    return {
        "dataset": BENZENE,
        "runner": "owner",
        "at": at,
        "release_or_commit": "v0.2.0b1",
        "protocol_sha256": PROTOCOL,
        **changes,
    }


NOW = datetime(2026, 11, 25, 12, 0, tzinfo=UTC)


def test_a_logged_submission_after_the_freeze_is_authorized() -> None:
    v = _v()
    ledger = _with_rows(FREEZE, _submission_row("2026-11-25T10:00Z"))
    assert v.authorize(_record(), ledger, now=NOW) == []


REFUSALS = {
    "no freeze approval": ([_submission_row("2026-11-25T10:00Z")], {}),
    "a submission at the freeze instant": (
        [_row("2026-11-25T10:00Z", "freeze approved"), _submission_row("2026-11-25T10:00Z")],
        {},
    ),
    "not logged": ([FREEZE], {}),
    "logged with another time": ([FREEZE, _submission_row("2026-11-25T10:01Z")], {}),
    "logged with another protocol revision": ([FREEZE, _submission_row("2026-11-25T10:00Z", protocol="0" * 64)], {}),
    "logged for another runner": (
        [FREEZE, _submission_row("2026-11-25T10:00Z", runner="participant")],
        {},
    ),
    "an agent runner": ([FREEZE, _submission_row("2026-11-25T10:00Z", runner="agent")], {"runner": "agent"}),
    "a submission in the future": (
        [FREEZE, _submission_row("2026-11-25T13:00Z")],
        {"at": datetime(2026, 11, 25, 13, 0, tzinfo=UTC)},
    ),
}


@pytest.mark.parametrize("name", list(REFUSALS))
def test_an_unauthorized_submission_is_refused(name: str) -> None:
    v = _v()
    rows, changes = REFUSALS[name]
    problems = v.authorize(_record(**changes), _with_rows(*rows), now=NOW)
    assert problems, name
    assert all(isinstance(p, str) and PROTOCOL not in p for p in problems)


def test_a_malformed_ledger_authorizes_nothing() -> None:
    v = _v()
    assert v.authorize(_record(), "no log here", now=NOW)
    assert v.authorize(_record(), _with_rows(FREEZE, MALFORMED_LOGS["out of order"]), now=NOW)


# ===================================================================== the command
def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@invalid", *args],
        cwd=root,
        check=True,
        capture_output=True,
    )


def _committed_ledger(root: Path, text: str) -> None:
    (root / LEDGER_REL).parent.mkdir(parents=True, exist_ok=True)
    (root / LEDGER_REL).write_text(text, encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "add", str(LEDGER_REL))
    _git(root, "commit", "-q", "-m", "ledger")


def _command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, v: Any, syn: Synthetic, call: Any) -> int:
    monkeypatch.setattr(v.pr, "ROOT", tmp_path)
    monkeypatch.setattr(v.pr, "load", lambda: syn.prereg)
    monkeypatch.setattr(v, "local_call", lambda: call)
    monkeypatch.setattr(v, "_now", lambda: NOW)  # the runner's clock (UTC)
    submission = {**syn.submission(), "at": syn.submission()["at"].isoformat()}
    (tmp_path / "submission.json").write_text(json.dumps(submission), encoding="utf-8")
    code: int = v.main(
        [
            "--dataset",
            BENZENE,
            "--submission",
            str(tmp_path / "submission.json"),
            "--out",
            "datasets-local/verification/benzene-report.md",
        ]
    )
    return code


def test_the_command_fits_nothing_without_a_committed_authorization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    v = _v()
    syn = Synthetic(tmp_path, BENZENE)
    # Logged in the working copy only: the committed ledger has no submission.
    _committed_ledger(tmp_path, _with_rows(FREEZE))
    (tmp_path / LEDGER_REL).write_text(
        _with_rows(FREEZE, _submission_row("2026-11-25T10:00Z", protocol=syn.protocol)), encoding="utf-8"
    )
    assert _command(tmp_path, monkeypatch, v, syn, _never) != 0
    assert not (tmp_path / "datasets-local" / "verification").exists()
    assert "authoriz" in capsys.readouterr().err


def test_the_command_fits_a_committed_authorized_submission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    v = _v()
    truths = {k: {"S_zz": -0.0731987654321 - 1.234567e-4 * i} for i, k in enumerate(_condition_keys(BENZENE))}
    syn = Synthetic(tmp_path, BENZENE, truths=truths)
    _committed_ledger(tmp_path, _with_rows(FREEZE, _submission_row("2026-11-25T10:00Z", protocol=syn.protocol)))
    assert _command(tmp_path, monkeypatch, v, syn, v.local_call()) == 0
    record = json.loads(
        (tmp_path / "datasets-local/verification" / f"{BENZENE}.fit-values.json").read_text(encoding="utf-8")
    )
    assert record["submission"] == {
        "dataset": BENZENE,
        "runner": "owner",
        "at": "2026-11-25T10:00Z",
        "release_or_commit": "v0.2.0b1",
        "protocol_sha256": syn.protocol,
    }
    out = capsys.readouterr()
    assert _leaks(out.out + out.err, [e["value"] for e in record["values"]]) == []
