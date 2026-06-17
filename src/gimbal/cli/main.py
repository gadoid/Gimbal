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

import signal
import sys
import typer

from gimbal.cli.context import CLIContext
from gimbal.cli.params import starter, ConfigFile, NoColor, ShowVersion
# 修复 #40：从 common 导入 LogLevel（enum），不是从 params 导入（已删除）
from gimbal.cli.common import LogLevel


# 修复 B8：SIGINT (Ctrl-C) 信号处理
# 注册一个全局 handler 设置 cancel flag；Engine/StateMachine 在 step 之间检查
_cancelled = False


def _set_cancelled(signum, frame):
    """SIGINT handler: 设置全局 cancel flag，下个 step 检查后停止。"""
    """首次 SIGINT 置位 cancel flag 并提示；第二次 SIGINT 直接抛 KeyboardInterrupt 强制终止。"""
    global _cancelled
    if not _cancelled:
        _cancelled = True
        # 用 stderr 输出，避免破坏 stdout 缓冲
        print(
            "\n[gimbal] SIGINT 收到，将在当前 step 完成后退出..."
            "（再按一次强制退出）",
            file=sys.stderr, flush=True,
        )
    else:
        # 第二次 Ctrl-C：立即退出（保留 KeyboardInterrupt 的标准行为）
        raise KeyboardInterrupt()


def is_cancelled() -> bool:
    """检查是否被 SIGINT 取消。"""
    """返回全局 cancel flag 当前值，True 表示已收到 SIGINT 等待下次 step 边界退出。"""
    return _cancelled


def reset_cancelled():
    """重置 cancel flag（用于新一次运行）。"""
    """把全局 cancel flag 复位为 False，供新一次 CLI 启动时复用。"""
    global _cancelled
    _cancelled = False


def _install_sigint_handler() -> None:
    """在 CLI 真正被调用时安装 SIGINT handler。

    修复 #B7：不要在 import 期执行 signal.signal() —— 这会覆盖 pytest/IDE/
    其他工具已注册的 handler。在 typer callback（main）执行时注册能覆盖
    `gimbal` (entry script) 与 `python -m gimbal` 两条入口路径。
    """
    try:
        signal.signal(signal.SIGINT, _set_cancelled)
    except (ValueError, AttributeError):
        # Windows 子线程 / 非主线程无法注册；忽略
        pass


@starter.callback()
def main(
    ctx: typer.Context,
    config: ConfigFile = None,
    no_color: NoColor= False,
    version: ShowVersion = False,
    log_level : LogLevel = LogLevel.info
) -> None:
    """Typer 回调入口：安装 SIGINT handler 并把 CLIContext 写入 ctx.obj 供子命令共享。"""
    """回调入口方法：初始化共享上下文。"""
    _install_sigint_handler()
    ctx.obj = CLIContext(
        config_file=config,
        no_color=no_color,
        log_level=log_level
    )



if __name__ == "__main__":
    _install_sigint_handler()
    starter()