"""Pydantic schemas for the V3 Scenario Composer API.

Mirrors the frontend TypeScript shapes in
``frontend/src/types/scenario-composer.ts`` (camelCase wire format) and
the document ``docs/PLATFORM-SCENARIO-COMPOSER-API.md`` §2.

Key conventions:
* All request/response fields use camelCase on the wire (frontend reads
  ``meta.scenarioId`` etc.).  Pydantic ``Field(alias=...)`` +
  ``populate_by_name=True`` lets Python code use snake_case identifiers
  while still emitting/receiving camelCase JSON.
* The DB layer uses snake_case; the routers transform to/from the
  camelCase DTOs defined here.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ─── helpers ────────────────────────────────────────────────────────
# `populate_by_name` + alias lets us write `ScenarioMeta(scenario_id="...")`
# in Python while still emitting `"scenarioId": "..."` in JSON.  Both
# `by_alias=True` (the default in `.model_dump(by_alias=True)`) and
# plain attribute access work.
_CAMEL = ConfigDict(populate_by_name=True, str_strip_whitespace=True)


# ─── enums / small refs ─────────────────────────────────────────────
AuthType = Literal["bearer", "cookie", "oauth2", "apikey"]
StepKind = Literal["http", "rpc", "sql", "script", "wait", "extract"]
HttpMethod = Literal["GET", "POST", "PUT", "DELETE", "PATCH"]
RunStatus = Literal["PASS", "FAIL", "SKIP"]
Priority = Literal[0, 1, 2, 3]


class AuthSessionRef(BaseModel):
    """A reference to a pre-defined AuthSession; matches frontend type."""

    model_config = _CAMEL

    name: str = Field(min_length=1, max_length=128)
    type: AuthType
    ref: str | None = None


class RetryRef(BaseModel):
    model_config = _CAMEL

    max_attempts: int = Field(default=0, ge=0, alias="maxAttempts")
    interval_ms: int = Field(default=500, ge=0, alias="intervalMs")


# ─── scenario meta + steps ─────────────────────────────────────────
class ScenarioMeta(BaseModel):
    """Scenario metadata; one Scenario has exactly one Meta."""

    model_config = _CAMEL

    scenario_id: str = Field(
        alias="scenarioId",
        pattern=r"^sc-[a-z0-9-]+$",
        min_length=3,
        max_length=128,
    )
    name: str = Field(min_length=1, max_length=64)
    description: str = Field(default="", max_length=2048)
    module: str = Field(min_length=1, max_length=64)
    priority: int = Field(ge=0, le=3)
    author: str = Field(default="", max_length=128)
    owner: str = Field(default="", max_length=128)
    tags: list[str] = Field(default_factory=list, max_length=32)
    system: list[str] = Field(default_factory=list, min_length=1)
    version: str = Field(default="v0.1.0", max_length=32)
    expire: bool = False
    create_time: datetime | None = Field(default=None, alias="createTime")

    @field_validator("tags")
    @classmethod
    def _clean_tags(cls, v: list[str]) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for t in v:
            t = (t or "").strip()
            if not t:
                continue
            if len(t) > 20:
                t = t[:20]
            if t in seen:
                continue
            seen.add(t)
            out.append(t)
        return out

    @field_validator("system")
    @classmethod
    def _validate_system(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("system must contain at least one tag")
        cleaned: list[str] = []
        for s in v:
            s = (s or "").strip()
            if not s:
                raise ValueError("system tag must be non-empty")
            cleaned.append(s)
        # Allow well-known tags + any custom string
        allowed = {"fin", "logi", "wms", "mall", "common"}
        for s in cleaned:
            if s != "common" and s in {"fin", "logi", "wms", "mall"}:
                continue
            if s == "common":
                continue
            # accept any other (custom) system tag
        return cleaned


# ─── draft (request body) ──────────────────────────────────────────
class CaseOverride(BaseModel):
    """Subset of Case used to carry case-level overrides on a draft."""

    model_config = _CAMEL

    env: str = ""
    auth: AuthSessionRef
    data_set_ids: list[str] = Field(default_factory=list, alias="dataSetIds")


class StepOrchestration(BaseModel):
    """Platform-side fields for one step, index-aligned with definition.steps[i]."""
    model_config = _CAMEL

    enabled: bool = True
    name: str = ""


class Orchestration(BaseModel):
    """Platform rendering/orchestration container.

    steps is index-aligned with definition.steps (same order, same length).
    resourceMeta is name-aligned with definition.resource keys.
    """
    model_config = _CAMEL

    steps: list[StepOrchestration] = Field(default_factory=list)
    resourceMeta: dict[str, str] = Field(default_factory=dict)


class ScenarioDraft(BaseModel):
    """Platform draft container.

    definition: the plate Scenario structure as a free-form dict. Backend does
                not model plate's internal types — plate /convert is the single
                validation authority ("plate outputs a neutral dict; consumers
                model it themselves").
    orchestration: platform-only rendering/orchestration fields, never sent
                   to plate (plate doesn't know about them).
    caseMeta: case-level runtime overrides (env/auth/dataset).
    """
    model_config = _CAMEL

    definition: dict[str, Any]
    orchestration: Orchestration = Field(default_factory=Orchestration)
    case_meta: CaseOverride | None = Field(default=None, alias="caseMeta")


# ─── case ──────────────────────────────────────────────────────────
class Case(BaseModel):
    model_config = _CAMEL

    case_id: str = Field(
        alias="caseId", min_length=1, max_length=128
    )
    scenario_id: str = Field(alias="scenarioId", min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=2048)
    env: str = Field(default="", max_length=64)
    auth: AuthSessionRef
    retry: RetryRef | None = None
    data_set_ids: list[str] = Field(default_factory=list, alias="dataSetIds")
    last_run_status: RunStatus | None = Field(default=None, alias="lastRunStatus")
    last_run_at: datetime | None = Field(default=None, alias="lastRunAt")
    created_by: str = Field(default="", alias="createdBy", max_length=128)
    updated_at: datetime | None = Field(default=None, alias="updatedAt")
    starred: bool = False


class CasePatch(BaseModel):
    """Subset of Case allowed in PATCH /cases/{id}.

    Immutable fields (caseId / scenarioId / createdBy / updatedAt /
    lastRunStatus / lastRunAt) are NOT included; supplying them is a
    400.  All other Case fields are optional.
    """

    model_config = _CAMEL

    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=2048)
    env: str | None = Field(default=None, max_length=64)
    auth: AuthSessionRef | None = None
    retry: RetryRef | None = None
    data_set_ids: list[str] | None = Field(default=None, alias="dataSetIds")

    @model_validator(mode="before")
    @classmethod
    def _reject_immutable(cls, data: Any) -> Any:
        if isinstance(data, dict):
            forbidden = {
                "caseId",
                "scenarioId",
                "createdBy",
                "updatedAt",
                "lastRunStatus",
                "lastRunAt",
                "starred",
            }
            bad = forbidden & set(data.keys())
            if bad:
                raise ValueError(
                    f"case patch does not allow fields: {sorted(bad)}"
                )
        return data


# ─── data-set ──────────────────────────────────────────────────────
class DataSetRow(BaseModel):
    """One row of a DataSet; keys are field names, values are scalars.

    Stored as a plain dict on the wire (extra keys per row allowed).
    """

    model_config = ConfigDict(extra="allow")


class DataSet(BaseModel):
    model_config = _CAMEL

    dataset_id: str = Field(
        alias="datasetId", pattern=r"^ds-[a-z0-9-]+$", min_length=3, max_length=128
    )
    case_id: str = Field(alias="caseId", min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=2048)
    row_count: int = Field(default=0, ge=0, alias="rowCount")
    rows: list[dict[str, Any]] = Field(default_factory=list)
    last_run_status: RunStatus | None = Field(default=None, alias="lastRunStatus")
    last_run_at: datetime | None = Field(default=None, alias="lastRunAt")

    @model_validator(mode="after")
    def _check_rows_consistent(self) -> "DataSet":
        if not self.rows:
            return self
        keys = set(self.rows[0].keys())
        for i, row in enumerate(self.rows[1:], start=1):
            if set(row.keys()) != keys:
                raise ValueError(
                    f"inconsistent_row_columns: row {i} has keys "
                    f"{sorted(set(row.keys()))} but row 0 has {sorted(keys)}"
                )
        return self


class DataSetSummary(BaseModel):
    """Lightweight view used in list endpoints (preview[0:3])."""

    model_config = _CAMEL

    dataset_id: str = Field(alias="datasetId", min_length=1)
    case_id: str = Field(alias="caseId", min_length=1)
    case_name: str = Field(default="", alias="caseName", max_length=128)
    name: str = Field(min_length=1, max_length=128)
    row_count: int = Field(default=0, ge=0, alias="rowCount")
    last_run_status: RunStatus | None = Field(default=None, alias="lastRunStatus")
    last_run_at: datetime | None = Field(default=None, alias="lastRunAt")
    preview: list[dict[str, Any]] = Field(default_factory=list, max_length=3)


class DataSetDraft(BaseModel):
    """Request body for POST /cases/{caseId}/data-sets and PUT /data-sets/{id}."""

    model_config = _CAMEL

    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=2048)
    rows: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_rows_consistent(self) -> "DataSetDraft":
        if not self.rows:
            return self
        keys = set(self.rows[0].keys())
        for i, row in enumerate(self.rows[1:], start=1):
            if set(row.keys()) != keys:
                raise ValueError(
                    f"inconsistent_row_columns: row {i} has keys "
                    f"{sorted(set(row.keys()))} but row 0 has {sorted(keys)}"
                )
        return self


# ─── envs / runs ───────────────────────────────────────────────────
class RunEnv(BaseModel):
    model_config = _CAMEL

    env_id: str = Field(alias="envId", min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=64)
    base_url: str = Field(alias="baseUrl", min_length=1, max_length=512)


class RunRequest(BaseModel):
    model_config = _CAMEL

    case_id: str = Field(alias="caseId", min_length=1, max_length=128)
    data_set_ids: list[str] = Field(alias="dataSetIds", min_length=1)
    env: RunEnv
    auth: str | None = None
    retry: RetryRef | None = None


class RunResponse(BaseModel):
    model_config = _CAMEL

    run_id: str = Field(alias="runId", min_length=1)


# ─── preview-plate ─────────────────────────────────────────────────
class PreviewPlateError(BaseModel):
    model_config = _CAMEL

    path: str = Field(min_length=1, max_length=512)
    message: str = Field(min_length=1, max_length=1024)


class PreviewPlateResponse(BaseModel):
    """Return shape for POST /scenarios/preview-plate.

    导出场景时前端用 ``converted`` 字段拿 Plate 转换后的"可执行"用例结构
    (已合并 config/services/setup/teardown,字段归一化) — 这就是 GIMBAL
    实际运行时的输入。``errors`` 是 Plate 返回的字段级校验错。
    """

    model_config = _CAMEL

    ok: bool
    errors: list[PreviewPlateError] = Field(default_factory=list)
    # Plate /convert 转换后的场景 dict (consumer="platform")
    converted: dict[str, Any] | None = None


# ─── star ──────────────────────────────────────────────────────────
class StarIn(BaseModel):
    model_config = _CAMEL

    starred: bool


# ─── composite read-side shapes ────────────────────────────────────
class Scenario(BaseModel):
    """Read shape for a Scenario (list / detail / create response)."""

    model_config = _CAMEL

    meta: ScenarioMeta
    steps: list[dict[str, Any]] = Field(default_factory=list)  # plate step dicts
    # Optional round-trip of the persisted sub-structure for composer reload.
    # All absent on legacy rows → frontend rebuilds defaults; present on rows
    # saved by the container schema (definition/orchestration/caseMeta).
    config: dict[str, Any] | None = None
    resource: dict[str, Any] | None = None
    orchestration: Orchestration | None = None
    case_count: int = Field(default=0, ge=0, alias="caseCount")
    data_set_count: int = Field(default=0, ge=0, alias="dataSetCount")
    step_count: int = Field(default=0, ge=0, alias="stepCount")
    tags: list[str] = Field(default_factory=list)
    starred: bool = False


__all__ = [
    "AuthSessionRef",
    "AuthType",
    "Case",
    "CaseOverride",
    "CasePatch",
    "DataSet",
    "DataSetDraft",
    "DataSetRow",
    "DataSetSummary",
    "HttpMethod",
    "Orchestration",
    "PreviewPlateError",
    "PreviewPlateResponse",
    "Priority",
    "RetryRef",
    "RunEnv",
    "RunRequest",
    "RunResponse",
    "RunStatus",
    "Scenario",
    "ScenarioDraft",
    "ScenarioMeta",
    "StarIn",
    "StepKind",
    "StepOrchestration",
]
