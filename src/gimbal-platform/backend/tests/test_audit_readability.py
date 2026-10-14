"""审计可读性(2026-10-14 平台侧问题 2)—— 写侧快照收口。

resource_name 随 detail 落库(与 actor_name 同思路:资源事后删除,审计
仍可读);user.role_change 留 role_from/is_active_from 前值,读侧渲染
「从 X 改为 Y」。读侧(中文标签/渲染模板)在前端 auditText.ts 单测覆盖。
"""
from __future__ import annotations

from tests.helpers import register_and_login


async def _latest(client, admin, action: str) -> dict:
    r = await client.get("/api/admin/audit-logs", headers=admin,
                         params={"action": action})
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert items, f"expected audit rows for {action}"
    return items[0]


async def test_audit_snapshots_resource_name_and_from_values(client):
    admin = await register_and_login(client, "rk_admin", "pw123456")
    # member 走 admin 开号(POST /users)—— user.create 审计只记特权写,
    # 自助注册 /auth/register 不落审计
    r = await client.post("/api/users", headers=admin,
                          json={"username": "rk_member", "password": "Test2026!"})
    assert r.status_code == 201, r.text

    # user.create → resource_name 快照 = 用户名
    row = await _latest(client, admin, "user.create")
    assert row["detail"]["resource_name"] == "rk_member"

    r = await client.get("/api/users", headers=admin, params={"q": "rk_member"})
    uid = next(u["id"] for u in r.json()["items"]
               if u["username"] == "rk_member")

    # 角色变更 user → member:审计留 from/to + 名称快照
    r = await client.patch(f"/api/users/{uid}", headers=admin,
                           json={"role": "member"})
    assert r.status_code == 200, r.text
    row = await _latest(client, admin, "user.role_change")
    d = row["detail"]
    assert d["resource_name"] == "rk_member"
    assert d["role_from"] == "user" and d["role"] == "member"
    assert d["changed"] == ["role"]

    # 停用:is_active_from 留前值
    r = await client.patch(f"/api/users/{uid}", headers=admin,
                           json={"is_active": False})
    assert r.status_code == 200, r.text
    row = await _latest(client, admin, "user.role_change")
    assert row["detail"]["is_active_from"] is True
    assert row["detail"]["is_active"] is False

    # 公告:resource_name = 标题(resource_id 仍为空)
    r = await client.post("/api/notifications/announcements", headers=admin,
                          json={"title": "停机维护", "body": "今晚", "hours": 0})
    assert r.status_code == 201, r.text
    row = await _latest(client, admin, "announcement.publish")
    assert row["detail"]["resource_name"] == "停机维护"
    assert row["resourceId"] is None


async def test_record_resource_name_merge_semantics(client):
    """record(resource_name=...) 进 detail;不覆盖调用方自带键,空串不落。"""
    admin = await register_and_login(client, "rk2_admin", "pw123456")
    from app.core import db as db_module
    from app.services import audit as audit_svc

    async with db_module.SessionLocal() as s:
        await audit_svc.record(
            s, actor_id=None, actor_name="系统", action="announcement.publish",
            resource_name="快照名",
            detail={"title": "t1", "resource_name": "自带名"},
        )
        await audit_svc.record(
            s, actor_id=None, actor_name="系统", action="announcement.publish",
            resource_name="", detail={"title": "t2"},
        )
    r = await client.get("/api/admin/audit-logs", headers=admin,
                         params={"action": "announcement.publish"})
    items = r.json()["items"]  # 新→旧:t2 在前
    assert items[0]["detail"] == {"title": "t2"}
    assert items[1]["detail"]["resource_name"] == "自带名"
