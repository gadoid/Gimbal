"""执行配置分层②:三链插位(环境链②/④ + 槽位取用覆盖 + carry 覆盖层)
+ 入口排除守则。

设计方案 §5:环境 = 本次 > [选定配置 │ 方案] > 项目默认 > [默认配置 │
偏好] > 平台默认;绑定 = 仅显式选定配置换池取用(注入标签不变);
carry = 场景显式 > 配置覆盖(项目区仅显式,决策 9)> 层序。守则:
令牌/编排/临时调用不吃执行配置;跨人配置 404。
"""
from __future__ import annotations

import sqlalchemy as sa

from app.core import db as db_module
from app.core.security import fernet_encrypt
from app.models import Deployment, Environment, ExecConfig
from app.models.auth_session import AuthSession
from app.models.service_alias import ServiceAlias
from app.services import carry_store, env_chain
from app.services.carry_injection import build_carry_context
from app.services.env_chain import EnvChoice, resolve_environment
from app.services.exec_config import (
    ExecConfigNotFound, carry_overrides_for, load_choice,
)
from app.services.run_prepare import resolve_exec_auths

from .helpers import make_draft as _draft, register_and_login, wait_until as _wait
from .test_run_m1_capabilities import _patch_launch_capture, _run_payload
from .test_scenario_composer_plate_integration import (  # noqa: F401
    PlateMock, plate_mock,
)

_BASE = "fin-service"
_ALIAS = "fin-dev"          # 引用基础服务的别名(声明槽位 qa1)
_STEP = {"kind": "step",
         "call": {"service": _ALIAS, "method": "GET", "path": "/x"},
         "request": {"kind": "request", "body": {}}, "strategy": []}


async def _uid(username: str) -> int:
    async with db_module.SessionLocal() as s:
        return (await s.execute(sa.text(
            "SELECT id FROM users WHERE username = :u"),
            {"u": username})).scalar()


async def _env(s, name: str, *, is_default: bool = False) -> int:
    env = Environment(name=name, description="", lines={},
                      is_default=is_default)
    s.add(env)
    await s.flush()
    return env.id


async def _seed_scene(client, h, sid: str, *, slot: str = "qa1") -> None:
    """别名(声明槽位)+ 场景(步骤引用别名)+ 默认平台环境。"""
    async with db_module.SessionLocal() as s:
        await _env(s, "ec-plain", is_default=True)
        s.add(ServiceAlias(alias_name=_ALIAS, base_service=_BASE, slot=slot))
        await s.commit()
    r = await client.post("/api/scenarios", headers=h,
                          json=_draft(sid, steps=[_STEP]))
    assert r.status_code in (200, 201), r.text


async def _mk_config(
    uid: int, name: str, *, is_default: bool = False, env_id=None,
    bindings: dict | None = None, carry: dict | None = None,
) -> int:
    systems = ([{"service": _BASE, "bindings": bindings or {},
                 "carryOverrides": carry or {}}]
               if (bindings or carry) else [])
    async with db_module.SessionLocal() as s:
        row = ExecConfig(
            scope="user", scope_id=uid, name=name, is_default=is_default,
            environment_id=env_id,
            payload={"systems": systems})
        s.add(row)
        await s.commit()
        return row.id


async def _seed_auth(uid: int, slot: str, username: str) -> int:
    async with db_module.SessionLocal() as s:
        a = AuthSession(
            owner_id=uid, alias=f"b-{slot}", slot=slot, system=_BASE,
            url=f"http://{slot}-auth",
            username_enc=fernet_encrypt(username),
            password_enc=fernet_encrypt(f"pw-{slot}"),
            is_default=True)
        s.add(a)
        await s.commit()
        return a.id


async def _last_cfg() -> dict:
    from app.models import Execution
    async with db_module.SessionLocal() as s:
        ex = (await s.execute(sa.select(Execution).order_by(
            Execution.id.desc()))).scalars().first()
        return ex.config_json


# ── ① 环境链插位(resolve_environment 单元)─────────────────────────

