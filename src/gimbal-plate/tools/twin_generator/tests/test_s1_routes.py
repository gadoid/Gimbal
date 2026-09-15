from pathlib import Path

from twin_generator.s1_routes import scan_actions
from conftest import FIXTURES

APP = FIXTURES / "php" / "app" / "Application"


def test_scan_actions():
    actions = scan_actions(APP)
    by_id = {a.id: a for a in actions}
    # Script 模块排除;_internal/__construct 排除;Base 排除
    assert set(by_id) == {"fin.order_entrust.order_add", "fin.order_entrust.order_page"}
    a = by_id["fin.order_entrust.order_add"]
    assert a.path == "/api/order/orderEntrust/orderAdd"
    assert a.method == "POST"
    assert a.ruleset == ("OrderEntrustValidator", "orderAddRules")
    assert a.validator_checks == ["checkSupplier"]
    assert a.callees == [("OrderEntrustService", "orderUpdate")]
    page = by_id["fin.order_entrust.order_page"]
    assert page.ruleset is None and page.callees == [("OrderEntrustService", "orderPage")]
