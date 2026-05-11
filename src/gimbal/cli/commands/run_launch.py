"""gimbal run launch —— 直接解析传入的路径文本信息，发送请求"""
from __future__ import annotations

import sys
from typing import Annotated

import typer

from gimbal.cli.common import (
    AllowEmptyOpt, DryRunOpt, EnvOpt, LogLevel, LogLevelOpt,
    InputFormat, FormatOpt, TagOpt, TimeoutOpt, VarFileOpt, VarOpt, YesOpt,
    parse_parallel, parse_vars,
)
from gimbal.cli.context import CLIContext
from gimbal.core.asset_resolver import AssetKind
from gimbal.core.runner import LocalMatcher, Runner, RunRequest

def launch(
    ctx: typer.Context,
    # ========== 输入控制 ==========
    source: Annotated[
        str | None, 
        typer.Argument(help="文件路径或 '-' 表示 stdin", metavar="SOURCE")
        ] = None,
    inline: Annotated[
        str | None, 
        typer.Option("--inline", help="直接传内容", rich_help_panel="输入控制")
        ] = None,
    fmt: FormatOpt = InputFormat.auto,
    # ========== 通用(复用) ==========
    env: EnvOpt = "dev",
    log_level: LogLevelOpt = LogLevel.info,
    var: VarOpt = None,
    var_file: VarFileOpt = None,
    tag: TagOpt = None,
    dry_run: DryRunOpt = False,
    # ========== launch 特有 ==========
    persist: Annotated[bool, typer.Option("--persist/--no-persist", help="是否持久化结果,调试默认不持久化", rich_help_panel="执行控制")] = False,
) -> None:
    """指定标准输入，用例文件或inline内容交给框架直接执行。

    [bold]示例：[/bold]
      文件路径:    
        gimbal run launch ./debug.yaml\
      内联字符串:      
        gimbal run launch --inline '{"name":"x"}' -f json
      标准输入(stdin): 
        cat case.yaml | gimbal run launch - -f yaml
    """
    clictx : CLIContext = ctx.obj
    clictx.action_path = "run.launch"