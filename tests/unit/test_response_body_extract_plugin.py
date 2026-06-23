"""Smoke test: load the new plugin, activate it, and verify the
HTTP_AFTER_RECV hook is registered.

This is a minimal end-to-end test:
  1. Build a PluginContext (bus + hook registry)
  2. Activate the plugin
  3. Fire a fake HTTP_AFTER_RECV payload with a stub view
  4. Verify the plugin wrote the configured scratch key

Run:
    cd d:\\Gimbal\\Gimbal
    python -m pytest tests/unit/test_response_body_extract_plugin.py -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent.parent
sys.path.insert(0, str(_REPO / "src"))
sys.path.insert(0, str(_REPO / "plugins" / "response_body_extract"))

from gimbal.core.plugin import PluginContext          # noqa: E402
from gimbal.core.hooks import HookPoint, HookRegistry   # noqa: E402
from gimbal.events.bus import InMemoryEventBus          # noqa: E402

from gimbal_response_body_extract.plugin import ResponseBodyExtractPlugin  # noqa: E402


# ── 桩 StepContextAdapter ────────────────────────────

class _StubView:
    """最小的 StepContextAdapter 替身：只暴露插件会用到的 scratch API。"""

    def __init__(self) -> None:
        self._scratch: dict[str, Any] = {}

    def write_scratch(self, key: str, value: Any) -> None:
        self._scratch[key] = value

    def read_scratch(self, key: str, default: Any = None) -> Any:
        return self._scratch.get(key, default)


# ── 测试用例 ──────────────────────────────────────

class TestResponseBodyExtractPlugin(unittest.TestCase):

    def _make_ctx(self, config: dict | None = None) -> PluginContext:
        bus = InMemoryEventBus()
        hooks = HookRegistry()
        return PluginContext(
            plugin_name="gimbal-response-body-extract",
            config=config or {},
            event_bus=bus,
            hook_registry=hooks,
        )

    def test_manifest_declares_generic_capability(self) -> None:
        m = ResponseBodyExtractPlugin.manifest
        self.assertEqual(m.name, "gimbal-response-body-extract")
        self.assertIn("generic", m.capabilities)

    def _activate(self, p: ResponseBodyExtractPlugin, config: dict) -> PluginContext:
        """辅助：完成 load → activate 两步，返回 ctx。"""
        p.load()
        ctx = self._make_ctx(config)
        p.activate(ctx)
        return ctx

    def test_default_config_values(self) -> None:
        p = ResponseBodyExtractPlugin()
        ctx = self._activate(p, {})  # empty → fall back to default_config
        try:
            self.assertEqual(p._target, "response_body")
            self.assertEqual(p._on_missing, "warn")
            self.assertTrue(p._overwrite)
        finally:
            p.deactivate()

    def test_user_config_overrides_defaults(self) -> None:
        p = ResponseBodyExtractPlugin()
        self._activate(p, {
            "target": "body",
            "on_missing": "raise",
            "overwrite": False,
        })
        try:
            self.assertEqual(p._target, "body")
            self.assertEqual(p._on_missing, "raise")
            self.assertFalse(p._overwrite)
        finally:
            p.deactivate()

    def test_hook_registers_http_after_recv(self) -> None:
        p = ResponseBodyExtractPlugin()
        ctx = self._activate(p, {})
        try:
            hooks = ctx.hook_registry.list_hooks(point=HookPoint.HTTP_AFTER_RECV)
            names = {h.plugin_name for h in hooks}
            self.assertIn("gimbal-response-body-extract", names)
        finally:
            p.deactivate()

    def test_hook_extracts_response_body_into_scratch(self) -> None:
        """核心场景：response_body 在 scratch 中，钩子应写入 target key。"""
        p = ResponseBodyExtractPlugin()
        ctx = self._activate(p, {"target": "resp"})
        try:
            view = _StubView()
            view.write_scratch("response_body", {"code": 0, "data": "ok"})

            payload = {
                "method": "POST",
                "url": "http://example/api",
                "status": "passed",
                "step_id": "step-001",
                "ctx": view,
            }
            res = ctx.hook_registry.trigger(HookPoint.HTTP_AFTER_RECV, payload)

            self.assertFalse(res.stopped)
            self.assertEqual(view.read_scratch("resp"), {"code": 0, "data": "ok"})
            self.assertEqual(p.stats["extracted"], 1)
        finally:
            p.deactivate()

    def test_hook_warns_when_response_body_missing(self) -> None:
        p = ResponseBodyExtractPlugin()
        ctx = self._activate(p, {"on_missing": "warn"})
        try:
            view = _StubView()  # scratch 为空
            payload = {
                "method": "GET",
                "url": "http://example/api",
                "status": "passed",
                "step_id": "step-002",
                "ctx": view,
            }
            res = ctx.hook_registry.trigger(HookPoint.HTTP_AFTER_RECV, payload)

            self.assertFalse(res.stopped)
            self.assertIsNone(view.read_scratch("response_body"))
            self.assertEqual(p.stats["missing"], 1)
            self.assertEqual(p.stats["extracted"], 0)
        finally:
            p.deactivate()

    def test_hook_raise_when_response_body_missing(self) -> None:
        p = ResponseBodyExtractPlugin()
        ctx = self._activate(p, {"on_missing": "raise"})
        try:
            view = _StubView()
            payload = {
                "method": "GET",
                "url": "http://example/api",
                "status": "passed",
                "step_id": "step-003",
                "ctx": view,
            }
            res = ctx.hook_registry.trigger(HookPoint.HTTP_AFTER_RECV, payload)

            self.assertTrue(res.stopped, "on_missing=raise should STOP the hook chain")
            self.assertEqual(p.stats["raised"], 1)
        finally:
            p.deactivate()

    def test_overwrite_false_skips_existing_target(self) -> None:
        p = ResponseBodyExtractPlugin()
        ctx = self._activate(p, {"target": "resp", "overwrite": False})
        try:
            view = _StubView()
            view.write_scratch("response_body", {"new": 1})
            view.write_scratch("resp", {"old": 999})

            payload = {
                "method": "GET",
                "url": "http://x",
                "status": "passed",
                "step_id": "step-004",
                "ctx": view,
            }
            ctx.hook_registry.trigger(HookPoint.HTTP_AFTER_RECV, payload)

            # overwrite=False 时不应覆盖已存在的值
            self.assertEqual(view.read_scratch("resp"), {"old": 999})
            # 但 extracted 计数也不应增加（语义：跳过 = 无副作用）
            self.assertEqual(p.stats["extracted"], 0)
        finally:
            p.deactivate()

    def test_overwrite_true_replaces_existing_target(self) -> None:
        p = ResponseBodyExtractPlugin()
        ctx = self._activate(p, {"target": "resp", "overwrite": True})
        try:
            view = _StubView()
            view.write_scratch("response_body", {"new": 1})
            view.write_scratch("resp", {"old": 999})

            payload = {
                "method": "GET",
                "url": "http://x",
                "status": "passed",
                "step_id": "step-005",
                "ctx": view,
            }
            ctx.hook_registry.trigger(HookPoint.HTTP_AFTER_RECV, payload)

            self.assertEqual(view.read_scratch("resp"), {"new": 1})
            self.assertEqual(p.stats["extracted"], 1)
            self.assertEqual(p.stats["overwritten"], 1)
        finally:
            p.deactivate()

    def test_invalid_config_falls_back_to_defaults(self) -> None:
        p = ResponseBodyExtractPlugin()
        self._activate(p, {"target": "", "on_missing": "BAD"})
        try:
            self.assertEqual(p._target, "response_body")  # fall back
            self.assertEqual(p._on_missing, "warn")       # fall back
        finally:
            p.deactivate()


if __name__ == "__main__":
    unittest.main()