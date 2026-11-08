"""M0 spike 4: journal crash recovery (ADR-0014, 04 §8.2).

Question: if the process is killed in the middle of a commit, does the journal come back
consistent, and does every command a client was told about survive?

Method: a child process (``crash_writer.py``) commits in a loop and prints ``ack <seq>`` after
each acknowledged command. The parent kills it with SIGKILL at random moments, restarts it on the
same journal (which runs recovery), and repeats. In ``slow`` mode the child writes each record a
few bytes at a time, so most kills tear a record. At the end the parent checks:

  * every restart opened the journal (recovery never refused a crash-torn journal);
  * every acknowledged sequence number is in the final journal (no acknowledged loss);
  * the journal replays to a contiguous sequence with matching hashes (``replay`` checks this);
  * each discarded tail was kept in a quarantine file, byte for byte;
  * torn tails really were exercised (slow mode).

A last test kills a real ``dipolar serve``, tears its journal, and restarts it.

Out of scope, by design: power loss and storage faults. A process kill keeps every byte already
written in the page cache; only an fsync-acknowledged record is promised to survive power loss,
and this spike does not simulate one.
"""

from __future__ import annotations

import json
import os
import random
import select
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest
from dipolar_app.journal import Journal
from dipolar_app.registry import CONTRACT_VERSION
from dipolar_app.session import Session

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
WRITER = HERE / "crash_writer.py"


def run_until_killed(journal_dir: Path, mode: str, rng: random.Random) -> tuple[dict[str, int], list[int]]:
    """Start the writer, let it acknowledge a few commands, kill it at a random moment."""
    child = subprocess.Popen(
        [sys.executable, str(WRITER), str(journal_dir), mode], stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    assert child.stdout is not None
    header = json.loads(child.stdout.readline())  # recovery has run once this line exists
    acks: list[int] = []
    deadline = time.monotonic() + 30
    wanted = rng.randint(1, 6)
    while len(acks) < wanted:  # wait for a few acknowledgements, so the kill lands during traffic
        assert time.monotonic() < deadline and child.poll() is None, child.stderr.read() if child.stderr else ""
        ready, _, _ = select.select([child.stdout], [], [], 1.0)
        if ready:
            acks.append(int(child.stdout.readline().split()[1]))
    time.sleep(rng.uniform(0.0, 0.05))
    child.send_signal(signal.SIGKILL)
    rest, _ = child.communicate(timeout=10)
    acks += [int(line.split()[1]) for line in rest.decode().splitlines() if line.startswith("ack ")]
    assert child.returncode == -signal.SIGKILL
    return header, acks


@pytest.mark.parametrize(("mode", "cycles"), [("slow", 15), ("normal", 10)])
def test_kill_at_random_moments_loses_no_acknowledged_command(tmp_path: Path, mode: str, cycles: int) -> None:
    check_kill_loop(tmp_path, mode, cycles, seed=19980101)


@pytest.mark.slow
def test_kill_loop_long(tmp_path: Path) -> None:
    check_kill_loop(tmp_path, "slow", 200, seed=42)


def check_kill_loop(tmp_path: Path, mode: str, cycles: int, seed: int) -> None:
    rng = random.Random(seed)
    acknowledged: set[int] = set()
    recoveries = 0
    discarded_total = 0
    previous_end = 0
    for _ in range(cycles):
        header, acks = run_until_killed(tmp_path, mode, rng)
        assert header["start_seq"] >= previous_end  # the restart kept everything acknowledged before
        if header["discarded_bytes"]:
            recoveries += 1
            discarded_total += header["discarded_bytes"]
        acknowledged |= set(acks)
        previous_end = max(acks)
    session = Session(Journal(tmp_path / "project.events.jsonl"), contract_version=CONTRACT_VERSION)
    if session.recovery is not None:
        recoveries += 1
        discarded_total += session.recovery.discarded_bytes
    final_seq = session.state.seq
    assert acknowledged <= set(range(1, final_seq + 1)), sorted(acknowledged - set(range(1, final_seq + 1)))
    assert max(acknowledged) <= final_seq
    quarantined = sorted(tmp_path.glob("project.events.jsonl.torn-*"))
    assert len(quarantined) == recoveries
    assert sum(p.stat().st_size for p in quarantined) == discarded_total
    if mode == "slow":
        assert recoveries >= cycles // 2, f"only {recoveries} of {cycles} kills tore a record"
    print(f"\n{mode}: {cycles} kills, {recoveries} torn tails recovered, final seq {final_seq}")


def test_a_killed_server_restarts_from_its_torn_journal(tmp_path: Path) -> None:
    """The real server: SIGKILL, a torn tail left on disk, restart, then carry on."""
    project = tmp_path / "project"
    ready_file = project / "serve.ready.json"

    def serve() -> tuple[subprocess.Popen[bytes], dict[str, object], Path]:
        out = tmp_path / f"serve-{time.monotonic_ns()}.out"
        with out.open("wb") as handle:
            proc = subprocess.Popen(
                [sys.executable, "-m", "dipolar_app.cli", "serve", "--project-dir", str(project)],
                stdout=handle,
                stderr=subprocess.STDOUT,
            )
        deadline = time.monotonic() + 20
        while True:
            try:
                ready = json.loads(ready_file.read_text())
                if ready["pid"] == proc.pid:
                    return proc, ready, out
            except (OSError, ValueError):
                pass
            assert proc.poll() is None and time.monotonic() < deadline, out.read_text()
            time.sleep(0.05)

    def robot(ready_path: Path) -> subprocess.CompletedProcess[str]:
        env = {k: v for k, v in os.environ.items() if not k.startswith(("PYTHON", "VIRTUAL_ENV", "UV_"))}
        return subprocess.run(
            [sys.executable, "-I", str(ROOT / "tools" / "robot" / "robot.py"), "--ready-file", str(ready_path)],
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
            check=False,
        )

    first, _, _ = serve()
    assert robot(ready_file).returncode == 0
    first.send_signal(signal.SIGKILL)
    first.wait()
    journal = project / "project.events.jsonl"
    kept = journal.read_bytes()
    with journal.open("ab") as handle:  # the crash cut the next record short
        handle.write(b'{"actor":"script:robot","args":{"ids":["cpl_0000')

    second, _, out = serve()
    try:
        assert "Recovered the journal" in out.read_text()
        assert journal.read_bytes() == kept
        assert robot(ready_file).returncode == 0  # the session carries on: reopens and selects again
    finally:
        second.terminate()
        second.wait(timeout=10)
