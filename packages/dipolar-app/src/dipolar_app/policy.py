"""Trusted policy (04 D17, §8.3). Identity and tier come from the credential, never from arguments."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Tier(StrEnum):
    READ = "read"
    PROPOSE = "propose"
    APPLY = "apply"
    ADMIN = "admin"


class Capability(StrEnum):
    QUERY = "query"  # read-only queries, render.*, describe_view
    PREVIEW = "preview"  # fit.preview: non-mutating and bounded
    VIEW_WRITE = "view_write"
    SCIENCE_MUTATION = "science_mutation"
    COMPUTE_JOB = "compute_job"
    IO = "io"
    JOB_CANCEL = "job_cancel"
    PROPOSE = "propose"  # submit a change set for a human to approve (M2 step 2)
    APPROVE = "approve"  # accept or reject a proposal: human principals only


class Decision(StrEnum):
    ALLOW = "allow"
    PROPOSE = "propose"  # must become a proposal approved by a human (M2)
    DENY = "deny"


@dataclass(frozen=True, slots=True)
class Principal:
    """An authenticated caller. ``actor`` is e.g. ``user``, ``script:robot`` or ``agent:<name>``."""

    actor: str
    tier: Tier
    human: bool


A, P, D = Decision.ALLOW, Decision.PROPOSE, Decision.DENY

#: The §8.3 capability matrix. Preview budgets and job ownership are enforced by the operations.
MATRIX: dict[Capability, dict[Tier, Decision]] = {
    Capability.QUERY: {Tier.READ: A, Tier.PROPOSE: A, Tier.APPLY: A, Tier.ADMIN: A},
    Capability.PREVIEW: {Tier.READ: A, Tier.PROPOSE: A, Tier.APPLY: A, Tier.ADMIN: A},
    Capability.VIEW_WRITE: {Tier.READ: D, Tier.PROPOSE: A, Tier.APPLY: A, Tier.ADMIN: A},
    Capability.SCIENCE_MUTATION: {Tier.READ: D, Tier.PROPOSE: P, Tier.APPLY: A, Tier.ADMIN: A},
    Capability.COMPUTE_JOB: {Tier.READ: D, Tier.PROPOSE: P, Tier.APPLY: A, Tier.ADMIN: A},
    Capability.IO: {Tier.READ: D, Tier.PROPOSE: P, Tier.APPLY: A, Tier.ADMIN: A},
    Capability.JOB_CANCEL: {Tier.READ: D, Tier.PROPOSE: A, Tier.APPLY: A, Tier.ADMIN: A},
    Capability.PROPOSE: {Tier.READ: D, Tier.PROPOSE: A, Tier.APPLY: A, Tier.ADMIN: A},
    Capability.APPROVE: {Tier.READ: D, Tier.PROPOSE: D, Tier.APPLY: A, Tier.ADMIN: A},
}


def decide(principal: Principal, capability: Capability) -> Decision:
    """The §8.3 decision. Approval also needs a **human** principal (§8.3 "Approval"): a script or
    an agent never approves, whatever its tier."""
    if capability is Capability.APPROVE and not principal.human:
        return Decision.DENY
    return MATRIX[capability][principal.tier]
