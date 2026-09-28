"""cli/commands/events_cmds.py — gimbal events：事件流导入与回放（P1-05）。

    gimbal events replay <file.jsonl> [--reporter json] [--report-dir DIR]
        把一次执行留下的 jsonl 事件流按 seq 顺序重喂给指定报告器，
        产出与原运行相同的报告（时间戳字段除外；判定计数取自末行
        run.finished，非重放推导）。

    gimbal events query <file.jsonl> [--where k=v ...] [--events p ...]
        用 P1-04 的 where 语法过滤事件流（fnmatch 通配），命中行原样输出。
"""
from __future__ import annotations

import fnmatch
import json
from pathlib import Path
from typing import Annotated, Any, Optional

import typer

from gimbal.cli.common import OutputFormat

events_app = typer.Typer(help="事件流导入与回放（jsonl 事后消费）")


# ── 事件重建：event_type 字符串 → FrameworkEvent 子类 ──────────

_EVENT_CLASS_BY_TYPE: dict[str, type] | None = None


def _event_classes() -> dict[str, type]:
    """events/types.py 全部事件类的 event_type → 类映射（惰性缓存）。"""
    global _EVENT_CLASS_BY_TYPE
    if _EVENT_CLASS_BY_TYPE is None:
        from gimbal.events.types import FrameworkEvent
        table: dict[str, type] = {}
        import gimbal.events.types as mod
        for obj in vars(mod).values():
            if (isinstance(obj, type) and issubclass(obj, FrameworkEvent)
                    and obj is not FrameworkEvent):
                et = getattr(obj, "model_fields", {}).get("event_type")
                if et is not None:
                    default = et.get_default()
                    if isinstance(default, str) and default:
                        table.setdefault(default, obj)
        _EVENT_CLASS_BY_TYPE = table
    return _EVENT_CLASS_BY_TYPE


def _load_events(path: Path) -> list[tuple[int, Any]]:
    """读 jsonl → [(seq, 事件对象)]；按 seq 升序（发布序）。"""
    out: list[tuple[int, Any]] = []
    classes = _event_classes()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            d = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        et = d.get("event_type") or ""
        cls = classes.get(et)
        if cls is None:
            continue    # 未知事件（插件扩展）：跳过并保序
        try:
            out.append((int(d.get("seq") or 0), cls.model_validate(d)))
        except Exception:  # noqa: BLE001  # 单行损坏不阻断回放
            continue
    out.sort(key=lambda t: t[0])
    return out


def _run_result_from_finished(events: list[Any]) -> Any:
    """末行 run.finished → RunResult（判定计数不重放推导，原样取回）。"""
    from gimbal.core.runner import RunResult
    finished = next((e for e in reversed(events)
                     if getattr(e, "event_type", "") == "run.finished"), None)
    if finished is None:
        return RunResult(exit_code=1, error=1)
    return RunResult(
        exit_code=finished.exit_code, total=finished.total,
        passed=finished.passed, failed=finished.failed,
        skipped=finished.skipped, error=finished.error,
        halted=finished.halted, blocked=finished.blocked,
        repaired=finished.repaired, details=list(finished.details or []),
    )


