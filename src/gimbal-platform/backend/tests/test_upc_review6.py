"""评审六轮回归:P2-1 缺省 rowIndex 读取面 / P2-2 单元级
needs/repeat/nRuns 写入闸 + 总 cap 一致校验 / P2-3 无 CAS 解绑并发
「200 但未生效」与 revision 重号。"""
from __future__ import annotations

import asyncio

from httpx import AsyncClient
from sqlalchemy import select

from app.core import db as db_module
from tests.helpers import default_space_id, make_draft, register_and_login
from tests.test_suites_validate import STEPS, _mk, _patch_convert

CAP = 1000          # settings.SUITE_RUN_TOTAL_CAP(同一缺省,写死仅断言用)


async def _mk_suite(client: AsyncClient, h: dict, name: str,
                     scenario: str, mode: str = "chain",
                     units: dict | None = None) -> int:
    sid = (await client.post("/api/suites", headers=h,
                             json={"name": name, "description": ""})
           ).json()["suiteId"]
    body = {"rev": 0, "mode": mode,
            "members": [{"scenarioId": scenario}],
            "modeConfig": {"units": {scenario: units or {"ref": "a"}}}}
    r = await client.put(f"/api/suites/{sid}/composition", headers=h,
                         json=body)
    assert r.status_code == 200, r.text
    return sid


# ── P2-1:缺省 rowIndex(合法配置)读取面不再 500 ───────────────────

async def test_row_without_rowindex_validates(client: AsyncClient,
                                               monkeypatch):
    """单元 row 省略 rowIndex = 合法缺省(默认 0,写入边界接受)——
    修前 validate 的 row_single 告警直接下标 u['row']['rowIndex'] →
    KeyError → 500;读取端统一缺省后正常出告警「第 0 行」。"""
    _patch_convert(monkeypatch)
    await register_and_login(client, "r6p1_boot", "r4_bootpass123")
    h = await register_and_login(client, "r6p1_own", "pw123456")
    r = await client.post("/api/scenarios", headers=h,
                          json=make_draft("sc-r6p1", steps=STEPS,
                                          vars_map={"amount": 1}))
    assert r.status_code in (200, 201), r.text
    # 数据集列须 ⊆ 声明变量;两行 → 方案选 [0,1] = 2 行(>1 触发告警)
    r = await client.post("/api/scenarios/sc-r6p1/data-sets", headers=h,
                          json={"name": "两行", "rows": [
                              {"amount": 1}, {"amount": 2}]})
    assert r.status_code in (200, 201), r.text
    ds_id = r.json()["datasetId"]
    scheme_id = (await client.post("/api/scenarios/sc-r6p1/run-schemes",
                                   headers=h,
                                   json={"name": "两行方案", "isDefault": False,
                                         "dataSetSelection": [
                                             {"datasetId": ds_id,
                                              "rowIndexes": [0, 1]}],
                                         "injectionEntryIds": [],
                                         "serviceBindings": {}, "options": {
                                             "step_from": None,
                                             "step_to": None, "n_runs": 1,
                                             "parallel": 1,
                                             "subscribe": None}})
                ).json()["schemeId"]
    sid = await _mk_suite(client, h, "缺省行", "sc-r6p1",
                          units={"ref": "a", "schemeId": scheme_id,
                                 "row": {"datasetId": ds_id}})
    r = await client.post(f"/api/suites/{sid}/validate", headers=h)
    assert r.status_code == 200, r.text          # 修前 500(KeyError)
    body = r.json()
    assert body["ok"] is True, body["items"]
    hit = next((i for i in body["items"] if i["code"] == "row_single"), None)
    assert hit is not None, body["items"]
    assert "第 0 行" in hit["message"], hit["message"]


# ── P2-2:单元级 needs/repeat/nRuns/injectionEntryIds 写入闸 ────────

async def test_composition_unit_scalar_fields_type_gated(
        client: AsyncClient):
    """needs=7(修前 needs_edges 推导 TypeError → 500)、repeat/nRuns
    非整数、负值/零(修前落库后 est 被压到 0 以下绕过总 cap)、超 cap
    单值、injectionEntryIds=7 —— 统一 422 mode_config_invalid,不再
    穿透业务层 500 或污染持久化数据。"""
    await register_and_login(client, "r6p2_boot", "r4_bootpass123")
    h = await register_and_login(client, "r6p2_own", "pw123456")
    await _mk(client, h, "sc-r6p2")
    bad_units = [
        {"ref": "a", "needs": 7},
        {"ref": "a", "repeat": "x"},
        {"ref": "a", "nRuns": "x"},
        {"ref": "a", "repeat": -1},
        {"ref": "a", "repeat": 0},
        {"ref": "a", "nRuns": -5},
        {"ref": "a", "nRuns": CAP + 1},
        {"ref": "a", "injectionEntryIds": 7},
        {"ref": "a", "needs": ["ok", 7]},
    ]
    sid = (await client.post("/api/suites", headers=h,
                             json={"name": "类型闸", "description": ""})
           ).json()["suiteId"]
    for u in bad_units:
        r = await client.put(f"/api/suites/{sid}/composition", headers=h,
                             json={"rev": 0, "mode": "compose",
                                   "members": [{"scenarioId": "sc-r6p2"}],
                                   "modeConfig": {"units": {"sc-r6p2": u}}})
        assert r.status_code == 422, f"{u}: {r.text}"
        assert r.json()["detail"]["code"] == "mode_config_invalid", u


