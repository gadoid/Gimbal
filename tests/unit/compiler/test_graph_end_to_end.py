"""批次 C 端到端：编排图经 Engine 真跑（echo 协议）——数据流转/blocked/括号。

验收门：三模式端到端 + 三形态连线（数据真实流过：上游 extract 提升 →
调度器收集 outputs → 连线注入下游 vars → 模板解析 → 断言验证）。
"""
import dataclasses
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from gimbal.auth.registry import AuthRegistry
from gimbal.config.models import BootstrapConfig
from gimbal.context.archive import InMemoryArchive
from gimbal.context.manager import ContextManager
from gimbal.core.bootstrap import Configuration
from gimbal.core.hooks import HookRegistry
from gimbal.core.runner import Engine
from gimbal.events.bus import InMemoryEventBus
from gimbal.plugins import PluginRegistry
from gimbal.protocols.base import ProtocolCallContext, ProtocolExecutor
from gimbal.protocols.result import CallResult
from gimbal.schema.call import Call
from gimbal.schema.scenario import (
    Config as ScenarioConfig, Meta, Scenario, SuiteGraph, UnitDecl,
)
from gimbal.schema.step import Step
from gimbal.strategy.dispatcher import build_default_dispatcher


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


class EchoExecutor(ProtocolExecutor):
    protocol = "echo"

    def build_spec(self, call, pctx):
        return EchoSpec(message=str(getattr(call, "message", "")), pctx=pctx)

    def send(self, spec, view):
        return CallResult.build(protocol=self.protocol,
                                request={"message": spec.message},
                                status=0, body={"echo": spec.message})


def _make_engine():
    bus = InMemoryEventBus()
    archive = InMemoryArchive()
    hooks = HookRegistry()
    dispatcher = build_default_dispatcher(hook_registry=hooks)
    dispatcher.protocols.register(EchoExecutor())
    ctx_manager = ContextManager(archive=archive, event_bus=bus)
    cfg = BootstrapConfig(env="test", mode="local", log_level="error")
    conf = Configuration(
        cfg=cfg, auth_registry=AuthRegistry(), ctx_manager=ctx_manager,
        dispatcher=dispatcher, event_bus=bus, archive=archive,
        hook_registry=hooks, plugin_registry=PluginRegistry(), plugins=(),
        reporter_runtime=None, protocols=dispatcher.protocols,
    )
    return Engine(conf)


def _scenario(sid: str, *, message=None, extract_to=None, assert_echo=None, vars=None):
    strategy = []
    if extract_to:
        strategy.append({"kind": "extract", "name": "out",
                         "expression": "$.call.response.body.echo",
                         "target": extract_to, "scope": "scenario"})
    if assert_echo is not None:
        strategy.append({"kind": "assertion", "name": "chk",
                         "target": "$.call.response.body.echo",
                         "operator": "eq", "expected": assert_echo})
    return Scenario(
        scenarioId=sid,
        meta=Meta(name=sid, description="d", module="m", priority=1, author="a",
                  owner="o", tags=[], version="1.0",
                  createTime=datetime.now(timezone.utc), expire=False,
                  requirementRef=[]),
        config=ScenarioConfig(vars=vars or {}),
        resource={},
        steps=[Step(call=Call(protocol="echo", message=message or sid),
                    strategy=strategy)],
    )


