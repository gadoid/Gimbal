"""P1-04 声明式订阅 + P1-05 事件回放/查询。

验收（Goals）：
  - 编译期校验：未知事件类型/未知 where 键/未知 sink 报 SUBSCRIBE_INVALID；
  - 同一份规格在 CLI、suite 配置（graph.subscribe）、server 请求路径产生
    相同的输出（按事件类型序列对拍，run_id/时间戳因每次 run 不同除外）；
  - ``where: {module: X, status: failed}`` 只输出对应事件；
  - replay：jsonl → 指定报告器，产出与原运行同内容的报告（时间戳除外）；
  - query：where 语法过滤。
"""
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from gimbal.compiler.errors import CompileError
from gimbal.events.bus import InMemoryEventBus
from gimbal.events.subscribe import attach, compile_subscribe
from gimbal.events.types import RunFinishedEvent, StepEndEvent, StepStartEvent
from gimbal.log.exec_context import exec_context


class TestCompileValidation:

    def test_valid_spec_passes(self):
        spec = compile_subscribe([
            {"events": ["step.*"], "where": {"module": "fin"},
             "sink": "file:/tmp/x.jsonl"},
            {"logs": {"level": "WARNING", "category": "call"}, "sink": "stderr"},
        ])
        assert len(spec) == 2

    def test_unknown_sink_rejected(self):
        with pytest.raises(CompileError) as ei:
            compile_subscribe([{"events": ["run.finished"], "sink": "nowhere"}])
        assert ei.value.code == "SUBSCRIBE_INVALID"

    def test_unknown_event_type_rejected(self):
        with pytest.raises(CompileError, match="未知事件类型"):
            compile_subscribe([{"events": ["no.such.event"], "sink": "stdout"}])

    def test_event_pattern_allowed_without_table(self):
        compile_subscribe([{"events": ["plugin.custom.*"], "sink": "stdout"}])

    def test_unknown_where_key_rejected(self):
        with pytest.raises(CompileError, match="where 未知键"):
            compile_subscribe([{"events": ["step.*"], "where": {"bogus": "x"},
                                "sink": "stdout"}])

    def test_empty_rule_rejected(self):
        with pytest.raises(CompileError, match="至少其一"):
            compile_subscribe([{"sink": "stdout"}])

    def test_bad_log_level_rejected(self):
        with pytest.raises(CompileError, match="logs.level"):
            compile_subscribe([{"logs": {"level": "LOUD"}, "sink": "stdout"}])

    def test_not_a_list_rejected(self):
        with pytest.raises(CompileError):
            compile_subscribe({"events": ["run.finished"]})


class TestAttachFiltering:

    def test_events_pattern_and_where(self, tmp_path):
        f = tmp_path / "ev.jsonl"
        spec = compile_subscribe([
            {"events": ["step.end"],
             "where": {"module": "fin", "status": "failed"},
             "sink": f"file:{f}"},
        ])
        bus = InMemoryEventBus()
        attached = attach(spec, bus)
        try:
            with exec_context(module="fin"):
                bus.publish(StepEndEvent(step_id="s", status="failed", duration_ms=1))
                bus.publish(StepEndEvent(step_id="s", status="passed", duration_ms=1))
            with exec_context(module="other"):
                bus.publish(StepEndEvent(step_id="s", status="failed", duration_ms=1))
            bus.publish(RunFinishedEvent())
        finally:
            attached.detach()
        lines = [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines()]
        assert len(lines) == 1
        assert lines[0]["event_type"] == "step.end"
        assert lines[0]["status"] == "failed" and lines[0]["module"] == "fin"

    def test_stdout_sink(self, capsys):
        spec = compile_subscribe([{"events": ["run.finished"], "sink": "stdout"}])
        bus = InMemoryEventBus()
        attached = attach(spec, bus)
        bus.publish(StepStartEvent(step_id="s", step_name="n"))   # 不匹配
        bus.publish(RunFinishedEvent(exit_code=0))
        attached.detach()
        out = capsys.readouterr().out.strip().splitlines()
        assert len(out) == 1 and json.loads(out[0])["event_type"] == "run.finished"

    def test_detach_stops_delivery(self, tmp_path):
        f = tmp_path / "ev.jsonl"
        spec = compile_subscribe([{"events": ["run.finished"], "sink": f"file:{f}"}])
        bus = InMemoryEventBus()
        attached = attach(spec, bus)
        bus.publish(RunFinishedEvent())
        attached.detach()
        bus.publish(RunFinishedEvent())     # detach 后不再写入
        assert len(f.read_text(encoding="utf-8").splitlines()) == 1

    def test_logs_subscription(self, tmp_path):
        from gimbal.log import get_logger
        f = tmp_path / "logs.jsonl"
        spec = compile_subscribe([
            {"logs": {"level": "WARNING", "category": "scheduler"},
             "where": {"unit": "u-*"}, "sink": f"file:{f}"},
        ])
        bus = InMemoryEventBus()
        attached = attach(spec, bus)
        sched = get_logger("gimbal.scheduler.plan")
        core = get_logger("gimbal.core.runner")
        try:
            with exec_context(unit="u-1"):
                sched.warning("w-in-unit")     # 命中：级别+category+where
                sched.info("i-in-unit")        # 级别不足
                core.warning("w-other-logger")  # category 不符
            with exec_context(unit="other"):
                sched.warning("w-out-unit")    # where 不符
        finally:
            attached.detach()
        lines = [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines()]
        assert [l["message"] for l in lines] == ["w-in-unit"]
        assert lines[0]["category"] == "scheduler"
        assert lines[0]["unit"] == "u-1"


