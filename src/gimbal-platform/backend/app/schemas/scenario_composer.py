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
    (runSchemes sidecar 键已随阶段④下线 — 方案不经场景 payload,唯一
    读写面是 /run-schemes CRUD;存量 payload 中的同键被 extra=ignore
    静默忽略。)
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
    assertion_registry: 断言管理注册表(spec v2 §3)— 平台侧偏离注入条目,
                与 orchestration 同级;引擎不感知,不进 plate convert。自由 dict,
                条目形状权威在前端 types/assertion-registry.ts 与运行时物化函数。
    """
    model_config = _CAMEL

    definition: dict[str, Any]
    orchestration: Orchestration = Field(default_factory=Orchestration)
    # 默认形状对齐前端权威契约(types/assertion-registry.ts:{ entries: [] })—
    # V2 之前的存量 draft 无此键,default 补 {} 曾让前端 ?? 归一失效
    # (truthy 无 entries)。前端水化已统一 normalizeRegistry,这里补形状
    # 只是把同一契约立在后端出参上(防御纵深,非唯一防线)。
    assertion_registry: dict[str, Any] = Field(
        default_factory=lambda: {"entries": []}
    )


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
    var_unlocks: list[str] = Field(default_factory=list, alias="varUnlocks")


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
    var_unlocks: list[str] = Field(default_factory=list, alias="varUnlocks")


# ─── runs ───────────────────────────────────────────────────────────
class ServiceBinding(BaseModel):
    """service → {authAlias?, url?} 绑定(spec §3.1/§5)。
    查询凭证唯一来源 = config.users 首键(查询身份 = 执行身份),
    与运行方案无关;侧车残留键被 extra=ignore 静默丢弃
    (退场记录见 docs/adr/0003)。"""
    model_config = _CAMEL

    auth_alias: str | None = Field(default=None, alias="authAlias", max_length=128)
    url: str | None = Field(default=None, alias="url", max_length=512)


class DataSetSelection(BaseModel):
    """行级数据集选择(spec v3 §4):datasetId + rowIndexes(0-based,
    与编辑器行号一致;缺省/空 = 整库)。RunRequest/RunScheme 的权威
    选择键;旧 dataSetIds 保留为兼容读(两键同发本键优先)。"""
    model_config = _CAMEL

    dataset_id: str = Field(alias="datasetId", min_length=1, max_length=128)
    row_indexes: list[int] = Field(default_factory=list, alias="rowIndexes")


class RunScheme(BaseModel):
    """场景级运行方案(工作台一等实体,plate 零感知,spec §4)。

    /run-schemes CRUD(方案唯一读写面)的请求/响应 wire 契约;
    isDefault/stepTo/nRuns/parallel 为工作台键。
    """
    model_config = _CAMEL

    name: str = Field(min_length=1, max_length=64)
    is_default: bool = Field(default=False, alias="isDefault")
    data_set_ids: list[str] = Field(default_factory=list, alias="dataSetIds")
    # 断言注入条目(spec v2 §5):RunDialog 异常组多选,选中的条目与数据集
    # 行并列生成 case;default 空 = 旧方案缺键不炸。
    injection_entry_ids: list[str] = Field(default_factory=list,
                                           alias="injectionEntryIds")
    # 行级数据集选择(spec v3 §4)— 权威键;旧方案无此键 = 整库回读。
    data_set_selection: list[DataSetSelection] = Field(
        default_factory=list, alias="dataSetSelection"
    )
    service_bindings: dict[str, ServiceBinding] = Field(default_factory=dict,
                                                        alias="serviceBindings")
    step_to: int | None = Field(default=None, alias="stepTo", ge=0)
    n_runs: int = Field(default=1, alias="nRuns", ge=1, le=1000)
    parallel: int = Field(default=1, alias="parallel", ge=1, le=200)
    plugins: Any = None        # 预埋,gimbal 就绪前 no-op
    log_sub: Any = Field(default=None, alias="logSub")  # 预埋,同上


class ExportOverlay(BaseModel):
    """导出/预览的运行方案覆盖层(spec §8)。dataSetIds 有意不收 —
    导出是场景级产物,行级展开是非目标。执行环境键已随 D2 退役。"""
    model_config = _CAMEL

    service_bindings: dict[str, ServiceBinding] = Field(default_factory=dict,
                                                        alias="serviceBindings")


class RunRequest(BaseModel):
    """一次执行的配方(recipe):数据集/认证等全是纯值。

    Case 层已解散 — RunRequest 即配方本身,直接挂在 scenario 上。
    旧 ``env`` 字段已随 D2 退役 — 旧客户端多发的 env 键被 pydantic
    静默忽略,仅失效、不 422。
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
    # 行级数据集选择(spec v3 §4)— 权威键;两键同发时本键优先,dataSetIds 忽略
    data_set_selection: list[DataSetSelection] = Field(
        default_factory=list, alias="dataSetSelection"
    )
    # service → {authAlias?, url?} 绑定(spec §3.1/§5):注入清单 =
    # 模板扫描(steps 里的 ${auth.*} 引用)∪ 绑定 authAlias;绑定 url
    # 物化进 services(显式绑定最优先)。旧凭证策略四字段(auths /
    # inject_credentials / prefix / merge 策略)已退役(spec §6)—
    # 旧客户端多发的键被 pydantic 静默忽略,仅失效、不 422。
    service_bindings: dict[str, ServiceBinding] = Field(
        default_factory=dict, alias="serviceBindings"
    )
    # 断言注入条目(spec v2 §5/§8):选中条目在 dispatch 时物化为注入族
    # (payload.assertion_registry → 基线 vars 覆写 + asserts patch),
    # 与数据集行并列生成 case;空 = 不注入。
    injection_entry_ids: list[str] = Field(default_factory=list,
                                           alias="injectionEntryIds")
    # V1 高级能力移植:``stepTo`` 0-based 含端点(与 V1 executions 的
    # step_to 同语义),dispatcher 透传 gimbal HTTP ``halt_at``。
    step_to: int | None = Field(default=None, ge=0, alias="stepTo")
    # ── M1 执行能力补齐(V1 executor 语义移植)────────────────────
    # 每行数据的重复执行次数;total_runs = Σ(rows) × nRuns。
    n_runs: int = Field(default=1, ge=1, le=1000, alias="nRuns")
    # fan-out 并发度(asyncio.Semaphore 上限)。
    parallel: int = Field(default=1, ge=1, le=200, alias="parallel")
    # 方案溯源(spec §5,阶段③):config_json 快照语义 — 记录本次执行
    # 来自哪个方案(改名不断链:schemeId 权威,name 仅展示)。可选 —
    # 基线/旧客户端不传;纯记录,不参与任何分发语义。
    scheme_id: str | None = Field(default=None, alias="schemeId", max_length=128)
    scheme_name: str | None = Field(default=None, alias="schemeName", max_length=64)
    # 批次键(执行设计 §1.2/§6):前端队列逐条顺序发起时共用一个客户端
    # 生成的 batch_id,Execution.batch_id 落列、执行记录据此归并。可选 —
    # 单条发起(运行对话框/重跑)不传;纯归并键,不参与分发语义(每条
    # 仍是独立 Execution,批级执行策略本期不存在)。
    batch_id: str | None = Field(default=None, alias="batchId", max_length=64)


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
    scheme_count: int = Field(default=0, ge=0, alias="schemeCount")
    step_count: int = Field(default=0, ge=0, alias="stepCount")
    tags: list[str] = Field(default_factory=list)
    starred: bool = False
    # private(默认,仅 owner/admin 可读)| public(所有登录用户可读)
    visibility: str = Field(default="private")


