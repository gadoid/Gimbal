"""auth_references 账户引用反查(registry rework §1.4;P1-7 续期)。

两层聚合(账户 → ref 条目 → 场景)+ 可见性 + 删除拦截窄口径:
* template(steps ${auth.<条目名>.*})= 真依赖,计数与 409;
  setup/teardown 节点同源扫描(webhook v4 §3.2);
* snapshot(config.users 同名键)= 卫生信号,面板展示不计数不阻断;
* identity_refs = ref 指向该账户的身份条目(条目不分池,匹配看
  system/env/ref 三元,与 run_prepare._resolve_identities 同构);
* 场景名按 can_read_scenario 过滤(public / owner;账户行主镜头),
  剩余 = hidden_count(只给数不泄露标题);
* DELETE 409 仅本人场景的 template;他人场景(即使 public
  我能跑)与快照不阻断 — 名字引用按执行者池解析;
* 存量方案 serviceBindings.authAlias 不在扫描面(S6 沿革)。
"""
from __future__ import annotations

import sqlalchemy as sa

from app.core import db as db_module
from app.models.composer_run_scheme import ComposerRunScheme
from app.models.composer_scenario import ComposerScenario
from app.models.user import User
from app.schemas.scenario_composer import ScenarioDraft
from app.services import scenario_store

from .conftest import seed_identity_fixture
from .helpers import make_draft, register_and_login

ALIAS = "qa1"  # 身份条目名(场景引用键)
ACCOUNT_USER = "qa1-user"


async def _uid(username: str) -> int:
    async with db_module.SessionLocal() as s:
        return (await s.execute(
            sa.select(User).where(User.username == username))).scalar_one().id


def _tpl_step(endpoint: str, header_value: str) -> dict:
    return {"call": {"view_hints": {"endpoint_id": endpoint},
                    "headers": {"Authorization": header_value}},
            "request": {"body": {}}}


async def _seed(owner_ids: dict[str, int]) -> None:
    """六场景 × 引用形状:
    sc-own-tpl   本人私有,模板引用 → 阻断 + member 可见
    sc-own-sch   本人私有,存量方案带 authAlias(无模板)→ 不算引用
    sc-own-snap  本人私有,仅 config.users 快照 → 不阻断,kind=snapshot
    sc-other-pub 他人 public,模板 → member 可见,不阻断(能跑但名字引用)
    sc-other-prv 他人 private,模板 → 行主不可见(hidden_count)
    sc-clean     本人私有,零引用 → 计数 0
    """
    async with db_module.SessionLocal() as s:
        async def _create(sid: str, owner: str, visibility: str, steps) -> None:
            await scenario_store.create(
                s, ScenarioDraft.model_validate(make_draft(
                    sid, steps=steps, **{"name": sid})),
                owner=owner, owner_id=owner_ids[owner])
            if visibility != "private":
                # S1.3 起 set_visibility 退役:公共行(迁移形态)直改。
                # §20.2 复合 FK:方案行随场景同迁(挂起约束 + 同步携带)
                from sqlalchemy import text as _txt, update as _upd

                from app.models.composer_run_scheme import ComposerRunScheme
                from app.services.zone import public_project_id
                pub = await public_project_id(s)
                await s.execute(_txt(
                    "SET CONSTRAINTS fk_scheme_scenario_zone DEFERRED"))
                await s.execute(_upd(ComposerScenario).where(
                    ComposerScenario.scenario_id == sid).values(
                    project_id=pub))
                await s.execute(_upd(ComposerRunScheme).where(
                    ComposerRunScheme.scenario_id == sid).values(
                    project_id=pub))

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

        # sc-own-snap 的 config.users 快照(键 = 身份条目名)
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

        # sc-own-sch 的存量方案绑定(authAlias,无模板;扫描面不读方案)
        # is_default=False:create 已自动建默认方案(partial unique
        # 每场景一个 default)— 扫描面读全部方案的绑定,与 default 无关
        from tests.helpers import scenario_project_id

        s.add(ComposerRunScheme(
            scheme_id="rs-own-1", scenario_id="sc-own-sch", name="方案二",
            project_id=await scenario_project_id(s, "sc-own-sch"),
            is_default=False, payload={"serviceBindings": {
                "fin-service": {"authAlias": ALIAS}}},
        ))
        await s.commit()


