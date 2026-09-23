"""M5-3 活动时间线服务端合流(/api/activity)+ F3 事件日志化(2026-09-23)。

读侧:三源合并倒序、owner 隔离、无时间戳执行跳过。
F3 起 scenario 面走 activity_events(写入点:edit/rename/save_as;
创建不落事件 —— 方案 kind 域拍板只有四值,首编辑的 autosave 会补上)。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from tests.helpers import make_draft, register_and_login

UTC = timezone.utc


async def _mk_exec(s, *, sid, owner_id, status_="done", finished=None, started=None):
    from app.models.execution import Execution

    s.add(Execution(
        scenario_id=sid, owner_id=owner_id, status=status_,
        total_runs=1, passed=1 if status_ == "done" else 0,
        failed=0 if status_ == "done" else 1,
        finished_at=finished, started_at=started, config_json={},
    ))


async def test_activity_merges_three_sources_desc(client):
    h = await register_and_login(client, "m5act", "pw123456")
    from app.core import db as db_module

    t0 = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)
    async with db_module.SessionLocal() as s:
        from app.models import ActivityEvent

        # F3:场景事件直接落 activity_events(读侧按 actor 检索,
        # 公共/私有之分不再由读侧过滤 —— 事件归属即时间线归属)
        s.add(ActivityEvent(
            actor_id=1, kind="scenario.edit", resource_type="scenario",
            resource_id="sc-act-a", detail={"name": "A"}, created_at=t0))
        # 执行:done@13:00 / queued 无时间戳(不进轴)
        await _mk_exec(s, sid="sc-act-a", owner_id=1, status_="done",
                       finished=t0 + timedelta(hours=1))
        await _mk_exec(s, sid="sc-act-a", owner_id=1, status_="queued")
        await s.commit()

    r = await client.get("/api/activity", headers=h, params={"limit": 40})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["sources"] == {"executions": True, "scenarios": True,
                               "adaptations": True}
    kinds = [(e["kind"], e.get("scenarioId") or e.get("name")) for e in body["events"]]
    assert ("scenario", "sc-act-a") in kinds
    assert ("execution", "sc-act-a") in kinds
    assert len([k for k in kinds if k[0] == "execution"]) == 1
    # 倒序:执行(13:00)在场景事件(12:00)前
    assert kinds[0][0] == "execution"
    # F3:子动作与 detail 透传
    scen_ev = next(e for e in body["events"] if e["kind"] == "scenario")
    assert scen_ev["action"] == "scenario.edit"
    assert scen_ev["detail"]["name"] == "A"


async def test_activity_owner_isolation(client):
    """我的活动轴只含本人的执行/场景。"""
    alice = await register_and_login(client, "m5act_a", "pw123456")
    await register_and_login(client, "m5act_b", "pw123456")  # bob(id=2)

    from app.core import db as db_module

    t0 = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)
    async with db_module.SessionLocal() as s:
        await _mk_exec(s, sid="sc-x", owner_id=2, status_="done",
                       finished=t0)  # bob 的执行
        await s.commit()

    r = await client.get("/api/activity", headers=alice)
    body = r.json()
    assert body["events"] == []  # bob 的执行不进 alice 的轴


async def test_activity_requires_auth(client):
    r = await client.get("/api/activity")
    assert r.status_code == 401


# ── F3(2026-09-23):写入点 + autosave 短窗合并 + best-effort ───────
async def test_activity_write_points_and_coalesce(client):
    """常规保存 → edit(同窗合并);改名 → rename;复制 → save_as。
    创建不落事件(kind 域拍板只有四值)。"""
    h = await register_and_login(client, "f3w", "pw123456")
    await client.post(
        "/api/scenarios", headers=h, json=make_draft("sc-f3"))

    # 同名 PUT ×2(模拟 autosave 连发)→ 短窗内合并为 1 条 edit
    assert (await client.put(
        "/api/scenarios/sc-f3", headers=h, json=make_draft("sc-f3"))
    ).status_code == 200
    assert (await client.put(
        "/api/scenarios/sc-f3", headers=h, json=make_draft("sc-f3"))
    ).status_code == 200
    # 改名 → rename
    assert (await client.put(
        "/api/scenarios/sc-f3", headers=h, json=make_draft("sc-f3", name="Renamed"))
    ).status_code == 200
    # 复制 → save_as(属新副本资源)
    assert (await client.post(
        "/api/scenarios/sc-f3/copy", headers=h)
    ).status_code == 201

    from sqlalchemy import select

    from app.core import db as db_module
    from app.models import ActivityEvent

    async with db_module.SessionLocal() as s:
        rows = (await s.execute(
            select(ActivityEvent).order_by(ActivityEvent.id))).scalars().all()
    by_kind = {}
    for r in rows:
        by_kind.setdefault(r.kind, []).append(r.detail or {})

    assert list(by_kind) == ["scenario.edit", "scenario.rename",
                             "scenario.save_as"], list(by_kind)
    assert len(by_kind["scenario.edit"]) == 1, "同窗两次保存必须合并"
    assert by_kind["scenario.edit"][0]["name"] == "Test"
    rn = by_kind["scenario.rename"][0]
    assert (rn["oldName"], rn["newName"]) == ("Test", "Renamed")
    sa = by_kind["scenario.save_as"][0]
    assert sa["sourceScenarioId"] == "sc-f3"
    assert sa["name"] == "Renamed (副本)"

    # /api/activity 的 scenario 事件带 action 子动作(同秒写入的 at 相同,
    # 倒序在同秒内不稳定 —— 断言集合不断言顺序)
    body = (await client.get("/api/activity", headers=h)).json()
    actions = sorted(e["action"] for e in body["events"] if e["kind"] == "scenario")
    assert actions == ["scenario.edit", "scenario.rename", "scenario.save_as"]


async def test_activity_record_best_effort(monkeypatch):
    """record 失败不上抛(audit.record 口径)。"""
    from app.core import db as db_module
    from app.services import activity

    async with db_module.SessionLocal() as s:

        async def _boom():
            raise RuntimeError("db down")

        monkeypatch.setattr(s, "commit", _boom)
        await activity.record(
            s, actor_id=None, kind="scenario.edit",
            resource_type="scenario", resource_id="sc-x",
            detail={"name": "x"})  # 不抛 = 通过