async def test_env_chain_exec_positions(client, fresh_db):
    await register_and_login(client, "ec_chain", "pw123456")
    uid = await _uid("ec_chain")
    async with db_module.SessionLocal() as s:
        dflt = await _env(s, "ec-dflt", is_default=True)
        sit = await _env(s, "ec-sit")
        uat = await _env(s, "ec-uat")
        # 选定配置遮蔽方案(位②,左优先)
        assert await resolve_environment(
            s, exec_env=uat, scheme_env=sit) == EnvChoice(uat, "exec_config")
        # 配置没设 env(位②空)→ 方案生效
        assert await resolve_environment(
            s, scheme_env=sit) == EnvChoice(sit, "scheme")
        # 默认配置遮蔽个人偏好(位④);没传(无默认配置)→ 偏好回落
        assert await resolve_environment(
            s, default_exec_env=uat, user_id=uid) == \
            EnvChoice(uat, "exec_config_default")
        from app.models.permission import UserPref
        s.add(UserPref(user_id=uid, key=env_chain.PREF_KEY, value=sit))
        await s.flush()
        assert await resolve_environment(s, user_id=uid) == \
            EnvChoice(sit, "preference")
        assert await resolve_environment(
            s, default_exec_env=uat, user_id=uid) == \
            EnvChoice(uat, "exec_config_default")
        # 悬空的配置环境视同未设置,落到下一位
        assert await resolve_environment(
            s, exec_env=99999, scheme_env=sit) == EnvChoice(sit, "scheme")
        assert await resolve_environment(
            s, default_exec_env=99999, user_id=uid) == \
            EnvChoice(sit, "preference")
        assert await resolve_environment(
            s, default_exec_env=dflt) == EnvChoice(dflt, "exec_config_default")


# ── ② load_choice 摊平 + 越权 ──────────────────────────────────────

async def test_load_choice_flatten_and_isolation(client, fresh_db):
    await register_and_login(client, "ec_a", "pw123456")
    await register_and_login(client, "ec_b", "pw123456")
    a, b = await _uid("ec_a"), await _uid("ec_b")
    cid = await _mk_config(
        a, "商户B", bindings={_ALIAS: "merchant-b"},
        carry={"grade": "B", "nil": None})

    async with db_module.SessionLocal() as s:
        ch = await load_choice(s, a, cid)
        assert ch is not None and ch.explicit
        assert ch.bindings == {_ALIAS: "merchant-b"}
        assert ch.carry_overrides == {_BASE: {"grade": "B", "nil": None}}
        # 跨人显式选定 → NotFound(个人数据不泄露存在性)
        try:
            await load_choice(s, b, cid)
            raise AssertionError("expected ExecConfigNotFound")
        except ExecConfigNotFound:
            pass
        # None → 默认行;无默认行 → None
        assert await load_choice(s, a, None) is None
    async with db_module.SessionLocal() as s:
        real_env = await _env(s, "ec-lc")
        await s.commit()
    await _mk_config(a, "默认", is_default=True, env_id=real_env)
    async with db_module.SessionLocal() as s:
        ch = await load_choice(s, a, None)
        assert ch is not None and not ch.explicit and ch.env_id == real_env
        assert await load_choice(s, b, None) is None


# ── ③ 决策 9:carry 覆盖的区规则 ───────────────────────────────────

async def test_carry_overrides_zone_rule(client, fresh_db):
    await register_and_login(client, "ec_z", "pw123456")
    uid = await _uid("ec_z")
    explicit = await _mk_config(uid, "显式", carry={"k": "v"})
    await _mk_config(uid, "默认", is_default=True, carry={"k": "v"})
    async with db_module.SessionLocal() as s:
        ch_e = await load_choice(s, uid, explicit)
        ch_d = await load_choice(s, uid, None)   # 默认链 = 默认行(explicit=False)
    assert carry_overrides_for(ch_e, None) == {_BASE: {"k": "v"}}
    assert carry_overrides_for(ch_d, None) == {_BASE: {"k": "v"}}   # 私有区:默认也吃
    assert carry_overrides_for(ch_e, 42) == {_BASE: {"k": "v"}}     # 项目区:显式吃
    assert carry_overrides_for(ch_d, 42) is None                    # 项目区:默认不吃
    assert carry_overrides_for(None, None) is None


