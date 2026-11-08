"""Append-only journal (04 D14, §8.2).

One accepted command is one transaction record: a single JSON Lines entry carrying all of the
command's events and a SHA-256 checksum. The record is fsynced before the command is acknowledged.

M0 scope: append, read and verify. If an append fails, the session stops accepting commands
(fail-stop, see ``Session.commit``). Recovery from a torn final record is the M0 step-4 spike; until
then a damaged journal is refused (``JournalCorrupt``) rather than silently repaired.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from dipolar_app.project import canonical_json

JOURNAL_SCHEMA_VERSION = 1


class JournalCorrupt(Exception):
    pass


def checksum(record_without_checksum: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(record_without_checksum).encode()).hexdigest()


class Journal:
    def __init__(self, path: Path) -> None:
        self.path = path
        if not path.exists():
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            os.fsync(fd)
            os.close(fd)
            dir_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)

    def append(self, record: dict[str, Any]) -> dict[str, Any]:
        """Add the checksum, write the record as one line and fsync it. Returns the stored record."""
        if "checksum" in record:
            raise ValueError("the journal computes the checksum")
        stored = {**record, "checksum": checksum(record)}
        line = (canonical_json(stored) + "\n").encode()
        fd = os.open(self.path, os.O_WRONLY | os.O_APPEND)
        try:
            view = memoryview(line)
            while view:  # os.write may store fewer bytes than asked; never acknowledge a partial record
                written = os.write(fd, view)
                if written <= 0:
                    raise OSError("journal write stored no bytes")
                view = view[written:]
            os.fsync(fd)
        finally:
            os.close(fd)
        return stored

    def records(self) -> Iterator[dict[str, Any]]:
        """Yield verified records in order; raise ``JournalCorrupt`` on any damaged line."""
        with self.path.open("rb") as handle:
            for number, raw in enumerate(handle, start=1):
                if not raw.endswith(b"\n"):
                    raise JournalCorrupt(f"line {number}: incomplete final record")
                try:
                    stored = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise JournalCorrupt(f"line {number}: not JSON ({exc.msg})") from None
                body = {k: v for k, v in stored.items() if k != "checksum"}
                if stored.get("checksum") != checksum(body):
                    raise JournalCorrupt(f"line {number}: checksum mismatch")
                yield stored
