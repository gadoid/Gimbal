"""权限域二期 P2:引用分享核心链路测试。

《Suite成员层、引用分享与浏览镜头-设计方案》§7/§8.2 验收面:
- 判定式三处同步(PG 谓词经 can_read/can_run 对象级;SQLite 兜底同口径);
- 引用者:可读定义/方案/数据集,可执行单场景与 rerun,写 403,再分享被拒;
- 引用闭包:引用 suite ⇒ 覆盖全部成员;引用单场景不带来 suite 访问;
- 撤销即时生效;退订不通知;admin 撤销入审计;admin 不能代发分享;
- 转为副本:原引用保留;副本 forked_from 三件套;
- suite 深拷贝:成员逐个复制 + 来源字段;发布联动(级联/连带下架/加入确认)。
"""
from __future__ import annotations

from httpx import AsyncClient

from tests.helpers import make_draft, register_and_login


async def _mk(client: AsyncClient, h: dict, sid: str) -> None:
    r = await client.post("/api/scenarios", headers=h, json=make_draft(sid))
    assert r.status_code in (200, 201), r.text


async def _mk_suite(client: AsyncClient, h: dict, name: str,
                    member: str | None = None) -> int:
    r = await client.post("/api/suites", headers=h,
                          json={"name": name, "description": ""})
    assert r.status_code == 201, r.text
    sid = r.json()["suiteId"]
    if member:
        r = await client.post(f"/api/suites/{sid}/members", headers=h,
                              json={"scenarioIds": [member]})
        assert r.status_code == 200, r.text
    return sid


async def test_ref_grants_read_and_run(client: AsyncClient) -> None:
    """引用者:读定义/方案/数据集 ✓;执行 ✓;写 403;再分享被拒。"""
    await register_and_login(client, "sh_admin", "sh_admin_pass123")
    owner = await register_and_login(client, "sh_owner", "sh_owner_pass123")
    bob = await register_and_login(client, "sh_bob", "sh_bob_pass123")
    await _mk(client, owner, "sc-sh-1")

    # 属主发起引用分享(admin 不可代发)
    admin = await register_and_login(client, "sh_admin2", "sh_admin2_pass123")
    # 从 /api/users/roster 找 bob id(人员选择器同款,§7.7)
    roster = (await client.get("/api/users/roster", headers=admin)).json()["items"]
    bob_id = next(u["id"] for u in roster if u["username"] == "sh_bob")
    r = await client.post("/api/shares", headers=admin, json={
        "resourceType": "scenario", "resourceId": "sc-sh-1",
        "granteeUserId": bob_id, "mode": "ref"})
    assert r.status_code == 403, r.text  # admin 不可代他人分享(§8.1)

    r = await client.post("/api/shares", headers=owner, json={
        "resourceType": "scenario", "resourceId": "sc-sh-1",
        "granteeUserId": bob_id, "mode": "ref"})
    assert r.status_code == 201, r.text
    ref_id = r.json()["id"]

    # 引用者:读定义/详情/方案/数据集 ✓(闭包,§7.4)
    assert (await client.get("/api/scenarios/sc-sh-1/draft",
                             headers=bob)).status_code == 200
    assert (await client.get("/api/scenarios/sc-sh-1",
                             headers=bob)).status_code == 200
    assert (await client.get(
        "/api/scenarios/sc-sh-1/run-schemes", headers=bob)).status_code == 200
    assert (await client.get("/api/data-sets",
                             headers=bob,
                             params={"scenarioId": "sc-sh-1"})).status_code == 200

    # 列表可见(all 上限内含被引用)
    r = await client.get("/api/scenarios?scope=all", headers=bob)
    assert any(i["meta"]["scenarioId"] == "sc-sh-1" for i in r.json()["items"])

    # 写 403
    r = await client.put("/api/scenarios/sc-sh-1", headers=bob,
                         json=make_draft("sc-sh-1"))
    assert r.status_code == 403

    # 再分享被拒(副本才可,§7.1)
    r = await client.post("/api/shares", headers=bob, json={
        "resourceType": "scenario", "resourceId": "sc-sh-1",
        "granteeUserId": bob_id, "mode": "ref"})
    assert r.status_code in (403, 404)

    # 退订(被分享人;不通知属主)
    r = await client.delete(f"/api/shares/{ref_id}", headers=bob)
    assert r.status_code == 204
    # 撤销即时生效(§7.5-3):下一次请求即失效
    assert (await client.get("/api/scenarios/sc-sh-1/draft",
                             headers=bob)).status_code == 404


