"""RS4b：步骤结构级 op 与场景内引用改写（Release v4.4 §5.4 / R30）。

覆盖：
- 5 种结构级 op（replaceEndpoint/splitStep/mergeSteps/insertStep/removeStep）
- 场景内引用改写（assertion_registry stepIndex / ui.fieldStates 位置）
- renamePathParam 字段级 op
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "gimbal-platform" / "backend"))

from app.services.adaptation_ops import (
    STRUCTURE_OPS,
    apply_to_definition,
)


def _definition(steps: list, **extra) -> dict:
    d = {
        "kind": "scenario", "scenarioId": "sc-test",
        "meta": {"name": "test", "plate": {"fin": "1.0#1"}},
        "config": {},
        "resource": {},
        "steps": steps,
    }
    d.update(extra)
    return d


def _step(endpoint: str = "fin.a.b", **extra) -> dict:
    s = {"kind": "step", "endpoint": endpoint,
         "call": {"protocol": "http", "method": "GET", "path": "/b"},
         "strategy": []}
    s.update(extra)
    return s


def _payload(assertion_registry: dict | None = None,
             field_states: dict | None = None) -> dict:
    p = {"definition": _definition([])}
    if assertion_registry:
        p["assertion_registry"] = assertion_registry
    if field_states:
        p["ui"] = {"fieldStates": field_states}
    return p


class TestReplaceEndpoint:
    def test_basic(self) -> None:
        d = _definition([_step("fin.a.old")])
        op = {"op": "replaceEndpoint", "step": 0,
              "endpoint": "fin.a.new",
              "newStep": {"call": {"protocol": "http", "method": "POST",
                                    "path": "/new"}}}
        apply_to_definition(d, op)
        assert d["steps"][0]["endpoint"] == "fin.a.new"
        assert d["steps"][0]["call"]["method"] == "POST"

    def test_cross_system(self) -> None:
        d = _definition([_step("fin.a.old")])
        op = {"op": "replaceEndpoint", "step": 0,
              "endpoint": "platform.b.new",
              "newStep": {},
              "targetRevision": "1.0#1"}
        apply_to_definition(d, op)
        assert d["steps"][0]["endpoint"] == "platform.b.new"
        assert d["meta"]["plate"]["platform"] == "1.0#1"


class TestSplitStep:
    def test_one_to_two(self) -> None:
        d = _definition([_step("fin.a.a"), _step("fin.a.c")])
        op = {"op": "splitStep", "step": 0,
              "newSteps": [_step("fin.a.a1"), _step("fin.a.a2")]}
        apply_to_definition(d, op)
        assert len(d["steps"]) == 3
        assert d["steps"][0]["endpoint"] == "fin.a.a1"
        assert d["steps"][1]["endpoint"] == "fin.a.a2"
        assert d["steps"][2]["endpoint"] == "fin.a.c"  # 原来的 1 → 2


class TestMergeSteps:
    def test_two_to_one(self) -> None:
        d = _definition([_step("fin.a.a"), _step("fin.a.b"), _step("fin.a.c")])
        op = {"op": "mergeSteps", "steps": [0, 1],
              "mergedStep": _step("fin.a.merged")}
        apply_to_definition(d, op)
        assert len(d["steps"]) == 2
        assert d["steps"][0]["endpoint"] == "fin.a.merged"
        assert d["steps"][1]["endpoint"] == "fin.a.c"


class TestInsertStep:
    def test_insert_at_position(self) -> None:
        d = _definition([_step("fin.a.a"), _step("fin.a.c")])
        op = {"op": "insertStep", "at": 1,
              "newStep": _step("fin.a.b")}
        apply_to_definition(d, op)
        assert len(d["steps"]) == 3
        assert d["steps"][1]["endpoint"] == "fin.a.b"
        assert d["steps"][2]["endpoint"] == "fin.a.c"


class TestRemoveStep:
    def test_remove(self) -> None:
        d = _definition([_step("fin.a.a"), _step("fin.a.b"), _step("fin.a.c")])
        op = {"op": "removeStep", "step": 1}
        apply_to_definition(d, op)
        assert len(d["steps"]) == 2
        assert d["steps"][0]["endpoint"] == "fin.a.a"
        assert d["steps"][1]["endpoint"] == "fin.a.c"


class TestPositionRefRewrite:
    def test_assertion_registry_step_index_rewritten(self) -> None:
        payload = _payload(
            assertion_registry={"grp1": [
                {"id": "e0", "path": {"stepIndex": 0, "source": "body",
                                      "jsonpath": "$.a"}},
                {"id": "e2", "path": {"stepIndex": 2, "source": "body",
                                      "jsonpath": "$.c"}},
            ]})
        d = payload["definition"]
        d["steps"] = [_step(), _step(), _step()]
        # insertStep at 1 → indices shift
        op = {"op": "insertStep", "at": 1, "newStep": _step(),
              "_payload": payload}
        apply_to_definition(d, op)
        entries = payload["assertion_registry"]["grp1"]
        assert entries[0]["path"]["stepIndex"] == 0   # 在插入点前,不变
        assert entries[1]["path"]["stepIndex"] == 3   # 2 → 3(后移一位)

    def test_removed_step_dangling(self) -> None:
        payload = _payload(
            assertion_registry={"grp": [
                {"id": "e1", "path": {"stepIndex": 1, "source": "body",
                                      "jsonpath": "$.b"}}]})
        d = payload["definition"]
        d["steps"] = [_step(), _step(), _step()]
        op = {"op": "removeStep", "step": 1, "_payload": payload}
        apply_to_definition(d, op)
        entry = payload["assertion_registry"]["grp"][0]
        assert entry.get("_dangling") is True

    def test_field_states_position_rewritten(self) -> None:
        payload = _payload(field_states={"0": {"a": "carry"},
                                          "2": {"c": "carry"}})
        d = payload["definition"]
        d["steps"] = [_step(), _step(), _step()]
        op = {"op": "insertStep", "at": 1, "newStep": _step(),
              "_payload": payload}
        apply_to_definition(d, op)
        fs = payload["ui"]["fieldStates"]
        assert "0" in fs          # 前面不变
        assert "3" in fs          # 2 → 3
        assert "2" not in fs      # 旧位置不存在


class TestRenamePathParam:
    def test_basic(self) -> None:
        d = _definition([{
            "kind": "step", "endpoint": "fin.a.ep",
            "call": {"protocol": "http", "method": "GET", "path": "/a/{uid}",
                     "path_params": {"uid": "u1"}},
            "strategy": [],
        }])
        op = {"op": "renamePathParam", "step": 0, "from": "uid",
              "to": "user_id"}
        apply_to_definition(d, op)
        pp = d["steps"][0]["call"]["path_params"]
        assert "user_id" in pp and "uid" not in pp
