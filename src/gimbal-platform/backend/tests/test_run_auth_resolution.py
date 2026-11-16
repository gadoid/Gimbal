"""Real-path tests for run_prepare.resolve_exec_auths(重构 §4.1 条目语义)。

覆盖新解析链的核心语义:条目→ref→账户、env 必填收紧、多条目共享
账户、解密 fail-fast、明文不落 ORM、缺条目告警继续。
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from sqlalchemy import text

from app.core import db as db_module
from app.models import AuthAccount, User
from app.services import run_prepare

from .conftest import seed_identity_fixture


async def _seed_owner(factory, alias: str, username: str, password: str,
                      *, env_name: str = "测试") -> int:
    """新 owner + 四件套布景(环境/主档/账户/条目);返回 user id。"""
    async with factory() as db:
        user = User(username=f"u_{alias}", display_name=f"u_{alias}",
                    password_hash="x")
        db.add(user)
        await db.commit()
        await db.refresh(user)
        await seed_identity_fixture(
            db, alias=alias, username=username, password=password,
            owner_id=user.id, env_name=env_name)
        return user.id


async def test_resolve_identity_chain_and_orm_purity(fresh_db) -> None:
    """条目→ref→账户全链:值解密正确 + url 取实例登录口 + ORM 行
    保持密文(ResolvedAuth 值对象的全部意义)。"""
    factory = db_module.SessionLocal
    owner_id = await _seed_owner(factory, "svc", "alice", "s3cret")

    async with factory() as db:
        env_id = (await db.execute(text(
            "SELECT id FROM environments WHERE name = '测试'"))).scalar()

    resolved = await run_prepare.resolve_exec_auths(
        factory, owner_id=owner_id, aliases=["svc"], env_id=env_id)
    assert len(resolved) == 1
    r = resolved[0]
    assert isinstance(r, run_prepare.ResolvedAuth)
    assert (r.alias, r.username, r.password) == ("svc", "alice", "s3cret")
    assert r.url == "https://svc.internal"

    # ORM 行不得获得明文属性(password 恒密文;username 实体键为明文列)
    async with factory() as db:
        row = (await db.execute(select(AuthAccount))).scalar_one()
        assert "password" not in row.__dict__
        assert row.password_enc != "s3cret"
        assert row.username == "alice"


async def test_resolve_requires_env(fresh_db) -> None:
    """env 必填收紧(§1.4):无环境执行无从解析身份 —— 全部 missing,
    告警后返回空(V1 语义:缺条目是步骤级错误,不是派发失败)。"""
    factory = db_module.SessionLocal
    owner_id = await _seed_owner(factory, "svc", "alice", "s3cret")

    resolved = await run_prepare.resolve_exec_auths(
        factory, owner_id=owner_id, aliases=["svc"], env_id=None)
    assert resolved == []


async def test_env_mismatch_is_missing(fresh_db) -> None:
    """条目 env ≠ 执行 env → 环境不符 → 缺(无回退分支,决策 8)。"""
    factory = db_module.SessionLocal
    owner_id = await _seed_owner(factory, "svc", "alice", "s3cret")
    # 建第二个环境,条目挂在「测试」上 —— 用「预发」执行解析不到
    from app.models import Environment

    async with factory() as db:
        db.add(Environment(name="预发"))
        await db.commit()
        other_env = (await db.execute(select(Environment.id).where(
            Environment.name == "预发"))).scalar()

    resolved = await run_prepare.resolve_exec_auths(
        factory, owner_id=owner_id, aliases=["svc"], env_id=other_env)
    assert resolved == []


async def test_two_identities_share_one_account(fresh_db) -> None:
    """多条目共享账户(§4.1 ref 引用):svc 与 svc-ro 两条目 ref 同一
    username 账户 —— 「一个凭证装载在多套身份上」的实现形态。"""
    factory = db_module.SessionLocal
    async with factory() as db:
        user = User(username="u_shared", display_name="u_shared",
                    password_hash="x")
        db.add(user)
        await db.commit()
        await db.refresh(user)
        await seed_identity_fixture(
            db, alias="svc", username="alice", password="s3cret",
            owner_id=user.id)
        # 第二条目:同服务/环境,ref 同一 username
        from app.models import ServiceIdentity
        env_id = (await db.execute(text(
            "SELECT id FROM environments WHERE name = '测试'"))).scalar()
        db.add(ServiceIdentity(
            alias_name="svc-ro", base_service="fin-service", env_id=env_id,
            ref_mode="username", ref_username="alice"))
        await db.commit()
        owner_id = user.id

    resolved = await run_prepare.resolve_exec_auths(
        factory, owner_id=owner_id, aliases=["svc", "svc-ro"],
        env_id=env_id)
    by_alias = {r.alias: r for r in resolved}
    assert set(by_alias) == {"svc", "svc-ro"}
    assert by_alias["svc"].username == by_alias["svc-ro"].username == "alice"
    assert by_alias["svc"].password == by_alias["svc-ro"].password
    # 同一绑定标识(同一账户行)
    assert by_alias["svc"].binding_id == by_alias["svc-ro"].binding_id


async def test_default_ref_takes_is_default_account(fresh_db) -> None:
    """ref_mode=default:取 (system, env) 的 is_default 账户。"""
    factory = db_module.SessionLocal
    async with factory() as db:
        user = User(username="u_def", display_name="u_def", password_hash="x")
        db.add(user)
        await db.commit()
        await db.refresh(user)
        await seed_identity_fixture(
            db, alias="primary", username="alice", password="pw1",
            owner_id=user.id, is_default=True)
        await seed_identity_fixture(
            db, alias="secondary", username="bob", password="pw2",
            owner_id=user.id, is_default=False)
        # default 型条目(不指定 username)
        from app.models import ServiceIdentity
        env_id = (await db.execute(text(
            "SELECT id FROM environments WHERE name = '测试'"))).scalar()
        db.add(ServiceIdentity(
            alias_name="svc-auto", base_service="fin-service",
            env_id=env_id, ref_mode="default"))
        await db.commit()
        owner_id = user.id

    resolved = await run_prepare.resolve_exec_auths(
        factory, owner_id=owner_id, aliases=["svc-auto"], env_id=env_id)
    assert [r.username for r in resolved] == ["alice"]


async def test_decrypt_failure_fails_fast(fresh_db) -> None:
    """坏密文 → AuthResolveError(V1 严格语义:fail-fast,不静默空跑)。"""
    factory = db_module.SessionLocal
    owner_id = await _seed_owner(factory, "good", "alice", "s3cret")
    async with factory() as db:
        from app.models import AuthAccount, ServiceIdentity
        env_id = (await db.execute(text(
            "SELECT id FROM environments WHERE name = '测试'"))).scalar()
        acc = AuthAccount(
            owner_id=owner_id, system="fin-service", env_id=env_id,
            username="rotten", password_enc="gitleaks:not-a-fernet-token")
        db.add(acc)
        await db.flush()
        db.add(ServiceIdentity(
            alias_name="rotten", base_service="fin-service", env_id=env_id,
            ref_mode="username", ref_username="rotten"))
        await db.commit()

    with pytest.raises(run_prepare.AuthResolveError, match="rotten"):
        await run_prepare.resolve_exec_auths(
            factory, owner_id=owner_id, aliases=["good", "rotten"],
            env_id=env_id)


async def test_missing_identity_warns_and_continues(fresh_db) -> None:
    """条目不存在 → 解不到(告警后继续,V1 语义:步骤级错误)。"""
    factory = db_module.SessionLocal
    owner_id = await _seed_owner(factory, "svc", "alice", "s3cret")
    from sqlalchemy import text as _t

    async with factory() as db:
        env_id = (await db.execute(db_module.engine.sync_engine \
            .raw_connection() and text(
                "SELECT id FROM environments WHERE name = '测试'"))).scalar() \
            if False else None
    async with factory() as db:
        env_id = (await db.execute(text(
            "SELECT id FROM environments WHERE name = '测试'"))).scalar()

    resolved = await run_prepare.resolve_exec_auths(
        factory, owner_id=owner_id, aliases=["svc", "ghost"], env_id=env_id)
    assert [r.alias for r in resolved] == ["svc"]
