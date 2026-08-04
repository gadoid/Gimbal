"""V3 阶段 4:export/gimbal.py 与 case/exporter 等价,to_gimbal_step 翻译正确,旧路径仍可用。

新增 GimbalScenarioExporter 测试,验证 Scenario 数据类 → gimbal 可执行 dict 的链路。
"""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from gimbal_plate.case.exporter import (
    EndpointCase as LegacyCase,
)
from gimbal_plate.case.exporter import (
    EndpointCaseDataset as LegacyDataset,
)
from gimbal_plate.case.exporter import (
    EndpointCaseExporter as LegacyExporter,
)
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
from gimbal_plate.schema.interface.scenario import Scenario as ScenarioModel


REPO = Path(__file__).resolve().parents[2]
SCENARIO_PATH = REPO / "gimbal-tmp" / "Scenario_Test_14_copy.json"


def _load_scenario() -> ScenarioModel:
    raw = json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))
    raw["meta"]["system"] = "fin"
    raw.setdefault("resource", {})
    raw["kind"] = "scenario"
    return ScenarioModel.model_validate(raw)


class _InBody(BaseModel):
    order_id: str


class _OutBody(BaseModel):
    order_id: str
    status: str


class TestDualPathImport:
    """export/gimbal 与 case/exporter 必须指向同一类对象。"""

    def test_endpoint_case_exporter_is_same_class(self) -> None:
        assert EndpointCaseExporter is LegacyExporter

    def test_endpoint_case_is_same_class(self) -> None:
        assert EndpointCase is LegacyCase

    def test_endpoint_case_dataset_is_same_class(self) -> None:
        assert EndpointCaseDataset is LegacyDataset


class TestExportGimbalFunctional:
    """export.gimbal.EndpointCaseExporter 的核心方法正确翻译为 gimbal dict。"""

    def _endpoint(self) -> EndpointSpec:
        return EndpointSpec(
            id="fin.settlement.create_order",
            system="fin",
            service="settlement",
            name="创建结算单",
            api=ApiSpec(service="settlement", method="POST", path="/api/v1/fin/settlement/orders"),
            request=RequestSpec(body_type="json", model=_InBody),
            responses={200: ResponseSpec(status=200, model=_OutBody)},
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
        import pytest

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


class TestLegacyPathStillWorks:
    """case/exporter 旧路径仍能工作(向后兼容)。"""

    def test_legacy_import_returns_same_object(self) -> None:
        assert LegacyExporter is EndpointCaseExporter

    def test_legacy_to_gimbal_step(self) -> None:
        endpoint = EndpointSpec(
            id="legacy.id",
            system="legacy",
            service="legacy",
            name="legacy test",
            api=ApiSpec(service="legacy", method="GET", path="/legacy"),
            responses={200: ResponseSpec(status=200)},
        )
        exporter = LegacyExporter(endpoint=endpoint)
        case = LegacyCase(name="c1")
        step = exporter.to_gimbal_step(case)
        assert step["kind"] == "step"


class TestGimbalScenarioExporter:
    """基于 Scenario 数据类的 gimbal export。"""

    def test_constructible(self) -> None:
        sc = _load_scenario()
        exporter = GimbalScenarioExporter(sc)
        assert exporter.scenario is sc

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
        assert d["meta"]["system"] == "fin"


class TestPlatformScenarioExporterSharedScenario:
    """验证 platform 与 gimbal exporter 共享同一份 Scenario 实例。

    这是用户要求的核心:一个 Scenario 数据类,两个 exporter 出口。
    """

    def test_two_exporters_share_same_scenario(self) -> None:
        from gimbal_plate.export.platform import PlatformScenarioExporter

        sc = _load_scenario()
        gimbal_exp = GimbalScenarioExporter(sc)
        platform_exp = PlatformScenarioExporter(sc, endpoints=ALL_ENDPOINTS)
        assert gimbal_exp.scenario is platform_exp.scenario

    def test_gimbal_and_platform_share_data_class(self) -> None:
        from gimbal_plate.export.platform import PlatformScenarioExporter

        sc = _load_scenario()
        gimbal_dict = GimbalScenarioExporter(sc).to_dict()
        platform_dict = PlatformScenarioExporter(sc, endpoints=ALL_ENDPOINTS).to_dict()

        # 同一个 ScenarioId
        assert gimbal_dict["scenarioId"] == platform_dict["scenarioId"]
        # 同一个 meta.name
        assert gimbal_dict["meta"]["name"] == platform_dict["meta"]["name"]
        # 同 step 数
        assert len(gimbal_dict["steps"]) == len(platform_dict["steps"])
        # 每条 step.method/path 必一致
        for gs, ps in zip(gimbal_dict["steps"], platform_dict["steps"]):
            assert gs["api"]["method"] == ps["api"]["method"]
            assert gs["api"]["path"] == ps["api"]["path"]


from gimbal_plate.systems.fin.endpoint import ALL_ENDPOINTS  # noqa: E402
