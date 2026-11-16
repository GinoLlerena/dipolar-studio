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
