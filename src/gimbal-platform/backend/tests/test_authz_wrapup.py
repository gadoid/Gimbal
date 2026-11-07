"""authz 收尾(2026-11-07):守卫白名单清零后的行为钉。

① 变更适配编辑权 = 场景属主单判 —— 原 super_admin 旁路(getattr 形态
   角色字面量,守卫前三种形状漏扫)删除:Admin+ 对他人私有场景无任何
   动词(方案 1.3)。
② 个人别名(ownerUserId)写面 = users.manage,错误契约统一为
   ``capability_forbidden``(取代 ``admin_only: …`` 字符串,方案 9.7)。
③ 用户管理门按表 A 判定:admin(ops.write)不能改他人资料/角色。
"""
from __future__ import annotations

from httpx import AsyncClient

from tests.helpers import make_draft, role_headers


async def test_super_admin_cannot_adapt_others_private_scenario(
        client: AsyncClient):
    h_owner = await role_headers(client, "wu_own", role="user")
    r = await client.post("/api/scenarios", headers=h_owner,
                          json=make_draft("sc-wu-ad"))
    assert r.status_code in (200, 201), r.text
    h_sa = await role_headers(client, "wu_sa", role="super_admin")
    r = await client.post("/api/adaptations/submit", headers=h_sa, json={
        "scenarioId": "sc-wu-ad", "ops": [], "targetRevision": "1.0#1",
        "saveMode": "direct"})
    assert r.status_code == 403, r.text
    assert "not_scenario_owner" in r.text


async def test_personal_alias_requires_users_manage(client: AsyncClient):
    h_adm = await role_headers(client, "wu_adm", role="admin")
    r = await client.post("/api/service-aliases", headers=h_adm, json={
        "aliasName": "wu-personal", "baseUrl": "https://p.local",
        "ownerUserId": 1})
    assert r.status_code == 403, r.text
    detail = r.json()["detail"]
    assert detail["code"] == "capability_forbidden"
    assert detail["capability"] == "users.manage"


async def test_admin_cannot_patch_other_users(client: AsyncClient):
    from sqlalchemy import select as sa_select

    from app.core import db as db_module
    from app.models.user import User

    await role_headers(client, "wu_victim", role="user")
    h_adm = await role_headers(client, "wu_adm2", role="admin")
    async with db_module.SessionLocal() as s:
        vid = (await s.execute(sa_select(User.id).where(
            User.username == "wu_victim"))).scalar_one()
    r = await client.patch(f"/api/users/{vid}", headers=h_adm,
                           json={"role": "admin"})
    assert r.status_code == 403, r.text
    h_sa = await role_headers(client, "wu_sa2", role="super_admin")
    r = await client.patch(f"/api/users/{vid}", headers=h_sa,
                           json={"role": "admin"})
    assert r.status_code == 200, r.text


async def test_batch_op_endpoints_require_users_manage(client: AsyncClient):
    """④ 适配批次内写操作(补 op / 应用 / 跳过 / 改 payload / 回滚)与批次
    详情同门 users.manage —— 此前仅需登录,任何用户可经批次改写全局
    carry 与他人场景。门在取数之前,不存在的 id 也先 403。"""
    h_user = await role_headers(client, "wu_bu", role="user")
    h_adm = await role_headers(client, "wu_ba", role="admin")
    calls = [
        ("post", "/api/adaptations/batches/no-such/ops",
         {"opType": "addCarryBinding", "payload": {}}),
        ("post", "/api/adaptations/ops/999999/apply", None),
        ("post", "/api/adaptations/ops/999999/skip", None),
        ("patch", "/api/adaptations/ops/999999", {"payload": {}}),
        ("post", "/api/adaptations/batches/no-such/rollback", None),
    ]
    for h in (h_user, h_adm):
        for method, path, body in calls:
            kw = {"headers": h}
            if body is not None:
                kw["json"] = body
            r = await getattr(client, method)(path, **kw)
            assert r.status_code == 403, (method, path, r.text)
            assert r.json()["detail"]["code"] == "capability_forbidden"
    h_sa = await role_headers(client, "wu_bs", role="super_admin")
    r = await client.post("/api/adaptations/ops/999999/apply", headers=h_sa)
    assert r.status_code == 404, r.text
