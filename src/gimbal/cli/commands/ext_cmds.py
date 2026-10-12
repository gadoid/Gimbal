"""gimbal ext list —— 六张扩展注册表的描述导出（v2 §1，批次 C）。

``ext list --json`` = strategy + protocol + mode + plugin + generator + event 六张表
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


def _event_payload_fields() -> dict[str, list[str]]:
    """事件表载荷字段(模块级可测;B-6/W23 修复处)。

    event_type 是 pydantic 字段,类上 getattr 拿到的是 FieldInfo 而非
    字符串 —— 取默认值的正确姿势 = model_fields 的 get_default()
    (与 known_event_types() 同源)。context.promotion 是
    variable.promoted 的旧订阅别名,载荷类同一个,字段同源。
    """
    from gimbal.events.types import FrameworkEvent
    import gimbal.events.types as _event_types
    payload_fields: dict[str, list[str]] = {}
    for _obj in list(vars(_event_types).values()):
        if (isinstance(_obj, type) and issubclass(_obj, FrameworkEvent)
                and _obj is not FrameworkEvent):
            _f = _obj.model_fields.get("event_type")
            et = _f.get_default() if _f is not None else None
            if isinstance(et, str) and et:
                fields = sorted(
                    f for f in _obj.model_fields
                    if f not in ("seq", "event_type"))  # 信封/判别字段非载荷
                payload_fields.setdefault(et, fields)
    if "variable.promoted" in payload_fields:
        payload_fields.setdefault("context.promotion",
                                  payload_fields["variable.promoted"])
    return payload_fields


def describe_extensions(dispatcher, protocols, mode_registry, plugin_registry) -> list[dict]:
    """聚合四张表的 describe()（JSON 安全）。

    S-1：strategy 表参数模型经 dispatcher.params_of（注册面收敛），
    protocol 表经 protocols.params_of —— 本文件不再持有任何硬编码映射。
    """
    out: list[dict] = []

    # strategy 表（dispatcher 的 kind 键；params 模型由注册面携带）
    for kind in dispatcher.kinds():
        params_cls = dispatcher.params_of(kind)
        out.append({
            "table": "strategy",
            "name": kind,
            "params_schema": params_cls.model_json_schema() if params_cls else None,
        })

    # protocol 表（ProtocolRegistry）
    for proto in protocols.protocols():
        params_cls = protocols.params_of(proto)
        out.append({
            "table": "protocol",
            "name": proto,
            "params_schema": params_cls.model_json_schema() if params_cls else None,
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

    # 生成器表（Q5/M2 §2.4：variable generators 的 spec 模型 + 参数 Schema）
    from gimbal.generator.specs import (
        NowSpec, RandomDecimalSpec, RandomDecoratedSpec, RandomIntSpec,
        RandomStrSpec, SeqSpec, TimeOffsetSpec, TimestampSpec, UuidSpec,
    )
    for spec_cls in (UuidSpec, RandomStrSpec, RandomIntSpec,
                     RandomDecimalSpec, TimestampSpec, NowSpec,
                     SeqSpec, RandomDecoratedSpec, TimeOffsetSpec):
        out.append({
            "table": "generator",
            "name": spec_cls.model_fields["kind"].default,
            "params_schema": spec_cls.model_json_schema(),
        })

    # 事件表（Q5/M2 §2.4：event_type + payload 字段，供报告定义编写检索）
    from gimbal.events.types import known_event_types
    payload_fields = _event_payload_fields()
    for et in sorted(known_event_types()):
        out.append({
            "table": "event",
            "name": et,
            "fields": payload_fields.get(et, []),
        })
    # 第七表:param_registry(C 类快照,执行器参数合并代数)
    from gimbal.schema.param_registry import PARAM_REGISTRY
    for name, decl in sorted(PARAM_REGISTRY.items()):
        out.append({
            "table": "param_registry",
            "field": name,
            "level": decl.level,
            "merge": decl.merge,
            "sources": list(decl.sources),
        })
    return out


def ext_list(
    ctx: typer.Context,
    env: EnvOpt = "dev",
    mode: ModeOpt = "local",
    log_level: LogLevelOpt = LogLevel.error,
    as_json: Annotated[bool, typer.Option("--json", help="机器可读输出")] = False,
    table: Annotated[Optional[str], typer.Option("--table", help="只看某张表: strategy/protocol/mode/plugin/generator/event")] = None,
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
