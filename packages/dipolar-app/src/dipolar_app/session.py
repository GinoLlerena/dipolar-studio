"""The headless session (04 D14, D15, §8.1, §8.2).

State is immutable and replaced atomically under a single writer lock. Four counters stay
separate: the journal sequence, the science revision (advanced only by science events), the
workspace revision (view only) and, later, job status. Proposals have their own event domain and
advance neither revision.

A command runs as ``session.commit(plan)``: under the lock, ``plan(state)`` validates against
the current state and returns the events and the result. The events are written to the journal
(fsynced) **before** they are applied in memory and acknowledged. Replay applies recorded events
and never re-runs computations.

One journal record is one transaction. It holds one or more **steps** (an accepted proposal has
one per accepted command), and each step advances the revisions of the domains it touches, so a
proposal's chain of ``expected_science_revision`` values replays exactly. The record is still
written as one line with one checksum, so it is applied entirely or not at all (M2 step 2).

**Idempotency (§8.1).** A command may carry a ``request_id``. The record stores the request ID and
its outcome, so the deduplication table is rebuilt by replay: a retry after a lost response, or
after a restart, returns the stored outcome and is never applied twice. Keys are scoped to the
actor; reusing a key for a different command is refused.

**Undo (§8.2).** The science history is global and chronological. Every record that changes the
science pushes one undo entry (the project before it); ``history.undo`` and ``history.redo`` are
new, journaled commands whose events say which way they move, so revisions never decrease and
replay rebuilds the stacks.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import threading
import uuid
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field, replace
from typing import Any, Literal, TypeVar

from dipolar_core.context import numerical_context
from pydantic import BaseModel

from dipolar_app.errors import ErrorCode, OperationError
from dipolar_app.journal import JOURNAL_SCHEMA_VERSION, Journal, JournalCorrupt, Recovery
from dipolar_app.policy import Principal
from dipolar_app.project import (
    PROJECT_SCHEMA_VERSION,
    Project,
    canonical_json,
    migrate_project,
    payload_hash,
    science_hash,
)

T = TypeVar("T")

SCIENCE, WORKSPACE, PROPOSAL = "science", "workspace", "proposal"
DOMAINS = frozenset({SCIENCE, WORKSPACE, PROPOSAL})

#: Undo depth: the oldest entries are dropped beyond this.
MAX_UNDO = 100
#: Decided proposals kept in the state for listing; pending ones are always kept.
MAX_DECIDED_PROPOSALS = 64

HistoryKind = Literal["do", "undo", "redo"]
ProposalStatus = Literal["pending", "accepted", "rejected", "expired"]


@dataclass(frozen=True, slots=True)
class ViewState:
    """Shared view state (D15). The beta has a single shared view."""

    selection: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    """One undoable (or redoable) science change."""

    project: Project  # the project that undoing (or redoing) restores
    operation: str  # the command that made the change
    actor: str
    science_revision: int  # the science revision the change produced


@dataclass(frozen=True, slots=True)
class ProposalStep:
    operation: str
    args_json: str  # canonical JSON of the validated arguments (immutable, and its size is known)
    depends_on: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class Proposal:
    id: str
    proposer: str
    created_at: str  # ISO 8601, UTC
    expires_at: str
    base_science_revision: int
    note: str
    steps: tuple[ProposalStep, ...]
    status: ProposalStatus = "pending"
    decided_by: str | None = None
    decided_at: str | None = None
    accepted_steps: tuple[int, ...] = ()
    reason: str = ""

    @property
    def size(self) -> int:
        return sum(len(s.args_json.encode()) for s in self.steps)


@dataclass(frozen=True, slots=True)
class SessionState:
    project: Project | None = None
    view: ViewState = field(default_factory=ViewState)
    seq: int = 0
    science_revision: int = 0
    workspace_revision: int = 0
    undo: tuple[HistoryEntry, ...] = ()  # oldest first
    redo: tuple[HistoryEntry, ...] = ()  # the next redo last
    proposals: tuple[Proposal, ...] = ()  # in the order of their last event (creation or decision)
    next_proposal: int = 1

    @property
    def science_hash(self) -> str:
        return science_hash(self.project)

    def proposal(self, proposal_id: str) -> Proposal | None:
        return next((p for p in self.proposals if p.id == proposal_id), None)


Event = dict[str, Any]


class Steps(tuple[list[Event], ...]):
    """A plan's events split into steps (each advances the revisions of its domains)."""

    __slots__ = ()


