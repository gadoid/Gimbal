"""S7.4 引用分享退役:副本分享契约 + 转换服务。

- POST /shares 仅剩 copy(mode=ref 422 枚举收窄);属主单判;
  引用面(列表/撤销/fork/referrers)整体 404/405 退役;
- 转换服务 share_ref_retire.convert_ref:场景/套件 → grantee 私有副本
  (forked_from 三件套 + 跨属主剥凭证)、删 ref 行幂等、双方通知、审计;
- 表 B ref 谓词退役:私有场景对非属主 404(can/can_run 收敛)。
"""
from __future__ import annotations

import sqlalchemy as sa
from httpx import AsyncClient

from app.core import db as db_module
from app.services.share_ref_retire import RefRow, convert_ref, list_refs
from tests.helpers import make_draft, register_and_login


async def _mk(client: AsyncClient, h: dict, sid: str) -> None:
    r = await client.post("/api/scenarios", headers=h, json=make_draft(sid))
    assert r.status_code in (200, 201), r.text


async def _uid(client: AsyncClient, admin_h: dict, username: str) -> int:
    roster = (await client.get("/api/users/roster", headers=admin_h)).json()["items"]
    return next(u["id"] for u in roster if u["username"] == username)


async def test_copy_only_and_ref_retired(client: AsyncClient) -> None:
    """mode=ref 422(枚举收窄);引用面路由退役;副本照常。"""
    await register_and_login(client, "s74_adm", "s74_adm_pass123")
    owner = await register_and_login(client, "s74_own", "s74_own_pass123")
    bob = await register_and_login(client, "s74_bob", "s74_bob_pass123")
    await _mk(client, owner, "sc-s74-1")
    bob_id = await _uid(client,
                        await register_and_login(client, "s74_adm2", "x1111111"), "s74_bob")

    # ref 模式 422(枚举收窄,前端已无入口)
    r = await client.post("/api/shares", headers=owner, json={
        "resourceType": "scenario", "resourceId": "sc-s74-1",
        "granteeUserId": bob_id, "mode": "ref"})
    assert r.status_code == 422, r.text
    assert "copy" in r.text

    # 副本分享照常(mode 缺省 = copy)
    r = await client.post("/api/shares", headers=owner, json={
        "resourceType": "scenario", "resourceId": "sc-s74-1",
        "granteeUserId": bob_id})
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["mode"] == "copy" and out["scenarioId"]
    # 副本归 bob:草稿可读;原件不可读(无引用通道)
    assert (await client.get(
        f"/api/scenarios/{out['scenarioId']}/draft", headers=bob)).status_code == 200
    assert (await client.get("/api/scenarios/sc-s74-1/draft",
                             headers=bob)).status_code == 404

    # 引用面路由退役
    assert (await client.get("/api/shares", headers=owner)).status_code == 405
    assert (await client.get("/api/shares/referrers", headers=owner,
                             params={"scenarioId": "sc-s74-1"})
            ).status_code == 404
    assert (await client.post("/api/shares/1/fork", headers=bob)).status_code in (404, 405)
    assert (await client.delete("/api/shares/1", headers=owner)).status_code in (404, 405)

    # admin 不可代发(§8.1 不变)
    admin = await register_and_login(client, "s74_adm3", "x1111111")
    r = await client.post("/api/shares", headers=admin, json={
        "resourceType": "scenario", "resourceId": "sc-s74-1",
        "granteeUserId": bob_id, "mode": "copy"})
    assert r.status_code == 403


async def _mk_ref(grantee: int, scenario_id: str | None = None,
                  suite_id: int | None = None) -> RefRow:
    """直插存量引用行(模拟转换命令的输入;Q2 存量形态)。

    表随模型退役不再进 create_all —— 按 0013 原始定义现建(生产表由
    迁移 0049 在转换完成前才删)。"""
    async with db_module.SessionLocal() as s:
        await s.execute(sa.text("""
            CREATE TABLE IF NOT EXISTS share_refs (
                id SERIAL PRIMARY KEY,
                grantee_user_id INTEGER NOT NULL
                    REFERENCES users(id) ON DELETE CASCADE,
                scenario_id VARCHAR(128),
                suite_id INTEGER,
                granted_by_name VARCHAR(128) NOT NULL,
                granted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                CONSTRAINT fk_share_refs_scenario FOREIGN KEY (scenario_id)
                    REFERENCES composer_scenarios(scenario_id) ON DELETE CASCADE,
                CONSTRAINT fk_share_refs_suite FOREIGN KEY (suite_id)
                    REFERENCES suites(id) ON DELETE CASCADE,
                CONSTRAINT ck_share_refs_exactly_one CHECK (
                    (scenario_id IS NULL) <> (suite_id IS NULL))
            )"""))
        rid = (await s.execute(sa.text(
            "INSERT INTO share_refs (grantee_user_id, scenario_id,"
            " suite_id, granted_by_name) VALUES (:g, :sc, :su, :n)"
            " RETURNING id"),
            {"g": grantee, "sc": scenario_id, "su": suite_id,
             "n": "存量属主"})).scalar()
        await s.commit()
        return RefRow(id=rid, grantee_user_id=grantee,
                      scenario_id=scenario_id, suite_id=suite_id)


