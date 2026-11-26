"""UPC §13.1 生命周期端点 + 默认空间切换(按代码惯例推断实施;依据 =
模型状态机常量/docstring「处置流程随 M2+ 实现」、DB 触发器 ④(恢复
active 须有效 admin,延迟约束)/⑥(每用户至少一个默认私有空间)、
uq_projects_private_default 部分唯一索引与既有 R3-6/评审四轮归档闸)。"""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import text as sa_text
from sqlalchemy.exc import IntegrityError

from app.core import db as db_module
from tests.helpers import register_and_login, role_headers


# ── 归档(normal):管理员可归档;成员写冻结;恢复解冻 ────────────────

async def test_normal_project_archive_restore_roundtrip(client: AsyncClient):
    """§13.1:admin 归档 → archived(成员写 409 project_not_active)
    → admin 恢复 → active(成员写恢复);状态机双向、审计落账。"""
    from tests.test_authz_s14_projects import _create_project

    h_admin = await role_headers(client, "r13a_adm", role="admin")
    h_own = await role_headers(client, "r13a_own", role="user")
    uid_own = (await client.get("/api/auth/me", headers=h_own)).json()["user"]["id"]
    pid = (await _create_project(
        client, h_admin, "r13a-proj", uid_own))["id"]

    # 归档:项目管理员
    r = await client.post(f"/api/projects/{pid}/archive", headers=h_own)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "archived"
    # 归档中:成员管理写冻结(§13.1 闸;非生命周期面)
    r = await client.patch(f"/api/projects/{pid}",
                           headers=h_own, json={"name": "改名"})
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "project_not_active"
    # 重复归档 → 状态机单向闸 409
    r = await client.post(f"/api/projects/{pid}/archive", headers=h_own)
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "project_not_active"

    # 恢复:解冻(不受归档闸)
    r = await client.post(f"/api/projects/{pid}/restore", headers=h_own)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "active"
    r = await client.patch(f"/api/projects/{pid}",
                           headers=h_own, json={"name": "改名"})
    assert r.status_code == 200, r.text
    # 恢复非归档项目 → 409 project_not_archived
    r = await client.post(f"/api/projects/{pid}/restore", headers=h_own)
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "project_not_archived"


async def test_archive_gates_non_admin_and_public(client: AsyncClient):
    """归档门:normal 非管理员成员 403、非成员 404;public 恒 active
    409(Admin+ 治理面同样不可归档公共项目)。"""
    from tests.test_authz_s14_projects import _create_project

    h_admin = await role_headers(client, "r13b_adm", role="admin")
    h_a = await role_headers(client, "r13b_a", role="user")
    h_out = await role_headers(client, "r13b_out", role="user")
    a_uid = (await client.get("/api/auth/me", headers=h_a)).json()["user"]["id"]
    pid = (await _create_project(
        client, h_admin, "r13b-proj", a_uid))["id"]
    r = await client.post(f"/api/projects/{pid}/members",
                          headers=h_a, json={"userId": (
        await client.get("/api/auth/me", headers=h_out)).json()["user"]["id"],
        "role": "member"})
    assert r.status_code == 201, r.text

    # 成员(非管理员)→ 403;非成员 Admin+ → 404(D1 不旁路)
    r = await client.post(f"/api/projects/{pid}/archive", headers=h_out)
    assert r.status_code == 403, r.text
    r = await client.post(f"/api/projects/{pid}/archive", headers=h_admin)
    assert r.status_code == 404, r.text

    # 公共项目:唯一行恒 active
    async with db_module.SessionLocal() as s:
        pub_id = (await s.execute(sa_text(
            "SELECT id FROM projects WHERE kind='public'"))).scalar_one()
    r = await client.post(f"/api/projects/{pub_id}/archive", headers=h_admin)
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "public_project_protected"


# ── 恢复的库层兜底:触发器 ④(直写路径)────────────────────────────

async def test_restore_requires_valid_admin_db_guard(client: AsyncClient):
    """绕过 API 直写(存量/竞态面):无有效管理员的 normal 项目置
    active → 延迟触发器 ④ 提交期拒绝(§20 不变量,API 端点的人话
    前置检与之同口径;并发竞态由同一触发器兜底)。触发器 ⑤ 使
    「active 项目的唯一管理员停用」本身不可达 —— 先归档(合法)、
    再停用管理员(archived 不受 ⑤)、再直写恢复,④ 兜底。"""
    from app.models.project import Project
    from tests.test_authz_s14_projects import _create_project

    h_admin = await role_headers(client, "r13c_adm", role="admin")
    h_a = await role_headers(client, "r13c_a", role="user")
    a_uid = (await client.get("/api/auth/me", headers=h_a)).json()["user"]["id"]
    pid = (await _create_project(
        client, h_admin, "r13c-proj", a_uid))["id"]
    # ① 归档(唯一管理员在位,合法)
    r = await client.post(f"/api/projects/{pid}/archive", headers=h_a)
    assert r.status_code == 200, r.text
    # ② 归档态下停用管理员(触发器 ⑤ 只管 active 项目 → 放行)
    async with db_module.SessionLocal() as s:
        await s.execute(sa_text(
            "UPDATE users SET is_active=false WHERE id=:u"), {"u": a_uid})
        await s.commit()
    # ③ 直写恢复(无有效管理员)→ 触发器 ④ 提交期拒绝
    async with db_module.SessionLocal() as s:
        proj = await s.get(Project, pid)
        proj.status = Project.STATUS_ACTIVE
        with pytest.raises(IntegrityError):
            await s.commit()
        await s.rollback()


