"""Real-path tests for run_prepare.resolve_exec_auths(§4.1 条目语义 +
§8.3 凭证去 env 匹配,2026-11-17 环境降级轮)。

覆盖新解析链核心语义:条目→ref→账户(引用不校验标签)、同标签优先 →
system 唯一 → 歧义、默认账户按 system、**登录口按账户标签**(密码与
登录口同源不变式)、多条目共享账户、解密 fail-fast、明文不落 ORM、
缺条目告警继续。
"""
from __future__ import annotations

import pytest
from sqlalchemy import select, text

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


async def _env_id(factory, name: str = "测试") -> int:
    async with factory() as db:
        return (await db.execute(text(
            "SELECT id FROM environments WHERE name = :n"),
            {"n": name})).scalar()


async def test_resolve_identity_chain_and_orm_purity(fresh_db) -> None:
    """条目→ref→账户全链:值解密正确 + url 取实例登录口 + ORM 行
    保持密文(ResolvedAuth 值对象的全部意义)。"""
    factory = db_module.SessionLocal
    owner_id = await _seed_owner(factory, "svc", "alice", "s3cret")

    resolved = await run_prepare.resolve_exec_auths(
        factory, owner_id=owner_id, aliases=["svc"])
    assert len(resolved) == 1
    r = resolved[0]
    assert isinstance(r, run_prepare.ResolvedAuth)
    assert (r.alias, r.username, r.password) == ("svc", "alice", "s3cret")
    # 登录口 = (system, 账户标签) 的实例 login_url(§8.3 不变式)
    assert r.url == "https://svc.internal"

    # ORM 行不得获得明文属性(password 恒密文;username 实体键为明文列)
    async with factory() as db:
        row = (await db.execute(select(AuthAccount))).scalar_one()
        assert "password" not in row.__dict__
        assert row.password_enc != "s3cret"
        assert row.username == "alice"


async def test_cross_tag_resolves_by_system_uniqueness(fresh_db) -> None:
    """§8.3:条目标签 ≠ 账户标签也能解析 —— system 内唯一即命中
    (旧「环境不符 → missing」门槛退役;凭证解耦,错了 401 自然暴露)。"""
    factory = db_module.SessionLocal
    owner_id = await _seed_owner(factory, "svc", "alice", "s3cret")
    from app.models import Environment

    async with factory() as db:
        db.add(Environment(name="预发"))
        await db.commit()

    resolved = await run_prepare.resolve_exec_auths(
        factory, owner_id=owner_id, aliases=["svc"])
    assert [r.username for r in resolved] == ["alice"]


async def test_same_tag_preference_beats_other_tag(fresh_db) -> None:
    """同标签优先(§8.3):同 system 同 username 两标签账户并存时,
    取与条目同标签的那行(密码可区分)。"""
    factory = db_module.SessionLocal
    async with factory() as db:
        from app.core.security import fernet_encrypt
        from app.models import AuthAccount, Environment
        user = User(username="u_pref", display_name="u_pref",
                    password_hash="x")
        db.add(user)
        await db.commit()
        await db.refresh(user)
        # 条目 + 测试账户走四件套;生产账户手工补(非默认环境)
        await seed_identity_fixture(
            db, alias="svc", username="alice", password="pw-test",
            owner_id=user.id, env_name="测试")
        db.add(Environment(name="生产"))
        await db.flush()
        env_prod = (await db.execute(select(Environment.id).where(
            Environment.name == "生产"))).scalar()
        db.add(AuthAccount(
            owner_id=user.id, system="fin-service", env_id=env_prod,
            username="alice", password_enc=fernet_encrypt("pw-prod"),
            is_default=False))
        await db.commit()
        owner_id = user.id

    resolved = await run_prepare.resolve_exec_auths(
        factory, owner_id=owner_id, aliases=["svc"])
    assert [r.password for r in resolved] == ["pw-test"]


