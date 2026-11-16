"""authz M2a S7.5(ref 重做,P2-B.6):导入时内置凭证(``config.users``)
→ 身份条目。

落库仍不含明文(P2);``call.user`` 标签按条目口径落地 —— 注入键 =
条目名(无「声明槽位」):映射/新建到条目 E 的服务,其唯一未被模板引
用的标签改写为 E;模板引用的标签按同名条目注入;多标签/无条目如实回
报。落库回报「需要装载的身份条目 × 导入人装载状态」。
"""
from __future__ import annotations

from sqlalchemy import select

from app.core import db as db_module
from app.models.service_identity import ServiceIdentity
from app.models.user import User

from .conftest import seed_identity_fixture
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


async def _seed_env() -> None:
    """条目 env 必填:导入建条目/装载回报都要有默认环境。"""
    from app.models import Environment
    async with db_module.SessionLocal() as s:
        s.add(Environment(name="测试", is_default=True))
        await s.commit()


async def _seed_entry(alias: str, *, username: str | None = None,
                      owner_id: "int | None" = None) -> None:
    """四件套布景:环境 + 主档 + 账户 + 身份条目。"""
    async with db_module.SessionLocal() as s:
        await seed_identity_fixture(
            s, alias=alias, username=username or f"{alias}-acct",
            password="pw123456", service="fin-service", owner_id=owner_id)


async def test_create_rewrites_call_user_to_entry(
        client, plate_mock: PlateMock):
    """新建条目:服务唯一的内置标签改写为条目名(注入键 = 条目名);
    未用到的内置键回报 dropped;明文不落库。"""
    _mock_faces(plate_mock)
    h = await register_and_login(client, "admin0", "admin0pass123")
    await _seed_env()
    r = await client.post("/api/scenarios/import", headers=h, json={
        "bundle": _bundle_with_users(extra_users=("unused",)),
        "mappings": [{"serviceKey": "fin-service-qa", "decision": "create"}]})
    assert r.status_code == 201, r.text
    body = r.json()
    async with db_module.SessionLocal() as s:
        ident = (await s.execute(select(ServiceIdentity).where(
            ServiceIdentity.alias_name == "fin-service-qa"))).scalar_one()
        assert ident.ref_mode == "default"        # 导入建条目:ref=默认账户
        assert ident.base_service == "fin-service"
        env_id = ident.env_id
    entries = {x["entry"]: x for x in body["authEntries"]}
    # qa1 = 模板引用(${auth.qa1.token});fin-service-qa = 新建条目(改写目标)
    assert set(entries) == {"qa1", "fin-service-qa"}
    assert entries["qa1"] == {"entry": "qa1", "bound": False,
                              "fromBuiltin": True, "system": None,
                              "envId": None}
    assert entries["fin-service-qa"] == {
        "entry": "fin-service-qa", "bound": False, "fromBuiltin": True,
        "system": None, "envId": env_id}
    assert body["undeclaredUsers"] == []
    assert body["authRenames"] == [
        {"service": "fin-service-qa", "from": "maker", "to": "fin-service-qa"}]
    assert body["droppedUsers"] == ["unused"]
    defn = await _stored_definition(_SCENARIO_ID)
    assert "users" not in (defn.get("config") or {})
    assert defn["steps"][1]["call"]["user"] == "fin-service-qa"


async def test_create_multi_tag_reports_multi_user(
        client, plate_mock: PlateMock):
    """服务用到多个内置标签 → 无法收敛到单一条目,不改写、如实回报
    (reason=multi_user);条目照建,模板引用不受影响。"""
    _mock_faces(plate_mock)
    h = await register_and_login(client, "admin0", "admin0pass123")
    await _seed_env()
    b = _bundle()
    b["steps"][0]["call"]["user"] = "maker"
    b["steps"][0]["call"]["service"] = "fin-service-qa"
    b["steps"][1]["call"]["user"] = "checker"
    b["steps"][1]["call"]["service"] = "fin-service-qa"
    b["config"]["users"] = {
        "qa1": {"username": "a", "password": "b"},
        "maker": {"username": "a", "password": "b"},
        "checker": {"username": "a", "password": "b"}}
    r = await client.post("/api/scenarios/import", headers=h,
                          json={"bundle": b, "mappings": [
        {"serviceKey": "fin-service-qa", "decision": "create"}]})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["authRenames"] == []
    assert body["undeclaredUsers"] == [
        {"tag": "checker", "services": ["fin-service-qa"],
         "reason": "multi_user"},
        {"tag": "maker", "services": ["fin-service-qa"],
         "reason": "multi_user"}]
    assert {x["entry"] for x in body["authEntries"]} == {
        "qa1", "fin-service-qa"}
    defn = await _stored_definition(_SCENARIO_ID)
    assert defn["steps"][0]["call"]["user"] == "maker"
    assert defn["steps"][1]["call"]["user"] == "checker"


