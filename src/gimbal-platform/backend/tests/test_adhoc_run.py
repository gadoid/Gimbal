"""P3 临时调用(设计 2026-11-02)—— §十三 测试矩阵 + 拆段对拍 + §九 只读加固。

* 身份:JWT 403 adhoc_inbound_only;平台模式 403 adhoc_requires_grant;
  个人模式通过;steps 与 scenarioId 互斥 422 run_target_ambiguous;
* 结构:call.method/path、headers、config、schemeId、runOptions、未知策略、
  步数越界、release 形状 → 422 adhoc_field_not_allowed(fields 列全);
  缺 endpoint → 422 adhoc_step_invalid;入站 M1 先拒 serviceBindings;
* 别名:不存在 / external / base_service 与锚点系统不符 → adhoc_service_
  mismatch;无 base_url → adhoc_service_unresolved;
* 版本:显式 release 生效;环境版本线 → 线内最新修订;无环境 / plate 无此线
  → adhoc_version_unresolved;
* 校验:plate convert 拒绝 → 422 adhoc_invalid 带逐字段 errors;plate 不可达
  503;均不建执行行;
* 执行:单步端到端 —— kind='adhoc'、占位 id、快照为组装 payload(无
  method/path、call.user = 别名 credential_alias、无 config.services)、
  地址来自别名 base_url、凭证来自 grant 用户池、plate_pins 写入、outputs
  为 extract 结果、回调 kind=adhoc / scenarioId=null;
* 展示:重跑 409 rerun_unsupported;按场景筛选不含占位 id;
* 对拍:dispatch_run 与 dispatch_target 同请求下 fanout 实参 / config_json /
  快照逐字段相等,config_json 键集钉住;
* 只读加固:未知策略类型 → 只读检查不通过;四种已知策略不影响判定。
"""
from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa

from app.core import db as db_module
from app.core.security import fernet_encrypt
from app.models import Execution
from app.models.auth_session import AuthSession
from app.models.environment import Environment
from app.models.execution import ExecutionSnapshot
from app.models.service_alias import ServiceAlias
from app.services import run_dispatcher as rd
from app.services.gimbal_launcher import LaunchResult
from app.services.integration_runner import is_scenario_read_only
from app.services.run_dispatcher import STATUS_DONE, RunTarget

from .helpers import make_draft as _draft, wait_until as _wait
from .inbound_fixtures import (
    body_of, deliveries,
    seed_alias as _seed_alias, seed_platform_user as _seed_platform_user,
)
from .test_inbound_identity import (
    GET_STEP, _gic, _mk_credential, _mk_grant, _register, _user_id,
)
from .test_inbound_recipe_scope import _capture_fanout
from . import test_scenario_composer_plate_integration as _plate_it

PlateMock = _plate_it.PlateMock
# pytest 按对象上的 fixture 标记注册(名称仍为 plate_mock);走模块属性
# 而非 from-import,避免测试参数同名触发 pyflakes 的重定义告警。
plate_mock = _plate_it.plate_mock

EP = "settle.order.query"
SYSTEM = "settle"
SVC = "settle-sit"
CRED = "qa-cred"
BASE_URL = "https://settle.sit.local"
PLATE_FULL = {
    "binding": {"protocol": "http", "method": "GET",
                "path": "/orders/query", "timeout": 30},
    "metadata": {"query_safe": True},
    "request": {"declarations": [
        {"name": "orderNo", "path": "$.orderNo", "type": "string",
         "state": "form", "required": True}]},
}


# ── 助手 ──────────────────────────────────────────────────────────


def _step(**over) -> dict:
    st = {"endpoint": EP, "service": SVC, "body": {"orderNo": "PO1"},
          "strategy": [{"kind": "extract", "expression": "$.data.status",
                        "target": "status"}]}
    st.update(over)
    return st


def _body(steps: list | None = None, **extra) -> dict:
    return {"steps": steps if steps is not None else [_step()], **extra}


async def _personal(client, username: str) -> dict:
    """注册 username → gic 凭证 + 该用户签发的 grant → 入站个人模式头。"""
    await _register(client, username)
    uid = await _user_id(username)
    token = await _mk_credential()
    grant = await _mk_grant("agent-sys", uid)
    return _gic(token, grant)


