"""凭证治理 §3.3 手配落池(阶段 2;拍板 2026-11-20 方案 A)。

钉子:
* 同事务:手配随保存落 ① AuthAccount 本人池(Fernet + 掩码闸同单源)
  + ② ServiceIdentity username-ref;响应 newAuths 列新建清单
  (行为规则④);校验失败整单回滚(池无孤儿行);
* 冲突码:同名条目 409 auth_draft_alias_taken / 账户四元组 409
  auth_draft_account_exists(行为规则①:提示直接引用,不覆盖);
  未知系统 422 auth_draft_system_unknown(手配条目 base_service 须
  落主档既有服务)/ 环境 422 auth_draft_env_not_found;
* 属主闸(§3.8 拍板):update 时 user ≠ row.owner → 403
  auth_draft_owner_required(项目成员可写他人场景但不代落池);
* 决策 1 登记闸协调:enforce 态下手配名(同事务将建)按已登记放行。
"""
from __future__ import annotations

import pytest
import sqlalchemy as sa
from httpx import AsyncClient

from app.core import db as db_module
from app.core.config import settings
from app.models import Environment, Service
from app.models.auth_account import AuthAccount
from app.models.service_identity import ServiceIdentity

from .helpers import make_draft, role_headers
from .test_scenario_composer_plate_integration import PlateMock, plate_mock  # noqa: F401


async def _seed_base() -> int:
    """默认环境 + fin 系主档服务;返回 env id。"""
    async with db_module.SessionLocal() as s:
        env = (await s.execute(sa.select(Environment.id).where(
            Environment.is_default.is_(True)))).scalar_one_or_none()
        if env is None:
            s.add(Environment(name="测试", is_default=True))
            await s.flush()
            env = (await s.execute(sa.select(Environment.id).where(
                Environment.is_default.is_(True)))).scalar_one()
        if (await s.execute(sa.select(Service.id).where(
                Service.name == "fin-svc"))).scalar_one_or_none() is None:
            s.add(Service(name="fin-svc", system="fin", kind="plate"))
        await s.commit()
        return env


def _steps(auth_ref: str) -> list[dict]:
    auth_header = f"${{auth.{auth_ref}.token}}"
    return [{
        "kind": "step", "endpoint": "fin.orders.get",
        "call": {"service": "fin-svc", "method": "GET", "path": "/o",
                 "headers": {"Authorization": auth_header}},
        "request": {"kind": "request", "body": {}}, "strategy": [],
    }]


def _draft(sid: str, auth_ref: str, drafts: list[dict] | None) -> dict:
    d = make_draft(sid, steps=_steps(auth_ref))
    if drafts is not None:
        d["authDrafts"] = drafts
    return d


def _manual_cfg(name="pay-uat", *, username="u1", system="fin", env=None,
                password="secret1") -> dict:
    return {"name": name, "system": system, "envId": env,
            "username": username, "password": password,
            "accountFields": {"orgNo": "1001"}}


@pytest.mark.asyncio
async def test_manual_config_creates_pool_and_identity(
        client: AsyncClient, plate_mock):
    env = await _seed_base()
    h = await role_headers(client, "ad_own")
    r = await client.post("/api/scenarios", headers=h, json=_draft(
        "sc-ad-1", "pay-uat", [_manual_cfg(env=env)]))
    assert r.status_code in (200, 201), r.text
    assert r.json().get("newAuths") == ["pay-uat"]
    async with db_module.SessionLocal() as s:
        uid = (await s.execute(sa.text(
            "SELECT id FROM users WHERE username='ad_own'"))).scalar()
        ident = (await s.execute(sa.select(ServiceIdentity).where(
            ServiceIdentity.alias_name == "pay-uat"))).scalar_one()
        assert (ident.ref_mode, ident.ref_username,
                ident.base_service) == ("username", "u1", "fin-svc")
        acct = (await s.execute(sa.select(AuthAccount).where(
            AuthAccount.owner_id == uid))).scalar_one()
        assert (acct.system, acct.username, acct.is_default) == (
            "fin", "u1", True)
        assert acct.account_fields == {"orgNo": "1001"}
        assert acct.password_enc != "secret1"      # Fernet 落库
        # 手配清单不落 payload(authDrafts 是保存期通道,非存储形态)
        row = (await s.execute(sa.text(
            "SELECT payload FROM composer_scenarios"
            " WHERE scenario_id='sc-ad-1'"))).scalar()
        assert "authDrafts" not in row


