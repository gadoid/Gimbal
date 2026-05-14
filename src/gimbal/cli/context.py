"""CLI 上下文。

Typer 通过 ctx.obj 传递跨子命令的共享状态，机制和 Click 一致
（Typer 本质就是 Click 的类型注解封装）。
"""
from __future__ import annotations

from pydantic import BaseModel, Field
from pathlib import Path
from typing import Any


class CLIContext(BaseModel):
    """CLI 全局上下文。"""

    config_file: Path | None = None
    mode: str = "local"
    env: str = "dev"
    report_dir: str = "./report/"
    log_level: str = "info"
    no_color: bool = False

    extras: dict[str, Any] = Field(default_factory=dict)
