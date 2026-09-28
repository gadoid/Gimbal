"""suite/selector.py — 检索器 v1（D-15：目录枚举 + --where 直接字段）。

D-14 双模式：source 为单文件（现状主路径）或目录（枚举 *.json 场景）；
--where K=V 按 scenario 直接字段精确匹配（点路径最多两级，如
scenarioId / meta.name / meta.module / kind），多条件 AND。
模糊/嵌套/标签检索与"池条目用检索条件"留以后再议（D-15 边界）。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from pydantic import TypeAdapter

from gimbal.log import get_logger
from gimbal.schema.scenario import Scenario

logger = get_logger(__name__)


def iter_scenario_files(source: str | Path) -> list[Path]:
    """source 为文件 → [该文件]；为目录 → 目录下 *.json（不含子目录）。"""
    p = Path(source)
    if p.is_dir():
        files = sorted(p.glob("*.json"))
        if not files:
            raise FileNotFoundError(f"目录下没有 *.json 场景文件: {p}")
        return files
    if not p.is_file():
        raise FileNotFoundError(f"路径不存在: {p}")
    return [p]


def parse_where(items: Iterable[str]) -> dict[str, str]:
    """--where K=V（可多次）→ dict；非法形态（无 =）抛 ValueError。"""
    where: dict[str, str] = {}
    for item in items or []:
        k, sep, v = item.partition("=")
        if not sep or not k:
            raise ValueError(f"--where 非法形态（应为 K=V）: {item!r}")
        where[k] = v
    return where


def _field_value(scenario: Scenario, dotted: str) -> Any:
    """直接字段取值：最多两级点路径（scenarioId / meta.name）。"""
    obj: Any = scenario
    for part in dotted.split("."):
        obj = getattr(obj, part, None)
        if obj is None:
            return None
    return obj


def matches(scenario: Scenario, where: dict[str, str]) -> bool:
    """全部条件 AND 精确匹配（字符串化比较；None 视为不匹配）。"""
    for key, expected in where.items():
        actual = _field_value(scenario, key)
        if actual is None or str(actual) != expected:
            return False
    return True


def select(source: str | Path, where: dict[str, str] | None = None) -> list[Scenario]:
    """检索入口：枚举 → 解析 scenario → --where 过滤；零命中且给了条件时报错。"""
    adapter = TypeAdapter(Scenario)
    out: list[Scenario] = []
    for f in iter_scenario_files(source):
        try:
            payload = f.read_text(encoding="utf-8")
            import json
            sc = adapter.validate_json(payload) if False else Scenario.model_validate_json(payload)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[selector] 跳过无法解析的文件: {} ({})", f.name, exc)
            continue
        if not where or matches(sc, where):
            out.append(sc)
    if not out:
        raise ValueError(
            f"检索零命中: source={source} where={where or '(none)'}"
        )
    logger.info("[selector] 命中 {} 个场景: source={}", len(out), source)
    return out
