"""gimbal/logging/intercept.py

InterceptHandler — stdlib logging → loguru 桥接器。

工作原理
--------
Python 的 logging.Handler.emit() 在每条日志记录到达时被调用。
InterceptHandler 重写 emit()，将 logging.LogRecord 转换为等价的
loguru 调用，保持原始调用位置（module / function / line）不变。

为什么需要 depth 参数
---------------------
loguru 默认从调用 logger.xxx() 的帧开始记录位置信息。
当消息来自 stdlib logging 时，调用栈比正常情况深了若干帧（emit → handle →
callHandlers → … → 实际业务代码）。通过 `logger.opt(depth=depth)` 告诉
loguru 向上回溯多少帧，使记录的位置信息指向真正的业务代码，而不是这个桥接器。

参考
----
https://loguru.readthedocs.io/en/stable/recipes.html#capturing-standard-logging-messages
"""
from __future__ import annotations

import logging

from loguru import logger


class InterceptHandler(logging.Handler):
    """将 stdlib logging 消息重定向到 loguru。

    注册方式（在 setup_logging 中完成，用户无需手动调用）::

        logging.basicConfig(handlers=[InterceptHandler()], level=logging.DEBUG)
    """

    def emit(self, record: logging.LogRecord) -> None:
        """把一条 stdlib logging 记录转换为 loguru 调用，保持原始位置和异常信息。"""
        # 将 logging 级别名映射到 loguru 级别名
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            # 未知级别（某些库使用自定义级别号）直接用数字
            level = record.levelno

        # 计算回溯深度：从当前帧向上找到第一个不属于 logging 模块的帧
        frame = logging.currentframe()
        depth = 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back  # type: ignore[assignment]
            depth += 1

        # 使用 opt(depth=…, exception=…) 保留原始位置和异常信息
        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )