"""gimbal export —— 把 Scenario 数据类翻译为 gimbal 可执行 dict。

公开 API:
    GimbalScenarioExporter
    EndpointCase
    EndpointCaseDataset
    EndpointCaseExporter           (单 endpoint 翻译器,被 ScenarioExporter 调用)

V3.1 设计(PLATE_V3_DESIGN.md §7):
- 真相源是 gimbal_plate.schema.Scenario(中性数据类)
- GimbalScenarioExporter 接收 Scenario,产出 gimbal 可执行 dict
- 通过 model_dump(exclude=...) 过滤掉平台视图扩展字段(endpoints/navigation/
  config_summary/api.view_hints/request.fields_meta/strategy[*].view_note)
- 端到端链路:platform 落库 dict → Scenario.model_validate(仅改 kind) →
  GimbalScenarioExporter.to_dict() → gimbal 可执行 dict(无需任何预处理)
- EndpointCaseExporter 仍可独立使用(供单 endpoint 维度的精细控制)
- 与 export/platform.py 共享同一个 Scenario 实例

V3.1.1 抽象化(V3.1.1):继承 ``gimbal_plate.export._protocol.ScenarioExporter``,
获得统一 consumer_id / to_dict 契约 + Step 2 声明式 dispatch 的预留能力。
"""
from __future__ import annotations

from typing import Any, override

from pydantic import BaseModel, ConfigDict, Field

from gimbal_plate.export._protocol import ExporterCapabilities, ScenarioExporter
from gimbal_plate.schema.endpoint import EndpointSpec
from gimbal_plate.schema.scenario import Scenario as ScenarioModel


# ── 数据驱动用例模型 ──────────────────────────────────────────────

class EndpointCase(BaseModel):
    """单个数据驱动用例。"""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)
    expected: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)


class EndpointCaseDataset(BaseModel):
    """一个接口下的所有数据驱动用例。"""

    model_config = ConfigDict(extra="forbid")

    endpoint_id: str
    cases: list[EndpointCase] = Field(default_factory=list)
    variables: dict[str, Any] = Field(default_factory=dict)


# ── 断言翻译(私有) ──────────────────────────────────────────────

_OPERATOR_MAP = {
    "eq": "eq",
    "ne": "ne",
    "gt": "gt",
    "gte": "gte",
    "lt": "lt",
    "lte": "lte",
    "in": "in",
    "not_in": "not_in",
    "contains": "contains",
    "not_contains": "not_contains",
    "exists": "exists",
    "empty": "empty",
    "length_eq": "length_eq",
    "schema": "schema",
}


def _translate_assertions(expected: dict[str, Any]) -> list[dict[str, Any]]:
    """把 EndpointCase.expected 翻译为 gimbal.schema.Assertion dict 列表。"""
    out: list[dict[str, Any]] = []
    for raw in expected.get("assertions", []):
        op = raw.get("operator", "eq")
        if op not in _OPERATOR_MAP:
            raise ValueError(f"不支持的断言 operator: {op!r}")
        out.append(
            {
                "kind": "assertion",
                "target": raw["target"],
                "operator": op,
                "expected": raw.get("expected"),
                "soft": bool(raw.get("soft", False)),
            }
        )
    return out


def _render_status_check(expected: dict[str, Any]) -> dict[str, Any] | None:
    """生成一个对 response.status 的等值断言(若声明了 status_code)。"""
    status = expected.get("status_code")
    if status is None:
        return None
    return {
        "kind": "assertion",
        "target": "response.status",
        "operator": "eq",
        "expected": int(status),
        "soft": False,
    }


def _interpolate(value: Any, variables: dict[str, Any]) -> Any:
    """极简变量插值:仅处理字符串 ${var.name}。"""
    if not isinstance(value, str):
        return value
    if "${" not in value:
        return value
    out = value
    for k, v in variables.items():
        out = out.replace("${" + k + "}", str(v))
    return out


def _interpolate_params(
    params: dict[str, Any],
    variables: dict[str, Any],
) -> dict[str, Any]:
    return {k: _interpolate(v, variables) for k, v in params.items()}


# ── EndpointCaseExporter(单 endpoint 翻译器,保留旧 API) ──────────────

