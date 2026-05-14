"""gimbal CLI 主入口
命令树：
    gimbal
    └── run
        ├── suite     - 按 ID 执行 Suite 资产
        ├── scenario  - 按 ID 执行 Scenario 资产
        ├── match     - 按路径/模式匹配本地文件执行
        └── server    - 作为服务监听任务
"""
from __future__ import annotations

import typer

from gimbal.cli.context import CLIContext
from gimbal.cli.params import starter, ConfigFile, NoColor, LogLevel, ShowVersion


@starter.callback()
def main(
    ctx: typer.Context,
    config: ConfigFile = None,
    no_color: NoColor= False,
    version: ShowVersion = False,
    log_level : LogLevel = "info"
) -> None:
    """回调入口方法：初始化共享上下文。"""
    ctx.obj = CLIContext(
        config_file=config,
        no_color=no_color,
        log_level=log_level
    )



if __name__ == "__main__":
    starter()