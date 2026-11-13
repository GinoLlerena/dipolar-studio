"""Session snapshots and journal compaction (dipolar_app.snapshot).

- A snapshot decodes to exactly the state it was written from, for every part of the state.
- After compaction, opening the project gives the same state and request table, the journal is
  empty and the covered records are archived, never deleted.
- A crash between writing the snapshot and rotating the journal is recovered.
- Damage is refused: a bad checksum, a snapshot the journal does not continue, a different
  numerical context.
- The request table and the number of records since the last snapshot are bounded.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from conftest import AGENT, client, new_session, run_fit
from dipolar_app import snapshot as snap
from dipolar_app.journal import Journal, JournalCorrupt
from dipolar_app.session import replay, replay_full

OPEN = {"name": "biphenyl-synthetic", "expected_science_revision": 0}


def ok(envelope: dict[str, Any]) -> dict[str, Any]:
    assert envelope["ok"], envelope
    result: dict[str, Any] = envelope["result"]
    return result


def deg(value: float) -> dict[str, object]:
    return {"value": value, "unit": "deg"}


def journal_of(tmp_path: Path) -> Journal:
    return Journal(tmp_path / "project.events.jsonl")


def busy_session(tmp_path: Path) -> Any:
    """A session whose state uses every part of SessionState: a project, a fit run (job and run),
    a camera and layers, a selection, undo and redo entries, a pending and a decided proposal,
    and request IDs."""
    s = new_session(tmp_path)
    c = client(s)
    ok(c.call("project.open_example", OPEN, request_id="open-1"))
    ok(run_fit(c))
    jump = {"kind": "jump4", "order": "bisector-diagonal", "frame": "bisector", "phi_domain": [deg(0), deg(90)]}
    ok(c.call("model.set", {**jump, "expected_science_revision": 1}, request_id="model-1"))
    rigid = {**jump, "kind": "rigid"}
    ok(c.call("model.set", {**rigid, "expected_science_revision": 2}))
    ok(c.call("history.undo", {"expected_science_revision": 3}))  # undo and redo both hold entries
    camera = {
        "position": {"xyz": [0.0, 20.0, 1.0], "unit": "Å"},
        "target": {"xyz": [0.0, 0.0, 1.0], "unit": "Å"},
        "up": {"xyz": [0.0, 0.0, 1.0]},
        "fov": {"value": 40.0, "unit": "deg"},
        "near": {"value": 5.0, "unit": "Å"},
        "far": {"value": 60.0, "unit": "Å"},
    }
    ok(c.call("view.set_camera", {"camera": camera, "viewport": {"width": 640, "height": 480}}))
    ok(c.call("view.set_layers", {"labels": False, "bonds": True, "couplings": True}))
    ok(c.call("view.select", {"ids": ["spn_000001"]}))
    agent = client(s, AGENT)
    for note in ("first", "second"):
        steps = [{"operation": "history.redo", "args": {"expected_science_revision": 4}}]
        ok(agent.call("proposal.create", {"steps": steps, "note": note}))
    ok(c.call("proposal.reject", {"proposal_id": "prp_000001", "reason": "no"}))
    return s, c


def test_a_snapshot_decodes_to_exactly_the_state_it_was_written_from(tmp_path: Path) -> None:
    s, _ = busy_session(tmp_path)
    state = s.state
    assert state.project and state.runs and state.jobs and state.undo and state.redo and len(state.proposals) == 2
    assert state.view.camera is not None and not state.view.layers.labels and state.view.selection
    body = snap.build(state, {}, "test")
    assert snap.state_from_json(json.loads(json.dumps(body["state"]))) == state


def test_after_compaction_the_project_reopens_identically_and_the_journal_is_archived(tmp_path: Path) -> None:
    s, _ = busy_session(tmp_path)
    before, requests = s.state, dict(s._requests)
    records = len(list(journal_of(tmp_path).records()))
    s.compact()
    assert (tmp_path / snap.SNAPSHOT_NAME).exists()
    assert list(journal_of(tmp_path).records()) == []
    archived = list((tmp_path / snap.ARCHIVE_DIR).iterdir())
    assert [p.name for p in archived] == [snap.archive_name(1, before.seq)]
    assert sum(1 for _ in Journal(archived[0]).records()) == records  # nothing deleted
    reopened = new_session(tmp_path)
    assert reopened.state == before and reopened._requests == requests
    # A retried request is still answered from the table, never applied twice.
    again = client(reopened).call("project.open_example", OPEN, request_id="open-1")
    assert again["replayed"] is True and reopened.state.seq == before.seq
    # Work continues after the snapshot, and replay goes through the snapshot transparently.
    c2 = client(reopened)
    ok(c2.call("view.select", {"ids": []}))
    ok(c2.call("history.redo", {"expected_science_revision": 4}))
    after = reopened.state
    assert replay(journal_of(tmp_path)) == after
    assert new_session(tmp_path).state == after
    # The run's result blob is still there and verified on open.
    assert after.runs and reopened.blobs.text(after.runs[0].result_sha256) is not None


def test_a_crash_between_the_snapshot_and_the_rotation_is_recovered(tmp_path: Path) -> None:
    s, _ = busy_session(tmp_path)
    before = s.state
    body = snap.build(before, dict(s._requests), "test")
    snap.write(tmp_path / snap.SNAPSHOT_NAME, body)  # step 1 done, step 2 not
    reopened = new_session(tmp_path)
    assert reopened.state == before
    ok(client(reopened).call("view.select", {"ids": []}))
    state, _ = replay_full(journal_of(tmp_path))  # the old records are skipped, the new one applied
    assert state == reopened.state and state.seq == before.seq + 1


def test_damage_to_a_snapshot_or_its_continuation_is_refused(tmp_path: Path) -> None:
    s, _ = busy_session(tmp_path)
    s.compact()
    path = tmp_path / snap.SNAPSHOT_NAME
    good = path.read_text(encoding="utf-8")
    path.write_text(good.replace('"seq":', '"seq": ', 1), encoding="utf-8")  # same JSON, but the
    new_session(tmp_path)  # checksum covers the canonical body, so a re-spacing is harmless
    data = json.loads(good)
    data["state"]["view"]["selection"] = []
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(JournalCorrupt, match="checksum"):
        new_session(tmp_path)
    path.write_text(good, encoding="utf-8")
    # A journal that does not continue the snapshot's sequence.
    journal = journal_of(tmp_path)
    record = {
        "journal_schema": 2,
        "project_schema": 2,
        "seq": s.state.seq + 2,
        "events": [],
        "revisions": {"science": s.state.science_revision, "workspace": s.state.workspace_revision},
    }
    journal.append(record)
    with pytest.raises(JournalCorrupt):
        new_session(tmp_path)


def test_a_snapshot_whose_covered_record_disagrees_is_refused(tmp_path: Path) -> None:
    s, _ = busy_session(tmp_path)
    body = snap.build(s.state, dict(s._requests), "test")
    body["state"]["view"]["selection"] = ["spn_000009"]  # not what the journal's records produce
    body = snap.build(snap.state_from_json(body["state"]), {}, "test")
    snap.write(tmp_path / snap.SNAPSHOT_NAME, body)
    with pytest.raises(JournalCorrupt, match="does not match the journal"):
        new_session(tmp_path)


def test_a_snapshot_from_another_numerical_context_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    s, _ = busy_session(tmp_path)
    s.compact()
    monkeypatch.setattr(snap, "numerical_context", lambda: {"numpy": "0.0"})
    with pytest.raises(JournalCorrupt, match="numerical context"):
        new_session(tmp_path)


def test_the_request_table_kept_in_a_snapshot_is_bounded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    s = new_session(tmp_path)
    c = client(s)
    ok(c.call("project.open_example", OPEN, request_id="r0"))
    for k in range(1, 4):
        ok(c.call("view.select", {"ids": [f"spn_00000{k}"]}, request_id=f"r{k}"))
    monkeypatch.setattr(snap, "MAX_REQUESTS", 2)
    s.compact()
    reopened = new_session(tmp_path)
    assert [key[1] for key in reopened._requests] == ["r2", "r3"]


def test_compaction_runs_by_itself_when_enough_records_follow_the_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(snap, "COMPACT_RECORDS", 3)
    s = new_session(tmp_path)
    c = client(s)
    ok(c.call("project.open_example", OPEN))
    for k in range(1, 6):
        ok(c.call("view.select", {"ids": [f"spn_00000{k}"]}))
    assert (tmp_path / snap.SNAPSHOT_NAME).exists()
    assert sum(1 for _ in journal_of(tmp_path).records()) < 3
    assert len(list((tmp_path / snap.ARCHIVE_DIR).iterdir())) == 2
    assert new_session(tmp_path).state == s.state


def test_a_snapshot_whose_metadata_disagrees_with_its_state_is_refused(tmp_path: Path) -> None:
    """A well-formed file (valid checksum) whose recorded sequence, revisions or science hash do
    not describe its own state."""
    s, _ = busy_session(tmp_path)
    s.compact()
    path = tmp_path / snap.SNAPSHOT_NAME
    good = json.loads(path.read_text(encoding="utf-8"))
    for key, value in (("seq", good["seq"] + 1), ("science_hash", "sha256:" + "0" * 64)):
        body = {k: v for k, v in good.items() if k != "checksum"}
        body[key] = value
        snap.write(path, body)
        with pytest.raises(JournalCorrupt, match="does not reproduce its recorded state"):
            new_session(tmp_path)


def test_a_snapshot_that_would_not_reproduce_the_state_is_never_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The guard against an incomplete codec: compaction stops before touching any file."""
    s, _ = busy_session(tmp_path)
    before = (tmp_path / "project.events.jsonl").read_bytes()
    real = snap.state_from_json
    monkeypatch.setattr(
        snap, "state_from_json", lambda data: real(data).__class__(**{**vars_of(real(data)), "undo": ()})
    )
    with pytest.raises(ValueError, match="does not reproduce the session state"):
        s.compact()
    assert not (tmp_path / snap.SNAPSHOT_NAME).exists() and not (tmp_path / snap.ARCHIVE_DIR).exists()
    assert (tmp_path / "project.events.jsonl").read_bytes() == before


def vars_of(state: Any) -> dict[str, Any]:
    from dataclasses import fields

    return {f.name: getattr(state, f.name) for f in fields(state)}
