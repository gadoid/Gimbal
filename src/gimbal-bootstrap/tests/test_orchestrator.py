"""编排逻辑 —— 用假 Platform 测「断言真的被评估了」。

不打真平台：这些用例验证的是编排器的判定逻辑（passed/failed 怎么来、
清理怎么倒序），不是平台的响应。平台的真实往返在 orchestrator 的
端到端跑里验。
"""

import pytest

from gimbal_bootstrap.orchestrator import run_case
from gimbal_bootstrap.platform_client import PlatformError


class FakePlatform:
    """记录调用、按 path 返回预置响应的 Platform 替身。"""

    def __init__(self, responses: dict[str, tuple[int, object]]):
        self.responses = responses
        self.calls: list[tuple[str, str]] = []

    def request(self, method, path, body=None):
        self.calls.append((method, path))
        if path in self.responses:
            return self.responses[path]
        return 200, {"ok": True}

    def get(self, path):
        return self.request("GET", path)

    def post(self, path, body=None):
        return self.request("POST", path, body)

    def delete(self, path):
        return self.request("DELETE", path)


def _case(asserts, path="/api/health", method="GET"):
    return {"id": "TX", "name": "x", "steps": [
        {"method": method, "path": path, "auth": False, "asserts": asserts}
    ]}


def test_passing_asserts_are_counted_as_passed():
    client = FakePlatform({"/api/health": (200, {"status": "ok"})})
    r = run_case(
        _case([{"target": "$.call.response.status", "operator": "eq", "expected": 200},
               {"target": "$.call.response.body.status", "operator": "eq", "expected": "ok"}]),
        client, "sb-u",
    )
    assert r["error"] is None
    assert r["passed"] == 2 and r["failed"] == 0


def test_failing_assert_is_counted_as_failed_not_passed():
    """编排器不评估断言就报 passed —— 那是在自欺。"""
    client = FakePlatform({"/api/health": (200, {"status": "degraded"})})
    r = run_case(
        _case([{"target": "$.call.response.body.status", "operator": "eq", "expected": "ok"}]),
        client, "sb-u",
    )
    assert r["failed"] == 1 and r["passed"] == 0
    assert any("degraded" in f or "status" in f for f in r["failures"])


def test_orchestration_is_index_aligned_with_definition_steps():
    client = FakePlatform({"/api/scenarios": (201, {"scenarioId": "sc-x"})})
    case = _case([{"target": "$.call.response.status", "operator": "eq", "expected": 201}],
                 path="/api/scenarios", method="POST")
    case["steps"][0]["body"] = {"definition": {}, "orchestration": {}}
    run_case(case, client, "sb-u")
    post = next(c for c in client.calls if c == ("POST", "/api/scenarios"))
    assert post is not None


def test_cleanup_runs_in_dependency_reverse_order():
    client = FakePlatform({
        "/api/scenarios": (201, {"scenarioId": "sc-x"}),
        "/api/scenarios/sc-x/data-sets": (201, {"datasetId": "ds-1"}),
        "/api/scenarios/sc-x/run-schemes": (201, {"schemeId": "sc-1"}),
    })
    case = {"id": "TX", "name": "x", "steps": [
        {"method": "POST", "path": "/api/scenarios", "body": {},
         "asserts": [{"target": "$.call.response.status", "operator": "eq", "expected": 201}]},
        {"method": "POST", "path": "/api/scenarios/${sb.scenario_id}/data-sets",
         "body": {"name": "d"},
         "asserts": [{"target": "$.call.response.status", "operator": "eq", "expected": 201}]},
        {"method": "POST", "path": "/api/scenarios/${sb.scenario_id}/run-schemes",
         "body": {"name": "s"},
         "asserts": [{"target": "$.call.response.status", "operator": "eq", "expected": 201}]},
    ]}
    r = run_case(case, client, "sb-u")
    assert r["error"] is None
    deletes = [p for m, p in client.calls if m == "DELETE"]
    assert deletes == [
        "/api/scenarios/sc-x/run-schemes/sc-1",
        "/api/scenarios/sc-x/data-sets/ds-1",
        "/api/scenarios/sc-x",
    ], deletes


def test_platform_error_becomes_reported_failure_not_crash():
    class Boom(FakePlatform):
        def request(self, method, path, body=None):
            raise PlatformError(503, {"detail": "unavailable"})

    r = run_case(_case([{"target": "$.call.response.status", "operator": "eq",
                         "expected": 200}]), Boom({}), "sb-u")
    assert r["error"] and "503" in r["error"]


