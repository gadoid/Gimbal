"""gimbal/logging/formatters.py

三种格式化器：

  ColorFormatter   — Rich ANSI 彩色终端，开发调试首选
  PlainFormatter   — 无颜色纯文本，CI / --no-color
  JsonFormatter    — JSON sink，机器消费 / ELK

设计约定
--------
- ColorFormatter / PlainFormatter 是 loguru format 字符串工厂（__call__ 返回格式字符串）
- JsonFormatter 是 loguru sink 本身（__call__ 接收 loguru Message，直接写入流）
  这是必须的：JSON 内容含花括号，如果走 loguru 的字符串插值会引发 KeyError

级别颜色
--------
  DEBUG    → dim blue（低调，调试噪音）
  INFO     → 默认前景
  SUCCESS  → bold green
  WARNING  → yellow
  ERROR    → bold red
  CRITICAL → bold white + bg red
"""
from __future__ import annotations

import json
import sys
from datetime import timezone
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Record, Message

# ── 常量 ──────────────────────────────────────────────────────────────────────

_LEVEL_STYLES: dict[str, str] = {
    "TRACE":    "<dim><cyan>",
    "DEBUG":    "<dim><blue>",
    "INFO":     "<level>",
    "SUCCESS":  "<bold><green>",
    "WARNING":  "<yellow>",
    "ERROR":    "<bold><red>",
    "CRITICAL": "<bold><white><bg red>",
}
_LEVEL_CLOSING: dict[str, str] = {
    "TRACE":    "</cyan></dim>",
    "DEBUG":    "</blue></dim>",
    "INFO":     "</level>",
    "SUCCESS":  "</green></bold>",
    "WARNING":  "</yellow>",
    "ERROR":    "</red></bold>",
    "CRITICAL": "</bg red></white></bold>",
}
_LEVEL_WIDTH = 8


# ── 彩色格式化器 ──────────────────────────────────────────────────────────────

class ColorFormatter:
    """返回 loguru format 字符串（含颜色标签）。

    Parameters
    ----------
    show_path : 是否显示 module:function:line
    """

    def __init__(self, *, show_path: bool = False) -> None:
        self._show_path = show_path

    def __call__(self, record: "Record") -> str:
        level_name: str = record["level"].name
        open_tag  = _LEVEL_STYLES.get(level_name, "<level>")
        close_tag = _LEVEL_CLOSING.get(level_name, "</level>")

        time_str  = "<dim>{time:YYYY-MM-DD HH:mm:ss.SSS}</dim>"
        level_str = f"{open_tag}{{level:<{_LEVEL_WIDTH}}}{close_tag}"

        if self._show_path:
            location = "<dim>{name}:{function}:{line}</dim>"
            return f"{time_str} | {level_str} | {location} - {{message}}\n{{exception}}"
        return f"{time_str} | {level_str} | {{message}}\n{{exception}}"


# ── 纯文本格式化器 ────────────────────────────────────────────────────────────

class PlainFormatter:
    """无 ANSI 颜色的纯文本格式化器（--no-color / CI）。"""

    def __init__(self, *, show_path: bool = False) -> None:
        self._show_path = show_path

    def __call__(self, record: "Record") -> str:
        if self._show_path:
            return (
                "{time:YYYY-MM-DD HH:mm:ss.SSS}"
                f" | {{level:<{_LEVEL_WIDTH}}}"
                " | {name}:{function}:{line}"
                " - {message}\n{exception}"
            )
        return (
            "{time:YYYY-MM-DD HH:mm:ss.SSS}"
            f" | {{level:<{_LEVEL_WIDTH}}}"
            " | {message}\n{exception}"
        )


# ── JSON sink ─────────────────────────────────────────────────────────────────

def _try_orjson_dumps(obj: Any) -> str:
    """优先使用 orjson 序列化 obj；不可用时回退到 stdlib json。
    参数：obj — 任意可序列化对象。返回：序列化后的字符串。
    """
    try:
        import orjson
        return orjson.dumps(obj).decode()
    except ImportError:
        return json.dumps(obj, ensure_ascii=False, default=str)


