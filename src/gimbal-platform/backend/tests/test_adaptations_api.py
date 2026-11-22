"""adaptations 路由 API 测试（RS3 后收窄 + A-6 清理）。

RS3 §5.10：按端点开批的旧流程（基线戳 / POST /batches / 草案展开）
已删除；A-6(2026-10-12) 再删 catalog/diff、impact、impact-bulk、
impact-summary、refs-drift 五读面。本文件只覆盖存续读面：
unindexed-steps。批次生命周期经 carry 批（见 test_carry_*）与新
RS4a 流程（随批次三重建）测试。
"""
from __future__ import annotations

from app.core import db as db_module
from app.schemas.scenario_composer import ScenarioDraft
from app.services import scenario_store

from .helpers import make_draft, register_and_login

EP = "fin.order.add"


def _steps():
    return [{
        "call": {"view_hints": {"endpoint_id": EP}, "headers": {}},
        "request": {"body": {"amount": "${var.amount}"}},
    }]


async def _session():
    return db_module.SessionLocal()


async def _api_seed_scenario(sid: str = "sc-api", owner_id: int = 1):
    async with await _session() as s:
        await scenario_store.create(
            s,
            ScenarioDraft.model_validate(
                make_draft(sid, steps=_steps(), vars_map={"amount": 100})
            ),
            owner=f"u{owner_id}", owner_id=owner_id,
        )


async def _seed_unindexed_scenario(sid: str = "sc-unbound"):
    async with await _session() as s:
        await scenario_store.create(
            s,
            ScenarioDraft.model_validate(
                make_draft(sid, steps=[{
                    "call": {"headers": {}},          # 无 endpoint 锚点
                    "request": {"body": {"x": "1"}},
                }])
            ),
            owner="u1", owner_id=1,
        )


# ─── 已删读面(2026-10-12 A-6):catalog/diff、impact、impact-bulk、
#     impact-summary、refs-drift 一并 404 —— 存量客户端升级提示 ──────
async def test_legacy_read_faces_removed(client, plate):
    admin = await register_and_login(client, "boss", "bosspass123")
    assert (await client.post("/api/adaptations/catalog/diff",
                              headers=admin)).status_code == 404
    for path in ("impact?endpointId=fin.order.add", "impact-bulk",
                 "refs-drift", "impact-summary"):
        r = await client.get(f"/api/adaptations/{path}", headers=admin)
        assert r.status_code == 404, path


# ─── unindexed-steps（CurrentUser；C10 只读警示）────────────────
async def test_unindexed_steps_lists_gap(client, plate):
    admin = await register_and_login(client, "boss", "bosspass123")
    await _api_seed_scenario()          # sc-api:步骤已挂 endpoint_id → 不在清单
    await _seed_unindexed_scenario()    # sc-unbound:缺 endpoint 锚点 → 在清单
    r = await client.get("/api/adaptations/unindexed-steps", headers=admin)
    assert r.status_code == 200
    assert r.json() == [{"scenarioId": "sc-unbound", "stepIndex": 0,
                         "reason": "no_endpoint_id"}]


async def test_unindexed_steps_admin_only_gate(client, plate):
    """B3 收口(2026-11-22):unindexed-steps 全表扫无属主过滤 → 补
    Admin+ 能力门(ops.write,模块 admin-only 约定同款)。普通用户
    403 capability_forbidden;admin 照常 200(见上一测试)。"""
    await register_and_login(client, "boss", "bosspass123")
    member = await register_and_login(client, "peon", "peonpass123")
    r = await client.get("/api/adaptations/unindexed-steps",
                         headers=member)
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["code"] == "capability_forbidden"


# ─── B2/B4 收口(2026-11-22):submit-suite 读闸 + copy 签名;
#     compare/save-check 场景读闸 ────────────────────────────────────

async def _mk_suite(owner_id: int, sid: str, *, name: str = "b2-suite") -> int:
    """直插私有 Suite + 单成员(同区:均私有区)。"""
    from app.models.suite import Suite, SuiteMember

    async with await _session() as s:
        suite = Suite(name=name, owner_id=owner_id, description="",
                      mode_config={"units": {sid: {}}})
        s.add(suite)
        await s.flush()
        s.add(SuiteMember(suite_id=suite.id, scenario_id=sid, sort=0))
        await s.commit()
        return suite.id


