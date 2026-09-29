import json

import pytest

from gimbal_bootstrap.case_builder import build_definition

GOLDEN = {
    "id": "T1",
    "name": "健康检查",
    "steps": [
        {
            "method": "GET",
            "path": "/api/health",
            "auth": False,
            "asserts": [
                {"target": "$.call.response.status", "operator": "eq", "expected": 200},
                {"target": "$.call.response.body.status", "operator": "eq", "expected": "ok"},
            ],
        }
    ],
}


def test_definition_passes_plate_validation():
    """用真实 plate 的 Scenario 模型校验 —— 少一个必填字段就会炸。"""
    import httpx
    from gimbal_plate.schema.scenario import Scenario

    d = build_definition(GOLDEN, sb_username="sb-t-user")

    # 契约本身必须合法
    Scenario.model_validate(d)

    # 且必须真的被 plate 的 convert 接受
    resp = httpx.post(
        "http://127.0.0.1:8765/api/scenario/action/convert",
        json={"consumer": "gimbal", "scenario": d},
        timeout=30.0,
    )
    assert resp.status_code == 200, resp.text[:500]


def test_scenario_id_matches_platform_regex():
    """Review Focus #4：scenarioId 必须匹配 ^sc-[a-z0-9-]+$。"""
    import re

    d = build_definition(GOLDEN, sb_username="sb-t-user")
    assert re.match(r"^sc-[a-z0-9-]+$", d["scenarioId"]), d["scenarioId"]


def test_assertions_carry_call_response_targets():
    d = build_definition(GOLDEN, sb_username="sb-t-user")
    strategies = d["steps"][0]["strategy"]
    assert len(strategies) == 2
    assert all(s["kind"] == "assertion" for s in strategies)
    assert strategies[0]["target"] == "$.call.response.status"


def test_extract_targets_use_call_response_body_prefix():
    """跨 step 传递必须走 $.call.response.body.* 通道。"""
    case = {
        "id": "TX",
        "name": "提取",
        "steps": [
            {
                "method": "GET", "path": "/api/health", "auth": False,
                "extract": {"expr": "$.call.response.body.status", "target": "sb_status"},
            },
            {
                "method": "GET", "path": "/api/health", "auth": False,
                "asserts": [{"target": "$.call.response.body.status", "operator": "eq",
                             "expected": "${sb_status}"}],
            },
        ],
    }
    d = build_definition(case, sb_username="sb-t-user")
    first = d["steps"][0]["strategy"][0]
    assert first["kind"] == "extract"
    assert first["expression"] == "$.call.response.body.status"
    assert first["target"] == "sb_status"
    assert first["scope"] == "scenario"


def test_body_template_substitutes_sb_username():
    """Review Focus #5：用户名带 uuid，避免重复运行撞名 409。"""
    case = {
        "id": "TX", "name": "注册",
        "steps": [{
            "method": "POST", "path": "/api/auth/register", "auth": False,
            "body": {"username": "${sb.username}", "display_name": "sb bootstrap",
                     "password": "Pw-12345678"},
            "asserts": [{"target": "$.call.response.status", "operator": "eq", "expected": 201}],
        }],
    }
    d = build_definition(case, sb_username="sb_t_a1b2c3")
    body = d["steps"][0]["request"]["body"]
    assert body["username"] == "sb_t_a1b2c3"
    assert "${" not in str(body)


def test_unknown_service_is_rejected():
    case = {"id": "TX", "name": "x",
            "steps": [{"method": "GET", "path": "/api/health", "service": "nope", "auth": False}]}
    with pytest.raises(ValueError, match="service"):
        build_definition(case, sb_username="u")


def test_step_without_strategy_is_rejected():
    case = {"id": "TX", "name": "x",
            "steps": [{"method": "GET", "path": "/api/health", "auth": False}]}
    with pytest.raises(ValueError, match="strategy"):
        build_definition(case, sb_username="u")


def test_auth_step_carries_bearer_header():
    case = {"id": "TX", "name": "x",
            "steps": [{"method": "GET", "path": "/api/scenarios",
                       "asserts": [{"target": "$.call.response.status",
                                    "operator": "eq", "expected": 200}]}]}
    d = build_definition(case, sb_username="u")
    headers = d["steps"][0]["api"]["headers"]
    assert headers["Authorization"] == "Bearer ${auth.sb.token}"


def test_run_token_makes_scenario_id_unique_per_run():
    """Review Focus #5（重跑侧）：固定 scenarioId 第二次跑必 409。"""
    import re

    a = build_definition(GOLDEN, sb_username="u", run_token="a1b2c3")
    b = build_definition(GOLDEN, sb_username="u", run_token="d4e5f6")
    assert a["scenarioId"] != b["scenarioId"]
    assert re.match(r"^sc-[a-z0-9-]+$", a["scenarioId"]), a["scenarioId"]
    assert a["scenarioId"] == "sc-t1-a1b2c3"


def test_run_token_keeps_scenario_id_regex_safe():
    import re

    d = build_definition(GOLDEN, sb_username="u", run_token="../../etc")
    assert re.match(r"^sc-[a-z0-9-]+$", d["scenarioId"]), d["scenarioId"]