async def _seed_target(*, base_url: str | None = BASE_URL, kind: str = "plate",
                       base_service: str = SYSTEM, credential: str | None = CRED,
                       env_lines: dict | None = None) -> None:
    """被调服务别名(默认挂一个声明 settle@2.1 的环境)。"""
    lines = {SYSTEM: "2.1"} if env_lines is None else env_lines
    async with db_module.SessionLocal() as s:
        env_id = None
        if lines:
            env = Environment(name=f"env-{uuid.uuid4().hex[:6]}", lines=lines)
            s.add(env)
            await s.flush()
            env_id = env.id
        s.add(ServiceAlias(
            alias_name=SVC, base_service=base_service, kind=kind,
            base_url=base_url, credential_alias=credential,
            environment_id=env_id))
        await s.commit()


async def _seed_user_auth(username: str, alias: str = CRED) -> None:
    uid = await _user_id(username)
    async with db_module.SessionLocal() as s:
        s.add(AuthSession(owner_id=uid, alias=alias, url="https://auth.local",
                          username_enc=fernet_encrypt(f"{alias}-user"),
                          password_enc=fernet_encrypt(f"{alias}-pass")))
        await s.commit()


def _plate_ready(plate_mock: PlateMock) -> None:
    """plate 桩:锚点 full(binding GET)+ settle 线 2.1 最新修订 #3 + echo convert。"""
    plate_mock.fulls[EP] = PLATE_FULL
    plate_mock.lines[SYSTEM] = [
        {"line": "1.0", "revisions": 1, "latest": "1.0#1"},
        {"line": "2.1", "revisions": 3, "latest": "2.1#3"}]
    plate_mock.behaviour = "echo"


def _patch_launch(monkeypatch, sink: list[dict],
                  outputs: dict | None = None) -> None:
    """gimbal_launcher.launch 打桩:捕获 case.json,回 passed(可带 extract 产物)。"""
    async def _capture(case_path, *, step_to=None, report_dir=None, cwd=None,
                       timeout=None, engine_log_path=None, on_event=None,
                       on_log=None, log_counters=None, n_runs=1, retry=0):
        case = json.loads(Path(case_path).read_text(encoding="utf-8"))
        sink.append(case)
        details = ([{"scenario_id": case.get("scenarioId"), "outputs": outputs}]
                   if outputs is not None else [])
        return LaunchResult(launch_status="ok", exit_code=0, total=1, passed=1,
                            details=details)

    from app.services import gimbal_launcher as gl
    monkeypatch.setattr(gl, "launch", _capture)


async def _executions() -> list[Execution]:
    async with db_module.SessionLocal() as s:
        return list((await s.execute(
            sa.select(Execution).order_by(Execution.id))).scalars().all())


async def _execution(ex_id: int) -> Execution:
    async with db_module.SessionLocal() as s:
        return await s.get(Execution, ex_id)


async def _snapshot(ex_id: int) -> dict:
    async with db_module.SessionLocal() as s:
        return (await s.execute(sa.select(ExecutionSnapshot.snapshot).where(
            ExecutionSnapshot.execution_id == ex_id))).scalar_one()


async def _wait_terminal(ex_id: int, timeout_s: float = 15.0) -> Execution:
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout_s
    while loop.time() < deadline:
        ex = await _execution(ex_id)
        if ex.status in ("done", "failed", "canceled"):
            return ex
        await asyncio.sleep(0.1)
    raise TimeoutError(f"execution {ex_id} not terminal")


async def _post(client, headers: dict, body: dict):
    return await client.post("/api/runs", headers=headers, json=body)


@pytest.fixture
async def ready(client, plate_mock: PlateMock) -> dict:
    """入站个人模式 + 被调别名(含环境/凭证)+ plate 桩,返回请求头。"""
    await _seed_platform_user()
    await _seed_alias()
    h = await _personal(client, "ad_user")
    await _seed_target()
    await _seed_user_auth("ad_user")
    _plate_ready(plate_mock)
    return h


# ── 身份与目标 ──────────────────────────────────────────────────