async def test_multi_tag_no_match_is_ambiguous(fresh_db) -> None:
    """歧义(§8.3):同 system 同 username 多标签账户、且无一与条目
    标签相同 → ambiguous(不命中;预检/派发期硬拦截,这里验证解析端)。"""
    factory = db_module.SessionLocal
    async with factory() as db:
        user = User(username="u_amb", display_name="u_amb",
                    password_hash="x")
        db.add(user)
        await db.commit()
        await db.refresh(user)
        # 条目挂「测试」(默认环境),但同 username 账户只在 预发/生产
        from app.core.security import fernet_encrypt
        from app.models import (
            AuthAccount, Environment, Service, ServiceIdentity,
        )
        db.add(Environment(name="测试", is_default=True))
        db.add(Environment(name="生产"))
        db.add(Environment(name="预发"))
        db.add(Service(name="fin-service", system="fin-service", kind="plate"))
        await db.flush()
        env_test = (await db.execute(select(Environment.id).where(
            Environment.name == "测试"))).scalar()
        env_prod = (await db.execute(select(Environment.id).where(
            Environment.name == "生产"))).scalar()
        env_uat = (await db.execute(select(Environment.id).where(
            Environment.name == "预发"))).scalar()
        db.add(AuthAccount(
            owner_id=user.id, system="fin-service", env_id=env_prod,
            username="alice", password_enc=fernet_encrypt("pw-prod"),
            is_default=False))
        db.add(AuthAccount(
            owner_id=user.id, system="fin-service", env_id=env_uat,
            username="alice", password_enc=fernet_encrypt("pw-uat"),
            is_default=False))
        db.add(ServiceIdentity(
            alias_name="svc", base_service="fin-service", env_id=env_test,
            ref_mode="username", ref_username="alice"))
        await db.commit()
        owner_id = user.id

    async with factory() as db:
        picked, missing, ambiguous = await run_prepare._resolve_identities(
            db, owner_id, ["svc"])
    assert picked == {}
    assert ambiguous == ["svc"]
    assert missing == []


async def test_login_url_follows_account_tag(fresh_db) -> None:
    """§8.3 不变式:登录口按**账户标签**取 —— 密码与登录口必须同源。
    条目标签=测试、账户(唯一)标签=生产 → 用生产的登录口 + 生产密码。"""
    factory = db_module.SessionLocal
    async with factory() as db:
        user = User(username="u_url", display_name="u_url",
                    password_hash="x")
        db.add(user)
        await db.commit()
        await db.refresh(user)
        from app.core.security import fernet_encrypt
        from app.models import (
            Environment, Service, ServiceIdentity, SystemEnvInstance,
        )
        db.add(Environment(name="测试", is_default=True))
        db.add(Environment(name="生产"))
        db.add(Service(name="fin-service", system="fin-service", kind="plate"))
        await db.flush()
        env_test = (await db.execute(select(Environment.id).where(
            Environment.name == "测试"))).scalar()
        env_prod = (await db.execute(select(Environment.id).where(
            Environment.name == "生产"))).scalar()
        # 两标签各配登录口;账户只在生产
        db.add(SystemEnvInstance(
            system="fin-service", env_id=env_test, login_url="http://test-login"))
        db.add(SystemEnvInstance(
            system="fin-service", env_id=env_prod, login_url="http://prod-login"))
        db.add(AuthAccount(
            owner_id=user.id, system="fin-service", env_id=env_prod,
            username="alice",
            password_enc=fernet_encrypt("pw-prod")))
        db.add(ServiceIdentity(
            alias_name="svc", base_service="fin-service", env_id=env_test,
            ref_mode="username", ref_username="alice"))
        await db.commit()
        owner_id = user.id

    resolved = await run_prepare.resolve_exec_auths(
        factory, owner_id=owner_id, aliases=["svc"])
    assert [(r.url, r.password) for r in resolved] \
        == [("http://prod-login", "pw-prod")]


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
        factory, owner_id=owner_id, aliases=["svc", "svc-ro"])
    by_alias = {r.alias: r for r in resolved}
    assert set(by_alias) == {"svc", "svc-ro"}
    assert by_alias["svc"].username == by_alias["svc-ro"].username == "alice"
    assert by_alias["svc"].password == by_alias["svc-ro"].password
    # 同一绑定标识(同一账户行)
    assert by_alias["svc"].binding_id == by_alias["svc-ro"].binding_id


async def test_default_ref_takes_system_default_account(fresh_db) -> None:
    """ref_mode=default(§8.3):取 **system 唯一**默认账户 —— 跨标签
    亦命中(默认位按 system,索引 0059 钉死)。"""
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
        factory, owner_id=owner_id, aliases=["svc-auto"])
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
            factory, owner_id=owner_id, aliases=["good", "rotten"])


async def test_missing_identity_warns_and_continues(fresh_db) -> None:
    """条目不存在 → 解不到(告警后继续,V1 语义:步骤级错误)。"""
    factory = db_module.SessionLocal
    owner_id = await _seed_owner(factory, "svc", "alice", "s3cret")

    resolved = await run_prepare.resolve_exec_auths(
        factory, owner_id=owner_id, aliases=["svc", "ghost"])
    assert [r.alias for r in resolved] == ["svc"]
