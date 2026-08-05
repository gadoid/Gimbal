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

from gimbal_plate.export.gimbal import GimbalScenarioExporter
from gimbal_plate.export.platform import PlatformScenarioExporter
from gimbal_plate.schema.scenario import Scenario as ScenarioModel
from gimbal_plate.systems.fin.endpoint import ALL_ENDPOINTS


REPO = Path(__file__).resolve().parents[2]
SCENARIO_PATH = REPO / "gimbal-tmp" / "Scenario_Test_14_copy.json"


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


class TestPlatformDictRoundTrip:
    """平台后端落库的 dict 必须能 reverse 回 Scenario → GimbalScenarioExporter。"""

    def test_platform_dict_reverses_to_scenario(self) -> None:
        sc = _load_scenario()
        platform_view = PlatformScenarioExporter(sc, endpoints=ALL_ENDPOINTS).to_dict()
        # V3.1:仅改 kind 后直接 model_validate,无需 strip
        parseable = deepcopy(platform_view)
        parseable["kind"] = "scenario"
        sc2 = ScenarioModel.model_validate(parseable)
        assert sc2.scenarioId == sc.scenarioId
        assert len(sc2.steps) == 36

    def test_platform_to_gimbal_dict_consistent(self) -> None:
        sc = _load_scenario()
        platform_view = PlatformScenarioExporter(sc, endpoints=ALL_ENDPOINTS).to_dict()
        parseable = deepcopy(platform_view)
        parseable["kind"] = "scenario"
        sc2 = ScenarioModel.model_validate(parseable)
        gimbal_dict = GimbalScenarioExporter(sc2).to_dict()
        # 与原始 gimbal 导出对齐
        gimbal_original = GimbalScenarioExporter(sc).to_dict()
        for gs, ge in zip(gimbal_dict["steps"], gimbal_original["steps"]):
            assert gs["api"]["method"] == ge["api"]["method"]
            assert gs["api"]["path"] == ge["api"]["path"]
            # 新设计:body 已是 endpoint 全量字段定义,所以 gs.body ⊇ ge.body
            # 每个 ge.body 的 key 必须在 gs.body 里且值一致
            for k, v in ge["request"]["body"].items():
                assert k in gs["request"]["body"], f"missing key {k!r}"
                assert gs["request"]["body"][k] == v, f"value mismatch at {k!r}"
            assert len(gs["strategy"]) == len(ge["strategy"])

    def test_fields_meta_does_not_leak_into_gimbal(self) -> None:
        """fields_meta 是平台视图扩展,Scenario.model_validate 直接接受,但
        GimbalScenarioExporter.to_dict() 通过 model_dump(exclude=...) 过滤掉。"""
        sc = _load_scenario()
        platform_view = PlatformScenarioExporter(sc, endpoints=ALL_ENDPOINTS).to_dict()
        # platform 落库 dict:step[0].request 应当有 fields_meta
        assert "fields_meta" in platform_view["steps"][0]["request"]
        # V3.1:仅改 kind,直接 model_validate(fields_meta 是 Request 上的合法 schema 字段)
        payload = deepcopy(platform_view)
        payload["kind"] = "scenario"
        sc2 = ScenarioModel.model_validate(payload)
        # Scenario 实例上 fields_meta 是真实字段(不应被静默丢弃)
        assert sc2.steps[0].request.fields_meta is not None
        # 走完整链路后,gimbal dict 的 step[0].request 不该有 fields_meta
        gimbal_dict = GimbalScenarioExporter(sc2).to_dict()
        assert "fields_meta" not in gimbal_dict["steps"][0]["request"]
        # 同时验证 request 的 keys 只有 kind / body(干净)
        assert set(gimbal_dict["steps"][0]["request"].keys()) == {"kind", "body"}


