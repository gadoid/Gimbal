"""PUT /run-schemes 窄端点 + runSchemes 键所有权(spec §3.2/§11)。

核心断言:composer 的 PUT /scenarios/{id}(整体替换)永不覆盖 runSchemes
— 键归窄端点专管,scenario_store.update 透传保留。
"""
from __future__ import annotations

from .helpers import make_draft as _draft
from .test_scenario_visibility_and_copy import _member

SCHEMES = [{"name": "冒烟-qa1", "envId": "test-env-A", "dataSetIds": [],
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
    assert [s["name"] for s in resp.json()] == ["冒烟-qa1"]
    # 保存后 GET 场景:orchestration.runSchemes 可见
    got = (await client.get(f"/api/scenarios/{sid}", headers=bob)).json()
    assert got["orchestration"]["runSchemes"][0]["envId"] == "test-env-A"


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
    assert [s["name"] for s in got["orchestration"]["runSchemes"]] == ["冒烟-qa1"]


async def test_invalid_refs_accepted_warn_level(client):
    """envId/datasetId/authAlias 失效 → 接受不拒(降级预填由前端标红)。"""
    bob = await _member(client, "bob")
    sid = await _saved_scenario(client, bob)
    resp = await client.put(f"/api/scenarios/{sid}/run-schemes", headers=bob,
                            json={"schemes": [{
                                "name": "ghost", "envId": "env-gone",
                                "dataSetIds": ["ds-gone"],
                                "serviceBindings": {"fin-service": {"authAlias": "ghost-alias"}},
                            }]})
    assert resp.status_code == 200


async def test_owner_enforced(client):
    bob = await _member(client, "bob")
    sid = await _saved_scenario(client, bob)
    eve = await _member(client, "eve")     # 第二用户(_member 即建用户返 headers)
    resp = await client.put(f"/api/scenarios/{sid}/run-schemes",
                            headers=eve, json={"schemes": SCHEMES})
    assert resp.status_code == 403
