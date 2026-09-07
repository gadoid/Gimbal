"""Step.field_states 收编(2026-09-07 spec §3.2)—— 模型层契约。

缺口背景(#6 导出穿线的根因):平台落库 definition 的 steps[].field_states
进 plate /convert 时被 Scenario.model_validate 以 extra=ignore 静默剥除,
导出器只能读 entry.state 共识默认 —— 场景侧增量在导出面失踪。

本文件钉三层:
① roundtrip:带增量的 step JSON → Scenario.model_validate 保留、dump 携带;
② 零漂:无增量 step 的 dump(exclude_none)与收编前逐键相等
   (存量 wire 逐键零漂 —— 导出链全部 dump 点均 exclude_none,已审计);
③ 容忍:词表外值原样进入(词表校验归解析链);形状不符不在此层拒 ——
   归一为合法 dict[str, str] 子集(非 dict / 空集 → None 读穿共识默认)。
"""
from __future__ import annotations

from gimbal_plate.schema.scenario import Scenario
from gimbal_plate.schema.step import Step


def _step_dict(**extra: object) -> dict:
    base: dict = {
        "kind": "step",
        "api": {"kind": "api", "service": "tst-service", "method": "POST", "path": "/p"},
        "request": {"kind": "request", "body": {}},
    }
    base.update(extra)
    return base


def _scenario_dict(step: dict) -> dict:
    return {
        "kind": "scenario",
        "scenarioId": "sc-fs-001",
        "meta": {
            "name": "field-states", "description": "Step.field_states 收编",
            "module": "plate", "priority": 1, "author": "t", "owner": "t",
            "tags": [], "version": "1",
            "createTime": "2026-09-07T00:00:00Z", "expire": False,
            "requirementRef": [],
        },
        "config": {},
        "resource": {},
        "steps": [step],
    }


# ── ① roundtrip:增量不再被剥 ────────────────────────────────────────


def test_step_roundtrip_preserves_field_states():
    step = Step.model_validate(_step_dict(field_states={"$.order_id": "carry"}))
    assert step.field_states == {"$.order_id": "carry"}


def test_scenario_validate_keeps_field_states():
    """#6 根因守卫:整场景 validate(平台 /convert 真实入口)后增量仍在。"""
    sc = Scenario.model_validate(_scenario_dict(
        _step_dict(field_states={"$.order_id": "carry", "$.remark": "collapse"})))
    assert sc.steps[0].field_states == {"$.order_id": "carry", "$.remark": "collapse"}
    # 出向同样携带(None-omitted 纪律下非 None 必须可见)
    dump = sc.model_dump(mode="json", exclude_none=True)
    assert dump["steps"][0]["field_states"] == {
        "$.order_id": "carry", "$.remark": "collapse"}


# ── ② 零漂:无增量 step 输出与收编前逐键相等 ────────────────────────


def test_no_increment_dump_key_identical():
    """收编前字段宇宙 = kind/api/request/strategy(description None 不携带)。
    全量字面比对 —— 任何意外加键(含 field_states: None)都会在此爆。"""
    dump = Step.model_validate(_step_dict()).model_dump(mode="json", exclude_none=True)
    assert dump == {
        "kind": "step",
        "api": {
            "kind": "api", "service": "tst-service", "method": "POST",
            "path": "/p", "headers": {}, "timeout": 30,
        },
        "request": {"kind": "request", "body": {}},
        "strategy": [],
    }


def test_scenario_dump_no_field_states_key_when_absent():
    sc = Scenario.model_validate(_scenario_dict(_step_dict()))
    dump = sc.model_dump(mode="json", exclude_none=True)
    assert "field_states" not in dump["steps"][0]


# ── ③ 容忍:不在此层拒(解析链防御口径)────────────────────────────


def test_vocabulary_foreign_value_enters_as_is():
    """词表外状态值原样进入 —— 词表校验归 platform validate_field_states /
    plate resolve_state(三处镜像解析链),模型层不裁决。"""
    step = Step.model_validate(_step_dict(field_states={"$.x": "bogus"}))
    assert step.field_states == {"$.x": "bogus"}


def test_non_dict_shape_normalized_to_none():
    """形状不符(非 dict)不拒:归 None = 读穿共识默认(fail-open,
    与收编前 extra=ignore 剥除的行为等价 —— 手改坏草稿不炸 /convert)。"""
    step = Step.model_validate(_step_dict(field_states=["oops"]))
    assert step.field_states is None


def test_non_str_values_dropped_str_kept():
    step = Step.model_validate(
        _step_dict(field_states={"$.x": 123, "$.y": "carry"}))
    assert step.field_states == {"$.y": "carry"}


def test_empty_dict_normalized_to_none():
    """空集 → None(§3.1 空 step 零存储;防 "{}" 漏进 wire)。"""
    step = Step.model_validate(_step_dict(field_states={}))
    assert step.field_states is None