async def test_carry_override_layer_beats_tiers(client, fresh_db):
    """配置覆盖层:压层序之上(公共层/个人层),null = 显式注入 null。"""
    await register_and_login(client, "ec_c", "pw123456")
    uid = await _uid("ec_c")
    async with db_module.SessionLocal() as s:
        s.add(ServiceAlias(alias_name=_ALIAS, base_service=_BASE,
                           kind="external"))
        await s.flush()
        pub = await carry_store.public_scope(s)
        await carry_store.put_bindings(
            s, _BASE, {"$.a": "pub", "$.keep": "pub"},
            updated_by_id=None, updated_by_name="t", scope=pub)
        await s.commit()

    definition = {"steps": [_STEP]}
    async with db_module.SessionLocal() as s:
        ctx = await build_carry_context(
            s, definition, user_id=uid,
            exec_overrides={_BASE: {"$.a": "cfg", "$.null": None}})
    rows = ctx.service_bindings[_ALIAS]
    assert rows == {"$.a": "cfg", "$.keep": "pub", "$.null": None}


# ── ④ 槽位取用覆盖:标签不变、池内换行 ────────────────────────────

async def test_slot_lookup_overrides_and_resolve(client, fresh_db):
    await register_and_login(client, "ec_s", "pw123456")
    uid = await _uid("ec_s")
    async with db_module.SessionLocal() as s:
        s.add(ServiceAlias(alias_name=_ALIAS, base_service=_BASE, slot="qa1"))
        await s.commit()
    await _seed_auth(uid, "qa1", "default-u")
    merchant_id = await _seed_auth(uid, "merchant-b", "merchant-u")

    from app.services.service_aliases import slot_lookup_overrides
    async with db_module.SessionLocal() as s:
        m = await slot_lookup_overrides(
            s, [_STEP], None, {_ALIAS: "merchant-b"})
    assert m == {"qa1": "merchant-b"}   # 标签(声明槽)→ 取用槽

    resolved = await resolve_exec_auths(
        db_module.SessionLocal, uid, ["qa1"], slot_map=m)
    assert len(resolved) == 1
    assert resolved[0].alias == "qa1"            # 注入标签不变(场景引用)
    assert resolved[0].username == "merchant-u"  # 池内取用换行
    assert resolved[0].binding_id == merchant_id


# ── ⑤ 派发端到端:env 快照 + users 注入 + 越权 404 ─────────────────

async def test_dispatch_env_from_selected_config(
        client, plate_mock: PlateMock, monkeypatch):
    plate_mock.behaviour = "echo"
    await register_and_login(client, "ec_r1", "pw123456")
    h = await register_and_login(client, "ec_r1", "pw123456")
    await _seed_scene(client, h, "sc-ec-r1")
    uid = await _uid("ec_r1")
    async with db_module.SessionLocal() as s:
        uat = await _env(s, "ec-uat")
        s.add(Deployment(base_service=_BASE, env_id=uat,
                         base_url="http://uat-fin"))
        await s.commit()
    await _seed_auth(uid, "qa1", "default-u")
    cid = await _mk_config(uid, "UAT套", env_id=uat)
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)

    r = await client.post("/api/runs", headers=h, json=_run_payload(
        scenarioId="sc-ec-r1", dataSetIds=[], execConfigId=cid))
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 1)
    cfg = await _last_cfg()
    assert cfg["environmentId"] == uat
    assert cfg["environmentSource"] == "exec_config"
    assert cfg["execConfigId"] == cid
    assert cases[0]["config"]["services"][_ALIAS] == "http://uat-fin"


