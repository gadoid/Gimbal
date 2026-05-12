"""CLI 上下文。

Typer 通过 ctx.obj 传递跨子命令的共享状态，机制和 Click 一致
（Typer 本质就是 Click 的类型注解封装）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class CLIContext:
    """CLI 全局上下文。"""

    config_file: Path | None = None
    profile: str = "default"
    env: str = "dev"

    log_level: str = "info"
    no_color: bool = False
    verbose: bool = False

    extras: dict[str, Any] = field(default_factory=dict)
