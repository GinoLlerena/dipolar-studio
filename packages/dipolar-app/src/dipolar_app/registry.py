"""Operation registry (04 D13, D20, §8.5) and the single typed dispatcher.

Every capability is declared once as an ``Operation``. Adapters (Python, HTTP, later MCP) are thin
wrappers around ``dispatch``, which alone applies policy, validation and error mapping.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Literal, TypeVar

from pydantic import BaseModel, ValidationError

from dipolar_app.errors import ErrorCode, OperationError
from dipolar_app.policy import Capability, Decision, Principal, decide
from dipolar_app.session import Plan, Session, SessionState

T = TypeVar("T")

#: Semantic version of the tool contract (D20), independent of the package version.
CONTRACT_VERSION = "0.1.0"

Kind = Literal["query", "command"]
Effect = Literal["none", "model", "view", "compute", "io", "destructive"]
Cost = Literal["instant", "seconds", "job"]


@dataclass(slots=True)
class Context:
    """Per-call context. It records the one state snapshot the operation observed or produced, so
    the envelope's revisions always describe the same state as the result (never a later one)."""

    session: Session
    principal: Principal
    observed: SessionState | None = None

    def read(self) -> SessionState:
        """Take the operation's state snapshot (queries compute from it outside the lock)."""
        self.observed = self.session.state
        return self.observed

    def commit(self, operation: str, args: dict[str, Any], plan: Plan[T]) -> T:
        result, state = self.session.commit(self.principal, operation, args, plan)
        self.observed = state
        return result


Handler = Callable[[Context, Any], BaseModel]


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
        }


class Registry:
    def __init__(self) -> None:
        self._ops: dict[str, Operation] = {}

    def register(self, op: Operation) -> None:
        if op.name in self._ops:
            raise ValueError(f"duplicate operation {op.name}")
        if (op.kind == "query") != (op.effect == "none"):
            raise ValueError(f"{op.name}: queries, and only queries, have effect 'none'")
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
            "operations": [self._ops[name].describe() for name in self.names],
        }


def _field_path(loc: tuple[int | str, ...]) -> str:
    out = ""
    for part in loc:
        out += f"[{part}]" if isinstance(part, int) else (f".{part}" if out else str(part))
    return out


def dispatch(
    registry: Registry,
    session: Session,
    principal: Principal,
    name: str,
    args: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Run one operation and return the JSON envelope every adapter returns unchanged."""
    try:
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
        if decision is Decision.PROPOSE:
            raise OperationError(
                ErrorCode.PROPOSAL_REQUIRED,
                f"{op.name} from tier {principal.tier.value!r} must be submitted as a proposal",
                hint="proposals arrive in M2; use an apply-tier credential for now",
            )
        try:
            parsed = op.input_model.model_validate(dict(args or {}))
        except ValidationError as exc:
            first = exc.errors()[0]
            raise OperationError(
                ErrorCode.INVALID_ARGUMENT,
                first["msg"],
                offending_field=_field_path(first["loc"]) or None,
                hint=f"see the input schema of {op.name}",
                details={"error_count": exc.error_count()},
            ) from None
        ctx = Context(session, principal)
        result = op.handler(ctx, parsed)
        if not isinstance(result, op.output_model):
            raise TypeError(f"{op.name} returned {type(result).__name__}, expected {op.output_model.__name__}")
        if ctx.observed is None:
            raise TypeError(f"{op.name} must read or commit through its Context")
        state = ctx.observed
        return {
            "ok": True,
            "operation": op.name,
            "result": result.model_dump(mode="json"),
            "revisions": {"science": state.science_revision, "workspace": state.workspace_revision},
        }
    except OperationError as err:
        return {"ok": False, "operation": name, "error": err.to_json()}