@events_app.command("replay")
def replay(
    source: Annotated[str, typer.Argument(help="jsonl 事件流文件路径")],
    reporter: Annotated[
        list[str] | None,
        typer.Option("--reporter", help="报告器名（可重复；缺省 json）"),
    ] = None,
    report_dir: Annotated[
        str, typer.Option("--report-dir", help="报告输出目录")
    ] = "./reports",
) -> None:
    """把 jsonl 事件流按 seq 顺序重喂给指定报告器，产出报告。"""
    path = Path(source)
    if not path.is_file():
        typer.secho(f"事件流文件不存在: {source}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)
    pairs = _load_events(path)
    events = [e for _, e in pairs]
    if not events:
        typer.secho("事件流为空或无已知事件类型", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)

    from gimbal.auth.registry import AuthRegistry
    from gimbal.config.models import BootstrapConfig
    from gimbal.context.archive import InMemoryArchive
    from gimbal.context.manager import ContextManager
    from gimbal.events.bus import InMemoryEventBus
    from gimbal.reporter.builtin import register_builtin_reporters
    from gimbal.reporter.registry import ReporterRegistry
    from gimbal.reporter.runtime import ReporterRuntime

    bus = InMemoryEventBus()
    registry = ReporterRegistry()
    register_builtin_reporters(registry)

    # run_id 取事件信封（jsonl 里 run 标签/run_id），缺失则生成；
    # create_framework_context 收 Configuration（reporter 读 cfg 字段面），
    # 回放组装轻量 Configuration（执行器为空——不重放执行，只喂数据）
    from gimbal.core.bootstrap import Configuration
    from gimbal.plugins import PluginRegistry
    run_id = next((getattr(e, "run_id", None) or getattr(e, "run", None)
                   for e in events if getattr(e, "run_id", None)), "replay")
    ctx_manager = ContextManager(archive=InMemoryArchive(), event_bus=bus)
    conf = Configuration(
        cfg=BootstrapConfig(env="replay", mode="local"),
        auth_registry=AuthRegistry(), ctx_manager=ctx_manager,
        dispatcher=None, event_bus=bus, archive=InMemoryArchive(),
        hook_registry=None, plugin_registry=PluginRegistry(), plugins=(),
        reporter_runtime=None, protocols=None,
    )
    framework_ctx = ctx_manager.create_framework_context(
        run_id=str(run_id), cfg=conf,
    )

    runtime = ReporterRuntime(registry)
    runtime.setup(bus, None)
    runtime.begin_all(
        framework_ctx=framework_ctx,
        reporter_names=list(reporter or ("json",)),
        report_dir=report_dir,
        plugin_configs={},
    )
    for event in events:
        bus.publish(event)
    result = _run_result_from_finished(events)
    artifacts = runtime.finalize_all(result)
    runtime.shutdown()

    for art in artifacts:
        typer.echo(f"report: {art.name} -> {art.path}")
    raise typer.Exit(code=0)


def _parse_where(pairs: list[str] | None) -> dict[str, str]:
    """--where k=v 对 → dict；键合法性沿用订阅编译的 where 键集。"""
    from gimbal.schema.subscribe import EVENT_WHERE_FIELDS
    from gimbal.log.exec_context import EXEC_LABEL_NAMES
    valid = set(EXEC_LABEL_NAMES) | set(EVENT_WHERE_FIELDS)
    where: dict[str, str] = {}
    for pair in pairs or []:
        if "=" not in pair:
            typer.secho(f"--where 需要 k=v 形态（得到 {pair!r}）",
                        fg=typer.colors.RED, err=True)
            raise typer.Exit(code=2)
        k, v = pair.split("=", 1)
        if k not in valid:
            typer.secho(f"--where 未知键: {k!r}（合法: {sorted(valid)}）",
                        fg=typer.colors.RED, err=True)
            raise typer.Exit(code=2)
        where[k] = v
    return where


@events_app.command("query")
def query(
    source: Annotated[str, typer.Argument(help="jsonl 事件流文件路径")],
    where: Annotated[
        list[str] | None,
        typer.Option("--where", help="过滤键值对 k=v（fnmatch 通配；可重复；P1-04 同款键集）"),
    ] = None,
    events_filter: Annotated[
        list[str] | None,
        typer.Option("--events", help="事件类型/模式（fnmatch；可重复）"),
    ] = None,
    output: Annotated[Optional[OutputFormat], typer.Option("-o", "--output")] = OutputFormat.console,
) -> None:
    """按 where/事件模式过滤 jsonl 事件流；命中行原样输出。"""
    path = Path(source)
    if not path.is_file():
        typer.secho(f"事件流文件不存在: {source}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)
    where_map = _parse_where(where)
    patterns = tuple(events_filter or [])
    hits: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            d = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(d, dict):
            continue
        if patterns and not any(
                fnmatch.fnmatchcase(str(d.get("event_type") or ""), p)
                for p in patterns):
            continue
        if any(
                d.get(k) is None
                or not fnmatch.fnmatchcase(str(d.get(k)), v)
                for k, v in where_map.items()):
            continue
        hits.append(d)

    if output == OutputFormat.json:
        typer.echo(json.dumps(hits, ensure_ascii=False, indent=2, default=str))
    else:
        for d in hits:
            typer.echo(json.dumps(d, ensure_ascii=False, default=str))
    raise typer.Exit(code=0)
