from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from gimbal.cli.commands.run import run_app
from gimbal.cli.commands.self_check import self_check
from gimbal.cli.commands.asset import asset_app

# 退出码集中定义在 gimbal.cli.exit_codes，避免与子命令模块形成循环导入。
from gimbal.cli.exit_codes import (  # noqa: E402,F401
    EXIT_OK,
    EXIT_TEST_FAILED,
    EXIT_USAGE_ERROR,
    EXIT_ASSET_NOT_FOUND,
    EXIT_SYSTEM_ERROR,
    EXIT_NO_MATCH,
)

starter = typer.Typer(
    name="gimbal",
    help=(
        "gimbal_engine —— 一个为现代测试场景而生的自动化测试框架。\n\n"
        "常用示例：\n"
        "  gimbal run suite customs-declare\n"
        "  gimbal run scenario sc-001 sc-002\n"
        '  gimbal run match "tests/**/*.yaml"\n'
        "  gimbal run server --port=8765\n"
        "  gimbal asset push customs/declare:v1 -f suite.json\n"
        "  gimbal asset list customs\n"
        "  gimbal self-check            验证框架基础设施"
    ),
    context_settings={"help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
    rich_markup_mode="rich",
    add_completion=True,
)
starter.add_typer(run_app, name="run")
# asset 是顶层命令（不是 run 的子命令），因为它不执行任何测试，只管理仓库
starter.add_typer(asset_app, name="asset")
# self-check 是顶层命令（不是 run 的子命令），因为它不执行任何测试
starter.command("self-check")(self_check)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo("gimbal 0.1.0")
        raise typer.Exit()

# ======================  配置项参数信息  ======================

OPT_CONFIG = typer.Option(
    "--config", "-c",
    help="配置文件路径，默认查找 ./gimbal.yaml 或 ~/.gimbal/config.yaml。",
    exists=True,
    dir_okay=False,
)

OPT_NO_COLOR = typer.Option(
    "--no-color",
    help="关闭彩色输出（CI 友好）。",
)

OPT_VERSION = typer.Option(
    "--version",
    help="显示版本并退出。",
    callback=_version_callback,
    is_eager=True,
)

OPT_LOGLEVEL = typer.Option(
    "--log-level",
    help="详细输出，等价于 --log-level=debug。",
)

ConfigFile = Annotated[Path | None, OPT_CONFIG]
NoColor = Annotated[bool, OPT_NO_COLOR]
ShowVersion = Annotated[bool, OPT_VERSION]
LogLevel = Annotated[str, OPT_LOGLEVEL]