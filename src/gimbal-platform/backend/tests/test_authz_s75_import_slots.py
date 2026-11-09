"""authz M2a S7.5:导入时内置凭证(``config.users``)转槽位声明。

落库仍不含明文(P2);键不再静默丢弃 —— 新建别名缺省声明该服务唯一
的内置标签、映射到声明了别的槽位的别名时改写步骤 ``call.user``、其余
如实回报;落库结果回报「需要绑定的槽位 × 导入人绑定状态」。
"""
from __future__ import annotations

from sqlalchemy import select

from app.core import db as db_module
from app.core.security import fernet_encrypt
from app.models.auth_session import AuthSession
from app.models.service_alias import ServiceAlias
from app.models.user import User

from .helpers import register_and_login
from .test_scenario_composer_plate_integration import PlateMock, plate_mock  # noqa: F401
from .test_scenario_import_pipeline import (
    _SCENARIO_ID, _bundle, _mock_faces, _stored_definition)


def _bundle_with_users(*, svc: str = "fin-service-qa",
                       user: str = "maker", extra_users: tuple = ()) -> dict:
    """基线文件 + 第 2 步 ``call.user`` 指向内置凭证键。"""
    b = _bundle()
    b["steps"][1]["call"]["user"] = user
    b["steps"][1]["call"]["service"] = svc
    users = {user: {"username": "src-u", "password": "src-p"}}
    for k in extra_users:
        users[k] = {"username": "x", "password": "y"}
    b["config"]["users"] = {**b["config"]["users"], **users}
    return b


async def _uid(username: str) -> int:
    async with db_module.SessionLocal() as s:
        return (await s.execute(select(User.id).where(
            User.username == username))).scalar_one()


async def _bind(username: str, slot: str) -> None:
    uid = await _uid(username)
    async with db_module.SessionLocal() as s:
        s.add(AuthSession(owner_id=uid, alias=slot, slot=slot,
                          url="https://auth.local", is_default=True,
                          username_enc=fernet_encrypt("u"),
                          password_enc=fernet_encrypt("p")))
        await s.commit()


async def test_create_alias_declares_builtin_slot(client, plate_mock: PlateMock):
    """新建别名未显式给槽位 → 缺省声明该服务唯一的内置标签;未用到的
    内置键回报 dropped;明文不落库。"""
    _mock_faces(plate_mock)
    h = await register_and_login(client, "admin0", "admin0pass123")
    r = await client.post("/api/scenarios/import", headers=h, json={
        "bundle": _bundle_with_users(extra_users=("unused",)),
        "mappings": [{"serviceKey": "fin-service-qa", "decision": "create"}]})
    assert r.status_code == 201, r.text
    body = r.json()
    async with db_module.SessionLocal() as s:
        alias = (await s.execute(select(ServiceAlias).where(
            ServiceAlias.alias_name == "fin-service-qa"))).scalar_one()
        assert alias.slot == "maker"
    slots = {x["slot"]: x for x in body["slots"]}
    # qa1 = 模板引用(${auth.qa1.token});maker = 新别名声明
    assert set(slots) == {"qa1", "maker"}
    assert slots["maker"] == {"slot": "maker", "bound": False,
                              "fromBuiltin": True}
    assert body["undeclaredUsers"] == []
    assert body["slotRenames"] == []
    assert body["droppedUsers"] == ["unused"]
    defn = await _stored_definition(_SCENARIO_ID)
    assert "users" not in (defn.get("config") or {})
    assert defn["steps"][1]["call"]["user"] == "maker"


async def test_create_explicit_slot_wins(client, plate_mock: PlateMock):
    _mock_faces(plate_mock)
    h = await register_and_login(client, "admin0", "admin0pass123")
    r = await client.post("/api/scenarios/import", headers=h, json={
        "bundle": _bundle_with_users(),
        "mappings": [{"serviceKey": "fin-service-qa", "decision": "create",
                      "credentialAlias": "maker"}]})
    assert r.status_code == 201, r.text
    async with db_module.SessionLocal() as s:
        assert (await s.execute(select(ServiceAlias.slot).where(
            ServiceAlias.alias_name == "fin-service-qa"))).scalar_one() == "maker"