async def test_submit_suite_read_gate_404_for_others(client, plate):
    """B2 收口:submit-suite 补表 B suite.read 读闸 —— 他人私有 Suite
    404 不泄露存在性(此前 db.get(Suite) 裸取,任意登录用户可触发
    他人套件的聚合;copy 模式深拷贝被签名错配的 500 侥幸挡住)。"""
    owner = await register_and_login(client, "b2boss", "b2pass123")
    await _api_seed_scenario("sc-b2m", owner_id=1)   # 首注 = id 1 = owner
    suite_id = await _mk_suite(1, "sc-b2m")
    other = await register_and_login(client, "b2peon", "b2pass123")
    r = await client.post("/api/adaptations/submit-suite", headers=other,
                          json={"suiteId": suite_id,
                                "targetRevision": "1.0#2",
                                "saveMode": "direct"})
    assert r.status_code == 404, r.text
    assert "suite_not_found" in r.text
    # copy 模式同样 404(fork 同款「公共 ∨ 属主」收窄)
    r = await client.post("/api/adaptations/submit-suite", headers=other,
                          json={"suiteId": suite_id,
                                "targetRevision": "1.0#2",
                                "saveMode": "copy"})
    assert r.status_code == 404, r.text


async def test_submit_suite_copy_mode_forks_without_500(
        client, plate, monkeypatch):
    """B2 修调用签名:copy 模式 deep_copy_suite(db, suite, user, disp)
    位置传参正常 fork(旧 owner_id=/owner_name= kwargs 必 TypeError →
    500);副本成员不可适配(no system 声明)时按循环既有口径逐成员
    记 failed,整体 200 + new_suite_id。"""
    owner = await register_and_login(client, "b2boss2", "b2pass123")
    await _api_seed_scenario("sc-b2c", owner_id=1)
    suite_id = await _mk_suite(1, "sc-b2c", name="b2-suite-c")
    # 深拷贝成员复制走 plate convert → 打桩(flow 测试同款);逐成员
    # compare 的 plate_diff_for_adaptation 打成 ValueError → 循环既有
    # 口径记 failed(本测试只钉 fork 签名收口,不追适配链)。
    from app.services import adaptation_service as _svc_diff
    from app.services import plate_client as _pc

    async def fake_convert(trial):
        return {"consumer": "gimbal", "converted": {}}

    monkeypatch.setattr(_pc, "convert", fake_convert)

    async def fake_diff_b2(system, from_ref, to_ref):
        raise ValueError("release_not_found: stub")

    monkeypatch.setattr(_svc_diff, "plate_diff_for_adaptation",
                        fake_diff_b2)
    r = await client.post("/api/adaptations/submit-suite", headers=owner,
                          json={"suiteId": suite_id,
                                "targetRevision": "1.0#2",
                                "saveMode": "copy"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["new_suite_id"]
    assert body["new_suite_id"] != suite_id
    assert body["total"] == 1
    assert body["succeeded"] == 0 and body["failed"] == 1


async def test_compare_savecheck_private_scoped_to_reader(
        client, plate, monkeypatch):
    """B4 收口:compare/save-check 补场景读闸 —— 非可读者 404
    scenario_not_found(不泄露存在性,与 GET /scenarios/{id} 同口径);
    属主照常。旧「R22 读面全员」随私有区教义废止。"""
    from app.services import adaptation_service as _svc

    owner = await register_and_login(client, "b4boss", "b4pass123")
    await _api_seed_scenario("sc-b4gate", owner_id=1)   # 首注 = id 1
    other = await register_and_login(client, "b4peon", "b4pass123")
    r = await client.get("/api/adaptations/compare", headers=other,
                         params={"scenarioId": "sc-b4gate",
                                 "target": "1.0#2"})
    assert r.status_code == 404, r.text
    assert "scenario_not_found" in r.text
    r = await client.post("/api/adaptations/save-check", headers=other,
                          json={"scenarioId": "sc-b4gate",
                                "targetRevision": "1.0#2"})
    assert r.status_code == 404, r.text
    assert "scenario_not_found" in r.text
    # 属主:compare 照常走通(plate diff 打桩,同 flow 测试口径)
    async def fake_diff(system, from_ref, to_ref):
        return {"from": from_ref, "to": to_ref,
                "added": [], "removed": [], "changed": {}}

    monkeypatch.setattr(_svc, "plate_diff_for_adaptation", fake_diff)
    r = await client.get("/api/adaptations/compare", headers=owner,
                         params={"scenarioId": "sc-b4gate",
                                 "target": "1.0#2"})
    assert r.status_code == 200, r.text
