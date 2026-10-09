"""Suite 层重构第 1 步:深拷贝重映射三入口 / 公共复制 / 删除通知引用者。

《Suite 层重构设计方案》约束 8 + API 表:
- 深拷贝(拷贝分享 / 引用转副本 / 公共复制)带完整编排:mode、成员
  role、mode_config 重映射到副本 scenarioId;副本 rev 归零、不是草稿;
- POST /suites/{id}/fork:公共读者「复制到我的」,读闸 + 公共可见;
- DELETE /suites/{id}:有引用者时删除后通知(share_ref_resource_deleted);
- 场景删除单点清理 suite 配置引用并推进 rev(约束 6,scenario_store.delete)。
"""
from __future__ import annotations

from httpx import AsyncClient

from tests.helpers import make_draft, register_and_login


async def _mk(client: AsyncClient, h: dict, sid: str) -> None:
    r = await client.post("/api/scenarios", headers=h, json=make_draft(sid))
    assert r.status_code in (200, 201), r.text


async def _mk_suite(client: AsyncClient, h: dict, name: str) -> int:
    r = await client.post("/api/suites", headers=h,
                          json={"name": name, "description": ""})
    assert r.status_code == 201, r.text
    return r.json()["suiteId"]


async def _compose(client: AsyncClient, h: dict, sid: int) -> dict:
    """编排集:b(main)→a(before)…实际为 compose:b 无 needs,a 为 before
    不连线;units 带 ref/needs/map/checks 全要素供重映射断言。"""
    cfg = {"units": {
        "sc-x-a": {"ref": "order"},
        "sc-x-b": {"ref": "auth"},
    }, "checks": [{"on": {"scenarioIds": ["sc-x-a", "sc-x-b"]},
                   "strategy": {}}]}
    r = await client.put(f"/api/suites/{sid}/composition", headers=h, json={
        "rev": 0, "mode": "compose",
        "members": [{"scenarioId": "sc-x-b"},
                    {"scenarioId": "sc-x-a", "role": "before"}],
        "modeConfig": cfg})
    assert r.status_code == 200, r.text
    return r.json()


async def test_copy_remaps_orchestration(client: AsyncClient) -> None:
    """拷贝分享:副本 mode/role/config 齐全且全部指向副本场景,rev=0。"""
    await register_and_login(client, "xc_admin", "xc_admin_pass123")
    owner = await register_and_login(client, "xc_owner", "xc_owner_pass123")
    bob = await register_and_login(client, "xc_bob", "xc_bob_pass123")
    await _mk(client, owner, "sc-x-a")
    await _mk(client, owner, "sc-x-b")
    sid = await _mk_suite(client, owner, "编排源")
    await _compose(client, owner, sid)

    roster = (await client.get(
        "/api/users/roster", headers=owner)).json()["items"]
    bob_id = next(u["id"] for u in roster if u["username"] == "xc_bob")
    r = await client.post("/api/shares", headers=owner, json={
        "resourceType": "suite", "resourceId": str(sid),
        "granteeUserId": bob_id, "mode": "copy"})
    assert r.status_code == 201, r.text
    new_id = r.json()["suiteId"]

    d = (await client.get(f"/api/suites/{new_id}", headers=bob)).json()
    assert d["mode"] == "compose" and d["rev"] == 0 and not d["isDraft"]
    new_ids = [m["scenarioId"] for m in d["members"]]
    assert all(n != old for n, old in
               zip(sorted(new_ids), ["sc-x-a", "sc-x-b"]))
    roles = {m["role"] for m in d["members"]}
    assert roles == {"main", "before"}            # 前置角色随副本
    units = d["modeConfig"]["units"]
    assert set(units) == set(new_ids)             # units 键全部重映射
    assert units[new_ids[0]]["ref"] in ("order", "auth")
    scrubs = d["modeConfig"]["checks"][0]["on"]["scenarioIds"]
    assert sorted(scrubs) == sorted(new_ids)      # checks 选择器重映射

    # 引用转副本(fork)走同一服务:同样带完整编排
    r = await client.post("/api/shares", headers=owner, json={
        "resourceType": "suite", "resourceId": str(sid),
        "granteeUserId": bob_id, "mode": "ref"})
    r = await client.post(f"/api/shares/{r.json()['id']}/fork", headers=bob)
    assert r.status_code == 201, r.text
    d2 = (await client.get(
        f"/api/suites/{r.json()['suiteId']}", headers=bob)).json()
    assert d2["mode"] == "compose" and d2["modeConfig"]["units"]