async def _setup(client):
    # ref_admin 注册在先:首个用户自动 admin(auth.py:72),
    # 后续 own_user/other_user 恰为普通用户
    admin = await register_and_login(client, "ref_admin", "pw123456")
    own = await register_and_login(client, "own_user", "pw123456")
    await register_and_login(client, "other_user", "pw123456")
    # own_user 的账户 + 引用它的身份条目 qa1(四件套一次布景)
    async with db_module.SessionLocal() as db:
        await seed_identity_fixture(
            db, alias=ALIAS, username=ACCOUNT_USER, password="p",
            service="fin-service", owner_id=await _uid("own_user"))
    owner_ids = {u: await _uid(u) for u in ("own_user", "other_user")}
    await _seed(owner_ids)
    return own, admin


async def _own_account_id(client, headers) -> int:
    items = (await client.get("/api/auths", headers=headers)).json()["items"]
    return next(a["id"] for a in items if a["username"] == ACCOUNT_USER)


async def test_references_kinds_and_visibility(client):
    own, admin = await _setup(client)
    aid = await _own_account_id(client, own)

    r = await client.get(f"/api/auths/{aid}/references", headers=own)
    assert r.status_code == 200, r.text
    body = r.json()
    # identity_refs:ref 该账户的身份条目(ref=username 精确命中)
    assert body["identityRefs"] == [
        {"aliasName": ALIAS, "baseService": "fin-service",
         "envId": body["identityRefs"][0]["envId"],
         "refMode": "username", "refUsername": ACCOUNT_USER}]
    visible = {v["scenarioId"]: v["kinds"]
               for v in body["scenarioRefs"]["visible"]}
    # member:本人 2 + 他人 public 1 可见;他人 private → hidden;
    # sc-own-sch 的方案 authAlias 不算引用(扫描面不读方案)
    assert visible == {
        "sc-own-tpl": ["template"],
        "sc-own-snap": ["snapshot"],
        "sc-other-pub": ["template"],
    }
    assert body["scenarioRefs"]["hidden_count"] == 1
    # ownerId 透出(抽屉底部「删除会被拦截」预告的口径:本人 × 模板)
    own_id = await _uid("own_user")
    by_sid = {v["scenarioId"]: v["ownerId"]
              for v in body["scenarioRefs"]["visible"]}
    assert by_sid["sc-own-tpl"] == own_id
    assert by_sid["sc-other-pub"] != own_id

    # 账户化后反查端点 owner-scoped:admin 摸他人账户行同样 404
    # (旧「别名键全员可查」口径随账户实体化退役;场景可见性过滤
    # 发生在行主面板里 —— 上方 hidden_count==1 已覆盖 member 镜头)
    r = await client.get(f"/api/auths/{aid}/references", headers=admin)
    assert r.status_code == 404


async def test_list_carries_counts_snapshot_not_counted(client):
    own, _ = await _setup(client)
    r = await client.get("/api/auths", headers=own)
    row = next(a for a in r.json()["items"]
               if a["username"] == ACCOUNT_USER)
    # N 条目 = 1(qa1);N 场景 = 条目名模板引用去重
    # = sc-own-tpl + sc-other-pub + sc-other-prv = 3(快照/方案不计)
    assert row["identityRefCount"] == 1
    assert row["scenarioRefCount"] == 3


async def test_delete_blocked_only_by_own_template(client):
    own, _ = await _setup(client)
    aid = await _own_account_id(client, own)

    # 本人模板引用 → 409 + 摘要(sc-other-* 与快照不在阻断集)
    r = await client.delete(f"/api/auths/{aid}", headers=own)
    assert r.status_code == 409, r.text
    detail = r.json()["detail"]
    assert detail["ownScenarioIds"] == ["sc-own-tpl"]

    # 清掉本人模板引用(场景删除)后 → 快照/他人引用不再阻断,可删
    async with db_module.SessionLocal() as s:
        await scenario_store.delete(s, "sc-own-tpl")
        await s.commit()
    r = await client.delete(f"/api/auths/{aid}", headers=own)
    assert r.status_code == 204, r.text


async def test_delete_clean_account_204(client):
    own, _ = await _setup(client)
    # 同 (system,env) 第二个账户:无条目引用、无场景引用 → 直接可删
    from app.core.security import fernet_encrypt
    from app.models import AuthAccount
    async with db_module.SessionLocal() as s:
        env_id = (await s.execute(sa.select(
            AuthAccount.env_id).limit(1))).scalar()
        acc = AuthAccount(
            owner_id=await _uid("own_user"), system="fin-service",
            env_id=env_id, username="lonely",
            password_enc=fernet_encrypt("p"), is_default=False)
        s.add(acc)
        await s.commit()
        aid = acc.id

    r = await client.delete(f"/api/auths/{aid}", headers=own)
    assert r.status_code == 204, r.text
