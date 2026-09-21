"""M5-3 活动时间线服务端合流(/api/activity)。

承接原前端 useActivityTimeline 测试里搬去服务端的语义:三源合并倒序、
私有桶过滤、无时间戳执行跳过、owner 视图批次。
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
    from app.schemas.scenario_composer import ScenarioDraft
    from app.services import scenario_store

    t0 = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)
    async with db_module.SessionLocal() as s:
        # 私有场景(最新 updated_at 不可控 —— 直接置值保序)
        from sqlalchemy import update

        from app.models import ComposerScenario

        await scenario_store.create(
            s, ScenarioDraft.model_validate(make_draft("sc-act-a")),
            owner="u", owner_id=1)
        await scenario_store.create(
            s, ScenarioDraft.model_validate(make_draft("sc-act-pub")),
            owner="u", owner_id=1, visibility="public")
        await s.execute(update(ComposerScenario)
            .where(ComposerScenario.scenario_id == "sc-act-a")
            .values(updated_at=t0))
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
    # 私有场景事件在场;公共原件的改动不算我的活动;queued 无时间戳不上轴
    assert ("scenario", "sc-act-a") in kinds
    assert ("execution", "sc-act-a") in kinds
    assert "sc-act-pub" not in str(kinds)
    assert len([k for k in kinds if k[0] == "execution"]) == 1
    # 倒序:执行(13:00)在场景(12:00)前
    assert kinds[0][0] == "execution"


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
