"""Comprehensive integration test for the new Plugin/Event infrastructure."""
import sys
import os
import time
import textwrap
import shutil
import pathlib
import tempfile
import inspect

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

print("=" * 60)
print("FINAL INTEGRATION TEST: All new infrastructure")
print("=" * 60)

# 1. Hook system
print()
print("[1] Hook system")
from gimbal.core.hooks import HookPoint, HookRegistry, HookSignal

reg = HookRegistry()
hits = []
reg.register(HookPoint.STEP_START, lambda p: hits.append(("a", p.get("step_id"))), priority=10)
reg.register(HookPoint.STEP_START, lambda p: hits.append(("b", p.get("step_id"))), priority=20)


def _stop(p):
    raise HookSignal.STOP("demo")


reg.register(HookPoint.STEP_START, _stop, priority=30)
r = reg.trigger(HookPoint.STEP_START, {"step_id": "s1"})
print(f"  hits={hits} stopped={r.stopped} reason={r.stop_reason}")
assert hits == [("a", "s1"), ("b", "s1")] and r.stopped
print("  PASS")

# 2. Event bus
print()
print("[2] Event bus with all subscription modes")
from gimbal.events import InMemoryEventBus, SubscriptionMode, StepStartEvent

bus = InMemoryEventBus()
log = []
bus.subscribe(lambda e: log.append(("sync", e.step_id)), mode=SubscriptionMode.SYNC)
bus.subscribe(lambda e: log.append(("async", e.step_id)), mode=SubscriptionMode.ASYNC)
bus.subscribe(lambda e: log.append(("batch", e.step_id)), mode=SubscriptionMode.BATCH)
bus.start_batch_loop()
bus.publish(StepStartEvent(step_id="s1", step_name="x"))
bus.publish(StepStartEvent(step_id="s2", step_name="y"))
time.sleep(0.1)
bus.stop()
print(f"  log={sorted(log)}")
assert ("sync", "s1") in log and ("sync", "s2") in log
print("  PASS")

# 3. Plugin loader + manifest + activate
print()
print("[3] Plugin loader end-to-end")
from gimbal.plugins import PluginLoader, PluginManifest, Plugin

tmp = tempfile.mkdtemp(prefix="gimbal_test_")
try:
    pdir = pathlib.Path(tmp) / "plugins" / "demo"
    pdir.mkdir(parents=True)
    (pdir / "plugin.yaml").write_text(textwrap.dedent("""
        name: demo
        version: 0.1.0
        entry_point: demo_plugin:DemoPlugin
        category: generic
    """), encoding="utf-8")
    (pdir / "demo_plugin.py").write_text(textwrap.dedent("""
        from gimbal.plugins import Plugin, PluginManifest
        class DemoPlugin(Plugin):
            manifest = PluginManifest(name="demo", version="0.1.0", entry_point="demo_plugin:DemoPlugin")
            def on_activate(self, ctx):
                self.events = []
                ctx.register_event("scenario.start", lambda e: self.events.append(e.scenario_id))
                def h(p):
                    p["seen"] = True
                    return p  # 修复 #15：in-place 修改需显式 return 才被识别为 modified
                ctx.register_hook("step.start", h, priority=10)
    """), encoding="utf-8")

    loader = PluginLoader(plugins_dir=pathlib.Path(tmp) / "plugins")
    specs = loader.discover()
    assert len(specs) == 1, specs
    specs = loader.resolve_deps(specs)
    plugins = loader.load_all(specs)
    assert len(plugins) == 1
    bus2 = InMemoryEventBus()
    hr2 = HookRegistry()
    activated = loader.activate_all(plugins, event_bus=bus2, hook_registry=hr2)
    assert len(activated) == 1
    p = activated[0]
    assert p.name == "demo"
    from gimbal.events import ScenarioStartEvent
    bus2.publish(ScenarioStartEvent(scenario_id="sc1", scenario_name="x", step_count=1))
    r2 = hr2.trigger(HookPoint.STEP_START, {})
    assert r2.modified is True
    print(f"  plugin received events: {p.events}")
    print(f"  hook modified: {r2.modified}")
    print("  PASS")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# 4. State machine hook integration (smoke test)
print()
print("[4] State machine accepts hook_registry and event_bus parameters")
from gimbal.statemachine.engine import StepStateMachine

sig = inspect.signature(StepStateMachine.__init__)
assert "hook_registry" in sig.parameters
assert "event_bus" in sig.parameters
print(f"  StepStateMachine.__init__ params: {list(sig.parameters.keys())}")
print("  PASS")

# 5. Dispatcher accepts hook_registry
print()
print("[5] StrategyDispatcher accepts hook_registry")
from gimbal.strategy.dispatcher import StrategyDispatcher

sig2 = inspect.signature(StrategyDispatcher.__init__)
assert "hook_registry" in sig2.parameters
print(f"  StrategyDispatcher.__init__ params: {list(sig2.parameters.keys())}")
print("  PASS")

# 6. ScenarioRunner accepts hook_registry and event_bus
print()
print("[6] ScenarioRunner accepts hook_registry and event_bus")
from gimbal.core.scenario_runner import ScenarioRunner

sig3 = inspect.signature(ScenarioRunner.__init__)
assert "hook_registry" in sig3.parameters
assert "event_bus" in sig3.parameters
print(f"  ScenarioRunner.__init__ params: {list(sig3.parameters.keys())}")
print("  PASS")

# 7. Configuration contains all infrastructure
print()
print("[7] Configuration contains all infrastructure")
from gimbal.core.bootstrap import Configuration
import dataclasses
fields = {f.name for f in dataclasses.fields(Configuration)}
for f in ("cfg", "ctx_manager", "dispatcher", "event_bus", "archive",
         "hook_registry", "plugin_registry", "plugins"):
    assert f in fields, f"missing {f}"
print(f"  Configuration fields: {sorted(fields)}")
print("  PASS")

# 8. BootstrapConfig has plugin user-config field
print()
print("[8] BootstrapConfig has plugin user-config field")
from gimbal.config.models import BootstrapConfig
bc_fields = BootstrapConfig.model_fields
assert "plugin_configs" in bc_fields
assert "plugins_dir" in bc_fields
print(f"  plugin fields: plugin_configs, plugins_dir")
print("  PASS")

print()
print("=" * 60)
print("ALL INTEGRATION TESTS PASSED")
print("=" * 60)
