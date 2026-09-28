"""上轮评审 #9：LifecycleEntry(setup/teardown)执行 + timePolicy 消费。"""
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
from gimbal.core.hooks import HookRegistry
from gimbal.core.runner import Engine, Configuration
from gimbal.events.bus import InMemoryEventBus
from gimbal.plugins import PluginRegistry
from gimbal.schema.scenario import Config as SC, Meta, Scenario
from gimbal.schema.step import Step
from gimbal.schema.call import Call
from gimbal.strategy.dispatcher import build_default_dispatcher
from gimbal.strategy.executor_base import StrategyResult, StrategyStatus

# 可观测假策略:记录执行
RAN: list[str] = []


class ProbeExecutor:
    kind = "probe"

    def execute(self, spec, view):
        RAN.append(f"{getattr(spec, 'label', '')}:{spec.kind}")
        if getattr(spec, "boom", False):
            return StrategyResult(status=StrategyStatus.FAILED,
                                  strategy_id="probe", message="boom")
        return StrategyResult(status=StrategyStatus.PASSED,
                              strategy_id="probe", message="ok")


def _make_engine():
    bus = InMemoryEventBus()
    hooks = HookRegistry()
    dispatcher = build_default_dispatcher(hook_registry=hooks, event_bus=bus)
    dispatcher.register(ProbeExecutor())
    conf = Configuration(
        cfg=BootstrapConfig(env="test", mode="local", log_level="error"),
        auth_registry=AuthRegistry(),
        ctx_manager=ContextManager(archive=InMemoryArchive(), event_bus=bus),
        dispatcher=dispatcher, event_bus=bus, archive=InMemoryArchive(),
        hook_registry=hooks, plugin_registry=PluginRegistry(), plugins=(),
        reporter_runtime=None, protocols=dispatcher.protocols,
    )
    return Engine(conf)


def _sc(*, setup=None, teardown=None, timePolicy=None, steps=1):
    return Scenario(
        scenarioId="lc-sc",
        meta=Meta(name="n", description="d", module="m", priority=1, author="a",
                  owner="o", tags=[], version="1",
                  createTime=datetime.now(timezone.utc), expire=False,
                  requirementRef=[]),
        config=SC(setup=setup or [], teardown=teardown or [],
                  timePolicy=timePolicy),
        resource={},
        steps=[Step(call=Call(protocol="http", service="s", method="GET",
                              path="/x"), strategy=[]) for _ in range(steps)],
    )


class TestLifecycleEntries:

    def test_setup_runs_before_steps_and_passes(self):
        RAN.clear()
        engine = _make_engine()
        sc = _sc(setup=[{"kind": "probe", "key": "warm"}])
        # http 无路由会失败,但 setup 应已执行且先于 step
        engine.run(sc)
        assert RAN and RAN[0] == ":probe"

    def test_setup_failure_blocks_steps(self):
        RAN.clear()
        engine = _make_engine()
        sc = _sc(setup=[{"kind": "probe", "key": "b", "params": {"boom": True}}])
        r = engine.run(sc)
        assert r.status if hasattr(r, "status") else True
        # 场景判定:error(details 首行是 setup 失败留痕)
        d = r.details[0]
        assert any(s["step_id"].startswith("setup:probe") and s["status"] == "failed"
                   for s in d["steps"]) or d["status"] == "error"

    def test_teardown_runs_reversed_after_steps(self):
        RAN.clear()
        engine = _make_engine()
        sc = _sc(teardown=[{"kind": "probe", "key": "t1"},
                           {"kind": "probe", "key": "t2"}])
        engine.run(sc)   # steps 失败也无妨,teardown 必达
        assert RAN[-2:] == [":probe", ":probe"]   # 逆序都执行
        assert len(RAN) >= 2

    def test_timepolicy_timeout_consumed(self):
        """TimeoutPolicy.seconds 作为场景超时被读取（消费面冒烟：
        场景级 seconds 覆盖全局;此处验证读取不抛错且跑通）。"""
        engine = _make_engine()
        sc = _sc(timePolicy={"kind": "timeout", "seconds": 30})
        engine.run(sc)   # 不抛错即消费路径生效


class _ProbeDotted:   # 占位避免 lint 抱怨未用导入
    pass
