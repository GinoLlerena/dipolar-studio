"""Structured operation errors (04 D13): every error has a code, a message, a field and a hint."""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    UNKNOWN_OPERATION = "UNKNOWN_OPERATION"
    UNAUTHENTICATED = "UNAUTHENTICATED"
    CAPABILITY_DENIED = "CAPABILITY_DENIED"
    PROPOSAL_REQUIRED = "PROPOSAL_REQUIRED"
    REVISION_CONFLICT = "REVISION_CONFLICT"
    NO_PROJECT = "NO_PROJECT"
    ID_NOT_FOUND = "ID_NOT_FOUND"
    OUT_OF_DOMAIN = "OUT_OF_DOMAIN"
    PROJECT_NOT_READY = "PROJECT_NOT_READY"
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
    IDEMPOTENCY_KEY_REUSED = "IDEMPOTENCY_KEY_REUSED"
    PROPOSAL_STALE = "PROPOSAL_STALE"
    PROPOSAL_CLOSED = "PROPOSAL_CLOSED"
    NOTHING_TO_UNDO = "NOTHING_TO_UNDO"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    JOURNAL_FAILED = "JOURNAL_FAILED"
    INTERNAL = "INTERNAL"
    # Contract 0.11.0 (Phase 2 V1.3): fixed-geometry fits.
    OBSERVATIONS_CONFLICT = "OBSERVATIONS_CONFLICT"
    SYMMETRY_NOT_SATISFIED = "SYMMETRY_NOT_SATISFIED"
    POINT_GROUP_NOT_SUPPORTED = "POINT_GROUP_NOT_SUPPORTED"
    MEDIUM_NOT_SUPPORTED = "MEDIUM_NOT_SUPPORTED"
    ISOTOPE_NOT_SUPPORTED = "ISOTOPE_NOT_SUPPORTED"
    NO_TORSION = "NO_TORSION"
    FIT_TOO_LARGE = "FIT_TOO_LARGE"


#: HTTP status for each code (the HTTP adapter's only error-mapping table).
HTTP_STATUS: dict[ErrorCode, int] = {
    ErrorCode.INVALID_ARGUMENT: 400,
    ErrorCode.UNKNOWN_OPERATION: 404,
    ErrorCode.UNAUTHENTICATED: 401,
    ErrorCode.CAPABILITY_DENIED: 403,
    ErrorCode.PROPOSAL_REQUIRED: 403,
    ErrorCode.REVISION_CONFLICT: 409,
    ErrorCode.NO_PROJECT: 409,
    ErrorCode.ID_NOT_FOUND: 404,
    ErrorCode.OUT_OF_DOMAIN: 400,
    ErrorCode.PROJECT_NOT_READY: 409,
    ErrorCode.PAYLOAD_TOO_LARGE: 413,
    ErrorCode.IDEMPOTENCY_KEY_REUSED: 409,
    ErrorCode.PROPOSAL_STALE: 409,
    ErrorCode.PROPOSAL_CLOSED: 409,
    ErrorCode.NOTHING_TO_UNDO: 409,
    ErrorCode.QUOTA_EXCEEDED: 429,
    ErrorCode.JOURNAL_FAILED: 503,
    ErrorCode.INTERNAL: 500,
    ErrorCode.OBSERVATIONS_CONFLICT: 409,
    ErrorCode.SYMMETRY_NOT_SATISFIED: 400,
    ErrorCode.POINT_GROUP_NOT_SUPPORTED: 400,
    ErrorCode.MEDIUM_NOT_SUPPORTED: 400,
    ErrorCode.ISOTOPE_NOT_SUPPORTED: 400,
    ErrorCode.NO_TORSION: 409,
    ErrorCode.FIT_TOO_LARGE: 413,
}


class OperationError(Exception):
    """An error an operation reports to its caller (user, script or, later, an agent)."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        offending_field: str | None = None,
        hint: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.offending_field = offending_field
        self.hint = hint
        self.details = details or {}

    def to_json(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "message": self.message,
            "offending_field": self.offending_field,
            "hint": self.hint,
            "details": self.details,
        }
