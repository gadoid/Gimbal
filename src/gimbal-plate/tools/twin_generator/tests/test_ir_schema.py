from twin_generator.ir import RuleEntry, ActionIR
from twin_generator.schema_source import load_columns
from conftest import FIXTURES


def test_rule_entry_derivations():
    r = RuleEntry("settle_type", "exist|num|in:1,2", zh="结算类型")
    assert r.required() is False            # exist≠非空
    assert r.must_include() is True         # 键须存在
    assert r.enum_values() == ["1", "2"]
    assert RuleEntry("customer_id", "require|num").required() is True
    assert RuleEntry("bl_no", "present|length_max:32").required() is True
    assert RuleEntry("bl_no", "present|length_max:32").max_length() == 32


def test_action_ir_naming():
    a = ActionIR(module="Order", controller="OrderEntrust", action="orderAdd")
    assert a.path == "/api/order/orderEntrust/orderAdd"
    assert a.id == "fin.order_entrust.order_add"
    assert a.const_name == "ORDER_ENTRUST_ORDER_ADD"


def test_load_columns():
    cat = load_columns(FIXTURES / "schema" / "fin_test_search.csv")
    cust = cat.by_name["customer_id"][0]
    assert (cust.table, cust.comment, cust.default) == ("sys_order", "客户ID", "0")
    # not_null_no_default:全表一致且无默认才 True;create_time 排除
    assert cat.not_null_no_default("bl_no") is True      # NO + "" 空默认
    assert cat.not_null_no_default("customer_id") is False  # 默认 '0'
    assert cat.not_null_no_default("etd") is False          # 默认 '0'
    assert cat.not_null_no_default("create_time") is False  # 排除清单
