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

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ._m2 import CheckDecl, DebugSpec, GateDecl, RunOptions


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
    """Scenario metadata; one Scenario has exactly one Meta.

    M2 ``Meta`` 的**超集读投影**:声明的字段做校验与别名,其余字段
    (``requirementRef`` 及 M2 后续新增)经 ``extra="allow"`` 原样透传。
    读侧由 ``_meta_from_row`` 从 payload.definition.meta 组装 —— 此前
    手写字段清单对未知键静默丢弃,requirementRef 读侧被剥、编排器水合
    再保存即丢字段(A-1,2026-10-12);M2 Meta 每加一个字段都会重演。
    ``module``/``system`` 对齐 M2 空值语义('' / []):旧库存量空值
    原样保留,不再注入伪系统/模块 "default"(M11:meta.system 每个
    系统必须有 plate 声明,"default" 永远不合法)。
    """

    model_config = ConfigDict(
        populate_by_name=True, str_strip_whitespace=True, extra="allow")

    scenario_id: str = Field(
        alias="scenarioId",
        pattern=r"^sc-[a-z0-9-]+$",
        min_length=3,
        max_length=128,
    )
    name: str = Field(min_length=1, max_length=64)
    description: str = Field(default="", max_length=2048)
    module: str = Field(default="", max_length=64)
    priority: int = Field(ge=0, le=3)
    author: str = Field(default="", max_length=128)
    owner: str = Field(default="", max_length=128)
    tags: list[str] = Field(default_factory=list, max_length=32)
    system: list[str] = Field(default_factory=list)
    version: str = Field(default="v0.1.0", max_length=32)
    expire: bool = False
    create_time: datetime | None = Field(default=None, alias="createTime")
    # 「最后编辑」— 服务端权威:读侧由 to_read_shape 以 DB 行 updated_at
    # 覆盖(_meta_from_row),draft 里客户端传的值不采信。
    update_time: datetime | None = Field(default=None, alias="updateTime")
    # 版本声明(Release 4.4):{系统: '<line>#<n>' | 'working'}。读侧必须
    # 透传 —— 编排器水合靠它保留版本声明;此前本模型缺此字段,普通 GET
    # 的响应序列化静默剥掉 plate,编排器导出/保存的草稿即失去重投影
    # 依据(锚点步骤的 call 直通校验必炸,2026-10-12 导出失效根因之二)。
    plate: dict[str, str] | None = Field(default=None, alias="plate")

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
        # A-1:空表 = 未声明系统,对齐 M2 Meta(List[str] = [])原样放行
        # ——「至少一个」不再由读模型强制(旧兜底注入的伪系统 "default"
        # 与 M11 每系统须有 plate 声明冲突,已随兜底一并删除)。
        if not v:
            return []
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
    # M4/Q18:编辑器状态(UI 侧投影)放定义之外 —— ui.fieldStates 按步骤
    # 位置索引({"<stepIndex>": {path: state}});与 orchestration 同级,
    # plate /convert 不感知(定义即纯 M2,Step 不再含 field_states)。
    ui: dict[str, Any] = Field(default_factory=dict)


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
    isDefault/options(M10 RunOptions)为工作台键。
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
    # M10 RunOptions 形状(迁移完成,不再收旧平铺键)
    options: dict[str, Any] = Field(default_factory=lambda: {
        "step_from": None, "step_to": None,
        "n_runs": 1, "parallel": 1, "subscribe": None,
    })
    log_sub: Any = Field(default=None, alias="logSub")  # 预埋,同上


class ExportOverlay(BaseModel):
    """导出/预览的运行方案覆盖层(spec §8)。dataSetIds 有意不收 —
    导出是场景级产物,行级展开是非目标。执行环境键已随 D2 退役。"""
    model_config = _CAMEL

    service_bindings: dict[str, ServiceBinding] = Field(default_factory=dict,
                                                        alias="serviceBindings")


class ScenarioCopyIn(BaseModel):
    """POST /scenarios/{id}/copy 可选请求体(2026-09-23 批次 F2 另存为)。

    缺省(无 body)= 旧「复制到我的」行为,副本名沿用 ``(副本)`` 后缀;
    带 ``name`` = 另存为,重名由端点 409 + suggestion 交前端确认
    (软校验口径见 scenario_store.resolve_name_conflict)。
    """

    name: str | None = Field(default=None, min_length=1, max_length=64)


class GraphControlSpec(BaseModel):
    """编排裁剪控制(重构方案):only = 试跑选中段(所选单元 + 传递
    上游,make 语义);toNode = 串联只跑到某一步。fromNode 刻意不收 ——
    执行器 from_node 切片要求被跳过的上游输出由外部提供,平台无从提供。"""

    model_config = _CAMEL

    only: list[str] = Field(default_factory=list)
    to_node: str | None = Field(default=None, alias="toNode")


