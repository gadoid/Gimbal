"""M5 bulk 端点(signals,债 12:关注页 N+1 消除)。

impact-bulk 随 A-6 清理(2026-10-12)删除 —— useInterfaceChange 退役。
"""
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


# ── W21:signals trendPins(趋势切换点)─────────────────────────────
async def test_signals_trend_pins(client):
    """默认方案两次执行钉定不同修订 → trendPins 反映签名变化(旧→新,
    未钉 = None);SignalDots 据此标切换点。"""
    h = await register_and_login(client, "m5pins", "pw123456")
    uid = 1

    from app.core import db as db_module
    from app.schemas.scenario_composer import ScenarioDraft
    from app.services import scenario_store

    async with db_module.SessionLocal() as s:
        await scenario_store.create(
            s, ScenarioDraft.model_validate(make_draft("sc-m5-pins")), owner="u")
        # 私有场景趋势锁默认方案(与既有用例同口径)
        from app.services import scheme_store
        schemes = await scheme_store.list_schemes(s, "sc-m5-pins")
        default_sid = next(x["schemeId"] for x in schemes if x["isDefault"])
        d = {"scenarioId": "sc-m5-pins", "dataSetIds": [],
             "schemeId": default_sid}
        from app.models.execution import Execution
        s.add(Execution(
            scenario_id="sc-m5-pins", owner_id=uid, status="done",
            total_runs=1, passed=1, failed=0, config_json=d,
            plate_pins=None))                       # 旧执行:未钉
        s.add(Execution(
            scenario_id="sc-m5-pins", owner_id=uid, status="done",
            total_runs=1, passed=1, failed=0, config_json=d,
            plate_pins={"fin": "1.0#1"}))           # 新执行:钉定
        await s.commit()

    r = await client.get("/api/scenarios/signals",
                         headers=h, params={"ids": "sc-m5-pins"})
    assert r.status_code == 200, r.text
    sig = r.json()["signals"]["sc-m5-pins"]
    assert sig["trend"] == ["done", "done"]         # 旧→新
    assert sig["trendPins"] == [None, "fin#1.0#1"]  # 切换点 = 索引 1
