"""gimbal run match —— 按路径/模式匹配本地未注册文件执行。"""
from __future__ import annotations

import sys
from typing import Annotated

import typer

from gimbal.cli.common import (
    AllowEmptyOpt, DryRunOpt, EnvOpt, FailFastOpt, LogLevel, LogLevelOpt,
    OutputFormat, OutputOpt, ParallelOpt, ModeOpt, ReportDirOpt,
    ReporterOpt, RetryOpt, TagOpt, TimeoutOpt, VarFileOpt, VarOpt, YesOpt,
    parse_parallel, parse_vars,
)
from gimbal.cli.context import CLIContext
from gimbal.core.asset_resolver import AssetKind
from gimbal.core import bootstrap,runner



def match(
    ctx: typer.Context,
    patterns: Annotated[
        list[str] | None,
        typer.Argument(
            help="匹配模式，支持路径 glob、id:xxx、name:xxx、tag:xxx、file::case 等。",
            metavar="PATTERN...",
        ),
    ] = None,
    # ========== 搜索路径 ==========
    path: Annotated[
        list[str] | None,
        typer.Option(
            "--path",
            help="限定搜索根目录，可重复。",
            rich_help_panel="搜索范围",
            exists=True, file_okay=False,
        ),
    ] = None,
    recursive: Annotated[
        bool,
        typer.Option(
            "--recursive/--no-recursive",
            help="是否递归子目录。",
            rich_help_panel="搜索范围",
        ),
    ] = True,
    include: Annotated[
        list[str] | None,
        typer.Option("--include", help="包含 glob，可重复。", rich_help_panel="搜索范围"),
    ] = None,
    exclude: Annotated[
        list[str] | None,
        typer.Option("--exclude", help="排除 glob，可重复。", rich_help_panel="搜索范围"),
    ] = None,
    # ========== 增量与重跑 ==========
    changed_only: Annotated[
        bool,
        typer.Option("--changed-only", help="只跑 git 改动过的用例。", rich_help_panel="增量与重跑"),
    ] = False,
    changed_since: Annotated[
        str,
        typer.Option("--changed-since", help="配合 --changed-only，git ref。", rich_help_panel="增量与重跑"),
    ] = "HEAD~1",
    last_failed: Annotated[
        bool,
        typer.Option("--last-failed", help="只重跑上次失败的用例。", rich_help_panel="增量与重跑"),
    ] = False,
    last_failed_first: Annotated[
        bool,
        typer.Option("--last-failed-first", help="上次失败的优先执行。", rich_help_panel="增量与重跑"),
    ] = False,
    # ========== 调试辅助 ==========
    collect_only: Annotated[
        bool,
        typer.Option("--collect-only", help="只收集不执行，列出会跑哪些。", rich_help_panel="调试辅助"),
    ] = False,
    shuffle: Annotated[
        bool,
        typer.Option("--shuffle", help="打乱执行顺序。", rich_help_panel="调试辅助"),
    ] = False,
    seed: Annotated[
        int | None,
        typer.Option("--seed", help="随机种子，用于 --shuffle 复现。", rich_help_panel="调试辅助"),
    ] = None,
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
    """Typer 命令：按路径 glob/查询表达式匹配本地未注册的用例文件并执行（不依赖资产注册表）。"""
    """按路径或表达式匹配本地未注册的用例文件并执行。

    [bold]示例：[/bold]

      gimbal run match "tests/customs/**/*.yaml"
      gimbal run match "id:sc-customs-*" --tag=smoke
      gimbal run match --changed-only --changed-since=main
      gimbal run match "tests/**" --collect-only
      gimbal run match --last-failed
    """
    cli_ctx: CLIContext = ctx.obj

    if not patterns and not (last_failed or changed_only):
        raise typer.BadParameter(
            "必须至少提供一个 PATTERN，或使用 --last-failed / --changed-only。"
        )