async def test_convert_ref_scenario(client: AsyncClient) -> None:
    """转换:场景 ref → grantee 私有副本(forked_from + 剥凭证),
    ref 行删除(幂等锚),双方通知 + 审计。"""
    await register_and_login(client, "cv_adm", "cv_adm_pass123")
    owner = await register_and_login(client, "cv_own", "cv_own_pass123")
    bob = await register_and_login(client, "cv_bob", "cv_bob_pass123")
    # 带内置凭证的场景(跨属主拷贝须剥):config 挂 definition
    draft = make_draft("sc-cv-1")
    draft["definition"]["config"]["users"] = {
        "qa1": {"url": "http://x", "username": "u",
                "password": "p", "token_type": "Bearer"}}
    r = await client.post("/api/scenarios", headers=owner, json=draft)
    assert r.status_code in (200, 201), r.text

    async with db_module.SessionLocal() as s:
        owner_id = (await s.execute(sa.text(
            "SELECT id FROM users WHERE username='cv_own'"))).scalar()
        bob_id = (await s.execute(sa.text(
            "SELECT id FROM users WHERE username='cv_bob'"))).scalar()
    ref = await _mk_ref(bob_id, scenario_id="sc-cv-1")

    async with db_module.SessionLocal() as s:
        out = await convert_ref(s, ref)
    assert out["kind"] == "scenario" and out["granteeId"] == bob_id
    copy_id = out["copyId"]
    # 副本可读、原件不可读(ref 通道已断)
    assert (await client.get(
        f"/api/scenarios/{copy_id}/draft", headers=bob)).status_code == 200
    assert (await client.get("/api/scenarios/sc-cv-1/draft",
                             headers=bob)).status_code == 404
    # 副本无内置凭证(跨属主剥离):draft 读面按实际形状取 config
    d = (await client.get(f"/api/scenarios/{copy_id}/draft",
                          headers=bob)).json()
    body = d.get("draft") if isinstance(d, dict) and "draft" in d else d
    cfg = (body or {}).get("config") if isinstance(body, dict) else None
    if cfg is None and isinstance(d, dict):
        cfg = (d.get("definition") or {}).get("config")
    assert not (cfg or {}).get("users"), d

    # ref 行已删;通知双方(handoff + converted);审计 share_ref.retire
    async with db_module.SessionLocal() as s:
        n = (await s.execute(sa.text(
            "SELECT count(*) FROM share_refs WHERE id = :rid"),
            {"rid": ref.id})).scalar()
        assert n == 0
        notes = (await s.execute(sa.text(
            "SELECT type, user_id FROM notifications"
            " WHERE resource_id = :rid"), {"rid": copy_id})).all()
        types = {(t, uid) for t, uid in notes}
        assert ("resource_handoff", bob_id) in types
        assert ("share_ref_converted", owner_id) in types
        audit = (await s.execute(sa.text(
            "SELECT action FROM audit_logs"
            " WHERE resource_id = :rid"), {"rid": copy_id})).scalar()
        assert audit == "share_ref.retire"

    # 幂等:同 grantee 同源再插 ref(漏跑行)→ 复用既有 fork 不重拷
    ref2 = await _mk_ref(bob_id, scenario_id="sc-cv-1")
    async with db_module.SessionLocal() as s:
        out2 = await convert_ref(s, ref2)
    assert out2["copyId"] == copy_id


async def test_convert_ref_suite(client: AsyncClient) -> None:
    """转换:套件 ref → deep_copy_suite(成员副本 + forked 三件套)。"""
    await register_and_login(client, "cs_adm", "cs_adm_pass123")
    owner = await register_and_login(client, "cs_own", "cs_own_pass123")
    bob = await register_and_login(client, "cs_bob", "cs_bob_pass123")
    await _mk(client, owner, "sc-cs-1")
    r = await client.post("/api/suites", headers=owner,
                          json={"name": "cs-集", "description": ""})
    sid = r.json()["suiteId"]
    r = await client.post(f"/api/suites/{sid}/members", headers=owner,
                          json={"scenarioIds": ["sc-cs-1"]})
    assert r.status_code == 200, r.text

    async with db_module.SessionLocal() as s:
        bob_id = (await s.execute(sa.text(
            "SELECT id FROM users WHERE username='cs_bob'"))).scalar()
    ref = await _mk_ref(bob_id, suite_id=sid)

    async with db_module.SessionLocal() as s:
        out = await convert_ref(s, ref)
    assert out["kind"] == "suite"
    copy_suite = int(out["copyId"])
    # 副本套件可访问,成员场景归 bob
    assert (await client.get(f"/api/suites/{copy_suite}",
                             headers=bob)).status_code == 200
    # 原 suite 对 bob 不可见(ref 通道断)
    assert (await client.get(f"/api/suites/{sid}",
                             headers=bob)).status_code in (403, 404)


async def test_private_non_owner_denied_after_retire(client: AsyncClient) -> None:
    """表 B ref 谓词退役:私有场景/套件对非属主 404/403(can_run 收敛)。"""
    await register_and_login(client, "pv_adm", "pv_adm_pass123")
    owner = await register_and_login(client, "pv_own", "pv_own_pass123")
    bob = await register_and_login(client, "pv_bob", "pv_bob_pass123")
    await _mk(client, owner, "sc-pv-1")
    assert (await client.get("/api/scenarios/sc-pv-1/draft",
                             headers=bob)).status_code == 404
    r = await client.post("/api/runs", headers=bob, json={
        "scenarioId": "sc-pv-1"})
    assert r.status_code in (403, 404)
    # 数据集不再随引用闭包
    r = await client.get("/api/data-sets", headers=bob,
                         params={"scenarioId": "sc-pv-1"})
    body = r.json() if r.status_code == 200 else []
    items = body.get("items", body) if isinstance(body, dict) else body
    assert items == []
