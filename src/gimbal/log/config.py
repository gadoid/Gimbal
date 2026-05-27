"""gimbal/logging/config.py

LoggingConfig — 日志系统的完整配置快照。

与 BootstrapConfig 协作：BootstrapConfig 持有 LoggingConfig 字段（或直接内联），
bootstrap() 拿到 BootstrapConfig 后调用 setup_logging(cfg.logging) 完成初始化。

字段设计原则：
  - 每个字段有合理默认值，零配置可直接运行
  - no_color 由 CLI --no-color flag 或 NO_COLOR 环境变量驱动（遵守 POSIX 规范）
  - json_mode 专为 CI / 机器消费设计，启用后 console sink 输出 JSON 而非彩色文本
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict, model_validator


class LoggingConfig(BaseModel):
    """日志系统配置快照（不可变）。"""

    model_config = ConfigDict(frozen=True)

    # ── 级别 ──────────────────────────────────────────────
    level: str = Field(
        default="INFO",
        description="日志级别：DEBUG / INFO / WARNING / ERROR / CRITICAL",
    )

    # ── 终端输出 ──────────────────────────────────────────
    no_color: bool = Field(
        default=False,
        description=(
            "禁用彩色输出。自动检测 NO_COLOR 环境变量（https://no-color.org/），"
            "也可由 CLI --no-color 覆盖。"
        ),
    )
    json_mode: bool = Field(
        default=False,
        description=(
            "终端输出切换为 JSON 行（适合 CI 管道 / ELK 消费）。"
            "启用后 no_color 自动生效，Rich 格式化被跳过。"
        ),
    )
    show_path: bool = Field(
        default=False,
        description="是否在终端日志行中显示 module:line 位置信息（DEBUG 模式下建议开启）。",
    )

    # ── 文件输出 ──────────────────────────────────────────
    log_file: Optional[Path] = Field(
        default=None,
        description=(
            "日志文件路径，支持 loguru 时间占位符，例如 ./logs/gimbal_{time}.log。"
            "为 None 时不开启文件 sink。"
        ),
    )
    rotation: str = Field(
        default="00:00",
        description="日志文件轮转策略，例如 '00:00'（每日凌晨）或 '100 MB'。",
    )
    retention: str = Field(
        default="7 days",
        description="日志文件保留策略，例如 '7 days' 或 '10 files'。",
    )
    compression: str = Field(
        default="gz",
        description="轮转后的压缩格式：'gz' / 'zip' / 'bz2'，或空字符串禁用。",
    )
    file_json: bool = Field(
        default=False,
        description="文件 sink 是否使用 JSON 格式（与 json_mode 独立控制，适合同时要彩色终端+JSON 文件）。",
    )

    # ── 诊断 ──────────────────────────────────────────────
    diagnose: bool = Field(
        default=False,
        description="loguru 诊断模式：异常帧中显示变量值，生产环境需关闭（可能泄露敏感数据）。",
    )
    backtrace: bool = Field(
        default=True,
        description="异常时是否显示完整调用链（含 loguru 装饰器之前的帧）。",
    )

    # ── 自动修正 ──────────────────────────────────────────
    @model_validator(mode="after")
    def _auto_adjust(self) -> "LoggingConfig":
        """json_mode 启用时自动关闭 diagnose，避免 ANSI 污染 JSON 字段。"""
        # frozen model 不允许直接赋值，用 object.__setattr__ 绕过
        if self.json_mode and self.diagnose:
            object.__setattr__(self, "diagnose", False)
        return self

    @classmethod
    def from_bootstrap(
        cls,
        level: str = "INFO",
        no_color: bool = False,
        **extras: object,
    ) -> "LoggingConfig":
        """从 BootstrapConfig 的扁平字段构造 LoggingConfig 的便捷方法。

        用法::

            logging_cfg = LoggingConfig.from_bootstrap(
                level=bootstrap_cfg.log_level.upper(),
                no_color=bootstrap_cfg.no_color,
            )
        """
        # 尊重 NO_COLOR 环境变量（https://no-color.org/）
        env_no_color = "NO_COLOR" in os.environ
        return cls(
            level=level.upper(),
            no_color=no_color or env_no_color,
            **{k: v for k, v in extras.items() if v is not None},
        )