async def test_ref_run_and_rerun(client: AsyncClient) -> None:
    """引用者可执行单场景(POST /runs 不再 not_owner);引用 suite 覆盖成员;
    引用单场景不带来 suite 访问(§7.4)。"""
    await register_and_login(client, "rr_admin", "rr_admin_pass123")
    owner = await register_and_login(client, "rr_owner", "rr_owner_pass123")
    bob = await register_and_login(client, "rr_bob", "rr_bob_pass123")
    await _mk(client, owner, "sc-rr-1")
    await _mk(client, owner, "sc-rr-2")
    suite_id = await _mk_suite(client, owner, "回归", "sc-rr-1")

    roster = (await client.get(
        "/api/users/roster", headers=owner)).json()["items"]
    bob_id = next(u["id"] for u in roster if u["username"] == "rr_bob")

    # 引用 suite ⇒ 覆盖全部成员(闭包)
    r = await client.post("/api/shares", headers=owner, json={
        "resourceType": "suite", "resourceId": str(suite_id),
        "granteeUserId": bob_id, "mode": "ref"})
    assert r.status_code == 201, r.text

    # 成员场景:读 + 执行入口判定过(执行因 plate 不可用以 5xx/4xx
    # 业务因失败,但**不得**是 403 not_owner —— 权限闸已过)
    assert (await client.get("/api/scenarios/sc-rr-1/draft",
                             headers=bob)).status_code == 200
    r = await client.post("/api/runs", headers=bob, json={
        "scenarioId": "sc-rr-1"})
    assert r.status_code != 403 or "not_owner" not in r.text

    # 非 suite 内的场景对 bob 不可读(引用不外溢)
    assert (await client.get("/api/scenarios/sc-rr-2/draft",
                             headers=bob)).status_code == 404
    # suite 详情可读(引用)
    assert (await client.get(f"/api/suites/{suite_id}",
                             headers=bob)).status_code == 200

    # 引用单场景不带来所属 suite 访问:换一个方向验证
    r = await client.post("/api/shares", headers=owner, json={
        "resourceType": "scenario", "resourceId": "sc-rr-2",
        "granteeUserId": bob_id, "mode": "ref"})
    assert r.status_code == 201
    r2 = await client.post("/api/shares", headers=owner, json={
        "resourceType": "scenario", "resourceId": "sc-rr-2",
        "granteeUserId": bob_id, "mode": "ref"})
    assert r2.status_code == 201  # 幂等 upsert(§7.7)


async def test_fork_and_copy(client: AsyncClient) -> None:
    """转为副本:原引用保留;副本写 forked_from;suite 深拷贝成员级联。"""
    await register_and_login(client, "fk_admin", "fk_admin_pass123")
    owner = await register_and_login(client, "fk_owner", "fk_owner_pass123")
    bob = await register_and_login(client, "fk_bob", "fk_bob_pass123")
    await _mk(client, owner, "sc-fk-1")
    suite_id = await _mk_suite(client, owner, "冒烟", "sc-fk-1")

    roster = (await client.get(
        "/api/users/roster", headers=owner)).json()["items"]
    bob_id = next(u["id"] for u in roster if u["username"] == "fk_bob")

    # 场景引用 → fork
    r = await client.post("/api/shares", headers=owner, json={
        "resourceType": "scenario", "resourceId": "sc-fk-1",
        "granteeUserId": bob_id, "mode": "ref"})
    ref_id = r.json()["id"]
    r = await client.post(f"/api/shares/{ref_id}/fork", headers=bob)
    assert r.status_code == 201, r.text
    copy_sid = r.json()["scenarioId"]
    # 原引用保留(§7.7);副本归 bob 可写
    assert (await client.get("/api/scenarios/sc-fk-1/draft",
                             headers=bob)).status_code == 200
    assert (await client.get(f"/api/scenarios/{copy_sid}",
                             headers=bob)).status_code == 200

    # suite copy:深拷贝(§7.8)
    r = await client.post("/api/shares", headers=owner, json={
        "resourceType": "suite", "resourceId": str(suite_id),
        "granteeUserId": bob_id, "mode": "copy"})
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["memberCount"] == 1
    new_suite = out["suiteId"]
    detail = (await client.get(f"/api/suites/{new_suite}",
                               headers=bob)).json()
    assert detail["memberCount"] == 1
    assert detail["members"][0]["scenarioId"] != "sc-fk-1"  # 是新副本

    # suite ref → fork:forked_from_owner_name 记**原属主**(评审补记修复,
    # 此前误写转副本人自己)
    r = await client.post("/api/shares", headers=owner, json={
        "resourceType": "suite", "resourceId": str(suite_id),
        "granteeUserId": bob_id, "mode": "ref"})
    sref_id = r.json()["id"]
    r = await client.post(f"/api/shares/{sref_id}/fork", headers=bob)
    assert r.status_code == 201, r.text
    forked_id = r.json()["suiteId"]
    from sqlalchemy import select as _sel

    from app.core import db as db_module
    from app.models.suite import Suite as SuiteRow
    async with db_module.SessionLocal() as s:
        src_name = (await s.execute(
            _sel(SuiteRow.forked_from_owner_name).where(
                SuiteRow.id == forked_id))).scalar_one()
    assert src_name == "fk_owner"  # 原属主,而非转副本人 fk_bob

    # direction=in 出参:scenarioName / memberCount 反查(评审补记补齐;
    # Suite「共享给我的」行「N 个场景」此前空白)
    r = await client.get("/api/shares?direction=in", headers=bob)
    items = {i["resourceType"]: i for i in r.json()}
    assert items["scenario"]["scenarioName"] == "Test"  # make_draft 缺省名
    assert items["scenario"]["memberCount"] is None
    assert items["suite"]["memberCount"] == 1
    assert items["suite"]["scenarioName"] is None


