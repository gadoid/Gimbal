"""端到端 demo：用真实 PluginLoader 发现 → activate → 触发事件 → 验证文件。

不通过 gimbal bootstrap()（依赖过多），直接模拟：
  - 把插件目录指向我们这个测试插件
  - 让 PluginLoader.discover / load_all / activate_all 走通
  - 通过 InMemoryEventBus 发事件
  - 断言 output_path 写出文件

这同时也是开发期的"如何用"的最小可运行样例。
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT / "plugins"))

from datetime import datetime, timezone

from gimbal.plugins.loader import PluginLoader
from gimbal.events import InMemoryEventBus
from gimbal.events.types import (
    RunStartEvent, RunEndEvent,
    ScenarioStartEvent, ScenarioEndEvent,
    StepStartEvent, StepEndEvent,
)
from gimbal.core.hooks import HookRegistry


def _ts() -> datetime:
    return datetime(2026, 7, 16, 11, 0, 0, tzinfo=timezone.utc)


def test_e2e_via_plugin_loader(tmp_path):
    """模拟用户场景：
        1. 用户把 plugin.yaml 放到 tmp_path / report_demo / plugin.yaml
        2. BootstrapConfig.plugin_configs["gimbal-test-report"]["output_path"] = ...
        3. PluginLoader(plugins_dir=tmp_path) 找到插件
        4. activate_all(plugins, user_configs={...}) 把 output_path 注进去
        5. 我们触发事件流 → 报告落盘
    """
    # 1. 把现有插件 "gimbal-test-report" 软链/复制一个入口到 tmp_path
    #    —— 但本测试更简单：直接用 PluginLoader 加载 test_report 插件类
    #    （覆盖 PluginLoader 的 entry_point 路径）
    loader = PluginLoader(plugins_dir=tmp_path)

    # 直接手动构造 PluginSpec（跳过 .yaml 解析这一步,因为我们已经知道 entry_point）
    from gimbal.plugins.spec import PluginSpec
    from gimbal.plugins.categories import PluginCategory

    spec = PluginSpec(
        name="gimbal-test-report",
        version="0.1.0",
        entry_point="test_report.plugin:ReportPlugin",
        category=PluginCategory.REPORTER,
        capabilities=["reporter"],
        default_config={
            "output_path": "./reports/test-report.html",
            "title": "Gimbal Test Report",
            "include_passed": True,
        },
        source="inline",
        enabled=True,
    )

    specs = loader.resolve_deps([spec])
    plugins = loader.load_all(specs)
    assert len(plugins) == 1
    p = plugins[0]

    # 2. activate_all — 注入合并后的 user_configs
    out = tmp_path / "demo-report.html"
    user_configs = {"gimbal-test-report": {"output_path": str(out), "title": "E2E Demo"}}
    bus = InMemoryEventBus()
    hook_reg = HookRegistry()

    activated = loader.activate_all(
        plugins,
        event_bus=bus,
        hook_registry=hook_reg,
        user_configs=user_configs,
    )
    assert len(activated) == 1
    assert activated[0].ctx.config["title"] == "E2E Demo"

    # 3. 跑一遍事件流
    bus.publish(RunStartEvent(run_id="e2e-1", env="dev", mode="ci", timestamp=_ts()))
    bus.publish(ScenarioStartEvent(
        run_id="e2e-1", scenario_id="demo_sc", scenario_name="Plugin Demo", step_count=2,
        timestamp=_ts()
    ))
    bus.publish(StepStartEvent(
        run_id="e2e-1", scenario_id="demo_sc", step_id="ds1", step_name="verify plugin", timestamp=_ts()
    ))
    bus.publish(StepEndEvent(
        run_id="e2e-1", scenario_id="demo_sc", step_id="ds1", status="passed",
        duration_ms=42, assertion_count=1, assertion_passed=1, timestamp=_ts(),
    ))
    bus.publish(StepStartEvent(
        run_id="e2e-1", scenario_id="demo_sc", step_id="ds2", step_name="write file", timestamp=_ts()
    ))
    bus.publish(StepEndEvent(
        run_id="e2e-1", scenario_id="demo_sc", step_id="ds2", status="passed",
        duration_ms=15, timestamp=_ts(),
    ))
    bus.publish(ScenarioEndEvent(
        run_id="e2e-1", scenario_id="demo_sc", status="passed", step_count=2, timestamp=_ts(),
    ))
    bus.publish(RunEndEvent(
        run_id="e2e-1", total=2, passed=2, failed=0, error=0, timestamp=_ts(),
    ))
    bus.stop()

    # 4. 验证产出
    assert out.exists(), f"expected report at {out}"
    text = out.read_text(encoding="utf-8")
    assert "E2E Demo" in text
    assert "Plugin Demo" in text
    assert "verify plugin" in text
    assert "write file" in text
    assert ">2<" in text   # total
