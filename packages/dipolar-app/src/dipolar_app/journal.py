"""Append-only journal (04 D14, §8.2).

One accepted command is one transaction record: a single JSON Lines entry carrying all of the
command's events and a SHA-256 checksum. The record is fsynced before the command is acknowledged.

If an append fails, the session stops accepting commands (fail-stop, see ``Session.commit``).

Crash recovery (M0 spike 4), run when a session opens the journal:

* **A torn tail is discarded.** Bytes after the last newline are a record whose write was cut
  short. A record is acknowledged only after its whole line, newline included, is written and
  fsynced, so a torn record was never acknowledged and discarding it loses nothing a client was
  told. The bytes are first copied to a private quarantine file next to the journal, then the
  journal is truncated; each step is fsynced.
* **Damage anywhere else is refused** (``JournalCorrupt``). A complete line that fails its checksum
  may have been acknowledged, so it is never repaired automatically.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dipolar_app.project import canonical_json

#: 2 (M2 step 2): records may carry ``step_lengths`` and a ``request`` (ID and outcome).
JOURNAL_SCHEMA_VERSION = 2


class JournalCorrupt(Exception):
    pass


def checksum(record_without_checksum: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(record_without_checksum).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class Recovery:
    """What opening the journal repaired: an unacknowledged torn tail, kept in ``quarantine``."""

    discarded_bytes: int
    kept_records: int
    quarantine: Path


def fsync_dir(path: Path) -> None:
    """Make a directory's entries durable. On Windows a directory cannot be opened for fsync, and
    NTFS journals its metadata itself, so this is a no-op there (small batch, Windows CI)."""
    if os.name == "nt":
        return
    dir_fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def make_durable_dirs(path: Path) -> None:
    """Create ``path`` and its missing ancestors, fsyncing each new directory's parent, so that the
    directory holding acknowledged records survives a power loss (round 34)."""
    missing: list[Path] = []
    current = path
    while not current.exists():
        missing.append(current)
        current = current.parent
    for directory in reversed(missing):
        directory.mkdir(mode=0o700, exist_ok=True)
        fsync_dir(directory.parent)


def _verify_line(number: int, raw: bytes) -> dict[str, Any]:
    try:
        stored = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise JournalCorrupt(f"line {number}: not JSON ({exc.msg})") from None
    if not isinstance(stored, dict):
        raise JournalCorrupt(f"line {number}: not a record")
    body = {k: v for k, v in stored.items() if k != "checksum"}
    if stored.get("checksum") != checksum(body):
        raise JournalCorrupt(f"line {number}: checksum mismatch")
    return stored


class Journal:
    def __init__(self, path: Path) -> None:
        self.path = path
        if not path.exists():
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            os.fsync(fd)
            os.close(fd)
            fsync_dir(path.parent)

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

    def rotate(self, archive: Path) -> None:
        """Move the journal to ``archive`` (a new file in an existing directory) and start an empty
        journal in its place (compaction, ``dipolar_app.snapshot``). Each step is made durable: the
        archive's directory, then the new journal and its directory. A crash in between leaves
        either the old journal in place or no journal, which opening recreates empty."""
        if archive.exists():
            raise FileExistsError(f"{archive} already exists")
        os.replace(self.path, archive)
        fsync_dir(archive.parent)
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.fsync(fd)
        os.close(fd)
        fsync_dir(self.path.parent)

    def records(self) -> Iterator[dict[str, Any]]:
        """Yield verified records in order; raise ``JournalCorrupt`` on any damaged line."""
        with self.path.open("rb") as handle:
            for number, raw in enumerate(handle, start=1):
                if not raw.endswith(b"\n"):
                    raise JournalCorrupt(f"line {number}: incomplete final record (run recovery)")
                yield _verify_line(number, raw)

    def recover_torn_tail(self) -> Recovery | None:
        """Discard an unacknowledged torn final record (see the module docstring).

        Every complete line is verified first; if any is damaged, nothing is changed and
        ``JournalCorrupt`` is raised. Returns None when the journal ends cleanly.
        """
        data = self.path.read_bytes()
        end = data.rfind(b"\n") + 1  # 0 if there is no complete line at all
        if end == len(data):
            return None
        complete = data[:end].splitlines(keepends=True)
        for number, raw in enumerate(complete, start=1):
            _verify_line(number, raw)
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        quarantine = self.path.with_name(f"{self.path.name}.torn-{stamp}-{secrets.token_hex(4)}")
        fd = os.open(quarantine, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            view = memoryview(data[end:])
            while view:
                written = os.write(fd, view)
                if written <= 0:
                    raise OSError("quarantine write stored no bytes")
                view = view[written:]
            os.fsync(fd)
        finally:
            os.close(fd)
        fsync_dir(self.path.parent)  # the quarantine copy exists before the journal is cut
        fd = os.open(self.path, os.O_WRONLY)
        try:
            os.ftruncate(fd, end)
            os.fsync(fd)
        finally:
            os.close(fd)
        return Recovery(discarded_bytes=len(data) - end, kept_records=len(complete), quarantine=quarantine)