@pytest.mark.asyncio
async def test_registry_gate_enforce_allows_draft_names(
        client: AsyncClient, plate_mock, monkeypatch):
    """enforce 态:引用名尚未入库、随保存将建 —— 登记闸按已登记放行
    (阶段 0 闸与手配同事务的时序协调)。"""
    monkeypatch.setattr(settings, "REGISTRY_ONLY_IDENTITIES", "enforce")
    env = await _seed_base()
    h = await role_headers(client, "ad_g")
    r = await client.post("/api/scenarios", headers=h, json=_draft(
        "sc-ad-gate", "pay-enf", [
            _manual_cfg(name="pay-enf", username="ue", env=env)]))
    assert r.status_code in (200, 201), r.text


@pytest.mark.asyncio
async def test_alias_taken_conflict_rolls_back(
        client: AsyncClient, plate_mock):
    """行为规则①:引用名已登记 → 409 提示直接引用;整单回滚
    (场景行、池行都不落)。"""
    env = await _seed_base()
    h = await role_headers(client, "ad_t")
    async with db_module.SessionLocal() as s:
        s.add(ServiceIdentity(alias_name="pay-uat", base_service="fin-svc",
                              env_id=env, ref_mode="default"))
        await s.commit()
    r = await client.post("/api/scenarios", headers=h, json=_draft(
        "sc-ad-2", "pay-uat", [_manual_cfg(env=env)]))
    assert r.status_code == 409, r.text
    assert r.json()["detail"].startswith("auth_draft_alias_taken")
    async with db_module.SessionLocal() as s:
        uid = (await s.execute(sa.text(
            "SELECT id FROM users WHERE username='ad_t'"))).scalar()
        assert (await s.execute(sa.text(
            "SELECT count(*) FROM composer_scenarios"
            " WHERE scenario_id='sc-ad-2'"))).scalar() == 0
        assert (await s.execute(sa.text(
            "SELECT count(*) FROM auth_accounts"
            " WHERE owner_id=:u"), {"u": uid})).scalar() == 0


@pytest.mark.asyncio
async def test_account_exists_conflict(client: AsyncClient, plate_mock):
    """账户四元组冲突 → 409 auth_draft_account_exists(提示直接引用
    同名条目/去认证管理改,不静默覆盖)。"""
    env = await _seed_base()
    h = await role_headers(client, "ad_a")
    r = await client.post("/api/scenarios", headers=h, json=_draft(
        "sc-ad-3", "pay-a", [_manual_cfg(name="pay-a", env=env)]))
    assert r.status_code in (200, 201), r.text
    # 同 (system, env, username) 再手配一个新名 → 账户冲突
    r = await client.post("/api/scenarios", headers=h, json=_draft(
        "sc-ad-4", "pay-b", [
            _manual_cfg(name="pay-b", env=env)]))
    assert r.status_code == 409, r.text
    assert r.json()["detail"].startswith("auth_draft_account_exists")


