"""Unified response envelope and error contract for the plate HTTP API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ErrorPayload(BaseModel):
    """Error body carried by :class:`EnvelopeErr`."""

    code: str
    message: str
    details: dict[str, Any] | None = None


class EnvelopeOk(BaseModel):
    """Success envelope."""

    ok: Literal[True] = True
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
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.http_status = http_status
        self.code = code
        self.message = message
        self.details = details

    def to_payload(self) -> ErrorPayload:
        return ErrorPayload(code=self.code, message=self.message, details=self.details)


def ok_response(data: Any) -> dict[str, Any]:
    """Return a JSON-serializable success envelope."""
    return EnvelopeOk(data=data).model_dump(mode="json", exclude_none=False)


def err_response(
    code: str,
    message: str,
    http_status: int = 400,
    details: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], int]:
    """Return a JSON-serializable failure envelope plus its HTTP status code."""
    err = EnvelopeErr(
        error=ErrorPayload(code=code, message=message, details=details)
    ).model_dump(mode="json", exclude_none=True)
    return err, http_status


__all__ = [
    "EnvelopeOk",
    "EnvelopeErr",
    "ErrorPayload",
    "PlateHTTPError",
    "ok_response",
    "err_response",
    # re-export the common base class for convenience
    "BaseModel",
    "Field",
]
