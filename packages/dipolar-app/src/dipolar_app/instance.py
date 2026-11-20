"""One live session per project directory (plan D10): the instance lock.

Shared by `dipolar serve` and the in-process Python API (`dipolar_app.api.Studio.local`), so a
notebook and a server never write the same journal at once.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


class InstanceRunning(Exception):
    pass


def lock_project(project_dir: Path) -> int:
    """Take the project's exclusive instance lock; the returned descriptor is held for life."""
    fd = os.open(project_dir / "serve.lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        if sys.platform == "win32":
            import msvcrt

            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(fd)
        raise InstanceRunning(f"another Dipolar Studio session is already using {project_dir}") from None
    return fd


def lock_checked(project_dir: Path) -> int:
    """Take the instance lock, then refuse a directory written by another version (D-1,
    ``dipolar_app.directory``) before anything else touches it. On a refusal the lock is released,
    and its file removed if this call created it, so the directory is left byte for byte as it was."""
    from dipolar_app.directory import check_directory

    lock = project_dir / "serve.lock"
    existed = lock.exists()
    fd = lock_project(project_dir)
    try:
        check_directory(project_dir)
    except BaseException:
        if os.name == "nt":  # an open file cannot be removed on Windows
            os.close(fd)
            if not existed:
                lock.unlink(missing_ok=True)
        else:
            if not existed:
                lock.unlink(missing_ok=True)  # while still held: no other process can own this file yet
            os.close(fd)
        raise
    return fd
