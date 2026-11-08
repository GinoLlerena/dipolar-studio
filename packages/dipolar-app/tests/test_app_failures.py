"""Failure paths found in validation round 8: journal writes, fail-stop, body streaming, snapshot
coherence of envelopes, and numerical provenance in the science identity."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

import pytest
from conftest import USER, VIEWER, client, new_session
from dipolar_app import journal as journal_module
from dipolar_app.auth import Credentials
from dipolar_app.http import MAX_BODY_BYTES, create_app
from dipolar_app.journal import Journal, JournalCorrupt
from dipolar_app.operations import DescribeViewIn, DescribeViewOut, build_registry, describe_view
from dipolar_app.policy import Capability
from dipolar_app.registry import Context, Operation, dispatch
from dipolar_app.session import replay

OPEN0 = {"name": "biphenyl-synthetic", "expected_science_revision": 0}


# --------------------------------------------------------------------------- journal writes
def test_short_writes_are_completed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    real_write = os.write

    def short_write(fd: int, data: Any) -> int:
        return real_write(fd, bytes(data[: max(1, len(data) // 3)]))  # never more than a third at once

    monkeypatch.setattr(journal_module.os, "write", short_write)
    s = new_session(tmp_path)
    assert client(s).call("project.open_example", OPEN0)["ok"]
    rebuilt = replay(Journal(tmp_path / "project.events.jsonl"))
    assert (rebuilt.seq, rebuilt.science_hash) == (1, s.state.science_hash)


def test_zero_byte_write_fails_stop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(journal_module.os, "write", lambda fd, data: 0)
    s = new_session(tmp_path)
    env = client(s).call("project.open_example", OPEN0)
    assert env["error"]["code"] == "JOURNAL_FAILED"
    assert s.state.seq == 0 and s.failed


def test_fsync_failure_stops_commands_and_restart_follows_the_journal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The record was fully written but fsync failed: the outcome is uncertain, so the session
    refuses every later command; queries still answer from the last acknowledged state."""

    def failing_fsync(fd: int) -> None:
        raise OSError(5, "simulated EIO")

    s = new_session(tmp_path)
    c = client(s)
    monkeypatch.setattr(journal_module.os, "fsync", failing_fsync)
    first = c.call("project.open_example", OPEN0)
    assert (first["ok"], first["error"]["code"]) == (False, "JOURNAL_FAILED")
    assert "uncertain" in first["error"]["message"]
    monkeypatch.undo()  # the disk "recovers", but the session must not carry on regardless

    retry = c.call("project.open_example", OPEN0)
    assert retry["error"]["code"] == "JOURNAL_FAILED"
    assert c.call("view.select", {"ids": []})["error"]["code"] == "JOURNAL_FAILED"
    assert c.call("render.describe_view")["ok"]
    assert s.state.seq == 0

    lines = (tmp_path / "project.events.jsonl").read_text().splitlines()
    assert len(lines) == 1  # no second record with the same sequence number
    restarted = new_session(tmp_path)  # replay: the journal is the source of truth
    assert (restarted.state.seq, restarted.state.science_revision) == (1, 1)
    assert client(restarted).call("project.open_example", {**OPEN0, "expected_science_revision": 1})["ok"]


