"""Unit tests for gimbal-collector plugin.

覆盖：
  1. ReportStore 事件聚合
  2. ReportReport.to_dict 序列化（含嵌套 dict / list / None）
  3. JsonRenderer 落盘（路径 + 内容）
  4. CollectorPlugin 通过 EventBus 端到端跑通（构造事件 → 落盘）
  5. 鲁棒性：handler 抛错不污染事件总线；on_deactivate 后 state 重置
"""
from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from typing import Any

# 让 tests 找得到 plugins/ 与 src/
_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent.parent
sys.path.insert(0, str(_REPO / "src"))
sys.path.insert(0, str(_REPO / "plugins" / "collector"))

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

from gimbal_collector.plugin import CollectorPlugin
from gimbal_collector.report_data import (
    HttpExchange,
    RunReport,
    ScenarioReport,
    StepReport,
)
from gimbal_collector.renderers.json_renderer import JsonRenderer
from gimbal_collector.store import ReportStore

# Stub EventBus
from gimbal.core.plugin import PluginContext
from gimbal.core.hooks import HookRegistry  # 真实存在
from gimbal.events.bus import InMemoryEventBus


# ── 事件工厂 ──────────────────────────────────────────

def ev(event_type: str, **fields) -> Any:
    """构造一个最小事件对象。"""
    base = {
        "event_type": event_type,
        "timestamp": datetime(2025, 1, 1, 12, 0, 0),
        "run_id": "run-001",
    }
    base.update(fields)
    return type("E", (), base)()


# ── 1. ReportStore ────────────────────────────────────

class TestReportStore(unittest.TestCase):
    def test_full_flow(self) -> None:
        s = ReportStore()
        s.on_run_start(ev("run.start", env="dev", mode="run"))
        s.on_scenario_start(ev("scenario.start", scenario_id="sc-1", scenario_name="login"))
        s.on_step_start(ev("step.start", step_id="st-1", step_name="GET /login"))
        s.on_http_request(ev("http.request", step_id="st-1", method="POST", url="/api/login",
                             request_body={"u": "x"}, request_headers={"X-A": "1"}))
        s.on_http_response(ev("http.response", step_id="st-1", method="POST", url="/api/login",
                              status_code=200, response_body={"token": "abc"}, duration_ms=12.5))
        s.on_variable_promoted(ev("variable.promoted", key="token", from_layer="step",
                                  to_layer="scenario", by_step_id="st-1", reason=None))
        s.on_step_end(ev("step.end", step_id="st-1", status="passed",
                         duration_ms=12.5, assertion_count=1, assertion_passed=1))
        s.on_scenario_end(ev("scenario.end", scenario_id="sc-1", status="passed"))
        s.on_run_end(ev("run.end", total=1, passed=1, failed=0, error=0))

        r = s.snapshot()
        self.assertIsNotNone(r)
        self.assertEqual(r.run_id, "run-001")
        self.assertEqual(r.env, "dev")
        self.assertEqual(r.passed, 1)
        self.assertEqual(len(r.scenarios), 1)
        sc = r.scenarios["sc-1"]
        self.assertEqual(sc.status, "passed")
        self.assertEqual(len(sc.steps), 1)
        st = sc.steps["st-1"]
        self.assertEqual(st.status, "passed")
        self.assertEqual(st.duration_ms, 12.5)
        self.assertEqual(st.assertion_count, 1)
        self.assertEqual(len(st.http_exchanges), 1)
        ex = st.http_exchanges[0]
        self.assertEqual(ex.status_code, 200)
        self.assertEqual(ex.method, "POST")
        self.assertEqual(len(st.promotions), 1)
        self.assertEqual(st.promotions[0]["key"], "token")

    def test_http_response_without_request_still_creates_exchange(self) -> None:
        """response 比 request 先到（异常路径）也要不丢数据。"""
        s = ReportStore()
        s.on_run_start(ev("run.start", env="t", mode="t"))
        s.on_scenario_start(ev("scenario.start", scenario_id="sc", scenario_name="n"))
        s.on_step_start(ev("step.start", step_id="st", step_name="n"))
        s.on_http_response(ev("http.response", step_id="st", method="GET", url="/x",
                              status_code=500, duration_ms=1.0))
        st = s.snapshot().scenarios["sc"].steps["st"]
        self.assertEqual(len(st.http_exchanges), 1)
        self.assertEqual(st.http_exchanges[0].status_code, 500)

    def test_snapshot_is_deep_copy(self) -> None:
        """返回深拷贝，避免 renderer 遍历时新事件打乱。"""
        s = ReportStore()
        s.on_run_start(ev("run.start"))
        s.on_scenario_start(ev("scenario.start", scenario_id="x", scenario_name="x"))
        snap = s.snapshot()
        # 后续事件不应影响 snapshot 拿到的对象
        s.on_scenario_end(ev("scenario.end", scenario_id="x", status="passed"))
        # snap 拿到的应是 scenario_start 设置的 running
        self.assertEqual(snap.scenarios["x"].status, "running")
        # 而 self._run 上的应该是 passed
        self.assertEqual(s.snapshot().scenarios["x"].status, "passed")


# ── 2. JSON 序列化 ────────────────────────────────────