@pytest.mark.asyncio
async def test_entry_only_draft_references_existing_account(
        client: AsyncClient, plate_mock):
    """检索面「选用」通道(2026-11-21):``password`` 缺省 = 只建
    username-ref 条目,账户取自本人池既有四元组 —— 不新建账户、不碰
    密码;条目同样随保存同事务落库,响应 newAuths 点名。"""
    env = await _seed_base()
    h = await role_headers(client, "ad_ref")
    # 先手配建账户 (fin, env, u1)
    r = await client.post("/api/scenarios", headers=h, json=_draft(
        "sc-ad-ref1", "pay-uat", [_manual_cfg(env=env)]))
    assert r.status_code in (200, 201), r.text
    # 引用已有账户建第二个条目:无 password
    r = await client.post("/api/scenarios", headers=h, json=_draft(
        "sc-ad-ref2", "pay-uat2", [{
            "name": "pay-uat2", "system": "fin", "envId": env,
            "username": "u1"}]))
    assert r.status_code in (200, 201), r.text
    assert r.json().get("newAuths") == ["pay-uat2"]
    async with db_module.SessionLocal() as s:
        uid = (await s.execute(sa.text(
            "SELECT id FROM users WHERE username='ad_ref'"))).scalar()
        ident = (await s.execute(sa.select(ServiceIdentity).where(
            ServiceIdentity.alias_name == "pay-uat2"))).scalar_one()
        assert (ident.ref_mode, ident.ref_username,
                ident.base_service) == ("username", "u1", "fin-svc")
        # 账户数不变(账户是引用,不是新建)
        cnt = (await s.execute(sa.text(
            "SELECT count(*) FROM auth_accounts WHERE owner_id=:u"),
            {"u": uid})).scalar()
        assert cnt == 1


@pytest.mark.asyncio
async def test_entry_only_draft_account_missing_rolls_back(
        client: AsyncClient, plate_mock):
    """引用已有账户但四元组不在本人池 → 422 auth_draft_account_not_found,
    整单回滚(条目/场景都不落)。"""
    env = await _seed_base()
    h = await role_headers(client, "ad_refx")
    r = await client.post("/api/scenarios", headers=h, json=_draft(
        "sc-ad-refx", "pay-ghost", [{
            "name": "pay-ghost", "system": "fin", "envId": env,
            "username": "nobody"}]))
    assert r.status_code == 422, r.text
    assert r.json()["detail"].startswith("auth_draft_account_not_found")
    async with db_module.SessionLocal() as s:
        assert (await s.execute(sa.select(ServiceIdentity.alias_name).where(
            ServiceIdentity.alias_name == "pay-ghost"))).scalar_one_or_none() \
            is None
        assert (await s.execute(sa.text(
            "SELECT count(*) FROM composer_scenarios"
            " WHERE scenario_id='sc-ad-refx'"))).scalar() == 0


@pytest.mark.asyncio
async def test_system_unknown_and_env_missing(client: AsyncClient,
                                              plate_mock):
    """手配条目 base_service 须落主档既有服务(admin 目录面):
    未知系统 422;环境不存在 422。"""
    env = await _seed_base()
    h = await role_headers(client, "ad_x")
    r = await client.post("/api/scenarios", headers=h, json=_draft(
        "sc-ad-5", "pay-x", [
            _manual_cfg(name="pay-x", system="nope", env=env)]))
    assert r.status_code == 422, r.text
    assert r.json()["detail"].startswith("auth_draft_system_unknown")
    r = await client.post("/api/scenarios", headers=h, json=_draft(
        "sc-ad-6", "pay-e", [
            _manual_cfg(name="pay-e", env=99_999_999)]))
    assert r.status_code == 422, r.text
    assert r.json()["detail"].startswith("auth_draft_env_not_found")