async def test_map_to_alias_with_other_slot_rewrites_call_user(
        client, plate_mock: PlateMock):
    """映射到已声明别的槽位的别名 → call.user 改写为本机槽位;绑定状态
    按导入人槽位绑定判。"""
    _mock_faces(plate_mock)
    async with db_module.SessionLocal() as s:
        s.add(ServiceAlias(alias_name="fin-service",
                           base_service="fin-service", slot="fin-acct"))
        await s.commit()
    h = await register_and_login(client, "admin0", "admin0pass123")
    await _bind("admin0", "fin-acct")
    r = await client.post("/api/scenarios/import", headers=h, json={
        "bundle": _bundle_with_users(svc="fin-service"),
        "mappings": [{"serviceKey": "fin-service", "decision": "map"}]})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["slotRenames"] == [
        {"service": "fin-service", "from": "maker", "to": "fin-acct"}]
    slots = {x["slot"]: x for x in body["slots"]}
    assert slots["fin-acct"] == {"slot": "fin-acct", "bound": True,
                                 "fromBuiltin": True}
    assert body["undeclaredUsers"] == []
    defn = await _stored_definition(_SCENARIO_ID)
    assert defn["steps"][1]["call"]["user"] == "fin-acct"


async def test_map_to_alias_without_slot_reports_undeclared(
        client, plate_mock: PlateMock):
    """别名未声明槽位 → 不能落地,如实回报(该步执行会报错);标签原样。"""
    _mock_faces(plate_mock)
    async with db_module.SessionLocal() as s:
        s.add(ServiceAlias(alias_name="fin-service",
                           base_service="fin-service"))
        await s.commit()
    await register_and_login(client, "admin0", "admin0pass123")
    h = await register_and_login(client, "plain75", "pw123456")
    r = await client.post("/api/scenarios/import", headers=h, json={
        "bundle": _bundle_with_users(svc="fin-service"),
        "mappings": [{"serviceKey": "fin-service", "decision": "map"}]})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["undeclaredUsers"] == [{
        "tag": "maker", "services": ["fin-service"],
        "reason": "alias_no_slot"}]
    assert "maker" not in {x["slot"] for x in body["slots"]}
    defn = await _stored_definition(_SCENARIO_ID)
    assert defn["steps"][1]["call"]["user"] == "maker"


async def test_templated_tag_not_rewritten(client, plate_mock: PlateMock):
    """标签被 ${auth.K} 模板引用 → 本就进注入清单,不改写(改写会换凭证)。"""
    _mock_faces(plate_mock)
    async with db_module.SessionLocal() as s:
        s.add(ServiceAlias(alias_name="fin-service",
                           base_service="fin-service", slot="fin-acct"))
        await s.commit()
    h = await register_and_login(client, "admin0", "admin0pass123")
    b = _bundle()
    b["steps"][0]["call"]["user"] = "qa1"        # 同时被 ${auth.qa1.token} 引用
    r = await client.post("/api/scenarios/import", headers=h, json={
        "bundle": b,
        "mappings": [{"serviceKey": "fin-service", "decision": "map"}]})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["slotRenames"] == []
    assert {"qa1", "fin-acct"} <= {x["slot"] for x in body["slots"]}
    defn = await _stored_definition(_SCENARIO_ID)
    assert defn["steps"][0]["call"]["user"] == "qa1"


async def test_precheck_lists_builtin_users(client, plate_mock: PlateMock):
    _mock_faces(plate_mock)
    h = await register_and_login(client, "admin0", "admin0pass123")
    await _bind("admin0", "maker")
    r = await client.post("/api/scenarios/import/precheck", headers=h,
                          json={"bundle": _bundle_with_users()})
    assert r.status_code == 200, r.text
    rows = {x["tag"]: x for x in r.json()["builtinUsers"]}
    assert rows["qa1"] == {"tag": "qa1", "services": [], "templated": True,
                           "bound": False}
    assert rows["maker"] == {"tag": "maker", "services": ["fin-service-qa"],
                             "templated": False, "bound": True}
