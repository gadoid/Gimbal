"""gimbal ext list —— 四张扩展注册表的描述导出（v2 §1，批次 C）。

``ext list --json`` = strategy + protocol + mode + plugin 四张表
describe() 之和：name + 参数 JSON Schema（供平台 G2 生成表单）。
需要 bootstrap（插件表按激活态导出），但不执行任何用例。
"""
from __future__ import annotations

import json
from typing import Annotated, Optional

import typer

from gimbal.cli.common import EnvOpt, LogLevel, LogLevelOpt, ModeOpt
from gimbal.cli.context import CLIContext
from gimbal.core.bootstrap import bootstrap, shutdown
from gimbal.log import get_logger

logger = get_logger(__name__)

# 策略 kind → 参数模型（dispatch 校验的 schema 面）
_STRATEGY_PARAMS = {
    "extract": "gimbal.schema.strategy:Extract",
    "assign": "gimbal.schema.strategy:Assign",
    "assertion": "gimbal.schema.strategy:Assertion",
}


def _resolve_params(dotted: str):
    mod, _, attr = dotted.partition(":")
    try:
        import importlib
        return getattr(importlib.import_module(mod), attr)
    except Exception:  # noqa: BLE001
        return None


def describe_extensions(dispatcher, protocols, mode_registry, plugin_registry) -> list[dict]:
    """聚合四张表的 describe()（JSON 安全）。"""
    out: list[dict] = []

    # strategy 表（dispatcher 的 kind 键；params 模型按映射解析）
    for kind in dispatcher.kinds():
        dotted = _STRATEGY_PARAMS.get(kind)
        params_cls = _resolve_params(dotted) if dotted else None
        out.append({
            "table": "strategy",
            "name": kind,
            "params_schema": params_cls.model_json_schema() if params_cls else None,
        })

    # protocol 表（ProtocolRegistry）
    for proto in protocols.protocols():
        out.append({
            "table": "protocol",
            "name": proto,
            "params_schema": None,   # per-协议 call 字段模型在批次 F Registry 收敛时补
        })

    # mode 表（泛型 Registry）
    out.extend(mode_registry.describe())

    # plugin 表（激活态：name + capabilities + 订阅计数）
    for plugin in plugin_registry.list_all():
        spec = plugin_registry.get_spec(plugin.name)
        out.append({
            "table": "plugin",
            "name": plugin.name,
            "params_schema": None,
            "version": getattr(spec, "version", "") if spec else "",
            "capabilities": list(getattr(spec, "capabilities", []) or []) if spec else [],
            "events": getattr(plugin.ctx, "event_count", 0) if getattr(plugin, "ctx", None) else 0,
            "hooks": getattr(plugin.ctx, "hook_count", 0) if getattr(plugin, "ctx", None) else 0,
        })
    return out


def ext_list(
    ctx: typer.Context,
    env: EnvOpt = "dev",
    mode: ModeOpt = "local",
    log_level: LogLevelOpt = LogLevel.error,
    as_json: Annotated[bool, typer.Option("--json", help="机器可读输出")] = False,
    table: Annotated[Optional[str], typer.Option("--table", help="只看某张表: strategy/protocol/mode/plugin")] = None,
) -> None:
    """列出所有扩展注册表条目（四张表之和）。"""
    cli_ctx: CLIContext = ctx.obj
    cli_ctx.env = env
    cli_ctx.mode = mode
    cli_ctx.log_level = log_level.value if hasattr(log_level, "value") else log_level

    configuration = bootstrap(cli_ctx)
    try:
        from gimbal.suite.modes import build_default_mode_registry
        entries = describe_extensions(
            configuration.dispatcher,
            configuration.protocols or configuration.dispatcher.protocols,
            build_default_mode_registry(),
            configuration.plugin_registry,
        )
    finally:
        shutdown(configuration)

    if table:
        entries = [e for e in entries if e["table"] == table]

    if as_json:
        typer.echo(json.dumps(entries, ensure_ascii=False, indent=2, default=str))
        return

    by_table: dict[str, list[dict]] = {}
    for e in entries:
        by_table.setdefault(e["table"], []).append(e)
    for t in ("strategy", "protocol", "mode", "plugin"):
        items = by_table.get(t, [])
        typer.secho(f"[{t}] ({len(items)})", fg=typer.colors.CYAN)
        for e in items:
            extra = ""
            if e.get("capabilities"):
                extra = f"  capabilities={e['capabilities']}"
            typer.echo(f"  - {e['name']}{extra}")
    raise typer.Exit(code=0)
