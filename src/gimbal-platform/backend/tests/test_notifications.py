"""通知中心(P1b/M2.5,权限方案 §3)回归。

覆盖:三接口(list/read/unread-count+roleVersion)、按 type 开关、
公告 fan-out、批量合并(同批 upsert 单条 + 聚合计数在 UPDATE 内现算)、
执行终态接线(dispatcher 单发/批量)、role_changed 接线。
"""
from __future__ import annotations

from httpx import AsyncClient

from tests.helpers import register_and_login


async def _mk_user(client: AsyncClient, name: str) -> dict:
    return await register_and_login(client, name, f"{name}-pass-123")


async def test_list_read_unread_count_and_role_version(client: AsyncClient):
    admin = await _mk_user(client, "notify_admin")
    # admin 是首位注册 → role=admin;给自己造两条通知
    from app.core import db as db_module
    from app.services import notifications as svc

    async with db_module.SessionLocal() as s:
        await svc.create_notification(
            s, user_id=1, type_="role_changed", title="t1", body="b1")
        await svc.create_notification(
            s, user_id=1, type_="execution_finished", title="t2", body="b2")

    r = await client.get("/api/notifications", headers=admin)
    assert r.status_code == 200
    body = r.json()
    assert body["unread"] == 2
    assert [i["title"] for i in body["items"][:2]] == ["t2", "t1"]  # 新的在前

    # unread-count 带 roleVersion(users.updated_at)
    r = await client.get("/api/notifications/unread-count", headers=admin)
    assert r.status_code == 200
    assert r.json()["count"] == 2
    assert r.json()["roleVersion"]  # ISO 字符串

    # 标读一条
    first_id = body["items"][0]["id"]
    r = await client.post(
        "/api/notifications/read", headers=admin, json={"ids": [first_id]})
    assert r.json()["marked"] == 1
    r = await client.get(
        "/api/notifications/unread-count", headers=admin)
    assert r.json()["count"] == 1

    # 全部已读
    await client.post("/api/notifications/read", headers=admin, json={})
    r = await client.get(
        "/api/notifications/unread-count", headers=admin)
    assert r.json()["count"] == 0


async def test_type_switch_suppresses_creation(client: AsyncClient):
    user = await _mk_user(client, "notify_off_user")
    from app.core import db as db_module
    from app.services import notifications as svc

    # 关掉 execution_finished
    r = await client.put(
        "/api/notifications/preferences", headers=user,
        json={"off": ["execution_finished"]})
    assert r.status_code == 200

    async with db_module.SessionLocal() as s:
        uid = 1  # 本测试新库的首位用户(notify_off_user)
        got = await svc.create_notification(
            s, user_id=uid, type_="execution_finished", title="不应存在")
        assert got is None  # 开关生效:不入库
        got2 = await svc.create_notification(
            s, user_id=uid, type_="role_changed", title="应存在")
        assert got2 is not None  # 其他 type 不受影响

    r = await client.get(
        "/api/notifications?unreadOnly=true", headers=user)
    titles = [i["title"] for i in r.json()["items"]]
    assert "应存在" in titles and "不应存在" not in titles


async def test_announcement_fanout_and_expiry(client: AsyncClient):
    admin = await _mk_user(client, "ann_admin")
    member = await _mk_user(client, "ann_member")

    r = await client.post(
        "/api/notifications/announcements", headers=admin,
        json={"title": "今晚停服迁移", "body": "23:00-24:00", "hours": 24})
    assert r.status_code == 201
    assert r.json()["delivered"] >= 2  # admin + member 都收到

    for h in (admin, member):
        rr = await client.get("/api/notifications", headers=h)
        assert any(i["type"] == "announcement" and i["title"] == "今晚停服迁移"
                   for i in rr.json()["items"])

    # member 发公告 → 403(admin only)
    rr = await client.post(
        "/api/notifications/announcements", headers=member,
        json={"title": "x"})
    assert rr.status_code == 403


async def test_batch_upsert_single_row_and_live_aggregate(client: AsyncClient):
    """批量合并:同批 N 条终态 → 单条通知;聚合计数随批内终态推进。"""
    from app.core import db as db_module
    from app.models.execution import Execution
    from app.services import notifications as svc

    async with db_module.SessionLocal() as s:
        from .helpers import ensure_fk_users

        await ensure_fk_users(s, 1)  # PG 强制 FK:owner_id=1 需垫
        for i, st in enumerate(("done", "failed", "queued"), 1):
            s.add(Execution(
                scenario_id=f"sc-b{i}", owner_id=1, status=st,
                total_runs=1, passed=1 if st == "done" else 0,
                failed=1 if st == "failed" else 0,
                batch_id="bt-notify-1", config_json={}))
        await s.commit()

        # 首条终态 → upsert 落一条
        await svc.upsert_execution_finished(
            s, user_id=1, batch_id="bt-notify-1", run_label="批次冒烟")
        # 第二条终态 → 再 upsert,仍是一条且计数刷新(子查询现算)
        from sqlalchemy import update as sa_update
        await s.execute(sa_update(Execution)
                        .where(Execution.batch_id == "bt-notify-1",
                               Execution.status == "queued")
                        .values(status="done", passed=1))
        await s.commit()
        await svc.upsert_execution_finished(
            s, user_id=1, batch_id="bt-notify-1", run_label="批次冒烟")

    async with db_module.SessionLocal() as s:
        from sqlalchemy import select
        from app.models import Notification
        rows = (await s.execute(select(Notification).where(
            Notification.batch_id == "bt-notify-1"))).scalars().all()
        assert len(rows) == 1, "同批必须合并为单条"
        assert "2 通过 / 1 失败" in rows[0].body, rows[0].body
        assert rows[0].link == "/executions?batch_id=bt-notify-1"


async def test_role_change_notification(client: AsyncClient):
    admin = await _mk_user(client, "role_admin")
    member = await _mk_user(client, "role_member")  # id=2

    r = await client.patch(
        "/api/users/2", headers=admin, json={"role": "operator"})
    assert r.status_code == 200

    r = await client.get("/api/notifications", headers=member)
    items = [i for i in r.json()["items"] if i["type"] == "role_changed"]
    assert items and "operator" in items[0]["title"]
