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


def test_torn_final_record_is_refused_until_recovery_lands(tmp_path: Path) -> None:
    """M0 step 4 designs recovery; until then a torn tail is detected, never half-applied."""
    path, _ = build(tmp_path)
    data = path.read_bytes()
    path.write_bytes(data[:-25])
    with pytest.raises(JournalCorrupt, match="incomplete"):
        replay(Journal(path))