Plan = Callable[[SessionState], tuple["list[Event] | Steps", T]]


def as_steps(events: list[Event] | Steps) -> list[list[Event]]:
    if isinstance(events, Steps):
        return [list(step) for step in events if step]
    return [list(events)] if events else []


def _proposal_from_event(data: dict[str, Any]) -> Proposal:
    steps = tuple(
        ProposalStep(operation=s["operation"], args_json=canonical_json(s["args"]), depends_on=tuple(s["depends_on"]))
        for s in data["steps"]
    )
    return Proposal(
        id=data["id"],
        proposer=data["proposer"],
        created_at=data["created_at"],
        expires_at=data["expires_at"],
        base_science_revision=data["base_science_revision"],
        note=data["note"],
        steps=steps,
    )


def _prune(proposals: tuple[Proposal, ...]) -> tuple[Proposal, ...]:
    decided = [p.id for p in proposals if p.status != "pending"]
    dropped = set(decided[: max(0, len(decided) - MAX_DECIDED_PROPOSALS)])
    return tuple(p for p in proposals if p.id not in dropped)


def apply_event(state: SessionState, event: Event) -> SessionState:
    """Pure state transition for one event. Unknown event types are an error, never skipped."""
    kind = event["type"]
    if kind == "project.replaced":
        project = Project.model_validate(migrate_project(event["project"]))
        return replace(state, project=project)
    if kind == "view.selection_set":
        return replace(state, view=replace(state.view, selection=tuple(event["selection"])))
    if kind == "proposal.created":
        proposal = _proposal_from_event(event["proposal"])
        if proposal.id != f"prp_{state.next_proposal:06d}":
            raise ValueError(f"proposal {proposal.id!r} out of sequence")
        return replace(state, proposals=(*state.proposals, proposal), next_proposal=state.next_proposal + 1)
    if kind == "proposal.decided":
        target = state.proposal(event["id"])
        if target is None or target.status != "pending":
            raise ValueError(f"proposal {event['id']!r} is not pending")
        status = event["status"]
        if status not in ("accepted", "rejected", "expired"):
            raise ValueError(f"unknown proposal status {status!r}")
        decided = replace(
            target,
            status=status,
            decided_by=event["by"],
            decided_at=event["at"],
            accepted_steps=tuple(event["accepted_steps"]),
            reason=event["reason"],
        )
        # A decided proposal moves to the end, so the decided ones stay in decision order and
        # pruning drops the earliest decisions.
        proposals = (*(p for p in state.proposals if p.id != target.id), decided)
        return replace(state, proposals=_prune(proposals))
    raise ValueError(f"unknown event type {kind!r}")


def _history_kind(steps: Sequence[Sequence[Event]]) -> HistoryKind | None:
    kinds = {e.get("history", "do") for step in steps for e in step if e["domain"] == SCIENCE}
    if not kinds:
        return None
    if len(kinds) > 1 or not kinds <= {"do", "undo", "redo"}:
        raise ValueError(f"a transaction mixes history kinds {sorted(kinds)}")
    kind: HistoryKind = kinds.pop()
    return kind


def apply_record(state: SessionState, steps: Sequence[Sequence[Event]], *, operation: str, actor: str) -> SessionState:
    """Apply one transaction: its steps in order, then one journal sequence number and, if it
    changed the science, one history entry."""
    before = state
    for step in steps:
        domains = set()
        for event in step:
            if event.get("domain") not in DOMAINS:
                raise ValueError(f"unknown event domain {event.get('domain')!r}")
            state = apply_event(state, event)
            domains.add(event["domain"])
        state = replace(
            state,
            science_revision=state.science_revision + (SCIENCE in domains),
            workspace_revision=state.workspace_revision + (WORKSPACE in domains),
        )
    state = replace(state, seq=state.seq + 1)
    kind = _history_kind(steps)
    if kind is None:
        return state
    if kind == "do":
        undo = state.undo
        if before.project is not None:  # opening the first project is not undoable
            entry = HistoryEntry(before.project, operation, actor, state.science_revision)
            undo = (*undo, entry)[-MAX_UNDO:]
        return replace(state, undo=undo, redo=())
    if kind == "undo":
        if not state.undo:
            raise ValueError("an undo with nothing to undo")
        undone = state.undo[-1]
        assert before.project is not None  # an undo entry exists only after a project
        redo_entry = HistoryEntry(before.project, undone.operation, undone.actor, undone.science_revision)
        return replace(state, undo=state.undo[:-1], redo=(*state.redo, redo_entry))
    if not state.redo:
        raise ValueError("a redo with nothing to redo")
    redone = state.redo[-1]
    assert before.project is not None
    undo_entry = HistoryEntry(before.project, redone.operation, redone.actor, state.science_revision)
    return replace(state, undo=(*state.undo, undo_entry)[-MAX_UNDO:], redo=state.redo[:-1])


