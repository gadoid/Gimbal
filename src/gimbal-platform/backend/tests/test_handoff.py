"""资源分发(F1,2026-09-23 批次)回归。

方案 §1.9 T1–T8:正常分发/冲突后缀/越权/目标无效/悬浮标签数据源/
销账/副本独立;外加 roster 端点与 handoff_received 事件。
"""
from __future__ import annotations

from httpx import AsyncClient

from .helpers import make_draft, register_and_login


async def _mk_user(client: AsyncClient, name: str) -> dict[str, str]:
    return await register_and_login(client, name, f"{name}-pass-123")


async def test_handoff_normal_and_badge_flow(client: AsyncClient):
    """T1/T6/T7:正常分发 → 通知入库 → handoff-unread 可见 → read 销账。"""
    # 首注册者为 admin,垫掉 bootstrap;alice=2, bob=3
    await _mk_user(client, "handoff_admin")
    alice = await _mk_user(client, "alice")
    bob = await _mk_user(client, "bob")
    await client.post(
        "/api/scenarios", headers=alice,
        json=make_draft("sc-hd-a", name="订单查询"))

    # bob 先有一个同名场景 → 冲突后缀(T2)
    await client.post(
        "/api/scenarios", headers=bob,
        json=make_draft("sc-hd-bob-old", name="订单查询"))

    r = await client.post("/api/handoff", headers=alice, json={
        "resource_type": "scenario", "resource_id": "sc-hd-a",
        "target_user_id": 3})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "ok"
    assert body["renamed"] is True
    assert body["new_name"] == "订单查询 (2)"
    new_sid = body["new_resource_id"]
    assert new_sid.startswith("sc-hd-a-copy-")

    # 悬浮标签数据源(T6)
    r = await client.get("/api/notifications/handoff-unread", headers=bob)
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["resourceId"] == new_sid
    assert items[0]["senderName"] == "alice"
    nid = items[0]["id"]

    # 销账(T7):POST /read 按 id
    r = await client.post("/api/notifications/read", headers=bob,
                          json={"ids": [nid]})
    assert r.status_code == 200
    r = await client.get("/api/notifications/handoff-unread", headers=bob)
    assert r.json()["items"] == []

    # 副本归 bob(T8 前半):bob 可读、alice 对副本无控制
    assert (await client.get(
        f"/api/scenarios/{new_sid}", headers=bob)).status_code == 200
    assert (await client.put(
        f"/api/scenarios/{new_sid}", headers=alice,
        json=make_draft(new_sid))).status_code in (403, 404)


async def test_handoff_sender_edit_does_not_leak(client: AsyncClient):
    """T8:发送方改原场景,副本不受影响(深拷贝快照)。"""
    await _mk_user(client, "handoff_admin2")
    alice = await _mk_user(client, "alice2")
    bob = await _mk_user(client, "bob2")
    await client.post(
        "/api/scenarios", headers=alice,
        json=make_draft("sc-hd-ind", name="独立副本"))
    r = await client.post("/api/handoff", headers=alice, json={
        "resource_id": "sc-hd-ind", "target_user_id": 3})
    new_sid = r.json()["new_resource_id"]
    assert r.json()["renamed"] is False

    # alice 改原场景名
    await client.put(
        "/api/scenarios/sc-hd-ind", headers=alice,
        json=make_draft("sc-hd-ind", name="原名已改"))
    # 副本名不变、bob 可编辑
    r = await client.get(f"/api/scenarios/{new_sid}", headers=bob)
    assert r.json()["meta"]["name"] == "独立副本"
    assert (await client.put(
        f"/api/scenarios/{new_sid}", headers=bob,
        json=make_draft(new_sid, name="bob 的副本"))).status_code == 200


async def test_handoff_auth_and_target_errors(client: AsyncClient):
    """T4/T5:非 owner 403;目标无效/是自己 422;resource_type 422。"""
    await _mk_user(client, "handoff_admin3")
    alice = await _mk_user(client, "alice3")
    carol = await _mk_user(client, "carol3")
    await client.post(
        "/api/scenarios", headers=alice, json=make_draft("sc-hd-perm"))

    # carol(非 owner、非 admin)分发 alice 的场景 → 403
    r = await client.post("/api/handoff", headers=carol, json={
        "resource_id": "sc-hd-perm", "target_user_id": 4})
    assert r.status_code == 403
    # 目标不存在 → 422;目标是发起人自己 → 422
    r = await client.post("/api/handoff", headers=alice, json={
        "resource_id": "sc-hd-perm", "target_user_id": 9999})
    assert r.status_code == 422
    r = await client.post("/api/handoff", headers=alice, json={
        "resource_id": "sc-hd-perm", "target_user_id": 2})
    assert r.status_code == 422
    # resource_type 不支持 → 422
    r = await client.post("/api/handoff", headers=alice, json={
        "resource_type": "dataset", "resource_id": "ds-x",
        "target_user_id": 3})
    assert r.status_code == 422
    # 资源不存在 → 404
    r = await client.post("/api/handoff", headers=alice, json={
        "resource_id": "sc-none", "target_user_id": 3})
    assert r.status_code == 404


async def test_handoff_activity_event_and_roster(client: AsyncClient):
    """T10 事件(actor=接收方,detail 带发送方)+ roster 端点。"""
    from sqlalchemy import select

    from app.core import db as db_module
    from app.models import ActivityEvent

    await _mk_user(client, "handoff_admin4")
    alice = await _mk_user(client, "alice4")
    bob = await _mk_user(client, "bob4")
    await client.post(
        "/api/scenarios", headers=alice, json=make_draft("sc-hd-ev"))

    await client.post("/api/handoff", headers=alice, json={
        "resource_id": "sc-hd-ev", "target_user_id": 3})

    async with db_module.SessionLocal() as s:
        rows = (await s.execute(select(ActivityEvent).where(
            ActivityEvent.kind == "scenario.handoff_received"))
        ).scalars().all()
    assert len(rows) == 1
    ev = rows[0]
    assert ev.actor_id == 3, "actor 必须是接收方(时间线归属)"
    assert ev.detail["senderId"] == 2
    assert ev.detail["senderName"] == "alice4"

    # /api/activity 里 bob 能看到该事件
    r = await client.get("/api/activity", headers=bob)
    evs = [e for e in r.json()["events"] if e["kind"] == "scenario"]
    assert any(e["action"] == "scenario.handoff_received"
               and e["detail"]["senderName"] == "alice4" for e in evs)

    # roster:member 可调、排除自己、字段最小
    r = await client.get("/api/users/roster", headers=alice)
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    ids = {u["id"] for u in items}
    assert 3 in ids and 2 not in ids, "含 bob、排除自己(alice)"
    assert set(items[0]) == {"id", "username", "display_name"}
