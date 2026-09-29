"""编排器 —— 验证的是「由 gimbal 驱动」这件事本身。

编排器**不执行**用例里的 HTTP 步骤：它把场景建出来、发起运行、把引擎的
判定读回来、清理干净。步骤执行和断言求值都是 gimbal 的活。这里不打真平台 ——
平台的真实往返在端到端跑里验。
"""

import json

import pytest

from gimbal_bootstrap.orchestrator import run_case
from gimbal_bootstrap.platform_client import PlatformError

RESULT_OK = {
    "status": "passed", "total": 1, "passed": 1, "failed": 0, "skipped": 0,
    "details": [],
}
RESULT_BAD = {
    "status": "failed", "total": 1, "passed": 0, "failed": 1, "skipped": 0,
    "details": [{
        "scenario_id": "sc-x",
        "steps": [{
            "step_id": "step-000", "status": "failed",
            "error": "期望 200 实得 403", "error_phase": "verifying",
        }],
    }],
}


class FakePlatform:
    """记录调用、按 path 返回预置响应的 Platform 替身。

    默认让运行一步到位地跑完（终态 done + 一份通过的 result.json），
    免得用例全在 _poll 里等到超时。
    """

    def __init__(self, responses=None, *, result=RESULT_OK):
        self.responses = responses or {}
        self.calls = []
        self.writes = []  # (method, path, body)
        self.token = "tok-fake"
        self._result = result

    def request(self, method, path, body=None):
        self.calls.append((method, path))
        if method != "GET":
            self.writes.append((method, path, body))
        if "case-artifact" in path:
            return 200, self._result
        if path in self.responses:
            return self.responses[path]
        return 200, {"ok": True}

    def get(self, path):
        return self.request("GET", path)

    def post(self, path, body=None):
        return self.request("POST", path, body)

    def delete(self, path):
        return self.request("DELETE", path)


def _client(**kw):
    return FakePlatform({
        "/api/scenarios": (201, {"scenarioId": "sc-x"}),
        "/api/runs": (201, {"executionId": 42}),
        "/api/executions/42": (200, {"status": "done", "totalRuns": 1}),
        "/api/executions/42/rows": (200, {"items": [
            {"caseDir": "case-000-r0-n0", "status": "done"}]}),
    }, **kw)


def _case(path="/api/health", method="GET", endpoint="platform.health.get_root"):
    return {"id": "D01", "name": "花名册", "steps": [
        {"method": method, "path": path, "endpoint": endpoint,
         "asserts": [{"target": "$.call.response.status", "operator": "eq",
                      "expected": 200}]}
    ]}


def _run(client=None, case=None, **kw):
    return run_case(case or _case(), client or _client(), "sb_u",
                    run_token="tk1", **kw)


# --- 编排器不自己发 HTTP：那是 gimbal 的活 ---------------------------------


def test_orchestrator_never_calls_the_case_paths_itself():
    client = _client()
    _run(client)
    assert "/api/users/roster" not in [p for _, p in client.calls], client.calls


def test_every_case_becomes_a_dispatched_run():
    client = _client()
    r = _run(client)
    assert ("POST", "/api/scenarios") in client.calls, client.calls
    assert ("POST", "/api/runs") in client.calls, client.calls
    assert r["executionId"] == 42, r


def test_run_is_issued_against_the_scenario_that_was_created():
    client = _client()
    _run(client)
    runs = [b for m, p, b in client.writes if p == "/api/runs"]
    assert runs == [{"scenarioId": "sc-x", "nRuns": 1, "parallel": 1}], runs


def test_orchestration_stays_index_aligned_with_the_definition():
    client = _client()
    _run(client)
    body = next(b for m, p, b in client.writes if p == "/api/scenarios")
    assert len(body["orchestration"]["steps"]) == len(body["definition"]["steps"])


# --- 判定来自 gimbal，不是编排器自己算的 -----------------------------------


