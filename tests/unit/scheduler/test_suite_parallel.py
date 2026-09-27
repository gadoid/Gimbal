"""Suite 多线程分派 — SuiteScheduler 单元测试 + Engine 级端到端。

覆盖：
  - SuiteScheduler 串行模式：结果有序、fail-fast 停止（历史语义等价）；
  - 并行模式：结果按提交序、并发真实发生（耗时证明）、fail-fast 取消未开始单元；
  - Engine 级并行 suite（echo 协议 sleep 步骤）：
      * 多 scenario 并行执行（wall time < 串行下界）；
      * Archive step/exchange 键空间化 —— 并行 scenario 各自的 step-000 不互踩；
      * 事件经总线锁串行化，全部到达且无异常；
      * RunResult 计数正确、details 按提交序；
      * 串行 suite（不声明 execution）行为不变。
"""
import dataclasses
import os
import sys
import time
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
from gimbal.schema.call import Call
from gimbal.schema.scenario import Config as ScenarioConfig
from gimbal.schema.scenario import Meta, Scenario, SuiteGraph, UnitDecl
from gimbal.schema.plan import PlanPolicy
from gimbal.schema.step import Step
from gimbal.strategy.dispatcher import build_default_dispatcher
from gimbal.strategy.executor_base import StrategyResult, StrategyStatus
from gimbal.scheduler import SuiteScheduler
from gimbal.scheduler.concurrency import clamp_workers


# ── 测试用慢速 echo 协议（并发证明的耗时源）─────────────────

@dataclass
class SlowEchoSpec:
    kind: str = "_call:echo"
    message: str = ""
    delay: float = 0.0
    name: Optional[str] = "echo_call"
    phase: Optional[str] = None
    order: int = 0
    enabled: bool = True
    onFailure: str = "abort"
    tags: list = dataclasses.field(default_factory=list)
    pctx: Optional[ProtocolCallContext] = None


class SlowEchoProtocolExecutor(ProtocolExecutor):
    protocol = "echo"

    def build_spec(self, call, pctx: ProtocolCallContext):
        return SlowEchoSpec(
            message=getattr(call, "message", ""),
            delay=float(getattr(call, "delay", 0.0) or 0.0),
            pctx=pctx,
        )

    def send(self, spec, view):
        from gimbal.protocols.result import CallResult
        time.sleep(spec.delay)
        return CallResult.build(
            protocol=self.protocol,
            request={"message": spec.message},
            status=0,
            body={"echo": spec.message},
        )


# ── SuiteScheduler 纯调度测试 ───────────────────────────────

class TestSuiteScheduler:

    def test_serial_ordered_and_fail_fast(self):
        sched = SuiteScheduler()

        def run_one(i):
            return type("R", (), {"passed": i != 2})()

        results = sched.run_all([0, 1, 2, 3, 4], run_one, fail_fast=True)
        # fail-fast：第 3 项（i=2）失败即停止，i=3/4 未执行（None 占位）
        assert results[:3] == [results[0], results[1], results[2]]
        assert getattr(results[2], "passed") is False
        assert results[3] is None and results[4] is None

    def test_parallel_results_in_submission_order(self):
        sched = SuiteScheduler()

        def run_one(i):
            # 靠后的项先完成 —— 结果仍须按提交序
            time.sleep(0.05 * (4 - i))
            return i

        results = sched.run_all(list(range(5)), run_one, parallel=True, max_workers=5)
        assert results == [0, 1, 2, 3, 4]

    def test_parallel_actually_concurrent(self):
        sched = SuiteScheduler()
        started = []
        import threading
        barrier = threading.Barrier(3, timeout=5)

        def run_one(i):
            barrier.wait()   # 3 个任务同时在场才放行 —— 证明真并发
            return i

        t0 = time.monotonic()
        results = sched.run_all([0, 1, 2], run_one, parallel=True, max_workers=3)
        assert results == [0, 1, 2]
        assert time.monotonic() - t0 < 4   # barrier 没死锁即通过

    def test_parallel_fail_fast_cancels_pending(self):
        sched = SuiteScheduler()

        def run_one(i):
            if i == 0:
                return type("R", (), {"passed": False})()
            time.sleep(0.3)
            return type("R", (), {"passed": True})()

        results = sched.run_all(list(range(6)), run_one, parallel=True,
                                max_workers=1, fail_fast=True)
        # max_workers=1：首项失败后其余全部取消
        assert getattr(results[0], "passed") is False
        assert all(r is None for r in results[1:])

    def test_clamp_workers(self):
        assert clamp_workers(None) == 4
        assert clamp_workers(0) == 1
        assert clamp_workers(999) == 64


# ── Engine 级并行 suite 端到端 ─────────────────────────────