class JsonSink:
    """loguru JSON sink：直接接收 loguru Message 对象并序列化为 JSON 行。

    与 ColorFormatter / PlainFormatter 不同，JsonSink **不是** format 字符串工厂，
    而是直接注册为 sink：

        logger.add(json_sink, level="INFO")

    这样可以避免 JSON 内容中的花括号被 loguru 的字符串插值误解析。

    输出字段
    --------
    timestamp, level, logger, function, line, message,
    run_id?, scenario_id?, step_id?, suite_id?, exception?
    """

    def __init__(self, stream=None) -> None:
        self._stream = stream or sys.stderr

    def __call__(self, message: "Message") -> None:
        record = message.record
        serialized = self._serialize(record)
        self._stream.write(serialized)
        if hasattr(self._stream, "flush"):
            self._stream.flush()

    def _serialize(self, record: "Record") -> str:
        ts = record["time"].astimezone(timezone.utc).isoformat()

        payload: dict[str, Any] = {
            "timestamp": ts,
            "level":    record["level"].name,
            "logger":   record.get("name") or record.get("module", ""),
            "function": record["function"],
            "line":     record["line"],
            "message":  record["message"],
        }

        extra = record.get("extra", {})
        for key in ("run_id", "scenario_id", "step_id", "suite_id"):
            if key in extra:
                payload[key] = extra[key]

        exc = record.get("exception")
        if exc is not None:
            exc_type, exc_val, _ = exc
            payload["exception"] = {
                "type":    exc_type.__name__ if exc_type else None,
                "message": str(exc_val) if exc_val else None,
            }

        return _try_orjson_dumps(payload) + "\n"


# 向后兼容别名
JsonFormatter = JsonSink


# ── 工厂函数 ──────────────────────────────────────────────────────────────────

def make_console_sink(
    *,
    stream,
    no_color: bool,
    json_mode: bool,
    show_path: bool,
    level: str,
    backtrace: bool,
    diagnose: bool,
) -> dict:
    """返回一组 loguru.add() 关键字参数，用于注册 console sink。

    Returns
    -------
    dict  可直接 **展开 到 logger.add()
    """
    if json_mode:
        return dict(
            sink=JsonSink(stream=stream),
            level=level,
            backtrace=backtrace,
            diagnose=diagnose,
            enqueue=False,
        )

    colorize = (
        not no_color
        and not json_mode
        and hasattr(stream, "isatty")
        and stream.isatty()
    )
    formatter = PlainFormatter(show_path=show_path) if no_color else ColorFormatter(show_path=show_path)
    return dict(
        sink=stream,
        format=formatter,
        level=level,
        colorize=colorize,
        backtrace=backtrace,
        diagnose=diagnose,
        enqueue=False,
    )


def make_file_sink(
    *,
    path,
    file_json: bool,
    show_path: bool,
    level: str,
    rotation: str,
    retention: str,
    compression,
    backtrace: bool,
    diagnose: bool,
) -> dict:
    """返回一组 loguru.add() 关键字参数，用于注册 file sink。"""
    if file_json:
        # 文件 JSON sink：需要包装让 JsonSink 写入文件而非 stderr
        # loguru 会把文件路径自动管理，我们用标准的 path 参数 + serialize
        # 由于 loguru 支持 sink 为可调用对象，传路径时用默认文本 + 格式化器
        formatter = PlainFormatter(show_path=True)  # fallback，实际由 serialize=True 覆盖
        return dict(
            sink=str(path),
            serialize=True,      # loguru 内置 JSON 序列化
            level=level,
            rotation=rotation,
            retention=retention,
            compression=compression or None,
            backtrace=backtrace,
            diagnose=diagnose,
            enqueue=True,
            encoding="utf-8",
        )

    return dict(
        sink=str(path),
        format=PlainFormatter(show_path=True),
        level=level,
        rotation=rotation,
        retention=retention,
        compression=compression or None,
        backtrace=backtrace,
        diagnose=diagnose,
        enqueue=True,
        encoding="utf-8",
    )