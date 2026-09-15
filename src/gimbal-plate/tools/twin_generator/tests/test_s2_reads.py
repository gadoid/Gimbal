from twin_generator.s1_routes import scan_actions
from twin_generator.s2_validator import attach_rules
from twin_generator.s2_reads import collect_reads
from conftest import FIXTURES

APP = FIXTURES / "php" / "app" / "Application"


def _actions():
    acts = scan_actions(APP)
    attach_rules(acts, APP)
    collect_reads(acts, APP)
    return {a.action: a for a in acts}


def test_reads_via_getdata_and_default():
    acts = _actions()
    r = acts["orderAdd"].reads
    assert r["action"].via == "getData" and r["action"].default == "submit"  # 别名 $data 也追到
    assert r["bl_no"].via == "subscript"
    assert r["container"].via == "isset"
    # 跨服务边 + 形参链($requestData → $payload)
    assert r["etd"].via == "isset"
    assert r["service_items"].via == "getData"
    assert "status" in acts["orderPage"].reads
