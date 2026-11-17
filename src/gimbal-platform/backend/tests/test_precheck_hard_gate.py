"""M3 预检硬门(redesign §8.5,2026-11-17)—— 七码正例 + 三负例 + 三路径。

硬门语义:UI/JWT、access token(webhook 手动/定时同链)派发前统一 409,
错误码表 = env_unspecified | env_mixed | address_missing | login_missing |
identity_missing | account_missing | account_ambiguous;detail 必带
标签/服务/系统/身份上下文。**提示不拦截**:跨标签凭证(envWarnings)、
out_of_scope_targets 只记录、scope_missing 仍走 scheme_valid=False 软面
(真拒在 403 范围闸);suites validate 保持 warn 聚合(离线面恒 200)。

判定优先级钉死:env_mixed > identity_missing(悬空条目的根因不是
「标签不可解析」)> env_unspecified > account_missing > account_ambiguous
> login_missing > address_missing。
"""
from __future__ import annotations

import sqlalchemy as sa

from app.core import db as db_module
from app.core.security import fernet_encrypt
from app.models import (
    AuthAccount, Deployment, Environment, Execution, IntegrationTask,
    Service, ServiceIdentity, SystemEnvInstance,
)
from app.services import scheme_store
from tests.helpers import make_draft as _draft, register_and_login

from ._fanout_stub import _capture_fanout
from .test_run_m1_capabilities import _run_payload
from .test_scenario_composer_plate_integration import PlateMock, plate_mock  # noqa: F401


def _auth_step(alias: str) -> dict:
    return {"kind": "step",
            "call": {"service": alias, "method": "GET", "path": "/x",
                     "headers": {"Authorization": f"${{auth.{alias}.token}}"}},
            "request": {"kind": "request", "body": {}}, "strategy": []}


async def _seed_scenario(client, h, sid: str, aliases: list[str],
                         *, declared: dict | None = None) -> None:
    draft = _draft(sid, steps=[_auth_step(a) for a in aliases])
    if declared is not None:
        draft["definition"]["config"] = {"services": declared}
    r = await client.post("/api/scenarios", headers=h, json=draft)
    assert r.status_code in (200, 201), r.text


async def _env_id(name: str, *, is_default: bool = False) -> int:
    async with db_module.SessionLocal() as s:
        env = Environment(name=name, is_default=is_default)
        s.add(env)
        await s.commit()
        await s.refresh(env)
        return env.id


async def _uid(username: str) -> int:
    async with db_module.SessionLocal() as s:
        return (await s.execute(sa.text(
            "SELECT id FROM users WHERE username = :u"),
            {"u": username})).scalar()


async def _seed_identity(alias: str, env_id: "int | None", *,
                         service: str = "svc") -> None:
    async with db_module.SessionLocal() as s:
        if (await s.execute(sa.select(Service.id).where(
                Service.name == service))).scalar_one_or_none() is None:
            s.add(Service(name=service, system=service, kind="plate"))
        s.add(ServiceIdentity(alias_name=alias, base_service=service,
                              env_id=env_id, ref_mode="default"))
        await s.commit()


async def _seed_account(uid: int, env_id: int, *, system: str = "svc",
                        username: str = "u", is_default: bool = True) -> None:
    async with db_module.SessionLocal() as s:
        s.add(AuthAccount(owner_id=uid, system=system, env_id=env_id,
                          username=username,
                          password_enc=fernet_encrypt("p"),
                          is_default=is_default))
        await s.commit()


async def _seed_instance(system: str, env_id: int, *,
                         login_url: str = "http://login") -> None:
    async with db_module.SessionLocal() as s:
        s.add(SystemEnvInstance(system=system, env_id=env_id,
                                login_url=login_url))
        await s.commit()


async def _seed_deploy(service: str, env_id: int, *,
                       url: str = "http://dep") -> None:
    async with db_module.SessionLocal() as s:
        s.add(Deployment(base_service=service, env_id=env_id,
                         base_url=url))
        await s.commit()


async def _dispatch_409(client, h, sid: str) -> dict:
    r = await client.post("/api/runs", headers=h, json=_run_payload(
        scenarioId=sid, dataSetIds=[]))
    assert r.status_code == 409, r.text
    return r.json()["detail"]


async def _mk_scheme(sid: str, name: str = "方案H") -> str:
    async with db_module.SessionLocal() as s:
        sch = await scheme_store.create_scheme(s, sid, name=name, payload={})
        return sch["schemeId"]


# ── 七码正例(JWT 派发,同步 409)─────────────────────────────────


