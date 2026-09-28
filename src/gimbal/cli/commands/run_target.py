"""gimbal run scenario / run suite —— 按 kind 执行（v2.1 批次 B：全走 Plan 单路径）。

run scenario：路径命中的 scenario → 隐式 aggregate Plan；
run suite：suite 声明 → aggregate Plan（execution.parallel/maxWorkers/failFast）。
两者共用 execute_run_file（bootstrap → 加载 → kind 校验 → Engine.run（内部
编译为 Plan）→ 报告）；与 run launch 的区别只有 kind 强校验与更窄的参数面。
"""
from __future__ import annotations

from typing import Annotated, Literal

import typer
from pydantic import TypeAdapter

from gimbal.cli.common import (
    EnvOpt, InputFormat, FormatOpt, LogLevel, LogLevelOpt, ModeOpt,
    OutputFormat, OutputOpt, ReportDirOpt, ReporterOpt,
    _print_run_report, _publish_run_meta,
)
from gimbal.cli.context import CLIContext
from gimbal.cli.commands.run_launch import InputError, normalize_input
from gimbal.core.bootstrap import bootstrap, shutdown
from gimbal.core.runner import Engine
from gimbal.log import get_logger
from gimbal.schema.scenario import RunUnion

logger = get_logger(__name__)


def _run_loaded(cli_ctx, configuration, target, *, expect_kind, output,
                step_from=None, step_to=None, halt_at=None) -> int:
    """已加载目标 → kind 校验 → jsonl sink → Engine.run → 报告；返回退出码。"""
    actual = target.kind
    if not actual == expect_kind:
        typer.secho(
            f"输入是 {actual}，但本命令只接受 {expect_kind}（请用 run launch 按 kind 分派）",
            fg=typer.colors.RED, err=True,
        )
        shutdown(configuration)
        return 2

    jsonl_sub = None
    if output == OutputFormat.jsonl:
        from gimbal.cli.common import attach_jsonl_sink
        jsonl_sub = attach_jsonl_sink(configuration.event_bus)

    from gimbal.core.scenario_runner import RuntimeControl
    runtime_control = None
    if any(v is not None for v in (step_from, step_to, halt_at)):
        runtime_control = RuntimeControl(
            halt_at=step_to if step_to is not None else halt_at,
            halt_reason=(
                f"cli --step-to={step_to}" if step_to is not None
                else (f"cli --halt-at={halt_at}" if halt_at is not None else "user-requested")
            ),
            step_from=step_from,
        )

    engine = Engine(configuration)
    try:
        result = engine.run(target, runtime_control=runtime_control)
    finally:
        if jsonl_sub is not None:
            try:
                configuration.event_bus.unsubscribe(jsonl_sub)
            except Exception:  # noqa: BLE001
                pass
        shutdown(configuration)
    _print_run_report(result, output, artifacts=engine.artifacts)
    return result.exit_code


