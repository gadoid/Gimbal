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
    # C1 收口(2026-11-22):直通 approved 行落库 → 授权带
    # source_promotion_id 溯源(与 approve 路径同观感;旧「瞬态对象
    # 溯源 NULL = 与手工授权不可区分」已废)。
    assert grants[0].source_promotion_id is not None

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


# ── projectAccountReady 解析口径钉(评审 P2-1:镜像 _resolve_identities)──

async def _seed_ready_fixture(project_id: int) -> tuple[int, int, int]:
    """主档:fin-svc(system=fin)—— 条目名 ≠ 系统名形态(①的靶);
    三个环境 E1(默认)/E2/E3;项目池:default 'other'@E1、username
    'svc1'@E2(非默认,唯一候选靶)、同名双行 'dup'@E1/E2(username-
    ref 歧义靶)。(uq_account_default 部分唯一索引 = 池×系统单默认 →
    歧义靶改由 username-ref 双行构造。)返回 (E1, E2, E3)。"""
    from app.models import Environment, Service
    from app.models.auth_account import AuthAccount

    async with db_module.SessionLocal() as s:
        if (await s.execute(select(Service.id).where(
                Service.name == "fin-svc"))).scalar_one_or_none() is None:
            s.add(Service(name="fin-svc", system="fin", kind="plate"))
        envs: list[int] = []
        for name, is_default in (("测试", True), ("预发", False),
                                 ("压测", False)):
            s.add(Environment(name=name, is_default=is_default))
            await s.flush()
            envs.append((await s.execute(
                select(Environment.id).where(
                    Environment.name == name))).scalar_one())
        e1, e2, e3 = envs
        for username, env, is_default in (
                ("other", e1, True), ("svc1", e2, False),
                ("dup", e1, False), ("dup", e2, False)):
            s.add(AuthAccount(project_id=project_id, system="fin",
                              env_id=env, username=username,
                              password_enc="enc", token_type="Bearer",
                              is_default=is_default))
        await s.commit()
        return e1, e2, e3


async def _seed_entry_full(alias: str, base: str, env_id: int,
                           ref_mode: str = "default",
                           ref_username: str = "") -> None:
    from app.models import Environment, ServiceIdentity

    async with db_module.SessionLocal() as s:
        env = (await s.execute(select(Environment.id).where(
            Environment.is_default.is_(True)))).scalar_one_or_none()
        if env is None:
            s.add(Environment(name="测试", is_default=True))
            await s.flush()
            env = (await s.execute(select(Environment.id).where(
                Environment.is_default.is_(True)))).scalar_one()
        s.add(ServiceIdentity(alias_name=alias, base_service=base,
                              env_id=env_id, ref_mode=ref_mode,
                              ref_username=ref_username))
        await s.commit()


def _ref_draft(scenario_id: str, entry: str) -> dict:
    return make_draft(scenario_id, steps=[{
        "id": "s1", "kind": "step",
        "call": {"service": "fin-svc", "path": "/x",
                 "headers": {"Authorization": f"${{auth.{entry}.token}}"}},
    }])


async def _analyze_entries(client, headers, pid, sid) -> dict:
    r = await client.post(
        f"/api/projects/{pid}/promotions/analyze", headers=headers,
        json={"kind": "scenario", "sourceId": sid})
    assert r.status_code == 200, r.text
    return {e["aliasName"]: e for e in r.json()["identityEntries"]}


class TestProjectAccountReady:
    async def test_ready_mirrors_resolution(self, client: AsyncClient):
        """①name→system 派生:条目 base=fin-svc、池账户 system=fin →
        default-ref 就绪(直比 AuthAccount.system==base_service 恒假);
        ②ref 口径:username-ref 缺命中 → 未就绪(池里有别的默认账户
        不算);③env 偏好非过滤:唯一候选 env 不同 → 就绪;
        多候选无同标签 → 歧义未就绪;主档缺行 → 未就绪。"""
        from app.models.auth_account import AuthAccount

        h_m = await role_headers(client, "ig_rm", role="user")
        pid = await _mk_project("ig-ready", members={"ig_rm": "member"})
        e1, e2, e3 = await _seed_ready_fixture(pid)
        await _seed_entry_full("e-name-sys", "fin-svc", e1)             # ①
        await _seed_entry_full("e-user-miss", "fin-svc", e1,
                               ref_mode="username", ref_username="nope")  # ②
        await _seed_entry_full("e-user-hit", "fin-svc", e1,
                               ref_mode="username", ref_username="svc1")  # ③
        await _seed_entry_full("e-amb", "fin-svc", e3,
                               ref_mode="username", ref_username="dup")   # 歧义
        await _seed_entry_full("e-nosvc", "ghost-base", e1)             # 主档缺
        r = await client.post("/api/scenarios", headers=h_m,
                              json=_ref_draft("sc-ig-ready", "e-name-sys"))
        assert r.status_code == 201, r.text
        # 同场景引用全部条目(模板面拼满)
        from app.core import db as db_module
        from app.models.composer_scenario import ComposerScenario
        from app.services.scenario_store import definition_from_payload
        async with db_module.SessionLocal() as s:
            row = (await s.execute(select(ComposerScenario).where(
                ComposerScenario.scenario_id == "sc-ig-ready"))).scalar_one()
            defn = definition_from_payload(row.payload)
            defn["steps"][0]["call"]["headers"]["Authorization"] = (
                "${auth.e-name-sys.token} ${auth.e-user-miss.token} "
                "${auth.e-user-hit.token} ${auth.e-amb.token} "
                "${auth.e-nosvc.token}")
            row.payload = {"definition": defn}
            await s.commit()
        ents = await _analyze_entries(client, h_m, pid, "sc-ig-ready")
        assert ents["e-name-sys"]["projectAccountReady"] is True    # ①
        assert ents["e-user-miss"]["projectAccountReady"] is False  # ②
        assert ents["e-user-hit"]["projectAccountReady"] is True    # ③
        assert ents["e-amb"]["projectAccountReady"] is False        # 歧义
        assert ents["e-nosvc"]["projectAccountReady"] is False      # 主档缺
        assert "AuthAccount" not in str(ents)
