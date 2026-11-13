"""Session snapshots and journal compaction (04 §8.2 "periodic snapshots record the sequence number
they cover"; the storage limit left open after M2).

Without compaction the journal and the request table grow for ever, and opening a project
replays every record. A **snapshot** is the whole session state at one journal sequence number,
written so that opening the project can start from it and replay only the records after it.

**What a snapshot holds.** The state (project, view, undo and redo stacks, proposals, jobs, runs
and the ID counters), the most recent ``MAX_REQUESTS`` request outcomes (the deduplication table),
the sequence number and revisions it covers, the science hash, the schema versions, the numerical
context and a SHA-256 checksum of the whole file.

**What makes it verifiable.** A snapshot is written only after decoding it again reproduces the
in-memory state exactly. When a project opens, the checksum, the decoded science hash, the
numerical context and the schema versions are checked, and the first journal record after it must
continue its sequence and revisions; any mismatch is ``JournalCorrupt``, never repaired.

**Compaction** (``compact``), under the session's writer lock:

1. write the snapshot to a private temporary file, fsync it, rename it over
   ``project.snapshot.json`` and fsync the directory;
2. move the journal it covers to ``archive/project.events.<first>-<last>.jsonl`` and start an
   empty journal, fsyncing the directories.

A crash between the steps leaves a snapshot and a journal that still holds the records it covers;
opening skips those records after checking that the last of them matches the snapshot. Nothing is
deleted: archived journals keep the full audit trail, and the user may remove them.

**The request table is bounded.** A retry of a request older than the last ``MAX_REQUESTS``
recorded requests, after a compaction, is treated as a new request; a command that carries an
expected revision then fails its precondition instead of applying twice.
"""

from __future__ import annotations

import json
import os
import secrets
from dataclasses import fields
from pathlib import Path
from typing import Any

from dipolar_core.context import numerical_context

from dipolar_app.journal import JOURNAL_SCHEMA_VERSION, JournalCorrupt, checksum, fsync_dir
from dipolar_app.project import PROJECT_SCHEMA_VERSION, Project, canonical_json, migrate_project, payload_hash
from dipolar_app.session import (
    Camera,
    HistoryEntry,
    Job,
    Layers,
    Proposal,
    ProposalStep,
    Run,
    SessionState,
    StoredOutcome,
    ViewState,
)

SNAPSHOT_FORMAT = "dipolar-session-snapshot"
SNAPSHOT_SCHEMA_VERSION = 1
SNAPSHOT_NAME = "project.snapshot.json"
ARCHIVE_DIR = "archive"

#: Request outcomes kept in a snapshot (the most recent ones).
MAX_REQUESTS = 10_000
#: Compact when this many records follow the last snapshot (checked after each commit and when a
#: project opens).
COMPACT_RECORDS = 5_000


# --------------------------------------------------------------------------- state codec
def _plain(value: Any) -> Any:
    """A frozen dataclass (or tuple of them) as JSON data; projects as their stored payload."""
    if isinstance(value, Project):
        return value.model_dump(mode="json")
    if isinstance(value, tuple):
        return [_plain(v) for v in value]
    if hasattr(value, "__dataclass_fields__"):
        return {f.name: _plain(getattr(value, f.name)) for f in fields(value)}
    return value


def state_to_json(state: SessionState) -> dict[str, Any]:
    return dict(_plain(state))


def _project(data: Any) -> Project | None:
    return None if data is None else Project.model_validate(migrate_project(data))


def _tuple3(values: Any) -> tuple[float, float, float]:
    x, y, z = (float(v) for v in values)
    return (x, y, z)


def _view(data: dict[str, Any]) -> ViewState:
    camera = data["camera"]
    width, height = data["viewport"]
    return ViewState(
        selection=tuple(data["selection"]),
        highlights=tuple(data["highlights"]),
        camera=None
        if camera is None
        else Camera(
            position=_tuple3(camera["position"]),
            target=_tuple3(camera["target"]),
            up=_tuple3(camera["up"]),
            fov_deg=float(camera["fov_deg"]),
            near=float(camera["near"]),
            far=float(camera["far"]),
        ),
        viewport=(int(width), int(height)),
        layers=Layers(**data["layers"]),
    )


def _history(data: dict[str, Any]) -> HistoryEntry:
    project = _project(data["project"])
    assert project is not None
    return HistoryEntry(project, data["operation"], data["actor"], data["science_revision"])


def _proposal(data: dict[str, Any]) -> Proposal:
    steps = tuple(ProposalStep(s["operation"], s["args_json"], tuple(s["depends_on"])) for s in data["steps"])
    return Proposal(**{**data, "steps": steps, "accepted_steps": tuple(data["accepted_steps"])})


def state_from_json(data: dict[str, Any]) -> SessionState:
    expected = {f.name for f in fields(SessionState)}
    if set(data) != expected:
        raise ValueError(f"snapshot state fields {sorted(set(data) ^ expected)} do not match this version")
    return SessionState(
        project=_project(data["project"]),
        view=_view(data["view"]),
        seq=data["seq"],
        science_revision=data["science_revision"],
        workspace_revision=data["workspace_revision"],
        undo=tuple(_history(h) for h in data["undo"]),
        redo=tuple(_history(h) for h in data["redo"]),
        proposals=tuple(_proposal(p) for p in data["proposals"]),
        next_proposal=data["next_proposal"],
        jobs=tuple(Job(**j) for j in data["jobs"]),
        next_job=data["next_job"],
        runs=tuple(Run(**r) for r in data["runs"]),
        next_run=data["next_run"],
    )


