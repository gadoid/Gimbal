"""gimbal/logging/integration.py

将 GIMBAL 现有配置体系接入日志系统的适配层。

这个文件是"胶水层"——它不改变任何现有模块，只负责：
  1. 从 BootstrapConfig 提取日志相关字段，构造 LoggingConfig
  2. 替换 bootstrap.py 中旧的 _configure_logging() 实现
  3. 提供 Typer callback 中可直接使用的辅助函数

迁移路径（对现有代码的修改量最小）
------------------------------------
Step 1 — 在 config/models.py 的 BootstrapConfig 中增加一个字段（可选）：

    from gimbal.logging import LoggingConfig
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

Step 2 — 在 core/bootstrap.py 中替换 _configure_logging()：

    # 旧代码
    from gimbal.logging import _configure_logging
    _configure_logging(cfg)

    # 新代码
    from gimbal.logging.integration import configure_logging_from_bootstrap
    configure_logging_from_bootstrap(cfg)

Step 3 — 业务模块替换 stdlib import：

    # 旧代码
    import logging
    logger = logging.getLogger(__name__)

    # 新代码
    from gimbal.logging import get_logger
    logger = get_logger(__name__)
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from gimbal.config.models import BootstrapConfig
    from gimbal.cli.context import CLIContext

from .config import LoggingConfig
from .setup import setup_logging


def configure_logging_from_bootstrap(cfg: "BootstrapConfig") -> None:
    """从 BootstrapConfig 初始化日志系统。

    这是对 core/bootstrap.py 中 _configure_logging(cfg) 的直接替换。
    将此函数放在 ConfigLoader().load() 之后、任何 logger 调用之前。

    Parameters
    ----------
    cfg:
        完成合并的 BootstrapConfig 实例（frozen）。

    Notes
    -----
    日志文件路径规则：
      - 若 cfg 包含 extras["log_file"]，则使用该路径
      - 否则不开启文件 sink（CI 场景不需要文件）
      - 可通过 GIMBAL_LOG_FILE 环境变量覆盖
    """
    import os

    # 从 extras 或环境变量读取文件路径（不在 BootstrapConfig 核心字段中，避免破坏现有模型）
    log_file_raw: Optional[str] = (
        cfg.extras.get("log_file")           # type: ignore[attr-defined]
        if hasattr(cfg, "extras") and cfg.extras
        else None
    ) or os.environ.get("GIMBAL_LOG_FILE")

    log_file = Path(log_file_raw) if log_file_raw else None

    # json_mode：CI 环境（无 tty）默认开启，除非显式关闭
    import sys
    json_mode_default = not sys.stderr.isatty()
    json_mode = bool(
        (cfg.extras.get("json_mode") if hasattr(cfg, "extras") and cfg.extras else None)
        or os.environ.get("GIMBAL_LOG_JSON", "")
        or json_mode_default
    )

    # show_path：DEBUG 级别时自动开启
    show_path = cfg.log_level.upper() == "DEBUG"

    logging_cfg = LoggingConfig(
        level=cfg.log_level.upper(),
        no_color=cfg.no_color,
        json_mode=json_mode,
        show_path=show_path,
        log_file=log_file,
        # diagnose 仅在 DEBUG 模式开启，生产环境不暴露变量值
        diagnose=cfg.log_level.upper() == "DEBUG",
    )

    setup_logging(logging_cfg)


def configure_logging_from_cli(cli_ctx: "CLIContext") -> None:
    """从 CLIContext 进行早期日志初始化（bootstrap() 之前）。

    在 CLI callback（main()）中调用，使得 bootstrap() 过程本身的日志也能被捕获。

    Parameters
    ----------
    cli_ctx:
        Typer 传入的 CLIContext，此时 BootstrapConfig 尚未合并。
    """
    import os
    import sys

    no_color = cli_ctx.no_color or ("NO_COLOR" in os.environ)
    level = cli_ctx.log_level.upper() if cli_ctx.log_level else "INFO"

    # 早期阶段：不开启文件 sink，不开启 JSON（尚不知道最终配置）
    logging_cfg = LoggingConfig(
        level=level,
        no_color=no_color,
        json_mode=False,
        show_path=level == "DEBUG",
        diagnose=level == "DEBUG",
    )
    setup_logging(logging_cfg)