class TestDataFlow:

    def test_chain_real_variable_flow(self):
        """chain：a 产出 greeting → b 模板消费并断言（数据真实流过）。"""
        engine = _make_engine()
        graph = SuiteGraph(
            mode="chain",
            units=[
                UnitDecl(ref="a", scenario=_scenario(
                    "a", message="hello-from-a", extract_to="greeting")),
                UnitDecl(ref="b", scenario=_scenario(
                    "b", message="${var.greeting}", extract_to="heard",
                    assert_echo="hello-from-a")),
            ],
        )
        result = engine.run(graph)
        assert result.exit_code == 0, [d for d in result.details]
        assert result.passed == 2
        rows = {d["scenario_id"]: d for d in result.details}
        assert rows["b"]["status"] == "passed"   # b 断言收到的就是 a 的输出

    def test_compose_parallel_with_shared_upstream(self):
        """compose 并行：一源两汇，两个汇都拿到源的输出。"""
        engine = _make_engine()
        graph = SuiteGraph(
            mode="compose",
            policy={"parallel": 2},
            units=[
                UnitDecl(ref="src", scenario=_scenario(
                    "src", message="TOKEN-1", extract_to="token")),
                UnitDecl(ref="u1", scenario=_scenario(
                    "u1", message="${var.token}", assert_echo="TOKEN-1"),
                    needs=["src"]),
                UnitDecl(ref="u2", scenario=_scenario(
                    "u2", message="${var.token}", assert_echo="TOKEN-1"),
                    needs=["src"]),
            ],
        )
        result = engine.run(graph)
        assert result.passed == 3 and result.exit_code == 0

    def test_fanout_end_to_end(self):
        engine = _make_engine()
        graph = SuiteGraph(
            mode="fanout",
            units=[
                UnitDecl(ref="s", scenario=_scenario("s", message="FAN",
                                                     extract_to="v")),
                UnitDecl(ref="x", scenario=_scenario("x", message="${var.v}",
                                                     assert_echo="FAN")),
                UnitDecl(ref="y", scenario=_scenario("y", message="${var.v}",
                                                     assert_echo="FAN")),
            ],
        )
        result = engine.run(graph)
        assert result.passed == 3


class TestBlockedAndBrackets:

    def test_blocked_cascade_on_upstream_failure(self):
        """compose：中间单元失败 → 下游 blocked（不是 cancelled/failed）。"""
        engine = _make_engine()
        graph = SuiteGraph(
            mode="chain",
            units=[
                UnitDecl(ref="a", scenario=_scenario("a", message="v",
                                                     extract_to="tok")),
                UnitDecl(ref="bad", scenario=_scenario(
                    "bad", message="${var.tok}", extract_to="tok_bad",
                    assert_echo="definitely-not-matching")),   # 断言失败
                UnitDecl(ref="c", scenario=_scenario("c", message="${var.tok}",
                                                     assert_echo="v")),
            ],
        )
        result = engine.run(graph)
        statuses = [d["status"] for d in result.details]
        assert statuses == ["passed", "failed", "blocked"]
        assert result.blocked == 1
        assert result.exit_code == 1

    def test_after_bracket_always_runs_despite_failure(self):
        """after 必达：主体失败，清理单元仍执行。"""
        engine = _make_engine()
        after_ran = _scenario("cleanup", message="cleaned", extract_to="cleaned_at")
        graph = SuiteGraph(
            mode="aggregate",
            units=[UnitDecl(ref="boom", scenario=_scenario(
                "boom", message="x", assert_echo="never"))],
            after=[UnitDecl(ref="cleanup", scenario=after_ran)],
        )
        result = engine.run(graph)
        assert result.failed == 1
        rows = [d for d in result.details if d.get("bracket") == "after"]
        assert rows and rows[0]["status"] == "passed"
        assert rows[0]["scenario_id"] == "cleanup"

    def test_before_output_feeds_all_units(self):
        """before 全局前置：登录产出 token，主体单元消费。"""
        engine = _make_engine()
        graph = SuiteGraph(
            mode="aggregate",
            before=[UnitDecl(ref="login", scenario=_scenario(
                "login", message="SESSION-9", extract_to="token"))],
            units=[
                UnitDecl(ref="u1", scenario=_scenario(
                    "u1", message="${var.token}", assert_echo="SESSION-9")),
                UnitDecl(ref="u2", scenario=_scenario(
                    "u2", message="${var.token}", assert_echo="SESSION-9")),
            ],
        )
        result = engine.run(graph)
        assert result.passed == 2 and result.exit_code == 0
