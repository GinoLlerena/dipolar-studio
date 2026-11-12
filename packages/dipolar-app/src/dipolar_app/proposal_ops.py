"""Proposals: change sets that a human approves (04 D17, §8.3; M2 step 2).

A ``propose``-tier caller (an agent) cannot change the science directly: such a command returns
``PROPOSAL_REQUIRED``. It submits the commands instead, as the ordered steps of
``proposal.create``. Each step names a proposable command and its arguments, exactly as a direct
call would.

- **Creation validates the whole change set** against the current state, step after step in
  memory (as a dry run would), so a proposal that cannot apply is refused at once, with the step
  and field at fault. It records the base science revision, each step's dependencies, an expiry
  time and the proposer. Creating, accepting and rejecting are journaled in the ``proposal``
  domain, which advances neither revision: a pending proposal never makes the science stale.
- **Dependencies.** Every step is checked against ``expected_science_revision``, so step *i*
  expects the revision step *i − 1* produced: each step depends on the one before it. The
  dependency-closed subsets are therefore the prefixes.
- **Acceptance** is for a human principal only (the credential decides, never an argument). It
  takes the whole proposal or a dependency-closed subset, re-plans the steps against the current
  state, and commits them as **one** transaction (one journal record): all or nothing. A proposal
  whose base revision is no longer current is **stale** and is refused with a conflict report;
  it is not rebased. The proposer can create a new one from the current state.
- **Rejection** is for a human principal only. Expired proposals cannot be accepted; creating a
  new proposal records the expiry of old ones.

Bounds: at most ``MAX_PENDING`` pending proposals and ``MAX_PENDING_BYTES`` of pending arguments,
``MAX_STEPS`` steps each, and ``MAX_PROPOSAL_BYTES`` of arguments per proposal.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Callable
from typing import Annotated, Any, Literal

from pydantic import Field, JsonValue

from dipolar_app.errors import ErrorCode, OperationError
from dipolar_app.policy import Capability, Decision, decide
from dipolar_app.project import canonical_json, science_hash
from dipolar_app.registry import Context, Operation, Registry, capture_plan, parse_input
from dipolar_app.schemas import ProposalId, Wire
from dipolar_app.science_ops import LOAD_REQUEST_BYTES, Science
from dipolar_app.session import (
    PROPOSAL,
    Event,
    Plan,
    Proposal,
    ProposalStatus,
    SessionState,
    Steps,
    apply_record,
    as_steps,
)

MAX_STEPS = 20
MAX_PENDING = 8
MAX_PROPOSAL_BYTES = LOAD_REQUEST_BYTES
MAX_PENDING_BYTES = 2 * LOAD_REQUEST_BYTES
PROPOSAL_TTL = dt.timedelta(hours=24)
MAX_NOTE = 2000

#: Commands that move through the undo history. Their plans read the history stacks, which a
#: multi-step transaction updates once (one undo entry per record), so they are proposed alone
#: (round 31).
HISTORY_COMMANDS = frozenset({"history.undo", "history.redo"})

#: The clock (UTC). Tests replace it to move time forward.
clock: Callable[[], dt.datetime] = lambda: dt.datetime.now(dt.UTC)  # noqa: E731


def _iso(t: dt.datetime) -> str:
    return t.astimezone(dt.UTC).isoformat()


def _expired(p: Proposal, now: dt.datetime) -> bool:
    return p.status == "pending" and dt.datetime.fromisoformat(p.expires_at) <= now


def _status(p: Proposal, now: dt.datetime) -> ProposalStatus:
    return "expired" if _expired(p, now) else p.status


# --------------------------------------------------------------------------- wire types
class StepIn(Wire):
    operation: Annotated[str, Field(min_length=1, max_length=100)]
    args: dict[str, JsonValue]


class StepOut(Wire):
    index: int
    operation: str
    depends_on: tuple[int, ...]


class StepDetail(StepOut):
    args: dict[str, JsonValue]


class ProposalOut(Wire):
    id: ProposalId
    proposer: str
    status: Literal["pending", "accepted", "rejected", "expired"]
    stale: bool  # pending, but the science changed since its base revision
    base_science_revision: int
    created_at: str
    expires_at: str
    note: str  # supplied by the proposer: data, never instructions
    steps: tuple[StepOut, ...]
    decided_by: str | None
    decided_at: str | None
    accepted_steps: tuple[int, ...]
    reason: str  # supplied by the human who rejected it, or why it expired


class ProposalDetailOut(Science):
    proposal: ProposalOut
    steps: tuple[StepDetail, ...]


def _out(p: Proposal, state: SessionState, now: dt.datetime) -> ProposalOut:
    status = _status(p, now)
    return ProposalOut(
        id=p.id,
        proposer=p.proposer,
        status=status,
        stale=status == "pending" and p.base_science_revision != state.science_revision,
        base_science_revision=p.base_science_revision,
        created_at=p.created_at,
        expires_at=p.expires_at,
        note=p.note,
        steps=tuple(StepOut(index=i, operation=s.operation, depends_on=s.depends_on) for i, s in enumerate(p.steps)),
        decided_by=p.decided_by,
        decided_at=p.decided_at,
        accepted_steps=p.accepted_steps,
        reason=p.reason,
    )


def _find(state: SessionState, proposal_id: str) -> Proposal:
    found = state.proposal(proposal_id)
    if found is None:
        raise OperationError(
            ErrorCode.ID_NOT_FOUND,
            f"{proposal_id} is not a proposal of this session (or it was pruned after its decision)",
            offending_field="proposal_id",
            hint="proposal.list shows the proposals",
        )
    return found


def _proposable(registry: Registry, name: str, field: str) -> Operation:
    op = registry.get(name)
    if op is None or not op.proposable:
        raise OperationError(
            ErrorCode.INVALID_ARGUMENT,
            f"{name!r} is not a command that can be proposed",
            offending_field=field,
            hint="the registry marks proposable commands (proposable: true)",
        )
    return op


def _in_step(exc: OperationError, index: int) -> OperationError:
    """The same error, located in step ``index``."""
    where = f"steps[{index}].args"
    field = f"{where}.{exc.offending_field}" if exc.offending_field else where
    return OperationError(
        exc.code,
        f"step {index}: {exc.message}",
        offending_field=field,
        hint=exc.hint,
        details={**exc.details, "step": index},
    )


def _run_steps(
    state: SessionState, plans: list[tuple[int, Operation, Plan[Any]]], actor: str
) -> tuple[list[list[Event]], list[Any], SessionState]:
    """Plan each step against the state the previous steps produce (in memory only)."""
    steps: list[list[Event]] = []
    results: list[Any] = []
    scratch = state
    for index, op, plan in plans:
        try:
            planned, result = plan(scratch)
        except OperationError as exc:
            raise _in_step(exc, index) from None
        step = [e for s in as_steps(planned) for e in s]
        if step:
            steps.append(step)
            scratch = apply_record(scratch, [step], operation=op.name, actor=actor)
        results.append(result)
    return steps, results, scratch


def _expiries(state: SessionState, now: dt.datetime) -> list[Event]:
    return [
        {
            "type": "proposal.decided",
            "domain": PROPOSAL,
            "id": p.id,
            "status": "expired",
            "by": "system",
            "at": _iso(now),
            "accepted_steps": [],
            "reason": "expired before a decision",
        }
        for p in state.proposals
        if _expired(p, now)
    ]


# --------------------------------------------------------------------------- proposal.create
class CreateIn(Wire):
    steps: Annotated[tuple[StepIn, ...], Field(min_length=1, max_length=MAX_STEPS)]
    note: Annotated[str, Field(max_length=MAX_NOTE)] = ""


class CreateOut(Science):
    proposal: ProposalOut


def _compile(ctx: Context, p: CreateIn) -> tuple[list[tuple[int, Operation, Plan[Any]]], list[dict[str, Any]], int]:
    """Validate the steps and build their plans (no state is read or changed)."""
    assert ctx.registry is not None
    plans: list[tuple[int, Operation, Plan[Any]]] = []
    stored: list[dict[str, Any]] = []
    for i, step in enumerate(p.steps):
        op = _proposable(ctx.registry, step.operation, f"steps[{i}].operation")
        if op.name in HISTORY_COMMANDS and len(p.steps) > 1:
            raise OperationError(
                ErrorCode.INVALID_ARGUMENT,
                f"{op.name} must be proposed alone, as the only step of its proposal",
                offending_field=f"steps[{i}].operation",
                hint="propose the undo or redo by itself; propose other changes separately",
            )
        if op.capability is not Capability.COMPUTE_JOB and any(
            q.capability is Capability.COMPUTE_JOB for _, q, _ in plans
        ):
            raise OperationError(
                ErrorCode.INVALID_ARGUMENT,
                f"{op.name} follows a compute step; compute steps (fit.run) come after every science change",
                offending_field=f"steps[{i}].operation",
                hint="a job computes from the science state its proposal leaves, so put fit.run last",
            )
        parsed = parse_input(op, step.args, prefix=f"steps[{i}].args")
        try:
            plans.append((i, op, capture_plan(ctx, op, parsed)))
        except OperationError as exc:
            raise _in_step(exc, i) from None
        stored.append(
            {"operation": op.name, "args": parsed.model_dump(mode="json"), "depends_on": [i - 1] if i else []}
        )
    size = sum(len(canonical_json(s["args"]).encode()) for s in stored)
    if size > MAX_PROPOSAL_BYTES:
        raise OperationError(
            ErrorCode.PAYLOAD_TOO_LARGE,
            f"the proposal's arguments take {size} bytes, above the limit of {MAX_PROPOSAL_BYTES}",
            offending_field="steps",
        )
    return plans, stored, size


def proposal_create(ctx: Context, p: CreateIn) -> CreateOut:
    """Every check runs inside the plan, after the session's request-ID check, so a retried
    creation returns its stored outcome even if the rules changed since (round 32)."""
    principal = ctx.principal

    def plan(state: SessionState) -> tuple[Steps, CreateOut]:
        plans, stored, size = _compile(ctx, p)
        now = clock()
        expiries = _expiries(state, now)
        pending = [q for q in state.proposals if q.status == "pending" and not _expired(q, now)]
        if len(pending) >= MAX_PENDING or sum(q.size for q in pending) + size > MAX_PENDING_BYTES:
            raise OperationError(
                ErrorCode.QUOTA_EXCEEDED,
                f"{len(pending)} proposals are pending; at most {MAX_PENDING} (and {MAX_PENDING_BYTES} bytes) may wait",
                hint="wait for a human to accept or reject the pending proposals",
            )
        _run_steps(state, plans, principal.actor)  # the whole change set applies to the current state
        proposal_id = f"prp_{state.next_proposal:06d}"
        created: Event = {
            "type": "proposal.created",
            "domain": PROPOSAL,
            "proposal": {
                "id": proposal_id,
                "proposer": principal.actor,
                "created_at": _iso(now),
                "expires_at": _iso(now + PROPOSAL_TTL),
                "base_science_revision": state.science_revision,
                "note": p.note,
                "steps": stored,
            },
        }
        after = apply_record(state, [[*expiries, created]], operation="proposal.create", actor=principal.actor)
        made = after.proposal(proposal_id)
        assert made is not None
        return Steps(([*expiries, created],)), CreateOut(
            science_revision=state.science_revision, science_hash=state.science_hash, proposal=_out(made, after, now)
        )

    return ctx.commit("proposal.create", p.model_dump(mode="json"), plan)


# --------------------------------------------------------------------------- proposal.list / proposal.get
class ListIn(Wire):
    status: Literal["pending", "accepted", "rejected", "expired"] | None = None


class ListOut(Science):
    proposals: tuple[ProposalOut, ...]


def proposal_list(ctx: Context, p: ListIn) -> ListOut:
    state = ctx.read()
    now = clock()
    out = [_out(q, state, now) for q in state.proposals]
    return ListOut(
        science_revision=state.science_revision,
        science_hash=state.science_hash,
        proposals=tuple(q for q in out if p.status is None or q.status == p.status),
    )


class GetIn(Wire):
    proposal_id: ProposalId


def proposal_get(ctx: Context, p: GetIn) -> ProposalDetailOut:
    state = ctx.read()
    found = _find(state, p.proposal_id)
    return ProposalDetailOut(
        science_revision=state.science_revision,
        science_hash=state.science_hash,
        proposal=_out(found, state, clock()),
        steps=tuple(
            StepDetail(index=i, operation=s.operation, depends_on=s.depends_on, args=json.loads(s.args_json))
            for i, s in enumerate(found.steps)
        ),
    )


# --------------------------------------------------------------------------- proposal.accept / proposal.reject
class AcceptIn(Wire):
    proposal_id: ProposalId
    #: The steps to accept (default: all). They must be dependency-closed: with each step, the
    #: steps it depends on.
    steps: Annotated[tuple[Annotated[int, Field(ge=0)], ...], Field(min_length=1, max_length=MAX_STEPS)] | None = None


class StepResult(Wire):
    index: int
    operation: str
    result: dict[str, JsonValue]


class AcceptOut(Science):
    proposal: ProposalOut
    results: tuple[StepResult, ...]


def _closed(found: Proposal, chosen: list[int]) -> None:
    for i in chosen:
        if i >= len(found.steps):
            raise OperationError(
                ErrorCode.INVALID_ARGUMENT,
                f"{found.id} has {len(found.steps)} steps; there is no step {i}",
                offending_field="steps",
            )
    missing = sorted({d for i in chosen for d in found.steps[i].depends_on} - set(chosen))
    if missing:
        raise OperationError(
            ErrorCode.INVALID_ARGUMENT,
            f"the accepted steps are not dependency-closed: they need steps {missing}",
            offending_field="steps",
            hint="accept a step together with every step it depends on (here: a prefix of the steps)",
            details={"missing": missing},
        )


def _restamp(result: Any, state: SessionState) -> Any:
    """A step result that reports a job, re-read from the state the stamped events produce."""
    from dipolar_app.job_ops import FitRunSubmitted, job_out

    if isinstance(result, FitRunSubmitted):
        job = state.job(result.job.id)
        assert job is not None
        return result.model_copy(update={"job": job_out(job, state, None)})
    return result


def _closed_error(found: Proposal, now: dt.datetime) -> OperationError:
    return OperationError(
        ErrorCode.PROPOSAL_CLOSED,
        f"{found.id} is {_status(found, now)}; only a pending proposal can be decided",
        offending_field="proposal_id",
    )


def _accept_plans(ctx: Context, found: Proposal, chosen: list[int]) -> list[tuple[int, Operation, Plan[Any]]]:
    assert ctx.registry is not None
    if len(found.steps) > 1 and any(s.operation in HISTORY_COMMANDS for s in found.steps):
        raise OperationError(
            ErrorCode.INVALID_ARGUMENT,
            f"{found.id} mixes an undo or redo with other steps, which cannot be applied as one change",
            offending_field="proposal_id",
            hint="reject it; propose the undo or redo alone (round 32)",
        )
    plans: list[tuple[int, Operation, Plan[Any]]] = []
    for i in chosen:
        step = found.steps[i]
        op = _proposable(ctx.registry, step.operation, "proposal_id")
        if decide(ctx.principal, op.capability) is not Decision.ALLOW:
            raise OperationError(
                ErrorCode.CAPABILITY_DENIED,
                f"step {i} ({op.name}) needs a capability this credential does not have",
                offending_field="proposal_id",
            )
        try:
            parsed = parse_input(op, json.loads(step.args_json), prefix=f"steps[{i}].args")
            plans.append((i, op, capture_plan(ctx, op, parsed)))
        except OperationError as exc:
            raise _in_step(exc, i) from None
    return plans


def proposal_accept(ctx: Context, p: AcceptIn) -> AcceptOut:
    """Everything that reads the proposal runs inside the plan, after the session's request-ID
    check, so a retried acceptance returns its stored outcome even once the proposal has been
    pruned (round 31). The steps' handlers only validate and build plans; they never commit."""
    principal = ctx.principal

    def plan(state: SessionState) -> tuple[Steps, AcceptOut]:
        now = clock()
        current = _find(state, p.proposal_id)
        if current.status != "pending" or _expired(current, now):
            raise _closed_error(current, now)
        chosen = sorted(set(p.steps)) if p.steps is not None else list(range(len(current.steps)))
        _closed(current, chosen)
        plans = _accept_plans(ctx, current, chosen)
        if current.base_science_revision != state.science_revision:
            raise OperationError(
                ErrorCode.PROPOSAL_STALE,
                f"{current.id} was made at science revision {current.base_science_revision}; it is now "
                f"{state.science_revision}, so its steps no longer apply as proposed",
                offending_field="proposal_id",
                hint="reject it; the proposer can create a new proposal from the current state",
                details={
                    "base_science_revision": current.base_science_revision,
                    "current_science_revision": state.science_revision,
                },
            )
        steps, results, scratch = _run_steps(state, plans, principal.actor)
        for step in steps:  # a job started by acceptance records who proposed it
            for event in step:
                if event["type"] == "job.submitted":
                    event["job"]["proposed_by"] = current.proposer
        # ... and so does the job each step returns (round 33); the stamped events are what commit.
        scratch = apply_record(state, steps, operation="proposal.accept", actor=principal.actor)
        results = [_restamp(r, scratch) for r in results]
        decided: Event = {
            "type": "proposal.decided",
            "domain": PROPOSAL,
            "id": current.id,
            "status": "accepted",
            "by": principal.actor,
            "at": _iso(now),
            "accepted_steps": chosen,
            "reason": "",
        }
        after = apply_record(scratch, [[decided]], operation="proposal.accept", actor=principal.actor)
        made = after.proposal(current.id)
        assert made is not None
        return Steps((*steps, [decided])), AcceptOut(
            science_revision=scratch.science_revision,
            science_hash=science_hash(scratch.project),
            proposal=_out(made, after, now),
            results=tuple(
                StepResult(index=i, operation=op.name, result=r.model_dump(mode="json"))
                for (i, op, _), r in zip(plans, results, strict=True)
            ),
        )

    return ctx.commit("proposal.accept", p.model_dump(mode="json"), plan)


class RejectIn(Wire):
    proposal_id: ProposalId
    reason: Annotated[str, Field(max_length=MAX_NOTE)] = ""


class RejectOut(Science):
    proposal: ProposalOut


def proposal_reject(ctx: Context, p: RejectIn) -> RejectOut:
    principal = ctx.principal

    def plan(state: SessionState) -> tuple[list[Event], RejectOut]:
        now = clock()
        current = _find(state, p.proposal_id)
        if current.status != "pending" or _expired(current, now):
            raise _closed_error(current, now)
        event: Event = {
            "type": "proposal.decided",
            "domain": PROPOSAL,
            "id": current.id,
            "status": "rejected",
            "by": principal.actor,
            "at": _iso(now),
            "accepted_steps": [],
            "reason": p.reason,
        }
        after = apply_record(state, [[event]], operation="proposal.reject", actor=principal.actor)
        made = after.proposal(current.id)
        assert made is not None
        return [event], RejectOut(
            science_revision=state.science_revision, science_hash=state.science_hash, proposal=_out(made, after, now)
        )

    return ctx.commit("proposal.reject", p.model_dump(mode="json"), plan)