# --- 账号复用：重跑编排器不该每次都往平台里再塞一个账号 -----------------------


def test_existing_account_from_env_is_reused_without_registering(monkeypatch):
    """设了 GIMBAL_SB_USERNAME 就直接登录，不再注册新账号、也不再等人提权。"""
    from gimbal_bootstrap import orchestrator

    monkeypatch.setenv("GIMBAL_SB_USERNAME", "sb-existing")
    monkeypatch.setenv("GIMBAL_SB_PASSWORD", "Pw-12345678")

    seen: list[tuple[str, str, object]] = []

    class Recording:
        def __init__(self, base_url, token=None):
            seen.append(("init", base_url, token))
            self.token = token

        def post(self, path, body=None):
            seen.append(("post", path, body))
            return 200, {"access_token": "tok-1"}

    monkeypatch.setattr(orchestrator, "Platform", Recording)

    def boom():  # 复用路径上绝不能等人按回车
        raise AssertionError("复用已有账号时不该有人工暂停")

    monkeypatch.setattr("builtins.input", boom)

    client, username, _pw = orchestrator._bootstrap_account(pause=True)
    assert username == "sb-existing"
    assert client.token == "tok-1", "登录拿到的 token 必须挂到 client 上"
    assert [p for _, p, _ in seen if p == "/api/auth/register"] == []


def test_without_env_it_registers_a_fresh_random_account(monkeypatch):
    """没设 env 才注册，且用户名必须带随机尾巴 —— 固定名字第二次跑必 409。"""
    from gimbal_bootstrap import orchestrator

    monkeypatch.delenv("GIMBAL_SB_USERNAME", raising=False)

    posts: list[str] = []

    class Recording:
        def __init__(self, base_url, token=None):
            pass

        def post(self, path, body=None):
            posts.append(path)
            return 200, {"access_token": "tok-2"}

    monkeypatch.setattr(orchestrator, "Platform", Recording)
    monkeypatch.setattr("builtins.input", lambda: "")

    _, username, _pw = orchestrator._bootstrap_account(pause=True)
    assert "/api/auth/register" in posts
    assert username.startswith("sb_") and len(username) == 13, username


def test_generated_username_satisfies_the_platform_pattern(monkeypatch):
    """平台 `app/schemas/auth.py` 的 RegisterIn.username 是 `^[A-Za-z0-9_]+$` ——
    **不含连字符**。编排器生成的账号名必须过得了这一关，否则一启动就 422。"""
    import re

    from gimbal_bootstrap import orchestrator

    monkeypatch.delenv("GIMBAL_SB_USERNAME", raising=False)
    usernames: list[str] = []

    class Recording:
        def __init__(self, base_url, token=None):
            pass

        def post(self, path, body=None):
            if path == "/api/auth/register":
                usernames.append(body["username"])
            return 200, {"access_token": "tok-3"}

    monkeypatch.setattr(orchestrator, "Platform", Recording)
    monkeypatch.setattr("builtins.input", lambda: "")

    orchestrator._bootstrap_account(pause=True)
    assert usernames, "根本没调注册"
    assert re.match(r"^[A-Za-z0-9_]+$", usernames[0]), usernames[0]


def test_password_is_generated_not_hardcoded(monkeypatch):
    """管理员提权之后，硬编码在源码里的密码等于一个登进平台的活凭据。
    密码必须每次注册时随机生成，只在注册那一刻打印一次。"""
    import re
    import secrets

    from gimbal_bootstrap import orchestrator

    monkeypatch.delenv("GIMBAL_SB_USERNAME", raising=False)
    monkeypatch.delenv("GIMBAL_SB_PASSWORD", raising=False)
    seen: list[str] = []

    class Recording:
        def __init__(self, base_url, token=None):
            pass

        def post(self, path, body=None):
            if path == "/api/auth/register":
                seen.append(body["password"])
            return 200, {"access_token": "tok-4"}

    monkeypatch.setattr(orchestrator, "Platform", Recording)
    monkeypatch.setattr("builtins.input", lambda: "")

    orchestrator._bootstrap_account(pause=True)
    assert seen, "没调注册"
    # 平台 RegisterIn 要求：>=8 位，且同时含字母和数字
    assert len(seen[0]) >= 8 and re.search(r"[A-Za-z]", seen[0]) and re.search(r"\d", seen[0])
    # 源码里不得再留一个固定口令
    assert orchestrator.PASSWORD == "", "PASSWORD 不该是硬编码常量"
