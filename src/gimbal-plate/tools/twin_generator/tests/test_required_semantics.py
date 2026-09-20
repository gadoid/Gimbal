"""T4.1 required 语义回归钉(四分支)。

手建 ground truth 实证:
- 表单动作(add/edit/book/dispatch + action 键)require 直译全降级;
- present 语义 = 键须存在(must_include),required 恒 False;
- page 端点 page_no/page_size 无规则也必填。
"""
from twin_generator.ir import ActionIR, RuleEntry
from twin_generator.s3_semantics import _required_of, _is_form_action
from twin_generator.schema_source import ColumnCatalog
from twin_generator.s3_semantics import enrich


def _rule(rules: str):
    return RuleEntry(key="x", rules=rules)


def test_is_form_action():
    assert _is_form_action("orderAdd")
    assert _is_form_action("orderBook")
    assert _is_form_action("book_real_amount_edit")
    assert _is_form_action("OrderDispatch")
    assert not _is_form_action("orderPage")
    assert not _is_form_action("asset_push")


def test_require_non_form_action_true():
    assert _required_of(_rule("require"), False, "order_id",
                        "orderNotice", True) is True


def test_require_form_action_downgraded():
    assert _required_of(_rule("require"), False, "bl_no",
                        "orderAdd", True) is False


def test_present_always_false():
    # read 与否都 False(present 归 must_include)
    assert _required_of(_rule("present"), True, "bl_no", "orderPage", False) is False
    assert _required_of(_rule("present"), False, "bl_no", "orderAdd", True) is False


def test_page_keys_required_on_list_actions():
    assert _required_of(None, False, "page_no", "orderPage", False) is True
    assert _required_of(None, False, "page_size", "auditList", False) is True
    assert _required_of(None, False, "page_no", "orderAdd", False) is False


def test_enrich_end_to_end_branches():
    a = ActionIR(module="Order", controller="Order", action="orderPage")
    a.rules = [RuleEntry(key="bl_no", rules="present")]
    a.reads = {"bl_no": None}          # type: ignore[dict-item]
    fs = enrich([a], ColumnCatalog([]), None, {}, {}, {})
    by = {f.key: f for f in fs["fin.order.order_page"]}
    assert by["bl_no"].required is False
    assert by["page_no"].required is True and by["page_size"].required is True
    assert by["bl_no"].must_include is True