async def test_revoke_by_owner_and_admin(client: AsyncClient) -> None:
    """撤销:属主可撤(通知被分享人);admin 可撤(入审计);退订免通知。"""
    # fresh_db 下首个注册者 = 真 admin(M2.5 口径);rv_admin 即 admin
    admin = await register_and_login(client, "rv_admin", "rv_admin_pass123")
    owner = await register_and_login(client, "rv_owner", "rv_owner_pass123")
    bob = await register_and_login(client, "rv_bob", "rv_bob_pass123")
    await _mk(client, owner, "sc-rv-1")

    roster = (await client.get(
        "/api/users/roster", headers=owner)).json()["items"]
    bob_id = next(u["id"] for u in roster if u["username"] == "rv_bob")
    # 属主撤
    r = await client.post("/api/shares", headers=owner, json={
        "resourceType": "scenario", "resourceId": "sc-rv-1",
        "granteeUserId": bob_id, "mode": "ref"})
    rid = r.json()["id"]
    r = await client.delete(f"/api/shares/{rid}", headers=owner)
    assert r.status_code == 204
    assert (await client.get("/api/scenarios/sc-rv-1/draft",
                             headers=bob)).status_code == 404

    # admin 撤(入审计)——rv_admin 是本测试首个注册者 = 真 admin
    r = await client.post("/api/shares", headers=owner, json={
        "resourceType": "scenario", "resourceId": "sc-rv-1",
        "granteeUserId": bob_id, "mode": "ref"})
    rid2 = r.json()["id"]
    r = await client.delete(f"/api/shares/{rid2}", headers=admin)
    assert r.status_code == 204
    notes = (await client.get("/api/notifications", headers=bob)).json()
    items = notes.get("items") or notes.get("data", {}).get("items") or []
    assert any("撤销" in (n.get("title") or "") for n in items)


async def test_publish_linkage(client: AsyncClient) -> None:
    """发布联动:suite publish 级联成员;公共 suite 加私有成员 409→确认发布;
    成员下架 ⇒ 公共 suite 连带下架(§7.9)。"""
    await register_and_login(client, "pb_admin", "pb_admin_pass123")
    owner = await register_and_login(client, "pb_owner", "pb_owner_pass123")
    await _mk(client, owner, "sc-pb-1")
    await _mk(client, owner, "sc-pb-2")
    suite_id = await _mk_suite(client, owner, "发布集", "sc-pb-1")

    # suite 先发布:级联发布未发布成员(sc-pb-1 一并 public)
    r = await client.post(f"/api/suites/{suite_id}/publish", headers=owner)
    assert r.status_code == 200
    assert r.json()["visibility"] == "public"
    assert r.json()["publishedMembers"] == ["sc-pb-1"]  # 级联回执(§7.9)

    # 公共 suite 加第二个私有成员 → 409 列出;确认后发布+入组同事务
    r = await client.post(f"/api/suites/{suite_id}/members", headers=owner,
                          json={"scenarioIds": ["sc-pb-2"]})
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "suite_member_publish_required"
    r = await client.post(f"/api/suites/{suite_id}/members", headers=owner,
                          json={"scenarioIds": ["sc-pb-2"],
                                "publishUnpublished": True})
    assert r.status_code == 200, r.text

    # 成员下架 ⇒ 公共 suite 连带下架
    r = await client.post("/api/scenarios/sc-pb-1/unpublish", headers=owner)
    assert r.status_code == 200
    detail = (await client.get(f"/api/suites/{suite_id}",
                               headers=owner)).json()
    assert detail["visibility"] == "private"

    # suite unpublish:成员 public 状态独立保留
    await client.post("/api/scenarios/sc-pb-1/publish", headers=owner)
    await client.post(f"/api/suites/{suite_id}/publish", headers=owner)
    r = await client.delete(f"/api/suites/{suite_id}/publish",
                            headers=owner)
    assert r.status_code == 200
    pub = (await client.get("/api/scenarios/sc-pb-1", headers=owner)).json()
    assert pub["visibility"] == "public"
