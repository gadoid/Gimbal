"""platform export —— 把 Scenario 数据类翻译为 platform 后端消费的渲染视图。

公开 API:
    PlatformScenarioExporter
    PlatformScenarioView
    PlatformStepView
    PlatformEndpointView

V3.1 设计(PLATE_V3_DESIGN.md §7,与 gimbal export 共享同一个 Scenario 数据类):
- 真相源是 gimbal_plate.schema.Scenario(中性数据类)
- PlatformScenarioExporter 接收 Scenario,产出 platform 渲染视图 dict
- 顶层与 gimbal 对齐(kind/scenarioId/meta/config/resource/steps),
  再附加 platform 视图扩展字段(endpoints / navigation / config_summary)
- 每条 step 内层加 platform 视图扩展字段:
  - api.view_hints(endpoint_id/module/tags)
  - request.body 已用 endpoint 全量字段定义补全(直接渲染 + 直接执行);carry 键不补默认,仅透传 body 已有字面量
  - request.fields_meta:{字段名 → binding 通道声明条目全量元数据}(平台前端渲染用)
  - strategy[i].view_note(人类语言摘要)
- 端到端链路:platform 落库 dict → (仅改 kind)→ Scenario.model_validate()
  → GimbalScenarioExporter.to_dict() 得到 gimbal 可执行 dict
- V3.1 删除 strip_platform_view_fields():所有平台视图字段都已在 schema 上声明,
  Scenario.model_validate 直接接受,不再需要预处理函数

V3.1.1 抽象化:继承 ``gimbal_plate.export._protocol.ScenarioExporter``,
获得统一 consumer_id / render 契约 + Step 2 声明式 dispatch 的预留能力。
"""
from __future__ import annotations

import re
from typing import Any, override

from pydantic import BaseModel, ConfigDict, Field

from gimbal_plate.export._protocol import ExporterCapabilities, ScenarioExporter
from gimbal_plate.schema.api import Api
from gimbal_plate.schema.endpoint import EndpointSpec
from gimbal_plate.schema.request import Request
from gimbal_plate.schema.scenario import Scenario as ScenarioModel
from gimbal_plate.schema.strategy import Assertion, Assign, Extract
from gimbal_plate.utils import path as _path_utils


# ── 视图输出模型 ──────────────────────────────────────────────────

class PlatformStepView(BaseModel):
    """platform 视角下的单条 step,shape 与 gimbal step 对齐 + platform 扩展字段。"""

    model_config = ConfigDict(extra="forbid")

    kind: str = "step"
    description: str = ""
    api: dict[str, Any]
    request: dict[str, Any]
    strategy: list[dict[str, Any]] = Field(default_factory=list)


