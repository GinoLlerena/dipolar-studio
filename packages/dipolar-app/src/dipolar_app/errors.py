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
    JOURNAL_FAILED = "JOURNAL_FAILED"
    INTERNAL = "INTERNAL"


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
    ErrorCode.JOURNAL_FAILED: 503,
    ErrorCode.INTERNAL: 500,
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
