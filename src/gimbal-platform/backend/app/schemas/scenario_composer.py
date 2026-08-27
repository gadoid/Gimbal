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
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ─── helpers ────────────────────────────────────────────────────────
# `populate_by_name` + alias lets us write `ScenarioMeta(scenario_id="...")`
# in Python while still emitting `"scenarioId": "..."` in JSON.  Both
# `by_alias=True` (the default in `.model_dump(by_alias=True)`) and
# plain attribute access work.
_CAMEL = ConfigDict(populate_by_name=True, str_strip_whitespace=True)


# ─── enums / small refs ─────────────────────────────────────────────
# NOTE: 运行级 retry 已按设计决策移除(PLATFORM_REQUIREMENTS.md #13:
# "N 次之间不做重试"——step 级重试由场景 Config.retry 承担,平台不叠加
# 重试层)。


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
    # 「最后编辑」— 服务端权威:读侧由 to_read_shape 以 DB 行 updated_at
    # 覆盖(_meta_from_row),draft 里客户端传的值不采信。
    update_time: datetime | None = Field(default=None, alias="updateTime")

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
        return cleaned


# ─── draft (request body) ──────────────────────────────────────────
class StepOrchestration(BaseModel):
    """Platform-side fields for one step, index-aligned with definition.steps[i]."""
    model_config = _CAMEL

    enabled: bool = True
    name: str = ""


class Orchestration(BaseModel):
    """Platform rendering/orchestration container.

    steps is index-aligned with definition.steps (same order, same length).
    resourceMeta is name-aligned with definition.resource keys.
    runSchemes is the run-scheme sidecar (spec §3.1): owned exclusively by
    PUT /scenarios/{id}/run-schemes — composer saves pass the stored value
    through untouched (scenario_store.update), so the key never round-trips
    through the editor. Old payloads without the key deserialize to [].
    """
    model_config = _CAMEL

    steps: list[StepOrchestration] = Field(default_factory=list)
    resourceMeta: dict[str, str] = Field(default_factory=dict)
    # RunScheme 定义在后文(依赖 ServiceBinding);future annotations 使该
    # 前向引用延迟解析,Orchestration.model_rebuild() 在其定义后闭合。
    run_schemes: list[RunScheme] = Field(default_factory=list, alias="runSchemes")


class ScenarioDraft(BaseModel):
    """Platform draft container.

    definition: the plate Scenario structure as a free-form dict. Backend does
                not model plate's internal types — plate /convert is the single
                validation authority ("plate outputs a neutral dict; consumers
                model it themselves").
    orchestration: platform-only rendering/orchestration fields, never sent
                   to plate (plate doesn't know about them).
    """
    model_config = _CAMEL

    definition: dict[str, Any]
    orchestration: Orchestration = Field(default_factory=Orchestration)


# ─── data-set ──────────────────────────────────────────────────────
class DataSet(BaseModel):
    model_config = _CAMEL

    dataset_id: str = Field(
        alias="datasetId", pattern=r"^ds-[a-z0-9-]+$", min_length=3, max_length=128
    )
    scenario_id: str = Field(
        alias="scenarioId",
        pattern=r"^sc-[a-z0-9-]+$",
        min_length=3,
        max_length=128,
    )
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=2048)
    row_count: int = Field(default=0, ge=0, alias="rowCount")
    rows: list[dict[str, Any]] = Field(default_factory=list)


class DataSetSummary(BaseModel):
    """Lightweight view used in list endpoints (preview[0:3])."""

    model_config = _CAMEL

    dataset_id: str = Field(alias="datasetId", min_length=1)
    scenario_id: str = Field(
        alias="scenarioId",
        pattern=r"^sc-[a-z0-9-]+$",
        min_length=3,
        max_length=128,
    )
    name: str = Field(min_length=1, max_length=128)
    row_count: int = Field(default=0, ge=0, alias="rowCount")
    preview: list[dict[str, Any]] = Field(default_factory=list, max_length=3)


class DataSetDraft(BaseModel):
    """Request body for POST /scenarios/{scenarioId}/data-sets and PUT /data-sets/{id}."""

    model_config = _CAMEL

    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=2048)
    rows: list[dict[str, Any]] = Field(default_factory=list)


# ─── envs / runs ───────────────────────────────────────────────────
class RunEnv(BaseModel):
    model_config = _CAMEL

    env_id: str = Field(alias="envId", min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=64)
    base_url: str = Field(alias="baseUrl", min_length=1, max_length=512)


class ServiceBinding(BaseModel):
    """service → {authAlias?, url?} 绑定(spec §3.1/§5)。"""
    model_config = _CAMEL

    auth_alias: str | None = Field(default=None, alias="authAlias", max_length=128)
    url: str | None = Field(default=None, alias="url", max_length=512)


