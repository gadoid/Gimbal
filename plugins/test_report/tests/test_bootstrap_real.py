"""验收测试：真正走一遍 bootstrap 链路（含 mode=local 配置合并），
确认 gimbal-test-report 被加载、激活、并写出报告文件。

模拟用户的实际场景：
  - base_dir = 仓库根
  - plugins_dir = plugins  ← 默认值
  - plugins 白名单 = ['gimbal-test-report', 'gimbal-response-body-extract']
                       ← 来源 src/gimbal/config/mode/local.yml
  - plugin_configs['gimbal-test-report']['output_path'] = './reports/...'
                       ← 来源 src/gimbal/config/gimbal.yaml
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT / "plugins"))

import os
from datetime import datetime, timezone
from pathlib import Path

os.chdir(str(_ROOT))  # 让 _find_base_dir 找到 pyproject.toml

from gimbal.config.loader import ConfigLoader
from gimbal.cli.context import CLIContext
from gimbal.plugins.loader import PluginLoader
from gimbal.events import InMemoryEventBus
from gimbal.events.types import (
    RunStartEvent, RunEndEvent,
    ScenarioStartEvent, ScenarioEndEvent,
    StepStartEvent, StepEndEvent,
)
from gimbal.core.hooks import HookRegistry


def test_bootstrap_real_world(tmp_path):
    """Walk through real bootstrap:
      1. ConfigLoader → BootstrapConfig
      2. PluginLoader with enabled_filter=set(cfg.plugins) → 3 specs
      3. activate_all(..., user_configs=cfg.plugin_configs)
      4. publish events → flush → file on disk
    """
    out = tmp_path / "demo-real-bootstrap.html"

    cfg = ConfigLoader().load(CLIContext())
    print("base_dir      =", cfg.base_dir)
    print("plugins       =", cfg.plugins)
    print("plugin_configs=", cfg.plugin_configs)

    # 验证 config 已经包含 gimbal-test-report
    assert "gimbal-test-report" in cfg.plugins, \
        f"plugin not whitelisted: {cfg.plugins}"
    assert "gimbal-test-report" in cfg.plugin_configs, \
        f"plugin config missing: {cfg.plugin_configs.keys()}"

    # 验证插件目录能找到
    plugins_dir = cfg.base_dir / cfg.plugins_dir
    assert (plugins_dir / "test_report" / "plugin.yaml").exists()

    # 验证 PluginLoader 能 discover（只查白名单内的）
    loader = PluginLoader(plugins_dir=plugins_dir,
                           enabled_filter=set(cfg.plugins) or None)
    specs = loader.discover()
    names = [s.name for s in specs]
    print("discovered    =", names)
    assert "gimbal-test-report" in names

    # resolve_deps / load_all / activate_all —— 但 output_path 替成 tmp_path
    user_cfg = dict(cfg.plugin_configs)
    user_cfg["gimbal-test-report"] = {
        **user_cfg["gimbal-test-report"],
        "output_path": str(out),  # 写到 tmp_path，不污染仓库
    }
    specs = loader.resolve_deps(specs)
    plugins = loader.load_all(specs)
    bus = InMemoryEventBus()
    activated = loader.activate_all(
        plugins,
        event_bus=bus,
        hook_registry=HookRegistry(),
        user_configs=user_cfg,
    )
    activated_names = {p.name for p in activated}
    print("activated     =", activated_names)
    assert "gimbal-test-report" in activated_names

    # 触发事件流
    ts = lambda: datetime(2026, 7, 16, 13, 0, 0, tzinfo=timezone.utc)
    bus.publish(RunStartEvent(run_id="rb-1", env="dev", mode="local", timestamp=ts()))
    bus.publish(ScenarioStartEvent(
        run_id="rb-1", scenario_id="rb-sc", scenario_name="Real Bootstrap",
        step_count=2, timestamp=ts()
    ))
    bus.publish(StepStartEvent(
        run_id="rb-1", scenario_id="rb-sc", step_id="s1", step_name="step 1", timestamp=ts()
    ))
    bus.publish(StepEndEvent(
        run_id="rb-1", scenario_id="rb-sc", step_id="s1", status="passed",
        duration_ms=10, timestamp=ts()
    ))
    bus.publish(StepStartEvent(
        run_id="rb-1", scenario_id="rb-sc", step_id="s2", step_name="step 2", timestamp=ts()
    ))
    bus.publish(StepEndEvent(
        run_id="rb-1", scenario_id="rb-sc", step_id="s2", status="failed",
        duration_ms=20, error_brief="expected 200 got 500", timestamp=ts()
    ))
    bus.publish(ScenarioEndEvent(
        run_id="rb-1", scenario_id="rb-sc", status="failed", step_count=2, timestamp=ts()
    ))
    bus.publish(RunEndEvent(
        run_id="rb-1", total=2, passed=1, failed=1, error=0, timestamp=ts()
    ))
    bus.stop()

    assert out.exists(), f"expected report at {out}"
    text = out.read_text(encoding="utf-8")
    # 来自 gimbal.yaml::plugin_configs.title 注入
    assert "Gimbal Test Report" in text
    # scenario / step names
    assert "Real Bootstrap" in text
    assert "step 2" in text
    assert "expected 200 got 500" in text