async def test_public_fork_endpoint(client: AsyncClient) -> None:
    """POST /suites/{id}/fork:公共可见才可复制;非公共 404;副本归自己。"""
    await register_and_login(client, "pf_admin", "pf_admin_pass123")
    owner = await register_and_login(client, "pf_owner", "pf_owner_pass123")
    carol = await register_and_login(client, "pf_carol", "pf_carol_pass123")
    await _mk(client, owner, "sc-x-a")
    await _mk(client, owner, "sc-x-b")
    await _mk(client, owner, "sc-pf-1")
    sid = await _mk_suite(client, owner, "公共编排集")
    await _compose(client, owner, sid)
    await client.post(f"/api/suites/{sid}/publish", headers=owner)

    r = await client.post(f"/api/suites/{sid}/fork", headers=carol)
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["mode"] == "compose" and out["memberCount"] == 2
    d = (await client.get(f"/api/suites/{out['suiteId']}",
                          headers=carol)).json()
    assert d["access"] == "owner" and d["modeConfig"]["units"]

    # 未发布的私有 suite → 404(仅公共可复制)
    sid2 = await _mk_suite(client, owner, "私有集")
    await client.post(f"/api/suites/{sid2}/members", headers=owner,
                      json={"scenarioIds": ["sc-pf-1"]})
    assert (await client.post(
        f"/api/suites/{sid2}/fork", headers=carol)).status_code == 404


async def test_delete_suite_notifies_referrers(
    client: AsyncClient,
) -> None:
    """删除 Suite:引用者收到 share_ref_resource_deleted 通知(级联前取名单)。"""
    await register_and_login(client, "dn_admin", "dn_admin_pass123")
    owner = await register_and_login(client, "dn_owner", "dn_owner_pass123")
    bob = await register_and_login(client, "dn_bob", "dn_bob_pass123")
    await _mk(client, owner, "sc-dn-1")
    sid = await _mk_suite(client, owner, "被引集")
    await client.post(f"/api/suites/{sid}/members", headers=owner,
                      json={"scenarioIds": ["sc-dn-1"]})
    roster = (await client.get(
        "/api/users/roster", headers=owner)).json()["items"]
    bob_id = next(u["id"] for u in roster if u["username"] == "dn_bob")
    r = await client.post("/api/shares", headers=owner, json={
        "resourceType": "suite", "resourceId": str(sid),
        "granteeUserId": bob_id, "mode": "ref"})
    assert r.status_code == 201, r.text

    r = await client.delete(f"/api/suites/{sid}", headers=owner)
    assert r.status_code == 204
    notes = (await client.get(
        "/api/notifications?page_size=50", headers=bob)).json()["items"]
    hit = [n for n in notes if n["type"] == "share_ref_resource_deleted"]
    assert hit, "删除后引用者应收到失效通知"


async def test_scenario_delete_cleans_suite_config(
    client: AsyncClient,
) -> None:
    """约束 6 单点:场景删除 → 所属 suite 配置引用被清、rev 推进。"""
    await register_and_login(client, "sd_admin", "sd_admin_pass123")
    owner = await register_and_login(client, "sd_owner", "sd_owner_pass123")
    await _mk(client, owner, "sc-sd-a")
    await _mk(client, owner, "sc-sd-b")
    sid = await _mk_suite(client, owner, "联动集")
    r = await client.put(f"/api/suites/{sid}/composition", headers=owner,
                         json={"rev": 0, "mode": "compose",
                               "members": [{"scenarioId": "sc-sd-a"},
                                           {"scenarioId": "sc-sd-b"}],
                               "modeConfig": {"units": {
                                   "sc-sd-a": {"needs": ["sc-sd-b"]},
                                   "sc-sd-b": {}}}})
    assert r.status_code == 200, r.text
    rev = r.json()["rev"]

    r = await client.delete("/api/scenarios/sc-sd-b", headers=owner)
    assert r.status_code in (200, 204), r.text
    d = (await client.get(f"/api/suites/{sid}", headers=owner)).json()
    assert d["rev"] == rev + 1
    assert "sc-sd-b" not in d["modeConfig"]["units"]
    assert d["modeConfig"]["units"]["sc-sd-a"]["needs"] == []
    assert [m["scenarioId"] for m in d["members"]] == ["sc-sd-a"]
