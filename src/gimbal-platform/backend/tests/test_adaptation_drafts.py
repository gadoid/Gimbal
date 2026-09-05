"""diff_field_specs 草案生成测试(纯函数,无 DB;spec §5.4 收窄裁定)。"""
from __future__ import annotations

from app.services.adaptation_ops import ALL_OPS, diff_field_specs


def _spec(fields: list[dict]) -> dict:
    """新 wire(M1 目录态):request.declarations 条目(全量,无通道轴)。"""
    return {"id": "fin.order.add", "version": "1.1.0",
            "request": {"declarations": [
                {"state": "form", **f} for f in fields]}}


def _legacy_spec(fields: list[dict]) -> dict:
    """已废弃的旧 wire 形状(wire 归一化前的 fields 键,仅用于负向断言)。"""
    return {"id": "fin.order.add", "version": "1.0.0",
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


def test_legacy_fields_key_not_read():
    # 旧 wire 的 fields 键不做兼容读(2026-09-02 剥离,清库重基线):
    # 旧形状解析为空 → diff 只产 addField、无 removeField ——
    # 存量库须重跑 catalog 基线,此行为为剥离决策的锁定
    old = _legacy_spec([{"name": "a"}, {"name": "c"}])
    new = _spec([{"name": "a"}, {"name": "d"}])
    assert diff_field_specs(old, new) == [
        {"op": "addField", "field": "a", "value": ""},
        {"op": "addField", "field": "d", "value": ""},
    ]


# ── 2026-09-05 目录化:diff 全量泛化(§4.1(a),去通道过滤)──────────


def test_diff_sees_carry_entries_too():
    """全量目录:carry 条目同样参与 diff(旧 binding 通道过滤已退役)—
    新增 carry 字段产 addField,消失产 removeField。"""
    old = _spec([{"name": "amount"}, {"name": "remark"}])
    new = _spec([{"name": "amount"}, {"name": "trace"}])
    assert diff_field_specs(old, new) == [
        {"op": "addField", "field": "trace", "value": ""},
        {"op": "removeField", "field": "remark"},
    ]


def test_diff_flattens_children_tree():
    """children 树先序展开(iter_flat):容器与叶子都在字段宇宙里 —
    叶子消失/新增同样产 removeField/addField(容器行壳跟 children,
    §4 值×结构分离)。"""
    old = _spec([
        {"name": "supplier", "path": "$.supplier", "state": "carry",
         "type": "array", "children": [
             {"name": "supplier_id",
              "path": "$.supplier.order_supplier_id"}]},
    ])
    new = _spec([
        {"name": "supplier", "path": "$.supplier", "state": "carry",
         "type": "array", "children": [
             {"name": "supplier_id",
              "path": "$.supplier.order_supplier_id"},
             {"name": "order_id", "path": "$.supplier.order_id"}]},
    ])
    assert diff_field_specs(old, new) == [
        {"op": "addField", "field": "order_id", "value": ""},
    ]