class GraphUnitSpec(BaseModel):
    """C5:编排单元 —— 一个平台场景在 graph 里的一个节点。"""
    model_config = _CAMEL

    ref: str = Field(..., min_length=1, max_length=128)
    scenario_id: str = Field(alias="scenarioId",
                             pattern=r"^sc-[a-z0-9-]+$")
    needs: list[str] = Field(default_factory=list)
    shared: str | None = None
    inputs: dict[str, Any] = Field(default_factory=dict)
    repeat: int = Field(default=1, ge=1, le=64)
    n_runs: int = Field(default=1, ge=1, le=64, alias="nRuns")
    # 单元粒度注入(条目 id 取自该场景的 assertion_registry)
    injection_entry_ids: list[str] = Field(default_factory=list,
                                           alias="injectionEntryIds")
    # 单元粒度服务绑定(与 graph 级合并,单元覆盖同名)
    service_bindings: dict[str, Any] = Field(default_factory=dict,
                                              alias="serviceBindings")
    # ── 重构方案约束 5/第 6 处(单行内联 + 连线改名)──
    # 运行方案:空 = 该场景的默认方案
    scheme_id: str | None = Field(default=None, alias="schemeId")
    # 选定该单元唯一运行的一行;空 = 裸基线(不带数据集行)
    row: dict[str, Any] | None = Field(default=None, description=(
        "{datasetId, rowIndex}(0-based,与编辑器一致;缺省=裸基线)"))
    # 连线改名(上游输出名 → 本地输入名),对应执行器 UnitDecl.map
    map: dict[str, str] = Field(default_factory=dict)


class GraphSpec(BaseModel):
    """C5:suite 编排执行规格(D-6 保留横切面:gates/checks 可选)。"""
    model_config = _CAMEL

    mode: Literal["aggregate", "compose", "fanout", "chain"] = "aggregate"
    units: list[GraphUnitSpec] = Field(..., min_length=1)
    before: list[GraphUnitSpec] = Field(default_factory=list)
    after: list[GraphUnitSpec] = Field(default_factory=list)
    parallel: int = Field(default=1, ge=1, le=64)
    n_runs: int = Field(default=1, ge=1, le=64, alias="nRuns")
    # N1 横切面(D-6 保留):与引擎 GateDecl/CheckDecl 同形
    # M2 §9.6(W20):gates/checks 均改用生成物(镜像清零;wire 键
    # 单词无驼峰差,CheckDecl extra=forbid 即保存时校验)
    gates: list[GateDecl] = Field(default_factory=list)
    checks: list[CheckDecl] = Field(default_factory=list)
    # graph 级服务绑定(单元可覆盖)
    service_bindings: dict[str, Any] = Field(default_factory=dict,
                                              alias="serviceBindings")
    # 裁剪控制(重构方案第 2 处:only / toNode;fromNode 不开放)
    control: GraphControlSpec | None = None


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
    # ── M2 RunOptions 生成物形状(W19/B-4;Q4 结论:上限对齐 64)──
    # 执行参数不再平铺 — ``stepTo``/``nRuns``/``parallel``/``debug``
    # 四个顶层键退役,统一收进 ``runOptions``(内层键 snake_case,
    # 与生成物/执行器 ``POST /runs`` options 同形;RunScheme.options
    # 自 M10 起已是同一形状)。旧客户端多发的平铺键被 pydantic
    # 静默忽略,仅失效、不 422。
    # step_from/subscribe 在生成物形状里存在但平台派发链未接
    # (前者需要被跳过上游的输出由外部提供,后者无消费面)——
    # dispatch 侧显式 409,不静默丢弃。
    run_options: RunOptions | None = Field(
        default=None, alias="runOptions",
        description="执行指令(M2 RunOptions 生成物;缺省全默认)")
    # C5(P3-05):suite 编排执行 —— 非空时走 graph 链(单元 = 平台场景),
    # 数据集/注入在单元粒度声明;graph 链忽略顶层 dataSetIds/selection。
    graph: "GraphSpec | None" = Field(default=None, description="编排执行规格(C5)")
    # P3-07/C7:执行时选择报告定义 → 引擎 definition reporter 产出工件
    report_definition_id: int | None = Field(
        default=None, alias="reportDefinitionId",
        description="报告定义 id(P3-07;None = 默认报告)")
    # 方案溯源(spec §5,阶段③):config_json 快照语义 — 记录本次执行
    # 来自哪个方案(改名不断链:schemeId 权威,name 仅展示)。可选 —
    # 基线/旧客户端不传;纯记录,不参与任何分发语义。
    scheme_id: str | None = Field(default=None, alias="schemeId", max_length=128)
    scheme_name: str | None = Field(default=None, alias="schemeName", max_length=64)
    # 批次键(执行设计 §1.2/§6):前端队列逐条顺序发起时共用一个客户端
    # 生成的 batch_id,Execution.batch_id 落列、执行记录据此归并。可选 —
    # 单条发起(运行对话框/重跑)不传;纯归并键,不参与任何分发语义(每条
    # 仍是独立 Execution,批级执行策略本期不存在)。
    batch_id: str | None = Field(default=None, alias="batchId", max_length=64)

    # ── 派生读取面(W19):调用方按习惯属性读执行参数 ─────────────
    # 值的唯一权威 = run_options(缺省 = RunOptions() 全默认);
    # 这些 property 只是薄投影,不另立状态。
    @property
    def opts(self) -> RunOptions:
        return self.run_options if self.run_options is not None else RunOptions()

    @property
    def n_runs(self) -> int:
        return self.opts.n_runs

    @property
    def parallel(self) -> int:
        return self.opts.parallel

    @property
    def step_to(self) -> int | None:
        return self.opts.step_to

    @property
    def debug(self) -> DebugSpec | None:
        return self.opts.debug


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
