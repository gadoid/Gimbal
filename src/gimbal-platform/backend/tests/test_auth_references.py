"""auth_references 凭证反查(配套方案 §1,2026-09-20)。

四类引用 + 可见性 + 删除拦截窄口径:
* template(steps ${auth.*})/scheme(run 方案绑定)= 真依赖,计数与 409;
* snapshot(config.users 同名键)= 卫生信号,面板展示不计数不阻断;
* alias(service_aliases.credential_alias)= 查表,面板展示;
* 场景名按 can_read_scenario 过滤(admin 全量 / public / owner),
  剩余 = hidden_count(只给数不泄露标题);
* DELETE 409 仅本人场景的 template/scheme;他人场景(即使 public
  我能跑)与快照/别名绑定不阻断 — 名字引用按执行者池解析。
"""
from __future__ import annotations

import sqlalchemy as sa

from app.core import db as db_module
from app.models.composer_run_scheme import ComposerRunScheme
from app.models.composer_scenario import ComposerScenario
from app.models.service_alias import ServiceAlias
from app.models.user import User
from app.schemas.scenario_composer import ScenarioDraft
from app.services import scenario_store

from .helpers import make_draft, register_and_login

ALIAS = "qa1"


async def _uid(username: str) -> int:
    async with db_module.SessionLocal() as s:
        return (await s.execute(
            sa.select(User).where(User.username == username))).scalar_one().id


def _tpl_step(endpoint: str, header_value: str) -> dict:
    return {"api": {"view_hints": {"endpoint_id": endpoint},
                    "headers": {"Authorization": header_value}},
            "request": {"body": {}}}


async def _seed(owner_ids: dict[str, int]) -> None:
    """六场景 × 引用形状:
    sc-own-tpl   本人私有,模板引用 → 阻断 + member 可见
    sc-own-sch   本人私有,方案绑定引用(无模板)→ 阻断
    sc-own-snap  本人私有,仅 config.users 快照 → 不阻断,kind=snapshot
    sc-other-pub 他人 public,模板 → member 可见,不阻断(能跑但名字引用)
    sc-other-prv 他人 private,模板 → member 不可见(hidden),admin 可见
    sc-clean     本人私有,零引用 → 计数 0
    """
    async with db_module.SessionLocal() as s:
        async def _create(sid: str, owner: str, visibility: str, steps) -> None:
            await scenario_store.create(
                s, ScenarioDraft.model_validate(make_draft(
                    sid, steps=steps, **{"name": sid})),
                owner=owner, owner_id=owner_ids[owner])
            if visibility != "private":
                await scenario_store.set_visibility(s, sid, visibility)

        await _create("sc-own-tpl", "own_user", "private",
                      [_tpl_step("fin.order.add", "${auth.qa1.token}")])
        await _create("sc-own-sch", "own_user", "private",
                      [_tpl_step("fin.order.get", "static")])
        await _create("sc-own-snap", "own_user", "private",
                      [_tpl_step("fin.order.book", "static")])
        await _create("sc-other-pub", "other_user", "public",
                      [_tpl_step("fin.order.add", "${auth.qa1.token}")])
        await _create("sc-other-prv", "other_user", "private",
                      [_tpl_step("fin.order.add", "${auth.qa1.token}")])
        await _create("sc-clean", "own_user", "private",
                      [_tpl_step("fin.order.get", "static")])

        # sc-own-snap 的 config.users 快照(键 = 凭证别名)
        row = (await s.execute(
            sa.select(ComposerScenario).where(
                ComposerScenario.scenario_id == "sc-own-snap")
        )).scalar_one()
        payload = dict(row.payload or {})
        defn = dict(payload.get("definition") or {})
        cfg = dict(defn.get("config") or {})
        cfg["users"] = {ALIAS: {"url": "https://auth", "username": "u",
                                "password": "p", "token_type": "Bearer"}}
        defn["config"] = cfg
        payload["definition"] = defn
        row.payload = payload

        # sc-own-sch 的方案绑定(authAlias,无模板)
        # is_default=False:create 已自动建默认方案(partial unique
        # 每场景一个 default)— 扫描面读全部方案的绑定,与 default 无关
        s.add(ComposerRunScheme(
            scheme_id="rs-own-1", scenario_id="sc-own-sch", name="方案二",
            is_default=False, payload={"serviceBindings": {
                "fin-service": {"authAlias": ALIAS}}},
        ))

        # 别名表绑定(共享配置,不阻断)
        s.add(ServiceAlias(alias_name="fin-service-uat", base_service="fin-service",
                           group_tag="测试", credential_alias=ALIAS))
        await s.commit()


