"""Run scenario command."""
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
from gimbal.core.boostrap import bootstrap, shutdown
from gimbal.core.runner import Engine
from gimbal.log import get_logger
from gimbal.schema.scenario import Scenario

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

    # 1. 协调资产来源 → 解析资产
    resolved_source = resolve_source(source, no_cache, cache_only)
    asset_store = _build_default_asset_store(Path(registry) if registry else None)
    logger.debug("[CLI] asset_store ready: backend={}", asset_store.backend_name)

    resolver = AssetResolver(
        kind=AssetKind.SCENARIO,
        asset_store=asset_store,
        source=resolved_source.value,
        registry=registry,
    )
    matched = resolver.resolve(scenario_ids)

    # 2. 零匹配处理
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

    # 3. dry-run：仅解析 + 校验，不执行
    if dry_run:
        for asset in matched:
            try:
                Scenario.model_validate(asset.content.parsed)
            except Exception as exc:
                typer.secho(f"[{asset.id}] 校验失败: {exc}", fg=typer.colors.RED, err=True)
                raise typer.Exit(code=2)
            typer.secho(f"[{asset.id}] OK (dry-run)", fg=typer.colors.CYAN)
        raise typer.Exit(code=0)

    # 4. 引导框架：上下文注入 + 配置合并 + 基础设施初始化
    cli_ctx.env = env
    cli_ctx.mode = mode
    cli_ctx.log_level = log_level.value
    try:
        configuration = bootstrap(cli_ctx)
    except Exception as exc:  # noqa: BLE001
        logger.exception("[CLI] bootstrap 失败: {}", exc)
        typer.secho(f"Framework bootstrap failed: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=4)

    # 5. 解析 + 校验每个匹配到的资产
    scenarios: list[tuple[str, Scenario]] = []
    for asset in matched:
        try:
            sc = Scenario.model_validate(asset.content.parsed)
        except Exception as exc:  # noqa: BLE001
            logger.exception("[CLI] scenario 校验失败: id={} err={}", asset.id, exc)
            typer.secho(
                f"Scenario validation failed for {asset.id}: {exc}",
                fg=typer.colors.RED, err=True,
            )
            shutdown(configuration)
            raise typer.Exit(code=2)
        scenarios.append((asset.id, sc))

    # 6. 构造 Engine（注入 asset_store 用于 Phase 0 引用物化），逐个执行
    engine = Engine(configuration, asset_store=asset_store)
    try:
        results = []
        for original_id, sc in scenarios:
            logger.info("[CLI] 执行 scenario: id={} scenario_id={}", original_id, sc.scenarioId)
            result = engine.run(sc)
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

    # 7. 汇总输出
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

