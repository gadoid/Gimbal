"""promotion 身份授权(决策 1 阶段 4;identity-registry §5 共享即授权):

* analyze 身份条目分区:逐条目 ``{aliasName, baseService, envLabel,
  registered, granted, projectAccountReady}``(slots 平铺名不变);
* execute(无冲突直通复制 ∨ 批准)对引用条目批量 upsert 授权
  (source_promotion_id 溯源;幂等);
* revoke 兜底:reject/withdraw 删授权(当前状态机 approve 终态下
  正常流无授权可删 —— 幂等清理);
* 执行解析不查授权表(拍板 2026-11-20 照默认口径)—— 本表纯管理面。
"""
from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select

from app.core import db as db_module
from app.models.identity_grant import IdentityProjectGrant
from tests.helpers import make_draft, role_headers

from .test_authz_s72_promotions import _mk_project


def _draft_with_ref(scenario_id: str, entry: str) -> dict:
    """fin 服务步骤 + ``${auth.<entry>.token}`` 模板引用(enforce 态下
    条目须先登记 —— 本文件 seeding 顺序即真实操作序)。"""
    return make_draft(scenario_id, steps=[{
        "id": "s1", "kind": "step",
        "call": {"service": "fin", "path": "/x",
                 "headers": {"Authorization": f"${{auth.{entry}.token}}"}},
    }])


async def _seed_entry(alias: str, base: str = "fin") -> int:
    """登记条目(+主档服务行 + 默认环境),返回 identity id。"""
    from app.models import Environment, Service, ServiceIdentity

    async with db_module.SessionLocal() as s:
        env_id = (await s.execute(select(Environment.id).where(
            Environment.is_default.is_(True)))).scalar_one_or_none()
        if env_id is None:
            s.add(Environment(name="测试", is_default=True))
            await s.flush()
            env_id = (await s.execute(select(Environment.id).where(
                Environment.is_default.is_(True)))).scalar_one()
        if (await s.execute(select(Service.id).where(
                Service.name == base))).scalar_one_or_none() is None:
            s.add(Service(name=base, system=base, kind="plate"))
        s.add(ServiceIdentity(alias_name=alias, base_service=base,
                              env_id=env_id, ref_mode="default"))
        await s.commit()
        return (await s.execute(select(ServiceIdentity.id).where(
            ServiceIdentity.alias_name == alias))).scalar_one()


async def _grants(project_id: int) -> list[IdentityProjectGrant]:
    async with db_module.SessionLocal() as s:
        return list((await s.execute(
            select(IdentityProjectGrant).where(
                IdentityProjectGrant.project_id == project_id))).scalars())


async def test_analyze_identity_entries(client: AsyncClient):
    """analyze 身份条目分区:已登记条目 → registered/granted/ready 三态;
    slots 平铺名保持;未登记名 registered=False(enforce 下保存面本已
    拦,分区对历史/旁路面只报事实)。"""
    h_m = await role_headers(client, "ig_am", role="user")
    pid = await _mk_project("ig-ana", members={"ig_am": "member"})
    await _seed_entry("e1", base="fin")
    r = await client.post("/api/scenarios", headers=h_m,
                          json=_draft_with_ref("sc-ig-ana", "e1"))
    assert r.status_code == 201, r.text
    r = await client.post(
        f"/api/projects/{pid}/promotions/analyze", headers=h_m,
        json={"kind": "scenario", "sourceId": "sc-ig-ana"})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["slots"] == ["e1"]
    ents = out["identityEntries"]
    assert len(ents) == 1
    e = ents[0]
    assert e["aliasName"] == "e1" and e["baseService"] == "fin"
    assert e["registered"] is True
    assert e["granted"] is False       # 尚未共享
    assert e["projectAccountReady"] is False  # 项目池无账户行
    assert e["envLabel"]               # 默认环境名回显


