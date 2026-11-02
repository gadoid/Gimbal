"""RunMetaEvent 时序（全量评估 2026-11-02 #4）：真实 Engine.run 路径下 HTML
reporter 能收到 run.meta。

此前 CLI 在 Engine.run 之前 publish，而 reporter 的订阅发生在 Engine.run 内
的 reporter_runtime.begin_all，总线无回放 → HTML/JSON 报告永远拿不到
CI/Git/触发人。单测只直调 r.on_event 掩盖了这一点，本文件走真实接缝：
Configuration.run_meta → Engine._emit_run_meta（begin_all 之后）→ reporter。
"""
from __future__ import annotations

import os
import sys
import tempfile
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
from gimbal.reporter.builtin import register_builtin_reporters
from gimbal.reporter.registry import ReporterRegistry
from gimbal.reporter.runtime import ReporterRuntime
from gimbal.schema import Call, Config as SC, Meta, Scenario, Step
from gimbal.strategy.dispatcher import build_default_dispatcher


def _scenario() -> Scenario:
    return Scenario(
        scenarioId="meta-sc",
        meta=Meta(name="n", description="d", module="m", priority=1, author="a",
                  owner="o", tags=[], version="1",
                  createTime=datetime.now(timezone.utc), expire=False,
                  requirementRef=[]),
        config=SC(setup=[], teardown=[], timePolicy=None),
        resource={},
        steps=[Step(call=Call(protocol="http", service="s", method="GET",
                              path="/x"), strategy=[])],
    )


def _engine(report_dir: str, run_meta: dict | None) -> tuple[Engine, ReporterRuntime]:
    bus = InMemoryEventBus()
    hooks = HookRegistry()
    dispatcher = build_default_dispatcher(hook_registry=hooks, event_bus=bus)
    cfg = BootstrapConfig(env="test", mode="local", log_level="error",
                          reporters=("html",), report_dir=report_dir)
    registry = ReporterRegistry()
    register_builtin_reporters(registry)
    runtime = ReporterRuntime(registry)
    runtime.setup(bus=bus, config=cfg)
    conf = Configuration(
        cfg=cfg, auth_registry=AuthRegistry(),
        ctx_manager=ContextManager(archive=InMemoryArchive(), event_bus=bus),
        dispatcher=dispatcher, event_bus=bus, archive=InMemoryArchive(),
        hook_registry=hooks, plugin_registry=PluginRegistry(), plugins=(),
        reporter_runtime=runtime, protocols=dispatcher.protocols,
        run_meta=run_meta,
    )
    return Engine(conf), runtime


def test_html_reporter_receives_run_meta_through_real_engine_run() -> None:
    meta = {"ci": True, "branch": "feat/x", "commit": "abc123def456",
            "triggered_by": "alice", "build_url": "https://ci/1"}
    with tempfile.TemporaryDirectory() as td:
        engine, runtime = _engine(td, meta)
        engine.run(_scenario())
        html = next(r for r in runtime._reporters if getattr(r, "name", "") == "html")
        assert html._run_meta == meta
        # 落盘的报告头部带上了元数据 pill
        files = [os.path.join(dp, f) for dp, _, fs in os.walk(td) for f in fs
                 if f.endswith(".html")]
        assert files, "html 报告未生成"
        body = open(files[0], encoding="utf-8").read()
        assert "feat/x" in body and "alice" in body


def test_run_meta_none_publishes_nothing() -> None:
    with tempfile.TemporaryDirectory() as td:
        engine, runtime = _engine(td, None)
        engine.run(_scenario())
        html = next(r for r in runtime._reporters if getattr(r, "name", "") == "html")
        assert html._run_meta == {}
