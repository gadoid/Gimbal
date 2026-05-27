"""gimbal/logging/setup.py — setup_logging() 唯一初始化入口。"""
from __future__ import annotations

import logging
import sys
from typing import Optional

from loguru import logger

from .config import LoggingConfig
from .formatters import make_console_sink, make_file_sink
from .intercept import InterceptHandler

_INTERCEPT_INSTALLED = False


def setup_logging(config: Optional[LoggingConfig] = None) -> None:
    """初始化 loguru 日志系统（幂等，可多次调用）。

    每次调用：
      1. 清除所有已注册 sink
      2. 注册 console sink（彩色 / 纯文本 / JSON，根据 config 自动选择）
      3. 若 config.log_file 不为 None，注册 file sink
      4. 安装 stdlib logging 拦截器（仅首次）
      5. 静默高频三方库的 DEBUG 噪音
    """
    global _INTERCEPT_INSTALLED

    cfg = config or LoggingConfig()

    logger.remove()

    # ── Console sink ─────────────────────────────────────
    console_kwargs = make_console_sink(
        stream=sys.stderr,
        no_color=cfg.no_color,
        json_mode=cfg.json_mode,
        show_path=cfg.show_path,
        level=cfg.level,
        backtrace=cfg.backtrace,
        diagnose=cfg.diagnose,
    )
    logger.add(**console_kwargs)

    # ── File sink（可选）────────────────────────────────────
    if cfg.log_file is not None:
        cfg.log_file.parent.mkdir(parents=True, exist_ok=True)
        file_kwargs = make_file_sink(
            path=cfg.log_file,
            file_json=cfg.file_json,
            show_path=True,
            level=cfg.level,
            rotation=cfg.rotation,
            retention=cfg.retention,
            compression=cfg.compression,
            backtrace=cfg.backtrace,
            diagnose=cfg.diagnose,
        )
        logger.add(**file_kwargs)

    # ── stdlib intercept（幂等）─────────────────────────────
    if not _INTERCEPT_INSTALLED:
        _install_intercept()
        _INTERCEPT_INSTALLED = True

    _silence_noisy_loggers()


def _install_intercept() -> None:
    intercept = InterceptHandler()
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(intercept)
    root.setLevel(logging.DEBUG)
    for name in logging.root.manager.loggerDict:
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True


def _silence_noisy_loggers() -> None:
    for name in ["httpx", "httpcore", "httpcore.connection", "httpcore.http11", "urllib3", "asyncio"]:
        logging.getLogger(name).setLevel(logging.WARNING)


def reset_logging() -> None:
    """测试辅助：重置所有 sink 和拦截标志。"""
    global _INTERCEPT_INSTALLED
    logger.remove()
    _INTERCEPT_INSTALLED = False