class TestIdentityAndTarget:
    async def test_jwt_403_inbound_only(self, client, plate_mock):
        h = await _register(client, "ad_jwt")
        r = await _post(client, h, _body())
        assert r.status_code == 403, r.text
        assert r.json()["detail"]["code"] == "adhoc_inbound_only"
        assert await _executions() == []

    async def test_platform_mode_403_requires_grant(self, client, plate_mock):
        await _seed_platform_user()
        await _seed_alias()
        token = await _mk_credential()
        r = await _post(client, _gic(token), _body())
        assert r.status_code == 403, r.text
        assert r.json()["detail"]["code"] == "adhoc_requires_grant"
        assert await _executions() == []

    async def test_target_ambiguous_422(self, ready, client):
        r = await _post(client, ready, {**_body(), "scenarioId": "sc-x"})
        assert r.status_code == 422, r.text
        assert r.json()["detail"]["code"] == "run_target_ambiguous"
        r = await _post(client, ready, {"clientRef": "x"})
        assert r.status_code == 422, r.text
        assert r.json()["detail"]["code"] == "run_target_ambiguous"
        assert await _executions() == []


# ── 结构(§三 白名单)───────────────────────────────────────────


class TestStructure:
    @pytest.mark.parametrize("body,fields", [
        (_body([_step(call={"method": "GET", "path": "/x"})]),
         ["steps[0].call.method", "steps[0].call.path"]),
        (_body([_step(headers={"X-A": "1"})]), ["steps[0].headers"]),
        (_body([_step(config={"services": {SVC: "https://evil"}})]),
         ["steps[0].config"]),
        (_body(schemeId="rs-001"), ["schemeId"]),
        (_body(runOptions={"step_to": 0}), ["runOptions"]),
        (_body([_step(strategy=[{"kind": "sleep", "seconds": 1}])]),
         ["steps[0].strategy[0].kind"]),
        (_body([_step() for _ in range(11)]), ["steps"]),
        (_body(release={"other": "1.0#1"}), ["release.other"]),
        (_body(release={SYSTEM: "2.1"}), [f"release.{SYSTEM}"]),
    ])
    async def test_field_not_allowed_422(self, ready, client, body, fields):
        r = await _post(client, ready, body)
        assert r.status_code == 422, r.text
        d = r.json()["detail"]
        assert d["code"] == "adhoc_field_not_allowed", d
        assert d["fields"] == fields
        assert await _executions() == []

    async def test_missing_endpoint_422_step_invalid(self, ready, client):
        st = _step()
        del st["endpoint"]
        r = await _post(client, ready, _body([st]))
        assert r.status_code == 422, r.text
        d = r.json()["detail"]
        assert d["code"] == "adhoc_step_invalid"
        assert d["fields"] == ["steps[0].endpoint"]

    async def test_path_params_shape_and_passthrough(self, ready, client,
                                                      monkeypatch):
        """评审补项:pathParams 只是 plate 路径模板占位的值 —— 形状错 422
        adhoc_step_invalid;合法时落 call.path_params(执行器据此填 {key})。"""
        r = await _post(client, ready, _body([_step(pathParams=["x"])]))
        assert r.status_code == 422, r.text
        assert r.json()["detail"]["code"] == "adhoc_step_invalid"
        assert r.json()["detail"]["fields"] == ["steps[0].pathParams"]
        _patch_launch(monkeypatch, [])
        r = await _post(client, ready, _body(
            [_step(pathParams={"orderNo": "PO1", "page": 2})]))
        assert r.status_code == 201, r.text
        snap = await _snapshot(r.json()["executionId"])
        assert snap["definition"]["steps"][0]["call"] == {
            "service": SVC, "user": CRED,
            "path_params": {"orderNo": "PO1", "page": 2}}

    async def test_inbound_recipe_rejected_by_m1_first(self, ready, client):
        """入站 M1 闸先于临时调用分支:serviceBindings 仍是 inbound_field_not_allowed。"""
        r = await _post(client, ready, _body(
            serviceBindings={SVC: {"url": "https://evil.example"}}))
        assert r.status_code == 422, r.text
        assert r.json()["detail"]["code"] == "inbound_field_not_allowed"


# ── 别名 / 地址 / 版本 ──────────────────────────────────────────