def test_counts_come_from_gimbal_result_json():
    r = _run(_client(result=RESULT_BAD))
    assert r["passed"] == 0 and r["failed"] == 1, r
    assert any("403" in f and "verifying" in f for f in r["failures"]), r["failures"]


def test_passing_run_reports_gimbal_pass_counts():
    r = _run()
    assert r["passed"] == 1 and r["failed"] == 0, r
    assert r["ok"] is True, r


def test_result_json_may_arrive_as_a_raw_string():
    """artifact 接口给的是文件原文，解析责任在编排器。"""
    r = _run(_client(result=json.dumps(RESULT_BAD)))
    assert r["failed"] == 1, r


def test_a_run_gimbal_rejects_is_reported_as_failed():
    client = _client()
    client.responses["/api/executions/42"] = (200, {"status": "failed"})
    client.responses["/api/executions/42/rows"] = (200, {"items": [
        {"caseDir": "case-000-r0-n0", "status": "gimbal_rejected"}]})
    r = _run(client)
    assert r["failed"] >= 1, r
    assert any("gimbal" in f for f in r["failures"]), r["failures"]


def test_unparseable_result_json_is_a_failure_not_a_silent_pass():
    r = _run(_client(result="not json at all"))
    assert r["failed"] == 1, r


# --- 生命周期 -------------------------------------------------------------


def test_scenario_is_deleted_after_the_run():
    client = _client()
    _run(client)
    assert [p for m, p in client.calls if m == "DELETE"] == ["/api/scenarios/sc-x"]


def test_scenario_is_deleted_even_when_the_run_blows_up():
    class Boom(FakePlatform):
        def post(self, path, body=None):
            if path == "/api/runs":
                raise PlatformError(503, {"detail": "dispatcher down"})
            return FakePlatform.post(self, path, body)

    client = Boom({"/api/scenarios": (201, {"scenarioId": "sc-x"})})
    r = _run(client)
    assert r["error"] and "503" in r["error"]
    assert [p for m, p in client.calls if m == "DELETE"] == ["/api/scenarios/sc-x"]


def test_platform_error_becomes_a_reported_failure_not_a_crash():
    class Boom(FakePlatform):
        def post(self, path, body=None):
            raise PlatformError(503, {"detail": "unavailable"})

    r = _run(Boom({}))
    assert r["error"] and "503" in r["error"]


# --- 凭证池：场景引 alias，平台在 run 期注入 --------------------------------


def test_bootstrap_creates_a_credential_pool_entry_for_the_sb_account():
    """场景步骤头写 ${auth.sb.token}，平台调度时按 alias 从凭证池解析。池里
    没有 sb 这条，gimbal 就 gimbal_rejected。池里存的是**口令**不是 token ——
    引擎拿 auth.url 现登一次换 token。"""
    from gimbal_bootstrap.orchestrator import CREDENTIAL_URL, _ensure_credential

    client = FakePlatform()
    _ensure_credential(client, "sb_abc", "Pw-12345678")
    posts = [b for m, p, b in client.writes if m == "POST" and p == "/api/auths"]
    assert posts == [{
        "alias": "sb", "url": CREDENTIAL_URL,
        "username": "sb_abc", "password": "Pw-12345678",
        "token_type": "Bearer",
    }], posts


def test_bootstrap_reuses_an_existing_credential_instead_of_duplicating():
    from gimbal_bootstrap.orchestrator import _ensure_credential

    client = FakePlatform({"/api/auths": (200, {"items": [
        {"id": 7, "alias": "sb", "url": "http://127.0.0.1:8000/api/auth/login"}]})})
    _ensure_credential(client, "sb_abc", "Pw-new")
    patches = [(p, b) for m, p, b in client.writes if m == "PATCH"]
    assert [p for p, _ in patches] == ["/api/auths/7"], client.writes
    assert patches[0][1]["username"] == "sb_abc"
    assert not [c for c in client.writes if c[0] == "POST" and c[1] == "/api/auths"]


# --- 账号 -----------------------------------------------------------------


