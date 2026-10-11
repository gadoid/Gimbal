"""V3.1 平台视图扩展契约一致性测试(PLATE_V3_DESIGN.md §7.6)。

本文件专门用于核对设计文档 §7 与代码运行时行为的一致性,任何字段名/类型/
导出行为的偏离都会失败。每条 test 都对应 §7 中的一段设计决策。

测试覆盖:
- §7.2 字段归属表:每个平台视图扩展字段都在对应 schema 数据类上声明、类型匹配
- §7.4 反序列化契约:platform 落库 dict 不需要 strip 就能 model_validate
- §7.6.2 下划线前缀零引用:除文档/注释中说明历史外,代码层面零引用
- §7.6.3 strip 零引用:除文档/注释中说明历史外,代码层面零引用
- §7.6.4 gimbal dict 不携带平台视图扩展字段(model_dump exclude 生效)
- §7.6.5 platform dict 携带全部平台视图扩展字段
- 端到端字节级一致:platform → Scenario → gimbal == 原生 gimbal
"""
from __future__ import annotations

from gimbal_plate.dialect import EndpointSpec
from tests.plate.conftest import SYSTEMS_ROOT
from gimbal_plate.loader import load_registry

_REG = load_registry([SYSTEMS_ROOT])
ALL_ENDPOINTS = [e for e in _REG.list_endpoints() if isinstance(e, EndpointSpec)]
ALL_FIN = [e for e in ALL_ENDPOINTS if e.system == 'fin']

import inspect
import json
from copy import deepcopy
from pathlib import Path

from gimbal_plate.export.gimbal import GimbalScenarioExporter
from gimbal_plate.schema.call import Call
from gimbal_plate.schema.request import Request
from gimbal_plate.schema.scenario import Scenario as ScenarioModel
from gimbal_plate.schema.strategy import (
    Assign,
    Assertion,
    Extract,
    StrategyBase,
)


REPO = Path(__file__).resolve().parents[2]
SCENARIO_PATH = REPO / "tests" / "plate" / "fixtures" / "Scenario_Test_14_copy.json"


# ── 辅助函数 ──────────────────────────────────────────────────────


def _load_scenario() -> ScenarioModel:
    raw = json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))
    raw["meta"]["system"] = ["fin"]
    raw.setdefault("resource", {})
    raw["kind"] = "scenario"
    return ScenarioModel.model_validate(raw)




def _platform_view() -> dict:
    sc = _load_scenario()


_EP_BY_KEY = {(ep.binding.method, ep.binding.path): ep for ep in ALL_ENDPOINTS}


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


# §7.2 字段归属表 —— 测试代码必须与文档表格逐项对齐
EXPECTED_PLATFORM_FIELDS: dict[str, tuple[type, str]] = {
    # field_name -> (owning_class, documented_type)
    "fields_meta": (Request, "Dict[str, DeclarationEntry] | None"),
    "view_hints": (Call, "dict[str, Any] | None"),
    "view_note": (StrategyBase, "Optional[str]"),
    "endpoints": (ScenarioModel, "list[dict[str, Any]] | None"),
    "navigation": (ScenarioModel, "dict[str, Any] | None"),
    "config_summary": (ScenarioModel, "dict[str, Any] | None"),
}


# ── §7.2 字段归属表对齐 ──────────────────────────────────────────


class TestSchemaFieldsMatchDesignDoc:
    """PLATE_V3_DESIGN.md §7.2 字段表中的每个字段,都必须在 schema 数据类上声明。"""

    
class TestDeserializationContract:
    """§7.4:platform 落库 dict 可以直接 Scenario.model_validate(),仅需改 kind。"""

    
class TestLegacyFieldsAreRemoved:
    """§7.6.2 / §7.6.3:除文档/注释中说明历史外,代码层面零引用 _fields_meta / strip_platform_view_fields。"""

    
class TestRejectedApproachesAreAbsent:
    """§7.5 反面教材:验证被明确拒绝的设计不会出现在代码中。"""

    