def _make_engine():
    """手工装配 Configuration（不走 bootstrap 全链，聚焦执行链）。"""
    bus = InMemoryEventBus()
    archive = InMemoryArchive()
    hooks = HookRegistry()
    dispatcher = build_default_dispatcher(hook_registry=hooks)
    dispatcher.protocols.register(SlowEchoProtocolExecutor())
    ctx_manager = ContextManager(archive=archive, event_bus=bus)
    cfg = BootstrapConfig(env="test", mode="local", log_level="error")
    conf = Configuration(
        cfg=cfg, auth_registry=AuthRegistry(), ctx_manager=ctx_manager,
        dispatcher=dispatcher, event_bus=bus, archive=archive,
        hook_registry=hooks, plugin_registry=PluginRegistry(), plugins=(),
        reporter_runtime=None, protocols=dispatcher.protocols,
    )
    return Engine(conf), archive, bus


def _make_scenario(sid: str, delay: float = 0.3) -> Scenario:
    return Scenario(
        scenarioId=sid,
        meta=Meta(name=f"n-{sid}", description="d", module="m", priority=1,
                  author="a", owner="o", tags=[], version="1.0",
                  createTime=datetime.now(timezone.utc), expire=False,
                  requirementRef=[]),
        config=ScenarioConfig(),
        resource={},
        steps=[Step(call=Call(protocol="echo", message=sid, delay=delay),
                    strategy=[])],
    )


class TestEngineParallelSuite:

    def test_parallel_suite_runs_concurrently(self):
        """3 个 0.4s 场景、3 worker：并行 wall time < 串行下界 1.2s 的 80%。"""
        engine, archive, bus = _make_engine()
        recorder = []
        bus.subscribe(lambda e: recorder.append(e), "scenario.end")

        graph = SuiteGraph(
            kind="graph", mode="aggregate",
            units=[UnitDecl(ref="sc-p1", scenario=_make_scenario("sc-p1", 0.4)),
                   UnitDecl(ref="sc-p2", scenario=_make_scenario("sc-p2", 0.4)),
                   UnitDecl(ref="sc-p3", scenario=_make_scenario("sc-p3", 0.4))],
            policy=PlanPolicy(parallel=3),
        )
        t0 = time.monotonic()
        result = engine.run(graph)
        wall = time.monotonic() - t0

        assert result.total == 3 and result.passed == 3 and result.exit_code == 0
        assert [d["scenario_id"] for d in result.details] == ["sc-p1", "sc-p2", "sc-p3"]
        assert wall < 0.4 * 3 * 0.8, f"未并发? wall={wall:.2f}s"
        # scenario.end 事件全部到达且无异常（scenario.end 双发是历史行为：
        # runner emit + ContextManager 投影，断言口径按 sid 覆盖）
        assert {e.scenario_id for e in recorder} == {"sc-p1", "sc-p2", "sc-p3"}
        assert len(recorder) >= 3

    def test_archive_step_keyspace_no_clobber(self):
        """并行 scenario 各自的 step-000/exchange 不互相覆盖。"""
        engine, archive, _ = _make_engine()
        graph = SuiteGraph(
            kind="graph", mode="aggregate",
            units=[UnitDecl(ref="sc-a", scenario=_make_scenario("sc-a", 0.05)),
                   UnitDecl(ref="sc-b", scenario=_make_scenario("sc-b", 0.05)),
                   UnitDecl(ref="sc-c", scenario=_make_scenario("sc-c", 0.05))],
            policy=PlanPolicy(parallel=3),
        )
        result = engine.run(graph)
        assert result.passed == 3

        # 三个 scenario 各有 step-000：按 (scenario_id, step_id) 可分别取回
        for sid in ("sc-a", "sc-b", "sc-c"):
            step = archive.get_step("step-000", scenario_id=sid)
            assert step is not None, f"{sid} 的 step-000 被互踩"
            ex = archive.get_exchange("step-000", scenario_id=sid)
            assert ex is not None and ex["call"]["response"]["body"]["echo"] == sid

    def test_serial_suite_default_unchanged(self):
        """不声明 execution（缺省串行）：行为与历史一致，全部通过、按序。"""
        engine, archive, _ = _make_engine()
        graph = SuiteGraph(
            kind="graph", mode="aggregate",
            units=[UnitDecl(ref="sc-s1", scenario=_make_scenario("sc-s1", 0.02)),
                   UnitDecl(ref="sc-s2", scenario=_make_scenario("sc-s2", 0.02))],
        )
        result = engine.run(graph)
        assert result.total == 2 and result.passed == 2
        assert [d["scenario_id"] for d in result.details] == ["sc-s1", "sc-s2"]

    def test_parallel_bus_serializes_events(self):
        """并发发布的事件全部无异常到达（总线锁的吞吐正确性冒烟）。"""
        engine, archive, bus = _make_engine()
        counter = {"n": 0, "errors": 0}

        def handler(event):
            counter["n"] += 1
            # 模拟 reporter 的非重入工作：短暂睡眠放大竞态窗口
            time.sleep(0.001)

        bus.subscribe(handler, "call.exchange")

        graph = SuiteGraph(
            kind="graph", mode="aggregate",
            units=[UnitDecl(ref=f"sc-e{i}", scenario=_make_scenario(f"sc-e{i}", 0.05))
                   for i in range(4)],
            policy=PlanPolicy(parallel=4),
        )
        result = engine.run(graph)
        assert result.passed == 4
        assert counter["n"] == 4, f"SYNC 事件在并行下丢失: n={counter['n']}"
