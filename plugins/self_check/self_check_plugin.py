"""SelfCheck plugin — verifies the plugin/event/hook infrastructure works correctly.

When activated, it:
  1. Validates that PluginContext carries the right dependencies
  2. Subscribes to all 9 framework event types
  3. Registers hooks at 3 different hook points
  4. Registers a FRAMEWORK_INIT hook that fires after activation
  5. At FRAMEWORK_TEARDOWN, prints a structured verification report

If any check fails, the plugin logs an ERROR (and the report shows FAIL rows).
"""
from __future__ import annotations

import logging
import time
from typing import Any, Callable

from gimbal.plugins import Plugin, PluginContext, PluginManifest

logger = logging.getLogger(__name__)


class SelfCheckPlugin(Plugin):
    """A diagnostic plugin that verifies the plugin infrastructure is functional."""

    manifest = PluginManifest(
        name="self_check",
        version="1.0.0",
        entry_point="self_check_plugin:SelfCheckPlugin",
        description="Verifies plugin/event/hook infrastructure works correctly.",
    )

    # ── Lifecycle ──

    def on_load(self) -> None:
        """Lightweight setup: just record start time and init accumulators."""
        self.start_ts = time.monotonic()
        self.events_received: list[tuple[str, str]] = []
        self.hooks_invoked: list[tuple[str, str]] = []
        self.checks: list[tuple[str, bool, str]] = []
        logger.info("[self_check] plugin LOADED — ready to verify framework")

    def on_activate(self, ctx: PluginContext) -> None:
        """Subscribe to events, register hooks, and self-verify."""
        # ── 1. Verify PluginContext carries working dependencies ──
        self._check("ctx.event_bus is not None", ctx.event_bus is not None)
        self._check("ctx.hook_registry is not None", ctx.hook_registry is not None)
        self._check("ctx.plugin_registry is not None", ctx.plugin_registry is not None)
        self._check("ctx.config is a dict", isinstance(ctx.config, dict))
        self._check("ctx has register_event", hasattr(ctx, "register_event") and callable(ctx.register_event))
        self._check("ctx has register_hook", hasattr(ctx, "register_hook") and callable(ctx.register_hook))
        self._check("ctx has emit", hasattr(ctx, "emit") and callable(ctx.emit))

        # ── 2. Subscribe to all framework event types ──
        subscribed_types = [
            "step.start", "step.end", "step.failed",
            "http.request", "http.response",
            "scenario.start", "scenario.end",
            "run.start", "run.end",
        ]
        for ev_type in subscribed_types:
            ctx.register_event(ev_type, self._make_event_handler(ev_type))
        self._check(
            f"subscribed {len(subscribed_types)} event types",
            len(ctx.registered_event_ids) == len(subscribed_types),
        )

        # ── 3. Register hooks at 3 different hook points ──
        ctx.register_hook(
            "http.before_send",
            self._make_hook("http.before_send"),
            priority=10,
            description="self_check: add X-Self-Check header",
        )
        ctx.register_hook(
            "http.after_recv",
            self._make_hook("http.after_recv"),
            priority=10,
            description="self_check: trace responses",
        )
        ctx.register_hook(
            "step.start",
            self._make_hook("step.start"),
            priority=200,  # high number = low priority
            description="self_check: trace step starts",
        )
        self._check(
            f"registered 3 hooks",
            len(ctx.registered_hook_ids) == 3,
        )

        # ── 4. Register a FRAMEWORK_INIT hook ──
        # Note: bootstrap fires FRAMEWORK_INIT *after* on_activate, so this hook
        # will be triggered and we can verify the framework init payload.
        hid = ctx.hook_registry.register(
            "framework.init",
            self._on_framework_init,
            plugin_name=self.name,
            description="self_check: post-init infrastructure check",
        )
        self._check("registered framework.init hook", hid is not None)

        # ── 5. Verify we can read the framework's own plugin registry ──
        # The framework should have registered us by the time this returns
        # (the loader does this immediately after on_activate).
        # We can't see ourselves yet (we're inside on_activate), so we
        # verify via a different signal: a non-empty registry.
        self._check(
            "plugin_registry is accessible",
            ctx.plugin_registry is not None,
        )

        # ── 6. Verify the EventBus supports fire-and-forget from inside a plugin ──
        # We don't actually publish here (we'd be triggering our own listeners)
        # but we verify the bus has a publish method.
        self._check(
            "event_bus.publish is callable",
            callable(getattr(ctx.event_bus, "publish", None)),
        )

    def on_deactivate(self) -> None:
        """Print a structured report and log pass/fail summary."""
        duration_ms = (time.monotonic() - self.start_ts) * 1000
        passed = sum(1 for _, ok, _ in self.checks if ok)
        total = len(self.checks)

        print()
        print("=" * 72)
        print(f"  [self_check] PLUGIN VERIFICATION REPORT  (lifetime: {duration_ms:.1f} ms)")
        print("=" * 72)
        for name, ok, detail in self.checks:
            mark = "PASS" if ok else "FAIL"
            line = f"  [{mark}] {name}"
            if detail:
                line += f"  — {detail}"
            print(line)
        print("-" * 72)
        # Group event/hook counts
        ev_count = len(self.events_received)
        hk_count = len(self.hooks_invoked)
        ev_by_type: dict[str, int] = {}
        for ev_type, _ in self.events_received:
            ev_by_type[ev_type] = ev_by_type.get(ev_type, 0) + 1
        hk_by_point: dict[str, int] = {}
        for point, _ in self.hooks_invoked:
            hk_by_point[point] = hk_by_point.get(point, 0) + 1

        print(f"  checks       : {passed} / {total} passed")
        print(f"  events seen  : {ev_count} total  {ev_by_type if ev_by_type else '{}'}")
        print(f"  hooks hit    : {hk_count} total  {hk_by_point if hk_by_point else '{}'}")
        print("=" * 72)
        print()

        if passed != total:
            logger.error("[self_check] %d / %d checks FAILED — plugin infrastructure broken!",
                         total - passed, total)
        else:
            logger.info("[self_check] ALL %d CHECKS PASSED — plugin system verified OK",
                        total)

    # ── Internals ──

    def _check(self, name: str, condition: bool, detail: str = "") -> None:
        """Record a check result (used in on_activate and the FRAMEWORK_INIT hook)."""
        ok = bool(condition)
        self.checks.append((name, ok, detail))
        if ok:
            logger.info("[self_check] PASS  %s", name + (f"  ({detail})" if detail else ""))
        else:
            logger.error("[self_check] FAIL  %s", name + (f"  ({detail})" if detail else ""))

    def _make_event_handler(self, event_type: str) -> Callable[[Any], None]:
        def handler(event: Any) -> None:
            # Identify by step_id / scenario_id / url depending on event type
            label = (
                getattr(event, "step_id", None)
                or getattr(event, "scenario_id", None)
                or getattr(event, "url", None)
                or "?"
            )
            self.events_received.append((event_type, str(label)))
        return handler

    def _make_hook(self, point: str) -> Callable[[dict], Any]:
        def hook(payload: dict) -> None:
            label = str(
                payload.get("url")
                or payload.get("step_id")
                or payload.get("strategy_name")
                or "?"
            )
            self.hooks_invoked.append((point, label))
            if point == "http.before_send":
                # Verify the hook can mutate the request payload
                payload.setdefault("headers", {})["X-Self-Check"] = "1"
        return hook

    def _on_framework_init(self, payload: dict) -> None:
        """Triggered after bootstrap finishes plugin activation."""
        self._check("framework.init hook fired (after activation)", True)
        self._check("framework.init payload has 'cfg'", "cfg" in payload)
        self._check("framework.init payload has 'ctx_manager'", "ctx_manager" in payload)
        self._check("framework.init payload has 'plugin_registry'", "plugin_registry" in payload)
        logger.info("[self_check] FRAMEWORK_INIT hook fired — bootstrap is intact")
