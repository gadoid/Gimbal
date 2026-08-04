"""platform export —— 把 Scenario 数据类翻译为 platform 后端消费的渲染视图。

公开 API:
    PlatformScenarioExporter
    PlatformScenarioView
    PlatformStepView
    PlatformEndpointView

V3.1 设计(PLATE_V3_DESIGN.md §7,与 gimbal export 共享同一个 Scenario 数据类):
- 真相源是 gimbal_plate.schema.interface.Scenario(中性数据类)
- PlatformScenarioExporter 接收 Scenario,产出 platform 渲染视图 dict
- 顶层与 gimbal 对齐(kind/scenarioId/meta/config/resource/steps),
  再附加 platform 视图扩展字段(endpoints / navigation / config_summary)
- 每条 step 内层加 platform 视图扩展字段:
  - api.view_hints(endpoint_id/module/tags)
  - request.body 已用 endpoint 全量字段定义补全(直接渲染 + 直接执行)
  - request.fields_meta:{字段名 → IOFieldBinding 全量元数据}(平台前端渲染用)
  - strategy[i].view_note(人类语言摘要)
- 端到端链路:platform 落库 dict → (仅改 kind)→ Scenario.model_validate()
  → GimbalScenarioExporter.to_dict() 得到 gimbal 可执行 dict
- V3.1 删除 strip_platform_view_fields():所有平台视图字段都已在 schema 上声明,
  Scenario.model_validate 直接接受,不再需要预处理函数
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from gimbal_plate.schema.endpoint import EndpointSpec
from gimbal_plate.schema.interface.api import Api
from gimbal_plate.schema.interface.request import Request
from gimbal_plate.schema.interface.scenario import Scenario as ScenarioModel
from gimbal_plate.schema.interface.strategy import Assertion, Assign, Extract
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
      来自 EndpointSpec.responses[*].fields / assertable_fields
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


def _render_request_view(request: Request, ep: EndpointSpec | None) -> dict[str, Any]:
    """把 Request 翻译为 dict,body 全量补全 + fields_meta 携带字段元数据。

    设计(PLATE_V3_DESIGN.md §7.2 方案 C):
    - body 仍是纯 dict,key = 字段名,value = 字面量值
    - 字段值优先级:body 已填值 → endpoint default → endpoint example → None
    - 字段元数据集中放在 fields_meta:{name → IOFieldBinding 全部字段元信息}
      (path / required / default / example / description / enum / ui_kind / source_kind)
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
        for f in ep.request.fields:
            # 1) 字段元数据全量带上(让平台表单渲染有依据)
            fields_meta[f.name] = f.model_dump(mode="json", exclude_none=True)
            # 2) body 的值优先级
            if f.name in body:
                full_body[f.name] = body[f.name]
            elif f.default is not None:
                full_body[f.name] = f.default
            elif f.example is not None:
                full_body[f.name] = f.example
            else:
                full_body[f.name] = None
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
        for f in ep.request.fields:
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
        for f in spec.fields:
            response_fields.append({
                "status": status,
                "name": f.name,
                "path": _path_utils.normalize(f.path),
                "required": f.required,
                "ui_kind": f.ui_kind,
                "example": f.example,
            })
        assertable.extend(spec.assertable_fields)

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

class PlatformScenarioExporter:
    """把 Scenario(中性数据类)翻译为 platform 渲染视图 dict。

    使用方式:
        scenario = Scenario.model_validate(raw_dict)
        exporter = PlatformScenarioExporter(scenario, endpoints=ALL_ENDPOINTS)
        platform_dict = exporter.to_dict()

    endpoints 可选;提供时同时附加 endpoints / navigation / config_summary 视图。

    反向(platform 落库 dict → gimbal 可执行 dict,V3.1 无 strip):
        from gimbal_plate.export.gimbal import GimbalScenarioExporter
        from gimbal_plate.schema.interface.scenario import Scenario

        platform_dict = json.loads(平台后端落库的 JSON)
        platform_dict["kind"] = "scenario"   # 唯一需要的预处理
        scenario = Scenario.model_validate(platform_dict)
        gimbal_dict = GimbalScenarioExporter(scenario).to_dict()
    """

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
        """整 scenario → platform 落库 dict。"""
        view = self.to_view()
        return view.model_dump(mode="json", exclude_none=True)

    def to_view(self) -> PlatformScenarioView:
        """整 scenario → PlatformScenarioView。"""
        # 1. 按 (method, path) 聚合每个 endpoint 引用过的 step body
        bodies_by_ep: dict[str, list[dict[str, Any]]] = {}
        for s in self.scenario.steps:
            ep = self._ep_by_key.get((s.api.method, s.api.path))
            if ep is None:
                continue
            body = s.request.body
            if body:
                bodies_by_ep.setdefault(ep.id, []).append(body)

        # 2. 构造 endpoint 视图
        endpoint_views = [
            _render_endpoint_view(ep, bodies_by_ep.get(ep.id, []))
            for ep in self.endpoints
        ]

        # 3. 构造 step 视图(注入 view_hints / source_kind / field_count / field_names / view_note)
        step_views: list[PlatformStepView] = []
        for s in self.scenario.steps:
            ep = self._ep_by_key.get((s.api.method, s.api.path))
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
        config_dict = self.scenario.config.model_dump(mode="json", exclude_none=True)
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
            scenarioId=self.scenario.scenarioId,
            meta=self.scenario.meta.model_dump(mode="json", exclude_none=True),
            config=config_dict,
            resource=self._resource_dict(),
            steps=step_views,
            endpoints=endpoint_views,
            navigation=navigation,
            config_summary=config_summary,
        )

    def _resource_dict(self) -> dict[str, Any]:
        """resource 字段统一为 dict[str, Any]。"""
        out: dict[str, Any] = {}
        for k, v in self.scenario.resource.items():
            if hasattr(v, "model_dump"):
                out[k] = v.model_dump(mode="json", exclude_none=True)
            else:
                out[k] = v
        return out


__all__ = [
    "PlatformStepView",
    "PlatformEndpointView",
    "PlatformScenarioView",
    "PlatformScenarioExporter",
]