class TestAliasAndVersion:
    async def test_unknown_alias_mismatch(self, client, plate_mock):
        await _seed_platform_user()
        await _seed_alias()
        h = await _personal(client, "ad_a1")
        r = await _post(client, h, _body())
        assert r.status_code == 422, r.text
        d = r.json()["detail"]
        assert d["code"] == "adhoc_service_mismatch"
        assert d["services"] == [{"service": SVC, "reason": "unknown"}]

    async def test_external_alias_mismatch(self, client, plate_mock):
        await _seed_platform_user()
        await _seed_alias()
        h = await _personal(client, "ad_a2")
        await _seed_target(kind="external")
        r = await _post(client, h, _body())
        assert r.status_code == 422, r.text
        assert r.json()["detail"]["services"][0]["reason"] == "not_plate"

    async def test_system_mismatch(self, client, plate_mock):
        await _seed_platform_user()
        await _seed_alias()
        h = await _personal(client, "ad_a3")
        await _seed_target(base_service="pay")
        r = await _post(client, h, _body())
        assert r.status_code == 422, r.text
        o = r.json()["detail"]["services"][0]
        assert o["reason"] == "system_mismatch"
        assert o["system"] == SYSTEM and o["baseService"] == "pay"

    async def test_no_base_url_unresolved(self, client, plate_mock):
        await _seed_platform_user()
        await _seed_alias()
        h = await _personal(client, "ad_a4")
        await _seed_target(base_url=None)
        r = await _post(client, h, _body())
        assert r.status_code == 422, r.text
        d = r.json()["detail"]
        assert d["code"] == "adhoc_service_unresolved"
        assert d["services"] == [SVC]
        assert await _executions() == []

    async def test_no_environment_version_unresolved(self, client, plate_mock):
        await _seed_platform_user()
        await _seed_alias()
        h = await _personal(client, "ad_v1")
        await _seed_target(env_lines={})
        r = await _post(client, h, _body())
        assert r.status_code == 422, r.text
        d = r.json()["detail"]
        assert d["code"] == "adhoc_version_unresolved"
        assert d["systems"] == [{"system": SYSTEM, "reason": "no_line"}]

    async def test_line_not_in_plate_unresolved(self, client, plate_mock):
        await _seed_platform_user()
        await _seed_alias()
        h = await _personal(client, "ad_v2")
        await _seed_target(env_lines={SYSTEM: "7.7"})
        plate_mock.lines[SYSTEM] = [{"line": "1.0", "revisions": 1,
                                     "latest": "1.0#1"}]
        plate_mock.line_revisions[SYSTEM] = {"7.7": []}
        r = await _post(client, h, _body())
        assert r.status_code == 422, r.text
        d = r.json()["detail"]
        assert d["code"] == "adhoc_version_unresolved"
        assert d["systems"][0]["reason"] == "line_not_in_plate"

    async def test_env_line_latest_and_release_override(
            self, ready, client, monkeypatch):
        _patch_launch(monkeypatch, [])
        r = await _post(client, ready, _body())
        assert r.status_code == 201, r.text
        snap = await _snapshot(r.json()["executionId"])
        assert snap["definition"]["meta"]["plate"] == {SYSTEM: "2.1#3"}
        r = await _post(client, ready, _body(release={SYSTEM: "1.0#1"}))
        assert r.status_code == 201, r.text
        snap = await _snapshot(r.json()["executionId"])
        assert snap["definition"]["meta"]["plate"] == {SYSTEM: "1.0#1"}


# ── 派发前 convert 校验 ──────────────────────────────────────────


class TestConvertValidation:
    async def test_plate_rejects_422_invalid_no_row(self, ready, client,
                                                     plate_mock):
        plate_mock.behaviour = "4xx"
        r = await _post(client, ready, _body())
        assert r.status_code == 422, r.text
        d = r.json()["detail"]
        assert d["code"] == "adhoc_invalid"
        assert d["errors"][0]["path"] == "steps[0].expectStatus"
        assert await _executions() == []

    async def test_plate_unavailable_503(self, ready, client, plate_mock):
        plate_mock.behaviour = "unavailable"
        r = await _post(client, ready, _body())
        assert r.status_code == 503, r.text
        assert r.json()["detail"]["code"] == "plate_unavailable"
        assert await _executions() == []


