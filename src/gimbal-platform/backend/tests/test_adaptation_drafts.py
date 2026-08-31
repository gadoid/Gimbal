"""diff_field_specs 草案生成测试(纯函数,无 DB;spec §5.4 收窄裁定)。"""
from __future__ import annotations

from app.services.adaptation_ops import ALL_OPS, diff_field_specs


def _spec(fields: list[dict]) -> dict:
    return {"id": "fin.order.add", "version": "1.1.0",
            "request": {"fields": fields}}


def test_op_constants():
    assert ALL_OPS == (
        "renameField", "addField", "removeField", "rebindField", "mapValue",
        "renameDatasetColumn", "mapDatasetValues", "renameVar",
        # carry 值表类(spec §7,Task 12):service 缺省 = 全局默认表
        "renameCarryPath", "addCarryBinding", "removeCarryBinding",
    )


def test_old_none_all_add():
    # 无旧形状缓存(spec_json 空 conservatism)→ 全部按新增处理
    assert diff_field_specs(None, _spec([
        {"name": "a"},
        {"name": "b", "default": 0},
    ])) == [
        {"op": "addField", "field": "a", "value": ""},
        {"op": "addField", "field": "b", "value": 0},
    ]


def test_remove_and_add_pair():
    old = _spec([{"name": "a"}, {"name": "c"}])
    new = _spec([{"name": "a"}, {"name": "d"}])
    # c→d 疑似改名,但形状 diff 只能给 remove+add 对(§5.4 裁定:
    # renameField 不可推断,保留值绑定由人工在 UI 合并为 rename)
    assert diff_field_specs(old, new) == [
        {"op": "addField", "field": "d", "value": ""},
        {"op": "removeField", "field": "c"},
    ]


def test_enum_change_map_skeleton():
    old = _spec([{"name": "settle_type", "enum": ["1", "2"]}])
    new = _spec([{"name": "settle_type", "enum": ["2", "3"]}])
    assert diff_field_specs(old, new) == [
        {"op": "mapValue", "field": "settle_type", "map": {}},
    ]


def test_no_change_no_drafts():
    spec = _spec([{"name": "a", "enum": ["1"]}])
    assert diff_field_specs(spec, spec) == []


def test_enum_one_side_only_no_map():
    # 单侧可枚举(或值域为空)不足以建映射骨架
    old = _spec([{"name": "a", "enum": ["1"]}])
    new = _spec([{"name": "a"}])
    assert diff_field_specs(old, new) == []


def test_request_missing_treated_as_empty():
    assert diff_field_specs({"id": "e", "version": "1.0.0"}, None) == []
