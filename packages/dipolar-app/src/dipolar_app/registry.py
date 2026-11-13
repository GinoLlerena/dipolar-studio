"""Operation registry (04 D13, D20, §8.5) and the single typed dispatcher.

Every capability is declared once as an ``Operation``. Adapters (Python, HTTP, later MCP) are thin
wrappers around ``dispatch``, which alone applies policy, validation and error mapping.

Every call may carry two request options (the ``RequestEnvelope``, M2 step 2):

- ``request_id``: an idempotency key for a command. A retry with the same key returns the stored
  outcome (``replayed: true``) and is never applied twice (04 §8.1).
- ``dry_run``: plan a command against the current state and report what it would change
  (``dry_run`` in the success envelope), changing nothing (04 D17, §8.3). Queries change nothing
  already, so they refuse it.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Annotated, Any, Literal, TypeVar

from pydantic import BaseModel, Field, JsonValue, RootModel, ValidationError

from dipolar_app.changes import DryRunReport, dry_run_report
from dipolar_app.errors import ErrorCode, OperationError
from dipolar_app.policy import Capability, Decision, Principal, decide
from dipolar_app.schemas import MAX_SAFE_INTEGER, RequestId, Revision, Wire, wire_problem
from dipolar_app.session import Plan, Session, SessionState, StoredOutcome

T = TypeVar("T")

#: Semantic version of the tool contract (D20), independent of the package version.
CONTRACT_VERSION = "0.7.0"

Kind = Literal["query", "command"]
Effect = Literal["none", "model", "view", "proposal", "compute", "io", "destructive"]
Cost = Literal["instant", "seconds", "job"]


class Replayed(Exception):
    """Raised through the handler when a request ID was already acknowledged."""

    def __init__(self, outcome: StoredOutcome) -> None:
        super().__init__(outcome.operation)
        self.outcome = outcome


class _Captured(Exception):
    def __init__(self, plan: Plan[Any]) -> None:
        super().__init__("captured")
        self.plan = plan


@dataclass(slots=True)
class Context:
    """Per-call context. It records the one state snapshot the operation observed or produced, so
    the envelope's revisions always describe the same state as the result (never a later one).
    For a dry run, ``before`` is the current state and ``observed`` the state the command would
    produce."""

    session: Session
    principal: Principal
    registry: Registry | None = None
    request_id: str | None = None
    dry_run: bool = False
    capture: bool = False
    observed: SessionState | None = None
    before: SessionState | None = None

    def read(self) -> SessionState:
        """Take the operation's state snapshot (queries compute from it outside the lock)."""
        self.observed = self.session.state
        return self.observed

    def commit(self, operation: str, args: dict[str, Any], plan: Plan[T]) -> T:
        if self.capture:
            raise _Captured(plan)
        done = self.session.commit(
            self.principal, operation, args, plan, request_id=self.request_id, dry_run=self.dry_run
        )
        if done.replayed is not None:
            raise Replayed(done.replayed)
        self.before, self.observed = done.before, done.state
        assert done.result is not None
        return done.result


Handler = Callable[[Context, Any], BaseModel]


# --------------------------------------------------------------------------- envelopes (published in the snapshot)
class ErrorBody(Wire):
    code: ErrorCode
    message: str
    offending_field: str | None
    hint: str | None
    details: dict[str, JsonValue]


class ErrorEnvelope(Wire):
    ok: Literal[False]
    operation: str | None
    error: ErrorBody


class Revisions(Wire):
    science: Revision
    workspace: Revision


class SuccessEnvelope(Wire):
    ok: Literal[True]
    operation: str
    result: dict[str, JsonValue]  # validated against the operation's own output schema
    revisions: Revisions  # of the state the result describes; for a dry run, the unchanged state
    replayed: bool  # the stored outcome of an earlier request with the same request_id
    dry_run: DryRunReport | None  # set only for a dry run


