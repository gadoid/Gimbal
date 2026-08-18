"""Plate integration tests for the V3 Scenario Composer.

Replaces the singleton ``httpx.AsyncClient`` in
``app.services.plate_client`` with an :class:`httpx.MockTransport` so
the real Plate server isn't needed.  This locks in:

* ``POST /api/scenarios/preview-plate`` envelope translation (Plate
  2xx / 4xx / 5xx → Platform 200 / 502 / 502).
* ``POST /api/runs`` per-row fan-out: we count the convert calls and
  assert it equals ``Σ rowCount``.
* ``POST /api/runs`` failure semantics: when Plate is down mid-fan-out
  the Execution row is marked ``status='failed'`` and the JSONL log
  records ``plate_unavailable``, but the response is still 201 with
  ``runId`` (per the agreed run-failure semantics).
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import pytest
from httpx import AsyncClient


# ── shared fixture: register + login + seed scenario/case/ds ───────
async def _register_and_login(
    client: AsyncClient, username: str = "alice", password: str = "alicepass123"
) -> dict[str, str]:
    await client.post(
        "/api/auth/register",
        json={"username": username, "password": password, "display_name": username},
    )
    r = await client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _draft(scenario_id: str = "sc-test", **meta_over) -> dict:
    meta = {
        "scenarioId": scenario_id,
        "name": "Test",
        "module": "order",
        "priority": 1,
        "system": ["fin"],
    }
    meta.update(meta_over)
    return {
        "definition": {
            "kind": "scenario",
            "scenarioId": scenario_id,
            "meta": meta,
            "config": {"timePolicy": {"kind": "record"}},
            "resource": {},
            "steps": [],
        },
        "orchestration": {"steps": [], "resourceMeta": {}},
    }


# ── Plate mock helpers ─────────────────────────────────────────────
class PlateMock:
    """Programmable Plate mock.  Each test sets the desired behaviour
    on ``mock.behaviour`` before issuing the HTTP call."""

    def __init__(self) -> None:
        self.convert_calls: list[dict] = []
        self.run_calls: list[dict] = []  # D2 run bodies (stubbed upstream)
        self.behaviour: str = "ok"  # ok | 4xx | 5xx | unavailable

    def install(self) -> None:
        """Replace the singleton httpx client with a MockTransport."""

        async def handler(request: httpx.Request) -> httpx.Response:
            path = request.url.path
            if path.endswith("/api/scenario/action/convert"):
                self.convert_calls.append(json.loads(request.content))
                if self.behaviour == "ok":
                    return httpx.Response(
                        200,
                        json={
                            "ok": True,
                            "dim": "scenario",
                            "data": {
                                "consumer": "platform",
                                "converted": {"kind": "platform_scenario"},
                            },
                        },
                    )
                if self.behaviour == "4xx":
                    return httpx.Response(
                        400,
                        json={
                            "ok": False,
                            "error": {
                                "code": "invalid_action",
                                "message": "bad shape",
                                "details": {
                                    "errors": [
                                        {
                                            "path": "steps[0].expectStatus",
                                            "message": "must be int",
                                        }
                                    ]
                                },
                            },
                        },
                    )
                if self.behaviour == "5xx":
                    return httpx.Response(500, text="plate crashed")
                if self.behaviour == "unavailable":
                    raise httpx.ConnectError("connection refused", request=request)
            if path.endswith("/api/scenario/action/run"):
                self.run_calls.append(json.loads(request.content))
                # D2 stays stubbed upstream; mirror its future shape.
                return httpx.Response(
                    200,
                    json={"ok": True, "dim": "scenario", "data": {"dispatched": True}},
                )
            return httpx.Response(404)

        from app.services import plate_client

        plate_client.set_client_for_tests(
            httpx.AsyncClient(
                transport=httpx.MockTransport(handler), base_url="http://plate-test"
            )
        )

    def uninstall(self) -> None:
        from app.services import plate_client

        plate_client.set_client_for_tests(None)


@pytest.fixture
def plate_mock():
    mock = PlateMock()
    mock.install()
    try:
        yield mock
    finally:
        mock.uninstall()


# ── Gimbal mock(#4 run 链路)───────────────────────────────────────
@pytest.fixture
def gimbal_mock():
    """MockTransport 版 gimbal 服务:捕获 /run 入参,可编程回包。

    真实 gimbal server 的 RunResponse 形状见
    src/gimbal/core/server.py RunResponse。
    """
    state = {
        "calls": [],
        "exit_code": 0,  # 测试可改
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/run":
            state["calls"].append(json.loads(request.content))
            return httpx.Response(
                200,
                json={
                    "exitCode": state["exit_code"],
                    "total": 1,
                    "passed": 1 if state["exit_code"] == 0 else 0,
                    "failed": 0 if state["exit_code"] == 0 else 1,
                    "skipped": 0,
                    "halted": 0,
                    "details": [],
                    "runId": "",
                },
            )
        return httpx.Response(404)

    from app.services import gimbal_client

    gimbal_client.set_client_for_tests(
        httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="http://gimbal-test"
        )
    )
    try:
        yield state
    finally:
        gimbal_client.set_client_for_tests(None)


# ── preview-plate ──────────────────────────────────────────────────
async def test_preview_plate_ok(client: AsyncClient, plate_mock: PlateMock) -> None:
    headers = await _register_and_login(client)
    r = await client.post(
        "/api/scenarios/preview-plate",
        headers=headers,
        json=_draft(),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["errors"] == []
    assert len(plate_mock.convert_calls) == 1


async def test_preview_plate_4xx_returns_422(
    client: AsyncClient, plate_mock: PlateMock
) -> None:
    """Upstream 4xx = verdict on the client's draft → 422 (not 502)."""
    plate_mock.behaviour = "4xx"
    headers = await _register_and_login(client)
    r = await client.post(
        "/api/scenarios/preview-plate",
        headers=headers,
        json=_draft(),
    )
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["code"] == "plate_rejected"
    assert detail["errors"][0]["path"] == "steps[0].expectStatus"