# ── 执行 / 回调 / 展示 ──────────────────────────────────────────


class TestExecution:
    async def test_single_step_end_to_end(self, ready, client, monkeypatch):
        cases: list[dict] = []
        _patch_launch(monkeypatch, cases, outputs={"status": "SETTLED",
                                                   "auth_token": "secret-x"})
        r = await _post(client, ready, _body(clientRef="agent-1",
                                             callbackPath="/agent/cb"))
        assert r.status_code == 201, r.text
        run_id, ex_id = r.json()["runId"], r.json()["executionId"]
        assert r.json()["identityMode"] == "personal"

        ex = await _execution(ex_id)
        assert ex.kind == "adhoc"
        assert ex.scenario_id == f"adhoc-{run_id}"
        assert ex.scenario_name == f"临时调用 · {SVC} · {EP}"
        assert ex.caller_alias_name == "agent-sys"
        assert ex.grant_id is not None
        assert ex.client_ref == "agent-1"
        assert ex.owner_id == await _user_id("ad_user")
        assert ex.config_json["scenarioId"] == f"adhoc-{run_id}"
        assert ex.config_json["injectedAuths"] == [CRED]   # 别名默认层
        # 快照 = 组装 payload:无 method/path、call.user、空 config
        snap = await _snapshot(ex_id)
        d = snap["definition"]
        assert d["scenarioId"] == f"sc-adhoc-{run_id}"
        assert d["config"] == {}
        assert d["meta"]["plate"] == {SYSTEM: "2.1#3"}
        assert d["meta"]["system"] == [SYSTEM]
        st = d["steps"][0]
        assert st["endpoint"] == EP
        assert st["call"] == {"service": SVC, "user": CRED}
        assert st["request"] == {"kind": "request", "body": {"orderNo": "PO1"}}
        assert st["strategy"][0]["kind"] == "extract"

        ex = await _wait_terminal(ex_id)
        assert ex.status == "done", ex.config_json
        # 执行器拿到的 case.json:method 由 plate 投影、地址来自别名、凭证来自 grant 用户池
        assert len(cases) == 1
        case = cases[0]
        assert case["steps"][0]["call"]["method"] == "GET"
        assert case["steps"][0]["call"]["path"] == "/orders/query"
        assert case["steps"][0]["call"]["user"] == CRED
        assert case["config"]["services"][SVC] == BASE_URL
        assert case["config"]["users"][CRED]["username"] == f"{CRED}-user"
        assert ex.plate_pins == {SYSTEM: "2.1#3"}
        assert ex.config_json["outputs"] == {"status": "SETTLED",
                                             "auth_token": "***"}
        # 回调(与终态同事务写行):kind=adhoc、scenarioId=null、outputs=extract 结果
        rows = await deliveries()
        assert len(rows) == 1
        body = body_of(rows[0])
        assert body["event"] == "execution.finished"
        assert body["kind"] == "adhoc"
        assert body["scenarioId"] is None
        assert body["clientRef"] == "agent-1"
        assert body["status"] == "done"
        assert body["outputs"] == {"status": "SETTLED", "auth_token": "***"}
        assert rows[0].url.endswith("/agent/cb")

    async def test_rerun_409_and_scenario_filter_excludes(self, client):
        h = await _register(client, "ad_owner")
        uid = await _user_id("ad_owner")
        async with db_module.SessionLocal() as s:
            ex = Execution(scenario_id="adhoc-run-x", scenario_name="临时调用",
                           owner_id=uid, owner_name="ad_owner", status="done",
                           total_runs=1, kind="adhoc",
                           config_json={"runId": "run-x",
                                        "scenarioId": "adhoc-run-x"})
            s.add(ex)
            await s.commit()
            ex_id = ex.id
        r = await client.post(f"/api/executions/{ex_id}/rerun", headers=h)
        assert r.status_code == 409, r.text
        assert r.json()["detail"]["code"] == "rerun_unsupported"
        r = await client.get("/api/executions", headers=h,
                             params={"scenario_id": "adhoc-run-x"})
        assert r.status_code == 200, r.text
        assert all(it["id"] != ex_id for it in r.json()["items"])