class PlatformEndpointView(BaseModel):
    """platform 视角下的单个 endpoint 渲染视图。

    字段来源:
    - id/system/service/name/description/method/path/auth/timeout/version:
      直接来自 EndpointSpec
    - module/tags/owner/priority/preconditions/success_criteria/business_notes:
      来自 EndpointMetadata
    - request_fields/response_fields/assertable_paths:
      来自 RequestSpec/ResponseSpec 的 declarations 按通道投影
      (binding / view_only / view_only∧assertable)
    - request_body_sample / request_body_samples:
      从 Scenario.steps 中按 (method,path) 匹配的 step.request.body 聚合
    - deep_link:平台前端跳转锚点
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    system: str
    service: str
    name: str
    description: str
    method: str
    path: str
    auth: str = "bearer"
    timeout_seconds: float = 30.0
    version: str

    module: str = ""
    tags: list[str] = Field(default_factory=list)
    owner: str = ""
    priority: int | None = None
    preconditions: list[str] = Field(default_factory=list)
    success_criteria: str = ""
    business_notes: str = ""

    request_fields: list[dict[str, Any]] = Field(default_factory=list)
    response_fields: list[dict[str, Any]] = Field(default_factory=list)
    assertable_paths: list[str] = Field(default_factory=list)

    request_body_sample: dict[str, Any] = Field(default_factory=dict)
    request_body_samples: list[dict[str, Any]] = Field(default_factory=list)

    deep_link: str = ""


class PlatformScenarioView(BaseModel):
    """platform 后端消费的 scenario 视图。

    顶层与 gimbal scenario 对齐,再附加 platform 视图扩展:
    - endpoints:每个 endpoint 的渲染视图(PlatformEndpointView)
    - navigation:按 service 分组的导航树
    - config_summary:配置项分类提示(env_placeholder / scenario_var_placeholder / ...)
    """

    model_config = ConfigDict(extra="forbid")

    kind: str = "platform_scenario"
    scenarioId: str
    meta: dict[str, Any] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)
    resource: dict[str, Any] = Field(default_factory=dict)
    steps: list[PlatformStepView] = Field(default_factory=list)

    endpoints: list[PlatformEndpointView] = Field(default_factory=list)
    navigation: dict[str, list[dict[str, str]]] = Field(default_factory=dict)
    config_summary: dict[str, Any] = Field(default_factory=dict)


# ── 平台 dict → Scenario 还原辅助 ──────────────────────────────────
# V3.1 已删除 strip_platform_view_fields()。所有平台视图字段都已在 schema 层
# 声明(PLATE_V3_DESIGN.md §7),Scenario.model_validate 直接接受,无需任何预处理。
# 端到端链路(由调用方 platform 后端负责):
#     platform_dict = json.loads(落库的 JSON)
#     platform_dict["kind"] = "scenario"        # 仅这一行
#     scenario = Scenario.model_validate(platform_dict)
#     gimbal_dict = GimbalScenarioExporter(scenario).to_dict()


# ── 内部:Step → platform dict ──────────────────────────────────

def _render_strategy_view(strategy: list[Assertion | Assign | Extract]) -> list[dict[str, Any]]:
    """把 Strategy 子模型列表翻译为 dict 列表,加 view_note。"""
    out: list[dict[str, Any]] = []
    for s in strategy:
        entry = s.model_dump(mode="json", exclude_none=True)
        if isinstance(s, Assertion):
            entry["view_note"] = (
                f"{s.target} {s.operator.value} {s.expected!r}"
            )
        elif isinstance(s, Assign):
            entry["view_note"] = f"{s.source} → {s.target}"
        elif isinstance(s, Extract):
            entry["view_note"] = f"{s.expression} → {s.target}"
        out.append(entry)
    return out


def _merge_carry_literal(path: str, body: dict[str, Any], full_body: dict[str, Any]) -> None:
    """把 body 中已存在的 carry 路径字面量原样并入 full_body。

    嵌套路径("$.a.b")逐层下钻;任一层缺失即视为无字面量,不加键。
    已存在于 full_body 的键不覆盖(fields/carry 面互斥,防御性保留)。
    """
    parts = [p for p in path.lstrip("$").split(".") if p]
    if not parts:
        return
    src: Any = body
    for p in parts:
        if isinstance(src, dict) and p in src:
            src = src[p]
        else:
            return
    dst: dict[str, Any] = full_body
    for p in parts[:-1]:
        nxt = dst.get(p)
        if not isinstance(nxt, dict):
            nxt = {}
            dst[p] = nxt
        dst = nxt
    dst.setdefault(parts[-1], src)


# ── 内部:path 寻址读写(D11 binding 补全按 path 寻址写) ───────────

_MISSING = object()


def _path_segs(path: str) -> list[Any]:
    """'$.a[0].b' → ['a', 0, 'b'](FIELD/INDEX 段;binding 限具体路径后无通配)。"""
    segs: list[Any] = []
    for m in re.finditer(r"([^[\].]+)|\[(\d+)\]", path.lstrip("$.")):
        segs.append(m.group(1) if m.group(1) is not None else int(m.group(2)))
    return segs


def _get_by_path(data: Any, segs: list[Any]) -> Any:
    cur = data
    for seg in segs:
        if isinstance(seg, int):
            if not isinstance(cur, list) or seg >= len(cur):
                return _MISSING
            cur = cur[seg]
        else:
            if not isinstance(cur, dict) or seg not in cur:
                return _MISSING
            cur = cur[seg]
    return cur


def _set_by_path(container: Any, segs: list[Any], value: Any) -> Any:
    """按段写值,中间节点自动创建(FIELD→dict/INDEX→list+pad None),对齐 gimbal _set_at。"""
    if not segs:
        return value
    seg, rest = segs[0], segs[1:]
    if isinstance(seg, int):
        if not isinstance(container, list):
            container = []
        while len(container) <= seg:
            container.append(None)
        container[seg] = _set_by_path(container[seg], rest, value)
        return container
    if not isinstance(container, dict):
        container = {}
    container[seg] = _set_by_path(container.get(seg), rest, value)
    return container


def _render_request_view(request: Request, ep: EndpointSpec | None) -> dict[str, Any]:
    """把 Request 翻译为 dict,body 全量补全 + fields_meta 携带字段元数据。

    设计(PLATE_V3_DESIGN.md §7.2 方案 C):
    - body 仍是纯 dict;D11 起 binding 补全按声明 path 寻址写:
      平铺路径落顶层键,深层路径("$.a[0].b")值落嵌套形态
    - 字段值优先级:body 已填值 → endpoint default → endpoint example → None
      (深层路径无值不落 None 骨架,D7:防挡 carry 容器注入;平铺维持 None 占位)
    - carry 面键(spec §2.2):不参与补全,仅透传 body 已有字面量(值归 platform 值表)
    - 字段元数据集中放在 fields_meta:{name → binding 通道声明条目全量元信息}
      (path / channel / type / required / default / example / description /
       enum / ui_kind / source_kind / assertable)
    - 平台前端:O(N) 遍历 body + O(1) 查 fields_meta[name]
    - 反向转 gimbal:Scenario.model_validate(platform_dict) 直接接受 fields_meta;
      GimbalScenarioExporter.to_dict() 通过 model_dump(exclude=...) 过滤掉,
      body 已是 Scenario 校验通过的完整字段,gimbal 零适配
    - 注:fields_meta 必须用普通字段名(不能 _fields_meta),因为 Pydantic 把
      下划线前缀视为 PrivateAttr,会静默丢弃(PLATE_V3_DESIGN.md §7.1)
    """
    body = request.body if request.body is not None else {}
    full_body: dict[str, Any] = {}
    fields_meta: dict[str, Any] = {}
    if ep is not None and ep.request is not None:
        for f in (e for e in ep.request.declarations if e.channel == "binding"):
            # 1) 字段元数据全量带上(让平台表单渲染有依据;按 name 键控,条目带 path)
            fields_meta[f.name] = f.model_dump(mode="json", exclude_none=True)
            # 2) body 的值优先级(D11 按 path 寻址,深层值落嵌套):
            #    body 已填值 → default → example → None
            segs = _path_segs(f.path)
            if not segs:
                # 根路径 binding($ 整体):无按键写值的语义,跳过值面(fields_meta 仍登记)
                continue
            deep = len(segs) > 1 or isinstance(segs[0], int)
            value = _get_by_path(body, segs)
            if value is _MISSING:
                if f.default is not None:
                    value = f.default
                elif f.example is not None:
                    value = f.example
                else:
                    value = None
            if value is None and deep:
                continue  # D7:深层无值不落 None 骨架(防挡 carry 容器注入)
            if deep or value is not _MISSING:
                _set_by_path(full_body, segs, value)
        # 3) carry 面键:值归 platform 两层值表管,不补默认、不造 None 占位;
        #    body 已带字面量的原样并入 —— 保住 gimbal→platform→gimbal 往返
        #    子集契约,且与运行时 fill-missing(body 显式值优先)语义一致。
        for carry_path in (e.path for e in ep.request.declarations
                           if e.channel == "carry"):
            _merge_carry_literal(carry_path, body, full_body)
    else:
        full_body = dict(body)
    return {
        "kind": request.kind,
        "body": full_body,
        "fields_meta": fields_meta,
    }


def _render_api_view(api: Api, ep: EndpointSpec | None) -> dict[str, Any]:
    """把 Api 翻译为 dict,加 view_hints。"""
    out: dict[str, Any] = {
        "kind": api.kind,
        "service": api.service,
        "method": api.method,
        "path": api.path,
        "headers": dict(api.headers),
        "timeout": api.timeout,
    }
    if ep is not None:
        out["view_hints"] = {
            "endpoint_id": ep.id,
            "module": ep.metadata.module,
            "tags": list(ep.metadata.tags),
        }
    return out


# ── 内部:Endpoint → PlatformEndpointView ────────────────────────

def _render_endpoint_view(
    ep: EndpointSpec,
    body_samples: list[dict[str, Any]],
) -> PlatformEndpointView:
    """单个 EndpointSpec + 聚合到的 request_body 样本 → PlatformEndpointView。"""
    request_fields: list[dict[str, Any]] = []
    if ep.request is not None:
        for f in (e for e in ep.request.declarations if e.channel == "binding"):
            request_fields.append({
                "name": f.name,
                "path": _path_utils.normalize(f.path),
                "required": f.required,
                "ui_kind": f.ui_kind,
                "example": f.example,
                "description": f.description,
                "enum": f.enum or [],
                "source_kind": f.source_kind,
            })

    response_fields: list[dict[str, Any]] = []
    assertable: list[str] = []
    for status, spec in ep.responses.items():
        for f in (e for e in spec.declarations if e.channel == "view_only"):
            response_fields.append({
                "status": status,
                "name": f.name,
                "path": _path_utils.normalize(f.path),
                "required": f.required,
                "ui_kind": f.ui_kind,
                "example": f.example,
            })
        assertable.extend(
            e.path for e in spec.declarations
            if e.channel == "view_only" and e.assertable
        )

    md = ep.metadata
    sample = body_samples[0] if body_samples else {}
    samples = [s for s in body_samples if s]

    return PlatformEndpointView(
        id=ep.id,
        system=ep.system,
        service=ep.service,
        name=ep.name,
        description=ep.description,
        method=ep.api.method,
        path=ep.api.path,
        auth=ep.api.auth,
        timeout_seconds=ep.api.timeout_seconds,
        version=ep.version,
        module=md.module,
        tags=list(md.tags),
        owner=md.owner,
        priority=md.priority,
        preconditions=list(md.preconditions),
        success_criteria=md.success_criteria,
        business_notes=md.business_notes,
        request_fields=request_fields,
        response_fields=response_fields,
        assertable_paths=assertable,
        request_body_sample=sample,
        request_body_samples=samples,
        deep_link=f"/platform/endpoints/{ep.id}",
    )


def _classify_placeholder(value: Any) -> str:
    """把 ${env.XXX} / ${var.XXX} / 字面量分类,给平台前端做提示。"""
    if not isinstance(value, str):
        return "literal"
    if value.startswith("${env."):
        return "env_placeholder"
    if value.startswith("${var."):
        return "scenario_var_placeholder"
    if value.startswith("${auth."):
        return "auth_placeholder"
    return "literal"


def _resource_dict_for(scenario: ScenarioModel) -> dict[str, Any]:
    """resource 字段统一为 dict[str, Any](V3.1.1 提升为模块级函数)。

    由 ``PlatformScenarioExporter._resource_dict`` 与 ``render()`` 共享。
    """
    out: dict[str, Any] = {}
    for k, v in scenario.resource.items():
        if hasattr(v, "model_dump"):
            out[k] = v.model_dump(mode="json", exclude_none=True)
        else:
            out[k] = v
    return out


def _classify_var(value: Any) -> str:
    if isinstance(value, dict):
        if "kind" in value:
            return value["kind"]
    if isinstance(value, str) and value.startswith("${"):
        return "reference"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, bool):
        return "boolean"
    return "literal"


# ── ScenarioExporter(消费 Scenario 数据类) ─────────────────────────

class PlatformScenarioExporter(ScenarioExporter):
    """把 Scenario(中性数据类)翻译为 platform 渲染视图 dict。

    使用方式(向后兼容):
        scenario = Scenario.model_validate(raw_dict)
        exporter = PlatformScenarioExporter(scenario, endpoints=ALL_ENDPOINTS)
        platform_dict = exporter.to_dict()

    endpoints 可选;提供时同时附加 endpoints / navigation / config_summary 视图。

    反向(platform 落库 dict → gimbal 可执行 dict,V3.1 无 strip):
        from gimbal_plate.export.gimbal import GimbalScenarioExporter
        from gimbal_plate.schema.scenario import Scenario

        platform_dict = json.loads(平台后端落库的 JSON)
        platform_dict["kind"] = "scenario"   # 唯一需要的预处理
        scenario = Scenario.model_validate(platform_dict)
        gimbal_dict = GimbalScenarioExporter(scenario).to_dict()

    V3.1.1 继承 ``ScenarioExporter``:
        - ``consumer_id`` = "platform"
        - ``to_dict()`` / ``to_view()`` 形态不变(向后兼容)
        - ABC 契约通过 ``render()`` 满足(Step 2 dispatcher 调用入口)
        - ``capabilities`` 声明:支持 sections=("endpoints","navigation",
          "config_summary")、needs_endpoints=True
    """

    consumer_id: str = "platform"

    def __init__(
        self,
        scenario: ScenarioModel,
        *,
        endpoints: list[EndpointSpec] | None = None,
    ) -> None:
        self.scenario = scenario
        self.endpoints: list[EndpointSpec] = list(endpoints or [])
        self._ep_by_key: dict[tuple[str, str], EndpointSpec] = {
            (ep.api.method, ep.api.path): ep for ep in self.endpoints
        }

    def to_dict(self) -> dict[str, Any]:
        """整 scenario → platform 落库 dict(向后兼容入口)。"""
        view = self.to_view()
        return view.model_dump(mode="json", exclude_none=True)

    @override
    def render(
        self,
        scenario: ScenarioModel,
        *,
        endpoints: list[EndpointSpec] | None = None,
    ) -> dict[str, Any]:
        """Step 2 dispatcher 入口。

        与 ``__init__`` 不同:本方法**忽略** self.endpoints,使用调用方
        传入的 ``endpoints``,便于 dispatcher 自由切换 endpoint 集合。

        C3/C4/C7 实现:校验 scenario 是 ``ScenarioModel``;当
        ``capabilities.needs_endpoints=True`` 时校验 endpoints 元素类型;
        出口处自检返回 dict 可被 ``json.dumps`` 序列化。
        """
        self._validate_scenario(scenario)
        ep_list = self._validate_endpoints(endpoints)
        ep_by_key: dict[tuple[str, str], EndpointSpec] = {
            (ep.api.method, ep.api.path): ep for ep in ep_list
        }
        view = self.to_view(
            scenario=scenario,
            endpoints=ep_list,
            ep_by_key=ep_by_key,
        )
        out = view.model_dump(mode="json", exclude_none=True)
        return self._validate_serializable(out)

    @property
    @override
    def capabilities(self) -> ExporterCapabilities:
        """本 consumer 的能力声明(C5/C13)。

        未来 Step 2 时,``supports(request)`` 可根据 ``request.sections``
        是否为以下子集做精确判断。
        """
        return ExporterCapabilities(
            consumer=self.consumer_id,
            sections=("endpoints", "navigation", "config_summary"),
            needs_endpoints=True,
            description=(
                "把 Scenario 翻译为 platform 后端消费的渲染视图 dict;"
                "支持 endpoints / navigation / config_summary 切片"
            ),
            output_schema_kind="platform_scenario",
        )

    def to_view(
        self,
        *,
        scenario: ScenarioModel | None = None,
        endpoints: list[EndpointSpec] | None = None,
        ep_by_key: dict[tuple[str, str], EndpointSpec] | None = None,
    ) -> PlatformScenarioView:
        """整 scenario → PlatformScenarioView。

        向后兼容:无参调用时使用 ``self.scenario`` / ``self.endpoints`` /
        ``self._ep_by_key``。Step 2 ``render()`` 调用时传入显式参数,跳过
        self 状态。
        """
        sc = scenario if scenario is not None else self.scenario
        eps = endpoints if endpoints is not None else self.endpoints
        keys = ep_by_key if ep_by_key is not None else self._ep_by_key

        # 1. 按 (method, path) 聚合每个 endpoint 引用过的 step body
        bodies_by_ep: dict[str, list[dict[str, Any]]] = {}
        for s in sc.steps:
            ep = keys.get((s.api.method, s.api.path))
            if ep is None:
                continue
            body = s.request.body
            if body:
                bodies_by_ep.setdefault(ep.id, []).append(body)

        # 2. 构造 endpoint 视图
        endpoint_views = [
            _render_endpoint_view(ep, bodies_by_ep.get(ep.id, []))
            for ep in eps
        ]

        # 3. 构造 step 视图(注入 view_hints / source_kind / field_count / field_names / view_note)
        step_views: list[PlatformStepView] = []
        for s in sc.steps:
            ep = keys.get((s.api.method, s.api.path))
            api_dict = _render_api_view(s.api, ep)
            request_dict = _render_request_view(s.request, ep)
            strategy_list = _render_strategy_view(s.strategy)  # type: ignore[arg-type]
            step_views.append(PlatformStepView(
                description=s.description or "",
                api=api_dict,
                request=request_dict,
                strategy=strategy_list,
            ))

        # 4. navigation:按 service 分组
        navigation: dict[str, list[dict[str, str]]] = {}
        for ev in endpoint_views:
            navigation.setdefault(ev.service, []).append({
                "id": ev.id,
                "name": ev.name,
                "description": ev.description,
                "method": ev.method,
                "path": ev.path,
                "deep_link": ev.deep_link,
            })

        # 5. config_summary:从 scenario.config 中分类
        config_dict = sc.config.model_dump(mode="json", exclude_none=True)
        config_summary = {
            "services": [
                {"name": k, "url": v}
                for k, v in (config_dict.get("services") or {}).items()
            ],
            "users": [
                {
                    "name": k,
                    "username": v.get("username") if isinstance(v, dict) else None,
                    "password_source": _classify_placeholder(
                        v.get("password") if isinstance(v, dict) else None
                    ),
                }
                for k, v in (config_dict.get("users") or {}).items()
            ],
            "vars": [
                {"name": k, "kind": _classify_var(v), "value": v}
                for k, v in (config_dict.get("vars") or {}).items()
            ],
        }

        return PlatformScenarioView(
            kind="platform_scenario",
            scenarioId=sc.scenarioId,
            meta=sc.meta.model_dump(mode="json", exclude_none=True),
            config=config_dict,
            resource=_resource_dict_for(sc),
            steps=step_views,
            endpoints=endpoint_views,
            navigation=navigation,
            config_summary=config_summary,
        )

    def _resource_dict(self) -> dict[str, Any]:
        """resource 字段统一为 dict[str, Any]。"""
        return _resource_dict_for(self.scenario)


__all__ = [
    "PlatformStepView",
    "PlatformEndpointView",
    "PlatformScenarioView",
    "PlatformScenarioExporter",
]