# ─── M1 列表响应投影(PG迁移方案 §7 M1 / §4.1)────────────────────────
class ScenarioListItem(BaseModel):
    """列表行形态 — 响应投影:不含 steps/config/resource/orchestration
    (payload 重的字段),列表页只消费 meta 摘要 + 计数 + starred。

    服务端查询仍是全表加载 payload + Python 过滤(M1 不假装拿到 SQL 端
    过滤——那是 M3 生成列上线后的事);本形态砍的是**响应体**,不是查询。
    """

    model_config = _CAMEL

    meta: ScenarioMeta
    data_set_count: int = Field(default=0, ge=0, alias="dataSetCount")
    scheme_count: int = Field(default=0, ge=0, alias="schemeCount")
    step_count: int = Field(default=0, ge=0, alias="stepCount")
    # 声明变量数(列表「变量」列;count only,config 本体不出列表)
    var_count: int = Field(default=0, ge=0, alias="varCount")
    tags: list[str] = Field(default_factory=list)
    starred: bool = False
    visibility: str = Field(default="private")


class ScenarioOptionsItem(BaseModel):
    """``?fields=options`` 轻量元数据形态(§4.2)——选择器与名称映射专用,
    砍掉四处「为拿名字拉全量场景表」。可见性口径与列表一致(member =
    自己 + public / admin = 全量,由路由层保证)。"""

    model_config = _CAMEL

    scenario_id: str = Field(alias="scenarioId")
    name: str
    visibility: str = Field(default="private")
    owner: str = Field(default="")


class ScenarioListOut(BaseModel):
    """Page 信封(§4.1 统一列表契约):{items, total, page, pageSize}。"""

    model_config = _CAMEL

    items: list[ScenarioListItem]
    total: int
    page: int
    page_size: int = Field(alias="pageSize")


class ScenarioOptionsOut(BaseModel):
    """options 形态共用同一 Page 信封(§4.1)。"""

    model_config = _CAMEL

    items: list[ScenarioOptionsItem]
    total: int
    page: int
    page_size: int = Field(alias="pageSize")


__all__ = [
    "DataSet",
    "DataSetDraft",
    "DataSetSelection",
    "DataSetSummary",
    "ExportOverlay",
    "Orchestration",
    "PreviewPlateError",
    "PreviewPlateIn",
    "PreviewPlateResponse",
    "RunRequest",
    "RunResponse",
    "RunScheme",
    "Scenario",
    "ScenarioDraft",
    "ScenarioListItem",
    "ScenarioListOut",
    "ScenarioMeta",
    "ScenarioOptionsItem",
    "ScenarioOptionsOut",
    "ServiceBinding",
    "StarIn",
    "StepOrchestration",
]
