"""T3.2 Enum 类自动挂载回归钉。

判据两层:键名(剥 _type/_status/_state)== 类名去 Enum 后缀
(后缀族一致:pay_type 不配 PayStatusEnum),且与 in: 规则一致
(规则赢,冲突留 enum_candidate)。
"""
from twin_generator.ir import ActionIR, RuleEntry
from twin_generator.s3_semantics import _match_enum_class, _enum_map, enrich
from twin_generator.schema_source import ColumnCatalog

ENUMS = {
    "OrderRevokeStatusEnum": [("0", ""), ("1", "撤单中"), ("2", "撤单成功"),
                              ("3", "撤单失败"), ("4", "有意向撤单"),
                              ("0", "未撤单")],
    "PayStatusEnum": [("0", "未支付"), ("1", "已支付")],
    "OrderEnum": [("1", "海运"), ("2", "空运")],
    "AuditEnum": [("1", "待审"), ("2", "已审")],
}


def test_match_enum_class_suffix_family():
    assert _match_enum_class("revoke_status", ENUMS) == "OrderRevokeStatusEnum"
    assert _match_enum_class("order_status", ENUMS) == "OrderEnum"
    assert _match_enum_class("audit_type", ENUMS) == "AuditEnum"
    # 后缀族不一致:支付方式 ≠ 支付状态 → 拒
    assert _match_enum_class("pay_type", ENUMS) is None
    # 裸 status(剥完为空)/无后缀键 → 不挂
    assert _match_enum_class("status", ENUMS) is None
    assert _match_enum_class("bl_no", ENUMS) is None


def test_enum_map_list_overrides_const():
    m = _enum_map(ENUMS["OrderRevokeStatusEnum"])
    assert m["0"] == "未撤单"          # $list 后写覆盖 const 空注释
    assert list(m) == ["0", "1", "2", "3", "4"]   # 值有序去重


def test_enrich_auto_attach_when_no_in_rule():
    a = ActionIR(module="Order", controller="Order", action="orderAdd")
    a.rules = [RuleEntry(key="revoke_status", rules="require")]
    fs = enrich([a], ColumnCatalog([]), None, {}, {}, {}, ENUMS)
    f = {x.key: x for x in fs["fin.order.order_add"]}["revoke_status"]
    assert f.enum_values == ["0", "1", "2", "3", "4"]
    assert f.enum_candidate == "OrderRevokeStatusEnum"


def test_enrich_rule_in_wins_on_conflict():
    a = ActionIR(module="Order", controller="Order", action="orderAdd")
    a.rules = [RuleEntry(key="revoke_status", rules="require|in:9,8")]
    fs = enrich([a], ColumnCatalog([]), None, {}, {}, {}, ENUMS)
    f = {x.key: x for x in fs["fin.order.order_add"]}["revoke_status"]
    assert f.enum_values == ["9", "8"]            # 规则赢
    assert f.enum_candidate == "OrderRevokeStatusEnum"   # 冲突留痕


def test_enrich_rule_in_consistent_keeps_rule():
    a = ActionIR(module="Order", controller="Order", action="orderAdd")
    a.rules = [RuleEntry(key="order_status", rules="in:1,2")]
    fs = enrich([a], ColumnCatalog([]), None, {}, {}, {}, ENUMS)
    f = {x.key: x for x in fs["fin.order.order_add"]}["order_status"]
    assert f.enum_values == ["1", "2"]            # 一致:规则给的保持