def test_existing_account_from_env_is_reused_without_registering(monkeypatch):
    """设了 GIMBAL_SB_USERNAME 就直接登录，不再注册新账号、也不再等人提权。"""
    from gimbal_bootstrap import orchestrator

    monkeypatch.setenv("GIMBAL_SB_USERNAME", "sb_existing")
    monkeypatch.setenv("GIMBAL_SB_PASSWORD", "Pw-12345678")

    seen = []

    class Recording:
        def __init__(self, base_url, token=None):
            seen.append(("init", base_url))
            self.token = token

        def post(self, path, body=None):
            seen.append(("post", path, body))
            return 200, {"access_token": "tok-1"}

    monkeypatch.setattr(orchestrator, "Platform", Recording)
    monkeypatch.setattr("builtins.input", _never_pause)

    client, username, _pw = orchestrator._bootstrap_account(pause=True)
    assert username == "sb_existing"
    assert client.token == "tok-1", "登录拿到的 token 必须挂到 client 上"
    assert [e[1] for e in seen if e[0] == "post"] == ["/api/auth/login"], seen


def test_generated_username_satisfies_the_platform_pattern(tmp_path, monkeypatch):
    """平台 app/schemas/auth.py 的 RegisterIn.username 是 `^[A-Za-z0-9_]+$` ——
    **不含连字符**。生成的账号名过不了这一关，一启动就 422。"""
    import re

    from gimbal_bootstrap import orchestrator

    monkeypatch.delenv("GIMBAL_SB_USERNAME", raising=False)
    monkeypatch.setenv("GIMBAL_SB_PASSWORD", "Pw-12345678")
    monkeypatch.setattr(orchestrator, "DOTENV_PATH", tmp_path / ".env")
    seen = []

    class Recording:
        def __init__(self, base_url, token=None):
            self.token = None

        def post(self, path, body=None):
            seen.append((path, body))
            return 200, {"access_token": "tok-3"}

    monkeypatch.setattr(orchestrator, "Platform", Recording)
    monkeypatch.setattr("builtins.input", lambda: "")

    orchestrator._bootstrap_account(pause=True)
    regs = [b for p, b in seen if p == "/api/auth/register"]
    assert regs, "根本没调注册"
    assert re.match(r"^[A-Za-z0-9_]+$", regs[0]["username"]), regs[0]["username"]


def test_password_defaults_to_the_env_value_and_env_wins(tmp_path, monkeypatch):
    """用户要登进平台检查自举账号，所以口令固定、且能从 .env / 环境变量喂进来。"""
    from gimbal_bootstrap import orchestrator

    monkeypatch.setattr(orchestrator, "DOTENV_PATH", tmp_path / ".env")
    seen = []

    class Recording:
        def __init__(self, base_url, token=None):
            self.token = None

        def post(self, path, body=None):
            if path == "/api/auth/register":
                seen.append(body["password"])
            return 200, {"access_token": "tok-5"}

    monkeypatch.setattr(orchestrator, "Platform", Recording)
    monkeypatch.setattr("builtins.input", lambda: "")

    monkeypatch.setenv("GIMBAL_SB_PASSWORD", "Env-Ovr-9876")
    orchestrator._bootstrap_account(pause=True)
    assert seen == ["Env-Ovr-9876"], seen


def test_password_comes_from_local_env_file_not_source(tmp_path, monkeypatch):
    """固定口令要能登进平台检查，但不该躺在被跟踪的源码里。真值放 gitignore
    掉的 .env；进程环境变量仍然优先。"""
    from gimbal_bootstrap import orchestrator

    monkeypatch.delenv("GIMBAL_SB_PASSWORD", raising=False)
    monkeypatch.setattr(orchestrator, "DOTENV_PATH", tmp_path / ".env")
    (tmp_path / ".env").write_text("GIMBAL_SB_PASSWORD=from-dotenv-77\n", encoding="utf-8")

    assert orchestrator._resolve_password() == "from-dotenv-77"

    monkeypatch.setenv("GIMBAL_SB_PASSWORD", "from-process-88")
    assert orchestrator._resolve_password() == "from-process-88"