async def test_gate_env_mixed(client, plate_mock: PlateMock):
    """混拼:两有效身份标签不一致 → 409 env_mixed,detail.identities
    带条目→标签映射;不建执行行。"""
    h = await register_and_login(client, "hg_mix", "pw123456")
    e1, e2 = await _env_id("hg-a"), await _env_id("hg-b")
    await _seed_identity("a-dev", e1)
    await _seed_identity("a-sit", e2)
    await _seed_scenario(client, h, "sc-hg-mix", ["a-dev", "a-sit"])
    det = await _dispatch_409(client, h, "sc-hg-mix")
    assert det["code"] == "env_mixed"
    assert det["identities"] == {"a-dev": e1, "a-sit": e2}
    async with db_module.SessionLocal() as s:
        assert (await s.execute(sa.select(Execution.id))).first() is None


async def test_gate_identity_missing(client, plate_mock: PlateMock):
    """悬空条目 → 409 identity_missing(不是 env_unspecified —— 根因
    是「未登记」,错误码不给表象)。"""
    h = await register_and_login(client, "hg_idm", "pw123456")
    await _seed_scenario(client, h, "sc-hg-idm", ["ghost"])
    det = await _dispatch_409(client, h, "sc-hg-idm")
    assert det["code"] == "identity_missing"
    assert det["aliases"] == ["ghost"]


async def test_gate_env_unspecified(client, plate_mock: PlateMock):
    """env_unspecified 的可达性注记:``service_identities.env_id`` 为
    NOT NULL + FK(条目必有标签),悬空名走 identity_missing —— 该码
    在门内是防御位(标签链空的兜底根因,如未来放开 env 可空)。这里
    钉住现行为:悬空条目报 identity_missing 而非 env_unspecified。"""
    h = await register_and_login(client, "hg_env", "pw123456")
    await _seed_scenario(client, h, "sc-hg-env", ["no-tag"])
    det = await _dispatch_409(client, h, "sc-hg-env")
    assert det["code"] == "identity_missing"


async def test_gate_account_missing(client, plate_mock: PlateMock):
    """条目在、执行人池无账户 → 409 account_missing(personal 池文案)。"""
    h = await register_and_login(client, "hg_acc", "pw123456")
    env = await _env_id("hg-acc")
    await _seed_identity("qa1", env)
    await _seed_scenario(client, h, "sc-hg-acc", ["qa1"])
    det = await _dispatch_409(client, h, "sc-hg-acc")
    assert det["code"] == "account_missing"
    assert det["credentialSource"] == "personal"
    assert "qa1" in det["message"]


async def test_gate_account_ambiguous(client, plate_mock: PlateMock):
    """ref=username 跨标签多候选且无同标签唯一命中 → 409
    account_ambiguous(§8.3)。"""
    h = await register_and_login(client, "hg_amb", "pw123456")
    uid = await _uid("hg_amb")
    e1, e2, e3 = (await _env_id("hg-am-1"), await _env_id("hg-am-2"),
                  await _env_id("hg-am-3"))
    async with db_module.SessionLocal() as s:
        if (await s.execute(sa.select(Service.id).where(
                Service.name == "svc"))).scalar_one_or_none() is None:
            s.add(Service(name="svc", system="svc", kind="plate"))
        # 条目钉 e1;账户只有 e2/e3 两行(无同标签)→ 歧义
        s.add(ServiceIdentity(alias_name="qa1", base_service="svc",
                              env_id=e1, ref_mode="username",
                              ref_username="u"))
        await s.commit()
    await _seed_account(uid, e2, is_default=False)
    await _seed_account(uid, e3, is_default=False)
    await _seed_scenario(client, h, "sc-hg-amb", ["qa1"])
    det = await _dispatch_409(client, h, "sc-hg-amb")
    assert det["code"] == "account_ambiguous"
    assert det["aliases"] == ["qa1"]


async def test_gate_login_missing(client, plate_mock: PlateMock):
    """账户可解但 (system, 账户标签) 实例登录口缺 → 409 login_missing
    (§4.3 口径:缺席明确报;引擎 PreToken 兜底不作为放行理由)。"""
    h = await register_and_login(client, "hg_log", "pw123456")
    uid = await _uid("hg_log")
    env = await _env_id("hg-log")
    await _seed_identity("qa1", env)
    await _seed_account(uid, env)
    await _seed_deploy("svc", env)            # 地址有、登录口无
    await _seed_scenario(client, h, "sc-hg-log", ["qa1"])
    det = await _dispatch_409(client, h, "sc-hg-log")
    assert det["code"] == "login_missing"
    assert det["logins"] == [{"alias": "qa1", "system": "svc",
                              "envId": env}]


async def test_gate_address_missing(client, plate_mock: PlateMock):
    """服务地址 ②③ 双缺 → 409 address_missing(错误时机从引擎步骤级
    前移;detail 带标签坐标)。"""
    h = await register_and_login(client, "hg_addr", "pw123456")
    uid = await _uid("hg_addr")
    env = await _env_id("hg-addr")
    await _seed_identity("qa1", env)
    await _seed_account(uid, env)
    await _seed_instance("svc", env)          # 登录口有、部署行无
    await _seed_scenario(client, h, "sc-hg-addr", ["qa1"])
    det = await _dispatch_409(client, h, "sc-hg-addr")
    assert det["code"] == "address_missing"
    assert det["services"] == ["qa1"]
    assert det["environmentId"] == env


