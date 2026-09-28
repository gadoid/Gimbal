"""run 子命令组。

Typer 风格：每个子命令组是一个独立的 Typer 实例，用 register_command 注册。
"""
from __future__ import annotations

import typer

from gimbal.cli.commands.run_server import server
from gimbal.cli.commands.run_launch import launch
from gimbal.cli.commands.run_show import show
from gimbal.cli.commands.run_target import scenario, suite


run_app = typer.Typer(
    name="run",
    help=(
        "执行测试。\n\n"
        "执行模式：\n"
        "  server    作为服务监听端口接收任务\n"
        "  launch    直接接收文件信息进行加载执行\n"
        "  show      只读展示 Scenario 的步骤索引 → 描述映射（不执行，方便决定 --step-to）"
    ),
    no_args_is_help=True,
)


# 注册子命令
run_app.command("server")(server)
run_app.command("launch")(launch)
run_app.command("show")(show)
run_app.command("scenario")(scenario)   # v2.1 批次 B：隐式 aggregate Plan 单路径
run_app.command("suite")(suite)         # v2.1 批次 B：aggregate Plan（并行策略生效）