def test_fresh_username_is_written_back_to_the_dotenv_file(tmp_path, monkeypatch):
    """注册完把账号名写回 .env —— 下次重跑直接复用，不用每次手工 export。
    否则提权好的账号名只活在一次终端的回显里。"""
    from gimbal_bootstrap import orchestrator

    dotenv = tmp_path / ".env"
    dotenv.write_text("GIMBAL_SB_PASSWORD=Pw-12345678\n", encoding="utf-8")
    monkeypatch.delenv("GIMBAL_SB_USERNAME", raising=False)
    monkeypatch.delenv("GIMBAL_SB_PASSWORD", raising=False)
    monkeypatch.setattr(orchestrator, "DOTENV_PATH", dotenv)

    seen = []

    class Recording:
        def __init__(self, base_url, token=None):
            self.token = None

        def post(self, path, body=None):
            seen.append((path, body))
            return 200, {"access_token": "tok-9"}

    monkeypatch.setattr(orchestrator, "Platform", Recording)
    monkeypatch.setattr("builtins.input", lambda: "")

    _client_, username, _pw = orchestrator._bootstrap_account(pause=False)
    text = dotenv.read_text(encoding="utf-8")
    assert f"GIMBAL_SB_USERNAME={username}" in text, text
    # 口令行不能被冲掉，也不能重复追加
    assert text.count("GIMBAL_SB_PASSWORD=") == 1, text
    assert "tok-9" not in text


def test_dotenv_writeback_keeps_a_manually_edited_password(tmp_path, monkeypatch):
    from gimbal_bootstrap import orchestrator

    dotenv = tmp_path / ".env"
    dotenv.write_text("# 注释行\nGIMBAL_SB_PASSWORD=Pw-12345678\nOTHER=1\n", encoding="utf-8")
    monkeypatch.delenv("GIMBAL_SB_USERNAME", raising=False)
    monkeypatch.delenv("GIMBAL_SB_PASSWORD", raising=False)
    monkeypatch.setattr(orchestrator, "DOTENV_PATH", dotenv)

    class Recording:
        def __init__(self, base_url, token=None):
            self.token = None

        def post(self, path, body=None):
            return 200, {"access_token": "tok-9"}

    monkeypatch.setattr(orchestrator, "Platform", Recording)
    monkeypatch.setattr("builtins.input", lambda: "")

    _c, username, _pw = orchestrator._bootstrap_account(pause=False)
    text = dotenv.read_text(encoding="utf-8")
    assert "# 注释行" in text and "OTHER=1" in text, text
    assert "GIMBAL_SB_PASSWORD=Pw-12345678" in text, text
    assert f"GIMBAL_SB_USERNAME={username}" in text, text


def test_writeback_failure_does_not_lose_the_run(tmp_path, monkeypatch):
    """.env 只读/写不了都不该让注册好的账号白注册 —— 提示一下，照常返回。"""
    from gimbal_bootstrap import orchestrator

    monkeypatch.delenv("GIMBAL_SB_USERNAME", raising=False)
    monkeypatch.setenv("GIMBAL_SB_PASSWORD", "Pw-12345678")

    class Recording:
        def __init__(self, base_url, token=None):
            self.token = token

        def post(self, path, body=None):
            return 200, {"access_token": "tok-9"}

    def boom(username):
        raise OSError("read-only file system")

    monkeypatch.setattr(orchestrator, "Platform", Recording)
    monkeypatch.setattr("builtins.input", lambda: "")
    monkeypatch.setattr(orchestrator, "_remember_username", boom)

    client, username, _pw = orchestrator._bootstrap_account(pause=False)
    assert client.token == "tok-9"
    assert username.startswith("sb_")


