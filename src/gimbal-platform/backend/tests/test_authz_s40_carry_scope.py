"""authz M2a S4:carry 作用域分层(公共项目层 < 项目层 ∨ 个人层)+
${slot.X.field} 派发前替换 + 读写三面。

存量兼容(公共层唯一行、无身份上下文)由既有 carry/import 测试守着;
本文件钉新行为:tier 覆盖、项目区不吃个人层、槽位账号字段替换、
API 分权。
"""
from __future__ import annotations

import sqlalchemy as sa

from app.core import db as db_module
from app.models.project import Project, ProjectMember
from app.models.service_alias import ServiceAlias
from app.services import carry_store
from .test_scenario_composer_plate_integration import (  # noqa: F401
    PlateMock, plate_mock)
from app.services.carry_injection import build_carry_context

from .helpers import make_draft as _draft, register_and_login, role_headers

_STEP = {"kind": "step",
         "call": {"service": "fin-service", "method": "GET", "path": "/x"},
         "request": {"kind": "request", "body": {}}, "strategy": []}


async def _uid(username: str) -> int:
    async with db_module.SessionLocal() as s:
        return (await s.execute(sa.text(
            "SELECT id FROM users WHERE username = :u"),
            {"u": username})).scalar()


async def _pub_id() -> int:
    async with db_module.SessionLocal() as s:
        return (await carry_store.public_scope(s))[1]


# ── ① tier 序 ──────────────────────────────────────────────────────

async def test_tiers_public_then_personal(client, fresh_db):
    await register_and_login(client, "s40a", "pw123456")
    uid = await _uid("s40a")
    async with db_module.SessionLocal() as s:
        s.add(ServiceAlias(alias_name="fin-service", base_service="fin-service",
                           kind="external"))
        s.add(ServiceAlias(alias_name="fin-alias", base_service="fin-service",
                           kind="external"))
        await s.flush()
        pub = await carry_store.public_scope(s)
        await carry_store.put_bindings(
            s, "fin-service", {"$.a": "pub"}, updated_by_id=None,
            updated_by_name="t", scope=pub)
        await carry_store.put_bindings(
            s, "fin-service", {"$.a": "mine", "$.b": "mine"},
            updated_by_id=None, updated_by_name="t", scope=("user", uid))
        await s.commit()

    definition = {"steps": [_STEP]}
    # 私有区(无项目):公共层 < 个人层(字段级覆盖)
    async with db_module.SessionLocal() as s:
        ctx = await build_carry_context(s, definition, user_id=uid)
    assert ctx.service_bindings["fin-service"] == {
        "$.a": "mine", "$.b": "mine"}
    # 无身份:只吃公共层(旧行为)
    async with db_module.SessionLocal() as s:
        ctx = await build_carry_context(s, definition)
    assert ctx.service_bindings["fin-service"] == {"$.a": "pub"}


async def test_tiers_project_zone_ignores_user_layer(client, fresh_db):
    await register_and_login(client, "s40b", "pw123456")
    uid = await _uid("s40b")
    async with db_module.SessionLocal() as s:
        s.add(ServiceAlias(alias_name="fin-service", base_service="fin-service",
                           kind="external"))
        s.add(ServiceAlias(alias_name="fin-alias", base_service="fin-service",
                           kind="external"))
        await s.flush()
        pub = await carry_store.public_scope(s)
        proj = Project(name="s40-proj")
        s.add(proj)
        await s.flush()
        s.add(ProjectMember(project_id=proj.id, user_id=uid, role="member"))
        await carry_store.put_bindings(
            s, "fin-service", {"$.a": "pub"}, updated_by_id=None,
            updated_by_name="t", scope=pub)
        await carry_store.put_bindings(
            s, "fin-service", {"$.a": "proj"}, updated_by_id=None,
            updated_by_name="t", scope=("project", proj.id))
        await carry_store.put_bindings(
            s, "fin-service", {"$.a": "mine"}, updated_by_id=None,
            updated_by_name="t", scope=("user", uid))
        # 层内别名键稀疏覆盖:项目层 fin-alias 只覆盖 $.a
        await carry_store.put_bindings(
            s, "fin-alias", {"$.a": "alias-ovr"}, updated_by_id=None,
            updated_by_name="t", scope=("project", proj.id))
        await s.commit()
        pid = proj.id

    definition = {"steps": [_STEP]}
    # 项目区:公共层 < 项目层;**不吃个人层**(区模型收敛裁定)
    async with db_module.SessionLocal() as s:
        ctx = await build_carry_context(s, definition, project_id=pid)
    assert ctx.service_bindings["fin-service"] == {"$.a": "proj"}
    # 层内别名键 > base 服务键(tier 内键层级不动)
    step_alias = {**_STEP, "call": {**_STEP["call"], "service": "fin-alias"}}
    async with db_module.SessionLocal() as s:
        ctx = await build_carry_context(
            s, {"steps": [step_alias]}, project_id=pid)
    assert ctx.service_bindings["fin-alias"]["$.a"] == "alias-ovr"


# ── ② ${slot.X.field} 派发前替换 ──────────────────────────────────

