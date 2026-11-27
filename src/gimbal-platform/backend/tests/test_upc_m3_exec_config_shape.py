"""UPC §5/§11.2/§20 ExecConfig 单表显式互斥 FK 形状闸(0070,随冻结稿
实施):principal_id / project_id 恰一非空(XOR CHECK),两真实 FK,
同侧唯一/默认部分唯一索引 —— 无外键多态 scope 列已退役。

直写负向在库层提交期拒绝;fresh(create_all)与链路径(0069→0070
增量)终态一致由既有 §20.4 双路径断言覆盖(test_upc_dual_path 已增
exec_configs 对照),本文件补直写负向 + 链路径真实执行腿。"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import IntegrityError

from app.core import db as db_module
from app.models.exec_config import ExecConfig

from tests.test_migrations import temp_schema


async def _seed_uid(s) -> int:
    from app.core.security import hash_password
    from app.models.user import User

    uid = (await s.execute(select(User.id).order_by(User.id)
                           .limit(1))).scalar_one_or_none()
    if uid is None:
        u = User(username="shape-seed", display_name="形状种子",
                 password_hash=hash_password("pw123456"))
        s.add(u)
        await s.flush()
        uid = u.id
    return uid


async def test_xor_shape_rejected_at_db_layer(client):
    """直写违例(绕过路由配对闸):两侧同非空 / 两侧同空 →
    ck_exec_configs_owner_shape 在提交期拒绝(flush 期即 CHECK 违例,
    PG 立即校验);合法两型照常。"""
    async with db_module.SessionLocal() as s:
        uid = await _seed_uid(s)
        s.add(ExecConfig(principal_id=uid, name="合法-user"))
        await s.flush()
        bad_both = ExecConfig(principal_id=uid, project_id=1, name="违例-双侧")
        s.add(bad_both)
        with pytest.raises(IntegrityError):
            await s.flush()
        await s.rollback()
        bad_none = ExecConfig(name="违例-无归属")
        s.add(bad_none)
        with pytest.raises(IntegrityError):
            await s.flush()
        await s.rollback()


async def test_real_fk_enforced(client):
    """两真实 FK:principal_id / project_id 指向不存在行 → 提交期拒
    (§5「禁止无外键 scope_id」;悬空引用不再可能)。"""
    from app.models.project import Project

    # 种子先行提交(负向探测各自回滚,不得冲掉布景)
    async with db_module.SessionLocal() as s:
        uid = await _seed_uid(s)
        pid = (await s.execute(select(Project.id).where(
            Project.owner_id == uid))).scalar_one_or_none()
        if pid is None:
            proj = Project(kind="private", name="形状空间", owner_id=uid,
                           is_default=True, status=Project.STATUS_ACTIVE)
            s.add(proj)
            await s.flush()
            pid = proj.id
        await s.commit()

    async with db_module.SessionLocal() as s:
        s.add(ExecConfig(principal_id=99999999, name="悬空-主体"))
        with pytest.raises(IntegrityError):
            await s.flush()
        await s.rollback()
    async with db_module.SessionLocal() as s:
        s.add(ExecConfig(project_id=99999999, name="悬空-项目"))
        with pytest.raises(IntegrityError):
            await s.flush()
        await s.rollback()
    # 对照:合法两型照常(两行分次 flush —— 同事务多行合批 INSERT 在
    # asyncpg + 部分唯一索引组合下有误报唯一键的怪相,拆开即稳)
    async with db_module.SessionLocal() as s:
        pid = (await s.execute(select(Project.id).where(
            Project.kind == "private").limit(1))).scalar_one()
        s.add(ExecConfig(project_id=pid, name="合法-项目"))
        await s.flush()
        uid = (await s.execute(select(Project.owner_id).where(
            Project.id == pid))).scalar_one()
        s.add(ExecConfig(principal_id=uid, name="合法-个人"))
        await s.flush()


def test_0070_chain_path_swaps_shape():
    """链路径真实执行腿:时代造形回 0053 形状 → 0069(scope 枚举闸)→
    0070(换 XOR 形状)—— 升级后 scope 枚举 CHECK 摘除、XOR CHECK
    就位、两真实 FK 就位、旧列退役(回填/换形增量真实执行)。"""
    from alembic import command

    from tests.test_migrations import (_cfg, _to_exec_config_era_shape,
                                       _upgrade_to)

    with temp_schema() as (_schema, sync_url):
        _upgrade_to(sync_url, "0068_upc_resource_containers")
        # 时代造形:baseline(当前模型 = 0070 新形状)→ 0053 时代形态
        _to_exec_config_era_shape(create_engine(sync_url))
        command.upgrade(_cfg(sync_url), "0069_exec_config_scope_shape")
        eng = create_engine(sync_url)
        try:
            with eng.begin() as c:
                checks = {row[0] for row in c.execute(text(
                    "SELECT conname FROM pg_constraint WHERE conrelid = "
                    "'exec_configs'::regclass AND contype = 'c'"))}
                cols = {row[0] for row in c.execute(text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'exec_configs' "
                    "AND table_schema = current_schema()"))}
            # 0069 终态:scope 枚举闸在、旧形状列在
            assert "ck_exec_configs_scope" in checks
            assert {"scope", "scope_id"} <= cols
        finally:
            eng.dispose()
        command.upgrade(_cfg(sync_url), "0070_exec_config_owner_fk")
        eng = create_engine(sync_url)
        try:
            with eng.begin() as c:
                checks_after = {row[0] for row in c.execute(text(
                    "SELECT conname FROM pg_constraint WHERE conrelid = "
                    "'exec_configs'::regclass AND contype = 'c'"))}
                cols_after = {row[0] for row in c.execute(text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'exec_configs' "
                    "AND table_schema = current_schema()"))}
                fks = {row[0] for row in c.execute(text(
                    "SELECT conname FROM pg_constraint WHERE conrelid = "
                    "'exec_configs'::regclass AND contype = 'f'"))}
            assert "ck_exec_configs_owner_shape" in checks_after
            assert "ck_exec_configs_scope" not in checks_after
            assert {"fk_exec_configs_principal",
                    "fk_exec_configs_project"} <= fks
            assert not ({"scope", "scope_id"} & cols_after)
            assert {"principal_id", "project_id"} <= cols_after
        finally:
            eng.dispose()


def test_model_shape_registered_in_metadata():
    """模型元数据登记断言(防手滑摘除后 fresh 链静默漂移):XOR CHECK
    + 两 FK + 同侧默认部分唯一索引全部在 __table_args__/列上。"""
    checks = {c.name for c in ExecConfig.__table__.constraints
              if c.__class__.__name__ == "CheckConstraint"}
    assert "ck_exec_configs_owner_shape" in checks
    fks = {c.name for c in ExecConfig.__table__.constraints
           if c.__class__.__name__ == "ForeignKeyConstraint"}
    assert {"fk_exec_configs_principal", "fk_exec_configs_project"} <= fks
    idx = {i.name for i in ExecConfig.__table__.indexes}
    assert {"uq_exec_configs_principal_default",
            "uq_exec_configs_project_default",
            "uq_exec_configs_principal_name",
            "uq_exec_configs_project_name"} <= idx


def test_0070_backfills_and_cleans_orphans():
    """数据回填腿(复核 P2):时代形状播 (scope, scope_id) 行 ——
    user/project 各合法行 + 指向已删 user/project(含零 id)的孤儿行
    → 0070 后 principal_id/project_id 正确回填、孤儿行清理、合法行
    保留。形状腿(test_0070_chain_path_swaps_shape)之外的语义腿。"""
    from alembic import command
    from sqlalchemy import create_engine

    from tests.test_migrations import (
        _cfg,
        _to_exec_config_era_shape,
        _upgrade_to,
        temp_schema,
    )

    with temp_schema() as (_schema, sync_url):
        _upgrade_to(sync_url, "0068_upc_resource_containers")
        _to_exec_config_era_shape(create_engine(sync_url))
        command.upgrade(_cfg(sync_url), "0069_exec_config_scope_shape")
        # 时代形状播种:合法 user/project + 孤儿(user→无此 id、
        # project→无此 id、user→零 id)
        eng = create_engine(sync_url)
        with eng.begin() as c:
            c.execute(text(
                "INSERT INTO users (username, display_name, password_hash, "
                "role, is_active, is_system, created_at, updated_at) VALUES "
                "('ec70u', 'ec70u', 'x', 'user', true, true, now(), now())"))
            uid = c.execute(text(
                "SELECT id FROM users WHERE username = 'ec70u'")
            ).scalar_one()
            c.execute(text(
                "INSERT INTO projects (name, kind, description, owner_id, "
                "created_at) VALUES ('ec70p', 'private', '', :uid, now())"),
                {"uid": uid})
            pid = c.execute(text(
                "SELECT id FROM projects WHERE name = 'ec70p'")).scalar_one()
            for scope, sid, nm in (("user", uid, "合法-个人"),
                                   ("project", pid, "合法-项目"),
                                   ("user", 987000, "孤儿-主体"),
                                   ("project", 987001, "孤儿-项目"),
                                   ("user", 0, "孤儿-零id")):
                c.execute(text(
                    "INSERT INTO exec_configs (scope, scope_id, name, "
                    "is_default, payload, created_at, updated_at) VALUES "
                    "(:s, :sid, :nm, false, '{}', now(), now())"),
                    {"s": scope, "sid": sid, "nm": nm})
        eng.dispose()

        command.upgrade(_cfg(sync_url), "0070_exec_config_owner_fk")
        eng = create_engine(sync_url)
        try:
            with eng.begin() as c:
                data = {r[0]: (r[1], r[2]) for r in c.execute(text(
                    "SELECT name, principal_id, project_id FROM exec_configs"))}
        finally:
            eng.dispose()
        assert data["合法-个人"] == (uid, None), data
        assert data["合法-项目"] == (None, pid), data
        assert not {"孤儿-主体", "孤儿-项目", "孤儿-零id"} & set(data), data