def _requests_to_json(requests: dict[tuple[str, str], StoredOutcome]) -> list[dict[str, Any]]:
    kept = list(requests.items())[-MAX_REQUESTS:]  # insertion order is journal order
    return [
        {
            "actor": actor,
            "request_id": request_id,
            "fingerprint": o.fingerprint,
            "operation": o.operation,
            "result": o.result,
            "revisions": o.revisions,
        }
        for (actor, request_id), o in kept
    ]


def _requests_from_json(items: list[dict[str, Any]]) -> dict[tuple[str, str], StoredOutcome]:
    out: dict[tuple[str, str], StoredOutcome] = {}
    for item in items:
        key = (item["actor"], item["request_id"])
        if key in out:
            raise ValueError(f"request {item['request_id']!r} appears twice")
        out[key] = StoredOutcome(item["fingerprint"], item["operation"], item["result"], dict(item["revisions"]))
    return out


# --------------------------------------------------------------------------- files
def snapshot_path(journal_path: Path) -> Path:
    return journal_path.with_name(SNAPSHOT_NAME)


def build(state: SessionState, requests: dict[tuple[str, str], StoredOutcome], contract_version: str) -> dict[str, Any]:
    """The snapshot record (without its checksum), verified to decode back to ``state``."""
    body: dict[str, Any] = {
        "format": SNAPSHOT_FORMAT,
        "snapshot_schema": SNAPSHOT_SCHEMA_VERSION,
        "journal_schema": JOURNAL_SCHEMA_VERSION,
        "project_schema": PROJECT_SCHEMA_VERSION,
        "contract_version": contract_version,
        "numerical_context": numerical_context(),
        "seq": state.seq,
        "revisions": {"science": state.science_revision, "workspace": state.workspace_revision},
        "science_hash": state.science_hash,
        "state": state_to_json(state),
        "requests": _requests_to_json(requests),
    }
    # Verified before anything is written: decoding gives back exactly this state (and the
    # canonical JSON is the stored form, so the check covers what lands on disk).
    decoded = json.loads(canonical_json(body))
    if state_from_json(decoded["state"]) != state:
        raise ValueError("the snapshot does not reproduce the session state")
    return body


def write(path: Path, body: dict[str, Any]) -> None:
    """Write the snapshot atomically: a private temporary file, fsynced, renamed, then the
    directory fsynced."""
    stored = {**body, "checksum": checksum(body)}
    data = (canonical_json(stored) + "\n").encode()
    tmp = path.with_name(f".{path.name}.{secrets.token_hex(4)}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        view = memoryview(data)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise OSError("snapshot write stored no bytes")
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp, path)
    fsync_dir(path.parent)


def load(path: Path) -> tuple[SessionState, dict[tuple[str, str], StoredOutcome], dict[str, Any]] | None:
    """The snapshot's state, request table and metadata, verified; None if there is none."""
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return None
    try:
        stored = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise JournalCorrupt(f"{path.name}: not JSON") from None
    if not isinstance(stored, dict):
        raise JournalCorrupt(f"{path.name}: not a snapshot")
    body = {k: v for k, v in stored.items() if k != "checksum"}
    if stored.get("checksum") != checksum(body):
        raise JournalCorrupt(f"{path.name}: checksum mismatch")
    if body.get("format") != SNAPSHOT_FORMAT or body.get("snapshot_schema") != SNAPSHOT_SCHEMA_VERSION:
        raise JournalCorrupt(f"{path.name}: unsupported snapshot format or version")
    schema = body.get("project_schema")
    if not isinstance(schema, int) or isinstance(schema, bool) or not 1 <= schema <= PROJECT_SCHEMA_VERSION:
        raise JournalCorrupt(f"{path.name}: unsupported project_schema {schema!r}")
    if body.get("numerical_context") != numerical_context():
        raise JournalCorrupt(
            f"{path.name}: written under a different numerical context; a migration is required before replay"
        )
    try:
        state = state_from_json(body["state"])
        requests = _requests_from_json(body["requests"])
    except (KeyError, TypeError, ValueError) as exc:
        raise JournalCorrupt(f"{path.name}: cannot be decoded ({exc})") from None
    project_payload = body["state"]["project"]
    recorded = payload_hash(project_payload) if schema < PROJECT_SCHEMA_VERSION else state.science_hash
    revisions = body.get("revisions")
    if (
        body.get("seq") != state.seq
        or revisions != {"science": state.science_revision, "workspace": state.workspace_revision}
        or body.get("science_hash") != recorded
    ):
        raise JournalCorrupt(f"{path.name}: the snapshot does not reproduce its recorded state")
    return state, requests, body


def archive_name(first: int, last: int) -> str:
    return f"project.events.{first:09d}-{last:09d}.jsonl"
