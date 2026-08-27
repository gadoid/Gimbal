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
    _build_default_asset_store, _print_run_report, _publish_run_meta,
    parse_parallel, parse_vars, resolve_source,
)
from gimbal.cli.context import CLIContext
from gimbal.core.asset_resolver import AssetKind, AssetResolver
from gimbal.core.bootstrap import bootstrap, shutdown
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
    """Typer 命令：解析 scenario_ids → bootstrap 框架 → Engine 串行/并行执行每个 Scenario，汇总后退出。

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
    # breakpoint_at 仅与 step_to 互斥提示（不强制）：当同时给两者，优先级：
    #   1. step_to 优先（用户最明确的"执行到 X 停止"意图）
    #   2. breakpoint_at 适合交互模式（暂停 / 排查），非本阶段 1 范围
    if breakpoint_at is not None and step_to is not None:
        logger.warning(
            "[CLI] --step-to={} 与 --breakpoint={} 同时设置；优先使用 --step-to，"
            "--breakpoint 将在阶段 2 引入",
            step_to, breakpoint_at,
        )

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
    # 把 reporter 选项注入 extras，由 ConfigLoader._from_cli()提取为 BootstrapConfig.reporters
    if reporter:
        cli_ctx.extras["reporters"] = list(reporter)
    if report_dir:
        cli_ctx.extras["report_dir"] = report_dir
    # 把 --var / --var-file 注入 extras，供 SpecResolver 模板解析时使用
    parsed_vars = parse_vars(var)
    if var_file:
        from pathlib import Path
        import yaml as _yaml
        for vf in var_file:
            from gimbal.utils.jsonpath import _parse_filter_value  # noqa: F401  仅确保 import
            # 修复 #7：--var-file 错误升级为 Exit(2)，不静默吞。
            # 用户显式传的参数，YAML 解析错误/IO 错误/根不是 dict 都要快速失败，
            # 否则后续模板 ${var.x} 全解析为 None，错误信息指向 preprocessor 而不是 --var-file。
            try:
                with open(vf, "r", encoding="utf-8") as fh:
                    file_vars = _yaml.safe_load(fh)
            except Exception as exc:
                logger.error("[CLI] 加载 --var-file 失败: path={} error={}", vf, exc)
                typer.secho(
                    f"Error: failed to load --var-file {vf}: {exc}",
                    fg=typer.colors.RED, err=True,
                )
                raise typer.Exit(code=2)
            if file_vars is None:
                file_vars = {}
            if not isinstance(file_vars, dict):
                logger.error(
                    "[CLI] --var-file 根必须是 mapping: path={} got={}",
                    vf, type(file_vars).__name__,
                )
                typer.secho(
                    f"Error: --var-file {vf} root must be a mapping, "
                    f"got {type(file_vars).__name__}",
                    fg=typer.colors.RED, err=True,
                )
                raise typer.Exit(code=2)
            parsed_vars.update(file_vars)
    if parsed_vars:
        cli_ctx.extras["vars"] = parsed_vars
    try:
        configuration = bootstrap(cli_ctx)
    except Exception as exc:  # noqa: BLE001
        logger.exception("[CLI] bootstrap 失败: {}", exc)
        typer.secho(f"Framework bootstrap failed: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=4)

    # 4.5 发布 RunMetaEvent（CI/CD / git / 触发人等上下文），reporter 通过订阅此事件
    #     获取头部 meta 区。必须在 bootstrap 之后、Engine.run() 之前 publish。
    #     注意：此时 reporter_runtime 已 setup 但还没 begin_all——内置 reporter
    #     （console / junit / im_notifier 等）的订阅是在 Engine.run() 内部
    #     begin_all 时才建立的。所以这里 publish 的 RunMetaEvent 主要被"在
    #     bootstrap 阶段就通过插件或代码显式订阅的 listener"消费，**不是**被
    #     内置 reporter 消费（内置 reporter 通过 ScenarioStartEvent / RunEndEvent
    #     等其他事件拿到 framework_ctx 后再读取 framework_ctx 的 meta）。
    _publish_run_meta(configuration)

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
    #    阶段 1 最小子集：把 CLI 的 --step-from / --step-to 真正接到 Engine。
    #    --step-from 当前实现是"从 start_idx 开始"语义，但 ScenarioRunner.run()
    #    还没支持 start_idx；这里先只对 --step-to 实现 halt，
    #    step_from 用浅层截断 resolved_steps 不可能（preprocessor 内部），故 stage 1 只
    #    实现 step_to；step_from 在阶段 2 引入 StepResolver 时一并支持。
    from gimbal.core.scenario_runner import RuntimeControl

    # 优先级：step_to > breakpoint_at > 默认（不控制）
    runtime_control: RuntimeControl | None = None
    if step_to is not None:
        runtime_control = RuntimeControl(
            halt_at=step_to,
            halt_reason=f"cli --step-to={step_to}",
        )
    elif breakpoint_at is not None and breakpoint_at:
        # breakpoint_at 是 list[int]，取首个；interactive 模式在 stage 2 实现完整版
        runtime_control = RuntimeControl(
            halt_at=breakpoint_at[0],
            halt_reason=f"cli --breakpoint={breakpoint_at[0]}",
        )
    if step_from is not None:
        # step_from 在当前 ScenarioRunner 中未支持；显式提示，避免静默忽略。
        typer.secho(
            f"[warn] --step-from={step_from} 当前版本暂未生效（将在阶段 2 引入 StepResolver 后支持）。\n"
            f"       当前阶段 1 仅支持 --step-to 与 --breakpoint。",
            fg=typer.colors.YELLOW, err=True,
        )

    engine = Engine(configuration, asset_store=asset_store)
    try:
        results = []
        for original_id, sc in scenarios:
            logger.info("[CLI] 执行 scenario: id={} scenario_id={}", original_id, sc.scenarioId)
            result = engine.run(sc, runtime_control=runtime_control)
            results.append(result)
            # fail_fast 与 halted 的语义叠加：halted 视为未通过，触发 fail_fast
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
        halted=sum(r.halted for r in results),
        details=[d for r in results for d in r.details],
    )
    _print_run_report(merged, output, artifacts=engine.artifacts)
    raise typer.Exit(code=merged.exit_code)