def test_username_written_to_dotenv_is_picked_up_on_the_next_run(tmp_path, monkeypatch):
    """写回 .env 就要读得回来，否则「下次自动复用」是假的。"""
    from gimbal_bootstrap import orchestrator

    dotenv = tmp_path / ".env"
    dotenv.write_text(
        "GIMBAL_SB_PASSWORD=Pw-12345678\nGIMBAL_SB_USERNAME=sb_prev\n", encoding="utf-8"
    )
    monkeypatch.delenv("GIMBAL_SB_USERNAME", raising=False)
    monkeypatch.delenv("GIMBAL_SB_PASSWORD", raising=False)
    monkeypatch.setattr(orchestrator, "DOTENV_PATH", dotenv)

    seen = []

    class Recording:
        def __init__(self, base_url, token=None):
            self.token = token

        def post(self, path, body=None):
            seen.append(path)
            return 200, {"access_token": "tok-1"}

    monkeypatch.setattr(orchestrator, "Platform", Recording)
    monkeypatch.setattr("builtins.input", _never_pause)

    _client, username, _pw = orchestrator._bootstrap_account(pause=True)
    assert username == "sb_prev", username
    assert "/api/auth/register" not in seen, seen


def _run_main(monkeypatch, tmp_path, *, users=(), auths=()):
    """把 main() 架在假平台上跑一遍，返回记录了全部调用的 client。"""
    import sys

    from gimbal_bootstrap import orchestrator

    cases_dir = tmp_path / "cases"
    cases_dir.mkdir()
    (cases_dir / "a.yaml").write_text(
        "cases:\n"
        "  - id: T2\n    name: 注册\n    steps:\n"
        "      - {method: POST, path: /api/auth/register, auth: false,\n"
        "         endpoint: platform.auth.post_register,\n"
        "         asserts: [{target: '$.call.response.status', operator: eq, expected: 201}]}\n"
        "  - id: T3\n    name: 登录\n    steps:\n"
        "      - {method: POST, path: /api/auth/login, auth: false,\n"
        "         endpoint: platform.auth.post_login,\n"
        "         asserts: [{target: '$.call.response.status', operator: eq, expected: 200}]}\n",
        encoding="utf-8",
    )

    # main 自己生成一次性用户名（uuid），钉死它，否则断言无从下手。
    class _FixedUUID:
        hex = "deadbeef12345678"

    monkeypatch.setattr(orchestrator.uuid, "uuid4", lambda: _FixedUUID())

    class _P(FakePlatform):
        def __init__(self, base_url, token=None):
            super().__init__({
                "/api/auth/login": (200, {"access_token": "tok-live"}),
                "/api/auths": (200, {"items": list(auths)}),
                "/api/scenarios": (201, {"scenarioId": "sc-x"}),
                "/api/runs": (201, {"executionId": 42}),
                "/api/executions/42": (200, {"status": "done", "totalRuns": 1}),
                "/api/executions/42/rows": (200, {"items": [
                    {"caseDir": "case-000-r0-n0", "status": "done"}]}),
                "/api/users": (200, {"items": list(users)}),
            })
            self.token = token

    client = _P("http://x")
    monkeypatch.setattr(orchestrator, "Platform", lambda *a, **k: client)
    monkeypatch.setattr(orchestrator, "_resolve_env",
                        lambda k: {"GIMBAL_SB_USERNAME": "sb_u",
                                   "GIMBAL_SB_PASSWORD": "Pw-1234"}.get(k, ""))
    monkeypatch.setattr(sys, "argv", ["orchestrator", "--cases", str(cases_dir), "--no-pause"])
    return client


def test_keep_leaves_the_scenario_in_the_platform_for_a_person_to_read():
    """默认跑完就清（不往平台里堆垃圾），但要能留下给人看。

    用例是在平台上建出来的真场景，不留的话人登进平台只能看到一片空 ——
    想核对「编排器到底往平台写了什么」就没有窗口了。
    """
    client = _client()
    run_case(_case(), client, "sb_u", run_token="tk1", keep=True)
    assert not [p for m, p in client.calls if m == "DELETE"], client.calls


