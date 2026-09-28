"""编排逻辑 —— 用假 Platform 测「断言真的被评估了」。

不打真平台：这些用例验证的是编排器的判定逻辑（passed/failed 怎么来、
清理怎么倒序），不是平台的响应。平台的真实往返在 orchestrator 的
端到端跑里验。
"""

from pathlib import Path

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
        # 数据组的删除路由是扁平的 /api/data-sets/{id}，不挂在场景下
        "/api/data-sets/ds-1",
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


def test_password_defaults_to_a_fixed_value_and_env_wins(monkeypatch):
    """用户要登进平台检查自举账号，所以默认口令固定；GIMBAL_SB_PASSWORD 仍可覆盖。"""
    import re

    from gimbal_bootstrap import orchestrator

    seen: list[str] = []

    def register_with(env: dict | None) -> str:
        seen.clear()
        monkeypatch.delenv("GIMBAL_SB_USERNAME", raising=False)
        for k in ("GIMBAL_SB_PASSWORD",):
            monkeypatch.delenv(k, raising=False)
        for k, v in (env or {}).items():
            monkeypatch.setenv(k, v)

        class Recording:
            def __init__(self, base_url, token=None):
                pass

            def post(self, path, body=None):
                if path == "/api/auth/register":
                    seen.append(body["password"])
                return 200, {"access_token": "tok-5"}

        monkeypatch.setattr(orchestrator, "Platform", Recording)
        monkeypatch.setattr("builtins.input", lambda: "")
        orchestrator._bootstrap_account(pause=True)
        return seen[0]

    default = register_with(None)
    # 平台 RegisterIn：>=8 位，且同时含字母和数字
    assert len(default) >= 8 and re.search(r"[A-Za-z]", default) and re.search(r"\d", default)

    overridden = register_with({"GIMBAL_SB_PASSWORD": "Env-Ovr-9876"})
    assert overridden == "Env-Ovr-9876"
    assert overridden != default


def test_password_comes_from_local_env_file_not_source(tmp_path, monkeypatch):
    """固定口令要能登进平台检查，但不该躺在被跟踪的源码里。
    真值放在 gitignore 掉的 .env；进程环境变量仍然优先。"""
    from gimbal_bootstrap import orchestrator

    monkeypatch.delenv("GIMBAL_SB_PASSWORD", raising=False)
    monkeypatch.setattr(orchestrator, "DOTENV_PATH", tmp_path / ".env")
    (tmp_path / ".env").write_text("GIMBAL_SB_PASSWORD=from-dotenv-77\n", encoding="utf-8")

    assert orchestrator._resolve_password() == "from-dotenv-77"

    monkeypatch.setenv("GIMBAL_SB_PASSWORD", "from-process-88")
    assert orchestrator._resolve_password() == "from-process-88"


def test_missing_password_fails_loudly_instead_of_guessing(tmp_path, monkeypatch):
    from gimbal_bootstrap import orchestrator

    monkeypatch.delenv("GIMBAL_SB_PASSWORD", raising=False)
    monkeypatch.setattr(orchestrator, "DOTENV_PATH", tmp_path / ".env")
    with pytest.raises(SystemExit):
        orchestrator._resolve_password()


# --- 端到端第一次真跑揪出来的五个问题，各自钉一条测试 --------------------------


def test_list_get_on_a_collection_path_is_not_mistaken_for_a_created_resource():
    """D08：GET /api/data-sets 也以 /data-sets 结尾，但返回的是 list。
    按 path 后缀抓 id 就会在 list 上调 .get() 炸掉。只认 POST。"""
    client = FakePlatform({
        "/api/data-sets": (200, [{"datasetId": "ds-a"}]),
    })
    case = {"id": "D08", "name": "数据集列表", "steps": [
        {"method": "GET", "path": "/api/data-sets",
         "asserts": [{"target": "$.call.response.status", "operator": "eq", "expected": 200}]},
    ]}
    r = run_case(case, client, "sb_u", run_token="tk1")
    assert r["error"] is None, r["error"]
    assert r["failed"] == 0


