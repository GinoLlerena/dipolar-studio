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

A directory with no record and no snapshot holds nothing to carry over and opens as new. A journal
whose only bytes are a torn first record (no complete line) holds nothing acknowledged; it is
treated the same way, and opening quarantines those bytes as for any torn tail (documented).
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


def _first_record(journal: Path) -> dict[str, Any] | None:
    """The journal's first complete record, or None (no file, empty, or only a torn first line)."""
    try:
        handle = journal.open("rb")
    except FileNotFoundError:
        return None
    with handle:
        line = handle.readline(MAX_FIRST_RECORD + 1)
    if not line.endswith(b"\n"):
        if len(line) > MAX_FIRST_RECORD:
            raise DirectoryRefused(f"{journal.name}: its first record is larger than this version reads; not opened")
        return None  # nothing acknowledged
    try:
        record = json.loads(line)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise DirectoryRefused(
            f"{journal.name}: its first record cannot be read, so the version that wrote it is unknown; "
            "the directory was not opened or changed"
        ) from None
    if not isinstance(record, dict):
        raise DirectoryRefused(f"{journal.name}: its first line is not a record; the directory was not changed")
    return record


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


def _verdict(name: str, project_schema: object, store_schema: object, store_current: int, context: object) -> None:
    """Refuse unless a file was written by this version: its project schema, its own schema and the
    numerical context must all be this version's."""
    if context == numerical_context() and project_schema == PROJECT_SCHEMA_VERSION and store_schema == store_current:
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


def check_directory(project_dir: Path) -> None:
    """Raise ``DirectoryRefused`` unless this version may open ``project_dir`` (see the module
    docstring). Reads only."""
    from dipolar_app.snapshot import NEXT_NAME, SNAPSHOT_NAME, SNAPSHOT_SCHEMA_VERSION

    record = _first_record(project_dir / JOURNAL_NAME)
    if record is not None:
        _verdict(
            JOURNAL_NAME,
            record.get("project_schema"),
            record.get("journal_schema"),
            JOURNAL_SCHEMA_VERSION,
            record.get("numerical_context"),
        )
    for name in (SNAPSHOT_NAME, NEXT_NAME):
        body = _header(project_dir / name)
        if body is not None:
            _verdict(
                name,
                body.get("project_schema"),
                body.get("snapshot_schema"),
                SNAPSHOT_SCHEMA_VERSION,
                body.get("numerical_context"),
            )
