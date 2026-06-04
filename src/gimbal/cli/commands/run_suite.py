"""gimbal run suite —— 按 ID 执行 Suite 资产。"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer

from gimbal.cli.common import (
    AllowEmptyOpt, CacheOnlyOpt, ContinueOnErrorOpt, DryRunOpt, EnvOpt,
    FailFastOpt, LogLevel, LogLevelOpt, NoCacheOpt, OrderOpt, OrderStrategy,
    OutputFormat, OutputOpt, ParallelOpt, ModeOpt, RegistryOpt,
    ReportDirOpt, ReporterOpt, RetryOpt, SourceOpt, SourceStrategy, TagOpt,
    TimeoutOpt, VarFileOpt, VarOpt, VersionOpt, YesOpt,
    _build_default_asset_store, _print_run_report,
    parse_parallel, parse_vars, resolve_source,
)
from gimbal.cli.context import CLIContext
from gimbal.core.asset_resolver import AssetKind, AssetResolver
from gimbal.core.bootstrap import bootstrap, shutdown
from gimbal.core.runner import Engine
from gimbal.log import get_logger
from gimbal.schema.scenario import Suite

logger = get_logger(__name__)


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

    # 1. 协调资产来源 + 解析资产
    resolved_source = resolve_source(source, no_cache, cache_only)
    asset_store = _build_default_asset_store(Path(registry) if registry else None)
    logger.debug("[CLI] asset_store ready: backend={}", asset_store.backend_name)

    resolver = AssetResolver(
        kind=AssetKind.SUITE,
        asset_store=asset_store,
        source=resolved_source.value,
        registry=registry,
    )
    matched = resolver.resolve(suite_ids)

    # 2. 零匹配处理
    if not matched:
        if allow_empty:
            typer.echo("No suites matched, exiting cleanly due to --allow-empty.")
            raise typer.Exit(code=0)
        typer.secho(
            f"Error: No suites matched the given IDs: {', '.join(suite_ids)}",
            fg=typer.colors.RED, bold=True, err=True,
        )
        raise typer.Exit(code=5)

    # 3. 通配多匹配的确认
    if len(matched) > 1 and not yes and sys.stdin.isatty():
        typer.echo(f"Matched {len(matched)} suites:")
        for s in matched:
            typer.echo(f"  - {s.id}")
        if not typer.confirm("Proceed?", default=False):
            typer.echo("Aborted.")
            raise typer.Exit(code=0)

    # 4. dry-run：仅解析 + 校验
    if dry_run:
        for asset in matched:
            try:
                parsed = Suite.model_validate(asset.content.parsed)
            except Exception as exc:  # noqa: BLE001
                typer.secho(f"[{asset.id}] 校验失败: {exc}", fg=typer.colors.RED, err=True)
                raise typer.Exit(code=2)
            typer.secho(
                f"[{asset.id}] OK (dry-run): {len(parsed.suite)} scenario(s)",
                fg=typer.colors.CYAN,
            )
        raise typer.Exit(code=0)

    # 5. 引导框架
    cli_ctx.env = env
    cli_ctx.mode = mode
    cli_ctx.log_level = log_level.value
    try:
        configuration = bootstrap(cli_ctx)
    except Exception as exc:  # noqa: BLE001
        logger.exception("[CLI] bootstrap 失败: {}", exc)
        typer.secho(f"Framework bootstrap failed: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=4)

    # 6. 校验每个匹配到的 suite
    suites: list[tuple[str, Suite]] = []
    for asset in matched:
        try:
            st = Suite.model_validate(asset.content.parsed)
        except Exception as exc:  # noqa: BLE001
            logger.exception("[CLI] suite 校验失败: id={} err={}", asset.id, exc)
            typer.secho(
                f"Suite validation failed for {asset.id}: {exc}",
                fg=typer.colors.RED, err=True,
            )
            shutdown(configuration)
            raise typer.Exit(code=2)
        suites.append((asset.id, st))

    # 7. 构造 Engine，依次执行
    engine = Engine(configuration, asset_store=asset_store)
    try:
        results = []
        for original_id, st in suites:
            logger.info("[CLI] 执行 suite: id={} scenario_count={}", original_id, len(st.suite))
            result = engine.run(st)
            results.append(result)
            if fail_fast and result.exit_code != 0:
                logger.warning("[CLI] fail_fast 触发：在 {} 后停止", original_id)
                break
    except Exception as exc:  # noqa: BLE001
        logger.exception("[CLI] 执行异常: {}", exc)
        typer.secho(f"Execution error: {exc}", fg=typer.colors.RED, err=True)
        shutdown(configuration)
        raise typer.Exit(code=3)
    finally:
        shutdown(configuration)

    # 8. 汇总
    from gimbal.core.runner import RunResult as _RR
    merged = _RR(
        exit_code=0 if all(r.exit_code == 0 for r in results) else 1,
        total=sum(r.total for r in results),
        passed=sum(r.passed for r in results),
        failed=sum(r.failed for r in results),
        error=sum(r.error for r in results),
        details=[d for r in results for d in r.details],
    )
    _print_run_report(merged, output)
    raise typer.Exit(code=merged.exit_code)