async def test_slot_ref_substitution(client, plate_mock, monkeypatch):
    """模板字面值里的 ${slot.X.Y} → 账号字段;未命中原样保留
    (fail-visible);carry 注入值同通道(carry 值在 run 副本里替换)。"""
    plate_mock.behaviour = "echo"
    h = await register_and_login(client, "s40slot", "pw123456")
    uid = await _uid("s40slot")
    async with db_module.SessionLocal() as s:
        from app.core.security import fernet_encrypt
        from app.models.auth_session import AuthSession
        s.add(AuthSession(
            owner_id=uid, alias="qa9", url="http://auth",
            username_enc=fernet_encrypt("u"),
            password_enc=fernet_encrypt("p"),
            slot="qa9", is_default=True,
            account_fields={"orgNo": "1001", "opId": "op-7"}))
        pub = await carry_store.public_scope(s)
        # carry 值本身带 ${slot...}(字段不在锚点面 → 注入不发生,
        # 但若发生也走同一替换;字面值面用 steps 覆盖)
        await carry_store.put_bindings(
            s, "fin-service", {"$.token": "org-${slot.qa9.orgNo}"},
            updated_by_id=None, updated_by_name="t", scope=pub)
        await s.commit()

    from .helpers import wait_until as _wait
    from .test_run_m1_capabilities import _patch_launch_capture, _run_payload

    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)
    draft = _draft("sc-s40-slot", steps=[{
        **_STEP,
        "request": {"kind": "request", "body": {
            "op": "${slot.qa9.opId}", "no": "${slot.ghost.f}"}}}])
    r = await client.post("/api/scenarios", headers=h, json=draft)
    assert r.status_code in (200, 201), r.text
    r = await client.post("/api/runs", headers=h, json=_run_payload(
        scenarioId="sc-s40-slot", dataSetIds=[],
        serviceBindings={"fin-service": {"authAlias": "qa9"}}))
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 1)
    assert "qa9" in cases[0]["config"]["users"]   # 槽位凭证照常注入
    b = cases[0]["steps"][0]["request"]["body"]
    assert b["op"] == "op-7"                       # 命中 → 字段值
    assert b["no"] == "${slot.ghost.f}"            # 未命中 → 原样保留


# ── ③ API 三面 ─────────────────────────────────────────────────────

async def test_api_scope_read_filter_and_write_gates(client):
    adm = await role_headers(client, "s40adm", role="admin")
    usr = await role_headers(client, "s40usr", role="user")
    uid = await _uid("s40usr")
    async with db_module.SessionLocal() as s:
        proj = Project(name="s40-api-proj")
        s.add(proj)
        await s.flush()
        s.add(ProjectMember(project_id=proj.id, user_id=uid, role="member"))
        await s.commit()
        pid = proj.id

    # global 写 = Admin+(普通用户 403)
    r = await client.put("/api/carry/bindings/fin-service", headers=usr,
                         params={"scope": "global"},
                         json={"bindings": {"$.a": "x"}})
    assert r.status_code == 403, r.text
    r = await client.put("/api/carry/bindings/fin-service", headers=adm,
                         params={"scope": "global"},
                         json={"bindings": {"$.a": "pub"}})
    assert r.status_code == 200, r.text
    # user 层:普通用户可写自己的层
    r = await client.put("/api/carry/bindings/fin-service", headers=usr,
                         params={"scope": "user"},
                         json={"bindings": {"$.a": "mine"}})
    assert r.status_code == 200, r.text
    # project 层:普通成员 403;缺 projectId 422;项目不存在 404;
    # Admin+(ops.write)可写
    r = await client.put("/api/carry/bindings/fin-service", headers=usr,
                         params={"scope": "project"},
                         json={"bindings": {"$.a": "p"}})
    assert r.status_code == 422, r.text
    r = await client.put("/api/carry/bindings/fin-service", headers=usr,
                         params={"scope": "project", "projectId": pid},
                         json={"bindings": {"$.a": "p"}})
    assert r.status_code == 403, r.text
    r = await client.put("/api/carry/bindings/fin-service", headers=usr,
                         params={"scope": "project", "projectId": 999},
                         json={"bindings": {}})
    assert r.status_code == 404, r.text
    r = await client.put("/api/carry/bindings/fin-service", headers=adm,
                         params={"scope": "project", "projectId": pid},
                         json={"bindings": {"$.a": "proj"}})
    assert r.status_code == 200, r.text

    # 列表读:可见层并集(公共 + 我所在项目 + 我的个人层)+ 层标签
    r = await client.get("/api/carry/bindings", headers=usr)
    assert r.status_code == 200, r.text
    out = r.json()
    pub_id = await _pub_id()
    scopes = {(row["scope"], row["scopeId"]) for row in out["rows"]}
    assert scopes == {("project", pub_id), ("project", pid), ("user", uid)}
    # flat 合并视图:个人层覆盖公共层同键(运行时 tier 同序)
    assert out["bindings"]["fin-service"]["$.a"] == "mine"
    # 单服务读按层:project 层读回
    r = await client.get("/api/carry/bindings/fin-service", headers=usr,
                         params={"scope": "project", "projectId": pid})
    assert r.json()["bindings"] == {"$.a": "proj"}

    # 无关用户看不到 s40usr 的个人层与该项目层
    other = await role_headers(client, "s40oth", role="user")
    r = await client.get("/api/carry/bindings", headers=other)
    scopes2 = {(row["scope"], row["scopeId"]) for row in r.json()["rows"]}
    # 无个人行/非成员:只见公共层(rows 只含有行的层)
    assert scopes2 == {("project", pub_id)}
