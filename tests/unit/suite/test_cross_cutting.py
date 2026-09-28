"""N1/N2/S4:suite 横切面(D-6 拍板保留)—— checks 注入 / gates 判定 /
SUITE 生命周期事件复活。

定稿 D6/D7 语义落地(2026-09-29 拍板):
  - checks:选择器(refs/tags/bracket)命中单元,编译期把断言策略追加到
    其场景各步骤策略列表尾 —— 运行期零感知;
  - gates:判定阶段按聚合度量(pass_rate/fail_count/total/avg/max
    duration)求与,失败改写 exit_code + details 追加 __gates__ 行;
  - suite.start/suite.end:事件类型复活(此前全仓无发布方,S4 死类型)。
"""
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from gimbal.compiler.pipeline import compile_target
from gimbal.schema.call import Call
from gimbal.schema.scenario import (
    Config as SC, Meta, Scenario, SuiteGraph, UnitDecl,
)
from gimbal.schema.step import Step


def _scenario(sid: str, *, tags: list[str] | None = None) -> Scenario:
    return Scenario(
        scenarioId=sid,
        meta=Meta(name=sid, description="d", module="m", priority=1, author="a",
                  owner="o", tags=tags or [], version="1",
                  createTime=datetime.now(timezone.utc), expire=False,
                  requirementRef=[]),
        config=SC(), resource={},
        steps=[Step(call=Call(protocol="echo", message=sid), strategy=[])],
    )


ASSERTION = {"kind": "assertion", "name": "cross", "target": "$.call.response.status",
             "operator": "eq", "expected": 200}


class TestCheckInjection:

    def test_check_injected_into_selected_units(self):
        graph = SuiteGraph(
            kind="graph", mode="aggregate",
            units=[UnitDecl(ref="a", scenario=_scenario("a")),
                   UnitDecl(ref="b", scenario=_scenario("b"))],
            checks=[{"on": {"refs": ["a"]}, "strategy": ASSERTION}],
        )
        plan = compile_target(graph)
        by_id = {u.id: u for u in plan.units}
        a_strategies = by_id["a"].scenario.steps[0].strategy
        b_strategies = by_id["b"].scenario.steps[0].strategy
        assert len(a_strategies) == 1 and a_strategies[0]["name"] == "cross"
        assert len(b_strategies) == 0        # 未命中不注入

    def test_check_by_tag_selector(self):
        graph = SuiteGraph(
            kind="graph", mode="aggregate",
            units=[UnitDecl(ref="x", scenario=_scenario("x", tags=["pay"])),
                   UnitDecl(ref="y", scenario=_scenario("y", tags=["logi"]))],
            checks=[{"on": {"tags": ["pay"]}, "strategy": ASSERTION}],
        )
        plan = compile_target(graph)
        by_id = {u.id: u for u in plan.units}
        assert len(by_id["x"].scenario.steps[0].strategy) == 1
        assert len(by_id["y"].scenario.steps[0].strategy) == 0

    def test_check_bracket_before(self):
        graph = SuiteGraph(
            kind="graph", mode="aggregate",
            before=[UnitDecl(ref="setup", scenario=_scenario("setup"))],
            units=[UnitDecl(ref="m", scenario=_scenario("m"))],
            checks=[{"on": {"bracket": "before"}, "strategy": ASSERTION}],
        )
        plan = compile_target(graph)
        assert len(plan.before[0].scenario.steps[0].strategy) == 1
        assert len(plan.units[0].scenario.steps[0].strategy) == 0

    def test_empty_selector_hits_all_main(self):
        graph = SuiteGraph(
            kind="graph", mode="aggregate",
            units=[UnitDecl(ref="a", scenario=_scenario("a")),
                   UnitDecl(ref="b", scenario=_scenario("b"))],
            checks=[{"on": {}, "strategy": ASSERTION}],
        )
        plan = compile_target(graph)
        assert all(len(u.scenario.steps[0].strategy) == 1 for u in plan.units)

    def test_invalid_strategy_rejected(self):
        import pytest

        from gimbal.compiler.errors import CompileError
        with pytest.raises(CompileError, match="checks\\[0\\]"):
            SuiteGraph(
                kind="graph", mode="aggregate",
                units=[UnitDecl(ref="a", scenario=_scenario("a"))],
                checks=[{"on": {"refs": ["a"]},
                         "strategy": {"kind": "no-such-kind"}}],
            ) and compile_target(SuiteGraph(
                kind="graph", mode="aggregate",
                units=[UnitDecl(ref="a", scenario=_scenario("a"))],
                checks=[{"on": {"refs": ["a"]},
                         "strategy": {"kind": "no-such-kind"}}],
            ))

    def test_source_scenario_not_mutated(self):
        """注入发生在深拷贝上:graph 原对象不被改写(声明不可变纪律)。"""
        sc = _scenario("a")
        graph = SuiteGraph(
            kind="graph", mode="aggregate",
            units=[UnitDecl(ref="a", scenario=sc)],
            checks=[{"on": {}, "strategy": ASSERTION}],
        )
        compile_target(graph)
        assert len(graph.units[0].scenario.steps[0].strategy) == 0


