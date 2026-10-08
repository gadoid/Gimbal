"""Unified response envelope and error contract for the plate HTTP API.

Per ADR 0002 (M6 grammar):
- Success envelope: ``{"ok": true, "dim": "<dim>", "data": {"items"|"item", "total", ...}}``
- Failure envelope: ``{"ok": false, "error": {"code": "<ErrorCode>", "message": ..., "details": ...}}``
- Error codes live in :class:`ErrorCode` (StrEnum).
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class ErrorCode(str, Enum):
    """All error codes used by the plate HTTP surface (ADR 0002 §D4)."""

    DIM_NOT_FOUND = "dim_not_found"
    DIM_ITEM_NOT_FOUND = "dim_item_not_found"
    SYSTEM_NOT_FOUND = "system_not_found"
    INVALID_ACTION = "invalid_action"
    REGISTRY_UNAVAILABLE = "registry_unavailable"
    INTERNAL_ERROR = "internal_error"
    ADMIN_NOT_IMPLEMENTED = "admin_not_implemented"
    REDACTED_SENSITIVE = "redacted_sensitive"
    INVALID_QUERY_PARAM = "invalid_query_param"


class ErrorPayload(BaseModel):
    """Error body carried by :class:`EnvelopeErr`."""

    code: str
    message: str
    details: dict[str, Any] | None = None


class EnvelopeOk(BaseModel):
    """Success envelope.

    ADR 0002 §D-D1: ``dim`` is a top-level contract field (option A).
    Generic handlers always pass ``dim``; non-dim handlers (e.g. ``/healthz``,
    ``/api/``) leave it as ``None``.
    """

    ok: Literal[True] = True
    dim: str | None = None
    data: Any = None


class EnvelopeErr(BaseModel):
    """Failure envelope."""

    ok: Literal[False] = False
    error: ErrorPayload


class PlateHTTPError(Exception):
    """Business exception that maps to a structured HTTP error envelope."""

    def __init__(
        self,
        *,
        http_status: int,
        code: str | ErrorCode,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.http_status = http_status
        # Normalise ErrorCode to its string value so JSON serialisation is stable.
        self.code = code.value if isinstance(code, ErrorCode) else code
        self.message = message
        self.details = details

    def to_payload(self) -> ErrorPayload:
        return ErrorPayload(code=self.code, message=self.message, details=self.details)


def ok_response(
    data: Any,
    *,
    dim: str | None = None,
) -> dict[str, Any]:
    """Return a JSON-serializable success envelope.

    Parameters
    ----------
    data:
        The dim-specific payload (must conform to the central shape:
        ``{"dim": ..., "items"|"item", "total", ...}``).
    dim:
        Dimension name reflected on the envelope top level (ADR 0002 §D-D1).
        ``None`` for non-dim handlers (health, root listing).
    """
    return EnvelopeOk(dim=dim, data=data).model_dump(mode="json", exclude_none=False)


def err_response(
    code: str | ErrorCode,
    message: str,
    *,
    http_status: int = 400,
    details: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], int]:
    """Return a JSON-serializable failure envelope plus its HTTP status code."""
    if isinstance(code, ErrorCode):
        code = code.value
    err = EnvelopeErr(
        error=ErrorPayload(code=code, message=message, details=details)
    ).model_dump(mode="json", exclude_none=True)
    return err, http_status


__all__ = [
    "ErrorCode",
    "EnvelopeOk",
    "EnvelopeErr",
    "ErrorPayload",
    "PlateHTTPError",
    "ok_response",
    "err_response",
    "BaseModel",
    "Field",
]