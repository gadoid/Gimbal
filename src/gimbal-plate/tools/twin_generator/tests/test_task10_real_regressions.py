"""Task 10 真源灰度暴露的回归钉(app2 fixture,形状均实测自 D:\fin-test)。

三个真源 bug:
1. tree-sitter-php 双引号字符串是 encapsed_string 节点,S2a/S2b/S3 只认 string
   → 双引号规则行整行丢失(generateOrderSubRules 实测 0 条)、双引号读取键丢失;
2. OrderController::orderAdd 把规则经局部变量间接绑定($rule = OrderValidator::$orderAddRules;
   paramVerification($rule))→ S1 正则只认 Cls::$prop 直写,回退按属性名撞类
   (orderAddRules 在 Order/OrderEntrust 两个 Validator 重名,实测错绑);
3. 被注释规则行无行尾 // 中文注时不捕获(真源 orderAddRules 丢 11 行);
   且回退绑定重名时无同模块优先(Customer/Order 撞名实测)。
"""
from pathlib import Path

from twin_generator.s1_routes import scan_actions
from twin_generator.s2_validator import parse_rules_file, attach_rules
from twin_generator.s2_reads import collect_reads
from twin_generator.s3_semantics import load_enums
from conftest import FIXTURES

APP2 = FIXTURES / "php" / "app2" / "Application"


def test_double_quoted_rule_rows_captured():
    rules = parse_rules_file(
        APP2 / "Order" / "Validator" / "OrderValidator.class.php")
    entries = {e.key: e for e in rules["orderAddRules"]}
    # 双引号值 "require|num" 不再整行丢失
    assert entries["customer_id"].required() is True
    assert entries["customer_id"].zh == "客户ID"
    # 双引号键 "order_sn"
    assert entries["order_sn"].rules == "exist"
    # 无行尾 // 注释的被注释行:键/规则仍在,zh 空且 inactive
    assert entries["settle_type"].active is False
    assert entries["settle_type"].rules == "present|num|in:1,2"
    assert entries["settle_type"].zh == ""
    assert entries["settle_type"].enum_values() == ["1", "2"]
    # 常规行不受影响
    assert entries["num"].required() is False and entries["num"].zh == "件数"


def test_indirect_ruleset_binding_via_local_var():
    acts_list = scan_actions(APP2)
    attach_rules(acts_list, APP2)
    add = next(a for a in acts_list if a.action == "orderAdd"
               and a.controller == "Order")
    # $rule = OrderValidator::$orderAddRules → 经变量解析到正确类(而非按名撞车
    # OrderEntrustValidator 的同名属性)
    assert add.ruleset == ("OrderValidator", "orderAddRules")
    assert {e.key for e in add.rules} == {
        "customer_id", "order_sn", "order_id", "settle_type", "num"}
    # customer_id require 来自双引号规则
    by_key = {e.key: e for e in add.rules}
    assert by_key["customer_id"].required() is True
    assert by_key["num"].active is True


def test_fallback_prefers_same_module_validator():
    acts_list = scan_actions(APP2)
    attach_rules(acts_list, APP2)
    rel = next(a for a in acts_list if a.action == "batchChangeRelated")
    # batchChangeRelatedRules 在 Customer(CustomerValidator)与 Order
    # (OrderEntrustValidator)撞名;Customer 控制器回退须取同模块
    assert [(e.key, e.zh) for e in rel.rules] == [("related_id", "关联ID")]


def test_double_quoted_read_keys():
    acts_list = scan_actions(APP2)
    attach_rules(acts_list, APP2)
    collect_reads(acts_list, APP2)
    edit = next(a for a in acts_list if a.action == "orderEdit")
    assert "pol" in edit.reads and edit.reads["pol"].via == "getData"
    assert "bl_no" in edit.reads and edit.reads["bl_no"].via == "subscript"


def test_double_quoted_enum_const():
    enums = load_enums(APP2)
    assert enums["PAY_TYPE"] == [("1", "付款")]
    assert enums["PUT_TYPE"] == [("2", "收款")]


def test_reads_do_not_leak_across_chained_services():
    acts_list = scan_actions(APP2)
    attach_rules(acts_list, APP2)
    collect_reads(acts_list, APP2)
    by_action = {a.action: a for a in acts_list}
    # orderDoc → makeDoc($orderId) → book([], $orderId):book 形参恰名
    # requestData 也不得串面 —— 请求面只有控制器实读的 order_id
    assert by_action["orderDoc"].reads == {"order_id"} or \
        set(by_action["orderDoc"].reads) == {"order_id"}
    # Service 自取请求(getRequestParam)仍可追踪;DB 行读不算请求面
    assert set(by_action["orderSelf"].reads) == {"etd"}


def test_direct_callee_with_request_param_keeps_recall():
    acts_list = scan_actions(APP2)
    attach_rules(acts_list, APP2)
    collect_reads(acts_list, APP2)
    by_action = {a.action: a for a in acts_list}
    # orderDoc 的直调 callee makeDoc 不持 requestData → 无串面;
    # OrderSvc::book 是链式被调(非直调),其 pol 不得出现在任何串面上
    assert "pol" not in by_action["orderDoc"].reads
    assert "bl_no" not in by_action["orderDoc"].reads
