"""生命周期收尾接缝（全量评估 2026-11-02 #10/#11）。

#10 SuiteContext 此前从不 finalize：finalize_suite 全仓零调用,Archive.save_suite
是死接口。现在 _run_plan 在 gates 之后、suite.end 之前收口,归档里能查到 Suite。
#11 预处理异常此前直接冒泡:finalize_scenario / scenario.start / scenario.end
全部跳过。现在补齐生命周期后原样上抛 —— 聚合仍记 error 行(判定口径不变),
但场景有归档(status=error)、事件流有成对的 start/end。
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from gimbal.auth.registry import AuthRegistry
from gimbal.config.models import BootstrapConfig
from gimbal.context.archive import InMemoryArchive
from gimbal.context.manager import ContextManager
from gimbal.core.hooks import HookRegistry
from gimbal.core.runner import Configuration, Engine
from gimbal.events.bus import InMemoryEventBus
from gimbal.plugins import PluginRegistry
from gimbal.schema import Call, Config as SC, Meta, Scenario, Step
from gimbal.strategy.dispatcher import build_default_dispatcher


def _engine() -> tuple[Engine, InMemoryArchive, InMemoryEventBus]:
    bus = InMemoryEventBus()
    hooks = HookRegistry()
    archive = InMemoryArchive()
    dispatcher = build_default_dispatcher(hook_registry=hooks, event_bus=bus)
    conf = Configuration(
        cfg=BootstrapConfig(env="test", mode="local", log_level="error"),
        auth_registry=AuthRegistry(),
        ctx_manager=ContextManager(archive=archive, event_bus=bus),
        dispatcher=dispatcher, event_bus=bus, archive=archive,
        hook_registry=hooks, plugin_registry=PluginRegistry(), plugins=(),
        reporter_runtime=None, protocols=dispatcher.protocols,
    )
    return Engine(conf), archive, bus


def _scenario(sid: str, *, headers: dict | None = None) -> Scenario:
    return Scenario(
        scenarioId=sid,
        meta=Meta(name="n", description="d", module="m", priority=1, author="a",
                  owner="o", tags=[], version="1",
                  createTime=datetime.now(timezone.utc), expire=False,
                  requirementRef=[]),
        config=SC(setup=[], teardown=[], timePolicy=None),
        resource={},
        steps=[Step(call=Call(protocol="http", service="s", method="GET",
                              path="/x", headers=headers or {}), strategy=[])],
    )


def test_suite_context_is_finalized_and_archived() -> None:
    engine, archive, _bus = _engine()
    assert archive.stats()["suites"] == 0
    engine.run(_scenario("lc-suite"))
    assert archive.stats()["suites"] == 1
    suite = next(iter(archive._suites.values()))
    assert suite.ended_at is not None
    assert suite.status in ("passed", "failed")


def test_preprocessor_failure_still_closes_scenario_lifecycle() -> None:
    engine, archive, bus = _engine()
    seen: list[tuple[str, str]] = []
    bus.subscribe(lambda e: seen.append((e.event_type, getattr(e, "status", ""))),
                  event_type="scenario.start")
    bus.subscribe(lambda e: seen.append((e.event_type, getattr(e, "status", ""))),
                  event_type="scenario.end")
    # 模板变量不存在 → ScenarioPreprocessor.run 抛 ValueError
    result = engine.run(_scenario(
        "lc-prep", headers={"Authorization": "${var.no_such_key}"}))
    # 判定口径不变:聚合记 error 行
    assert result.error == 1 and result.exit_code != 0
    # 生命周期补齐:成对 start/end,end 的状态是 error
    assert [k for k, _ in seen] == ["scenario.start", "scenario.end"]
    assert seen[1][1] == "error"
    # 场景有归档且 status=error
    ctx = archive.get_scenario("lc-prep")
    assert ctx is not None and ctx.status == "error"
