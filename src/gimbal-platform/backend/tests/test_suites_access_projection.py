"""01-03 §4.2 回归:套件能力投影按普通/公共项目分权。

修前事实(known-issue 登记):``_access_and_caps`` 把 ``project_id``
非空的非属主一律标 ``access='public'``(普通项目概念诞生前的投影)
⇒ 普通项目非属主成员详情页只读、无运行钮,而写闸走表 B contributor
放行;前端按 access='public' 渲染的「复制到我的」在普通项目 fork
404(必然失败入口)。修后:普通项目 = access 'member',canEdit/canRun
随表 B 真值;canShare 恒 False(跨区复制策略未定);公共读者不变。
"""
from __future__ import annotations

from sqlalchemy import select

from app.core import db as db_module
from app.models.project import Project, ProjectMember
from app.models.user import User
from tests.helpers import register_and_login, role_headers


async def _mk_project(name: str, *, members: dict[str, str]) -> int:
    async with db_module.SessionLocal() as db:
        proj = Project(name=name, kind="normal", description="")
        db.add(proj)
        await db.flush()
        for uname, role in members.items():
            uid = (await db.execute(select(User.id).where(
                User.username == uname))).scalar_one()
            db.add(ProjectMember(project_id=proj.id, user_id=uid, role=role))
        await db.commit()
        return proj.id


async def _mk_project_suite(client, *, project: str, owner: str) -> tuple[int, int]:
    owner_h = await register_and_login(client, owner, "pw123456")
    pid = await _mk_project(project, members={owner: "member"})
    r = await client.post("/api/suites", headers=owner_h, json={
        "name": f"{project}-suite", "projectId": pid})
    assert r.status_code in (200, 201), r.text
    sid = r.json()["suiteId"]
    return sid, pid


async def _detail(client, headers, sid: int) -> dict:
    r = await client.get(f"/api/suites/{sid}", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


async def test_project_member_capability_matrix(client):
    """普通项目 admin/member/user 三角色 + 属主的能力位与表 B 一致。"""
    sid, pid = await _mk_project_suite(
        client, project="sp-m1", owner="sp_own1")
    # 三角色成员挂进项目(先注册,后补成员行)
    padm = await role_headers(client, "sp_padm1", role="user")
    mem = await role_headers(client, "sp_mem1", role="user")
    usr = await role_headers(client, "sp_usr1", role="user")
    async with db_module.SessionLocal() as db:
        for uname, role in (("sp_padm1", "admin"), ("sp_mem1", "member"),
                            ("sp_usr1", "user")):
            uid = (await db.execute(select(User.id).where(
                User.username == uname))).scalar_one()
            db.add(ProjectMember(project_id=pid, user_id=uid, role=role))
        await db.commit()

    owner_h = await register_and_login(client, "sp_own1", "pw123456")
    d = await _detail(client, owner_h, sid)
    assert d["access"] == "owner" and d["canEdit"] and d["canRun"] and d["canShare"]

    # 项目管理员 / 项目成员(表 B contributor):可写可跑,无分享位
    for h in (padm, mem):
        d = await _detail(client, h, sid)
        assert d["access"] == "member", d
        assert d["canEdit"] is True and d["canRun"] is True
        assert d["canShare"] is False, "跨区复制策略未定:不给必然失败入口"

    # 项目只读用户(user 角色):可跑不可写(表 B run=member / write=contributor)
    d = await _detail(client, usr, sid)
    assert d["access"] == "member"
    assert d["canRun"] is True and d["canEdit"] is False
    assert d["canShare"] is False


async def test_project_member_fork_404_no_dead_entry(client):
    """普通项目非属主 fork → 404(跨区复制策略未定);投影层已不给
    canShare,前端「复制到我的」只在 access='public' 渲染 —— 钉死后
    端拒绝面,前端入口面由 SuiteManage 消费 access='member' 保证。"""
    sid, pid = await _mk_project_suite(
        client, project="sp-m2", owner="sp_own2")
    mem_h = await register_and_login(client, "sp_mem2", "pw123456")
    async with db_module.SessionLocal() as db:
        uid = (await db.execute(select(User.id).where(
            User.username == "sp_mem2"))).scalar_one()
        db.add(ProjectMember(project_id=pid, user_id=uid, role="member"))
        await db.commit()
    # 成员视角:详情可读(读闸表 B member)、无分享位
    d = await _detail(client, mem_h, sid)
    assert d["access"] == "member" and d["canShare"] is False
    # 但 fork 仍 404 —— 入口若渲染必然失败,投影不给位 + 后端拒绝双钉
    r = await client.post(f"/api/suites/{sid}/fork", headers=mem_h)
    assert r.status_code == 404, r.text


async def test_non_member_detail_404(client):
    """非成员对普通项目套件:详情 404(读闸表 B member;不泄露存在性)。"""
    sid, pid = await _mk_project_suite(
        project="sp-m3", owner="sp_own3", client=client)
    outsider = await register_and_login(client, "sp_out3", "pw123456")
    r = await client.get(f"/api/suites/{sid}", headers=outsider)
    assert r.status_code == 404, r.text