def apply_transaction(state: SessionState, events: Iterable[Event]) -> SessionState:
    """One single-step transaction (kept for callers that build states by hand)."""
    events = list(events)
    return apply_record(state, [events] if events else [], operation="", actor="")


def request_fingerprint(operation: str, args: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(canonical_json({"operation": operation, "args": args}).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class StoredOutcome:
    """The acknowledged outcome of a request, returned again for a retry with the same key."""

    fingerprint: str
    operation: str
    result: dict[str, Any]
    revisions: dict[str, int]


@dataclass(frozen=True, slots=True)
class Committed[R]:
    """What ``Session.commit`` did: the result and the state it produced (for a dry run, the state
    it *would* produce), or the stored outcome of an earlier request with the same key."""

    result: R | None
    before: SessionState
    state: SessionState
    replayed: StoredOutcome | None = None


class Session:
    def __init__(self, journal: Journal | None = None, *, contract_version: str) -> None:
        self._lock = threading.Lock()
        self._state = SessionState()
        self._requests: dict[tuple[str, str], StoredOutcome] = {}
        self._journal = journal
        self._contract_version = contract_version
        self._failure: str | None = None
        #: What opening the journal repaired (an unacknowledged torn tail), if anything.
        self.recovery: Recovery | None = None
        if journal is not None:
            self.recovery = journal.recover_torn_tail()
            self._state, self._requests = replay_full(journal)

    @property
    def state(self) -> SessionState:
        """A consistent snapshot. Queries compute from it outside the lock."""
        return self._state

    @property
    def failed(self) -> str | None:
        """Why the session stopped accepting commands, or None while it is healthy."""
        return self._failure

    def commit(
        self,
        principal: Principal,
        operation: str,
        args: dict[str, Any],
        plan: Plan[T],
        *,
        request_id: str | None = None,
        dry_run: bool = False,
    ) -> Committed[T]:
        """Plan, journal, then apply, atomically.

        - ``request_id``: a retry of an acknowledged request returns its stored outcome
          (``Committed.replayed``) and changes nothing; the same key with other arguments is
          refused. A request is recorded even when it changes nothing, so its retry stays a no-op.
        - ``dry_run``: plan and apply in memory only. Nothing is journaled, stored or acknowledged
          as done, and no revision is consumed.

        Fail-stop: if the journal append raises, the outcome on disk is uncertain (the record may
        or may not be durable). The in-memory state is left unchanged and **every later command is
        refused** until the process restarts and replays the journal, which is the source of truth.
        Queries keep working on the last acknowledged state.
        """
        if dry_run and request_id is not None:
            raise ValueError("a dry run is never recorded, so it takes no request_id")
        with self._lock:
            if self._failure is not None:
                raise OperationError(
                    ErrorCode.JOURNAL_FAILED,
                    "the session stopped accepting commands after a journal failure",
                    hint="restart dipolar serve; it replays the journal, which is the source of truth",
                    details={"cause": self._failure},
                )
            current = self._state
            fingerprint = request_fingerprint(operation, args)
            if request_id is not None:
                stored = self._requests.get((principal.actor, request_id))
                if stored is not None:
                    if stored.fingerprint != fingerprint:
                        raise OperationError(
                            ErrorCode.IDEMPOTENCY_KEY_REUSED,
                            f"request_id {request_id!r} was already used for a different command",
                            offending_field="request_id",
                            hint="use a new request_id for each distinct command; reuse it only to retry",
                            details={"operation": stored.operation},
                        )
                    return Committed(None, current, current, replayed=stored)
            planned, result = plan(current)
            steps = as_steps(planned)
            if not steps and request_id is None:
                return Committed(result, current, current)
            new_state = apply_record(current, steps, operation=operation, actor=principal.actor)
            if dry_run:
                return Committed(result, current, new_state)
            revisions = {SCIENCE: new_state.science_revision, WORKSPACE: new_state.workspace_revision}
            outcome: StoredOutcome | None = None
            if request_id is not None:
                if not isinstance(result, BaseModel):
                    raise TypeError(f"{operation}: a recorded request needs a model result")
                outcome = StoredOutcome(fingerprint, operation, result.model_dump(mode="json"), revisions)
            if self._journal is not None:
                events = [e for step in steps for e in step]
                record: dict[str, Any] = {
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
                    "revisions": revisions,
                    "numerical_context": numerical_context(),
                    "science_hash": new_state.science_hash,
                }
                if len(steps) != 1:
                    record["step_lengths"] = [len(step) for step in steps]
                if outcome is not None:
                    record["request"] = {"id": request_id, "outcome": outcome.result}
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
            if outcome is not None:
                assert request_id is not None
                self._requests[(principal.actor, request_id)] = outcome
            self._state = new_state
            return Committed(result, current, new_state)


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


def _record_steps(record: dict[str, Any]) -> list[list[Event]]:
    """Split a record's events into its steps (one step unless ``step_lengths`` says otherwise)."""
    events = record["events"]
    if not isinstance(events, list):
        raise JournalCorrupt(f"record seq {record.get('seq')}: events is not a list")
    lengths = record.get("step_lengths")
    if lengths is None:
        return [events] if events else []
    if (
        not isinstance(lengths, list)
        or not all(isinstance(n, int) and not isinstance(n, bool) and n > 0 for n in lengths)
        or sum(lengths) != len(events)
    ):
        raise JournalCorrupt(f"record seq {record.get('seq')}: step_lengths do not split its events")
    steps, start = [], 0
    for n in lengths:
        steps.append(events[start : start + n])
        start += n
    return steps


def _record_request(record: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    request = record.get("request")
    if request is None:
        return None
    if (
        not isinstance(request, dict)
        or set(request) != {"id", "outcome"}
        or not isinstance(request["id"], str)
        or not isinstance(request["outcome"], dict)
    ):
        raise JournalCorrupt(f"record seq {record.get('seq')}: malformed request entry")
    return request["id"], request["outcome"]


def replay_full(journal: Journal) -> tuple[SessionState, dict[tuple[str, str], StoredOutcome]]:
    """Rebuild the state and the request table from the journal, checking sequence, revisions and
    science hash.

    A record written under an older project schema is checked against the hash of the project
    payload *as stored*, then migrated (``migrate_project``, round 22). So old journals replay,
    and their integrity is still verified.
    """
    state = SessionState()
    requests: dict[tuple[str, str], StoredOutcome] = {}
    stored: dict[str, Any] | None = None  # the last project payload as written in the journal
    schema = 1
    for record in journal.records():
        schema = _record_schema(record, schema)
        steps = _record_steps(record)
        for event in record["events"]:
            if event.get("type") == "project.replaced":
                stored = event["project"]
        if record.get("numerical_context") != numerical_context():
            raise JournalCorrupt(
                f"record seq {record.get('seq')}: written under a different numerical context; "
                "a migration is required before replay"
            )
        try:
            state = apply_record(state, steps, operation=str(record.get("operation")), actor=str(record.get("actor")))
        except (KeyError, TypeError, ValueError) as exc:
            raise JournalCorrupt(f"record seq {record.get('seq')}: cannot be applied ({exc})") from None
        recorded = record["revisions"]
        if (
            record["seq"] != state.seq
            or recorded[SCIENCE] != state.science_revision
            or recorded[WORKSPACE] != state.workspace_revision
            or record["science_hash"] != _recorded_hash(schema, state, stored)
        ):
            raise JournalCorrupt(f"record seq {record['seq']}: replay does not reproduce the recorded state")
        request = _record_request(record)
        if request is not None:
            key = (str(record["actor"]), request[0])
            if key in requests:
                raise JournalCorrupt(f"record seq {record['seq']}: request_id {request[0]!r} recorded twice")
            fingerprint = request_fingerprint(str(record["operation"]), record["args"])
            requests[key] = StoredOutcome(fingerprint, str(record["operation"]), request[1], dict(recorded))
    return state, requests


def replay(journal: Journal) -> SessionState:
    return replay_full(journal)[0]