async def test_map_to_identity_rewrites_call_user(
        client, plate_mock: PlateMock):
    """映射到已有条目 → call.user 改写为条目名;装载状态按导入人
    条目→ref→账户判;回报附登记坐标(system/envId,深链用)。"""
    _mock_faces(plate_mock)
    h = await register_and_login(client, "admin0", "admin0pass123")
    await _seed_entry("fin-service", username="fin-acct",
                      owner_id=await _uid("admin0"))
    r = await client.post("/api/scenarios/import", headers=h, json={
        "bundle": _bundle_with_users(svc="fin-service"),
        "mappings": [{"serviceKey": "fin-service", "decision": "map"}]})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["authRenames"] == [
        {"service": "fin-service", "from": "maker", "to": "fin-service"}]
    entries = {x["entry"]: x for x in body["authEntries"]}
    assert entries["fin-service"]["bound"] is True
    assert entries["fin-service"]["fromBuiltin"] is True
    assert entries["fin-service"]["system"] == "fin-service"
    assert entries["fin-service"]["envId"] is not None
    assert body["undeclaredUsers"] == []
    defn = await _stored_definition(_SCENARIO_ID)
    assert defn["steps"][1]["call"]["user"] == "fin-service"


async def test_map_without_identity_reports_no_identity(
        client, plate_mock: PlateMock):
    """服务在目录但没登记身份条目 → 不能改写,如实回报(该步执行会报
    错);标签原样。"""
    _mock_faces(plate_mock)
    await register_and_login(client, "admin0", "admin0pass123")
    plain = await register_and_login(client, "plain75", "pw123456")
    r = await client.post("/api/scenarios/import", headers=plain, json={
        "bundle": _bundle_with_users(svc="fin-service"),
        "mappings": [{"serviceKey": "fin-service", "decision": "map"}]})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["undeclaredUsers"] == [{
        "tag": "maker", "services": ["fin-service"],
        "reason": "no_identity"}]
    assert "maker" not in {x["entry"] for x in body["authEntries"]}
    defn = await _stored_definition(_SCENARIO_ID)
    assert defn["steps"][1]["call"]["user"] == "maker"


async def test_templated_tag_not_rewritten(client, plate_mock: PlateMock):
    """标签被 ${auth.K} 模板引用 → 本就进注入清单,不改写(改写会换凭证)。"""
    _mock_faces(plate_mock)
    h = await register_and_login(client, "admin0", "admin0pass123")
    await _seed_entry("fin-service", username="fin-acct",
                      owner_id=await _uid("admin0"))
    b = _bundle()
    b["steps"][0]["call"]["user"] = "qa1"        # 同时被 ${auth.qa1.token} 引用
    r = await client.post("/api/scenarios/import", headers=h, json={
        "bundle": b,
        "mappings": [{"serviceKey": "fin-service", "decision": "map"}]})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["authRenames"] == []
    assert {"qa1", "fin-service"} <= {x["entry"] for x in body["authEntries"]}
    defn = await _stored_definition(_SCENARIO_ID)
    assert defn["steps"][0]["call"]["user"] == "qa1"


async def test_precheck_lists_builtin_users(client, plate_mock: PlateMock):
    _mock_faces(plate_mock)
    h = await register_and_login(client, "admin0", "admin0pass123")
    # 同名条目 maker + 导入人默认账户 → bound;qa1 无条目 → 未装载
    await _seed_entry("maker", owner_id=await _uid("admin0"))
    r = await client.post("/api/scenarios/import/precheck", headers=h,
                          json={"bundle": _bundle_with_users()})
    assert r.status_code == 200, r.text
    rows = {x["tag"]: x for x in r.json()["builtinUsers"]}
    assert rows["qa1"] == {"tag": "qa1", "services": [], "templated": True,
                           "bound": False}
    assert rows["maker"] == {"tag": "maker", "services": ["fin-service-qa"],
                             "templated": False, "bound": True}