def test_render_substitutes_new_username():
    """T2 注册用的新账号名，上一版 _render 漏了这个键，字面量原样发出去 422。"""
    from gimbal_bootstrap.orchestrator import _render

    out = _render(
        {"steps": [{"body": {"username": "${sb.new_username}",
                             "password": "${sb.password}"}}]},
        "sb_boot", "Pw-12345678", "sc-x-1",
    )
    assert out["steps"][0]["body"]["username"].startswith("sb_")
    assert out["steps"][0]["body"]["password"] == "Pw-12345678"


def test_render_substitutes_whole_object_placeholders():
    """T4 要把编排器构造好的 definition 整个塞进去，不能只替字符串。"""
    from gimbal_bootstrap.orchestrator import _render

    definition = {"scenarioId": "sc-x-1", "steps": [{"kind": "step"}]}
    out = _render({"body": {"definition": "${sb.definition}"}}, "u", "p", "sc-x-1",
                  definition=definition)
    assert out["body"]["definition"] == definition


def test_data_set_is_deleted_from_the_flat_route():
    """数据组的删除路由是 DELETE /api/data-sets/{id}，不是挂在场景下的。"""
    client = FakePlatform({
        "/api/scenarios": (201, {"scenarioId": "sc-x"}),
        "/api/scenarios/sc-x/data-sets": (201, {"datasetId": "ds-1"}),
    })
    case = {"id": "T5", "name": "建数据集", "steps": [
        {"method": "POST", "path": "/api/scenarios", "body": {},
         "asserts": [{"target": "$.call.response.status", "operator": "eq", "expected": 201}]},
        {"method": "POST", "path": "/api/scenarios/${sb.scenario_id}/data-sets",
         "body": {"name": "d"},
         "asserts": [{"target": "$.call.response.status", "operator": "eq", "expected": 201}]},
    ]}
    r = run_case(case, client, "sb_u", run_token="tk1")
    assert r["error"] is None, r["error"]
    deletes = [p for m, p in client.calls if m == "DELETE"]
    assert deletes == ["/api/data-sets/ds-1", "/api/scenarios/sc-x"], deletes


def test_golden_path_does_not_duplicate_the_scenario_creation(tmp_path):
    """编排器每条用例都已经建好一个场景（${sb.scenario_id} 指向它，T5/T6 建在
    它上面）。用例自己再 POST 一次同名场景必定 409。T4 改成读回来验证，
    不再重复创建。"""
    import yaml

    from gimbal_bootstrap.orchestrator import load_cases

    doc = yaml.safe_load(
        (Path(__file__).resolve().parents[1] / "cases" / "golden_path.yaml")
        .read_text(encoding="utf-8")
    )
    creators = [
        (c["id"], s["path"])
        for c in doc["cases"]
        for s in c["steps"]
        if s["method"] == "POST" and s["path"].rstrip("/") == "/api/scenarios"
    ]
    assert not creators, f"用例自己再建场景会和编排器的记账场景撞 id: {creators}"

    t4 = next(c for c in doc["cases"] if c["id"] == "T4")
    assert t4["steps"][0]["method"] == "GET"


def test_golden_path_register_uses_a_unique_display_name():
    """平台 assert_name_available 对 display_name 也查重。T2 发的
    display_name 不能是自举账号那个固定值。"""
    import yaml

    doc = yaml.safe_load(
        (Path(__file__).resolve().parents[1] / "cases" / "golden_path.yaml")
        .read_text(encoding="utf-8")
    )
    t2 = next(c for c in doc["cases"] if c["id"] == "T2")
    assert "${" in str(t2["steps"][0]["body"]["display_name"]), \
        t2["steps"][0]["body"]["display_name"]


def test_new_username_is_run_scoped_not_case_scoped():
    """T2 注册、T3 登录 —— 两次必须用同一个名字。之前按 scenario_id 派生，
    而 scenario_id 带用例 id，于是 T2 建的 sb_t2<x> 和 T3 登的 sb_t3<x>
    不是同一个账号，T3 必 401。新账号名必须由编排器按轮次传下来。"""
    from gimbal_bootstrap.orchestrator import _render

    out = _render(
        {"steps": [{"body": {"username": "${sb.new_username}"}}]},
        "sb_boot", "Pw-12345678", "sc-t3-tok", new_username="sb_shared9",
    )
    assert out["steps"][0]["body"]["username"] == "sb_shared9"