class RequestEnvelope(Wire):
    """The body of every call: the operation's arguments and the request options."""

    args: dict[str, JsonValue] = Field(default_factory=dict)
    request_id: RequestId | None = None
    dry_run: bool = False


# ------------------------------------------------------------- the event stream (M3 step 1)
# One line of GET /api/v1/events (http.stream_events). Part of the contract so that the browser's
# types are generated like every other wire type; tests validate every line the stream sends.
FeedCursor = Annotated[int, Field(ge=0, le=MAX_SAFE_INTEGER)]
FeedJobStatus = Literal["queued", "running", "succeeded", "failed", "cancelled", "interrupted"]
FeedJobId = Annotated[str, Field(pattern=r"^job_[0-9]{6}$")]


class FeedHello(Wire):
    """First line: this server process's boot ID and the state's cursor, sequence and revisions."""

    kind: Literal["hello"]
    boot_id: str
    cursor: FeedCursor
    seq: FeedCursor
    revisions: Revisions


class FeedJob(Wire):
    job_id: FeedJobId
    status: FeedJobStatus


class FeedCommit(Wire):
    """One acknowledged transaction: no arguments or labels, only what changed."""

    kind: Literal["commit"]
    cursor: FeedCursor
    seq: FeedCursor
    operation: str
    actor: str
    revisions: Revisions
    domains: list[Literal["science", "workspace", "proposal", "job"]]
    jobs: list[FeedJob]


class FeedJobProgress(Wire):
    """A job's unjournaled progress (``running``)."""

    kind: Literal["job"]
    cursor: FeedCursor
    job_id: FeedJobId
    status: FeedJobStatus


class FeedPing(Wire):
    kind: Literal["ping"]
    cursor: FeedCursor


class FeedResync(Wire):
    """Entries were dropped or belong to an earlier boot: read the state again, then continue."""

    kind: Literal["resync"]
    cursor: FeedCursor


class FeedItem(RootModel[FeedHello | FeedCommit | FeedJobProgress | FeedPing | FeedResync]):
    """One line of the event stream."""


@dataclass(frozen=True, slots=True)
class Operation:
    name: str
    kind: Kind
    effect: Effect
    capability: Capability
    summary: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    handler: Handler
    cost: Cost = "instant"
    idempotent: bool = False
    revision_check: str = "none"
    examples: tuple[dict[str, Any], ...] = ()
    #: The HTTP request limit for this operation (bytes). Most take the default; project.load
    #: carries a whole project document (round 27).
    max_request_bytes: int = 1 << 20
    #: Whether a ``proposal.create`` step may name this command (M2 step 2).
    proposable: bool = False

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "effect": self.effect,
            "capability": self.capability.value,
            "summary": self.summary,
            "cost": self.cost,
            "idempotent": self.idempotent,
            "revision_check": self.revision_check,
            "input_schema": self.input_model.model_json_schema(),
            "output_schema": self.output_model.model_json_schema(mode="serialization"),
            "examples": list(self.examples),
            "max_request_bytes": self.max_request_bytes,
            "proposable": self.proposable,
        }


class Registry:
    def __init__(self) -> None:
        self._ops: dict[str, Operation] = {}

    def register(self, op: Operation) -> None:
        if op.name in self._ops:
            raise ValueError(f"duplicate operation {op.name}")
        if (op.kind == "query") != (op.effect == "none"):
            raise ValueError(f"{op.name}: queries, and only queries, have effect 'none'")
        if op.proposable and (
            op.kind != "command" or op.capability not in (Capability.SCIENCE_MUTATION, Capability.COMPUTE_JOB)
        ):
            raise ValueError(f"{op.name}: only science-mutating and compute commands are proposable")
        self._ops[op.name] = op

    def get(self, name: str) -> Operation | None:
        return self._ops.get(name)

    @property
    def names(self) -> list[str]:
        return sorted(self._ops)

    def snapshot(self) -> dict[str, Any]:
        """The full contract, committed as a snapshot and compared in CI (D13, D20)."""
        return {
            "contract_version": CONTRACT_VERSION,
            "envelopes": {
                "request": RequestEnvelope.model_json_schema(),
                "success": SuccessEnvelope.model_json_schema(mode="serialization"),
                "error": ErrorEnvelope.model_json_schema(mode="serialization"),
                "event": FeedItem.model_json_schema(mode="serialization"),
            },
            "operations": [self._ops[name].describe() for name in self.names],
        }


