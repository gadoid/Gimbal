"""V3.1.1 抽象化:ScenarioExporter ABC 契约测试。

覆盖:
    - 两个现役 exporter 均继承自 ``ScenarioExporter``
    - ``consumer_id`` 唯一且稳定("gimbal" / "platform")
    - ``render()`` 是 ABC 契约的入口,且与 ``to_dict()`` 行为一致
    - ``capabilities`` 声明 sections / needs_endpoints
    - 基类默认 ``supports(request)`` 按 consumer 名匹配
    - 直接实例化基类会被 ABC 拦截
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from gimbal_plate.export._protocol import (
    ExporterCapabilities,
    ScenarioExporter,
)
from gimbal_plate.export.gimbal import GimbalScenarioExporter
from gimbal_plate.export.platform import PlatformScenarioExporter
from gimbal_plate.schema.scenario import Scenario as ScenarioModel


REPO = Path(__file__).resolve().parents[2]
SCENARIO_PATH = REPO / "gimbal-tmp" / "Scenario_Test_14_copy.json"


def _make_scenario() -> ScenarioModel:
    """复用 V3 export 链路已验证的 fixture,避免重新维护一份最小 Scenario。"""
    raw = json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))
    raw["meta"]["system"] = ["fin"]
    raw.setdefault("resource", {})
    raw["kind"] = "scenario"
    return ScenarioModel.model_validate(raw)


class TestScenarioExporterABC:
    """抽象基类本身的契约。"""

    def test_cannot_instantiate_abc_directly(self) -> None:
        """基类是 abstract,直接 ``ScenarioExporter()`` 必须抛 TypeError。"""
        with pytest.raises(TypeError):
            ScenarioExporter()  # type: ignore[abstract]

    def test_concrete_classes_inherit_from_abc(self) -> None:
        assert issubclass(GimbalScenarioExporter, ScenarioExporter)
        assert issubclass(PlatformScenarioExporter, ScenarioExporter)


class TestGimbalScenarioExporterContract:
    """gimbal exporter 的 ABC 实现。"""

    def test_consumer_id_is_gimbal(self) -> None:
        exporter = GimbalScenarioExporter(_make_scenario())
        assert exporter.consumer_id == "gimbal"

    def test_render_equivalent_to_to_dict(self) -> None:
        """render(scenario) 与 to_dict() 对相同输入产生相同输出。"""
        sc = _make_scenario()
        exporter = GimbalScenarioExporter(sc)
        assert exporter.render(sc) == exporter.to_dict()

    def test_render_ignores_endpoints(self) -> None:
        """gimbal consumer 不需要 endpoints,显式忽略。"""
        sc = _make_scenario()
        exporter = GimbalScenarioExporter(sc)
        # 传入 None / [] 都应得到与无参 render 等价的结果
        assert exporter.render(sc, endpoints=None) == exporter.render(sc)
        assert exporter.render(sc, endpoints=[]) == exporter.render(sc)

    def test_capabilities_declares_no_sections_no_endpoints(self) -> None:
        exporter = GimbalScenarioExporter(_make_scenario())
        caps = exporter.capabilities
        assert caps.consumer == "gimbal"
        assert caps.sections == ()
        assert caps.needs_endpoints is False

    def test_supports_self_consumer_name(self) -> None:
        exporter = GimbalScenarioExporter(_make_scenario())
        assert exporter.supports("gimbal") is True
        assert exporter.supports("platform") is False


class TestPlatformScenarioExporterContract:
    """platform exporter 的 ABC 实现。"""

    def test_consumer_id_is_platform(self) -> None:
        exporter = PlatformScenarioExporter(_make_scenario())
        assert exporter.consumer_id == "platform"

    def test_render_equivalent_to_to_dict(self) -> None:
        """render(scenario, endpoints=...) 与 to_dict() 在 endpoints 一致时等价。"""
        sc = _make_scenario()
        exporter = PlatformScenarioExporter(sc, endpoints=[])
        # to_dict() 用 self.endpoints=[],render 显式传 []
        assert exporter.render(sc, endpoints=[]) == exporter.to_dict()

    def test_render_uses_provided_endpoints_not_self(self) -> None:
        """render 应当用调用方传入的 endpoints,不依赖 self.endpoints。"""
        sc = _make_scenario()
        exporter = PlatformScenarioExporter(sc, endpoints=[])
        # render 传 None → 输出应等同于 endpoints=[]
        a = exporter.render(sc, endpoints=None)
        b = exporter.render(sc, endpoints=[])
        assert a == b

    def test_capabilities_declares_sections_and_needs_endpoints(self) -> None:
        exporter = PlatformScenarioExporter(_make_scenario())
        caps = exporter.capabilities
        assert caps.consumer == "platform"
        assert "endpoints" in caps.sections
        assert "navigation" in caps.sections
        assert "config_summary" in caps.sections
        assert caps.needs_endpoints is True

    def test_supports_self_consumer_name(self) -> None:
        exporter = PlatformScenarioExporter(_make_scenario())
        assert exporter.supports("platform") is True
        assert exporter.supports("gimbal") is False


class TestConsumerCapabilitiesDataclass:
    """ExporterCapabilities 数据类的语义。"""

    def test_default_construction(self) -> None:
        caps = ExporterCapabilities(consumer="mock")
        assert caps.consumer == "mock"
        assert caps.sections == ()
        assert caps.needs_endpoints is False
        assert caps.description == ""
        assert caps.output_schema_kind == ""

    def test_frozen_immutability(self) -> None:
        """Step 2 dispatcher 会用 caps 做 key,故必须 hashable/frozen。"""
        caps = ExporterCapabilities(consumer="mock")
        with pytest.raises(Exception):  # FrozenInstanceError 是 Exception 子类
            caps.consumer = "mutated"  # type: ignore[misc]

    def test_full_construction(self) -> None:
        """C13:description / output_schema_kind 字段可显式声明。"""
        caps = ExporterCapabilities(
            consumer="platform",
            sections=("endpoints", "navigation", "config_summary"),
            needs_endpoints=True,
            description="platform 渲染视图",
            output_schema_kind="platform_scenario",
        )
        assert caps.description == "platform 渲染视图"
        assert caps.output_schema_kind == "platform_scenario"

    def test_hashable(self) -> None:
        """C11:caps 可 hash(可作 dict key / set 元素)。"""
        a = ExporterCapabilities(consumer="mock", sections=("x",))
        b = ExporterCapabilities(consumer="mock", sections=("x",))
        assert hash(a) == hash(b)
        # 不同 caps 应当可以共存于 set
        s = {a, b, ExporterCapabilities(consumer="other")}
        assert len(s) == 2

    def test_rejects_none_description(self) -> None:
        """防止 description=None 误传(None 视作空串)。"""
        with pytest.raises(ValueError):
            ExporterCapabilities(consumer="mock", description=None)  # type: ignore[arg-type]


class TestInputValidationC3:
    """C3:render() 入参必须是 ``ScenarioModel``。"""

    def test_gimbal_rejects_non_scenario(self) -> None:
        exporter = GimbalScenarioExporter(_make_scenario())
        with pytest.raises(TypeError, match="scenario"):
            exporter.render({"kind": "scenario"})  # type: ignore[arg-type]

    def test_gimbal_rejects_none(self) -> None:
        exporter = GimbalScenarioExporter(_make_scenario())
        with pytest.raises(TypeError):
            exporter.render(None)  # type: ignore[arg-type]

    def test_platform_rejects_non_scenario(self) -> None:
        exporter = PlatformScenarioExporter(_make_scenario(), endpoints=[])
        with pytest.raises(TypeError, match="scenario"):
            exporter.render("not a scenario", endpoints=[])  # type: ignore[arg-type]


class TestEndpointValidationC7:
    """C7:render() endpoints 元素必须是 ``EndpointSpec``(当 needs_endpoints=True)。"""

    def test_platform_rejects_non_endpoint_elements(self) -> None:
        exporter = PlatformScenarioExporter(_make_scenario(), endpoints=[])
        with pytest.raises(TypeError, match="endpoints"):
            exporter.render(
                _make_scenario(),
                endpoints=[{"api": "invalid"}],  # type: ignore[list-item]
            )

    def test_platform_accepts_empty_list(self) -> None:
        sc = _make_scenario()
        exporter = PlatformScenarioExporter(sc, endpoints=[])
        # None 和 [] 都应被接受
        assert exporter.render(sc, endpoints=None) is not None
        assert exporter.render(sc, endpoints=[]) is not None


class TestOutputSerializationC4:
    """C4:render() 返回 dict 必须可被 json.dumps 序列化。"""

    def test_gimbal_output_is_serializable(self) -> None:
        sc = _make_scenario()
        out = GimbalScenarioExporter(sc).render(sc)
        import json
        # 不抛错即可
        json.dumps(out)

    def test_platform_output_is_serializable(self) -> None:
        sc = _make_scenario()
        out = PlatformScenarioExporter(sc, endpoints=[]).render(sc, endpoints=[])
        import json
        json.dumps(out)


class TestCapabilitiesMetadataC13:
    """C13:description / output_schema_kind 字段在两个现役 exporter 上都已声明。"""

    def test_gimbal_capabilities_description(self) -> None:
        caps = GimbalScenarioExporter(_make_scenario()).capabilities
        assert caps.description != ""
        assert caps.output_schema_kind == "scenario"

    def test_platform_capabilities_description(self) -> None:
        caps = PlatformScenarioExporter(_make_scenario()).capabilities
        assert caps.description != ""
        assert caps.output_schema_kind == "platform_scenario"