def test_cleanup_is_the_default():
    client = _client()
    run_case(_case(), client, "sb_u", run_token="tk1")
    assert [p for m, p in client.calls if m == "DELETE"] == ["/api/scenarios/sc-x"]


def test_a_case_does_not_retire_the_throwaway_that_later_cases_still_need():
    """一次性账号是**按轮次**的，不是按用例的。

    黄金链路里 T2 注册它、T3 拿同一个用户名口令去登录。之前 run_case 的
    finally 每条用例收工就把它删了 —— 账号在 T2 结束时就消失了，T3 的登录
    必然 401，而引擎给的 error 是 None（只说"失败"，不说是 401）。
    """
    client = _client()
    client.responses["/api/users"] = (200, {"items": [
        {"id": "u-x", "username": "sb_t2throw"}]})
    _run(client, new_username="sb_t2throw", new_password="Throw-9911")
    _run(client, new_username="sb_t2throw", new_password="Throw-9911")
    assert not [p for m, p in client.calls if m == "DELETE" and p.startswith("/api/users")]


def test_throwaway_is_retired_once_after_every_case_has_run(monkeypatch, tmp_path):
    """用完还是要删的 —— 但只删一次，且在**所有**用例跑完之后。

    不删的话每次重跑都往平台里堆一个死账号，而且它在 execution_snapshots
    里还留着一份明文口令。
    """
    from gimbal_bootstrap import orchestrator

    client = _run_main(
        monkeypatch, tmp_path,
        users=[{"id": "u-boot", "username": "sb_u"},   # 自举账号，绝不能删
               {"id": "u-x", "username": "sb_deadbeef"}],   # main 取 hex[:8]
    )

    assert orchestrator.main() == 0, "两条用例都应通过"

    user_deletes = [i for i, (m, p) in enumerate(client.calls)
                    if m == "DELETE" and p == "/api/users/u-x"]
    assert len(user_deletes) == 1, f"应只删一次，实际 {user_deletes}"
    last_dispatch = max(i for i, (m, p) in enumerate(client.calls) if p == "/api/runs")
    assert user_deletes[0] > last_dispatch, "账号必须在所有用例跑完之后才删"
    assert not [p for m, p in client.calls
                if m == "DELETE" and p.endswith("u-boot")], "自举账号被删了"


def test_bootstrap_credential_is_deleted_after_the_run(monkeypatch, tmp_path):
    """凭证池里 `sb` 那条存的是**管理员口令**，跑完必须删。

    常驻等于把 admin 明文长期搁在平台数据库里，而那条凭证没有 TTL。跑之前
    要它存在（场景头写的是 `${auth.sb.token}`，池里没这条 alias 解析不出来，
    引擎直接 gimbal_rejected），跑完就没必要留着了。
    """
    from gimbal_bootstrap import orchestrator

    client = _run_main(
        monkeypatch, tmp_path,
        auths=[{"id": "a-1", "alias": "sb"}],
    )
    assert orchestrator.main() == 0

    deletes = [i for i, (m, p) in enumerate(client.calls)
               if m == "DELETE" and p == "/api/auths/a-1"]
    assert len(deletes) == 1, f"凭证应被删一次，实际 {deletes}"
    last_dispatch = max(i for i, (m, p) in enumerate(client.calls) if p == "/api/runs")
    assert deletes[0] > last_dispatch, "凭证必须在所有用例跑完之后才删"


def test_bootstrap_account_is_never_deleted_even_if_it_looks_like_a_case_account():
    client = _client()
    client.responses["/api/users"] = (200, {"items": [
        {"id": "u-boot", "username": "sb_u"}]})
    run_case(_case(), client, "sb_u", run_token="tk1",
             new_username="sb_u", new_password="Throw-9911")
    assert not [p for m, p in client.calls if m == "DELETE" and p.startswith("/api/users")]


