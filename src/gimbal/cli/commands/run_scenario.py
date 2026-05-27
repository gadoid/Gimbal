"""Run scenario command."""
from __future__ import annotations

import sys
from typing import Annotated

import typer

from gimbal.cli.common import (
    AllowEmptyOpt, CacheOnlyOpt, ContinueOnErrorOpt, DryRunOpt, EnvOpt,
    FailFastOpt, LogLevel, LogLevelOpt, NoCacheOpt, OrderOpt, OrderStrategy,
    OutputFormat, OutputOpt, ParallelOpt, ModeOpt, RegistryOpt,
    ReportDirOpt, ReporterOpt, RetryOpt, SourceOpt, SourceStrategy, TagOpt,
    TimeoutOpt, VarFileOpt, VarOpt, VersionOpt, YesOpt,
    parse_parallel, parse_vars, resolve_source,
)
from gimbal.cli.context import CLIContext
from gimbal.core.asset_resolver import AssetKind, AssetResolver
from gimbal.log import get_logger

logger = get_logger(__name__)


def scenario(
    ctx: typer.Context,
    scenario_ids: Annotated[
        list[str],
        typer.Argument(
            help="一个或多个 Scenario ID，支持命名空间通配如 'payment/sc-*'。",
            metavar="SCENARIO_ID...",
        ),
    ],
    # ========== 步骤级控制（scenario 专属，对应你的状态机引擎）==========
    step_from: Annotated[
        int | None,
        typer.Option("--step-from", help="从指定 step 开始执行。", rich_help_panel="步骤控制"),
    ] = None,
    step_to: Annotated[
        int | None,
        typer.Option("--step-to", help="执行到指定 step 停止。", rich_help_panel="步骤控制"),
    ] = None,
    breakpoint_at: Annotated[
        list[int] | None,
        typer.Option("--breakpoint", help="在指定 step 暂停进入交互模式，可重复。", rich_help_panel="步骤控制"),
    ] = None,
    # ========== 资产来源 ==========
    source: SourceOpt = SourceStrategy.auto,
    registry: RegistryOpt = None,
    version: VersionOpt = None,
    no_cache: NoCacheOpt = False,
    cache_only: CacheOnlyOpt = False,
    # ========== 多目标控制 ==========
    order: OrderOpt = OrderStrategy.as_given,
    continue_on_error: ContinueOnErrorOpt = False,
    # ========== 确认 ==========
    yes: YesOpt = False,
    allow_empty: AllowEmptyOpt = False,
    # ========== 通用 ==========
    env: EnvOpt = "dev",
    mode: ModeOpt = "local",
    log_level: LogLevelOpt = LogLevel.info,
    tag: TagOpt = None,
    var: VarOpt = None,
    var_file: VarFileOpt = None,
    parallel: ParallelOpt = "1",
    timeout: TimeoutOpt = 300,
    retry: RetryOpt = 0,
    dry_run: DryRunOpt = False,
    fail_fast: FailFastOpt = False,
    reporter: ReporterOpt = None,
    report_dir: ReportDirOpt = "./reports",
    output: OutputOpt = OutputFormat.console,
) -> None:
    """执行已注册的 Scenario 资产。

    [bold]示例：[/bold]

      gimbal run scenario sc-payment-001
      gimbal run scenario sc-001 sc-002 --continue-on-error
      gimbal run scenario "payment/sc-*" --yes
      gimbal run scenario sc-001 --step-from=3 --breakpoint=5
    """
    cli_ctx: CLIContext = ctx.obj

    # 互斥校验
    if step_from is not None and step_to is not None and step_from > step_to:
        raise typer.BadParameter("--step-from 不能大于 --step-to。")

    logger.info("[CLI] Scenario command invoked: scenario_ids={} env={} mode={}", scenario_ids, env, mode)

    resolved_source = resolve_source(source, no_cache, cache_only)

    resolver = AssetResolver(
        kind=AssetKind.SCENARIO,
        source=resolved_source.value,
        registry=registry,
        version=version,
    )
    matched = resolver.resolve(scenario_ids)

    if not matched:
        if allow_empty:
            logger.warning("[CLI] No scenarios matched, allow_empty enabled - exiting cleanly")
            typer.echo("No scenarios matched, exiting cleanly due to --allow-empty.")
            raise typer.Exit(code=0)
        logger.error("[CLI] No scenarios matched: {}", scenario_ids)
        typer.secho(
            f"Error: No scenarios matched: {', '.join(scenario_ids)}",
            fg=typer.colors.RED, bold=True, err=True,
        )
        raise typer.Exit(code=5)

    logger.info("[CLI] Matched {} scenario(s)", len(matched))
    if len(matched) > 1 and not yes and sys.stdin.isatty():
        typer.echo(f"Matched {len(matched)} scenarios:")
        for s in matched:
            typer.echo(f"  - {s.id}")
        if not typer.confirm("Proceed?", default=False):
            logger.info("[CLI] User aborted - proceeding=false")
            typer.echo("Aborted.")
            raise typer.Exit(code=0)