class _Options(Wire):
    request_id: RequestId | None
    dry_run: bool


def _options(request_id: Any, dry_run: Any) -> _Options:
    """The request options, validated like arguments (a Python caller gets the HTTP rules)."""
    try:
        options = _Options.model_validate({"request_id": request_id, "dry_run": dry_run}, strict=True)
    except ValidationError as exc:
        first = exc.errors()[0]
        raise OperationError(
            ErrorCode.INVALID_ARGUMENT,
            first["msg"],
            offending_field=_field_path(first["loc"]) or None,
            hint="request_id is 1–128 characters of A–Z a–z 0–9 . _ : -; dry_run is a boolean",
        ) from None
    if options.dry_run and options.request_id is not None:
        raise OperationError(
            ErrorCode.INVALID_ARGUMENT,
            "a dry run is never recorded, so it takes no request_id",
            offending_field="request_id",
        )
    return options


def _field_path(loc: tuple[int | str, ...]) -> str:
    out = ""
    for part in loc:
        out += f"[{part}]" if isinstance(part, int) else (f".{part}" if out else str(part))
    return out


def canonical_numbers(value: Any) -> Any:
    """Integral finite numbers within ±(2⁵³ − 1) become integers before strict validation.

    JSON has one number type, and JSON Schema's "integer" accepts 0.0, so an integer field accepts
    0.0 exactly as the published schema says, while 0.5, true and "0" stay refused. Float fields
    accept integers anyway (validation round 10, finding 6).
    """
    if isinstance(value, float) and value.is_integer() and abs(value) <= MAX_SAFE_INTEGER:
        return int(value)
    if isinstance(value, dict):
        return {key: canonical_numbers(child) for key, child in value.items()}
    if isinstance(value, list | tuple):  # Python tuples are JSON arrays
        return [canonical_numbers(child) for child in value]
    return value


def _wire_json(args: Mapping[str, Any] | None) -> str:
    """The arguments as JSON text. Every adapter's input passes through here, so a Python caller
    gets exactly the HTTP rules: values JSON can represent (tuples become arrays), finite numbers,
    valid Unicode and bounded nesting; anything else is refused."""
    problem = wire_problem(args)
    if problem:
        raise OperationError(ErrorCode.INVALID_ARGUMENT, f"arguments are not valid JSON: {problem}")
    try:
        return json.dumps(canonical_numbers(dict(args or {})), allow_nan=False)
    except (TypeError, ValueError, RecursionError):
        raise OperationError(
            ErrorCode.INVALID_ARGUMENT,
            "arguments must be plain JSON values with finite numbers",
            hint="NaN and ±Infinity are not JSON; send numbers, strings, booleans, null, arrays and objects",
        ) from None


def parse_input(op: Operation, args: Mapping[str, Any] | None, *, prefix: str = "") -> BaseModel:
    """Validate ``args`` for ``op`` exactly as every adapter does: JSON values only, strict mode."""
    raw = _wire_json(args)
    try:
        # Strict JSON mode: no coercion. "37" is not a number and false is not 0 (spike 2).
        return op.input_model.model_validate_json(raw, strict=True)
    except ValidationError as exc:
        first = exc.errors()[0]
        path = _field_path(first["loc"])
        raise OperationError(
            ErrorCode.INVALID_ARGUMENT,
            first["msg"],
            offending_field=(f"{prefix}.{path}" if prefix and path else prefix or path) or None,
            hint=f"see the input schema of {op.name}",
            details={"error_count": exc.error_count()},
        ) from None