def test_new_username_is_distinct_from_the_bootstrap_account():
    """黄金链路 T2 要验 register 端点，但它注册的是编排器自己刚建好的那个
    账号 —— 同名第二次跑必 409。必须另给一个每轮唯一的新用户名。"""
    d = build_definition(
        {"id": "T2", "name": "注册", "steps": [
            {"method": "POST", "path": "/api/auth/register", "auth": False,
             "body": {"username": "${sb.new_username}", "password": "${sb.new_password}"},
             "asserts": [{"target": "$.call.response.status", "operator": "eq",
                          "expected": 201}]}]},
        sb_username="sb_boot", run_token="a1b2c3", new_password="Throw-9911",
    )
    body = d["steps"][0]["request"]["body"]
    assert body["username"] != "sb_boot"
    assert body["username"] == "sb_a1b2c3", body["username"]
    assert body["password"] == "Throw-9911"
    assert "${" not in str(body)


def test_admin_password_never_lands_in_the_persisted_scenario():
    """管理员口令不能进 definition。

    definition 就是 POST /api/scenarios 的 body，平台把它存进
    composer_scenario.payload，每次运行再深拷贝进 execution_snapshots ——
    那张表本仓库里没人清理。口令进去等于把平台交出去，而且是绕过
    「口令不入库」那条原则从数据库这条路绕出去的。

    一次性账号必须用**当场生成的一次性口令**，跟管理员口令无关。"""
    d = build_definition(
        {"id": "T2", "name": "注册", "steps": [
            {"method": "POST", "path": "/api/auth/register", "auth": False,
             "body": {"username": "${sb.new_username}", "password": "${sb.new_password}"},
             "asserts": [{"target": "$.call.response.status", "operator": "eq",
                          "expected": 201}]}]},
        sb_username="sb_boot", sb_password="ADMIN-SECRET-9f3a",
        run_token="a1b2c3", new_password="Throw-9911",
    )
    assert "ADMIN-SECRET-9f3a" not in json.dumps(d, ensure_ascii=False)


def test_builder_has_no_substitution_key_for_the_admin_password():
    """`${sb.password}` 这个占位符本身就不该存在 —— 留着它，早晚有人
    在某个用例里填进去。"""
    case = {"id": "T2", "name": "注册", "steps": [
        {"method": "POST", "path": "/api/auth/register", "auth": False,
         "body": {"username": "${sb.new_username}", "password": "${sb.password}"},
         "asserts": [{"target": "$.call.response.status", "operator": "eq",
                      "expected": 201}]}]}
    d = build_definition(case, sb_username="sb_boot", sb_password="ADMIN-SECRET-9f3a",
                         run_token="a1b2c3", new_password="Throw-9911")
    body = d["steps"][0]["request"]["body"]
    assert body["password"] != "ADMIN-SECRET-9f3a", body
    assert "${sb.password}" in body["password"], body


def test_new_username_satisfies_platform_username_pattern():
    """平台 RegisterIn.username = ^[A-Za-z0-9_]+$，不含连字符。"""
    import re

    d = build_definition(
        {"id": "T2", "name": "注册", "steps": [
            {"method": "POST", "path": "/api/auth/register", "auth": False,
             "body": {"username": "${sb.new_username}"},
             "asserts": [{"target": "$.call.response.status", "operator": "eq",
                          "expected": 201}]}]},
        sb_username="sb_boot", sb_password="Pw-123456", run_token="A1B2-C3/../D",
    )
    u = d["steps"][0]["request"]["body"]["username"]
    assert re.match(r"^[A-Za-z0-9_]+$", u), u


def test_substituted_text_is_never_rescanned_for_more_placeholders():
    """替换是**一遍过**的。

    逐个 key 依次 replace 的话，替换出来的内容会被后面的 key 再扫一遍：
    一次性口令里只要含有 `${sb.new_username}` 这种字面量，就会被当占位符
    改掉，T3 登录时拿着一个不存在的用户名。"""
    d = build_definition(
        {"id": "T2", "name": "注册", "steps": [
            {"method": "POST", "path": "/api/auth/register", "auth": False,
             "body": {"username": "${sb.new_username}", "password": "${sb.new_password}"},
             "asserts": [{"target": "$.call.response.status", "operator": "eq",
                          "expected": 201}]}]},
        sb_username="sb_boot", run_token="a1b2c3",
        new_username="sb_x", new_password="p4ss${sb.new_username}w0rd",
    )
    body = d["steps"][0]["request"]["body"]
    assert body["password"] == "p4ss${sb.new_username}w0rd", body["password"]


def test_unknown_placeholder_is_left_alone():
    """别把不认识的占位符清成空串 —— 那样一条用例会静悄悄丢掉它要填的东西。"""
    d = build_definition(
        {"id": "T1", "name": "x", "steps": [
            {"method": "GET", "path": "/api/health", "auth": False,
             "body": {"note": "${sb.nonexistent}"},
             "asserts": [{"target": "$.call.response.status", "operator": "eq",
                          "expected": 200}]}]},
        sb_username="sb_boot", run_token="a1b2c3",
    )
    assert d["steps"][0]["request"]["body"]["note"] == "${sb.nonexistent}"


