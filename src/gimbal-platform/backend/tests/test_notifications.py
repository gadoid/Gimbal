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


async def test_list_pagination_envelope(client: AsyncClient):
    """2026-09-23 分页批次:page/page_size/total 信封;越界页回空不报错。"""
    admin = await _mk_user(client, "notify_pager")
    from app.core import db as db_module
    from app.services import notifications as svc

    async with db_module.SessionLocal() as s:
        uid = 1  # 本测试新库的首位用户
        for i in range(5):
            await svc.create_notification(
                s, user_id=uid, type_="announcement",
                title=f"p{i}", body="")

    r = await client.get(
        "/api/notifications", headers=admin,
        params={"page": 1, "page_size": 2})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 5 and body["page"] == 1 and body["pageSize"] == 2
    assert [i["title"] for i in body["items"]] == ["p4", "p3"]

    r = await client.get(
        "/api/notifications", headers=admin,
        params={"page": 3, "page_size": 2})
    assert [i["title"] for i in r.json()["items"]] == ["p0"]

    r = await client.get(
        "/api/notifications", headers=admin,
        params={"page": 9, "page_size": 2})
    assert r.status_code == 200 and r.json()["items"] == []

    # 边界校验:负/超上限/零页码一律 422,不打到 DB(LIMIT 负数会 500)
    for bad in ({"page_size": -1}, {"page_size": 201}, {"page": 0}):
        r = await client.get("/api/notifications", headers=admin, params=bad)
        assert r.status_code == 422, f"{bad} 本该被拒"


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


async def test_notify_finished_name_and_id(client: AsyncClient):
    """执行终态通知:name + id 一起给,title=name(着重)、body 前缀 id。

    三条 label 路径:执行快照 name → 存量空快照查活场景行补 →
    场景已删回落 scenario_id。
    """
    from app.core import db as db_module
    from app.models.composer_scenario import ComposerScenario
    from app.models.execution import Execution, STATUS_DONE
    from app.services.run_dispatcher import _notify_finished

    async with db_module.SessionLocal() as s:
        from sqlalchemy import select

        from .helpers import ensure_fk_users
        await ensure_fk_users(s, 1)  # PG 强制 FK:owner_id=1 需垫
        # 活场景行(供空快照兜底查名;_notify_finished 只读
        # payload.definition.meta.name,payload 造最小形即可)
        s.add(ComposerScenario(
            scenario_id="sc-notify-alive", owner_id=1, owner_name="垫底",
            visibility="private",
            payload={"definition": {"meta": {"name": "活行场景名"}}}))
        # 三条单发执行:有快照名 / 空快照+场景存活 / 空快照+场景已删
        for sid, snap in (
            ("sc-notify-snap", "快照场景名"),
            ("sc-notify-alive", ""),
            ("sc-notify-gone", ""),
        ):
            s.add(Execution(
                scenario_id=sid, scenario_name=snap, owner_id=1,
                status="running", total_runs=2, passed=2, failed=0,
                batch_id=None, config_json={}))
        await s.commit()
        exec_ids = {
            row.scenario_id: row.id for row in (await s.execute(
                select(Execution).where(
                    Execution.scenario_id.like("sc-notify-%")))).scalars()}

    async with db_module.SessionLocal() as s:
        from sqlalchemy import select
        for ex in (await s.execute(select(Execution).where(
                Execution.scenario_id.like("sc-notify-%")))).scalars():
            await _notify_finished(ex, STATUS_DONE)

    async with db_module.SessionLocal() as s:
        from sqlalchemy import select
        from app.models import Notification
        rows = {r.link: r for r in (await s.execute(
            select(Notification).where(Notification.link.in_(
                [f"/executions/{i}" for i in exec_ids.values()])))).scalars()}
        snap_n = rows[f"/executions/{exec_ids['sc-notify-snap']}"]
        assert snap_n.title == "执行完成:快照场景名", snap_n.title
        assert snap_n.body == "sc-notify-snap · 2 通过 / 0 失败", snap_n.body
        alive_n = rows[f"/executions/{exec_ids['sc-notify-alive']}"]
        assert alive_n.title == "执行完成:活行场景名", alive_n.title
        assert alive_n.body.startswith("sc-notify-alive · "), alive_n.body
        gone_n = rows[f"/executions/{exec_ids['sc-notify-gone']}"]
        assert gone_n.title == "执行完成:sc-notify-gone", gone_n.title
        assert gone_n.body.startswith("sc-notify-gone · "), gone_n.body
