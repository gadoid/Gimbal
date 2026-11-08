"""authz M2a S2.0:部署表 + 环境链数据模型(迁移 0044 的模型面)。

迁移形态由 test_migrations::test_0044_* 覆盖;本文件钉模型/库层约束:
删环境级联部署行、项目默认环境置空;(基础服务, 环境) 唯一;默认环境
至多一行;环境响应带 is_default、不再有 visibility。
"""
from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core import db as db_module
from app.models import Deployment, Environment, Project

from .helpers import register_and_login


async def _env(s, name: str, *, is_default: bool = False) -> int:
    env = Environment(name=name, description="", lines={},
                      is_default=is_default)
    s.add(env)
    await s.flush()
    return env.id


async def test_env_delete_cascades_deployments_and_nulls_project_default(
        client, fresh_db):
    async with db_module.SessionLocal() as s:
        env_id = await _env(s, "s20-dev")
        s.add(Deployment(base_service="fin", env_id=env_id,
                         base_url="http://fin-dev"))
        proj = Project(name="s20-proj", default_environment_id=env_id)
        s.add(proj)
        await s.commit()
        pid = proj.id

    async with db_module.SessionLocal() as s:
        await s.delete(await s.get(Environment, env_id))
        await s.commit()

    async with db_module.SessionLocal() as s:
        left = (await s.execute(select(Deployment).where(
            Deployment.env_id == env_id))).scalars().all()
        assert left == []                         # 部署行随环境删除
        proj = await s.get(Project, pid)
        assert proj.default_environment_id is None  # 链路落到下一位


async def test_deployment_unique_per_service_env(client, fresh_db):
    async with db_module.SessionLocal() as s:
        env_id = await _env(s, "s20-uq")
        s.add(Deployment(base_service="fin", env_id=env_id,
                         base_url="http://a"))
        await s.commit()
    with pytest.raises(IntegrityError):
        async with db_module.SessionLocal() as s:
            s.add(Deployment(base_service="fin", env_id=env_id,
                             base_url="http://b"))
            await s.commit()


async def test_at_most_one_default_environment(client, fresh_db):
    async with db_module.SessionLocal() as s:
        await _env(s, "s20-d1", is_default=True)
        await s.commit()
    with pytest.raises(IntegrityError):
        async with db_module.SessionLocal() as s:
            await _env(s, "s20-d2", is_default=True)
            await s.commit()


async def test_environment_view_has_is_default_no_visibility(
        client, fresh_db):
    h = await register_and_login(client, "s20_admin", "pw123456")
    r = await client.post("/api/environments", headers=h, json={
        "name": "s20-view", "description": "", "lines": {}})
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["is_default"] is False
    assert "visibility" not in out
