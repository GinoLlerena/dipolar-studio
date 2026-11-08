"""Journal and replay (04 §7 Replay, §8.2)."""

from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest
from conftest import ROBOT, client, new_session
from dipolar_app.journal import Journal, JournalCorrupt
from dipolar_app.session import replay


def build(tmp_path: Path) -> tuple[Path, object]:
    s = new_session(tmp_path)
    user, robot = client(s), client(s, ROBOT)
    user.call("project.open_example", {"name": "biphenyl-synthetic", "expected_science_revision": 0})
    robot.call("view.select", {"ids": ["cpl_000004", "spn_000002"]})
    user.call("fit.preview", {"phi": {"value": 30.0, "unit": "deg"}})  # a query: not journaled
    user.call("project.open_example", {"name": "biphenyl-synthetic", "expected_science_revision": 1})
    robot.call("view.select", {"ids": ["cpl_000010"]})
    return tmp_path / "project.events.jsonl", s


def test_replay_reproduces_state(tmp_path: Path) -> None:
    path, live = build(tmp_path)
    records = [json.loads(line) for line in path.read_text().splitlines()]
    assert [r["operation"] for r in records] == [
        "project.open_example",
        "view.select",
        "project.open_example",
        "view.select",
    ]
    assert [r["actor"] for r in records] == ["user", "script:robot", "user", "script:robot"]
    assert [len(r["events"]) for r in records] == [1, 1, 2, 1]  # reopening also clears the selection
    assert records[1]["events"][0]["previous"] == []

    rebuilt = replay(Journal(path))
    state = live.state  # type: ignore[attr-defined]
    assert rebuilt.science_hash == state.science_hash
    assert (rebuilt.seq, rebuilt.science_revision, rebuilt.workspace_revision) == (4, 2, 3)
    assert rebuilt.view == state.view

    resumed = new_session(tmp_path)  # a new process resumes from the same journal
    assert resumed.state == rebuilt
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_tampered_record_is_refused(tmp_path: Path) -> None:
    path, _ = build(tmp_path)
    text = path.read_text()
    path.write_text(text.replace('"cpl_000010"', '"cpl_000011"', 1))
    with pytest.raises(JournalCorrupt, match="checksum"):
        replay(Journal(path))


def test_replay_alone_refuses_a_torn_tail(tmp_path: Path) -> None:
    """replay() never half-applies a record; recovery is an explicit, separate step."""
    path, _ = build(tmp_path)
    path.write_bytes(path.read_bytes()[:-25])
    with pytest.raises(JournalCorrupt, match="incomplete"):
        replay(Journal(path))


@pytest.mark.parametrize("cut", [1, 25, "all-but-newline"])
def test_a_torn_tail_is_discarded_and_quarantined(tmp_path: Path, cut: int | str) -> None:
    """Spike 4: an unacknowledged record cut short by a crash is moved aside; the rest replays."""
    path, _ = build(tmp_path)
    data = path.read_bytes()
    lines = data.splitlines(keepends=True)
    prefix = b"".join(lines[:-1])
    torn = lines[-1][:-1] if cut == "all-but-newline" else lines[-1][: -int(cut) - 1]
    path.write_bytes(prefix + torn)
    s = new_session(tmp_path)
    assert s.recovery is not None
    assert (s.recovery.discarded_bytes, s.recovery.kept_records) == (len(torn), 3)
    assert s.recovery.quarantine.read_bytes() == torn
    assert stat.S_IMODE(s.recovery.quarantine.stat().st_mode) == 0o600
    assert path.read_bytes() == prefix
    assert s.state.seq == 3  # the last command was never acknowledged, so it is gone
    assert client(s, ROBOT).call("view.select", {"ids": ["cpl_000010"]})["ok"]  # appends cleanly after the cut
    assert new_session(tmp_path).state == s.state and new_session(tmp_path).recovery is None


def test_a_journal_with_only_a_torn_record_recovers_to_empty(tmp_path: Path) -> None:
    path, _ = build(tmp_path)
    path.write_bytes(path.read_bytes().splitlines(keepends=True)[0][:30])
    s = new_session(tmp_path)
    assert s.recovery is not None and s.recovery.kept_records == 0
    assert s.state.seq == 0 and path.read_bytes() == b""


@pytest.mark.parametrize("damage", ["middle", "complete-last"])
def test_damage_to_a_complete_record_is_refused_and_left_untouched(tmp_path: Path, damage: str) -> None:
    """A complete line may have been acknowledged: it is never repaired automatically."""
    path, _ = build(tmp_path)
    lines = path.read_bytes().splitlines(keepends=True)
    index = 1 if damage == "middle" else len(lines) - 1
    assert b"cpl_0000" in lines[index]  # both lines are view.select records
    lines[index] = lines[index].replace(b"cpl_0000", b"cpl_9999", 1)  # still JSON; the checksum no longer matches
    damaged = b"".join(lines) + b'{"torn'
    path.write_bytes(damaged)
    with pytest.raises(JournalCorrupt):
        new_session(tmp_path)
    assert path.read_bytes() == damaged  # nothing was cut or rewritten
    assert not list(tmp_path.glob("*.torn-*"))