# ── 拆段对拍(§六)───────────────────────────────────────────────


class TestDispatchSplitEquivalence:
    async def test_dispatch_run_equals_dispatch_target(self, client, monkeypatch):
        h = await _register(client, "ad_eq")
        uid = await _user_id("ad_eq")
        await client.post("/api/scenarios", headers=h, json=_draft(
            "sc-eq", steps=[GET_STEP]))
        cap = await _capture_fanout(monkeypatch)
        r = await client.post("/api/runs", headers=h, json={
            "scenarioId": "sc-eq", "clientRef": "a"})
        assert r.status_code == 201, r.text
        await _wait(lambda: len(cap) == 1)
        ex1 = r.json()["executionId"]

        from app.schemas.scenario_composer import RunRequest
        from app.services.scenario_store import get_row
        async with db_module.SessionLocal() as db:
            scen = await get_row(db, "sc-eq")
            resp = await rd.dispatch_target(
                db, uid, RunRequest(scenarioId="sc-eq", clientRef="a"),
                RunTarget(scenario_id=scen.scenario_id,
                          payload=scen.payload or {}, kind="scenario"))
        await _wait(lambda: len(cap) == 2)
        ex2 = resp.execution_id

        volatile = {"execution_id", "run_id"}
        a = {k: v for k, v in cap[0].items() if k not in volatile}
        b = {k: v for k, v in cap[1].items() if k not in volatile}
        assert a == b
        e1, e2 = await _execution(ex1), await _execution(ex2)
        c1 = {k: v for k, v in e1.config_json.items() if k != "runId"}
        c2 = {k: v for k, v in e2.config_json.items() if k != "runId"}
        assert c1 == c2
        assert (e1.kind, e1.scenario_id) == (e2.kind, e2.scenario_id) == (
            "scenario", "sc-eq")
        assert await _snapshot(ex1) == await _snapshot(ex2)
        # 键集与缺省值钉住(拆段不得增删配方键;counterDrift 是终态时
        # 对账标记,由 _capture_fanout 桩直接置终态引出,与派发无关)
        assert set(c1) - {"counterDrift"} == {
            "scenarioId", "dataSetIds", "dataSetSelection", "injectedAuths",
            "serviceBindings", "runOptions", "injectionEntryIds", "schemeId",
            "schemeName", "batchId", "reportDefinitionId", "chain"}
        assert c1["scenarioId"] == "sc-eq" and c1["chain"] == "legacy"
        assert c1["dataSetIds"] == [] and c1["serviceBindings"] == {}
        ds = cap[0]["datasets"]
        assert len(ds) == 1 and ds[0]["datasetId"] is None
        assert len(ds[0]["rows"]) == 1
        assert cap[0]["owner_id"] == uid and cap[0]["chain"] == "legacy"
        assert (await _wait_terminal(ex1)).status == STATUS_DONE
        assert (await _wait_terminal(ex2)).status == STATUS_DONE


# ── 只读闸策略白名单(§九)─────────────────────────────────────


class TestReadOnlyStrategyGuard:
    @staticmethod
    def _payload(strategy: list[dict]) -> dict:
        step = {"kind": "step", "call": {"protocol": "http", "service": "svc",
                                         "method": "GET", "path": "/x"},
                "request": {"kind": "request", "body": {}}, "strategy": strategy}
        return {"definition": {"meta": {"name": "ro", "plate": {}},
                               "steps": [step]}}

    async def test_unknown_strategy_fails_closed(self):
        ok, offenders = await is_scenario_read_only(self._payload(
            [{"kind": "extract", "expression": "$.a", "target": "a"},
             {"kind": "nuke", "target": "db"}]))
        assert ok is False
        assert offenders == ["步骤 0(策略 nuke 未知)"]
        ok, offenders = await is_scenario_read_only(self._payload(
            [{"kind": "extract", "expression": "$.a", "target": "a"},
             {"kind": "assign", "source": 1, "target": "b"},
             {"kind": "assertion", "operator": "eq", "target": "$.c"},
             {"kind": "sleep", "seconds": 1}]))
        assert ok is True and offenders == []
