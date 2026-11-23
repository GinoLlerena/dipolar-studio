"""The ledger's first-fit log (docs/phase2/verification/gates.md §10; round 83, A1).

The log is the machine-read chronology of the first-fit gate: a Markdown table, appended to and
never edited. ``parse`` reads and checks it; ``extends`` tells whether a later log keeps every row
of an earlier one, in order. The runner (``verification.authorize``) fits only a submission logged
here, and the restricted-fit scan tier (``tools/datasets/restricted_scan.py``) is required from the
first logged submission on. Standard library only. Errors are value-free: they name a row number
and what is wrong, never the row's content.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

LEDGER = "docs/phase2/verification/gates.md"
HEADING = "## 10. First-fit log"
HEADER = "| UTC | Event | Dataset | Runner | Release or commit | Protocol revision |"
EVENTS = (
    "decisions approved",
    "decision changed",
    "amendments approved",
    "no-fit attestation",
    "freeze approved",
    "submission",
    "first access",
)
#: Events recorded at most once.
SINGLE = ("no-fit attestation", "freeze approved", "first access")
DATASETS = ("benzene-taggar2006", "odcb-chandrakumar1993")
RUNNERS = ("owner", "participant", "agent")
NONE = "—"
_TIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}Z")
_SHA = re.compile(r"[0-9a-f]{64}")
_RELEASE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/+-]*")


@dataclass(frozen=True)
class Entry:
    at: datetime
    event: str
    dataset: str | None = None
    runner: str | None = None
    release_or_commit: str | None = None
    protocol_sha256: str | None = None


def _time(text: str, n: int) -> datetime:
    if not _TIME.fullmatch(text):
        raise ValueError(f"first-fit log row {n}: the time is not UTC to the minute (YYYY-MM-DDTHH:MMZ)")
    try:
        return datetime.strptime(text, "%Y-%m-%dT%H:%MZ").replace(tzinfo=UTC)
    except ValueError:
        raise ValueError(f"first-fit log row {n}: the time is not a valid date") from None


def _entry(cells: list[str], n: int) -> Entry:
    at, event, *rest = cells
    when = _time(at, n)
    if event not in EVENTS:
        raise ValueError(f"first-fit log row {n}: unknown event (known: {', '.join(EVENTS)})")
    if event != "submission":
        if any(c != NONE for c in rest):
            raise ValueError(f"first-fit log row {n}: a {event} row holds {NONE} in its other cells")
        return Entry(when, event)
    dataset, runner, release, protocol = rest
    protocol = protocol.strip("`")
    if dataset not in DATASETS:
        raise ValueError(f"first-fit log row {n}: the dataset is not one of {', '.join(DATASETS)}")
    if runner not in RUNNERS:
        raise ValueError(f"first-fit log row {n}: the runner role is not one of {', '.join(RUNNERS)}")
    if release == NONE or not _RELEASE.fullmatch(release):
        raise ValueError(f"first-fit log row {n}: no release or commit")
    if not _SHA.fullmatch(protocol):
        raise ValueError(f"first-fit log row {n}: the protocol revision is not a full SHA-256")
    return Entry(when, event, dataset, runner, release, protocol)


def parse(text: str) -> list[Entry]:
    """The log's entries, in order. Raises ValueError for a missing, repeated or malformed log."""
    if text.count(f"\n{HEADING}\n") + text.startswith(f"{HEADING}\n") != 1:
        raise ValueError(f"the ledger has no single '{HEADING}' section")
    section = text.split(f"{HEADING}\n", 1)[1].split("\n## ", 1)[0]
    lines = section.splitlines()
    try:
        start = lines.index(HEADER)
    except ValueError:
        raise ValueError("the first-fit log has no table with the frozen header") from None
    if lines[start + 1 : start + 2] != ["|---|---|---|---|---|---|"]:
        raise ValueError("the first-fit log table has no separator row")
    entries: list[Entry] = []
    for n, line in enumerate(lines[start + 2 :], start=1):
        if not line.strip():
            break
        if not (line.startswith("| ") and line.endswith(" |")):
            raise ValueError(f"first-fit log row {n}: not a table row")
        cells = [c.strip() for c in line[1:-1].split("|")]
        if len(cells) != 6:
            raise ValueError(f"first-fit log row {n}: {len(cells)} cells, not 6")
        entry = _entry(cells, n)
        if entries and entry.at < entries[-1].at:
            raise ValueError(f"first-fit log row {n}: earlier than the row before it")
        if entry.event in SINGLE and any(e.event == entry.event for e in entries):
            raise ValueError(f"first-fit log row {n}: a second {entry.event}")
        if entry.event == "first access" and not submissions(entries):
            raise ValueError(f"first-fit log row {n}: first access before any submission")
        entries.append(entry)
    return entries


def submissions(entries: Sequence[Entry]) -> list[Entry]:
    return [e for e in entries if e.event == "submission"]


def extends(old: Sequence[Entry], new: Sequence[Entry]) -> bool:
    """Whether ``new`` keeps every entry of ``old``, unchanged and in order, adding only after."""
    return len(new) >= len(old) and list(new[: len(old)]) == list(old)
