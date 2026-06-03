"""gimbal self-check — 框架自检（集成测试级别）。

设计原则：
    - 这是**集成测试**，不是插件。不走 PluginLoader 流水线。
    - 直接 bootstrap 框架，然后手动 exercise event_bus / hook_registry。
    - 退出码：0 = 全部通过；非 0 = 有失败（CI 友好）。

替代了原来的 plugins/self_check/ —— 后者把框架自检伪装成插件，
混淆了"扩展点"和"基础设施自检"两个概念。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable

import typer

# 注意：不能从 gimbal.cli.params 顶层导入（会形成循环：params → self_check → params）
# 所有对 params 的依赖都在函数内部 lazy import。
from gimbal.cli.context import CLIContext


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class SelfCheckContext:
    """自检期间收集的所有状态——结构化、不依赖全局变量。"""
    checks: list[CheckResult] = field(default_factory=list)
    events_received: list[tuple[str, str]] = field(default_factory=list)
    hooks_invoked: list[tuple[str, str]] = field(default_factory=list)
    start_ts: float = 0.0

    def check(self, name: str, condition: bool, detail: str = "") -> None:
        ok = bool(condition)
        self.checks.append(CheckResult(name=name, ok=ok, detail=detail))

    def passed(self) -> int:
        return sum(1 for c in self.checks if c.ok)

    def total(self) -> int:
        return len(self.checks)


def _make_event_handler(ctx: SelfCheckContext, event_type: str) -> Callable[[Any], None]:
    def handler(event: Any) -> None:
        label = (
            getattr(event, "step_id", None)
            or getattr(event, "scenario_id", None)
            or getattr(event, "url", None)
            or "?"
        )
        ctx.events_received.append((event_type, str(label)))
    return handler


def _make_hook(ctx: SelfCheckContext, point: str) -> Callable[[dict], Any]:
    def hook(payload: dict) -> None:
        label = str(
            payload.get("url")
            or payload.get("step_id")
            or payload.get("strategy_name")
            or "?"
        )
        ctx.hooks_invoked.append((point, label))
    return hook


def _on_framework_init(ctx: SelfCheckContext) -> Callable[[dict], None]:
    def hook(payload: dict) -> None:
        ctx.check("framework.init hook fired (after activation)", True)
        ctx.check("framework.init payload has 'cfg'", "cfg" in payload)
        ctx.check("framework.init payload has 'ctx_manager'", "ctx_manager" in payload)
        ctx.check("framework.init payload has 'plugin_registry'", "plugin_registry" in payload)
    return hook


def _print_report(ctx: SelfCheckContext) -> None:
    duration_ms = (time.monotonic() - ctx.start_ts) * 1000
    typer.echo("")
    typer.echo("=" * 72)
    typer.echo(f"  GIMBAL FRAMEWORK SELF-CHECK  (lifetime: {duration_ms:.1f} ms)")
    typer.echo("=" * 72)
    for c in ctx.checks:
        mark = "PASS" if c.ok else "FAIL"
        line = f"  [{mark}] {c.name}"
        if c.detail:
            line += f"  — {c.detail}"
        typer.echo(line)
    typer.echo("-" * 72)

    ev_by_type: dict[str, int] = {}
    for ev_type, _ in ctx.events_received:
        ev_by_type[ev_type] = ev_by_type.get(ev_type, 0) + 1
    hk_by_point: dict[str, int] = {}
    for point, _ in ctx.hooks_invoked:
        hk_by_point[point] = hk_by_point.get(point, 0) + 1

    typer.echo(f"  checks       : {ctx.passed()} / {ctx.total()} passed")
    typer.echo(f"  events seen  : {len(ctx.events_received)} total  {ev_by_type}")
    typer.echo(f"  hooks hit    : {len(ctx.hooks_invoked)} total  {hk_by_point}")
    typer.echo("=" * 72)
    typer.echo("")


def self_check(ctx: typer.Context) -> None:
    """运行框架自检：验证 plugin/event/hook 基础设施工作正常。"""
    # Lazy imports（避开循环）
    from gimbal.cli.params import EXIT_OK, EXIT_SYSTEM_ERROR
    from gimbal.core.boostrap import bootstrap, shutdown
    from gimbal.core.hooks import HookPoint
    from gimbal.events.types import (
        EventType,
        RunStartEvent, RunEndEvent,
        StepStartEvent, StepEndEvent, StepFailedEvent,
        HttpRequestEvent, HttpResponseEvent,
        ScenarioStartEvent, ScenarioEndEvent,
    )
    from gimbal.events.protocols import EventBusProtocol, HookRegistryProtocol

    # self_check 不是 Plugin，但本工具直接往 bus / hook_registry 注册的订阅与 hook
    # 全部带上同一个 plugin_name（OWNER），便于精确清理。
    # 历史：原代码不带 plugin_name，注册物 plugin_name=None，shutdown 走
    # unsubscribe_plugin(None) / unregister_plugin(None) 路径，要么漏清，要么
    # 全清。Issue ③ 修复后所有自检的注册物都归到 OWNER 名下，finally 块里
    # 显式 unsubscribe / unregister，再走 shutdown——三层兜底。
    OWNER = "self_check"

    cli_ctx: CLIContext = ctx.obj
    typer.echo("[self_check] bootstrapping framework...")

    sc_ctx = SelfCheckContext(start_ts=time.monotonic())

    # 1. 引导框架（plugins: []，走的是空插件路径）
    configuration = bootstrap(cli_ctx)

    try:
        bus = configuration.event_bus
        hook_registry = configuration.hook_registry
        plugin_registry = configuration.plugin_registry

        # ── A. 验证 Configuration 各组件 ──
        sc_ctx.check("event_bus is not None", bus is not None)
        sc_ctx.check("hook_registry is not None", hook_registry is not None)
        sc_ctx.check("plugin_registry is not None", plugin_registry is not None)
        sc_ctx.check("event_bus.publish is callable", callable(getattr(bus, "publish", None)))
        sc_ctx.check("hook_registry.register is callable", callable(getattr(hook_registry, "register", None)))
        # Protocol 兼容校验（Issue 1 修复后的回归保护）
        sc_ctx.check("bus supports EventBusProtocol", isinstance(bus, EventBusProtocol))
        sc_ctx.check("hook_registry supports HookRegistryProtocol", isinstance(hook_registry, HookRegistryProtocol))

        # ── B. 订阅全部事件类型（演示 Issue 4 修复后的对称 API）──
        event_types = [
            EventType.STEP_START, EventType.STEP_END, EventType.STEP_FAILED,
            EventType.HTTP_REQUEST, EventType.HTTP_RESPONSE,
            EventType.SCENARIO_START, EventType.SCENARIO_END,
            EventType.RUN_START, EventType.RUN_END,
        ]
        for ev_type in event_types:
            # 两种风格都支持：EventType 枚举 或 字符串字面量
            bus.subscribe(_make_event_handler(sc_ctx, ev_type.name), ev_type, plugin_name=OWNER)
        sc_ctx.check(f"subscribed {len(event_types)} event types (EventType enum API)",
                     True, f"count={len(event_types)}")

        # ── C. 注册 3 个 hook（用 HookPoint 枚举，与 EventType 对称）──
        for point in (HookPoint.HTTP_BEFORE_SEND, HookPoint.HTTP_AFTER_RECV, HookPoint.STEP_START):
            hook_registry.register(point, _make_hook(sc_ctx, point.value), priority=10,
                                   plugin_name=OWNER,
                                   description="self_check: trace")
        sc_ctx.check("registered 3 hooks (HookPoint enum API)", True)

        # ── D. 注册 FRAMEWORK_INIT hook（验证 post-init 路径）──
        hook_registry.register(HookPoint.FRAMEWORK_INIT, _on_framework_init(sc_ctx),
                               plugin_name=OWNER,
                               description="self_check: post-init check")
        sc_ctx.check("registered framework.init hook", True)

        # ── E. 试发布一个事件，验证订阅者能收到 ──
        bus.publish(RunStartEvent(run_id="self-check", env=cli_ctx.env or "dev", mode="self-check"))
        sc_ctx.check("event publish→subscribe roundtrip works",
                     any(ev_type == "RUN_START" for ev_type, _ in sc_ctx.events_received))

        # ── F. 试触发一个 hook，验证 handler 被调用 ──
        hook_registry.trigger(HookPoint.HTTP_BEFORE_SEND, {"url": "http://self-check", "headers": {}})
        sc_ctx.check("hook trigger works",
                     any(point == "http.before_send" for point, _ in sc_ctx.hooks_invoked))

    finally:
        # 1. 显式清理 OWNER 名下的所有订阅 / hook（精确路径）
        try:
            configuration.event_bus.unsubscribe_plugin(OWNER)
        except Exception:  # noqa: BLE001
            pass
        try:
            configuration.hook_registry.unregister_plugin(OWNER)
        except Exception:  # noqa: BLE001
            pass

        # 2. 走统一的卸载入口（验证 Issue 5 的修复）
        #    此时 OWNER 名下的注册物已被清掉，shutdown 的 hook_registry.clear()
        #    兜底应只清零"零个"——若还有遗留说明有别的路径在泄漏，应 warning。
        shutdown(configuration)

    # 报告
    _print_report(sc_ctx)

    if sc_ctx.passed() != sc_ctx.total():
        raise typer.Exit(code=EXIT_SYSTEM_ERROR)
    raise typer.Exit(code=EXIT_OK)