@pytest.mark.asyncio
async def test_put_owner_manual_config(client: AsyncClient, plate_mock):
    """属主 PUT 带手配 → 200 + newAuths;非属主维护者(项目成员可写
    他人场景)带手配 → 403 auth_draft_owner_required(§3.8 拍板)。"""
    env = await _seed_base()
    from .test_authz_s8_project_credentials import _mk_project
    h_a = await role_headers(client, "ad_pa")
    r = await client.post("/api/scenarios", headers=h_a, json=_draft(
        "sc-ad-7", "pay-p", None))
    assert r.status_code in (200, 201), r.text
    r = await client.put("/api/scenarios/sc-ad-7", headers=h_a, json=_draft(
        "sc-ad-7", "pay-p", [_manual_cfg(name="pay-p", env=env)]))
    assert r.status_code == 200, r.text
    assert r.json().get("newAuths") == ["pay-p"]

    # 项目成员写他人场景(项目区写权),但不代属主落池
    h_b = await role_headers(client, "ad_pb")   # 先有用户再建项目
    pid = await _mk_project("ad-proj", members={"ad_pb": "admin"})
    async with db_module.SessionLocal() as s:
        owner_b = (await s.execute(sa.text(
            "SELECT id FROM users WHERE username='ad_pa'"))).scalar()
        member_b = (await s.execute(sa.text(
            "SELECT id FROM users WHERE username='ad_pb'"))).scalar()
        from app.models.project import ProjectMember
        s.add(ProjectMember(project_id=pid, user_id=owner_b, role="member"))
        await s.flush()
        from app.models.composer_scenario import ComposerScenario
        row = (await s.execute(sa.select(ComposerScenario).where(
            ComposerScenario.scenario_id == "sc-ad-7"))).scalar_one()
        row.project_id = pid
        await s.commit()
    h_b = await role_headers(client, "ad_pb")
    h_b = await role_headers(client, "ad_pb")
    r = await client.put("/api/scenarios/sc-ad-7", headers=h_b, json=_draft(
        "sc-ad-7", "pay-m", [
            _manual_cfg(name="pay-m", username="um", env=env)]))
    assert r.status_code == 403, r.text
    assert r.json()["detail"].startswith("auth_draft_owner_required")
    async with db_module.SessionLocal() as s:
        assert (await s.execute(sa.select(ServiceIdentity.alias_name).where(
            ServiceIdentity.alias_name == "pay-m"))).scalar_one_or_none() \
            is None


# ── 并发冲突码精确化(评审 P2,2026-11-20)──────────────────────────
def test_integrity_conflict_dispatch_map():
    """scenario_store.create/update 提交点的 IntegrityError 按约束名分派:
    手配落池进同一事务后,条目/账户唯一冲突不再误报 scenario_id_exists
    (此前 blanket 映射 → 前端撞号重试 regex 跟着白耗两次重试)。
    认不出的约束保守回落旧行为(FK 竞态宁 409 不 500)。"""
    from types import SimpleNamespace

    from sqlalchemy.exc import IntegrityError

    from app.services import scenario_store

    def mk(name: str) -> IntegrityError:
        e = IntegrityError("stmt", {}, Exception("boom"))
        e.orig = SimpleNamespace(constraint_name=name)
        return e

    dispatch = scenario_store._integrity_conflict_code
    # 条目名唯一(service_identities.alias_name,PG 自动名)
    assert dispatch(mk(
        "service_identities_alias_name_key")) == "auth_draft_alias_taken"
    # 账户四元组(0057 五键,模型显式名)/ 默认位部分索引 / XOR CHECK
    assert dispatch(mk(
        "uq_account_pool_system_env_user")) == "auth_draft_account_exists"
    assert dispatch(mk("uq_account_default")) == "auth_draft_account_exists"
    assert dispatch(mk(
        "ck_account_owner_xor_project")) == "auth_draft_account_exists"
    # 场景 PK 与未知约束:保守回落旧行为
    assert dispatch(mk("composer_scenarios_pkey")) == "scenario_id_exists"
    assert dispatch(mk("whatever_else")) == "scenario_id_exists"
    # 消息形:撞号带 id;drafts 家族带「同名直接引用」指引
    assert "sc-x" in scenario_store._integrity_message(
        "scenario_id_exists", "sc-x")
    assert "直接引用" in scenario_store._integrity_message(
        "auth_draft_alias_taken", "sc-x")


@pytest.mark.asyncio
async def test_create_duplicate_scenario_still_maps(client: AsyncClient,
                                                    plate_mock):
    """保守回归钉:未知/场景 PK 冲突照旧 scenario_id_exists → 409
    (前端撞号重试语义不变)。"""
    await _seed_base()
    h = await role_headers(client, "ad_dup")
    r = await client.post("/api/scenarios", headers=h, json=_draft(
        "sc-ad-dup", "pay-d", None))
    assert r.status_code in (200, 201), r.text
    r = await client.post("/api/scenarios", headers=h, json=_draft(
        "sc-ad-dup", "pay-d", None))
    assert r.status_code == 409, r.text
    assert r.json()["detail"].startswith("scenario_id_exists")