# ── 私有空间生命周期 + 默认空间切换(§4/触发器 ⑥)──────────────────

async def test_private_archive_and_default_protection(client: AsyncClient):
    """私有空间:所有者可归档非默认空间;**默认空间不可归档**
    (409 default_space_not_archivable —— 触发器 ⑥ 只保存在性,默认
    空间是新建场景的缺省落点,归档会让缺省写入面全冻结);他人 404。"""
    h = await register_and_login(client, "r13d_own", "pw123456")
    uid = (await client.get("/api/auth/me", headers=h)).json()["user"]["id"]
    # 第二私有空间(非默认;每用户可多个私有空间,§4)
    r = await client.post("/api/projects", headers=h,
                          json={"name": "第二空间", "description": "",
                                "kind": "private"})
    assert r.status_code == 201, r.text
    alt_id = r.json()["id"]
    async with db_module.SessionLocal() as s:
        rows = (await s.execute(sa_text(
            "SELECT id, is_default FROM projects "
            "WHERE kind='private' AND owner_id=:u ORDER BY id"),
            {"u": uid})).all()
    default_id = next(x.id for x in rows if x.is_default)
    assert default_id and alt_id

    # 默认空间 → 409
    r = await client.post(f"/api/projects/{default_id}/archive", headers=h)
    assert r.status_code == 409, r.text
    assert (r.json()["detail"]["code"]
            == "default_space_not_archivable")
    # 非默认空间 → 归档成功;他人(不可见)→ 404
    r = await client.post(f"/api/projects/{alt_id}/archive", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "archived"
    h_other = await register_and_login(client, "r13d_other", "pw123456")
    r = await client.post(f"/api/projects/{alt_id}/archive",
                          headers=h_other)
    assert r.status_code == 404, r.text
    # 归档空间不可成为默认(set-default → 409)
    r = await client.post(f"/api/projects/{alt_id}/set-default", headers=h)
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "project_not_active"
    # 恢复(所有者)→ 再切换默认 → 旧默认让位(恰一个默认)
    r = await client.post(f"/api/projects/{alt_id}/restore", headers=h)
    assert r.status_code == 200, r.text
    r = await client.post(f"/api/projects/{alt_id}/set-default", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["isDefault"] is True
    async with db_module.SessionLocal() as s:
        n_def = (await s.execute(sa_text(
            "SELECT count(*) FROM projects "
            "WHERE kind='private' AND owner_id=:u AND is_default"),
            {"u": uid})).scalar_one()
    assert n_def == 1, "部分唯一索引:切换后恰一个默认空间"
    # 原默认空间现在可归档(已不是默认)
    r = await client.post(f"/api/projects/{default_id}/archive", headers=h)
    assert r.status_code == 200, r.text


async def test_set_default_gates(client: AsyncClient):
    """set-default 门:normal/public 无默认语义 409;幂等(已是默认
    原样 200);触发器 ⑥ 全程成立(切换不落「零默认」窗口)。"""
    from tests.test_authz_s14_projects import _create_project

    h_admin = await role_headers(client, "r13e_adm", role="admin")
    h_a = await role_headers(client, "r13e_a", role="user")
    a_uid = (await client.get("/api/auth/me", headers=h_a)).json()["user"]["id"]
    pid = (await _create_project(client, h_admin, "r13e-proj", a_uid))["id"]
    r = await client.post(f"/api/projects/{pid}/set-default", headers=h_a)
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "default_space_private_only"

    async with db_module.SessionLocal() as s:
        pub_id = (await s.execute(sa_text(
            "SELECT id FROM projects WHERE kind='public'"))).scalar_one()
    r = await client.post(f"/api/projects/{pub_id}/set-default",
                          headers=h_admin)
    assert r.status_code == 409, r.text

    # 幂等:自己的默认空间 set-default → 200 且 isDefault True
    async with db_module.SessionLocal() as s:
        my_default = (await s.execute(sa_text(
            "SELECT id FROM projects WHERE kind='private' "
            "AND owner_id=:u AND is_default"), {"u": a_uid})).scalar_one()
    r = await client.post(f"/api/projects/{my_default}/set-default",
                          headers=h_a)
    assert r.status_code == 200, r.text
    assert r.json()["isDefault"] is True