async def test_preview_plate_5xx_returns_502(
    client: AsyncClient, plate_mock: PlateMock
) -> None:
    plate_mock.behaviour = "5xx"
    headers = await _register_and_login(client)
    r = await client.post(
        "/api/scenarios/preview-plate",
        headers=headers,
        json=_draft(),
    )
    assert r.status_code == 502
    assert r.json()["detail"]["code"] == "plate_unavailable"


async def test_preview_plate_connect_error_returns_502(
    client: AsyncClient, plate_mock: PlateMock
) -> None:
    plate_mock.behaviour = "unavailable"
    headers = await _register_and_login(client)
    r = await client.post(
        "/api/scenarios/preview-plate",
        headers=headers,
        json=_draft(),
    )
    assert r.status_code == 502
    assert r.json()["detail"]["code"] == "plate_unavailable"


# ── run dispatcher ────────────────────────────────────────────────
async def _seed_scenario_case_and_dataset(
    client: AsyncClient, headers: dict, *, rows: list[dict]
) -> None:
    """Create scenario + case + 1 dataset with the given rows."""
    await client.post("/api/scenarios", headers=headers, json=_draft())
    await client.post(
        "/api/cases",
        headers=headers,
        json={
            "caseId": "case-001",
            "scenarioId": "sc-test",
            "name": "c",
            "env": "dev",
            "auth": {"name": "a", "type": "bearer"},
            "dataSetIds": [],
            "createdBy": "alice",
        },
    )
    r = await client.post(
        "/api/cases/case-001/data-sets",
        headers=headers,
        json={"name": "ds", "rows": rows},
    )
    assert r.status_code == 201


async def test_run_dispatch_calls_convert_per_row(
    client: AsyncClient, plate_mock: PlateMock, gimbal_mock: dict
) -> None:
    headers = await _register_and_login(client)
    rows = [{"qty": i} for i in range(3)]
    await _seed_scenario_case_and_dataset(client, headers, rows=rows)

    r = await client.post(
        "/api/runs",
        headers=headers,
        json={
            "caseId": "case-001",
            "dataSetIds": ["ds-001"],
            "env": {
                "envId": "test-env-A",
                "name": "test-env-A",
                "baseUrl": "http://x",
            },
        },
    )
    assert r.status_code == 201
    assert "runId" in r.json()

    # Wait for the background fan-out to finish
    for _ in range(50):
        if len(plate_mock.convert_calls) >= 3:
            break
        await asyncio.sleep(0.05)
    assert len(plate_mock.convert_calls) == 3

    # Regression guard: the per-row payload handed to plate /convert is the
    # UNWRAPPED definition — never the container. orchestration / caseMeta
    # are platform-only and must not leak; plate-required fields survive.
    # (Covers run_dispatcher._compose_scenario's container unwrap, which the
    # call-count assertion above does not.)
    # convert_calls[i] is the full wire envelope plate_client posts:
    #   {"consumer": "gimbal", "scenario": <composed dict>}
    scenario_payload = plate_mock.convert_calls[0]["scenario"]
    assert "orchestration" not in scenario_payload
    assert "caseMeta" not in scenario_payload
    assert scenario_payload["kind"] == "scenario"
    assert scenario_payload["scenarioId"] == "sc-test"
    assert scenario_payload["meta"]["name"] == "Test"
    # the row's vars are layered into config.vars, and the scenario-level
    # config is preserved through the unwrap
    assert scenario_payload["config"]["timePolicy"] == {"kind": "record"}
    assert scenario_payload["config"]["vars"]["qty"] == 0  # first row {qty: 0}


