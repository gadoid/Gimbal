import json
from pathlib import Path

import pytest

from gimbal_bootstrap.case_builder import build_definition

GOLDEN = {
    "id": "T1",
    "name": "健康检查",
    "steps": [
        {
            "method": "GET",
            "path": "/api/health",
            "endpoint": "platform.health.get_root",
            "auth": False,
            "asserts": [
                {"target": "$.call.response.status", "operator": "eq", "expected": 200},
                {"target": "$.call.response.body.status", "operator": "eq", "expected": "ok"},
            ],
        }
    ],
}


def test_every_step_carries_the_endpoint_id_the_composer_needs_to_render_its_form():
    """**这是「结构还是个 json」那一条的根因门。**

    前端 `stepEndpointId()` 只认 `call.view_hints.endpoint_id`；拿不到就不拉
    plate 的 `/full`，`requestNodes` 为空，于是 body 退回**裸 JSON 文本框** +
    「该接口未声明请求字段契约」提示。契约定义得再全也没用 —— 用例组织这一侧
    没把接口身份带过去，字段面就到不了编辑面。

    平台自带的「从接口目录添加」路径（CaseComposerCanvas.onAddEndpoint）写的就是
    这个 key，注释原话是「字段设计渲染/断言候选/数据集绑定都依赖此 key」。
    自举生成的场景是手搓的 definition，绕开了那条路径，所以漏了。
    """
    d = build_definition(GOLDEN, sb_username="sb-t-user")
    for step in d["steps"]:
        assert step["call"]["view_hints"]["endpoint_id"] == "platform.health.get_root"


@pytest.mark.parametrize(
    ("step_path", "contract_path"),
    [
        # 契约侧是 OpenAPI 的模板态 `{x}`，用例侧是运行态 `${sb.x}` ——
        # 两者是同一条路由，只是变量来源不同
        ("/api/scenarios/${sb.scenario_id}", "/api/scenarios/{scenario_id}"),
        ("/api/scenarios/${sb.scenario_id}/data-sets", "/api/scenarios/{scenario_id}/data-sets"),
        ("/api/auth/register", "/api/auth/register"),
    ],
)
def test_a_step_is_bound_to_the_contract_entry_its_route_resolves_to(step_path, contract_path):
    """step 声明的 endpoint 必须与它实际打的那条路由对得上。

    只写 id 不校验是不够的：id 写错一个字母，用例照样建得起来、跑得起来，只是
    编辑面挂的是另一个接口的字段面 —— 断言写对了、用例绿了，人在页面上看到的
    却是错的契约。比对走**路径归一**（`${x}` 与 `{x}` 同形），因为用例的 path 是
    运行态、契约的 path 是模板态。
    """
    from gimbal_bootstrap.case_builder import path_shape

    assert path_shape(step_path) == path_shape(contract_path)


def test_a_step_that_names_no_endpoint_is_rejected():
    """不给 endpoint 就没有身份可带 —— 与其静默退回裸 JSON，不如生成期就拒。"""
    case = {"id": "T1", "name": "x", "steps": [
        {"method": "GET", "path": "/api/health", "auth": False,
         "asserts": [{"target": "$.call.response.status", "operator": "eq", "expected": 200}]},
    ]}
    with pytest.raises(ValueError, match="endpoint"):
        build_definition(case, sb_username="sb-t-user")


def test_an_endpoint_that_drifted_out_of_the_contract_is_rejected():
    """平台下掉一条路由、用例还指着它时，生成期就要响。

    否则症状是：场景建得起来、跑得起来，页面上 body 是个裸 JSON 框，看不出是
    契约没了 —— 与本次修的一模一样。
    """
    case = {"id": "T1", "name": "x", "steps": [
        {"method": "GET", "path": "/api/health", "auth": False,
         "endpoint": "platform.health.get_gone",
         "asserts": [{"target": "$.call.response.status", "operator": "eq", "expected": 200}]},
    ]}
    with pytest.raises(ValueError, match="get_gone"):
        build_definition(case, sb_username="sb-t-user")


def test_a_step_pointing_at_the_wrong_contract_entry_is_rejected():
    """id 存在、但对不上这条路由 —— 比「id 根本不存在」更隐蔽。"""
    case = {"id": "T1", "name": "x", "steps": [
        {"method": "GET", "path": "/api/health", "auth": False,
         "endpoint": "platform.constants.get_root",
         "asserts": [{"target": "$.call.response.status", "operator": "eq", "expected": 200}]},
    ]}
    with pytest.raises(ValueError, match="route"):
        build_definition(case, sb_username="sb-t-user")


