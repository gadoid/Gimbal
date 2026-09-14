"""PUT /run-schemes 窄端点 + runSchemes 键所有权(spec §3.2/§11)。

核心断言:composer 的 PUT /scenarios/{id}(整体替换)永不覆盖 runSchemes
— 键归窄端点专管,scenario_store.update 透传保留。
"""
from __future__ import annotations

from .helpers import make_draft as _draft
from .test_scenario_visibility_and_copy import _member

SCHEMES = [{"name": "冒烟-qa1", "dataSetIds": [],
            "serviceBindings": {"fin-service": {"authAlias": "qa1"}},
            "plugins": None, "logSub": None}]


async def _saved_scenario(client, headers) -> str:
    r = await client.post("/api/scenarios", headers=headers, json=_draft())
    assert r.status_code in (200, 201), r.text
    return "sc-test"                       # _draft 缺省 scenario_id


async def test_put_and_get_roundtrip(client):
    bob = await _member(client, "bob")
    sid = await _saved_scenario(client, bob)
    resp = await client.put(f"/api/scenarios/{sid}/run-schemes",
                            headers=bob, json={"schemes": SCHEMES})
    assert resp.status_code == 200, resp.text
    assert [s["name"] for s in resp.json()] == ["默认方案", "冒烟-qa1"]
    # 保存后 GET 场景:orchestration.runSchemes 可见(serviceBindings 键随存随读)
    got = (await client.get(f"/api/scenarios/{sid}", headers=bob)).json()
    assert "serviceBindings" in got["orchestration"]["runSchemes"][0]


async def test_duplicate_name_409(client):
    bob = await _member(client, "bob")
    sid = await _saved_scenario(client, bob)
    resp = await client.put(f"/api/scenarios/{sid}/run-schemes",
                            headers=bob, json={"schemes": SCHEMES + [SCHEMES[0]]})
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "run_scheme_name_conflict"


async def test_composer_save_never_overwrites_schemes(client):
    """并发保护:整体 PUT 场景(不带 runSchemes)后方案仍在。"""
    bob = await _member(client, "bob")
    sid = await _saved_scenario(client, bob)
    assert (await client.put(f"/api/scenarios/{sid}/run-schemes",
                             headers=bob, json={"schemes": SCHEMES})).status_code == 200
    # composer 保存:GET /draft → PUT 回写(orchestration 无 runSchemes 键;
    # 与前端编辑器同款流程 — PUT 体是 ScenarioDraft,非读侧 shape)
    cur = (await client.get(f"/api/scenarios/{sid}/draft", headers=bob)).json()
    cur["orchestration"].pop("runSchemes", None)
    resp = await client.put(f"/api/scenarios/{sid}", headers=bob, json=cur)
    assert resp.status_code == 200
    got = (await client.get(f"/api/scenarios/{sid}", headers=bob)).json()
    assert [s["name"] for s in got["orchestration"]["runSchemes"]] == [
        "默认方案", "冒烟-qa1"]


async def test_invalid_refs_accepted_warn_level(client):
    """datasetId/authAlias 失效 → 接受不拒(降级预填由前端标红)。"""
    bob = await _member(client, "bob")
    sid = await _saved_scenario(client, bob)
    resp = await client.put(f"/api/scenarios/{sid}/run-schemes", headers=bob,
                            json={"schemes": [{
                                "name": "ghost",
                                "dataSetIds": ["ds-gone"],
                                "serviceBindings": {"fin-service": {"authAlias": "ghost-alias"}},
                            }]})
    assert resp.status_code == 200


async def test_legacy_envid_schemes_silently_dropped(client):
    """D2:旧存量方案含 envId → pydantic 忽略,存下的方案无该键。"""
    bob = await _member(client, "bob")
    sid = await _saved_scenario(client, bob)
    resp = await client.put(f"/api/scenarios/{sid}/run-schemes", headers=bob,
                            json={"schemes": [{
                                "name": "legacy", "envId": "dev-local",
                                "dataSetIds": [], "serviceBindings": {},
                            }]})
    assert resp.status_code == 200
    legacy = next(s for s in resp.json() if s["name"] == "legacy")
    assert "envId" not in legacy


async def test_owner_enforced(client):
    bob = await _member(client, "bob")
    sid = await _saved_scenario(client, bob)
    eve = await _member(client, "eve")     # 第二用户(_member 即建用户返 headers)
    resp = await client.put(f"/api/scenarios/{sid}/run-schemes",
                            headers=eve, json={"schemes": SCHEMES})
    assert resp.status_code == 403


async def test_reserved_name_precheck_409_keeps_existing(client):
    """终审 I-1:入参含「默认方案」且不带 isDefault(旧 RunDialog 形状)→
    调 replace_all 之前 409 拒绝;存量方案原样保留 — 关闭「先删后建
    中途保留名抛错」的部分替换窗口。"""
    bob = await _member(client, "bob")
    sid = await _saved_scenario(client, bob)
    assert (await client.put(f"/api/scenarios/{sid}/run-schemes",
                             headers=bob, json={"schemes": SCHEMES})).status_code == 200
    resp = await client.put(f"/api/scenarios/{sid}/run-schemes",
                            headers=bob, json={"schemes": [
                                # 无 isDefault 键 → pydantic 默认 False → 保留名冲突
                                {"name": "默认方案", "dataSetIds": [],
                                 "serviceBindings": {}},
                                SCHEMES[0],
                            ]})
    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"]["code"] == "run_scheme_name_conflict"
    # 预检先于任何删改:存量自定义方案未被部分替换吞掉(读侧回填新表)
    got = (await client.get(f"/api/scenarios/{sid}", headers=bob)).json()
    assert [s["name"] for s in got["orchestration"]["runSchemes"]] == [
        "默认方案", "冒烟-qa1"]