# ── N2/S4:suite 生命周期事件 + gates 判定(Engine 集成)──────────

@dataclass
class EchoSpec:
    kind: str = "call:echo"
    message: str = ""
    name: Optional[str] = "echo_call"
    phase: Optional[str] = None
    order: int = 0
    enabled: bool = True
    onFailure: str = "abort"
    tags: list = field(default_factory=list)
    pctx: Optional[object] = None


def _run_graph(graph: SuiteGraph):
    """echo 引擎跑 graph,收全部事件与 RunResult。"""
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
    from gimbal.strategy.dispatcher import build_default_dispatcher

    class Echo(ProtocolExecutor):
        protocol = "echo"

        def build_spec(self, call, pctx):
            return EchoSpec(message=str(getattr(call, "message", "")), pctx=pctx)

        def send(self, spec, view):
            return CallResult.build(protocol=self.protocol,
                                    request={"message": spec.message},
                                    status=0, body={"echo": spec.message})

    bus = InMemoryEventBus()
    events: list = []
    bus.subscribe(events.append)
    hooks = HookRegistry()
    dispatcher = build_default_dispatcher(hook_registry=hooks, event_bus=bus)
    dispatcher.protocols.register(Echo())
    ctx_manager = ContextManager(archive=InMemoryArchive(), event_bus=bus)
    conf = Configuration(
        cfg=BootstrapConfig(env="test", mode="local", log_level="error"),
        auth_registry=AuthRegistry(), ctx_manager=ctx_manager,
        dispatcher=dispatcher, event_bus=bus, archive=InMemoryArchive(),
        hook_registry=hooks, plugin_registry=PluginRegistry(), plugins=(),
        reporter_runtime=None, protocols=dispatcher.protocols,
    )
    result = Engine(conf).run(graph)
    return events, result


def _two_unit_graph(**extra) -> SuiteGraph:
    return SuiteGraph(
        kind="graph", mode="aggregate",
        units=[UnitDecl(ref="a", scenario=_scenario("a")),
               UnitDecl(ref="b", scenario=_scenario("b"))],
        **extra,
    )


class TestSuiteLifecycleEvents:

    def test_suite_start_end_published(self):
        events, result = _run_graph(_two_unit_graph())
        starts = [e for e in events if e.event_type == "suite.start"]
        ends = [e for e in events if e.event_type == "suite.end"]
        assert len(starts) == 1 and len(ends) == 1
        assert starts[0].suite_id == "__graph__"
        # 序:suite.start 在 run.start 之后;suite.end 在 run.finished 之前
        seqs = {e.event_type: e.seq for e in events
                if e.event_type in ("run.start", "suite.start",
                                    "suite.end", "run.finished")}
        assert seqs["run.start"] < seqs["suite.start"] < seqs["suite.end"] < seqs["run.finished"]
        assert ends[0].status == "passed" and result.exit_code == 0

    def test_suite_end_failed_on_failure(self):
        graph = SuiteGraph(
            kind="graph", mode="aggregate",
            units=[UnitDecl(ref="a", scenario=_scenario("a"))],
            checks=[{"on": {},
                     "strategy": {"kind": "assertion", "name": "boom",
                                  "target": "$.call.response.body.echo",
                                  "operator": "eq", "expected": "definitely-not"}}],
        )
        events, result = _run_graph(graph)
        end = next(e for e in events if e.event_type == "suite.end")
        assert result.exit_code == 1 and end.status == "failed"


class TestGates:

    def test_pass_rate_gate_pass(self):
        events, result = _run_graph(_two_unit_graph(
            gates=[{"metric": "pass_rate", "op": "gte", "value": 1.0}]))
        assert result.exit_code == 0
        assert not any(isinstance(d, dict) and d.get("gates")
                       for d in result.details)

    def test_gate_failure_flips_exit_code_with_detail_row(self):
        events, result = _run_graph(_two_unit_graph(
            gates=[{"metric": "pass_rate", "op": "gte", "value": 1.1}]))
        assert result.exit_code == 1
        gate_rows = [d for d in result.details
                     if isinstance(d, dict) and d.get("gates")]
        assert len(gate_rows) == 1
        assert gate_rows[0]["scenario_id"] == "__gates__"
        assert "pass_rate" in gate_rows[0]["halt_reason"]

    def test_max_duration_gate(self):
        events, result = _run_graph(_two_unit_graph(
            gates=[{"metric": "max_duration_ms", "op": "lt", "value": 0.0001}]))
        assert result.exit_code == 1    # echo 一定慢于 0.0001ms

    def test_gates_transparent_to_unit_counts(self):
        """gates 只改写 exit_code,不动单元计数(P1-11 单元口径不变)。"""
        _, result = _run_graph(_two_unit_graph(
            gates=[{"metric": "total", "op": "eq", "value": 99}]))
        assert result.total == 2 and result.passed == 2 and result.failed == 0
        assert result.exit_code == 1
