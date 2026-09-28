"""协议中立化 — 协议注册表 / Step 归一化 / 插件注册通道 单元测试。

覆盖：
  - ProtocolRegistry：register/resolve/unregister_plugin + dispatcher kind 联动
  - build_default_dispatcher：http 第一员、kind="_call"、四策略齐备
  - PluginContext.register_protocol / register_strategy + 卸载清理
  - Step schema：api 糖归一化、恰好其一校验、dump/round-trip、显式 call
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from gimbal.context.views import StrategyContextView  # noqa: F401 (协议检查用)
from gimbal.core.hooks import HookRegistry
from gimbal.events.bus import InMemoryEventBus
from gimbal.plugins.loader import PluginLoader
from gimbal.protocols.base import ProtocolCallContext, ProtocolExecutor
from gimbal.protocols.registry import ProtocolRegistry, build_default_protocol_registry
from gimbal.schema.call import Call
from gimbal.schema.call import Call
from gimbal.schema.request import Request
from gimbal.schema.step import Step
from gimbal.strategy.builtin.call import CallExecutor
from gimbal.strategy.dispatcher import build_default_dispatcher
from gimbal.strategy.executor_base import StrategyResult, StrategyStatus
from gimbal.core.plugin import Plugin, PluginContext, PluginManifest


# ── 测试用自定义协议 ─────────────────────────────────────────

class EchoProtocolExecutor(ProtocolExecutor):
    """测试协议（v2.1 批次 A 契约样板）：仅实现 build_spec + send。"""

    protocol = "echo"

    def build_spec(self, call, pctx: ProtocolCallContext):
        return EchoSpec(message=getattr(call, "message", ""), pctx=pctx)

    def send(self, spec, view):
        from gimbal.protocols.result import CallResult
        return CallResult.build(
            protocol=self.protocol,
            request={"message": spec.message},
            status=0,
            body={"echo": spec.message},
        )


import dataclasses
from dataclasses import dataclass, field
from typing import Any, Optional, Union


@dataclass
class EchoSpec:
    kind: str = "_call:echo"
    message: str = ""
    name: Optional[str] = "echo_call"
    phase: Optional[str] = None
    order: int = 0
    enabled: bool = True
    onFailure: str = "abort"
    tags: list = dataclasses.field(default_factory=list)
    pctx: Optional[ProtocolCallContext] = None


# ── ProtocolRegistry ──────────────────────────────────────────

class TestProtocolRegistry:

    def test_default_registry_has_http(self):
        reg = build_default_protocol_registry()
        assert "http" in reg.protocols()
        assert isinstance(reg.resolve("http"), CallExecutor)

    def test_dispatcher_integration_default(self):
        d = build_default_dispatcher(hook_registry=HookRegistry())
        # http 经注册表联动进 dispatcher，kind 沿用历史值 "_call"
        assert "_call" in d.kinds()
        assert "extract" in d.kinds() and "assign" in d.kinds() and "assertion" in d.kinds()
        assert d.protocols is not None and "http" in d.protocols.protocols()

    def test_register_custom_protocol_links_dispatcher(self):
        d = build_default_dispatcher(hook_registry=HookRegistry())
        reg = d.protocols
        reg.register(EchoProtocolExecutor())
        assert "echo" in reg.protocols()
        assert "_call:echo" in d.kinds()   # kind 默认 _call:{protocol}
        assert isinstance(reg.resolve("echo"), EchoProtocolExecutor)

    def test_unregister_plugin_removes_both_tables(self):
        d = build_default_dispatcher(hook_registry=HookRegistry())
        reg = d.protocols
        reg.register(EchoProtocolExecutor(), plugin_name="my-proto-plugin")
        assert "echo" in reg.protocols()

        removed = reg.unregister_plugin("my-proto-plugin")
        assert removed == 1
        assert "echo" not in reg.protocols()
        assert "_call:echo" not in d.kinds()

    def test_register_rejects_non_protocol_executor(self):
        reg = build_default_protocol_registry()
        class NotAProtocol:
            kind = "x"
        try:
            reg.register(NotAProtocol())  # type: ignore[arg-type]
            raise AssertionError("应当 TypeError")
        except TypeError:
            pass

    def test_resolve_unknown_returns_none(self):
        reg = build_default_protocol_registry()
        assert reg.resolve("grpc") is None
        assert "grpc" not in reg


# ── S-1: 参数 schema 收敛入注册表 ────────────────────────────


class TestParamsConvergence:
    """S-1: strategy/protocol 参数模型入注册表;Call 编译期协议字段校验。"""

    def test_http_params_schema_registered(self):
        reg = build_default_protocol_registry()
        params = reg.params_of("http")
        assert params is not None
        for f in ("service", "method", "path", "headers", "timeout", "user"):
            assert f in params.model_fields, f

    def test_params_of_unknown_protocol_is_none(self):
        reg = build_default_protocol_registry()
        assert reg.params_of("grpc") is None

    def test_strategy_params_from_registry(self):
        """dispatcher 注册面携带参数模型 —— ext 不再依赖硬编码 dotted 映射。"""
        d = build_default_dispatcher(hook_registry=HookRegistry())
        expect = {"extract": "target", "assign": "source", "assertion": "operator"}
        for kind, field in expect.items():
            params = d.params_of(kind)
            assert params is not None, kind
            assert field in params.model_fields, kind

    def test_call_unknown_protocol_field_rejected(self):
        from datetime import datetime, timezone

        from gimbal.compiler.pipeline import CompileError, compile_target
        from gimbal.schema.scenario import Config as ScenarioConfig, Meta, Scenario

        scenario = Scenario(
            scenarioId="bad-call",
            meta=Meta(name="n", description="d", module="m", priority=1, author="a",
                      owner="o", tags=[], version="1.0",
                      createTime=datetime.now(timezone.utc), expire=False,
                      requirementRef=[]),
            config=ScenarioConfig(),
            resource={},
            steps=[Step(call=Call(protocol="http", service="s", method="GET",
                                  path="/x", bogus=1), strategy=[])],
        )
        with pytest.raises(CompileError, match="bogus|未知字段|Extra inputs"):
            compile_target(scenario)

    def test_call_unknown_protocol_rejected(self):
        """显式传入注册表（Engine 路径）= 严格模式：未注册协议编译期报错。"""
        from datetime import datetime, timezone

        from gimbal.compiler.pipeline import CompileError, compile_target
        from gimbal.schema.scenario import Config as ScenarioConfig, Meta, Scenario

        scenario = Scenario(
            scenarioId="bad-proto",
            meta=Meta(name="n", description="d", module="m", priority=1, author="a",
                      owner="o", tags=[], version="1.0",
                      createTime=datetime.now(timezone.utc), expire=False,
                      requirementRef=[]),
            config=ScenarioConfig(),
            resource={},
            steps=[Step(call=Call(protocol="nope", x=1), strategy=[])],
        )
        with pytest.raises(CompileError, match="未注册的协议|nope"):
            compile_target(scenario, protocols=build_default_protocol_registry())

    def test_call_unknown_protocol_lenient_without_explicit_registry(self):
        """缺省注册表（库直调/无 bootstrap CLI）只校验已知协议,容忍插件协议。"""
        from datetime import datetime, timezone

        from gimbal.compiler.pipeline import compile_target
        from gimbal.schema.scenario import Config as ScenarioConfig, Meta, Scenario

        scenario = Scenario(
            scenarioId="plugin-proto",
            meta=Meta(name="n", description="d", module="m", priority=1, author="a",
                      owner="o", tags=[], version="1.0",
                      createTime=datetime.now(timezone.utc), expire=False,
                      requirementRef=[]),
            config=ScenarioConfig(),
            resource={},
            steps=[Step(call=Call(protocol="echo", message="hi"), strategy=[])],
        )
        plan = compile_target(scenario)   # echo 不在内置表,不报错;运行期收口
        assert plan.units[0].scenario.scenarioId == "plugin-proto"

    def test_call_valid_http_fields_pass(self):
        from datetime import datetime, timezone

        from gimbal.compiler.pipeline import compile_target
        from gimbal.schema.scenario import Config as ScenarioConfig, Meta, Scenario

        scenario = Scenario(
            scenarioId="ok-call",
            meta=Meta(name="n", description="d", module="m", priority=1, author="a",
                      owner="o", tags=[], version="1.0",
                      createTime=datetime.now(timezone.utc), expire=False,
                      requirementRef=[]),
            config=ScenarioConfig(),
            resource={},
            steps=[Step(call=Call(protocol="http", service="s", method="POST",
                                  path="/x", headers={"A": "b"}, timeout=5.0,
                                  user="codfish"), strategy=[])],
        )
        plan = compile_target(scenario)
        assert plan.units and plan.units[0].scenario.scenarioId == "ok-call"


# ── PluginContext 注册通道 ───────────────────────────────────

class _StrategyProbe:
    kind = "probe_strategy"

    def execute(self, spec, view):
        return StrategyResult(status=StrategyStatus.PASSED, message="probe")


class _ProtocolPlugin(Plugin):
    """真实插件：on_activate 里注册协议 + 策略。"""

    def __init__(self):
        super().__init__()
        self.manifest = PluginManifest(
            name="proto-plugin", version="0.1.0", entry_point="x:Y",
            capabilities=["protocol"],
        )

    def on_activate(self, ctx: PluginContext) -> None:
        ctx.register_protocol(EchoProtocolExecutor())
        ctx.register_strategy(_StrategyProbe())


class TestPluginProtocolChannel:

    def _make_ctx(self):
        d = build_default_dispatcher(hook_registry=HookRegistry())
        return d, PluginContext(
            plugin_name="p1", config={},
            event_bus=InMemoryEventBus(), hook_registry=HookRegistry(),
            dispatcher=d, protocol_registry=d.protocols,
        )

    def test_register_protocol_via_context(self):
        d, ctx = self._make_ctx()
        ctx.register_protocol(EchoProtocolExecutor())
        assert ctx.protocol_count == 1
        assert "echo" in d.protocols.protocols()
        assert "_call:echo" in d.kinds()

    def test_register_strategy_via_context(self):
        d, ctx = self._make_ctx()
        ctx.register_strategy(_StrategyProbe())
        assert "probe_strategy" in d.kinds()

    def test_register_protocol_requires_registry(self):
        from gimbal.events.bus import InMemoryEventBus as Bus
        from gimbal.core.hooks import HookRegistry as HR
        ctx = PluginContext(plugin_name="p2", config={}, event_bus=Bus(),
                            hook_registry=HR())
        try:
            ctx.register_protocol(EchoProtocolExecutor())
            raise AssertionError("应当 RuntimeError")
        except RuntimeError:
            pass

    def test_deactivate_all_cleans_protocol_and_strategy(self):
        d = build_default_dispatcher(hook_registry=HookRegistry())
        plugin = _ProtocolPlugin()
        plugin.load()
        loader = PluginLoader()
        loader.activate_all(
            [plugin],
            event_bus=InMemoryEventBus(),
            hook_registry=HookRegistry(),
            dispatcher=d,
            protocol_registry=d.protocols,
        )
        assert "echo" in d.protocols.protocols()
        assert "probe_strategy" in d.kinds()

        report = loader.deactivate_all([plugin])
        assert report.all_ok
        assert "echo" not in d.protocols.protocols()
        assert "_call:echo" not in d.kinds()
        assert "probe_strategy" not in d.kinds()


# ── Step schema 归一化 ───────────────────────────────────────

class TestStepCallNormalization:
    """v2.1 批次 F 定稿：call 是唯一调用形态（api 糖已退役）。"""

    def test_call_passthrough(self):
        step = Step(call=Call(protocol="http", service="s", method="GET", path="/x"),
                    request=Request(body={}), strategy=[])
        assert step.call_protocol == "http"
        assert step.call.service == "s"

    def test_api_rejected(self):
        """api 糖已删除：Step 不再有 api 字段（extra=forbid 拒收）。"""
        with pytest.raises(Exception):
            Step.model_validate({
                "kind": "step",
                "api": {"kind": "api", "service": "s", "method": "GET", "path": "/x"},
                "request": {"kind": "request", "body": {}},
                "strategy": [],
            })

    def test_protocol_required(self):
        """v2.1 裁决 #1：F 批后协议显式必填（拼写错误编译期暴露）。"""
        with pytest.raises(Exception):
            Call.model_validate({"service": "s", "method": "GET", "path": "/x"})

    def test_dump_roundtrip_pure_call(self):
        step = Step(call=Call(protocol="http", service="s", method="GET", path="/x"),
                    request=Request(body={"a": 1}), strategy=[])
        d = step.model_dump()
        assert d["call"]["protocol"] == "http"
        assert "api" not in d
        step2 = Step.model_validate(d)
        assert step2.call_protocol == "http"

    def test_dump_explicit_call_serializes(self):
        step = Step(call=Call(protocol="echo", message="${var.x}"), strategy=[])
        d = step.model_dump()
        assert d["api"] if False else d["call"]["protocol"] == "echo"
        assert d["call"]["message"] == "${var.x}"
        step2 = Step.model_validate(d)
        assert step2.call_protocol == "echo"


# ── PluginContext 注册通道 ───────────────────────────────────