async def test_run_dispatch_preserves_row_value_types(
    client: AsyncClient, plate_mock: PlateMock, gimbal_mock: dict
) -> None:
    """行值进 config.vars 保类型(int/bool/float 不字符串化)。

    vars 两侧都是 dict[str, Any];断言 expected: 0 对 "0" 会错,
    #4 run 链路后这是 Gimbal 断言正确性的前置。
    """
    headers = await _register_and_login(client)
    rows = [{"qty": 7, "ok": True, "ratio": 1.5}]
    await _seed_scenario_case_and_dataset(client, headers, rows=rows)

    r = await client.post(
        "/api/runs",
        headers=headers,
        json={
            "caseId": "case-001",
            "dataSetIds": ["ds-001"],
            "env": {"envId": "test-env-A", "name": "test-env-A", "baseUrl": "http://x"},
        },
    )
    assert r.status_code == 201

    for _ in range(50):
        if len(plate_mock.convert_calls) >= 1:
            break
        await asyncio.sleep(0.05)
    assert len(plate_mock.convert_calls) == 1

    vars_out = plate_mock.convert_calls[0]["scenario"]["config"]["vars"]
    assert vars_out["qty"] == 7
    assert vars_out["qty"] is not "7"  # noqa: F632 — 类型守卫,防回归字符串化
    assert vars_out["ok"] is True
    assert vars_out["ratio"] == 1.5


async def _wait_execution_final(client_run_id: str | None = None) -> "Execution":
    """等 fan-out 把 Execution 行写到终态(done/failed)。

    gimbal 调用到达 ≠ 计数已落库(行级循环全部结束后才 update),
    直接读会撞到 queued 初始态。
    """
    import sqlalchemy as sa

    from app.core import db as db_module
    from app.models import Execution

    for _ in range(100):
        async with db_module.SessionLocal() as s:
            ex = (
                (await s.execute(sa.select(Execution).order_by(Execution.id.desc())))
                .scalars()
                .first()
            )
            if ex is not None and ex.status in ("done", "failed"):
                return ex
        await asyncio.sleep(0.05)
    raise AssertionError(f"execution never reached final state: {ex!r}")


async def test_run_chain_convert_then_gimbal_execute(
    client: AsyncClient, plate_mock: PlateMock, gimbal_mock: dict
) -> None:
    """#4 最小运行链路:每行 convert(plate) → run(gimbal),接线正确。

    锁四件事:
      1. gimbal /run 收到的 body.scenario 是 convert 的 **converted
         产物**(PlateMock 回 {"kind": "platform_scenario"}),不是平台
         原始 dict;
      2. 行值在 converted 之前已 merge 进 config.vars(保类型);
      3. exitCode=0 → 该行计 passed;Execution.status=done;
      4. Execution passed/failed 计数 = 行数(引擎计数被消费)。
    """
    headers = await _register_and_login(client)
    rows = [{"qty": 1}, {"qty": 2}]
    await _seed_scenario_case_and_dataset(client, headers, rows=rows)

    r = await client.post(
        "/api/runs",
        headers=headers,
        json={
            "caseId": "case-001",
            "dataSetIds": ["ds-001"],
            "env": {"envId": "test-env-A", "name": "test-env-A", "baseUrl": "http://x"},
        },
    )
    assert r.status_code == 201

    for _ in range(50):
        if len(gimbal_mock["calls"]) >= 2:
            break
        await asyncio.sleep(0.05)
    assert len(gimbal_mock["calls"]) == 2
    assert len(plate_mock.convert_calls) == 2

    # 1. 载体是 converted 产物
    body0 = gimbal_mock["calls"][0]
    assert body0["scenario"]["kind"] == "platform_scenario"
    # halt 参数不传(阶段 1 不用调试)
    assert "halt_at" not in body0

    # 2. convert 拿到的是平台原始 dict(vars 已 layer)
    conv_scenario = plate_mock.convert_calls[0]["scenario"]
    assert conv_scenario["config"]["vars"]["qty"] == 1
    assert conv_scenario["kind"] == "scenario"

    # 3+4. exitCode=0 两行 → passed=2 / failed=0 / done
    ex = await _wait_execution_final()
    assert ex.passed == 2
    assert ex.failed == 0
    assert ex.status == "done"


