"""The headless session (04 D14, D15, §8.1).

State is immutable and replaced atomically under a single writer lock. Four counters stay
separate: the journal sequence, the science revision (advanced only by science events), the
workspace revision (view only) and, later, job status.

A command runs as ``session.commit(plan)``: under the lock, ``plan(state)`` validates against
the current state and returns the events and the result. The events are written to the journal
(fsynced) **before** they are applied in memory and acknowledged. Replay applies recorded events
and never re-runs computations.
"""

from __future__ import annotations

import datetime as dt
import threading
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field, replace
from typing import Any, TypeVar

from dipolar_core.context import numerical_context

from dipolar_app.errors import ErrorCode, OperationError
from dipolar_app.journal import JOURNAL_SCHEMA_VERSION, Journal, JournalCorrupt, Recovery
from dipolar_app.policy import Principal
from dipolar_app.project import PROJECT_SCHEMA_VERSION, Project, migrate_project, payload_hash, science_hash

T = TypeVar("T")

SCIENCE, WORKSPACE = "science", "workspace"


@dataclass(frozen=True, slots=True)
class ViewState:
    """Shared view state (D15). The beta has a single shared view."""

    selection: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SessionState:
    project: Project | None = None
    view: ViewState = field(default_factory=ViewState)
    seq: int = 0
    science_revision: int = 0
    workspace_revision: int = 0

    @property
    def science_hash(self) -> str:
        return science_hash(self.project)


Event = dict[str, Any]
Plan = Callable[[SessionState], tuple[list[Event], T]]


def apply_event(state: SessionState, event: Event) -> SessionState:
    """Pure state transition for one event. Unknown event types are an error, never skipped."""
    kind = event["type"]
    if kind == "project.replaced":
        project = Project.model_validate(migrate_project(event["project"]))
        return replace(state, project=project)
    if kind == "view.selection_set":
        return replace(state, view=replace(state.view, selection=tuple(event["selection"])))
    raise ValueError(f"unknown event type {kind!r}")


def apply_transaction(state: SessionState, events: Iterable[Event]) -> SessionState:
    domains = set()
    for event in events:
        state = apply_event(state, event)
        domains.add(event["domain"])
    return replace(
        state,
        seq=state.seq + 1,
        science_revision=state.science_revision + (SCIENCE in domains),
        workspace_revision=state.workspace_revision + (WORKSPACE in domains),
    )


class Session:
    def __init__(self, journal: Journal | None = None, *, contract_version: str) -> None:
        self._lock = threading.Lock()
        self._state = SessionState()
        self._journal = journal
        self._contract_version = contract_version
        self._failure: str | None = None
        #: What opening the journal repaired (an unacknowledged torn tail), if anything.
        self.recovery: Recovery | None = None
        if journal is not None:
            self.recovery = journal.recover_torn_tail()
            self._state = replay(journal)

    @property
    def state(self) -> SessionState:
        """A consistent snapshot. Queries compute from it outside the lock."""
        return self._state

    @property
    def failed(self) -> str | None:
        """Why the session stopped accepting commands, or None while it is healthy."""
        return self._failure

    def commit(
        self, principal: Principal, operation: str, args: dict[str, Any], plan: Plan[T]
    ) -> tuple[T, SessionState]:
        """Plan, journal, then apply, atomically. Returns the result and the state it produced.

        Fail-stop: if the journal append raises, the outcome on disk is uncertain (the record may
        or may not be durable). The in-memory state is left unchanged and **every later command is
        refused** until the process restarts and replays the journal, which is the source of truth.
        Queries keep working on the last acknowledged state.
        """
        with self._lock:
            if self._failure is not None:
                raise OperationError(
                    ErrorCode.JOURNAL_FAILED,
                    "the session stopped accepting commands after a journal failure",
                    hint="restart dipolar serve; it replays the journal, which is the source of truth",
                    details={"cause": self._failure},
                )
            current = self._state
            events, result = plan(current)
            if not events:
                return result, current
            new_state = apply_transaction(current, events)
            if self._journal is not None:
                record = {
                    "journal_schema": JOURNAL_SCHEMA_VERSION,
                    "project_schema": PROJECT_SCHEMA_VERSION,
                    "contract_version": self._contract_version,
                    "seq": new_state.seq,
                    "txn_id": uuid.uuid4().hex,
                    "timestamp": dt.datetime.now(dt.UTC).isoformat(),
                    "actor": principal.actor,
                    "tier": principal.tier.value,
                    "operation": operation,
                    "args": args,
                    "events": events,
                    "revisions": {SCIENCE: new_state.science_revision, WORKSPACE: new_state.workspace_revision},
                    "numerical_context": numerical_context(),
                    "science_hash": new_state.science_hash,
                }
                try:
                    self._journal.append(record)
                except Exception as exc:
                    self._failure = f"{type(exc).__name__}: {exc}"
                    raise OperationError(
                        ErrorCode.JOURNAL_FAILED,
                        "the journal write failed; whether this command was recorded is uncertain",
                        hint="restart dipolar serve and read the state before retrying",
                        details={"cause": self._failure},
                    ) from exc
            self._state = new_state
            return result, new_state


def _record_schema(record: dict[str, Any], previous: int) -> int:
    """The record's project schema, validated (round 24). The metadata cannot choose a hash rule
    on its own:
    - it is a supported integer;
    - it never decreases along the journal;
    - every project payload in the record carries the same schema version.
    """
    seq = record.get("seq")
    version = record.get("project_schema")
    if not isinstance(version, int) or isinstance(version, bool) or not 1 <= version <= PROJECT_SCHEMA_VERSION:
        raise JournalCorrupt(f"record seq {seq}: unsupported project_schema {version!r}")
    if version < previous:
        raise JournalCorrupt(f"record seq {seq}: project_schema {version} follows a record written under {previous}")
    for event in record["events"]:
        if event.get("type") == "project.replaced":
            payload = event.get("project")
            if not isinstance(payload, dict) or payload.get("schema_version") != version:
                raise JournalCorrupt(f"record seq {seq}: a project payload does not match project_schema {version}")
    return version


def _recorded_hash(version: int, state: SessionState, stored: dict[str, Any] | None) -> str:
    """The hash a record should carry: of the current state, or, for a record written under an
    older project schema, of the project payload exactly as it was stored."""
    if version < PROJECT_SCHEMA_VERSION and stored is not None:
        return payload_hash(stored)
    return state.science_hash


def replay(journal: Journal) -> SessionState:
    """Rebuild the state from the journal, checking sequence, revisions and science hash.

    A record written under an older project schema is checked against the hash of the project
    payload *as stored*, then migrated (``migrate_project``, round 22). So old journals replay,
    and their integrity is still verified.
    """
    state = SessionState()
    stored: dict[str, Any] | None = None  # the last project payload as written in the journal
    schema = 1
    for record in journal.records():
        schema = _record_schema(record, schema)
        for event in record["events"]:
            if event.get("type") == "project.replaced":
                stored = event["project"]
        if record.get("numerical_context") != numerical_context():
            raise JournalCorrupt(
                f"record seq {record.get('seq')}: written under a different numerical context; "
                "a migration is required before replay"
            )
        state = apply_transaction(state, record["events"])
        recorded = record["revisions"]
        if (
            record["seq"] != state.seq
            or recorded[SCIENCE] != state.science_revision
            or recorded[WORKSPACE] != state.workspace_revision
            or record["science_hash"] != _recorded_hash(schema, state, stored)
        ):
            raise JournalCorrupt(f"record seq {record['seq']}: replay does not reproduce the recorded state")
    return state