def test_torn_write_stops_commands_and_is_recovered_on_restart(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    real_write = os.write
    calls = {"n": 0}

    def torn(fd: int, data: Any) -> int:
        calls["n"] += 1
        if calls["n"] == 1:
            return real_write(fd, bytes(data[:40]))
        raise OSError(28, "simulated ENOSPC")

    s = new_session(tmp_path)
    monkeypatch.setattr(journal_module.os, "write", torn)
    assert client(s).call("project.open_example", OPEN0)["error"]["code"] == "JOURNAL_FAILED"
    monkeypatch.undo()
    assert client(s).call("project.open_example", OPEN0)["error"]["code"] == "JOURNAL_FAILED"
    restarted = new_session(tmp_path)  # spike 4: the unacknowledged torn record is discarded
    assert restarted.recovery is not None and restarted.recovery.discarded_bytes == 40
    torn = restarted.recovery.quarantine.read_bytes()
    assert len(torn) == 40 and torn.startswith(b'{"') and b"\n" not in torn  # the cut-short record, kept aside
    assert (tmp_path / "project.events.jsonl").read_bytes() == b""
    assert (restarted.state.seq, restarted.state.science_revision) == (0, 0)
    assert client(restarted).call("project.open_example", OPEN0)["ok"]


# --------------------------------------------------------------------------- envelope coherence
def test_envelope_revisions_describe_the_result_snapshot() -> None:
    """A query whose state changes while it runs reports the revisions it actually read."""
    s = new_session()
    other = client(s)
    other.call("project.open_example", OPEN0)

    def racing_describe(ctx: Context, p: DescribeViewIn) -> DescribeViewOut:
        out = describe_view(ctx, p)  # reads the snapshot at science revision 1
        other.call("project.open_example", {**OPEN0, "expected_science_revision": 1})  # concurrent change
        return out

    registry = build_registry()
    registry.register(
        Operation(
            name="test.racing_describe",
            kind="query",
            effect="none",
            capability=Capability.QUERY,
            summary="test only",
            input_model=DescribeViewIn,
            output_model=DescribeViewOut,
            handler=racing_describe,
        )
    )
    env = dispatch(registry, s, USER, "test.racing_describe", {})
    assert s.state.science_revision == 2
    assert env["result"]["science_revision"] == env["revisions"]["science"] == 1


# --------------------------------------------------------------------------- streamed body limit
def test_chunked_body_is_never_buffered_past_the_limit() -> None:
    """Without Content-Length the adapter must stop reading as soon as the limit is exceeded."""
    tokens = {"tok": VIEWER}
    app = create_app(build_registry(), new_session(), Credentials(tokens), port=8765)
    chunk = b" " * 65536
    consumed = {"bytes": 0}
    sent: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        await asyncio.sleep(0)  # yield, so a regression times out instead of spinning
        consumed["bytes"] += len(chunk)
        more = consumed["bytes"] < 4 * MAX_BODY_BYTES  # bounded, so a regression fails, not exhausts memory
        return {"type": "http.request", "body": chunk, "more_body": more}

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/v1/ops/fit.preview",
        "raw_path": b"/api/v1/ops/fit.preview",
        "query_string": b"",
        "root_path": "",
        "headers": [
            (b"host", b"127.0.0.1:8765"),
            (b"authorization", b"Bearer tok"),
            (b"content-type", b"application/json"),
            (b"transfer-encoding", b"chunked"),
        ],
        "client": ("127.0.0.1", 50000),
        "server": ("127.0.0.1", 8765),
    }
    asyncio.run(asyncio.wait_for(app(scope, receive, send), timeout=10))  # type: ignore[arg-type]
    start = next(m for m in sent if m["type"] == "http.response.start")
    body = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    assert start["status"] == 413
    assert json.loads(body)["error"]["code"] == "PAYLOAD_TOO_LARGE"
    assert consumed["bytes"] <= MAX_BODY_BYTES + len(chunk)


# --------------------------------------------------------------------------- numerical provenance
def test_science_identity_covers_the_numerical_context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from dipolar_app import project as project_module
    from dipolar_app import session as session_module
    from dipolar_core.context import numerical_context

    s = new_session(tmp_path)
    c = client(s)
    c.call("project.open_example", OPEN0)
    preview = c.call("fit.preview", {"phi": {"value": 37.0, "unit": "deg"}})["result"]
    assert preview["numerical_context"] == numerical_context()
    before = s.state.science_hash

    changed = {**numerical_context(), "nuclide_table": "some-other-table"}
    monkeypatch.setattr(project_module, "numerical_context", lambda: changed)
    monkeypatch.setattr(session_module, "numerical_context", lambda: changed)
    assert s.state.science_hash != before  # same project, different numbers: different identity
    with pytest.raises(JournalCorrupt, match="numerical context"):
        new_session(tmp_path)