class RunScheme(BaseModel):
    """场景级运行方案(orchestration sidecar,plate 零感知,spec §3.1)。"""
    model_config = _CAMEL

    name: str = Field(min_length=1, max_length=64)
    env_id: str | None = Field(default=None, alias="envId", max_length=64)
    data_set_ids: list[str] = Field(default_factory=list, alias="dataSetIds")
    service_bindings: dict[str, ServiceBinding] = Field(default_factory=dict,
                                                        alias="serviceBindings")
    plugins: Any = None        # 预埋,gimbal 就绪前 no-op
    log_sub: Any = Field(default=None, alias="logSub")  # 预埋,同上


class RunSchemesIn(BaseModel):
    """PUT /scenarios/{id}/run-schemes 请求体。"""
    model_config = _CAMEL

    schemes: list[RunScheme]


# Orchestration.run_schemes 的前向引用在此闭合(见 Orchestration 字段注释)。
Orchestration.model_rebuild()


class ExportOverlay(BaseModel):
    """导出/预览的运行方案覆盖层(spec §8)。dataSetIds 有意不收 —
    导出是场景级产物,行级展开是非目标。"""
    model_config = _CAMEL

    env_id: str | None = Field(default=None, alias="envId", min_length=1, max_length=64)
    service_bindings: dict[str, ServiceBinding] = Field(default_factory=dict,
                                                        alias="serviceBindings")


class RunRequest(BaseModel):
    """一次执行的配方(recipe):env/数据集/认证等全是纯值。

    Case 层已解散 — RunRequest 即配方本身,直接挂在 scenario 上。
    """

    model_config = _CAMEL

    scenario_id: str = Field(
        alias="scenarioId",
        pattern=r"^sc-[a-z0-9-]+$",
        min_length=3,
        max_length=128,
    )
    # D12:空列表 = 基线执行(一个隐式空覆盖行),不再强制 min_length=1
    data_set_ids: list[str] = Field(alias="dataSetIds", default_factory=list)
    # service → {authAlias?, url?} 绑定(spec §3.1/§5):注入清单 =
    # 模板扫描(steps 里的 ${auth.*} 引用)∪ 绑定 authAlias;绑定 url
    # 物化进 services(显式绑定最优先)。旧 auths/inject_credentials/
    # prefix/merge_policy 四字段已退役(spec §6)— 旧客户端多发的键
    # 被 pydantic 静默忽略,仅失效、不 422。
    service_bindings: dict[str, ServiceBinding] = Field(
        default_factory=dict, alias="serviceBindings"
    )
    env: RunEnv
    # V1 高级能力移植:``stepTo`` 0-based 含端点(与 V1 executions 的
    # step_to 同语义),dispatcher 透传 gimbal HTTP ``halt_at``。
    step_to: int | None = Field(default=None, ge=0, alias="stepTo")
    # ── M1 执行能力补齐(V1 executor 语义移植)────────────────────
    # 每行数据的重复执行次数;total_runs = Σ(rows) × nRuns。
    n_runs: int = Field(default=1, ge=1, le=1000, alias="nRuns")
    # fan-out 并发度(asyncio.Semaphore 上限)。
    parallel: int = Field(default=1, ge=1, le=200, alias="parallel")


class RunResponse(BaseModel):
    model_config = _CAMEL

    run_id: str = Field(alias="runId", min_length=1)
    # Numeric Execution row backing this dispatch — lets the frontend jump
    # straight to /executions/{id} (the string runId alone has no route).
    execution_id: int = Field(alias="executionId")


# ─── preview-plate ─────────────────────────────────────────────────
class PreviewPlateIn(ScenarioDraft):
    """POST /scenarios/preview-plate 请求体:ScenarioDraft + 可选 overlay。

    ``overlay`` 不传 → 与旧 ScenarioDraft 行为完全一致(向后兼容,
    spec §8);传入则 convert 产物经 materialize_run_copy 物化(明文
    绑定/凭证注入 POST-convert 位点,不过 plate)。
    """

    overlay: ExportOverlay | None = None


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
    # Absent → frontend rebuilds defaults; present on rows saved by the
    # container schema (definition/orchestration).
    config: dict[str, Any] | None = None
    resource: dict[str, Any] | None = None
    orchestration: Orchestration | None = None
    data_set_count: int = Field(default=0, ge=0, alias="dataSetCount")
    step_count: int = Field(default=0, ge=0, alias="stepCount")
    tags: list[str] = Field(default_factory=list)
    starred: bool = False
    # private(默认,仅 owner/admin 可读)| public(所有登录用户可读)
    visibility: str = Field(default="private")


__all__ = [
    "DataSet",
    "DataSetDraft",
    "DataSetSummary",
    "ExportOverlay",
    "Orchestration",
    "PreviewPlateError",
    "PreviewPlateIn",
    "PreviewPlateResponse",
    "RunEnv",
    "RunRequest",
    "RunResponse",
    "RunScheme",
    "RunSchemesIn",
    "Scenario",
    "ScenarioDraft",
    "ScenarioMeta",
    "ServiceBinding",
    "StarIn",
    "StepOrchestration",
]
