"""C 类快照读取（M2 方案 v2.4 §2.1——executor_ext.json 的结构化访问）。

快照由 ``scripts/gen_m2.py gen --targets ext`` 运行 ``gimbal ext list --json``
生成并入库；plate 读数据文件，不 import 执行器。六张表：
strategy / protocol / mode / plugin / generator / event。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_SNAPSHOT_PATH = Path(__file__).parent / "executor_ext.json"
_cache: list[dict[str, Any]] | None = None


def _entries() -> list[dict[str, Any]]:
    global _cache
    if _cache is None:
        _cache = json.loads(_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    return _cache


def table(name: str) -> list[dict[str, Any]]:
    """取某张表的全部条目（如 ``table(\"strategy\")``）。"""
    return [e for e in _entries() if e.get("table") == name]


def generator_kinds() -> list[dict[str, Any]]:
    """生成器表（9 个 kind 的 spec 模型 + params_schema）。"""
    return table("generator")


def event_types() -> list[dict[str, Any]]:
    """事件表（event_type + payload 字段清单）。"""
    return table("event")


def strategy_kinds() -> list[dict[str, Any]]:
    """策略表。"""
    return table("strategy")


def protocols() -> list[dict[str, Any]]:
    """协议表。"""
    return table("protocol")


def modes() -> list[dict[str, Any]]:
    """模式表。"""
    return table("mode")


__all__ = [
    "event_types", "generator_kinds", "modes", "protocols",
    "strategy_kinds", "table",
]