def capture_plan(ctx: Context, op: Operation, parsed: BaseModel) -> Plan[Any]:
    """Run a command's handler up to its commit and return the plan it would commit, without
    committing. A proposal validates and later applies its steps through these plans."""
    probe = Context(ctx.session, ctx.principal, ctx.registry, capture=True)
    try:
        op.handler(probe, parsed)
    except _Captured as captured:
        return captured.plan
    raise TypeError(f"{op.name} did not commit")


def _replayed_envelope(op: Operation, outcome: StoredOutcome) -> dict[str, Any]:
    try:
        result = op.output_model.model_validate(outcome.result)
    except ValidationError:
        raise OperationError(
            ErrorCode.IDEMPOTENCY_KEY_REUSED,
            "this request was acknowledged under an earlier contract; its outcome cannot be returned",
            offending_field="request_id",
            hint="read the current state; use a new request_id for a new command",
        ) from None
    return {
        "ok": True,
        "operation": op.name,
        "result": result.model_dump(mode="json"),
        "revisions": dict(outcome.revisions),
        "replayed": True,
        "dry_run": None,
    }


def dispatch(
    registry: Registry,
    session: Session,
    principal: Principal,
    name: str,
    args: Mapping[str, Any] | None,
    *,
    request_id: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Run one operation and return the JSON envelope every adapter returns unchanged."""
    try:
        options = _options(request_id, dry_run)
        op = registry.get(name)
        if op is None:
            raise OperationError(
                ErrorCode.UNKNOWN_OPERATION,
                f"no operation named {name!r}",
                hint="list operations with the registry endpoint",
                details={"known": registry.names},
            )
        decision = decide(principal, op.capability)
        if decision is Decision.DENY:
            raise OperationError(
                ErrorCode.CAPABILITY_DENIED,
                f"tier {principal.tier.value!r} may not use {op.capability.value!r} operations",
                hint="use a credential with a higher tier",
            )
        if options.dry_run and op.kind == "query":
            raise OperationError(
                ErrorCode.INVALID_ARGUMENT,
                f"{op.name} is a query: it changes nothing, so there is nothing to dry-run",
                offending_field="dry_run",
                hint="call it without dry_run",
            )
        if decision is Decision.PROPOSE and not options.dry_run:  # a dry run changes nothing
            raise OperationError(
                ErrorCode.PROPOSAL_REQUIRED,
                f"{op.name} from tier {principal.tier.value!r} must be submitted as a proposal",
                hint=(
                    'submit it as a step of proposal.create ({"steps": [{"operation": ..., "args": ...}]}); '
                    "a human accepts it"
                    if op.proposable
                    else "use a credential with a higher tier"
                ),
            )
        parsed = parse_input(op, args)
        ctx = Context(session, principal, registry, request_id=options.request_id, dry_run=options.dry_run)
        try:
            result = op.handler(ctx, parsed)
        except Replayed as replayed:
            return _replayed_envelope(op, replayed.outcome)
        if not isinstance(result, op.output_model):
            raise TypeError(f"{op.name} returned {type(result).__name__}, expected {op.output_model.__name__}")
        if ctx.observed is None:
            raise TypeError(f"{op.name} must read or commit through its Context")
        report = None
        state = ctx.observed
        if options.dry_run:
            assert ctx.before is not None
            report = dry_run_report(ctx.before, ctx.observed).model_dump(mode="json")
            state = ctx.before
        return {
            "ok": True,
            "operation": op.name,
            "result": result.model_dump(mode="json"),
            "revisions": {"science": state.science_revision, "workspace": state.workspace_revision},
            "replayed": False,
            "dry_run": report,
        }
    except OperationError as err:
        return {"ok": False, "operation": name, "error": err.to_json()}
