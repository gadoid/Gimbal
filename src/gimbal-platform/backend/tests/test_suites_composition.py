"""Suite 层重构第 1 步:composition 整体保存 + rev + 草稿 + 访问角色。

《Suite 层重构设计方案》「功能与接口」/第 1 步验收面:
- PUT composition:模式 / 成员及顺序 / 编排配置一次落库,rev 乐观锁
  冲突 409 附最新内容;结构校验(引用都是成员、ref 唯一、needs 只给
  compose 且目标为主体成员、map str→str);公共 Suite 加私有成员复用
  发布确认分支;
- rev 推进:composition / 加成员 / 移成员 / 清草稿都推进,旧 rev 的
  整体保存被拒(而非仅接口路径);
- 移除成员同一事务清理配置引用(units 条目、他单元 needs);
- 草稿:name 缺省创建草稿、单独上限、不可发布 / 分享,clearDraft 清;
- access + 能力位:前端不自己推导角色(owner / admin / ref / public)。
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


def _comp(rev: int, members: list[dict], mode: str = "compose",
          config: dict | None = None) -> dict:
    return {"rev": rev, "mode": mode, "members": members,
            "modeConfig": config or {}}


async def test_composition_save_and_rev_conflict(
    client: AsyncClient,
) -> None:
    """整体保存落库 + rev 乐观锁:旧 rev 409 附最新,新 rev 通过。"""
    await register_and_login(client, "cp_admin", "cp_admin_pass123")
    owner = await register_and_login(client, "cp_owner", "cp_owner_pass123")
    await _mk(client, owner, "sc-cp-a")
    await _mk(client, owner, "sc-cp-b")
    await _mk(client, owner, "sc-cp-c")
    sid = await _mk_suite(client, owner, "编排集")
    detail = (await client.get(f"/api/suites/{sid}", headers=owner)).json()
    assert detail["rev"] == 0 and detail["access"] == "owner"
    assert detail["canEdit"] and detail["canRun"] and detail["canShare"]

    cfg = {"units": {
        "sc-cp-b": {"ref": "auth"},
        "sc-cp-a": {"ref": "order"},   # before 单元不连线(约束 7)
    }, "parallel": 2}
    r = await client.put(f"/api/suites/{sid}/composition", headers=owner, json={
        "rev": 0, "mode": "compose",
        "members": [{"scenarioId": "sc-cp-b"}, {"scenarioId": "sc-cp-a",
                                                "role": "before"}],
        "modeConfig": cfg})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["rev"] == 1 and out["mode"] == "compose"
    assert out["modeConfig"] == cfg
    assert [m["scenarioId"] for m in out["members"]] == ["sc-cp-b", "sc-cp-a"]
    assert out["members"][1]["role"] == "before"

    # 旧 rev → 409 附最新内容(currentRev + latest)
    r = await client.put(f"/api/suites/{sid}/composition", headers=owner,
                         json=_comp(0, [{"scenarioId": "sc-cp-a"}]))
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "suite_rev_conflict"
    assert r.json()["detail"]["currentRev"] == 1
    assert r.json()["detail"]["latest"]["rev"] == 1

    # 新 rev 通过;前置单元带 needs / needs 指向非主体 → 422
    r = await client.put(f"/api/suites/{sid}/composition", headers=owner,
                         json=_comp(1, [{"scenarioId": "sc-cp-a"},
                                        {"scenarioId": "sc-cp-b",
                                         "role": "after"}],
                                    config={"units": {
                                        "sc-cp-a": {"needs": ["sc-cp-b"]}}}))
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "needs_target_invalid"

    # 加成员推进 rev:旧 rev 的整体保存被拒(非仅本接口路径)
    r = await client.post(f"/api/suites/{sid}/members", headers=owner,
                          json={"scenarioIds": ["sc-cp-c"]})
    assert r.status_code == 200 and r.json()["rev"] >= 2
    r = await client.put(f"/api/suites/{sid}/composition", headers=owner,
                         json=_comp(1, [{"scenarioId": "sc-cp-a"}]))
    assert r.status_code == 409  # rev 已被加成员推进,旧 rev 再保存被拒


async def test_composition_validation(client: AsyncClient) -> None:
    """结构校验:重复成员/未知单元/重复 ref/非 compose needs/map 形态。"""
    await register_and_login(client, "cv_admin", "cv_admin_pass123")
    owner = await register_and_login(client, "cv_owner", "cv_owner_pass123")
    bob = await register_and_login(client, "cv_bob", "cv_bob_pass123")
    await _mk(client, owner, "sc-cv-a")
    await _mk(client, owner, "sc-cv-b")
    await _mk(client, bob, "sc-cv-x")   # 他人场景
    sid = await _mk_suite(client, owner, "校验集")

    async def put(body: dict):
        return await client.put(f"/api/suites/{sid}/composition",
                                headers=owner, json=body)

    r = await put(_comp(0, [{"scenarioId": "sc-cv-a"},
                            {"scenarioId": "sc-cv-a"}]))
    assert r.status_code == 422 and r.json()["detail"]["code"] == "duplicate_member"

    r = await put(_comp(0, [{"scenarioId": "sc-cv-a"}],
                        config={"units": {"sc-cv-b": {}}}))
    assert r.status_code == 422 and r.json()["detail"]["code"] == "unknown_unit"

    r = await put(_comp(0, [{"scenarioId": "sc-cv-a"},
                            {"scenarioId": "sc-cv-b"}],
                        config={"units": {
                            "sc-cv-a": {"ref": "u"},
                            "sc-cv-b": {"ref": "u"}}}))
    assert r.status_code == 422 and r.json()["detail"]["code"] == "duplicate_ref"

    r = await put(_comp(0, [{"scenarioId": "sc-cv-a"},
                            {"scenarioId": "sc-cv-b"}],
                        mode="chain",
                        config={"units": {"sc-cv-a": {"needs": ["sc-cv-b"]}}}))
    assert r.status_code == 422 and r.json()["detail"]["code"] == "needs_not_allowed"

    r = await put(_comp(0, [{"scenarioId": "sc-cv-a"}],
                        config={"units": {"sc-cv-a": {"map": {"x": 1}}}}))
    assert r.status_code == 422

    # 他人场景 → 404(§6.3 一刀切,composition 同口径)
    r = await put(_comp(0, [{"scenarioId": "sc-cv-x"}]))
    assert r.status_code == 404

    # 校验失败不落库:rev 仍是 0,合法保存仍可用 rev 0
    r = await put(_comp(0, [{"scenarioId": "sc-cv-a"}], mode="aggregate"))
    assert r.status_code == 200 and r.json()["rev"] == 1


async def test_remove_member_cleans_config(client: AsyncClient) -> None:
    """约束 6:移除成员同一事务清理 units 条目与他单元 needs,推进 rev。"""
    await register_and_login(client, "rc_admin", "rc_admin_pass123")
    owner = await register_and_login(client, "rc_owner", "rc_owner_pass123")
    await _mk(client, owner, "sc-rc-a")
    await _mk(client, owner, "sc-rc-b")
    sid = await _mk_suite(client, owner, "清理集")
    r = await client.put(f"/api/suites/{sid}/composition", headers=owner,
                         json=_comp(0, [{"scenarioId": "sc-rc-b"},
                                        {"scenarioId": "sc-rc-a"}],
                                    config={"units": {
                                        "sc-rc-a": {"needs": ["sc-rc-b"]},
                                        "sc-rc-b": {}}}))
    assert r.status_code == 200, r.text
    rev = r.json()["rev"]

    r = await client.delete(f"/api/suites/{sid}/members/sc-rc-b",
                            headers=owner)
    assert r.status_code == 204
    detail = (await client.get(f"/api/suites/{sid}", headers=owner)).json()
    assert detail["rev"] == rev + 1
    assert "sc-rc-b" not in detail["modeConfig"]["units"]
    assert detail["modeConfig"]["units"]["sc-rc-a"]["needs"] == []


async def test_draft_lifecycle_and_caps(
    client: AsyncClient, monkeypatch,
) -> None:
    """草稿:name 缺省创建、单独上限、不可发布/分享、clearDraft 清。"""
    from app.core.config import settings
    from pytest import MonkeyPatch

    await register_and_login(client, "df_admin", "df_admin_pass123")
    owner = await register_and_login(client, "df_owner", "df_owner_pass123")
    await _mk(client, owner, "sc-df-1")

    with MonkeyPatch.context() as mp:
        mp.setattr(settings, "SUITE_DRAFT_CAP", 2, raising=False)
        r1 = await client.post("/api/suites", headers=owner, json={})
        assert r1.status_code == 201, r1.text
        assert r1.json()["isDraft"] and r1.json()["name"] == "未命名 Suite"
        r2 = await client.post("/api/suites", headers=owner, json={})
        assert r2.json()["name"] == "未命名 Suite 2"
        r3 = await client.post("/api/suites", headers=owner, json={})
        assert r3.status_code == 409
        assert r3.json()["detail"]["code"] == "suite_draft_cap_exceeded"
        # 正式套件不占草稿额度,草稿也不占 50 上限
        r4 = await client.post("/api/suites", headers=owner,
                               json={"name": "正式集"})
        assert r4.status_code == 201 and not r4.json()["isDraft"]

    draft_id = r1.json()["suiteId"]
    # 草稿不可发布 / 不可分享(ref 与 copy 同拒)
    r = await client.post(f"/api/suites/{draft_id}/publish", headers=owner)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "suite_is_draft"
    roster = (await client.get("/api/users/roster", headers=owner)).json()["items"]
    bob_id = next(u["id"] for u in roster if u["username"] == "df_admin")
    r = await client.post("/api/shares", headers=owner, json={
        "resourceType": "suite", "resourceId": str(draft_id),
        "granteeUserId": bob_id, "mode": "ref"})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "suite_is_draft"
    r = await client.post("/api/shares", headers=owner, json={
        "resourceType": "suite", "resourceId": str(draft_id),
        "granteeUserId": bob_id, "mode": "copy"})
    assert r.status_code == 409

    # 完成编排:命名 + clearDraft(草稿标记清、rev 推进)
    r = await client.patch(f"/api/suites/{draft_id}", headers=owner,
                           json={"name": "编排完成集", "clearDraft": True})
    assert r.status_code == 200 and not r.json()["isDraft"]
    detail = (await client.get(f"/api/suites/{draft_id}", headers=owner)).json()
    assert detail["rev"] == 1
    # 清草稿后可发布
    await client.post(f"/api/suites/{draft_id}/members", headers=owner,
                      json={"scenarioIds": ["sc-df-1"]})
    r = await client.post(f"/api/suites/{draft_id}/publish", headers=owner)
    assert r.status_code == 200, r.text


async def test_access_and_capabilities(client: AsyncClient) -> None:
    """access + 能力位(§7.6 投影):ref 可跑不可改,public 不可跑,
    admin 可改不可代发。"""
    admin = await register_and_login(client, "ac_admin", "ac_admin_pass123")
    owner = await register_and_login(client, "ac_owner", "ac_owner_pass123")
    bob = await register_and_login(client, "ac_bob", "ac_bob_pass123")
    carol = await register_and_login(client, "ac_carol", "ac_carol_pass123")
    await _mk(client, owner, "sc-ac-1")
    sid = await _mk_suite(client, owner, "访问集")
    await client.post(f"/api/suites/{sid}/members", headers=owner,
                      json={"scenarioIds": ["sc-ac-1"]})

    roster = (await client.get("/api/users/roster", headers=owner)).json()["items"]
    bob_id = next(u["id"] for u in roster if u["username"] == "ac_bob")
    r = await client.post("/api/shares", headers=owner, json={
        "resourceType": "suite", "resourceId": str(sid),
        "granteeUserId": bob_id, "mode": "ref"})
    assert r.status_code == 201, r.text

    d = (await client.get(f"/api/suites/{sid}", headers=bob)).json()
    assert d["access"] == "ref" and d["canEdit"] is False
    assert d["canRun"] is True and d["canShare"] is False

    d = (await client.get(f"/api/suites/{sid}", headers=admin)).json()
    assert d["access"] == "admin" and d["canEdit"] is True
    assert d["canShare"] is False  # admin 不可代发(§8.1)

    # carol(无引用)私有套件 → 404;发布后 → public 读者,可读不可跑
    assert (await client.get(f"/api/suites/{sid}",
                             headers=carol)).status_code == 404
    await client.post(f"/api/suites/{sid}/publish", headers=owner)
    d = (await client.get(f"/api/suites/{sid}", headers=carol)).json()
    assert d["access"] == "public" and d["canRun"] is False
    assert d["canEdit"] is False and d["canShare"] is False
