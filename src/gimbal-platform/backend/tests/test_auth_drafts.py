"""调用身份草稿(保存期通道;架构一致性轮 2026-11-21 收窄)。

钉子:
* 同事务:场景保存随带 ``authDrafts`` 只建 ``ServiceIdentity``
  (username-ref),**不建账户** —— 凭证是独立资产,走 ``POST /auths``;
* ``baseService`` 是服务锚(不再是 system),同系统多服务由实例决定;
* 账户可见性 = 本人池 ∪ 场景项目池,env 不作门槛(§8.3);
* 冲突码:同名条目 409 ``auth_draft_alias_taken``;未知服务 422
  ``auth_draft_service_unknown``;环境 422 ``auth_draft_env_not_found``;
  账户不可见 422 ``auth_draft_account_not_found``;
* 属主闸(§3.8):update 时 user ≠ row.owner → 403
  ``auth_draft_owner_required``;
* 决策 1 登记闸协调:enforce 态下草稿名(同事务将建)按已登记放行。
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


async def _seed_account(
    owner: str | None, *, account_username: str = "u1",
    system: str = "fin", env: int, project_id: int | None = None,
) -> None:
    """在本人池 / 项目池种一个账户(草稿只引用,不创建)。"""
    async with db_module.SessionLocal() as s:
        owner_id = None
        if project_id is None:
            owner_id = (await s.execute(sa.text(
                "SELECT id FROM users WHERE username=:u"),
                {"u": owner})).scalar()
        s.add(AuthAccount(
            owner_id=owner_id, project_id=project_id, system=system,
            env_id=env, username=account_username, password_enc="enc",
            is_default=True))
        await s.commit()


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


def _cfg(name: str, *, username: str = "u1", base: str = "fin-svc",
         env: int) -> dict:
    return {"name": name, "baseService": base, "envId": env,
            "username": username}


@pytest.mark.asyncio
async def test_identity_draft_creates_entry_only(
        client: AsyncClient, plate_mock):
    """只建 username-ref 身份,不建账户;显式 baseService 生效。"""
    env = await _seed_base()
    h = await role_headers(client, "ad_own")
    await _seed_account("ad_own", env=env)
    r = await client.post("/api/scenarios", headers=h, json=_draft(
        "sc-ad-1", "pay-uat", [_cfg("pay-uat", env=env)]))
    assert r.status_code in (200, 201), r.text
    assert r.json().get("newAuths") == ["pay-uat"]
    async with db_module.SessionLocal() as s:
        uid = (await s.execute(sa.text(
            "SELECT id FROM users WHERE username='ad_own'"))).scalar()
        ident = (await s.execute(sa.select(ServiceIdentity).where(
            ServiceIdentity.alias_name == "pay-uat"))).scalar_one()
        assert (ident.ref_mode, ident.ref_username,
                ident.base_service) == ("username", "u1", "fin-svc")
        cnt = (await s.execute(sa.text(
            "SELECT count(*) FROM auth_accounts WHERE owner_id=:u"),
            {"u": uid})).scalar()
        assert cnt == 1     # 种子账户,草稿未新建
        row = (await s.execute(sa.text(
            "SELECT payload FROM composer_scenarios"
            " WHERE scenario_id='sc-ad-1'"))).scalar()
        assert "authDrafts" not in row


@pytest.mark.asyncio
async def test_registry_gate_enforce_allows_draft_names(
        client: AsyncClient, plate_mock, monkeypatch):
    """enforce 态:引用名尚未入库、随保存将建 —— 登记闸按已登记放行。"""
    monkeypatch.setattr(settings, "REGISTRY_ONLY_IDENTITIES", "enforce")
    env = await _seed_base()
    h = await role_headers(client, "ad_g")
    await _seed_account("ad_g", env=env)
    r = await client.post("/api/scenarios", headers=h, json=_draft(
        "sc-ad-gate", "pay-enf", [_cfg("pay-enf", env=env)]))
    assert r.status_code in (200, 201), r.text


@pytest.mark.asyncio
async def test_alias_taken_conflict_rolls_back(
        client: AsyncClient, plate_mock):
    """行为规则①:引用名已登记 → 409 提示直接引用;整单回滚。"""
    env = await _seed_base()
    h = await role_headers(client, "ad_t")
    await _seed_account("ad_t", env=env)
    async with db_module.SessionLocal() as s:
        s.add(ServiceIdentity(alias_name="pay-uat", base_service="fin-svc",
                              env_id=env, ref_mode="default"))
        await s.commit()
    r = await client.post("/api/scenarios", headers=h, json=_draft(
        "sc-ad-2", "pay-uat", [_cfg("pay-uat", env=env)]))
    assert r.status_code == 409, r.text
    assert r.json()["detail"].startswith("auth_draft_alias_taken")
    async with db_module.SessionLocal() as s:
        assert (await s.execute(sa.text(
            "SELECT count(*) FROM composer_scenarios"
            " WHERE scenario_id='sc-ad-2'"))).scalar() == 0


@pytest.mark.asyncio
async def test_account_missing_rolls_back(client: AsyncClient, plate_mock):
    """账户不在本人池/项目池 → 422 auth_draft_account_not_found,整单回滚。"""
    env = await _seed_base()
    h = await role_headers(client, "ad_refx")
    r = await client.post("/api/scenarios", headers=h, json=_draft(
        "sc-ad-refx", "pay-ghost", [_cfg("pay-ghost", username="nobody",
                                         env=env)]))
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
async def test_service_unknown_and_env_missing(client: AsyncClient,
                                               plate_mock):
    """baseService 须落主档;环境不存在 → 各自 422。"""
    env = await _seed_base()
    h = await role_headers(client, "ad_x")
    await _seed_account("ad_x", env=env)
    r = await client.post("/api/scenarios", headers=h, json=_draft(
        "sc-ad-5", "pay-x", [_cfg("pay-x", base="nope", env=env)]))
    assert r.status_code == 422, r.text
    assert r.json()["detail"].startswith("auth_draft_service_unknown")
    r = await client.post("/api/scenarios", headers=h, json=_draft(
        "sc-ad-6", "pay-e", [_cfg("pay-e", env=99_999_999)]))
    assert r.status_code == 422, r.text
    assert r.json()["detail"].startswith("auth_draft_env_not_found")


@pytest.mark.asyncio
async def test_project_pool_account_is_visible(client: AsyncClient,
                                               plate_mock):
    """场景所属项目池的账户也可被草稿引用(修复检索面可见但保存 422)。"""
    env = await _seed_base()
    from .test_authz_s8_project_credentials import _mk_project

    h = await role_headers(client, "ad_pj")
    pid = await _mk_project("ad-proj-pool", members={"ad_pj": "member"})
    await _seed_account(None, account_username="u1", env=env,
                        project_id=pid)
    r = await client.post(
        f"/api/scenarios?projectId={pid}", headers=h,
        json=_draft("sc-ad-pj", "pay-pj", [_cfg("pay-pj", env=env)]))
    assert r.status_code in (200, 201), r.text
    assert r.json().get("newAuths") == ["pay-pj"]


@pytest.mark.asyncio
async def test_put_owner_manual_config(client: AsyncClient, plate_mock):
    """属主 PUT 带草稿 → 200 + newAuths;非属主维护者 → 403。"""
    env = await _seed_base()
    from .test_authz_s8_project_credentials import _mk_project
    h_a = await role_headers(client, "ad_pa")
    await _seed_account("ad_pa", env=env)
    r = await client.post("/api/scenarios", headers=h_a, json=_draft(
        "sc-ad-7", "pay-p", None))
    assert r.status_code in (200, 201), r.text
    r = await client.put("/api/scenarios/sc-ad-7", headers=h_a, json=_draft(
        "sc-ad-7", "pay-p", [_cfg("pay-p", env=env)]))
    assert r.status_code == 200, r.text
    assert r.json().get("newAuths") == ["pay-p"]

    h_b = await role_headers(client, "ad_pb")
    pid = await _mk_project("ad-proj", members={"ad_pb": "admin"})
    async with db_module.SessionLocal() as s:
        owner_b = (await s.execute(sa.text(
            "SELECT id FROM users WHERE username='ad_pa'"))).scalar()
        from app.models.project import ProjectMember
        s.add(ProjectMember(project_id=pid, user_id=owner_b, role="member"))
        await s.flush()
        from app.models.composer_scenario import ComposerScenario
        row = (await s.execute(sa.select(ComposerScenario).where(
            ComposerScenario.scenario_id == "sc-ad-7"))).scalar_one()
        row.project_id = pid
        await s.commit()
    h_b = await role_headers(client, "ad_pb")
    await _seed_account("ad_pb", env=env)
    r = await client.put("/api/scenarios/sc-ad-7", headers=h_b, json=_draft(
        "sc-ad-7", "pay-m", [_cfg("pay-m", username="u1", env=env)]))
    assert r.status_code == 403, r.text
    assert r.json()["detail"].startswith("auth_draft_owner_required")
    async with db_module.SessionLocal() as s:
        assert (await s.execute(sa.select(ServiceIdentity.alias_name).where(
            ServiceIdentity.alias_name == "pay-m"))).scalar_one_or_none() \
            is None


def test_integrity_conflict_dispatch_map():
    """提交点 IntegrityError:条目名唯一 → auth_draft_alias_taken;
    账户约束不再由草稿触发(凭证走 /auths),保守回落 scenario_id_exists。"""
    from types import SimpleNamespace

    from sqlalchemy.exc import IntegrityError

    from app.services import scenario_store

    def mk(name: str) -> IntegrityError:
        e = IntegrityError("stmt", {}, Exception("boom"))
        e.orig = SimpleNamespace(constraint_name=name)
        return e

    dispatch = scenario_store._integrity_conflict_code
    assert dispatch(mk(
        "service_identities_alias_name_key")) == "auth_draft_alias_taken"
    assert dispatch(mk("uq_account_pool_system_env_user")) == \
        "scenario_id_exists"
    assert dispatch(mk("composer_scenarios_pkey")) == "scenario_id_exists"
    assert dispatch(mk("whatever_else")) == "scenario_id_exists"
    assert "sc-x" in scenario_store._integrity_message(
        "scenario_id_exists", "sc-x")
    assert "直接引用" in scenario_store._integrity_message(
        "auth_draft_alias_taken", "sc-x")


@pytest.mark.asyncio
async def test_create_duplicate_scenario_still_maps(client: AsyncClient,
                                                    plate_mock):
    """保守回归钉:场景 PK 冲突照旧 scenario_id_exists → 409。"""
    await _seed_base()
    h = await role_headers(client, "ad_dup")
    r = await client.post("/api/scenarios", headers=h, json=_draft(
        "sc-ad-dup", "pay-d", None))
    assert r.status_code in (200, 201), r.text
    r = await client.post("/api/scenarios", headers=h, json=_draft(
        "sc-ad-dup", "pay-d", None))
    assert r.status_code == 409, r.text
    assert r.json()["detail"].startswith("scenario_id_exists")
