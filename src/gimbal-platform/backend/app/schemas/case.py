"""Case-related Pydantic schemas (request/response DTOs)."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


class CaseSummaryOut(BaseModel):
    """Public-facing case summary view.

    Serializes a :class:`app.services.case_loader.CaseSummary` dataclass to a JSON
    shape suitable for the API surface.  ``updated_at`` is rendered as an ISO 8601
    string, ``file_path`` as a plain ``str``.
    """

    model_config = ConfigDict(from_attributes=True)

    case_id: str
    name: str
    module: str
    description: str
    visibility: str
    owner_id: int | None
    audited: bool
    file_path: str
    updated_at: str
    tags: list[str]
    # Optional display fields (task-12): read from meta in the loader.
    priority: int | None = None  # 1 | 2 | 3
    author: str | None = None  # meta.author || meta.owner
    # Spec-1 stub flags — populated by the public/mine endpoints.
    favorited_by_me: bool = False
    copied_by_me: bool = False

    @field_validator("updated_at", mode="before")
    @classmethod
    def _coerce_updated_at(cls, v: Any) -> Any:
        if isinstance(v, datetime):
            return v.isoformat()
        if isinstance(v, (int, float)):
            # case_loader emits POSIX seconds (float) on disk mtime.
            return datetime.fromtimestamp(float(v)).isoformat()
        return v

    @field_validator("file_path", mode="before")
    @classmethod
    def _coerce_file_path(cls, v: Any) -> Any:
        if isinstance(v, Path):
            return str(v)
        return v


class CaseListOut(BaseModel):
    """Paginated response shape used by /cases/mine and /cases/public."""

    items: list[CaseSummaryOut]
    total: int


class CaseDetailOut(BaseModel):
    """Response shape for GET /cases/{case_id}.

    ``payload`` is the parsed YAML/JSON contents of the case file (returned
    verbatim).  ``summary`` mirrors what /cases/mine|public would return for the
    same item.
    """

    payload: dict[str, Any]
    summary: CaseSummaryOut