async def test_graph_level_nruns_counted_in_run_cap(client: AsyncClient,
                                                     monkeypatch):
    """图级 nRuns 的整图乘法与单元级乘法**同语义计入 est** —— 修前
    est 只加 repeat×单元 nRuns,图级 nRuns 乘法漏计,单值合法但总量
    绕过 cap(validate 只报 6、run 侧照此放行)。"""
    _patch_convert(monkeypatch)
    await register_and_login(client, "r6p2b_boot", "r4_bootpass123")
    h = await register_and_login(client, "r6p2b_own", "pw123456")
    await _mk(client, h, "sc-r6p2b")
    sid = (await client.post("/api/suites", headers=h,
                             json={"name": "图级乘法", "description": ""})
           ).json()["suiteId"]
    r = await client.put(f"/api/suites/{sid}/composition", headers=h,
                         json={"rev": 0, "mode": "chain",
                               "members": [{"scenarioId": "sc-r6p2b"}],
                               "modeConfig": {
                                   "nRuns": 3,
                                   "units": {"sc-r6p2b": {
                                       "ref": "a", "repeat": 2}}}})
    assert r.status_code == 200, r.text
    r = await client.post(f"/api/suites/{sid}/validate", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["estimatedRuns"] == 6, r.json()

    # 绕 cap 探针:单元 repeat=cap 合法,图级 nRuns=2 → est=2*cap,
    # validate 报 too_many_runs(修前 est=cap 恰好不触界、静默放行)
    sid2 = (await client.post("/api/suites", headers=h,
                              json={"name": "绕界探针", "description": ""})
            ).json()["suiteId"]
    r = await client.put(f"/api/suites/{sid2}/composition", headers=h,
                         json={"rev": 0, "mode": "chain",
                               "members": [{"scenarioId": "sc-r6p2b"}],
                               "modeConfig": {
                                   "nRuns": 2,
                                   "units": {"sc-r6p2b": {
                                       "ref": "a", "repeat": CAP}}}})
    assert r.status_code == 200, r.text
    r = await client.post(f"/api/suites/{sid2}/validate", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is False, body
    assert any(i["code"] == "too_many_runs" for i in body["items"]), body
    r = await client.post(f"/api/suites/{sid2}/run", headers=h, json={})
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "too_many_runs"


async def test_legacy_garbage_unit_values_graceful(client: AsyncClient,
                                                    monkeypatch):
    """写入闸前落库的遗留垃圾(repeat="x")—— validate 报 error 级
    mode_config_invalid(ok=false)、run 422,不再拼装层 500
    (「污染持久化数据,后续运行持续失败」至少要以可读 4xx 收场)。"""
    from app.models.suite import Suite

    _patch_convert(monkeypatch)
    await register_and_login(client, "r6p2c_boot", "r4_bootpass123")
    h = await register_and_login(client, "r6p2c_own", "pw123456")
    await _mk(client, h, "sc-r6p2c")
    sid = await _mk_suite(client, h, "遗留垃圾", "sc-r6p2c",
                          units={"ref": "a"})
    # 绕过写入闸直改库(写入闸前落库的存量行形态)
    async with db_module.SessionLocal() as s:
        row = await s.get(Suite, sid)
        cfg = dict(row.mode_config or {})
        u = dict((cfg.get("units") or {}).get("sc-r6p2c") or {})
        u["repeat"] = "x"
        cfg["units"] = {"sc-r6p2c": u}
        row.mode_config = cfg
        await s.commit()
    r = await client.post(f"/api/suites/{sid}/validate", headers=h)
    assert r.status_code == 200, r.text          # 修前 500
    body = r.json()
    assert body["ok"] is False, body
    assert any(i["code"] == "mode_config_invalid" for i in body["items"]), \
        body["items"]
    r = await client.post(f"/api/suites/{sid}/run", headers=h, json={})
    assert r.status_code == 422, r.text          # 修前 500
    assert r.json()["detail"]["code"] == "mode_config_invalid"


# ── P2-3:无 CAS 解绑 × 带 CAS 换绑 —— 生效且 revision 唯一 ───────

async def test_unbind_after_rebind_effective_unique_revision(
        client: AsyncClient, monkeypatch):
    """确定性交错(服务层两会话):解绑先读过行(无锁快照)挂起 →
    换绑(rebind-combo,CAS)提交 combo=1/rev=3 → 放行解绑。

    修前:解绑 ORM 对象仍持旧值(combo=None),赋同值不产生 UPDATE
    diff → 只写 revision=3 —— **200 但绑定未生效**(库内仍 combo=1)
    且与换绑共享 revision=3(破坏 CAS token 唯一性)。
    收口后:行锁内重读(combo=1/rev=3)→ 真解绑 + rev=4,响应与库内
    一致,版本号严格递增。"""
    from app.services import scheme_repair, scheme_store
    from tests.conftest import seed_identity_fixture
    from app.models.composer_run_scheme import ComposerRunScheme

    h = await register_and_login(client, "r6p3_own", "pw123456")
    uid = (await client.get("/api/auth/me", headers=h)).json()["user"]["id"]
    async with db_module.SessionLocal() as s:
        await seed_identity_fixture(
            s, alias="r6p3-qa", username="u", password="p",
            service="fin-service", owner_id=uid)
        space = await default_space_id(s, uid)
        await s.commit()
    combo_id = (await client.post(
        f"/api/projects/{space}/account-combos", headers=h,
        json={"name": "换绑组合", "entries": [
            {"service": "fin-service", "alias": "r6p3-qa"}]})
    ).json()["id"]
    await client.post("/api/scenarios", headers=h,
                      json=make_draft("sc-r6p3", steps=STEPS))
    scheme_id = (await client.post("/api/scenarios/sc-r6p3/run-schemes",
                                   headers=h,
                                   json={"name": "待修", "isDefault": False,
                                         "dataSetSelection": [],
                                         "injectionEntryIds": [],
                                         "serviceBindings": {}, "options": {
                                             "step_from": None,
                                             "step_to": None, "n_runs": 1,
                                             "parallel": 1,
                                             "subscribe": None}})
                 ).json()["schemeId"]
    async with db_module.SessionLocal() as s:
        row = (await s.execute(select(ComposerRunScheme).where(
            ComposerRunScheme.scheme_id == scheme_id))).scalar_one()
        await scheme_repair.mark_blocked(
            s, row, reason="combo_missing", action="import.blocked",
            actor_id=uid, actor_name="seed")
        await s.commit()

    loaded = asyncio.Event()
    release = asyncio.Event()
    orig_get_row = scheme_store.get_row

    async def paused_get_row(db, scenario_id, scheme_id=None):
        row = await orig_get_row(db, scenario_id, scheme_id)
        loaded.set()
        await asyncio.wait_for(release.wait(), 10)
        return row

    monkeypatch.setattr(scheme_store, "get_row", paused_get_row)
    user = type("U", (), {"id": uid, "display_name": "r6"})()

    async with db_module.SessionLocal() as s1,                 db_module.SessionLocal() as s2:
        unbind_task = asyncio.ensure_future(scheme_store.update_scheme(
            s1, "sc-r6p3", scheme_id, name=None, payload=None,
            account_combo_id=None, expected_revision=None))
        await asyncio.wait_for(loaded.wait(), 10)
        sch2 = (await s2.execute(select(ComposerRunScheme).where(
            ComposerRunScheme.scheme_id == scheme_id))).scalar_one()
        await scheme_repair.rebind_combo(
            s2, sch2, user=user, combo_id=combo_id, expected_revision=2)
        await s2.commit()           # 换绑先提交:combo=1, rev=3
        release.set()
        out = await asyncio.wait_for(unbind_task, 10)
        await s1.rollback()

    assert out["accountComboId"] is None, out
    assert out["revision"] == 4, out
    async with db_module.SessionLocal() as s:
        row = (await s.execute(select(ComposerRunScheme).where(
            ComposerRunScheme.scheme_id == scheme_id))).scalar_one()
        assert row.account_combo_id is None, \
            "解绑 200 后绑定必须真的解除(修前库内仍指向换绑组合)"
        assert row.revision == 4, \
            "revision 严格递增(修前与换绑共享 revision=3)"


# ── 顺手回归:恒行锁后,CAS 腿语义不变(并发保存冲突仍 409)──────

async def test_cas_leg_semantics_unchanged_after_always_lock(
        client: AsyncClient):
    """恒行锁不改变 CAS 契约:expectedRevision 落空仍
    scheme_revision_conflict 409(走 HTTP 面)。"""
    h = await register_and_login(client, "r6p3b_own", "pw123456")
    await client.post("/api/scenarios", headers=h,
                      json=make_draft("sc-r6p3b", steps=STEPS))
    scheme_id = (await client.post("/api/scenarios/sc-r6p3b/run-schemes",
                                   headers=h,
                                   json={"name": "稳态", "isDefault": False,
                                         "dataSetSelection": [],
                                         "injectionEntryIds": [],
                                         "serviceBindings": {}, "options": {
                                             "step_from": None,
                                             "step_to": None, "n_runs": 1,
                                             "parallel": 1,
                                             "subscribe": None}})
                 ).json()["schemeId"]
    body = {"name": "稳态", "isDefault": False, "dataSetSelection": [],
            "injectionEntryIds": [], "serviceBindings": {},
            "expectedRevision": 99,
            "options": {"step_from": None, "step_to": None, "n_runs": 1,
                        "parallel": 1, "subscribe": None}}
    r = await client.put(f"/api/scenarios/sc-r6p3b/run-schemes/{scheme_id}",
                         headers=h, json=body)
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "scheme_revision_conflict"
