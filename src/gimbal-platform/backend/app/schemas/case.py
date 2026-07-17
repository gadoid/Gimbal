"""Case-related Pydantic schemas (request/response DTOs)."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


# ── Step description (gimbal run show) ───────────────────────────
# Mirrors the JSON shape produced by ``gimbal run show --from-path
# <yaml> --format=json`` (see src/gimbal/cli/commands/run_show.py).  The
# frontend ExecutionDrawer calls this endpoint to render the step picker
# popover; it does NOT receive the raw payload, so we keep the shape
# narrow on purpose (no bodies, no headers, no strategy bodies — just
# enough to display a one-line description per step).


class CaseShowStepOut(BaseModel):
    """One row in the gimbal run show steps array."""

    index: int
    kind: str
    description: str
    # ``api`` is optional: setup/teardown/ref steps don't have one.
    api: dict[str, str] | None = None
    strategy_kinds: list[str] = Field(default_factory=list)
    strategy_count: int = 0
    # ``ref`` is the asset-ref string for StepRef nodes; null otherwise.
    ref: str | None = None


class CaseShowOut(BaseModel):
    """Response shape for GET /cases/{case_id}/show.

    Top-level metadata plus the step list.  ``usage_hint`` is gimbal's
    runtime hint (e.g. "未注册到资产仓库"); we pass it through so the
    frontend can show it as a hint chip without a second roundtrip.
    """

    scenario_id: str
    name: str | None = None
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    module: str | None = None
    priority: int | None = None
    author: str | None = None
    step_count: int
    steps: list[CaseShowStepOut] = Field(default_factory=list)
    usage_hint: dict[str, str] | None = None