def test_throwaway_password_reaches_the_scenario_body():
    client = _client()
    case = {"id": "T2", "name": "注册", "steps": [
        {"method": "POST", "path": "/api/auth/register", "auth": False,
         "endpoint": "platform.auth.post_register",
         "body": {"username": "${sb.new_username}", "password": "${sb.new_password}"},
         "asserts": [{"target": "$.call.response.status", "operator": "eq",
                      "expected": 201}]}]}
    run_case(case, client, "sb_u", run_token="tk1",
             new_username="sb_t2throw", new_password="Throw-9911")
    body = next(b for m, p, b in client.writes if p == "/api/scenarios")
    rendered = body["definition"]["steps"][0]["request"]["body"]
    assert rendered["password"] == "Throw-9911", rendered


def test_a_run_that_never_reached_done_counts_as_a_failure():
    """回归：运行状态 failed 但一个断言都没失败 —— 这种必须算失败。

    之前屏幕打 `[FAIL]`、汇总说「0 failed」、退出码 0。接到 CI 里就是
    满屏红字配一个绿灯。"""
    from gimbal_bootstrap.orchestrator import _is_failure

    result = {"id": "T7", "passed": 1, "failed": 0, "error": None,
              "status": "failed", "ok": False, "failures": []}
    assert _is_failure(result) is True


def test_a_clean_run_is_not_a_failure():
    from gimbal_bootstrap.orchestrator import _is_failure

    assert _is_failure({"passed": 1, "failed": 0, "error": None,
                        "status": "done", "ok": True}) is False
    assert _is_failure({"passed": 0, "failed": 0, "error": None,
                        "status": "done", "ok": True, }) is False


def test_no_case_file_references_the_admin_password_placeholder():
    """兜底：`${sb.password}` 这个占位符已经不存在了，任何用例文件再用它
    都会渲染成空串 —— register 会因为「口令太弱」400，而不是让这条用例
    静悄悄失去它要验的东西。"""
    from pathlib import Path

    cases_dir = Path(__file__).resolve().parents[1] / "cases"
    offenders = [p.name for p in cases_dir.glob("*.yaml")
                 if "${sb.password}" in p.read_text(encoding="utf-8")]
    assert offenders == [], offenders


def test_no_case_dispatches_a_run_of_itself():
    """场景里 POST /api/runs 就是拿自己投自己：每跑一次派生一次新运行，
    无限递归。投递是编排器的活，用例里不能出现。"""
    from pathlib import Path

    from gimbal_bootstrap.orchestrator import load_cases

    cases_dir = Path(__file__).resolve().parents[1] / "cases"
    offenders = [
        f"{c['id']} {s['method']} {s['path']}"
        for p in sorted(cases_dir.glob("*.yaml"))
        for c in load_cases(p)
        for s in c["steps"]
        if s["method"] != "GET" and s["path"].rstrip("/") == "/api/runs"
    ]
    assert offenders == [], offenders


def test_every_case_hits_a_route_the_platform_actually_declares():
    """用例里手写的 path 必须真实存在于契约里。

    漂移门验的是「生成的契约 vs 平台」，验不到「用例的 path vs 契约」——
    中间这层是空的，于是 T7 打 `GET /api/runs` 一直到实跑才暴露（契约里
    /api/runs 只有 POST，405）。实跑一次要建场景、投递、等引擎跑完；契约
    就在本地，静态就能拦。

    路径参数按**段数**比：契约写 `{scenario_id}`、用例写 `${sb.scenario_id}`，
    都归一成 `{}`。参数名写错拦不住（那会 422，不是 404），但路由不存在
    拦得住 —— 那才是这类手写最容易犯的错。
    """
    import re
    from pathlib import Path

    from gimbal_plate.systems.platform.endpoint import ALL_ENDPOINTS as ALL_PLATFORM_ENDPOINTS

    from gimbal_bootstrap.orchestrator import load_cases

    def _shape(path: str) -> str:
        # 先吃 ${...}，否则 `$\{...\}` 会留下一个孤零零的 $
        path = re.sub(r"\$\{[^}]+\}", "{}", path)
        return re.sub(r"\{[^}]+\}", "{}", path)

    declared = {(ep.api.method.upper(), _shape(ep.api.path))
                for ep in ALL_PLATFORM_ENDPOINTS}

    cases_dir = Path(__file__).resolve().parents[1] / "cases"
    missing = [
        f"{c['id']}  {s['method'].upper()} {_shape(s['path'])}"
        for p in sorted(cases_dir.glob("*.yaml"))
        for c in load_cases(p)
        for s in c["steps"]
        if (s["method"].upper(), _shape(s["path"])) not in declared
    ]
    assert missing == [], "用例打了契约里没有的路由：\n" + "\n".join(missing)


