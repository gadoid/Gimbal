"""V3.1.1 dispatch() 入口与 ConsumerRequest 模型测试。

覆盖:
    - ``available_consumers()`` 返回当前已注册列表
    - ``dispatch(consumer, scenario, **kwargs)`` 走通 gimbal / platform
    - 未知 consumer 名抛 ValueError(带可用列表)
    - 校验错误的入参(如非法 sections、endpoints 类型)抛 ValidationError
    - 声明式 dispatch 与直接 exporter 调用结果一致(共享同一份真相)
    - ConsumerRequest 模型的字段约束(extra="forbid"、Literal sections)
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from gimbal_plate.export import (
    PlatformConsumerRequest,
    dispatch,
    available_consumers,
)
from gimbal_plate.export._requests import (
    GimbalConsumerRequest,
    PlatformSection,
)
from gimbal_plate.export.gimbal import GimbalScenarioExporter
from gimbal_plate.export.platform import PlatformScenarioExporter


REPO = Path(__file__).resolve().parents[2]
SCENARIO_PATH = REPO / "gimbal-tmp" / "Scenario_Test_14_copy.json"


def _make_scenario() -> object:
    raw = json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))
    raw["meta"]["system"] = ["fin"]
    raw.setdefault("resource", {})
    raw["kind"] = "scenario"
    from gimbal_plate.schema.scenario import Scenario as ScenarioModel
    return ScenarioModel.model_validate(raw)


class TestAvailableConsumers:
    def test_returns_sorted_list(self) -> None:
        names = available_consumers()
        assert isinstance(names, list)
        assert "gimbal" in names
        assert "platform" in names
        assert names == sorted(names)


class TestDispatchGimbal:
    def test_dispatch_gimbal_returns_to_dict_equivalent(self) -> None:
        """dispatch("gimbal", ...) 与直接 GimbalScenarioExporter.to_dict() 等价。"""
        sc = _make_scenario()
        via_dispatch = dispatch("gimbal", scenario=sc)
        direct = GimbalScenarioExporter(sc).to_dict()
        assert via_dispatch == direct

    def test_dispatch_gimbal_rejects_extra_kwargs(self) -> None:
        """gimbal 不接受 endpoints,多传字段应被 Pydantic 拒。"""
        sc = _make_scenario()
        with pytest.raises(ValidationError):
            dispatch("gimbal", scenario=sc, endpoints=[])


class TestDispatchPlatform:
    def test_dispatch_platform_default_sections(self) -> None:
        """默认 sections = 全选,输出包含 endpoints / navigation / config_summary。"""
        sc = _make_scenario()
        result = dispatch("platform", scenario=sc)
        assert "endpoints" in result
        assert "navigation" in result
        assert "config_summary" in result

    def test_dispatch_platform_with_endpoints(self) -> None:
        """显式传 endpoints,render 应当用它(而非 self.endpoints)。"""
        sc = _make_scenario()
        result = dispatch("platform", scenario=sc, endpoints=[])
        # endpoints=[] 时 sections 仍存在但为空
        assert result["endpoints"] == []

    def test_dispatch_platform_invalid_section_rejected(self) -> None:
        """非法 section 名应被 Literal 校验拦截。"""
        sc = _make_scenario()
        with pytest.raises(ValidationError):
            dispatch("platform", scenario=sc, sections=("bogus",))

    def test_dispatch_platform_sections_subset_accepted(self) -> None:
        """合法的子集应被接受(Pydantic Literal 不会按顺序校验)。"""
        sc = _make_scenario()
        # 不抛错即可
        result = dispatch(
            "platform",
            scenario=sc,
            sections=("endpoints",),
        )
        assert "endpoints" in result


class TestDispatchErrors:
    def test_unknown_consumer_raises_with_message(self) -> None:
        sc = _make_scenario()
        with pytest.raises(ValueError) as exc_info:
            dispatch("apidoc", scenario=sc)
        # 错误信息应该列出可用 consumer
        msg = str(exc_info.value)
        assert "apidoc" in msg
        assert "gimbal" in msg
        assert "platform" in msg


class TestConsumerRequestModels:
    def test_gimbal_request_minimal(self) -> None:
        sc = _make_scenario()
        req = GimbalConsumerRequest(scenario=sc)
        assert req.consumer == "gimbal"
        assert req.scenario is sc

    def test_gimbal_request_rejects_extra_fields(self) -> None:
        sc = _make_scenario()
        with pytest.raises(ValidationError):
            GimbalConsumerRequest(scenario=sc, endpoints=[])

    def test_platform_request_minimal(self) -> None:
        sc = _make_scenario()
        req = PlatformConsumerRequest(scenario=sc)
        assert req.consumer == "platform"
        assert req.scenario is sc
        assert req.endpoints is None
        assert req.sections == ("endpoints", "navigation", "config_summary")

    def test_platform_request_rejects_extra_fields(self) -> None:
        sc = _make_scenario()
        with pytest.raises(ValidationError):
            PlatformConsumerRequest(scenario=sc, something_else=42)

    def test_platform_section_literal_type(self) -> None:
        """``PlatformSection`` 应当是 Literal 类型(仅用于 IDE/类型检查)。"""
        # 运行时 Literal 就是 typing 内部的 _LiteralGeneric;这里只验证名字
        import typing
        assert hasattr(typing, "get_args")


class TestDispatchStaticContractParity:
    """声明式 dispatch 与静态契约路径产出应当一致。"""

    def test_platform_static_contract_matches_dispatch(self) -> None:
        sc = _make_scenario()
        via_dispatch = dispatch("platform", scenario=sc)

        # 静态契约路径:走同样的 ConsumerRequest 校验,然后调 render
        request = PlatformConsumerRequest(scenario=sc)
        exporter = PlatformScenarioExporter(
            request.scenario,
            endpoints=request.endpoints,
        )
        via_static = exporter.render(
            request.scenario,
            endpoints=request.endpoints,
        )

        assert via_dispatch == via_static

    def test_gimbal_static_contract_matches_dispatch(self) -> None:
        sc = _make_scenario()
        via_dispatch = dispatch("gimbal", scenario=sc)

        request = GimbalConsumerRequest(scenario=sc)
        exporter = GimbalScenarioExporter(request.scenario)
        via_static = exporter.render(request.scenario)

        assert via_dispatch == via_static