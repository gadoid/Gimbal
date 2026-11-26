"""UPC §11.2 ExecConfig 形状闸(库层 CHECK,随 M3 推断实施):
scope ∈ {user, project} 钉死在库层 —— 路由层成对写纪律(user → user.id /
project → 项目 id,scope_id 恒非空)的直写/存量违例在提交期拒绝;
fresh(create_all)与链路径(0069 增量)终态一致由既有 §20.4 双路径
断言(test_upc_dual_path.TestDualPathStructure.test_constraints)覆盖,
本文件补直写负向 + 链路径真实执行腿。"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from app.core import db as db_module
from app.models.exec_config import ExecConfig

from tests.test_migrations import temp_schema


async def test_illegal_scope_rejected_at_db_layer(client):
    """直写违例(绕过路由配对闸):scope='org' → ck_exec_configs_scope
    在提交期拒绝(flush 期即 CHECK 违例,PG 立即校验);合法两型照常。"""
    from sqlalchemy import select

    from app.models.user import User

    async with db_module.SessionLocal() as s:
        uid = (await s.execute(select(User.id).order_by(User.id)
                               .limit(1))).scalar_one_or_none()
        if uid is None:
            # 本测试 schema 尚无用户(client fixture 只建库不播种):
            # 建号(触发器 ⑥ 同事务造默认空间)后取 id
            from app.core.security import hash_password

            u = User(username="shape-seed", display_name="形状种子",
                     password_hash=hash_password("pw123456"))
            s.add(u)
            await s.flush()
            uid = u.id
        s.add(ExecConfig(scope="user", scope_id=uid, name="合法-user"))
        await s.flush()
        bad = ExecConfig(scope="org", scope_id=uid, name="违例-org")
        s.add(bad)
        with pytest.raises(IntegrityError):
            await s.flush()
        await s.rollback()


def test_0069_chain_path_adds_scope_shape_check():
    """链路径真实执行腿:_upgrade_to(baseline + 造形 + 续升)到
    0068 再升 0069 —— baseline create_all 已带模型 CHECK,0069 守卫
    空转即合法断言面(约束存在 + 幂等);fresh 路径由模型 __table_args__
    同名约束承载(双路径一致归既有 §20.4 套件)。"""
    from tests.test_migrations import _upgrade_to

    with temp_schema() as (_schema, sync_url):
        _upgrade_to(sync_url, "0068_upc_resource_containers")
        eng = create_engine(sync_url)
        try:
            with eng.begin() as c:
                names = {row[0] for row in c.execute(text(
                    "SELECT conname FROM pg_constraint WHERE conrelid = "
                    "'exec_configs'::regclass AND contype = 'c'"))}
            # baseline create_all 形态:模型 CHECK 已就位
            assert "ck_exec_configs_scope" in names, names
        finally:
            eng.dispose()
        # 升到 0069:守卫见约束已存在 → 空转(幂等不炸),约束仍在
        _upgrade_to(sync_url, "0069_exec_config_scope_shape")
        eng = create_engine(sync_url)
        try:
            with eng.begin() as c:
                names_after = {row[0] for row in c.execute(text(
                    "SELECT conname FROM pg_constraint WHERE conrelid = "
                    "'exec_configs'::regclass AND contype = 'c'"))}
            assert "ck_exec_configs_scope" in names_after
        finally:
            eng.dispose()


def test_model_check_registered_in_metadata():
    """模型元数据登记断言(防手滑摘除后 fresh 链静默漂移):
    exec_configs 的 CHECK 约束集含 ck_exec_configs_scope。"""
    checks = {c.name for c in ExecConfig.__table__.constraints
              if c.__class__.__name__ == "CheckConstraint"}
    assert "ck_exec_configs_scope" in checks
