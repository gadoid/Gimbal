"""gimbal run suite —— 按 ID 执行 Suite 资产。"""
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


def suite(
    ctx: typer.Context,
    # ========== 位置参数 ==========
    suite_ids: Annotated[
        list[str],
        typer.Argument(
            help="一个或多个 Suite ID，支持命名空间通配如 'customs/*'。",
            metavar="SUITE_ID...",
        ),
    ],
    # ========== 专属参数 ==========
    include_scenario: Annotated[
        list[str] | None,
        typer.Option("--include-scenario", help="只跑 Suite 内指定的 scenario，可重复。"),
    ] = None,
    exclude_scenario: Annotated[
        list[str] | None,
        typer.Option("--exclude-scenario", help="排除 Suite 内特定 scenario，可重复。"),
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
    # ========== 确认行为 ==========
    yes: YesOpt = False,
    allow_empty: AllowEmptyOpt = False,
    # ========== 环境与日志 ==========
    env: EnvOpt = "dev",
    mode: ModeOpt = "local",
    log_level: LogLevelOpt = LogLevel.info,
    # ========== 过滤与变量 ==========
    tag: TagOpt = None,
    var: VarOpt = None,
    var_file: VarFileOpt = None,
    # ========== 执行控制 ==========
    parallel: ParallelOpt = "1",
    timeout: TimeoutOpt = 300,
    retry: RetryOpt = 0,
    dry_run: DryRunOpt = False,
    fail_fast: FailFastOpt = False,
    # ========== 报告输出 ==========
    reporter: ReporterOpt = None,
    report_dir: ReportDirOpt = "./reports",
    output: OutputOpt = OutputFormat.console,
) -> None:
    """执行已注册的 Suite 资产。

    [bold]示例：[/bold]

        gimbal run suite customs-declare
        gimbal run suite customs-declare forex-settle --order=parallel
        gimbal run suite "customs/*" --yes
        gimbal run suite customs/declare:v1.2 --source=remote
        gimbal run suite tax-refund --include-scenario=happy-path
    """
    cli_ctx: CLIContext = ctx.obj

    # 1. 协调资产来源
    resolved_source = resolve_source(source, no_cache, cache_only)

    # 2. 解析资产
    resolver = AssetResolver(
        kind=AssetKind.SUITE,
        source=resolved_source.value,
        registry=registry,
        version=version,
    )
    matched = resolver.resolve(suite_ids)

    # 3. 零匹配处理
    if not matched:
        if allow_empty:
            typer.echo("No suites matched, exiting cleanly due to --allow-empty.")
            raise typer.Exit(code=0)
        typer.secho(
            f"Error: No suites matched the given IDs: {', '.join(suite_ids)}",
            fg=typer.colors.RED, bold=True, err=True,
        )
        raise typer.Exit(code=5)

    # 4. 通配多匹配的确认
    if len(matched) > 1 and not yes and sys.stdin.isatty():
        typer.echo(f"Matched {len(matched)} suites:")
        for s in matched:
            typer.echo(f"  - {s.id}")
        if not typer.confirm("Proceed?", default=False):
            typer.echo("Aborted.")
            raise typer.Exit(code=0)

