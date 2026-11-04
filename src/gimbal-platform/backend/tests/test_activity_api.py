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
                               "adaptations": True,
                               "suites": True, "integrations": True,
                               "inbound": True}
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


# ── 2026-11-03 容量语义:每类 30,不做全局截断 ──────────────────────
async def test_activity_per_kind_cap_without_global_truncation(client):
    """每类各留 limit 条(场景 35 → 30;执行 35 → 30),两类共存时
    总量 60 —— 不再有「合流后全局截 30」把单一类型外的世界挤掉。"""
    h = await register_and_login(client, "m5cap", "pw123456")
    from app.core import db as db_module

    t0 = datetime(2026, 11, 3, 8, 0, tzinfo=UTC)
    async with db_module.SessionLocal() as s:
        from app.models import ActivityEvent

        for i in range(35):
            s.add(ActivityEvent(
                actor_id=1, kind="scenario.edit", resource_type="scenario",
                resource_id=f"sc-cap-{i}", detail={"name": f"S{i}"},
                created_at=t0 + timedelta(seconds=i)))
        for i in range(35):
            await _mk_exec(s, sid=f"sc-cap-{i}", owner_id=1, status_="done",
                           finished=t0 + timedelta(seconds=i))
        await s.commit()

    body = (await client.get("/api/activity", headers=h,
                             params={"limit": 30})).json()
    kinds = [e["kind"] for e in body["events"]]
    assert kinds.count("scenario") == 30, "场景类必须恰为每类上限 30"
    assert kinds.count("execution") == 30, "执行类必须恰为每类上限 30"
    assert len(kinds) == 60, "全局不再截断 —— 两类各 30 共 60"
    # 每类留下的都是最近的:id 编号最大(时间最晚)的那批
    scen_ids = {e["scenarioId"] for e in body["events"]
                if e["kind"] == "scenario"}
    assert "sc-cap-34" in scen_ids and "sc-cap-0" not in scen_ids


# ── 2026-11-03:入站调用(inbound.run)入轴 ─────────────────────────
async def test_activity_inbound_source(client):
    """经个人令牌触发的执行/临时调用上轴(webhook v4 §7.3):
    tokenId/tokenName/clientRef 顶层透出,临时调用 detail 带全量 steps;
    owner 隔离;平台令牌不在此面(写入点就不写个人轴)。"""
    h1 = await register_and_login(client, "m5inb", "pw123456")   # id=1
    h2 = await register_and_login(client, "m5inb2", "pw123456")  # id=2(他人)
    from app.core import db as db_module

    t0 = datetime(2026, 11, 3, 9, 0, tzinfo=UTC)
    async with db_module.SessionLocal() as s:
        from app.models import ActivityEvent

        s.add(ActivityEvent(
            actor_id=1, kind="inbound.run", resource_type="inbound",
            resource_id="7",
            detail={"fn": "scenario", "execution_id": 351,
                    "run_id": "run-x", "scenario_id": "sc-import-1d9df0",
                    "scenario_name": "订单创建_1", "client_ref": "cr-9",
                    "identity_mode": "personal",
                    "token_id": 7, "token_name": "nightly"},
            created_at=t0))
        s.add(ActivityEvent(
            actor_id=1, kind="inbound.run", resource_type="inbound",
            resource_id="7",
            detail={"fn": "adhoc", "execution_id": 352, "run_id": "run-y",
                    "scenario_id": None, "scenario_name": None,
                    "client_ref": None, "identity_mode": "personal",
                    "token_id": 7, "token_name": "nightly",
                    "steps": [{"endpoint": "fin.ping", "service": "fin"}],
                    "release": {"fin": "prod#42"}},
            created_at=t0 + timedelta(seconds=5)))
        await s.commit()

    body = (await client.get("/api/activity", headers=h1,
                             params={"limit": 30})).json()
    inb = [e for e in body["events"] if e["kind"] == "inbound"]
    assert len(inb) == 2
    assert body["sources"]["inbound"] is True
    scen = next(e for e in inb if e["detail"]["fn"] == "scenario")
    assert scen["tokenId"] == 7
    assert scen["tokenName"] == "nightly"
    assert scen["clientRef"] == "cr-9"
    assert scen["scenarioName"] == "订单创建_1"
    assert scen["executionId"] == 351
    adhoc = next(e for e in inb if e["detail"]["fn"] == "adhoc")
    assert adhoc["detail"]["steps"] == [
        {"endpoint": "fin.ping", "service": "fin"}]
    assert adhoc["detail"]["release"] == {"fin": "prod#42"}
    # 他人轴不可见
    body2 = (await client.get("/api/activity", headers=h2,
                              params={"limit": 30})).json()
    assert not [e for e in body2["events"] if e["kind"] == "inbound"]


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

    # 2026-10-20 起 POST /scenarios 落 scenario.created(挂路由层,
    # copy 内部的 create 不双记 —— 本用例的 save_as 仍只一条)
    assert list(by_kind) == ["scenario.created", "scenario.edit",
                             "scenario.rename",
                             "scenario.save_as"], list(by_kind)
    assert by_kind["scenario.created"][0]["source"] == "manual"
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
    assert actions == ["scenario.created", "scenario.edit",
                       "scenario.rename", "scenario.save_as"]


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