# ── 三负例(提示不拦截)────────────────────────────────────────


async def test_gate_cross_tag_account_not_blocked(
        client, plate_mock: PlateMock, monkeypatch):
    """跨标签凭证:条目标签 e1、唯一账户在 e2 → system 唯一命中放行
    (凭证解耦);预检 envWarnings 如实提示(执行期 401 自然暴露)。"""
    h = await register_and_login(client, "hg_cross", "pw123456")
    uid = await _uid("hg_cross")
    e1, e2 = await _env_id("hg-x-1"), await _env_id("hg-x-2")
    await _seed_identity("qa1", e1)
    await _seed_account(uid, e2)              # 账户在另一标签
    await _seed_instance("svc", e2)           # 登录口随账户标签(§8.3)
    await _seed_deploy("svc", e1)             # 地址随执行标签
    await _seed_scenario(client, h, "sc-hg-cross", ["qa1"])
    cap = await _capture_fanout(monkeypatch)
    r = await client.post("/api/runs", headers=h, json=_run_payload(
        scenarioId="sc-hg-cross", dataSetIds=[]))
    assert r.status_code == 201, r.text

    sid = await _mk_scheme("sc-hg-cross")
    r = await client.post("/api/run/precheck", headers=h, json=[
        {"scenarioId": "sc-hg-cross", "schemeId": sid}])
    assert r.status_code == 200, r.text
    out = r.json()[0]
    assert out["envContext"] == {"environmentId": e1,
                                 "environmentSource": "identity"}
    assert out["envWarnings"], "跨标签提示应在场"
    assert any(f"#{e2}" in w for w in out["envWarnings"])


async def test_gate_precheck_soft_signals_stay_soft(client, plate_mock: PlateMock):
    """scope_missing 仍软(200 + scheme_valid=False,真拒在 403 范围闸);
    out_of_scope_targets 只记录不拦截(直连地址属范围外目标)。"""
    from .inbound_fixtures import mk_token
    h = await register_and_login(client, "hg_soft", "pw123456")
    uid = await _uid("hg_soft")
    tok_id, _plain = await mk_token(user_id=uid, scope_aliases=(),
                                    scope_auths=[])
    # 条目 + 属主池账户(凭证范围目标;token 无范围 → 缺项)—— 软面
    # 预检不连坐,只报 scopeMissing
    _env = await _env_id("hg-soft")
    await _seed_identity("qa1", _env)
    await _seed_account(uid, _env)
    await _seed_scenario(client, h, "sc-hg-soft", ["qa1"],
                         declared={"qa1": "http://direct"})  # 范围外直连
    sid = await _mk_scheme("sc-hg-soft")
    r = await client.post(f"/api/run/precheck?tokenId={tok_id}",
                          headers=h, json=[
        {"scenarioId": "sc-hg-soft", "schemeId": sid}])
    assert r.status_code == 200, r.text          # 软面:恒 200
    out = r.json()[0]
    assert out["scopeMissing"] and out["schemeValid"] is False
    assert out["outOfScopeTargets"]              # 只记录


async def test_gate_suites_validate_stays_warn(client, plate_mock: PlateMock):
    """suites validate 保持 warn 聚合(离线校验面,HTTP 恒 200;缺件进
    预检条目 unbound_services,不 409)。"""
    h = await register_and_login(client, "hg_sv", "pw123456")
    await _seed_scenario(client, h, "sc-hg-sv", ["ghost"])
    r = await client.post("/api/suites", headers=h,
                          json={"name": "hg-suite", "description": ""})
    assert r.status_code in (200, 201), r.text
    sid = r.json()["suiteId"]
    await client.post(f"/api/suites/{sid}/members", headers=h,
                      json={"scenarioIds": ["sc-hg-sv"]})
    r = await client.post(f"/api/suites/{sid}/validate", headers=h)
    assert r.status_code == 200, r.text          # 恒 200
    out = r.json()
    items = [i for i in out["items"]
             if i.get("code") == "unbound_services"]
    assert items and "ghost" in str(items[0])
    assert items[0]["level"] == "warn"


# ── 三路径各一例 ──────────────────────────────────────────────


