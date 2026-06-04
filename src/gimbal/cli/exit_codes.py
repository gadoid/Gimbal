"""gimbal CLI 退出码。

集中定义以避免 `gimbal.cli.params` 与子命令模块之间的循环导入。

约定（与 sysexits.h 风格兼容）：

    0   正常完成
    1   测试失败
    2   使用错误（参数/CLI 用法）
    3   资产未找到
    4   系统/运行时错误
    5   无匹配
"""
from __future__ import annotations

EXIT_OK = 0
EXIT_TEST_FAILED = 1
EXIT_USAGE_ERROR = 2
EXIT_ASSET_NOT_FOUND = 3
EXIT_SYSTEM_ERROR = 4
EXIT_NO_MATCH = 5

__all__ = [
    "EXIT_OK",
    "EXIT_TEST_FAILED",
    "EXIT_USAGE_ERROR",
    "EXIT_ASSET_NOT_FOUND",
    "EXIT_SYSTEM_ERROR",
    "EXIT_NO_MATCH",
]