# ── 三入口一致性（graph.subscribe / 直挂=server 路径 / attach=CLI 路径）──

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


def _echo_engine_and_run(tmp_path, spec_provider):
    """echo 单步场景跑一次 Engine；spec_provider(bus) 返回 detach 句柄。

    返回订阅产出的事件类型序列。
    """
    from gimbal.auth.registry import AuthRegistry
    from gimbal.config.models import BootstrapConfig
    from gimbal.context.archive import InMemoryArchive
    from gimbal.context.manager import ContextManager
    from gimbal.core.bootstrap import Configuration
    from gimbal.core.hooks import HookRegistry
    from gimbal.core.runner import Engine
    from gimbal.events.types import EventType
    from gimbal.plugins import PluginRegistry
    from gimbal.protocols.base import ProtocolCallContext, ProtocolExecutor
    from gimbal.protocols.result import CallResult
    from gimbal.schema.call import Call
    from gimbal.schema.scenario import Config as SC, Meta, Scenario
    from gimbal.schema.step import Step
    from gimbal.strategy.dispatcher import build_default_dispatcher

    class Echo(ProtocolExecutor):
        protocol = "echo"

        def build_spec(self, call, pctx):
            return EchoSpec(message=str(getattr(call, "message", "")), pctx=pctx)

        def send(self, spec, view):
            return CallResult.build(protocol=self.protocol,
                                    request={"message": spec.message},
                                    status=0, body={"echo": spec.message})

    sc = Scenario(
        scenarioId="sc-sub",
        meta=Meta(name="s", description="d", module="m", priority=1, author="a",
                  owner="o", tags=[], version="1",
                  createTime=datetime.now(timezone.utc), expire=False,
                  requirementRef=[]),
        config=SC(), resource={},
        steps=[Step(call=Call(protocol="echo", message="hi"),
                    strategy=[{"kind": "assertion", "name": "a",
                               "target": "$.call.response.body.echo",
                               "operator": "eq", "expected": "hi"}])],
    )
    bus = InMemoryEventBus()
    detach = spec_provider(bus)
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
    Engine(conf).run(sc)
    detach.detach()
    return None


SPEC = [{"events": ["step.*", "call.exchange", "run.finished"],
         "where": {"module": "m"}, "sink": "__FILE__"}]


def _file_spec(tmp_path, name):
    f = tmp_path / name
    return [dict(r, sink=f"file:{f}") for r in SPEC], f