def test_username_is_only_remembered_after_the_login_works(tmp_path, monkeypatch):
    """回归：写回 .env 必须发生在登录成功之后。

    顺序反了的话，register 成功但 login 401 时账号名照样进了 .env，之后
    每次重跑都走「复用已有账号」分支，永远卡在这个登不上的账号上。"""
    from gimbal_bootstrap import orchestrator

    dotenv = tmp_path / ".env"
    dotenv.write_text("GIMBAL_SB_PASSWORD=Pw-12345678\n", encoding="utf-8")
    monkeypatch.delenv("GIMBAL_SB_USERNAME", raising=False)
    monkeypatch.delenv("GIMBAL_SB_PASSWORD", raising=False)
    monkeypatch.setattr(orchestrator, "DOTENV_PATH", dotenv)

    class RegisterOnly:
        """register 收下了，login 拒绝。"""
        def __init__(self, base_url, token=None):
            self.token = token

        def post(self, path, body=None):
            if path == "/api/auth/login":
                raise PlatformError(401, {"detail": {"code": 4004}})
            return 201, {"access_token": "tok-9"}

    monkeypatch.setattr(orchestrator, "Platform", RegisterOnly)

    with pytest.raises(PlatformError):
        orchestrator._bootstrap_account(pause=False)

    assert "GIMBAL_SB_USERNAME" not in dotenv.read_text(encoding="utf-8"), \
        "登录都没成，账号名不该被写进 .env"


def test_concurrent_first_creation_409_is_absorbed_not_raised():
    """两个并发跑共用一个自举账号 → 抢着建同一条 alias → 一个吃 409
    （AuthCredential 对 (owner_id, alias) 有唯一约束）。

    函数叫 `_ensure_`，就该是幂等的：第二个调用者不能死在这儿，更不能把
    整个 run 带走 —— 一条栈追踪，用户看不出是两个终端同时跑。"""
    from gimbal_bootstrap.orchestrator import _ensure_credential

    class Racing(FakePlatform):
        def post(self, path, body=None):
            if path == "/api/auths":
                self.calls.append(("POST", path))
                self.writes.append(("POST", path, body))
                raise PlatformError(409, {"detail": "alias 已存在"})
            return FakePlatform.post(self, path, body)

        def get(self, path):
            if path == "/api/auths" and ("POST", "/api/auths") in self.calls:
                return 200, {"items": [{"id": 7, "alias": "sb"}]}
            return FakePlatform.get(self, path)

    client = Racing()
    _ensure_credential(client, "sb_abc", "Pw-12345678")
    assert [p for m, p, b in client.writes if m == "PATCH"] == ["/api/auths/7"], client.writes


def test_missing_password_fails_loudly_instead_of_guessing(tmp_path, monkeypatch):
    from gimbal_bootstrap import orchestrator

    monkeypatch.delenv("GIMBAL_SB_PASSWORD", raising=False)
    monkeypatch.setattr(orchestrator, "DOTENV_PATH", tmp_path / ".env")
    with pytest.raises(SystemExit):
        orchestrator._resolve_password()


def _never_pause():
    raise AssertionError("复用已有账号时不该有人工暂停")
