"""M5 bulk 端点(signals / impact-bulk,债 12:关注页与适配中心 N+1 消除)。"""
from __future__ import annotations

from tests.helpers import ensure_fk_users, make_draft, register_and_login


async def _mk_execution(s, *, sid, owner_id, scheme_id=None, status_="done",
                        seq_hint=0):
    from datetime import datetime, timedelta, timezone

    from app.models.execution import Execution

    s.add(Execution(
        scenario_id=sid, owner_id=owner_id, status=status_,
        total_runs=1, passed=1 if status_ == "done" else 0,
        failed=0 if status_ == "done" else 1,
        config_json={"schemeId": scheme_id} if scheme_id else {},
        finished_at=datetime(2026, 9, 1, tzinfo=timezone.utc)
        + timedelta(hours=seq_hint),
    ))


async def test_signals_bulk_trend_and_last_run(client):
    h = await register_and_login(client, "m5sig", "pw123456")
    uid = 1  # 首注册即 id=1

    from app.core import db as db_module
    from app.schemas.scenario_composer import ScenarioDraft
    from app.services import scenario_store, scheme_store

    async with db_module.SessionLocal() as s:
        # 私有场景(带默认方案)+ 公共场景
        await scenario_store.create(
            s, ScenarioDraft.model_validate(make_draft("sc-m5-a")), owner="u")
        await scenario_store.create(
            s, ScenarioDraft.model_validate(make_draft("sc-m5-pub")),
            owner="u", visibility="public")
        # 默认方案 = 场景创建时自动物化;取其 schemeId
        schemes = await scheme_store.list_schemes(s, "sc-m5-a")
        default_sid = next(x["schemeId"] for x in schemes if x["isDefault"])
        other = await scheme_store.create_scheme(
            s, "sc-m5-a", name="other", payload={})
        other_sid = other["schemeId"]
        # 私有:默认方案 3 次(done,failed,done 新→旧)+ 非默认方案 1 次(不进趋势)
        await _mk_execution(s, sid="sc-m5-a", owner_id=uid,
                            scheme_id=default_sid, status_="done", seq_hint=3)
        await _mk_execution(s, sid="sc-m5-a", owner_id=uid,
                            scheme_id=default_sid, status_="failed", seq_hint=2)
        await _mk_execution(s, sid="sc-m5-a", owner_id=uid,
                            scheme_id=default_sid, status_="done", seq_hint=1)
        await _mk_execution(s, sid="sc-m5-a", owner_id=uid,
                            scheme_id=other_sid, status_="failed", seq_hint=4)
        # 公共:自身全部执行(默认 + 非默认都算;插入序 = 时间旧→新)
        await _mk_execution(s, sid="sc-m5-pub", owner_id=uid,
                            scheme_id="sh-x", status_="failed", seq_hint=1)
        await _mk_execution(s, sid="sc-m5-pub", owner_id=uid,
                            scheme_id=default_sid, status_="done", seq_hint=2)
        await s.commit()

    r = await client.get(
        "/api/scenarios/signals",
        headers=h, params={"ids": "sc-m5-a,sc-m5-pub,sc-missing"})
    assert r.status_code == 200, r.text
    sig = r.json()["signals"]

    # 私有:锁默认方案 → trend = [done, failed, done](旧→新);lastRun=最新 done
    assert sig["sc-m5-a"]["trend"] == ["done", "failed", "done"]
    assert sig["sc-m5-a"]["lastRun"]["status"] == "done"
    # 非默认方案的 failed 不进趋势 ✓(trend 无第四项)
    # 公共:全部执行 → [failed, done](旧→新)
    assert sig["sc-m5-pub"]["trend"] == ["failed", "done"]
    # 缺失场景:空信号而非报错
    assert sig["sc-missing"] == {"trend": [], "lastRun": None}


async def test_signals_owner_isolation(client):
    """信号池 owner 隔离:他人执行不进我的趋势。"""
    alice = await register_and_login(client, "m5sig_a", "pw123456")
    bob = await register_and_login(client, "m5sig_b", "pw123456")  # id=2

    from app.core import db as db_module
    from app.schemas.scenario_composer import ScenarioDraft
    from app.services import scenario_store

    async with db_module.SessionLocal() as s:
        await scenario_store.create(
            s, ScenarioDraft.model_validate(make_draft("sc-m5-iso")),
            owner="alice", owner_id=1, visibility="public")
        await _mk_execution(s, sid="sc-m5-iso", owner_id=2,
                            scheme_id=None, status_="done")
        await s.commit()

    r = await client.get("/api/scenarios/signals", headers=alice,
                         params={"ids": "sc-m5-iso"})
    sig = r.json()["signals"]
    assert sig["sc-m5-iso"]["trend"] == []  # bob 的执行不进 alice 的趋势


async def test_signals_requires_auth_and_ids(client):
    r = await client.get("/api/scenarios/signals")
    assert r.status_code == 401
    h = await register_and_login(client, "m5sig_c", "pw123456")
    r = await client.get("/api/scenarios/signals", headers=h,
                         params={"ids": "  "})
    assert r.status_code == 422


async def test_impact_bulk_returns_map(client, plate):
    """impact-bulk:一次请求回全部 pending 端点的受影响清单。"""
    from tests.test_adaptation_batches import OLD_FULL, _seed_scenario, _seed_stamp

    EP = "fin.order.add"
    admin = await register_and_login(client, "m5bulk", "pw123456")
    plate.items = [{"id": EP, "version": "1.1.0", "updated_at": None}]
    plate.fulls = {EP: OLD_FULL}
    await _seed_scenario("sc-m5-imp")
    await _seed_stamp()

    r = await client.get(
        "/api/adaptations/impact-bulk", headers=admin,
        params=[("endpointIds", EP), ("endpointIds", "fin.ghost")])
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {EP, "fin.ghost"}
    assert isinstance(body[EP], list) and len(body[EP]) >= 1
    assert body["fin.ghost"] == []


async def test_impact_bulk_admin_only(client):
    await register_and_login(client, "m5bulk_root", "pw123456")  # 首注册= admin
    member = await register_and_login(client, "m5bulk_m", "pw123456")  # member
    r = await client.get("/api/adaptations/impact-bulk", headers=member,
                         params=[("endpointIds", "e")])
    assert r.status_code == 403