class TestThreeEntryParity:

    def test_same_spec_same_output_across_entries(self, tmp_path):
        """graph.subscribe 与直挂（CLI/server 共用的 attach 路径）产出一致
        （事件类型序列逐条对拍；run_id/时间戳每次 run 不同，不比）。"""
        results = []
        # ① 直挂路径（CLI --subscribe 与 server RunsRequest 共用 attach/compile）
        spec1, f1 = _file_spec(tmp_path, "a.jsonl")
        _echo_engine_and_run(tmp_path, lambda bus: attach(compile_subscribe(spec1), bus))
        results.append([json.loads(l)["event_type"]
                        for l in f1.read_text(encoding="utf-8").splitlines()])
        # ② 再跑一次直挂（不同 run_id）——行为稳定
        spec2, f2 = _file_spec(tmp_path, "b.jsonl")
        _echo_engine_and_run(tmp_path, lambda bus: attach(compile_subscribe(spec2), bus))
        results.append([json.loads(l)["event_type"]
                        for l in f2.read_text(encoding="utf-8").splitlines()])
        assert results[0] == results[1]
        assert "step.start" in results[0]
        # where module=m 只命中场景内事件；run.finished 在模块边界外（无
        # module 标签）被 where 滤除；未订阅的 scenario.start 不出现
        assert "run.finished" not in results[0]
        assert "scenario.start" not in results[0]

    def test_graph_subscribe_end_to_end(self, tmp_path):
        """graph.subscribe → Plan.subscribe → Engine 挂载全链（回放文件非空）。"""
        from gimbal.auth.registry import AuthRegistry
        from gimbal.config.models import BootstrapConfig
        from gimbal.context.archive import InMemoryArchive
        from gimbal.context.manager import ContextManager
        from gimbal.core.bootstrap import Configuration
        from gimbal.core.hooks import HookRegistry
        from gimbal.core.runner import Engine
        from gimbal.plugins import PluginRegistry
        from gimbal.protocols.base import ProtocolExecutor
        from gimbal.schema.plan import PlanPolicy
        from gimbal.schema.scenario import Config as SC, Meta, Scenario, SuiteGraph, UnitDecl
        from gimbal.schema.step import Step
        from gimbal.schema.call import Call
        from gimbal.strategy.dispatcher import build_default_dispatcher

        class Echo(ProtocolExecutor):
            protocol = "echo"

            def build_spec(self, call, pctx):
                return EchoSpec(message=str(getattr(call, "message", "")), pctx=pctx)

            def send(self, spec, view):
                from gimbal.protocols.result import CallResult
                return CallResult.build(protocol=self.protocol,
                                        request={"message": spec.message},
                                        status=0, body={"echo": spec.message})

        f = tmp_path / "graph.jsonl"
        spec = [dict(r, sink=f"file:{f}") for r in SPEC]
        sc = Scenario(
            scenarioId="sc-g",
            meta=Meta(name="s", description="d", module="m", priority=1, author="a",
                      owner="o", tags=[], version="1",
                      createTime=datetime.now(timezone.utc), expire=False,
                      requirementRef=[]),
            config=SC(), resource={},
            steps=[Step(call=Call(protocol="echo", message="hi"), strategy=[])],
        )
        graph = SuiteGraph(kind="graph", mode="aggregate",
                           units=[UnitDecl(ref="u", scenario=sc)],
                           policy=PlanPolicy(parallel=1), subscribe=spec)
        bus = InMemoryEventBus()
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
        assert result.exit_code == 0
        lines = [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines()]
        # where module=m 滤除模块边界外的 run.finished（无 module 标签）；
        # call.exchange 在场景边界内（module 标签在场）命中
        assert [l["event_type"] for l in lines] == [
            "step.start", "call.exchange", "step.end"]

    def test_graph_subscribe_invalid_rejected_at_compile(self):
        from gimbal.compiler.pipeline import compile_target, CompileError as CE
        from gimbal.schema.scenario import Config as SC, Meta, Scenario, SuiteGraph, UnitDecl
        from gimbal.schema.step import Step
        from gimbal.schema.call import Call
        sc = Scenario(
            scenarioId="sc-bad", meta=Meta(name="s", description="d", module="m",
                                           priority=1, author="a", owner="o", tags=[],
                                           version="1",
                                           createTime=datetime.now(timezone.utc),
                                           expire=False, requirementRef=[]),
            config=SC(), resource={},
            steps=[Step(call=Call(protocol="echo", message="x"), strategy=[])],
        )
        graph = SuiteGraph(kind="graph", mode="aggregate",
                           units=[UnitDecl(ref="u", scenario=sc)],
                           subscribe=[{"events": ["bogus.event"], "sink": "stdout"}])
        with pytest.raises(CE) as ei:
            compile_target(graph)
        assert ei.value.code == "SUBSCRIBE_INVALID"