async def test_path_sync_jwt_token_same_gate(client, plate_mock: PlateMock):
    """路径①:JWT 派发漏斗同步 409(account_missing 代表码)—— UI/JWT
    与 access token 同经 dispatch_target 的门(令牌路径的范围闸在路由
    入口,过闸后同一份判定)。"""
    h = await register_and_login(client, "hg_jwt", "pw123456")
    env = await _env_id("hg-pt")
    await _seed_identity("qa1", env)
    await _seed_instance("svc", env)
    await _seed_deploy("svc", env)
    await _seed_scenario(client, h, "sc-hg-pt", ["qa1"])   # 唯缺账户
    det = await _dispatch_409(client, h, "sc-hg-pt")
    assert det["code"] == "account_missing"
    assert det["credentialSource"] == "personal"


async def test_path_webhook_scheduled_pauses(client, plate_mock: PlateMock):
    """路径②:webhook 定时路径(integration_runner 装载前)命中门 →
    实例暂停;标签/地址域码 → precheck_config(修好配置后人工 resume,
    _RESUMABLE 已放行)。"""
    h = await register_and_login(client, "hg_sch", "pw123456")
    uid = await _uid("hg_sch")
    env = await _env_id("hg-sch")
    await _seed_identity("qa1", env)
    await _seed_account(uid, env)
    await _seed_instance("svc", env)            # 登录口有、部署无 → address
    await _seed_scenario(client, h, "sc-hg-sch", ["qa1"])
    r = await client.post("/api/integration/tasks", headers=h, json={
        "name": "HG", "scenarioId": "sc-hg-sch", "identityMode": "personal",
        "triggerCron": "*/5 * * * *", "resultPolicy": "latest",
        "visibility": "private"})
    assert r.status_code == 201, r.text
    tid = r.json()["id"]
    r = await client.post(f"/api/integration/tasks/{tid}/run", headers=h)
    assert r.status_code == 200, r.text
    async with db_module.SessionLocal() as s:
        inst = (await s.execute(sa.select(IntegrationTask).where(
            IntegrationTask.template_id == tid))).scalars().one()
        assert inst.state == "paused"
        assert inst.paused_reason == "precheck_config"
        assert "address_missing" in (inst.last_error or "")


async def test_path_precheck_contract_fields(client, plate_mock: PlateMock):
    """路径③:预检端点新契约 —— 混拼 envMixed=true + envContext=None +
    envUnspecified=False(根因不连坐);健康面 envContext 钉 identity。"""
    h = await register_and_login(client, "hg_pc", "pw123456")
    e1, e2 = await _env_id("hg-pc-1"), await _env_id("hg-pc-2")
    await _seed_identity("a-dev", e1)
    await _seed_identity("a-sit", e2)
    await _seed_scenario(client, h, "sc-hg-pcm", ["a-dev", "a-sit"])
    sid_m = await _mk_scheme("sc-hg-pcm")
    r = await client.post("/api/run/precheck", headers=h, json=[
        {"scenarioId": "sc-hg-pcm", "schemeId": sid_m}])
    assert r.status_code == 200, r.text
    out = r.json()[0]
    assert out["envMixed"] is True
    assert out["envContext"] is None
    assert out["envUnspecified"] is False       # 混拼不误报「标签不可解析」
    assert out["missingAuths"] == ["a-dev", "a-sit"]


# ── adhoc:EnvMixed 映射 409 ───────────────────────────────────


async def test_adhoc_env_mixed_maps_409(client, plate_mock: PlateMock):
    """adhoc 两条目异标签 → check_addresses 的 EnvMixed 映射 409
    env_mixed(此前裸冒 500,路由 except 清单不含)。"""
    from . import test_adhoc_run as _ad
    from .inbound_fixtures import mk_user
    e1, e2 = await _env_id("hg-ad-1"), await _env_id("hg-ad-2")
    ep1, ep2 = "settle.order.query", "settle.refund.query"
    async with db_module.SessionLocal() as s:
        s.add(Service(name="settle-service", system="settle", kind="plate"))
        s.add(ServiceIdentity(alias_name="settle-a", base_service="settle-service",
                              env_id=e1, ref_mode="default"))
        s.add(ServiceIdentity(alias_name="settle-b", base_service="settle-service",
                              env_id=e2, ref_mode="default"))
        await s.commit()
    for ep in (ep1, ep2):
        plate_mock.fulls[ep] = {**_ad.PLATE_FULL, "id": ep}
    plate_mock.behaviour = "echo"
    await mk_user("hg_adhoc")
    h = await _ad._personal(client, "hg_adhoc",
                            scope_aliases=("settle-a", "settle-b"))
    r = await _ad._post(client, h, _ad._body(steps=[
        {"endpoint": ep1, "service": "settle-a",
         "body": {"orderNo": "PO1"}, "strategy": []},
        {"endpoint": ep2, "service": "settle-b",
         "body": {"orderNo": "PO2"}, "strategy": []},
    ]))
    assert r.status_code == 409, r.text
    det = r.json()["detail"]
    assert det["code"] == "env_mixed"
    assert set(det["identities"]) == {"settle-a", "settle-b"}
