"""Child process for the journal crash spike: commit in a loop until killed.

    python crash_writer.py JOURNAL_DIR normal|slow

Opens the session (running crash recovery), prints one JSON line describing what it found, then
commits ``view.select`` forever, printing ``ack <seq>`` after each acknowledged command. In ``slow``
mode every journal write stores at most 7 bytes and pauses briefly, so a kill usually lands in the
middle of a record (a process kill otherwise rarely tears a small record).
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from dipolar_app import journal as journal_module
from dipolar_app.client import LocalClient
from dipolar_app.journal import Journal
from dipolar_app.operations import build_registry
from dipolar_app.policy import Principal, Tier
from dipolar_app.registry import CONTRACT_VERSION
from dipolar_app.session import Session

USER = Principal(actor="user", tier=Tier.APPLY, human=True)


def main() -> int:
    journal_dir, mode = Path(sys.argv[1]), sys.argv[2]
    if mode == "slow":
        real_write = os.write

        def trickle(fd: int, data: Any) -> int:
            time.sleep(0.0003)
            return real_write(fd, bytes(data[:7]))

        journal_module.os.write = trickle  # type: ignore[attr-defined]
    session = Session(Journal(journal_dir / "project.events.jsonl"), contract_version=CONTRACT_VERSION)
    recovery = session.recovery
    report = {"start_seq": session.state.seq, "discarded_bytes": recovery.discarded_bytes if recovery else 0}
    print(json.dumps(report), flush=True)
    client = LocalClient(build_registry(), session, USER)
    if session.state.project is None:
        opened = client.call("project.open_example", {"name": "biphenyl-synthetic", "expected_science_revision": 0})
        assert opened["ok"], opened
        print(f"ack {session.state.seq}", flush=True)
    while True:
        target = f"cpl_{session.state.seq % 14 + 1:06d}"  # always differs from the current selection
        envelope = client.call("view.select", {"ids": [target]})
        assert envelope["ok"], envelope
        print(f"ack {session.state.seq}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