async def test_immediate_copy_writes_grants(client: AsyncClient):
    """无冲突直通复制(execute 面)→ 引用条目批量落授权
    (source_promotion_id 溯源);再 analyze → granted=True 翻转。"""
    h_m = await role_headers(client, "ig_dm", role="user")
    pid = await _mk_project("ig-direct", members={"ig_dm": "member"})
    await _seed_entry("e2", base="fin")
    await _seed_entry("e3", base="fin")
    r = await client.post("/api/scenarios", headers=h_m,
                          json=_draft_with_ref("sc-ig-direct", "e2"))
    assert r.status_code == 201, r.text
    # 第二条引用同条目,验证幂等(多场景同条目只落一行)
    d2 = _draft_with_ref("sc-ig-direct2", "e2")
    r = await client.post("/api/scenarios", headers=h_m, json=d2)
    assert r.status_code == 201, r.text

    r = await client.post(f"/api/projects/{pid}/promotions", headers=h_m,
                          json={"kind": "scenario", "sourceId": "sc-ig-direct"})
    assert r.status_code == 201, r.text
    grants = await _grants(pid)
    assert len(grants) == 1
    # 直通路径「不落申请行」→ 溯源位为空(设计语义:非经申请行的共享
    # = NULL;经 approve 申请行的共享带 source_promotion_id,见下测)
    assert grants[0].source_promotion_id is None

    # 幂等:第二次共享同条目(另一场景)不重复落行
    r = await client.post(f"/api/projects/{pid}/promotions", headers=h_m,
                          json={"kind": "scenario",
                                "sourceId": "sc-ig-direct2"})
    assert r.status_code == 201, r.text
    assert len(await _grants(pid)) == 1

    # 授权可观测:re-analyze granted 翻转
    r = await client.post(
        f"/api/projects/{pid}/promotions/analyze", headers=h_m,
        json={"kind": "scenario", "sourceId": "sc-ig-direct"})
    assert r.json()["identityEntries"][0]["granted"] is True


async def test_approve_path_grants_carry_provenance(client: AsyncClient):
    """冲突 → pending → approve 面:授权带 source_promotion_id 溯源
    (申请行持久化,promotion id 落授权行)。"""
    h_m = await role_headers(client, "ig_pm", role="user")
    h_adm = await role_headers(client, "ig_pa", role="user")
    pid = await _mk_project("ig-prov", members={"ig_pm": "member",
                                                "ig_pa": "admin"})
    await _seed_entry("e6", base="fin")
    await _seed_entry("e7", base="fin")
    r = await client.post("/api/scenarios", headers=h_m,
                          json=_draft_with_ref("sc-ig-prov", "e6"))
    assert r.status_code == 201, r.text
    from .test_authz_s72_promotions import _put_carry, _put_personal_cfg
    await _put_personal_cfg(client, h_m, "fin", {"host": "mine"})
    await _put_carry(client, h_adm, "project", "fin",
                     {"host": "proj"}, project_id=pid)
    r = await client.post(f"/api/projects/{pid}/promotions", headers=h_m,
                          json={"kind": "scenario", "sourceId": "sc-ig-prov"})
    assert r.status_code == 201, r.text
    promo_id = r.json()["promotionId"]
    r = await client.post(f"/api/project-promotions/{promo_id}/approve",
                          headers=h_adm,
                          json={"decisions": [
                              {"service": "fin", "path": "host",
                               "use": "source", "sourceValue": "mine"}]})
    assert r.status_code == 200, r.text
    grants = await _grants(pid)
    assert len(grants) == 1
    assert grants[0].source_promotion_id == promo_id


async def test_withdraw_revoke_is_noop_safe(client: AsyncClient):
    """撤回(pending → withdrawn)走 revoke 兜底:pending 无授权可删,
    幂等安全(当前状态机 approve 终态,正常流本无授权)。"""
    h_m = await role_headers(client, "ig_wm", role="user")
    h_adm = await role_headers(client, "ig_wa", role="user")
    pid = await _mk_project("ig-wd", members={"ig_wm": "member",
                                              "ig_wa": "admin"})
    await _seed_entry("e4", base="fin")
    await _seed_entry("e5", base="fin")
    r = await client.post("/api/scenarios", headers=h_m,
                          json=_draft_with_ref("sc-ig-wd", "e4"))
    assert r.status_code == 201, r.text
    # 制造冲突 → pending 申请
    from .test_authz_s72_promotions import _put_carry
    await _put_carry(client, h_adm, "project", "fin",
                     {"host": "proj"}, project_id=pid)
    from .test_authz_s72_promotions import _put_personal_cfg
    await _put_personal_cfg(client, h_m, "fin", {"host": "mine"})
    r = await client.post(f"/api/projects/{pid}/promotions", headers=h_m,
                          json={"kind": "scenario", "sourceId": "sc-ig-wd"})
    assert r.status_code == 201, r.text
    promo_id = r.json()["promotionId"]
    r = await client.post(f"/api/project-promotions/{promo_id}/withdraw",
                          headers=h_m)
    assert r.status_code == 200, r.text
    assert await _grants(pid) == []
