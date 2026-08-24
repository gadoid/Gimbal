"""adaptation_ops 收敛应用引擎测试(纯函数,无 DB)。

核心断言面:每类 op 的语义正确 + **幂等**(二次应用同 op 无变化,spec §5.3)。
"""
from __future__ import annotations

import copy

from app.services.adaptation_ops import (
    apply_to_definition,
    apply_to_rows,
    check_step_addressable,
)

EP = "fin.order.add"


def _definition() -> dict:
    return {
        "kind": "scenario", "scenarioId": "sc-x",
        "meta": {"scenarioId": "sc-x", "name": "X", "module": "order",
                 "priority": 1, "system": ["fin"]},
        "config": {"timePolicy": {"kind": "record"},
                   "vars": {"amount": 100}},
        "resource": {},
        "steps": [
            {"api": {"view_hints": {"endpoint_id": EP},
                     "headers": {"Token": "t"}},
             "request": {"body": {"amount": "${var.amount}", "fixed": "X",
                                  "settle_type": "1", "cust_id": "7"}}},
        ],
    }


def _rows() -> list[dict]:
    return [{"amount": 5, "settle_type": "1"}, {"amount": 6}]


def test_check_step_addressable():
    d = _definition()
    op = {"op": "addField", "step": 0, "field": "x", "value": ""}
    assert check_step_addressable(d, op, EP) is None
    assert check_step_addressable(d, {"op": "addField", "step": 5}, EP) \
        == "step_missing: 5"
    assert check_step_addressable(d, op, "fin.order.book").startswith(
        "endpoint_mismatch:"
    )


def test_rename_field_and_idempotent():
    d = _definition()
    op = {"op": "renameField", "step": 0, "from": "cust_id", "to": "customerId"}
    apply_to_definition(d, op)
    body = d["steps"][0]["request"]["body"]
    assert "cust_id" not in body and body["customerId"] == "7"
    before = copy.deepcopy(d)
    apply_to_definition(d, op)  # from 已不在 → 无操作(收敛)
    assert d == before


def test_add_field_defaults_body_and_idempotent():
    d = _definition()
    op = {"op": "addField", "step": 0, "field": "extra", "value": "E"}
    apply_to_definition(d, op)
    assert d["steps"][0]["request"]["body"]["extra"] == "E"
    before = copy.deepcopy(d)
    apply_to_definition(d, op)  # 已存在 → 不覆盖既有值(收敛)
    assert d == before


def test_remove_field_all_sources():
    d = _definition()
    d["steps"][0]["api"]["headers"]["Token2"] = "t2"
    op = {"op": "removeField", "step": 0, "field": "Token2"}
    apply_to_definition(d, op)
    assert "Token2" not in d["steps"][0]["api"]["headers"]
    apply_to_definition(d, op)  # 再删无害
    assert "Token2" not in d["steps"][0]["api"]["headers"]


def test_rebind_registers_var_default():
    d = _definition()
    op = {"op": "rebindField", "step": 0, "field": "cust_id", "var": "cust"}
    apply_to_definition(d, op)
    body = d["steps"][0]["request"]["body"]
    assert body["cust_id"] == "${var.cust}"
    assert d["config"]["vars"]["cust"] == "7"  # 原值落 vars(D8)
    before = copy.deepcopy(d)
    apply_to_definition(d, op)  # 已是模板且 vars 已声明 → 无操作
    assert d == before


def test_map_value_only_mapped_keys():
    d = _definition()
    op = {"op": "mapValue", "step": 0, "field": "settle_type",
          "map": {"1": "2"}}
    apply_to_definition(d, op)
    assert d["steps"][0]["request"]["body"]["settle_type"] == "2"
    apply_to_definition(d, op)  # "2" 不在 map 键 → 无操作(收敛)
    assert d["steps"][0]["request"]["body"]["settle_type"] == "2"


def test_rename_var_deep_replace():
    d = _definition()
    d["steps"][0]["api"]["headers"]["Note"] = "amt=${var.amount}!"
    op = {"op": "renameVar", "from": "amount", "to": "amt"}
    apply_to_definition(d, op)
    assert d["steps"][0]["request"]["body"]["amount"] == "${var.amt}"
    assert "amt" not in d["steps"][0]["request"]["body"]
    assert d["steps"][0]["api"]["headers"]["Note"] == "amt=${var.amt}!"
    assert "amount" not in d["config"]["vars"]
    assert d["config"]["vars"]["amt"] == 100
    before = copy.deepcopy(d)
    apply_to_definition(d, op)  # 引用已全部替换 + vars 已改名 → 无操作
    assert d == before


def test_apply_to_definition_rejects_dataset_op():
    d = _definition()
    try:
        apply_to_definition(d, {"op": "renameDatasetColumn",
                                "from": "a", "to": "b"})
    except ValueError as e:
        assert "not_a_scenario_op" in str(e)
    else:
        raise AssertionError("expected ValueError")


def test_rows_rename_and_map():
    rows = _rows()
    apply_to_rows(rows, {"op": "renameVar", "from": "amount", "to": "amt"})
    assert rows == [{"amt": 5, "settle_type": "1"}, {"amt": 6}]
    apply_to_rows(rows, {"op": "mapDatasetValues", "column": "settle_type",
                         "map": {"1": "2"}})
    assert rows[0]["settle_type"] == "2"
    before = copy.deepcopy(rows)
    apply_to_rows(rows, {"op": "renameVar", "from": "amount", "to": "amt"})
    apply_to_rows(rows, {"op": "mapDatasetValues", "column": "settle_type",
                         "map": {"1": "2"}})
    assert rows == before  # 两侧均收敛


def test_apply_to_rows_rejects_step_op():
    try:
        apply_to_rows([], {"op": "addField", "field": "x"})
    except ValueError as e:
        assert "not_a_dataset_op" in str(e)
    else:
        raise AssertionError("expected ValueError")
