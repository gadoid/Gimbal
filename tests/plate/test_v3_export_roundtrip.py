"""V3.1 阶段 4:platform 落库 dict → Scenario → gimbal 可执行 dict 的 round-trip 测试。

V3.1 重大变更(PLATE_V3_DESIGN.md §7):
- 删除 strip_platform_view_fields():所有平台视图字段都已在 schema 层声明,
  Scenario.model_validate 直接接受,仅需修改 kind
- 字段名统一:fields_meta / view_hints / view_note / endpoints / navigation /
  config_summary 都是合法 schema 字段
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from gimbal_plate.dialect import EndpointSpec
from tests.plate.conftest import SYSTEMS_ROOT
from gimbal_plate.loader import load_registry

_REG = load_registry([SYSTEMS_ROOT])
ALL_ENDPOINTS = [e for e in _REG.list_endpoints() if isinstance(e, EndpointSpec)]
ALL_FIN = [e for e in ALL_ENDPOINTS if e.system == 'fin']

from gimbal_plate.export.gimbal import GimbalScenarioExporter
from gimbal_plate.schema.endpoint import EndpointSpec
from gimbal_plate.schema.scenario import Scenario as ScenarioModel


REPO = Path(__file__).resolve().parents[2]
SCENARIO_PATH = REPO / "tests" / "plate" / "fixtures" / "Scenario_Test_14_copy.json"


def _load_scenario() -> ScenarioModel:
    raw = json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))
    raw["meta"]["system"] = ["fin"]
    raw.setdefault("resource", {})
    raw["kind"] = "scenario"
    return ScenarioModel.model_validate(raw)


def _platform_view() -> dict:
    sc = _load_scenario()
    return PlatformScenarioExporter(sc, endpoints=ALL_ENDPOINTS).to_dict()


def _roundtrip(platform_dict: dict) -> tuple[ScenarioModel, dict]:
    """落库 dict → Scenario → gimbal 可执行 dict(V3.1 仅需改 kind,无需 strip)。"""
    payload = deepcopy(platform_dict)
    if payload.get("kind") == "platform_scenario":
        payload["kind"] = "scenario"
    sc = ScenarioModel.model_validate(payload)
    gimbal_dict = GimbalScenarioExporter(sc).to_dict()
    return sc, gimbal_dict


# 与 PlatformScenarioExporter 相同的 step↔endpoint 匹配键
_EP_BY_KEY = {ep.binding.locator(): ep for ep in ALL_ENDPOINTS}


def _declared_body_keys(ep) -> set[str] | None:
    """平台补全面会物化的顶层 body 键集;None = 不物化(全量透传)。

    2026-09-05 目录化(state 轴):form/collapse 面叶子按声明 path 补全,
    carry 面(含整容器)对 body 已有字面量透传 — 两者都取 path 首段。
    未声明键按设计丢弃(目录即宇宙,残缺键归前端「其他字段」区,
    不进 body 补全面)。
    """
    if ep is None or ep.request is None:
        return None
    keys: set[str] = set()
    for e in ep.request.declarations:
        seg = e.path[2:] if e.path.startswith("$.") else e.path
        first = seg.split(".", 1)[0].split("[", 1)[0]
        if first:
            keys.add(first)
    return keys