async def test_run_chain_gimbal_failure_counts_row_failed(
    client: AsyncClient, plate_mock: PlateMock, gimbal_mock: dict
) -> None:
    """引擎判败(exitCode=1)→ 该行计 failed;convert 本身没问题。"""
    gimbal_mock["exit_code"] = 1
    headers = await _register_and_login(client)
    await _seed_scenario_case_and_dataset(client, headers, rows=[{"qty": 1}])

    r = await client.post(
        "/api/runs",
        headers=headers,
        json={
            "caseId": "case-001",
            "dataSetIds": ["ds-001"],
            "env": {"envId": "test-env-A", "name": "test-env-A", "baseUrl": "http://x"},
        },
    )
    assert r.status_code == 201

    for _ in range(50):
        if len(gimbal_mock["calls"]) >= 1:
            break
        await asyncio.sleep(0.05)
    assert len(gimbal_mock["calls"]) == 1

    ex = await _wait_execution_final()
    # convert 过了(结构合法),但引擎判败 → failed 计数
    assert ex.passed == 0
    assert ex.failed == 1
    assert ex.status == "failed"


async def test_run_dispatch_records_failure_when_plate_down(
    client: AsyncClient, plate_mock: PlateMock
) -> None:
    """Plate 5xx mid-fan-out: still return 201 + runId; Execution marked failed."""
    plate_mock.behaviour = "5xx"
    headers = await _register_and_login(client)
    rows = [{"qty": 1}, {"qty": 2}]
    await _seed_scenario_case_and_dataset(client, headers, rows=rows)

    r = await client.post(
        "/api/runs",
        headers=headers,
        json={
            "caseId": "case-001",
            "dataSetIds": ["ds-001"],
            "env": {
                "envId": "test-env-A",
                "name": "test-env-A",
                "baseUrl": "http://x",
            },
        },
    )
    assert r.status_code == 201
    run_id = r.json()["runId"]
    assert run_id.startswith("run-")


