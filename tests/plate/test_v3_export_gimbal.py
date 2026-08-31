"""V3 阶段 4:export/gimbal.py 翻译链路,to_gimbal_step / Scenario → gimbal dict。

- TestExportGimbalFunctional:EndpointCase 数据 → gimbal step dict 的翻译链路。
- TestGimbalScenarioExporter:Scenario 数据类 → gimbal 可执行 dict 的链路。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import BaseModel

from gimbal_plate.export.gimbal import (
    EndpointCase,
    EndpointCaseDataset,
    EndpointCaseExporter,
    GimbalScenarioExporter,
)
from gimbal_plate.schema.endpoint import (
    ApiSpec,
    EndpointSpec,
    RequestSpec,
    ResponseSpec,
)
from gimbal_plate.schema.scenario import Scenario as ScenarioModel


REPO = Path(__file__).resolve().parents[2]
SCENARIO_PATH = REPO / "gimbal-tmp" / "Scenario_Test_14_copy.json"


def _load_scenario() -> ScenarioModel:
    raw = json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))
    raw["meta"]["system"] = ["fin"]
    raw.setdefault("resource", {})
    raw["kind"] = "scenario"
    return ScenarioModel.model_validate(raw)


class _InBody(BaseModel):
    order_id: str


class _OutBody(BaseModel):
    order_id: str
    status: str


class TestExportGimbalFunctional:
    """export.gimbal.EndpointCaseExporter 的核心方法正确翻译为 gimbal dict。"""

    def _endpoint(self) -> EndpointSpec:
        return EndpointSpec(
            id="fin.settlement.create_order",
            system="fin",
            service="settlement",
            name="创建结算单",
            api=ApiSpec(service="settlement", method="POST", path="/api/v1/fin/settlement/orders"),
            request=RequestSpec(body_type="json", schema_=_InBody.model_json_schema()),
            responses={200: ResponseSpec(status=200, schema_=_OutBody.model_json_schema())},
            version="1.0.0",
        )

    def test_to_gimbal_step_returns_compatible_dict(self) -> None:
        endpoint = self._endpoint()
        exporter = EndpointCaseExporter(endpoint=endpoint)
        case = EndpointCase(
            name="case-1",
            description="first case",
            parameters={"order_id": "o-1"},
            expected={
                "status_code": 200,
                "assertions": [
                    {"target": "order_id", "operator": "eq", "expected": "o-1"},
                ],
            },
        )
        step = exporter.to_gimbal_step(case)
        assert step["kind"] == "step"
        assert step["description"] == "first case"
        assert step["api"]["service"] == "settlement"
        assert step["api"]["method"] == "POST"
        assert step["request"]["kind"] == "request"
        # request body 应当经过 validate_body 链路(因为 _InBody 有 model)
        assert step["request"]["body"]["order_id"] == "o-1"
        # strategy 应包含 status check + 1 个 assertion
        assert len(step["strategy"]) == 2
        assert any(s["target"] == "response.status" for s in step["strategy"])

    def test_to_gimbal_scenario_steps_matches_dataset_endpoint_id(self) -> None:
        endpoint = self._endpoint()
        exporter = EndpointCaseExporter(endpoint=endpoint)
        dataset = EndpointCaseDataset(
            endpoint_id="fin.settlement.create_order",
            cases=[
                EndpointCase(name="c1", parameters={"order_id": "x"}),
                EndpointCase(name="c2", parameters={"order_id": "y"}),
            ],
        )
        steps = exporter.to_gimbal_scenario_steps(dataset)
        assert len(steps) == 2
        assert steps[0]["description"] == "c1"
        assert steps[1]["description"] == "c2"

    def test_dataset_endpoint_id_mismatch_raises(self) -> None:
        endpoint = self._endpoint()
        exporter = EndpointCaseExporter(endpoint=endpoint)
        dataset = EndpointCaseDataset(
            endpoint_id="different.id",
            cases=[EndpointCase(name="c1", parameters={"order_id": "x"})],
        )
        with pytest.raises(ValueError, match="不匹配"):
            exporter.to_gimbal_scenario_steps(dataset)

    def test_to_gimbal_scenario_dict_shape(self) -> None:
        endpoint = self._endpoint()
        exporter = EndpointCaseExporter(endpoint=endpoint)
        dataset = EndpointCaseDataset(
            endpoint_id="fin.settlement.create_order",
            cases=[EndpointCase(name="c1", parameters={"order_id": "x"})],
        )
        scenario_dict = exporter.to_gimbal_scenario_dict(dataset, scenario_id="sc_test")
        assert scenario_dict["scenarioId"] == "sc_test"
        assert scenario_dict["endpoint"]["id"] == "fin.settlement.create_order"
        assert scenario_dict["endpoint"]["path"] == "/api/v1/fin/settlement/orders"
        assert len(scenario_dict["steps"]) == 1

    def test_variable_interpolation_in_parameters(self) -> None:
        endpoint = self._endpoint()
        exporter = EndpointCaseExporter(endpoint=endpoint, variables={"oid": "interpolated"})
        case = EndpointCase(name="c1", parameters={"order_id": "${oid}"})
        step = exporter.to_gimbal_step(case)
        assert step["request"]["body"]["order_id"] == "interpolated"


class TestGimbalScenarioExporter:
    """基于 Scenario 数据类的 gimbal export。"""

    def test_scenario_attribute_is_exposed(self) -> None:
        sc = _load_scenario()
        exporter = GimbalScenarioExporter(sc)
        assert exporter.scenario is sc
        # 构造后可直接调用 to_dict;若 Scenario 字段缺失会在此处爆炸
        d = exporter.to_dict()
        assert d["scenarioId"] == sc.scenarioId

    def test_to_dict_top_shape(self) -> None:
        sc = _load_scenario()
        d = GimbalScenarioExporter(sc).to_dict()
        assert set(d.keys()) == {"kind", "scenarioId", "meta", "config", "resource", "steps"}
        assert d["kind"] == "scenario"
        assert d["scenarioId"] == sc.scenarioId

    def test_steps_count(self) -> None:
        sc = _load_scenario()
        d = GimbalScenarioExporter(sc).to_dict()
        assert len(d["steps"]) == 36

    def test_step_api_passthrough(self) -> None:
        sc = _load_scenario()
        d = GimbalScenarioExporter(sc).to_dict()
        s0 = d["steps"][0]
        assert s0["api"]["method"] == "POST"
        assert s0["api"]["path"] == "/api/order/orderEntrust/orderAdd"
        assert "Authorization" in s0["api"]["headers"]

    def test_request_body_passthrough(self) -> None:
        sc = _load_scenario()
        d = GimbalScenarioExporter(sc).to_dict()
        s0 = d["steps"][0]
        assert s0["request"]["body"]["bl_no"] == "${var.bl_no}"

    def test_strategy_kinds(self) -> None:
        sc = _load_scenario()
        d = GimbalScenarioExporter(sc).to_dict()
        all_kinds: list[str] = []
        for s in d["steps"]:
            all_kinds.extend(st["kind"] for st in s["strategy"])
        assert sorted(all_kinds).count("assertion") == 36
        assert sorted(all_kinds).count("assign") == 52
        assert sorted(all_kinds).count("extract") == 26

    def test_meta_contains_system(self) -> None:
        sc = _load_scenario()
        d = GimbalScenarioExporter(sc).to_dict()
        assert d["meta"]["system"] == ["fin"]
