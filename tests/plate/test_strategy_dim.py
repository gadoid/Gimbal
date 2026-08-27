"""strategy dim 内省单测 —— kind 清单 / 字段派生 / strategy_ref 排除 / base 拆分。

对应设计: docs/superpowers/specs/2026-08-17-strategy-syntax-service-design.md §3
strategy dim 是"语法级 dim"(items 是 kind 描述符而非数据实例),
strategy_ref 为预埋字段整条排除(用户 2026-08-17 拍板)。
"""
from __future__ import annotations

from gimbal_plate.http.strategy_dim import StrategyIndex


def _idx() -> StrategyIndex:
    return StrategyIndex(registry=None)


def test_kinds_exclude_strategy_ref() -> None:
    kinds = [it.kind for it in _idx().list_global()]
    assert sorted(kinds) == ["assertion", "assign", "extract"]
    assert _idx().get("strategy_ref") is None  # 预埋字段,整条排除


def test_each_kind_has_label_and_phase() -> None:
    for it in _idx().list_global():
        assert it.label, f"{it.kind} 缺 label"
        assert it.phase in (
            "before_request", "after_request", "verifying", "teardown",
        ), f"{it.kind} phase 非法: {it.phase!r}"


def test_extract_fields_derived() -> None:
    item = _idx().get("extract")
    assert item is not None
    names = [f["name"] for f in item.fields]
    assert "expression" in names and "target" in names
    assert "kind" not in names  # 判别字段剔除
    scope = next(f for f in item.fields if f["name"] == "scope")
    assert scope["ui_kind"] == "select"
    assert "scenario" in scope["enum"]
    assert scope["default"] == "step"


def test_base_fields_split() -> None:
    item = _idx().get("assertion")
    assert item is not None
    base_names = [f["name"] for f in item.base_fields]
    assert "order" in base_names and "onFailure" in base_names
    field_names = [f["name"] for f in item.fields]
    assert "kind" not in field_names and "order" not in field_names


def test_operator_enum_full() -> None:
    """AssertOperator 全量 14 个进 enum —— $defs ref 解析必须生效。

    Enum 字段在属性级输出 {"$ref": "#/$defs/AssertOperator"}(2026-08-17
    实测),不解析会误判 ui_kind=unknown。
    """
    op = next(f for f in _idx().get("assertion").fields if f["name"] == "operator")
    assert op["ui_kind"] == "select"
    assert op["enum"] == [
        "eq", "ne", "gt", "gte", "lt", "lte", "in", "not_in",
        "contains", "not_contains", "exists", "empty", "length_eq", "schema",
    ]
    assert op["required"] is True


def test_list_for_system_ignores_system() -> None:
    """语法是全局的 —— 任意 system 作用域返回全量 kinds。"""
    idx = _idx()
    assert [it.kind for it in idx.list_for_system("fin")] == [
        it.kind for it in idx.list_global()
    ]
    assert idx.list_for_system("no-such-system")  # 不 404,照常全量


def test_to_view_produces_light_shape() -> None:
    """to_view 是 light view: kind / label / phase 三键。"""
    view = _idx().to_view(_idx().get("extract"))
    assert set(view.keys()) == {"kind", "label", "phase"}