class TestPlatformEditPropagatesToGimbal:
    """平台用户编辑落库 dict 后,Plate 反向导出为 gimbal dict 时,改动必须真实反映。"""

    def test_edit_authorization_header_propagates(self) -> None:
        pv = _platform_view()
        step0 = pv["steps"][0]
        step0["api"]["headers"]["Authorization"] = (
            "${auth.codfish.token}.EDITED_BY_PLATFORM"
        )
        sc, gd = _roundtrip(pv)
        assert gd["steps"][0]["api"]["headers"]["Authorization"] == (
            "${auth.codfish.token}.EDITED_BY_PLATFORM"
        )
        # Scenario 内部也同步
        assert sc.steps[0].api.headers["Authorization"] == (
            "${auth.codfish.token}.EDITED_BY_PLATFORM"
        )

    def test_edit_request_body_propagates(self) -> None:
        pv = _platform_view()
        step0 = pv["steps"][0]
        # 取一个真实存在的 body 字段(bl_no 是 e2e 应收场景 step0 的真实字段)
        assert "bl_no" in step0["request"]["body"]
        step0["request"]["body"]["bl_no"] = "GIMBAL-PLATFORM-EDITED"
        sc, gd = _roundtrip(pv)
        assert gd["steps"][0]["request"]["body"]["bl_no"] == "GIMBAL-PLATFORM-EDITED"
        assert sc.steps[0].request.body["bl_no"] == "GIMBAL-PLATFORM-EDITED"

    def test_edit_remove_strategy_propagates(self) -> None:
        pv = _platform_view()
        # step[1] 有 2 条 strategy (assertion, extract),适合测试删除
        target_step = pv["steps"][1]
        original_count = len(target_step["strategy"])
        assert original_count >= 2
        removed = target_step["strategy"].pop(0)
        sc, gd = _roundtrip(pv)
        assert len(gd["steps"][1]["strategy"]) == original_count - 1
        assert len(sc.steps[1].strategy) == original_count - 1
        # 被删的 strategy 确实不再出现(按 kind+target 组合)
        removed_key = (removed["kind"], removed.get("target", removed.get("source", "")))
        remaining_keys = [
            (s["kind"], s.get("target", s.get("source", "")))
            for s in gd["steps"][1]["strategy"]
        ]
        assert removed_key not in remaining_keys

    def test_edit_add_assign_strategy_propagates(self) -> None:
        pv = _platform_view()
        target_step = pv["steps"][1]
        original_count = len(target_step["strategy"])
        # Assign schema 要求 source + target (而非 targets/bind)
        target_step["strategy"].append({
            "kind": "assign",
            "source": "PLATFORM_ADDED_VALUE",
            "target": "$.vars.platform_added",
            "scope": "scenario",
        })
        sc, gd = _roundtrip(pv)
        assert len(gd["steps"][1]["strategy"]) == original_count + 1
        assert len(sc.steps[1].strategy) == original_count + 1
        added = gd["steps"][1]["strategy"][-1]
        assert added["kind"] == "assign"
        assert added["target"] == "$.vars.platform_added"
        assert added["source"] == "PLATFORM_ADDED_VALUE"

    def test_edit_multiple_steps_propagates(self) -> None:
        pv = _platform_view()
        # 同时改 step0 header + step1 body
        pv["steps"][0]["api"]["headers"]["X-Test-1"] = "P1"
        pv["steps"][1]["request"]["body"]["bl_no"] = "P2-BODY"
        _sc, gd = _roundtrip(pv)
        assert gd["steps"][0]["api"]["headers"]["X-Test-1"] == "P1"
        assert gd["steps"][1]["request"]["body"]["bl_no"] == "P2-BODY"

    @pytest.mark.parametrize(
        "mutator, expected",
        [
            ("header", "${auth.codfish.token}.PARAM"),
            ("body", "PARAM-BODY"),
            ("strategy_add", "PARAM-ASSIGN"),
        ],
    )
    def test_edit_via_parametrized_mutator(self, mutator: str, expected: str) -> None:
        pv = _platform_view()
        if mutator == "header":
            pv["steps"][0]["api"]["headers"]["Authorization"] = expected
        elif mutator == "body":
            pv["steps"][0]["request"]["body"]["bl_no"] = expected
        elif mutator == "strategy_add":
            # 用 step[1] (它有 strategy 可以 append),Assign schema: source+target
            pv["steps"][1]["strategy"].append({
                "kind": "assign",
                "source": expected,
                "target": "$.vars.param_assign",
                "scope": "scenario",
            })
        sc, gd = _roundtrip(pv)
        if mutator == "header":
            assert gd["steps"][0]["api"]["headers"]["Authorization"] == expected
        elif mutator == "body":
            assert gd["steps"][0]["request"]["body"]["bl_no"] == expected
        elif mutator == "strategy_add":
            assert gd["steps"][1]["strategy"][-1]["kind"] == "assign"
            assert gd["steps"][1]["strategy"][-1]["source"] == expected
            assert gd["steps"][1]["strategy"][-1]["target"] == "$.vars.param_assign"