async def _setup(client):
    # ref_admin 注册在先:首个用户自动 admin(auth.py:72),
    # 后续 own_user/other_user 恰为普通用户
    admin = await register_and_login(client, "ref_admin", "pw123456")
    own = await register_and_login(client, "own_user", "pw123456")
    await register_and_login(client, "other_user", "pw123456")
    owner_ids = {u: await _uid(u) for u in ("own_user", "other_user")}
    await _seed(owner_ids)
    return own, admin


async def test_references_four_kinds_and_visibility(client):
    own, admin = await _setup(client)

    r = await client.get(f"/api/auths/{ALIAS}/references", headers=own)
    assert r.status_code == 200, r.text
    body = r.json()
    # 别名绑定行
    assert body["alias_refs"] == [
        {"alias_name": "fin-service-uat", "base_service": "fin-service",
         "group_tag": "测试"}]
    visible = {v["scenario_id"]: v["kinds"] for v in body["scenario_refs"]["visible"]}
    # member:本人 3 + 他人 public 1 可见;他人 private → hidden
    assert visible == {
        "sc-own-tpl": ["template"],
        "sc-own-sch": ["scheme"],
        "sc-own-snap": ["snapshot"],
        "sc-other-pub": ["template"],
    }
    assert body["scenario_refs"]["hidden_count"] == 1
    # owner_id 透出(抽屉底部「删除会被拦截」预告的口径:本人 × 模板/方案)
    own_id = await _uid("own_user")
    by_sid = {v["scenario_id"]: v["owner_id"] for v in body["scenario_refs"]["visible"]}
    assert by_sid["sc-own-tpl"] == own_id
    assert by_sid["sc-other-pub"] != own_id

    # admin:全可见(私有也见名,can_read_scenario 口径)
    r = await client.get(f"/api/auths/{ALIAS}/references", headers=admin)
    vis = {v["scenario_id"] for v in r.json()["scenario_refs"]["visible"]}
    assert "sc-other-prv" in vis
    assert r.json()["scenario_refs"]["hidden_count"] == 0


async def test_list_carries_counts_snapshot_not_counted(client):
    own, _ = await _setup(client)
    # 凭证登记(owner 池)
    await client.post("/api/auths", headers=own, json={
        "alias": ALIAS, "url": "https://auth", "username": "u",
        "password": "p", "token_type": "Bearer"})
    r = await client.get("/api/auths", headers=own)
    row = next(a for a in r.json()["items"] if a["alias"] == ALIAS)
    # N 别名 = 1(service_aliases);N 场景 = 模板∪方案绑定去重
    # = sc-own-tpl + sc-own-sch + sc-other-pub + sc-other-prv = 4(快照不计)
    assert row["alias_ref_count"] == 1
    assert row["scenario_ref_count"] == 4


async def test_delete_blocked_only_by_own_template_or_scheme(client):
    own, _ = await _setup(client)
    r = await client.post("/api/auths", headers=own, json={
        "alias": ALIAS, "url": "https://auth", "username": "u",
        "password": "p", "token_type": "Bearer"})
    auth_id = r.json()["id"]

    # 本人模板 + 方案绑定引用 → 409 + 摘要(sc-other-* 不在阻断集)
    r = await client.delete(f"/api/auths/{auth_id}", headers=own)
    assert r.status_code == 409, r.text
    detail = r.json()["detail"]
    assert detail["ownScenarioIds"] == ["sc-own-sch", "sc-own-tpl"]

    # 清掉本人两类引用(场景删除)后 → 快照/他人引用不再阻断,可删
    async with db_module.SessionLocal() as s:
        await scenario_store.delete(s, "sc-own-tpl")
        await scenario_store.delete(s, "sc-own-sch")
        await s.commit()
    r = await client.delete(f"/api/auths/{auth_id}", headers=own)
    assert r.status_code == 204, r.text


async def test_delete_clean_credential_204(client):
    own, _ = await _setup(client)
    r = await client.post("/api/auths", headers=own, json={
        "alias": "lonely", "url": "https://auth", "username": "u",
        "password": "p", "token_type": "Bearer"})
    auth_id = r.json()["id"]
    r = await client.delete(f"/api/auths/{auth_id}", headers=own)
    assert r.status_code == 204, r.text
