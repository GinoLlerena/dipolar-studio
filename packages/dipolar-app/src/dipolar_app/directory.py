"""Which project directories this version opens (Phase 2 V1.3, docs/phase2/v1.0-design.md D-1).

V1 changed the numerical context (D-2) and the project schema, so a directory written by
Dipolar Studio 0.1 cannot be replayed. It is **refused unopened and unchanged**: the owner's
decision is to carry projects over through their export file, never to migrate a directory in
place.

``check_directory`` decides from the journal's first record and the snapshot headers alone, reading
each file without changing it. It runs under the instance lock and before anything else that
touches the directory (recovery of a torn tail, compaction, blob collection, the ready file). A
directory is opened only when each of these is positively written by this version:

- the journal's first complete record (``project_schema``, ``journal_schema`` and the numerical
  context);
- the snapshot and the next snapshot of an interrupted compaction, when present (``project_schema``,
  ``snapshot_schema`` and the numerical context).

**A directory with no readable record** (round 77) is opened only when its version is known:

- a first record without its final newline (a record cut short, never acknowledged) is judged by
  its metadata when it parses, and otherwise by its bytes: it must carry this version's
  ``journal_schema``, ``project_schema`` and numerical context, or the directory is refused;
- with no record and no snapshot, the directory may hold only the lock file, a ready file, an empty
  journal, empty directories, and torn-record quarantines of this version. Anything else (result
  blobs, archives, a quarantine of unknown version) is refused: opening would recover, collect or
  overwrite it. A directory that this version left with an unrecognizable torn first record is
  refused too; it holds nothing acknowledged, and moving its files away opens it as new.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dipolar_core.context import numerical_context

from dipolar_app.journal import JOURNAL_SCHEMA_VERSION
from dipolar_app.project import PROJECT_SCHEMA_VERSION

JOURNAL_NAME = "project.events.jsonl"
#: The 0.1 message (D-1), verbatim.
PHASE1_MESSAGE = (
    "This project directory was written by Dipolar Studio 0.1. Open it with 0.1, export the project "
    "(Data → Export, or `project.export`), and load the file into a new directory with this version. "
    "The old directory is not changed."
)
#: The first line of a journal is read up to this many bytes (a record carries a whole project).
MAX_FIRST_RECORD = 128 << 20


class DirectoryRefused(Exception):
    """The directory was written by another version; nothing in it was changed."""


def _markers() -> tuple[bytes, ...]:
    """Byte strings every record of this version carries (canonical JSON: sorted keys, no spaces)."""
    from dipolar_app.project import canonical_json

    return (
        f'"journal_schema":{JOURNAL_SCHEMA_VERSION}'.encode(),
        f'"project_schema":{PROJECT_SCHEMA_VERSION}'.encode(),
        ('"numerical_context":' + canonical_json(numerical_context())).encode(),
    )


def _torn_is_current(raw: bytes) -> bool:
    """Whether the bytes of a record cut short were written by this version."""
    try:
        record = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return all(marker in raw for marker in _markers())
    return isinstance(record, dict) and _is_current(
        record.get("project_schema"),
        record.get("journal_schema"),
        JOURNAL_SCHEMA_VERSION,
        record.get("numerical_context"),
    )


def _first_record(journal: Path) -> tuple[dict[str, Any] | None, bool]:
    """(the journal's first complete record, whether it holds any bytes at all). A first record
    without its newline is refused here unless it was written by this version."""
    try:
        handle = journal.open("rb")
    except FileNotFoundError:
        return None, False
    with handle:
        line = handle.readline(MAX_FIRST_RECORD + 1)
    if not line:
        return None, False
    if not line.endswith(b"\n"):
        if len(line) > MAX_FIRST_RECORD:
            raise DirectoryRefused(f"{journal.name}: its first record is larger than this version reads; not opened")
        if not _torn_is_current(line):
            raise DirectoryRefused(
                f"{journal.name} holds only a record cut short, not written by this version (it may be "
                f"Dipolar Studio 0.1's). {PHASE1_MESSAGE}"
            )
        return None, True  # this version's own unacknowledged record: recovery quarantines it
    try:
        record = json.loads(line)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise DirectoryRefused(
            f"{journal.name}: its first record cannot be read, so the version that wrote it is unknown; "
            "the directory was not opened or changed"
        ) from None
    if not isinstance(record, dict):
        raise DirectoryRefused(f"{journal.name}: its first line is not a record; the directory was not changed")
    return record, True


def _header(path: Path) -> dict[str, Any] | None:
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return None
    try:
        body = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise DirectoryRefused(
            f"{path.name} cannot be read, so the version that wrote it is unknown; the directory was not opened "
            "or changed"
        ) from None
    if not isinstance(body, dict):
        raise DirectoryRefused(f"{path.name} is not a snapshot; the directory was not changed")
    return body


def _is_current(project_schema: object, store_schema: object, store_current: int, context: object) -> bool:
    return context == numerical_context() and project_schema == PROJECT_SCHEMA_VERSION and store_schema == store_current


def _verdict(name: str, project_schema: object, store_schema: object, store_current: int, context: object) -> None:
    """Refuse unless a file was written by this version: its project schema, its own schema and the
    numerical context must all be this version's."""
    if _is_current(project_schema, store_schema, store_current, context):
        return
    newer = (
        isinstance(project_schema, int)
        and not isinstance(project_schema, bool)
        and project_schema > PROJECT_SCHEMA_VERSION
    ) or (isinstance(store_schema, int) and not isinstance(store_schema, bool) and store_schema > store_current)
    if newer:
        raise DirectoryRefused(
            f"This project directory was written by a newer version of Dipolar Studio ({name}). Open it with that "
            "version. The directory is not changed."
        )
    raise DirectoryRefused(PHASE1_MESSAGE)


#: What a directory with no record may hold and still open as new.
_FRESH_FILES = frozenset({JOURNAL_NAME, "serve.lock", "serve.ready.json"})


def _check_fresh(project_dir: Path) -> None:
    """No record and no snapshot: open as new only if nothing else of value is there."""
    for path in sorted(project_dir.rglob("*")):
        if path.is_dir():
            continue
        name = path.relative_to(project_dir).as_posix()
        if name in _FRESH_FILES:
            continue
        if name.startswith(f"{JOURNAL_NAME}.torn-") and _torn_is_current(path.read_bytes()):
            continue
        raise DirectoryRefused(
            f"This project directory has no record this version can read, but it holds {name}: the version "
            f"that wrote it is unknown. {PHASE1_MESSAGE}"
        )


def check_directory(project_dir: Path) -> None:
    """Raise ``DirectoryRefused`` unless this version may open ``project_dir`` (see the module
    docstring). Reads only."""
    from dipolar_app.snapshot import NEXT_NAME, SNAPSHOT_NAME, SNAPSHOT_SCHEMA_VERSION

    record, has_bytes = _first_record(project_dir / JOURNAL_NAME)
    if record is not None:
        _verdict(
            JOURNAL_NAME,
            record.get("project_schema"),
            record.get("journal_schema"),
            JOURNAL_SCHEMA_VERSION,
            record.get("numerical_context"),
        )
    snapshots = 0
    for name in (SNAPSHOT_NAME, NEXT_NAME):
        body = _header(project_dir / name)
        if body is not None:
            snapshots += 1
            _verdict(
                name,
                body.get("project_schema"),
                body.get("snapshot_schema"),
                SNAPSHOT_SCHEMA_VERSION,
                body.get("numerical_context"),
            )
    if record is None and not has_bytes and not snapshots:
        _check_fresh(project_dir)
