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
                     "password": "Sb-Test-12345"},
            "asserts": [{"target": "$.call.response.status", "operator": "eq", "expected": 201}],
        }],
    }
    d = build_definition(case, sb_username="sb-t-a1b2c3")
    body = d["steps"][0]["request"]["body"]
    assert body["username"] == "sb-t-a1b2c3"
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