def execute_run_file(
    cli_ctx: CLIContext,
    source: str,
    fmt,
    *,
    expect_kind: Literal["scenario", "suite"],
    env, mode, log_level,
    reporter, report_dir, output,
    step_from=None, step_to=None, halt_at=None,
    where: "list[str] | None" = None,
) -> None:
    """加载 → kind 强校验 → bootstrap → Engine.run（编译 Plan 单路径）→ 报告。

    D-14 双模式：source 可为目录（枚举场景文件，--where 直接字段过滤；
    命中多个时逐个执行，exit_code 取最差）；--where 仅 run scenario 支持。
    """
    cli_ctx.env = env
    cli_ctx.mode = mode
    cli_ctx.log_level = log_level.value if hasattr(log_level, "value") else log_level
    if report_dir:
        cli_ctx.extras["report_dir"] = report_dir
    if reporter:
        cli_ctx.extras["reporters"] = list(reporter)

    # 检索器路径（D-15）：目录或带 --where 时经 selector 枚举/过滤
    import os as _os
    if where or _os.path.isdir(source):
        if expect_kind != "scenario":
            typer.secho("--where/目录模式仅支持 run scenario", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=2)
        from gimbal.suite.selector import parse_where, select
        try:
            scenarios = select(source, parse_where(where or []))
        except (ValueError, FileNotFoundError) as exc:
            typer.secho(f"检索失败: {exc}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=2)
        worst = 0
        for sc in scenarios:
            # 每个场景独立 run（bootstrap 新 Configuration；_run_loaded 内负责 shutdown）
            configuration = bootstrap(cli_ctx)
            _publish_run_meta(configuration)
            worst = max(worst, _run_loaded(
                cli_ctx, configuration, sc, expect_kind="scenario",
                output=output, step_from=step_from, step_to=step_to,
                halt_at=halt_at))
        raise typer.Exit(code=worst)

    configuration = bootstrap(cli_ctx)
    _publish_run_meta(configuration)

    payload = normalize_input(source, None, fmt)
    try:
        target = TypeAdapter(RunUnion).validate_python(payload)
    except Exception as exc:
        typer.secho(f"用例格式校验失败: {exc}", fg=typer.colors.RED, err=True)
        shutdown(configuration)
        raise typer.Exit(code=2)
    code = _run_loaded(
        cli_ctx, configuration, target, expect_kind=expect_kind, output=output,
        step_from=step_from, step_to=step_to, halt_at=halt_at)
    raise typer.Exit(code=code)


def scenario(
    ctx: typer.Context,
    source: Annotated[
        str,
        typer.Argument(help="Scenario 文件路径", metavar="SOURCE"),
    ],
    fmt: FormatOpt = InputFormat.auto,
    env: EnvOpt = "dev",
    mode: ModeOpt = "local",
    log_level: LogLevelOpt = LogLevel.info,
    reporter: ReporterOpt = None,
    report_dir: ReportDirOpt = "./reports",
    output: OutputOpt = OutputFormat.console,
    step_from: Annotated[
        int | None,
        typer.Option("--step-from", help="从指定 step 开始执行（0-based；被跳过步骤的输入由 vars/--var 提供）。", rich_help_panel="步骤控制"),
    ] = None,
    step_to: Annotated[
        int | None,
        typer.Option("--step-to", help="执行到指定 step 停止（0-based）。", rich_help_panel="步骤控制"),
    ] = None,
    halt_at: Annotated[
        int | None,
        typer.Option("--halt-at", help="执行到指定 step 停止（--step-to 的别名语义）。", rich_help_panel="步骤控制"),
    ] = None,
    var: Annotated[
        list[str] | None,
        typer.Option("--var", help="覆盖/追加场景变量，K=V 可多次。", rich_help_panel="输入"),
    ] = None,
    where: Annotated[
        list[str] | None,
        typer.Option("--where", help="检索条件 K=V 可多次（直接字段精确匹配，如 scenarioId=x / meta.module=m；source 可为目录）。", rich_help_panel="检索"),
    ] = None,
) -> None:
    """执行单个 Scenario（编译为隐式 aggregate Plan，v2.1 单路径）。"""
    if var:
        import json as _json
        overrides = {}
        for kv in var:
            k, _, v = kv.partition("=")
            try:
                overrides[k] = _json.loads(v)
            except Exception:  # noqa: BLE001 — 非 JSON 字面量按原始字符串
                overrides[k] = v
        # 残留 #9：变量覆盖进调用参数层;schema 补丁层(p_patch)接线后并入生效副本
        ctx.obj.extras.setdefault("vars", {}).update(overrides)
    execute_run_file(
        ctx.obj, source, fmt, expect_kind="scenario",
        env=env, mode=mode, log_level=log_level,
        reporter=reporter, report_dir=report_dir, output=output,
        step_from=step_from, step_to=step_to, halt_at=halt_at,
        where=where,
    )


def suite(
    ctx: typer.Context,
    source: Annotated[
        str,
        typer.Argument(help="编排套件文件路径（kind=graph）", metavar="SOURCE"),
    ],
    fmt: FormatOpt = InputFormat.auto,
    env: EnvOpt = "dev",
    mode: ModeOpt = "local",
    log_level: LogLevelOpt = LogLevel.info,
    reporter: ReporterOpt = None,
    report_dir: ReportDirOpt = "./reports",
    output: OutputOpt = OutputFormat.console,
) -> None:
    """执行编排套件（SuiteGraph，kind=graph；v2.1 F-2b 起嵌入式 Suite 已删除）。"""
    execute_run_file(
        ctx.obj, source, fmt, expect_kind="graph",
        env=env, mode=mode, log_level=log_level,
        reporter=reporter, report_dir=report_dir, output=output,
    )
