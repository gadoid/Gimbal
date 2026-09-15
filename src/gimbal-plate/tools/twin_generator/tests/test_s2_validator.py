from twin_generator.s2_validator import parse_rules_file, attach_rules
from twin_generator.s1_routes import scan_actions
from conftest import FIXTURES


def test_parse_rules_file():
    rules = parse_rules_file(FIXTURES / "php" / "sample_validator.php")
    entries = rules["orderAddRules"]
    by_key = {e.key: e for e in entries}
    assert by_key["customer_id"].required() and by_key["customer_id"].zh == "客户ID"
    # 被注释行:active=False 但键/规则/中文都在
    carrier = by_key["carrier"]
    assert carrier.active is False and carrier.zh == "船公司/承运人"
    assert by_key["settle_type"].enum_values() == ["1", "2"]
    assert by_key["bl_no"].max_length() == 32


def test_attach_rules():
    app = FIXTURES / "php" / "app" / "Application"
    # fixture app 需有 Validator:补一个最小文件(见 Step 2 注)
    actions = scan_actions(app)
    attach_rules(actions, app)
    add = next(a for a in actions if a.action == "orderAdd")
    assert {e.key for e in add.rules} >= {"customer_id", "carrier", "bl_no"}
    page = next(a for a in actions if a.action == "orderPage")
    assert page.rules == []          # 无绑定无同名规则集
