"""Schemas for executions + runs (Spec-2 §4.5 E)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# ── inputs ─────────────────────────────────────────────────────
MergePolicy = Literal["override", "merge", "append"]


class ExecutionCreateIn(BaseModel):
    case_id: str
    n_runs: int = Field(default=1, ge=1, le=1000)
    parallel: int = Field(default=1, ge=1, le=200)
    env: str = Field(default="dev")
    prefix: str | None = Field(default=None, max_length=64)
    # Aliases from /api/auths to inject as Config.users
    exec_auth_alias: list[str] = Field(default_factory=list)
    merge_policy: MergePolicy = Field(default="override")
    # ``inject_credentials=False`` → skip credential injection entirely;
    # ``Config.users`` in the rendered yaml stays exactly as the case yaml
    # defines it (a.k.a. "origin" in the UI).  Default is True so legacy
    # API consumers that only send ``merge_policy`` keep working — the new
    # "no-injection" mode is an opt-in via this flag.
    inject_credentials: bool = Field(default=True)
    # ``command_line``, when provided, replaces the entire subprocess
    # argv the executor would otherwise build.  Each list element is one
    # argv entry.  Restricted to admin users at the router layer (any
    # non-admin request with this field set gets 403).  When None the
    # executor falls back to its default
    # ``gimbal run launch <yaml> --env <env> --report-dir <dir>``.
    command_line: list[str] | None = Field(default=None, max_length=64)
    # 0-based inclusive halt index forwarded to
    # ``gimbal run launch --step-to <N>``.  ``None`` (default) means
    # "run all steps" — preserves legacy payloads.  Lower bound ``ge=0``
    # is enforced here; upper bound (``< step_count`` of the referenced
    # case) is enforced at the router layer so the error message can
    # include the actual step_count.
    step_to: int | None = Field(default=None, ge=0)


# ── outputs ────────────────────────────────────────────────────
class ExecRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    idx: int
    status: str
    exit_code: int | None
    report_path: str | None
    log_path: str | None
    command_line: str | None
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None


class ExecutionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    case_id: str
    status: str
    total_runs: int
    passed: int
    failed: int
    started_at: datetime | None
    finished_at: datetime | None
    config: dict


class ExecutionDetailOut(ExecutionOut):
    runs: list[ExecRunOut]


class ExecutionListOut(BaseModel):
    items: list[ExecutionOut]
    total: int