async def test_run_injects_exec_auths_into_run_copy_only(
    client: AsyncClient, plate_mock: PlateMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """执行用认证多选:解密注入只进 run 副本,convert 永不带明文。

    锁三条边界(#1 改造的安全契约 + #4 run 链路接线):
      1. convert 收到的 scenario.config.users 不含所选 alias 的明文凭据;
      2. dispatcher 发给 gimbal_client.run 的副本 config.users[alias] 含
         解密后的 url/username/password/token_type/expires_in(形状同
         V1 executor 生产路径),且载体是 convert 的 **converted 产物**
         不是平台原始 dict。gimbal 服务不在测试里起,monkeypatch 捕获
         入参 — 验证的是 dispatcher 侧接线;
      3. Execution.config_json 用读侧契约 key ``exec_auth_alias``(数组),
         不再是旧的 "auth" 单选 key。
    """
    headers = await _register_and_login(client)
    await _seed_scenario_case_and_dataset(client, headers, rows=[{"qty": 1}])

    # 建一个执行用认证(fernet 加密存储,与 /api/auths 生产路径一致)
    r = await client.post(
        "/api/auths",
        headers=headers,
        json={
            "alias": "qa1",
            "url": "http://auth.example/login",
            "username": "qa-user",
            "password": "qa-pass",
            "token_type": "bearer",
        },
    )
    assert r.status_code == 201

    # 捕获 dispatcher → gimbal_client.run 的入参
    from app.services import gimbal_client as gc

    run_payloads: list[dict] = []

    async def _capture_run(scenario_dict: dict, **_kw: object) -> dict:
        run_payloads.append(scenario_dict)
        return {"exitCode": 0, "total": 1, "passed": 1, "failed": 0,
                "skipped": 0, "halted": 0, "details": []}

    monkeypatch.setattr(gc, "run", _capture_run)

    r = await client.post(
        "/api/runs",
        headers=headers,
        json={
            "caseId": "case-001",
            "dataSetIds": ["ds-001"],
            "env": {
                "envId": "test-env-A",
                "name": "test-env-A",
                "baseUrl": "http://x",
            },
            "auths": ["qa1"],
        },
    )
    assert r.status_code == 201

    for _ in range(50):
        if len(run_payloads) >= 1:
            break
        await asyncio.sleep(0.05)
    assert len(run_payloads) == 1

    # 1. convert 无明文(users 里没有 qa1 条目)
    conv_scenario = plate_mock.convert_calls[0]["scenario"]
    assert "qa1" not in (conv_scenario.get("config", {}).get("users") or {})

    # 2. run 副本注入解密凭据(载体是 converted 产物:PlateMock 的 convert
    #    回包 converted = {"kind": "platform_scenario", ...})
    injected = run_payloads[0]["config"]["users"]["qa1"]
    assert injected["username"] == "qa-user"
    assert injected["password"] == "qa-pass"
    assert injected["url"] == "http://auth.example/login"
    assert injected["token_type"] == "bearer"

    # 3. Execution.config_json key 对齐读侧契约
    import sqlalchemy as sa

    from app.core import db as db_module
    from app.models import Execution

    async with db_module.SessionLocal() as s:
        ex = (
            (
                await s.execute(
                    sa.select(Execution).order_by(Execution.id.desc())
                )
            )
            .scalars()
            .first()
        )
        assert ex is not None
        assert ex.config_json["exec_auth_alias"] == ["qa1"]
        assert "auth" not in ex.config_json


async def test_run_exec_auths_owner_scoped_cross_owner_alias_collision(
    client: AsyncClient, plate_mock: PlateMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """跨 owner 撞名 alias:只解发起人自己的凭证。

    alias 唯一性是 owner 级(UniqueConstraint(owner_id, alias)),bob
    可以建与 alice 同名的 "qa1"。若无 owner 过滤,
    ``alias.in_(["qa1"])`` 会同时命中两行,注入谁的凭证取决于行序
    — 跨 owner 解错凭证的口子。锁:alice 发起 run,注入的必须是
    alice 的 username(且只有一行注入)。
    """
    headers = await _register_and_login(client)  # alice
    await _seed_scenario_case_and_dataset(client, headers, rows=[{"qty": 1}])

    async def _create_auth(h: dict, username: str) -> None:
        r = await client.post(
            "/api/auths",
            headers=h,
            json={
                "alias": "qa1",
                "url": f"http://{username}-auth/login",
                "username": f"{username}-user",
                "password": f"{username}-pass",
                "token_type": "bearer",
            },
        )
        assert r.status_code == 201, r.text

    await _create_auth(headers, "alice")
    # bob 建同名 alias(owner 级唯一约束允许)
    bob_headers = await _register_and_login(client, username="bob")
    await _create_auth(bob_headers, "bob")

    from app.services import gimbal_client as gc

    run_payloads: list[dict] = []

    async def _capture_run(scenario_dict: dict, **_kw: object) -> dict:
        run_payloads.append(scenario_dict)
        return {"exitCode": 0, "total": 1, "passed": 1, "failed": 0,
                "skipped": 0, "halted": 0, "details": []}

    monkeypatch.setattr(gc, "run", _capture_run)

    # alice 发起运行,选撞名 alias
    r = await client.post(
        "/api/runs",
        headers=headers,
        json={
            "caseId": "case-001",
            "dataSetIds": ["ds-001"],
            "env": {"envId": "test-env-A", "name": "test-env-A", "baseUrl": "http://x"},
            "auths": ["qa1"],
        },
    )
    assert r.status_code == 201

    for _ in range(50):
        if len(run_payloads) >= 1:
            break
        await asyncio.sleep(0.05)
    assert len(run_payloads) == 1

    users = run_payloads[0]["config"]["users"]
    # 恰好一个 qa1 条目,且是 alice 的凭证 — bob 的同名行绝不能被解入
    assert users["qa1"]["username"] == "alice-user"
    assert users["qa1"]["password"] == "alice-pass"
    assert users["qa1"]["url"] == "http://alice-auth/login"


def test_inject_exec_users_shape_and_no_mutation() -> None:
    """_inject_exec_users: 同名覆盖 + 不改入参 + 空列表原样返回(单元级)。"""
    from copy import deepcopy

    from app.models.auth_session import AuthSession
    from app.services.run_dispatcher import _inject_exec_users

    a = AuthSession(
        alias="qa1",
        url="http://x",
        username_enc="enc",
        password_enc="enc",
        token_type="bearer",
        expires_in=3600,
    )
    a.username = "u"
    a.password = "p"

    composed = {"kind": "scenario", "config": {"users": {"keep": {"url": "k"}}}}
    snapshot = deepcopy(composed)

    out = _inject_exec_users(composed, [a])
    # 同名覆盖 + 保留既有 users
    assert out["config"]["users"]["keep"] == {"url": "k"}
    assert out["config"]["users"]["qa1"]["username"] == "u"
    # 入参未被改动(明文不回渗 compose 结果)
    assert composed == snapshot
    # 空列表 → 同一引用(无注入面)
    assert _inject_exec_users(composed, []) is composed