async def test_dispatch_default_config_env_and_binding_injection(
        client, plate_mock: PlateMock, monkeypatch):
    """默认链:默认配置只占 env 位④(不吃绑定);显式选定时绑定换池行。"""
    plate_mock.behaviour = "echo"
    await register_and_login(client, "ec_r2", "pw123456")
    h = await register_and_login(client, "ec_r2", "pw123456")
    await _seed_scene(client, h, "sc-ec-r2")
    uid = await _uid("ec_r2")
    async with db_module.SessionLocal() as s:
        sit = await _env(s, "ec-sit")
        s.add(Deployment(base_service=_BASE, env_id=sit,
                         base_url="http://sit-fin"))
        await s.commit()
    default_id = await _mk_config(
        uid, "默认", is_default=True, env_id=sit, bindings={_ALIAS: "merchant-b"})
    await _seed_auth(uid, "qa1", "default-u")
    await _seed_auth(uid, "merchant-b", "merchant-u")
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)

    # 默认链:env 走默认配置(位④);绑定不吃(仍注入 qa1 的默认行)
    r = await client.post("/api/runs", headers=h, json=_run_payload(
        scenarioId="sc-ec-r2", dataSetIds=[]))
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 1)
    cfg = await _last_cfg()
    assert (cfg["environmentId"], cfg["environmentSource"]) == \
        (sit, "exec_config_default")
    assert "execConfigId" not in cfg
    assert cases[0]["config"]["users"]["qa1"]["username"] == "default-u"

    # 显式选定默认配置行本身:绑定生效(换 merchant-b 行,标签仍 qa1)
    r = await client.post("/api/runs", headers=h, json=_run_payload(
        scenarioId="sc-ec-r2", dataSetIds=[], execConfigId=default_id))
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 2)
    assert cases[1]["config"]["users"]["qa1"]["username"] == "merchant-u"
    cfg = await _last_cfg()
    assert cfg["execConfigId"] == default_id


async def test_dispatch_config_of_other_user_404(
        client, plate_mock: PlateMock):
    plate_mock.behaviour = "echo"
    await register_and_login(client, "ec_r3", "pw123456")
    h = await register_and_login(client, "ec_r3", "pw123456")
    await _seed_scene(client, h, "sc-ec-r3")
    await register_and_login(client, "ec_other", "pw123456")
    other_cid = await _mk_config(await _uid("ec_other"), "别人的")
    r = await client.post("/api/runs", headers=h, json=_run_payload(
        scenarioId="sc-ec-r3", dataSetIds=[], execConfigId=other_cid))
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "exec_config_not_found"


# ── ⑥ 预览:逐值带来源(source='exec_config')─────────────────────

async def test_preview_sources_with_exec_config(client, plate_mock: PlateMock):
    plate_mock.behaviour = "echo"
    await register_and_login(client, "ec_pv", "pw123456")
    h = await register_and_login(client, "ec_pv", "pw123456")
    await _seed_scene(client, h, "sc-ec-pv")
    uid = await _uid("ec_pv")
    async with db_module.SessionLocal() as s:
        uat = await _env(s, "ec-pv-uat")
        await s.commit()
    await _seed_auth(uid, "qa1", "default-u")
    await _seed_auth(uid, "merchant-b", "merchant-u")
    cid = await _mk_config(
        uid, "预览套", env_id=uat, bindings={_ALIAS: "merchant-b"},
        carry={"grade": "B"})
    # 公共层放一个 carry 值,验证覆盖层压层序
    async with db_module.SessionLocal() as s:
        pub = await carry_store.public_scope(s)
        await carry_store.put_bindings(
            s, _BASE, {"grade": "pub"}, updated_by_id=None,
            updated_by_name="t", scope=pub)
        await s.commit()

    r = await client.post("/api/runs/preview", headers=h, json={
        "scenarioId": "sc-ec-pv", "execConfigId": cid})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["env"]["environmentSource"] == "exec_config"
    # 槽位:键 = 声明槽 qa1,取用 = merchant-b 行,slotSource 明示偏离
    assert body["auths"]["qa1"]["bindingId"] is not None
    assert body["auths"]["qa1"]["slotSource"] == "exec_config"
    assert body["auths"]["qa1"]["configuredSlot"] == "merchant-b"
    # carry:覆盖值 source=exec_config(压公共层)
    assert body["carry"][_ALIAS]["grade"] == \
        {"value": "B", "source": "exec_config"}

    # 不带 execConfigId 且无默认配置:预览回落旧链(env 无/exec_config*)
    r = await client.post("/api/runs/preview", headers=h,
                          json={"scenarioId": "sc-ec-pv"})
    body = r.json()
    assert body["env"] is None or body["env"]["environmentSource"] not in \
        ("exec_config", "exec_config_default")
    assert body["auths"]["qa1"].get("slotSource") is None