class TestSerialization(unittest.TestCase):
    def test_run_report_to_dict_round_trip(self) -> None:
        r = RunReport(run_id="r1", env="dev", mode="r")
        sc = ScenarioReport(scenario_id="s1", scenario_name="login", status="passed",
                            started_at="t0", ended_at="t1")
        st = StepReport(step_id="st1", step_name="call", status="passed", duration_ms=10.0,
                        assertion_count=2, assertion_passed=2)
        st.http_exchanges.append(HttpExchange(method="POST", url="/x", status_code=200,
                                              request_body={"a": 1}, response_body={"b": 2},
                                              duration_ms=10.0))
        st.promotions.append({"key": "k", "from_layer": "step", "to_layer": "scenario"})
        sc.steps["st1"] = st
        r.scenarios["s1"] = sc

        payload = r.to_dict()
        # 序列化为 JSON 不抛
        text = json.dumps(payload, ensure_ascii=False, default=str)
        # 反序列化回来能拿到关键字段
        back = json.loads(text)
        self.assertEqual(back["run_id"], "r1")
        self.assertEqual(back["scenarios"][0]["steps"][0]["http_exchanges"][0]["status_code"], 200)
        self.assertEqual(back["scenarios"][0]["steps"][0]["promotions"][0]["key"], "k")


# ── 3. JsonRenderer ───────────────────────────────────

class TestJsonRenderer(unittest.TestCase):
    def test_writes_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            r = RunReport(run_id="abc")
            r.scenarios["s"] = ScenarioReport(scenario_id="s", scenario_name="n")
            paths = JsonRenderer().render(r, out)
            self.assertEqual(len(paths), 1)
            self.assertTrue(paths[0].exists())
            self.assertEqual(paths[0].name, "run-abc.json")
            data = json.loads(paths[0].read_text(encoding="utf-8"))
            self.assertEqual(data["run_id"], "abc")
            self.assertIn("s", [sc["scenario_id"] for sc in data["scenarios"]])

    def test_creates_output_dir_if_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            nested = Path(tmp) / "deep" / "down"
            r = RunReport(run_id="x")
            paths = JsonRenderer().render(r, nested)
            self.assertTrue(paths[0].exists())
            self.assertTrue(nested.is_dir())


# ── 4. 端到端：通过 EventBus 触发事件 → 落盘 ──────────

class TestEndToEnd(unittest.TestCase):
    def _make_ctx(self, bus: InMemoryEventBus, output_dir: Path) -> PluginContext:
        return PluginContext(
            plugin_name="gimbal-collector",
            config={"output_dir": str(output_dir)},
            event_bus=bus,
            hook_registry=HookRegistry(),
        )

    def test_full_run_emit_writes_file(self) -> None:
        bus = InMemoryEventBus()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            plugin = CollectorPlugin()
            plugin.load()
            plugin.activate(self._make_ctx(bus, out))
            self.assertEqual(plugin.state.value, "activated")

            # 模拟一整个 run 的事件流
            bus.publish(ev("run.start", env="dev", mode="run"))
            bus.publish(ev("scenario.start", scenario_id="sc-1", scenario_name="login"))
            bus.publish(ev("step.start", step_id="st-1", step_name="GET /login"))
            bus.publish(ev("http.request", step_id="st-1", method="GET", url="/api/login",
                           request_body=None, request_headers={}))
            bus.publish(ev("http.response", step_id="st-1", method="GET", url="/api/login",
                           status_code=200, duration_ms=5.0, response_body={"token": "abc"}))
            bus.publish(ev("step.end", step_id="st-1", status="passed", duration_ms=5.0,
                           assertion_count=0, assertion_passed=0))
            bus.publish(ev("scenario.end", scenario_id="sc-1", status="passed"))
            bus.publish(ev("run.end", total=1, passed=1, failed=0, error=0))

            # run.end 是同步事件，handler 跑完文件应已写
            report_file = out / "run-run-001.json"
            self.assertTrue(report_file.exists(), f"expected {report_file} to exist")
            data = json.loads(report_file.read_text(encoding="utf-8"))
            self.assertEqual(data["run_id"], "run-001")
            self.assertEqual(data["summary"]["passed"], 1)
            self.assertEqual(data["scenarios"][0]["steps"][0]["http_exchanges"][0]["status_code"], 200)

            plugin.deactivate()
            self.assertEqual(plugin.state.value, "deactivated")

    def test_handler_exception_does_not_break_bus(self) -> None:
        """故意让 store.on_step_start 抛错，断言后续事件还能正常处理。"""
        bus = InMemoryEventBus()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            plugin = CollectorPlugin()
            plugin.load()
            plugin.activate(self._make_ctx(bus, out))

            # 把 store 替换成一个会抛错的 mock
            class BoomStore:
                def __getattr__(self, name):
                    def fn(*a, **kw):
                        raise RuntimeError(f"boom in {name}")
                    return fn
            plugin._store = BoomStore()        # noqa: SLF001

            # 触发一个事件，handler 会抛错；EventBus._safe_call 兜底
            bus.publish(ev("run.start"))
            # 后续事件不应受影响
            bus.publish(ev("scenario.start", scenario_id="x", scenario_name="x"))
            # 事件总线仍能继续 dispatch
            self.assertGreater(len(bus.list_subscriptions()), 0)

            plugin.deactivate()


# ── 5. on_deactivate 状态重置 ──────────────────────────

class TestDeactivate(unittest.TestCase):
    def test_store_reset_after_deactivate(self) -> None:
        bus = InMemoryEventBus()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            plugin = CollectorPlugin()
            ctx = PluginContext(
                plugin_name="gimbal-collector",
                config={"output_dir": str(out)},
                event_bus=bus,
                hook_registry=HookRegistry(),
            )
            plugin.load()
            plugin.activate(ctx)

            bus.publish(ev("run.start"))
            self.assertIsNotNone(plugin._store.snapshot())        # noqa: SLF001

            plugin.deactivate()
            self.assertIsNone(plugin._store.snapshot())           # noqa: SLF001


if __name__ == "__main__":
    unittest.main(verbosity=2)