class EndpointCaseExporter:
    """把 EndpointSpec + EndpointCase / EndpointCaseDataset 翻译为 gimbal 可执行 dict。

    适用于单 endpoint 维度的精细翻译。整 scenario 维度的翻译请用
    GimbalScenarioExporter。
    """

    def __init__(self, endpoint: EndpointSpec, variables: dict[str, Any] | None = None) -> None:
        self.endpoint = endpoint
        self.variables = variables or {}

    def to_gimbal_step(self, case: EndpointCase) -> dict[str, Any]:
        """翻译为 gimbal.schema.Step 的 dict 形态。"""
        body = self._render_body(case.parameters)
        api_dict = self._render_api(case)
        strategy = self._render_strategy(case.expected)
        return {
            "kind": "step",
            "description": case.description or case.name,
            "api": api_dict,
            "request": {"kind": "request", "body": body},
            "strategy": strategy,
        }

    def to_gimbal_scenario_steps(self, dataset: EndpointCaseDataset) -> list[dict[str, Any]]:
        """翻译数据集为 Step dict 列表(不含 Scenario 包装)。"""
        if dataset.endpoint_id != self.endpoint.id:
            raise ValueError(
                f"dataset.endpoint_id={dataset.endpoint_id!r} 与 endpoint.id="
                f"{self.endpoint.id!r} 不匹配"
            )
        merged_vars = {**self.variables, **dataset.variables}
        old = self.variables
        try:
            self.variables = merged_vars
            return [self.to_gimbal_step(c) for c in dataset.cases]
        finally:
            self.variables = old

    def to_gimbal_scenario_dict(
        self,
        dataset: EndpointCaseDataset,
        *,
        scenario_id: str | None = None,
    ) -> dict[str, Any]:
        """翻译数据集为可被调用方组合的 Scenario 片段 dict。"""
        steps = self.to_gimbal_scenario_steps(dataset)
        return {
            "scenarioId": scenario_id or f"sc_{dataset.endpoint_id}",
            "steps": steps,
            "endpoint": {
                "id": self.endpoint.id,
                "name": self.endpoint.name,
                "service": self.endpoint.api.service,
                "method": self.endpoint.api.method,
                "path": self.endpoint.api.path,
            },
        }

    # ── 内部 ──────────────────────────────────────────────
    def _render_body(self, params: dict[str, Any]) -> Any:
        interpolated = _interpolate_params(params, self.variables)
        if self.endpoint.request is None:
            return interpolated
        return self.endpoint.request.validate_body(interpolated)

    def _render_api(self, case: EndpointCase) -> dict[str, Any]:
        api = self.endpoint.api
        return {
            "kind": "api",
            "service": api.service,
            "method": api.method,
            "path": api.path,
            "headers": dict(api.headers),
            "timeout": api.timeout_seconds,
        }

    def _render_strategy(self, expected: dict[str, Any]) -> list[dict[str, Any]]:
        status_check = _render_status_check(expected)
        assertions = _translate_assertions(expected)
        return ([status_check] if status_check else []) + assertions


# ── ScenarioExporter(消费 Scenario 数据类) ─────────────────────────

class GimbalScenarioExporter(ScenarioExporter):
    """把 Scenario(中性数据类)翻译为 gimbal 可执行 dict。

    使用方式(向后兼容):
        scenario = Scenario.model_validate(raw_dict)
        exporter = GimbalScenarioExporter(scenario)
        gimbal_dict = exporter.to_dict()

    V3.1.1 继承 ``ScenarioExporter``:
        - ``consumer_id`` = "gimbal"
        - ``to_dict()`` 形态不变(向后兼容)
        - ABC 契约通过 ``render()`` 满足(Step 2 dispatcher 调用入口)
        - ``capabilities`` 声明:无 sections、needs_endpoints=False
    """

    consumer_id: str = "gimbal"

    def __init__(self, scenario: ScenarioModel) -> None:
        self.scenario = scenario

    def to_dict(self) -> dict[str, Any]:
        """整 scenario → gimbal 可执行 dict(向后兼容入口)。

        通过 model_dump(exclude=...) 过滤掉平台视图扩展字段
        (PLATE_V3_DESIGN.md §7.3.2):
        - Scenario 顶层: endpoints / navigation / config_summary
        - steps[*].api: view_hints
        - steps[*].request: fields_meta
        - steps[*].strategy[*]: view_note
        """
        return self.render(self.scenario, endpoints=None)

    @override
    def render(
        self,
        scenario: ScenarioModel,
        *,
        endpoints: list[EndpointSpec] | None = None,
    ) -> dict[str, Any]:
        """Step 2 dispatcher 入口。

        本 consumer 不需要 endpoints(显式忽略,便于统一 dispatcher 调用)。

        C3/C4 实现:入口处校验 scenario 是 ``ScenarioModel``,
        出口处自检返回 dict 可被 ``json.dumps`` 序列化。
        """
        self._validate_scenario(scenario)
        # exclude 嵌套结构:Pydantic v2 接受 set 或 dict。
        # set 字面量不能与 dict 字面量混用,所以全部用 dict 表达。
        # 顶层 3 个字段用 {"name": True} 的形式(Pydantic 把 value 当 bool/None,
        # 仍视为排除字段),嵌套层用 dict-of-dict。
        exclude: dict[str, Any] = {
            "endpoints": True,
            "navigation": True,
            "config_summary": True,
            "steps": {
                "__all__": {
                    "api": {"view_hints": True},
                    "request": {"fields_meta": True},
                    "strategy": {"__all__": {"view_note": True}},
                }
            },
        }
        out = scenario.model_dump(
            mode="json", exclude_none=True, exclude=exclude
        )
        return self._validate_serializable(out)

    @property
    @override
    def capabilities(self) -> ExporterCapabilities:
        """本 consumer 的能力声明(C5/C13)。"""
        return ExporterCapabilities(
            consumer=self.consumer_id,
            sections=(),
            needs_endpoints=False,
            description=(
                "把 Scenario 翻译为 gimbal 引擎可执行 dict,丢弃平台视图扩展字段"
            ),
            output_schema_kind="scenario",
        )


__all__ = [
    "EndpointCase",
    "EndpointCaseDataset",
    "EndpointCaseExporter",
    "GimbalScenarioExporter",
]
