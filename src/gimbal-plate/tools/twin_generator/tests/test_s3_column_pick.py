"""T3.3 跨表 zh 上下文选表回归钉。

双表 fixture:同名列在模块表/无关表都有 → 模块表胜;
零模块命中回退全局首现;多候选注释不一致 flag zh_ambiguous。
"""
from pathlib import Path

from twin_generator.ir import ActionIR, RuleEntry
from twin_generator.s3_semantics import enrich, _pick_column
from twin_generator.schema_source import ColumnCatalog, ColumnInfo


def _cols():
    return [
        ColumnInfo(table="sys_user", column="status", col_type="tinyint(1)",
                   nullable=True, default=None, comment="用户状态"),
        ColumnInfo(table="sys_order", column="status", col_type="tinyint(1)",
                   nullable=True, default=None, comment="订单状态"),
        ColumnInfo(table="sys_order_sub", column="status", col_type="tinyint(1)",
                   nullable=True, default=None, comment=""),
    ]


def test_pick_column_module_table_wins():
    col, amb = _pick_column(_cols(), {"sys_order"})
    assert col.table == "sys_order" and col.comment == "订单状态"
    assert amb is False     # 唯一注释非空候选


def test_pick_column_ambiguous_flag():
    cols = _cols() + [ColumnInfo(
        table="sys_order_self", column="status", col_type="tinyint(1)",
        nullable=True, default=None, comment="自营订单状态")]
    col, amb = _pick_column(cols, {"sys_order"})
    assert amb is True      # 两个非空且不一致的注释 → 平局


def test_pick_column_fallback_global_first():
    col, amb = _pick_column(_cols(), {"sys_nonexistent"})
    assert col.table == "sys_user" and amb is False


def test_enrich_uses_module_table_zh():
    a = ActionIR(module="Order", controller="Order", action="orderPage")
    a.rules = [RuleEntry(key="status", rules="require")]
    fs = enrich([a], ColumnCatalog(_cols()), None, {}, {},
                {"Order": {"sys_order"}})
    f = fs["fin.order.order_page"][0]
    assert f.zh == "订单状态" and f.zh_source == "column"
    assert f.tables[0] == "sys_user"      # tables 保留全量,只选列变了