def test_every_golden_case_step_is_bound_to_its_contract_entry():
    """全量：8 条 golden case 的每一步，声明的 endpoint 都存在、路由对得上。

    且**发 body 的那几步**请求面真的非空 —— 非空才有表单可渲染，页面上的 body
    才不是裸 JSON 框。

    只对发 body 的方法提这个要求：GET 本来就没有请求体，请求面为空是**正确的**
    （契约里 42 个端点的请求面为空，其中相当一部分是 204/空体）。对无 body 的
    GET 提要求，等于逼用例侧去给契约编字段。
    """
    import yaml

    from gimbal_bootstrap.case_builder import CONTRACT_INDEX

    cases = yaml.safe_load(
        (Path(__file__).resolve().parents[1] / "cases" / "golden_path.yaml")
        .read_text(encoding="utf-8")
    )
    if isinstance(cases, dict):
        cases = cases.get("cases", [])

    problems: list[str] = []
    bodies = 0
    for case in cases:
        d = build_definition(case, sb_username="sb-t-user", run_token="r0")
        for i, step in enumerate(d["steps"]):
            eid = step["call"]["view_hints"]["endpoint_id"]
            ep = CONTRACT_INDEX.get(eid)
            if ep is None:
                problems.append(f"{case['id']} s{i}: {eid} 不在契约里")
                continue
            sends_body = step["call"]["method"] in ("POST", "PUT", "PATCH")
            if sends_body:
                bodies += 1
                if not ep.request.declarations:
                    problems.append(
                        f"{case['id']} s{i}: {eid} 发 body 却没有请求面声明，"
                        f"页面上仍是裸 JSON"
                    )
    assert not problems, "\n".join(problems)
    assert bodies >= 4, f"只有 {bodies} 步发 body —— golden_path 的覆盖面退化了"


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
                "method": "GET", "path": "/api/health", "endpoint": "platform.health.get_root", "auth": False,
                "extract": {"expr": "$.call.response.body.status", "target": "sb_status"},
            },
            {
                "method": "GET", "path": "/api/health", "endpoint": "platform.health.get_root", "auth": False,
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
            "method": "POST", "path": "/api/auth/register", "endpoint": "platform.auth.post_register", "auth": False,
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
            "steps": [{"method": "GET", "path": "/api/health", "service": "nope", "auth": False,
                       "endpoint": "platform.health.get_root"}]}
    with pytest.raises(ValueError, match="service"):
        build_definition(case, sb_username="u")


def test_step_without_strategy_is_rejected():
    case = {"id": "TX", "name": "x",
            "steps": [{"method": "GET", "path": "/api/health", "auth": False,
                       "endpoint": "platform.health.get_root"}]}
    with pytest.raises(ValueError, match="strategy"):
        build_definition(case, sb_username="u")


def test_auth_step_carries_bearer_header():
    case = {"id": "TX", "name": "x",
            "steps": [{"method": "GET", "path": "/api/scenarios", "endpoint": "platform.scenarios.get_root",
                       "asserts": [{"target": "$.call.response.status",
                                    "operator": "eq", "expected": 200}]}]}
    d = build_definition(case, sb_username="u")
    headers = d["steps"][0]["call"]["headers"]
    assert headers["Authorization"] == "Bearer ${auth.sb.token}"


def test_no_step_carries_the_retired_api_form():
    """v2.1 批次 F 退役了 step.api，plate 在 validate 期显式拒绝。

    生成器一旦改回 api 形态，platform 侧存进去的每个场景都是死的，而
    失败点在平台的 schema 校验里，离这里十万八千里。这门把它钉死在生成侧。
    """
    d = build_definition(GOLDEN, sb_username="u")
    for step in d["steps"]:
        assert "api" not in step, step
        assert step["call"]["kind"] == "call"
        assert step["call"]["protocol"] == "http"


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
            {"method": "POST", "path": "/api/auth/register", "endpoint": "platform.auth.post_register", "auth": False,
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
            {"method": "POST", "path": "/api/auth/register", "endpoint": "platform.auth.post_register", "auth": False,
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
        {"method": "POST", "path": "/api/auth/register", "endpoint": "platform.auth.post_register", "auth": False,
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
            {"method": "POST", "path": "/api/auth/register", "endpoint": "platform.auth.post_register", "auth": False,
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
            {"method": "POST", "path": "/api/auth/register", "endpoint": "platform.auth.post_register", "auth": False,
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
            {"method": "GET", "path": "/api/health", "endpoint": "platform.health.get_root", "auth": False,
             "body": {"note": "${sb.nonexistent}"},
             "asserts": [{"target": "$.call.response.status", "operator": "eq",
                          "expected": 200}]}]},
        sb_username="sb_boot", run_token="a1b2c3",
    )
    assert d["steps"][0]["request"]["body"]["note"] == "${sb.nonexistent}"


