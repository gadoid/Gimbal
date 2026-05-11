"""run 子命令组。

Typer 风格：每个子命令组是一个独立的 Typer 实例，用 register_command 注册。
"""
from __future__ import annotations

import typer

from gimbal.cli.commands.run_match import match
from gimbal.cli.commands.run_scenario import scenario
from gimbal.cli.commands.run_server import server
from gimbal.cli.commands.run_suite import suite


run_app = typer.Typer(
    name="run",
    help=(
        "执行测试。\n\n"
        "四种执行模式：\n"
        "  suite     按 ID 执行已注册的 Suite 资产（支持命名空间通配）\n"
        "  scenario  按 ID 执行已注册的 Scenario 资产（支持命名空间通配）\n"
        "  match     按路径/模式匹配本地未注册的用例文件\n"
        "  server    作为服务监听端口接收任务"
    ),
    no_args_is_help=True,
)


# 注册子命令
run_app.command("suite")(suite)
run_app.command("scenario")(scenario)
run_app.command("match")(match)
run_app.command("server")(server)