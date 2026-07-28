"""C2 数据驱动用例导出:EndpointSpec + 用例 → gimbal.Step / Scenario dict。

注意:
    本期不引入 ``interpolation.py`` / ``assertions.py`` 子模块。
    变量插值、断言翻译都是 exporter 的私有内部;等真有第二个用例类型复用时再拆。

输出形态:
    全部返回 dict,与 gimbal YAML 格式一致;
    调用方根据需要用 ``gimbal.schema.Step(**dict)`` / ``gimbal.schema.Scenario(**dict)`` 实例化。
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from gimbal_plate.schema.endpoint import EndpointSpec


# ── 数据驱动用例模型 ──────────────────────────────────────────────

class EndpointCase(BaseModel):
    """单个数据驱动用例。

    ``parameters`` 注入到 request body;
    ``expected`` 描述期望的响应与断言;
    ``tags`` 用于分类。
    """

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

# 期望断言 JSON 形态:
#   {"status_code": 200, "assertions": [{"target": "...", "operator": "eq", "expected": ...}]}
#
# 翻译为 gimbal 的 Assertion strategy:
#   {"kind": "assertion", "target": ..., "operator": ..., "expected": ...}

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
    """把 ``EndpointCase.expected`` 翻译为 ``gimbal.schema.Assertion`` dict 列表。"""
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
    """极简变量插值:仅处理字符串 ``${var.name}``。

    一期只支持字符串模板;非字符串按原样返回。
    """
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


# ── Exporter ──────────────────────────────────────────────

class EndpointCaseExporter:
    """把 ``EndpointSpec`` + ``EndpointCase`` / ``EndpointCaseDataset`` 翻译为 gimbal 可执行 dict。

    一期只产出 dict,不直接实例化 ``gimbal.schema.Step`` / ``gimbal.schema.Scenario`` —
    因为 ``Scenario`` 必填字段很多(meta/config),由调用方组合。
    """

    def __init__(self, endpoint: EndpointSpec, variables: dict[str, Any] | None = None) -> None:
        self.endpoint = endpoint
        self.variables = variables or {}

    def to_gimbal_step(self, case: EndpointCase) -> dict[str, Any]:
        """翻译为 ``gimbal.schema.Step`` 的 dict 形态。"""
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
        """翻译数据集为 Step dict 列表(不含 Scenario 包装)。

        返回:list[dict],每个 dict 与 ``gimbal.schema.Step`` 字段一致。
        """
        if dataset.endpoint_id != self.endpoint.id:
            raise ValueError(
                f"dataset.endpoint_id={dataset.endpoint_id!r} 与 endpoint.id="
                f"{self.endpoint.id!r} 不匹配"
            )
        # dataset 级 variables 合并到 exporter(若未设置)
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
        """翻译数据集为可被调用方组合的 Scenario 片段 dict。

        返回结构::

            {
                "scenarioId": <str>,
                "steps": [<step dict>, ...],
                "endpoint": {
                    "id": <str>,
                    "name": <str>,
                    "service": <str>,
                    "method": <str>,
                    "path": <str>,
                },
            }

        调用方负责拼装 ``Meta`` / ``Config`` 后再实例化 ``Scenario``。
        """
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
