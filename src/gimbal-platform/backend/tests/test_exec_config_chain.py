"""执行配置链(P1-7 续期;分层② 分批设计)—— env 位/装载映射/carry 覆盖。

registry 口径:配置绑定 = {服务/条目键: 换用条目名};注入标签 = 声明
条目名(场景引用),取用换池内账户(slot_lookup_overrides 的 lookup 映射)。
"""
from __future__ import annotations

import sqlalchemy as sa

from app.core import db as db_module
from app.core.security import fernet_encrypt
from app.models import (
    AuthAccount, Deployment, Environment, ExecConfig, Service,
    ServiceIdentity,
)
from app.services import carry_store
from app.services.carry_injection import build_carry_context
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
_ALIAS = "fin-dev"          # 引用基础服务的条目(场景步骤 call.service)
_STEP = {"kind": "step",
         "call": {"service": _ALIAS, "method": "GET", "path": "/x"},
         "request": {"kind": "request", "body": {}}, "strategy": []}


async def _uid(username: str) -> int:
    async with db_module.SessionLocal() as s:
        return (await s.execute(sa.text(
            "SELECT id FROM users WHERE username = :u"),
            {"u": username})).scalar()


async def _env(s, name: str, *, is_default: bool = False) -> int:
    env = Environment(name=name, description="",
                      is_default=is_default)
    s.add(env)
    await s.flush()
    return env.id


async def _default_env_id() -> int:
    async with db_module.SessionLocal() as s:
        env = (await s.execute(sa.select(Environment.id).where(
            Environment.is_default.is_(True)))).scalar_one_or_none()
        if env is not None:
            return env
        s.add(Environment(name="ec-plain", is_default=True))
        await s.commit()
        return (await s.execute(sa.select(Environment.id).where(
            Environment.is_default.is_(True)))).scalar_one()


async def _seed_scene(client, h, sid: str, *, env_id: int | None = None) -> None:
    """条目 fin-dev(钉给定环境,缺省 = 默认环境)+ 场景 + 主档。"""
    env = env_id if env_id is not None else await _default_env_id()
    async with db_module.SessionLocal() as s:
        if (await s.execute(sa.select(Service.id).where(
                Service.name == _BASE))).scalar_one_or_none() is None:
            s.add(Service(name=_BASE, system=_BASE, kind="plate"))
        s.add(ServiceIdentity(alias_name=_ALIAS, base_service=_BASE,
                              env_id=env, ref_mode="default"))
        await s.commit()
    r = await client.post("/api/scenarios", headers=h,
                          json=_draft(sid, steps=[_STEP]))
    assert r.status_code in (200, 201), r.text


async def _seed_entry(uid: int, name: str, username: str, *,
                      env_id: int | None = None) -> int:
    """条目 name(username-ref → 属主账户 username)+ 主档;返回账户 id。"""
    env = env_id if env_id is not None else await _default_env_id()
    async with db_module.SessionLocal() as s:
        from app.models import Deployment, SystemEnvInstance
        if (await s.execute(sa.select(Service.id).where(
                Service.name == _BASE))).scalar_one_or_none() is None:
            s.add(Service(name=_BASE, system=_BASE, kind="plate"))
        # M3 §8.5:实例登录口 + 部署行(派发硬门;幂等)
        if (await s.execute(sa.select(SystemEnvInstance.id).where(
                SystemEnvInstance.system == _BASE,
                SystemEnvInstance.env_id == env))
                ).scalar_one_or_none() is None:
            s.add(SystemEnvInstance(system=_BASE, env_id=env,
                                    login_url=f"https://{_BASE}.login"))
        if (await s.execute(sa.select(Deployment.id).where(
                Deployment.base_service == _BASE,
                Deployment.env_id == env))).scalar_one_or_none() is None:
            s.add(Deployment(base_service=_BASE, env_id=env,
                             base_url=f"https://{_BASE}.dep"))
        s.add(ServiceIdentity(alias_name=name, base_service=_BASE,
                              env_id=env, ref_mode="username",
                              ref_username=username))
        acc = AuthAccount(
            owner_id=uid, system=_BASE, env_id=env, username=username,
            password_enc=fernet_encrypt(f"pw-{username}"),
            is_default=False)
        s.add(acc)
        await s.commit()
        return acc.id


async def _seed_default_account(uid: int, username: str, *,
                                env_id: int | None = None) -> int:
    """属主默认账户(default-ref 条目的取用行)。"""
    env = env_id if env_id is not None else await _default_env_id()
    async with db_module.SessionLocal() as s:
        acc = AuthAccount(
            owner_id=uid, system=_BASE, env_id=env, username=username,
            password_enc=fernet_encrypt(f"pw-{username}"),
            is_default=True)
        s.add(acc)
        await s.commit()
        return acc.id


async def _mk_config(
    uid: int, name: str, *, is_default: bool = False, env_id=None,
    bindings: dict | None = None, carry: dict | None = None,
) -> int:
    systems = ([{"service": _BASE, "bindings": bindings or {},
                 "carryOverrides": carry or {}}]
               if (bindings or carry) else [])
    # §8.2:environment_id 列已退役(0060);env_id 形参保留但忽略
    async with db_module.SessionLocal() as s:
        row = ExecConfig(
            scope="user", scope_id=uid, name=name, is_default=is_default,
            payload={"systems": systems})
        s.add(row)
        await s.commit()
        return row.id


async def _last_cfg() -> dict:
    from app.models import Execution
    async with db_module.SessionLocal() as s:
        ex = (await s.execute(sa.select(Execution).order_by(
            Execution.id.desc()))).scalars().first()
        return ex.config_json


# ── ① 环境链位已随 §8.2 退役(2026-11-17):执行配置/方案/偏好/显式
#    均不再占链位 —— 链路优先级用例见 test_authz_s21_env_chain
#    (identity > project > default)。


# ── ② load_choice 摊平 + 越权 ──────────────────────────────────────

async def test_load_choice_flatten_and_isolation(client, fresh_db):
    await register_and_login(client, "ec_a", "pw123456")
    await register_and_login(client, "ec_b", "pw123456")
    a = await _uid("ec_a")
    b = await _uid("ec_b")
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
    await _mk_config(a, "默认", is_default=True)
    async with db_module.SessionLocal() as s:
        ch = await load_choice(s, a, None)
        assert ch is not None and not ch.explicit
        assert await load_choice(s, b, None) is None


# ── ②·5 §8.10:aliases(圈定调用身份)管理范围语义 —— 不进摊平 ──────

async def test_aliases_not_flattened_into_choice(client, fresh_db):
    """§8.10:aliases 只圈定配置页就绪度/拨测/凭证引导范围,执行链零消费
    —— _flatten 只取 bindings/carryOverrides,ExecConfigChoice 无该位。"""
    await register_and_login(client, "ec_al", "pw123456")
    uid = await _uid("ec_al")
    async with db_module.SessionLocal() as s:
        row = ExecConfig(
            scope="user", scope_id=uid, name="圈定套", is_default=False,
            payload={"systems": [{"service": _BASE, "aliases": [_ALIAS],
                                  "bindings": {_ALIAS: "merchant-b"}}]})
        s.add(row)
        await s.commit()
        cid = row.id

    async with db_module.SessionLocal() as s:
        ch = await load_choice(s, uid, cid)
        assert ch is not None and ch.explicit
        # 摊平值对象无 aliases 位;bindings 照常
        assert not hasattr(ch, "aliases")
        assert ch.bindings == {_ALIAS: "merchant-b"}


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
    env = await _default_env_id()
    async with db_module.SessionLocal() as s:
        s.add(ServiceIdentity(alias_name=_ALIAS, base_service=_BASE,
                              env_id=env, ref_mode="default"))
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


# ── ④ 取用换条目:标签不变、池内换行 ────────────────────────────────

async def test_slot_lookup_overrides_and_resolve(client, fresh_db):
    await register_and_login(client, "ec_s", "pw123456")
    uid = await _uid("ec_s")
    env = await _default_env_id()
    async with db_module.SessionLocal() as s:
        if (await s.execute(sa.select(Service.id).where(
                Service.name == _BASE))).scalar_one_or_none() is None:
            s.add(Service(name=_BASE, system=_BASE, kind="plate"))
        s.add(ServiceIdentity(alias_name=_ALIAS, base_service=_BASE,
                              env_id=env, ref_mode="default"))
        await s.commit()
    merchant_id = await _seed_entry(uid, "merchant-b", "merchant-u", env_id=env)

    from app.services.service_aliases import slot_lookup_overrides
    async with db_module.SessionLocal() as s:
        m = await slot_lookup_overrides(
            s, [_STEP], None, {_ALIAS: "merchant-b"})
    assert m == {_ALIAS: "merchant-b"}   # 声明条目(注入标签)→ 换用条目

    resolved = await resolve_exec_auths(
        db_module.SessionLocal, uid, [_ALIAS], slot_map=m)
    assert len(resolved) == 1
    assert resolved[0].alias == _ALIAS              # 注入标签不变(场景引用)
    assert resolved[0].username == "merchant-u"     # 池内取用换行
    assert resolved[0].binding_id == merchant_id


# ── ⑤ 派发端到端:env 快照 + users 注入 + 越权 404 ─────────────────

async def test_dispatch_env_from_selected_config(
        client, plate_mock: PlateMock, monkeypatch):
    plate_mock.behaviour = "echo"
    await register_and_login(client, "ec_r1", "pw123456")
    h = await register_and_login(client, "ec_r1", "pw123456")
    uid = await _uid("ec_r1")
    async with db_module.SessionLocal() as s:
        uat = await _env(s, "ec-uat")
        s.add(Deployment(base_service=_BASE, env_id=uat,
                         base_url="http://uat-fin"))
        await s.commit()
    # 条目/账户钉 uat(执行环境 = 选定配置的 env)
    await _seed_scene(client, h, "sc-ec-r1", env_id=uat)
    await _seed_default_account(uid, "default-u", env_id=uat)
    cid = await _mk_config(uid, "UAT套", env_id=uat)
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)

    r = await client.post("/api/runs", headers=h, json=_run_payload(
        scenarioId="sc-ec-r1", dataSetIds=[], execConfigId=cid))
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 1)
    cfg = await _last_cfg()
    # §8.2:执行配置不再给标签 —— 来源 = 身份位(条目钉 uat)
    assert cfg["environmentId"] == uat
    assert cfg["environmentSource"] == "identity"
    assert cfg["execConfigId"] == cid
    assert cases[0]["config"]["services"][_ALIAS] == "http://uat-fin"


async def test_dispatch_default_config_env_and_binding_injection(
        client, plate_mock: PlateMock, monkeypatch):
    """默认链:默认配置只吃私有区 carry(不吃绑定);显式选定时绑定换池行
    (env 链位已随 §8.2 退役 —— 标签一律按身份解析)。"""
    plate_mock.behaviour = "echo"
    await register_and_login(client, "ec_r2", "pw123456")
    h = await register_and_login(client, "ec_r2", "pw123456")
    uid = await _uid("ec_r2")
    async with db_module.SessionLocal() as s:
        sit = await _env(s, "ec-sit", is_default=True)
        s.add(Deployment(base_service=_BASE, env_id=sit,
                         base_url="http://sit-fin"))
        await s.commit()
    await _seed_scene(client, h, "sc-ec-r2", env_id=sit)
    default_id = await _mk_config(
        uid, "默认", is_default=True, env_id=sit, bindings={_ALIAS: "merchant-b"})
    await _seed_default_account(uid, "default-u", env_id=sit)
    await _seed_entry(uid, "merchant-b", "merchant-u", env_id=sit)
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)

    # 默认链:绑定不吃(仍取 fin-dev 默认账户);标签按身份(sit)
    r = await client.post("/api/runs", headers=h, json=_run_payload(
        scenarioId="sc-ec-r2", dataSetIds=[]))
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 1)
    cfg = await _last_cfg()
    assert (cfg["environmentId"], cfg["environmentSource"]) == \
        (sit, "identity")
    assert "execConfigId" not in cfg
    assert cases[0]["config"]["users"][_ALIAS]["username"] == "default-u"

    # 显式选定默认配置行本身:绑定生效(换 merchant-b 行,标签仍 fin-dev)
    r = await client.post("/api/runs", headers=h, json=_run_payload(
        scenarioId="sc-ec-r2", dataSetIds=[], execConfigId=default_id))
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 2)
    assert cases[1]["config"]["users"][_ALIAS]["username"] == "merchant-u"
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
    uid = await _uid("ec_pv")
    env = await _default_env_id()
    async with db_module.SessionLocal() as s:
        uat = await _env(s, "ec-pv-uat")
        await s.commit()
    await _seed_scene(client, h, "sc-ec-pv", env_id=env)
    await _seed_default_account(uid, "default-u", env_id=env)
    await _seed_entry(uid, "merchant-b", "merchant-u", env_id=env)
    cid = await _mk_config(
        uid, "预览套", env_id=env, bindings={_ALIAS: "merchant-b"},
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
    # §8.2:标签来源 = 身份位(执行配置只出绑定/carry,不再给 env)
    assert body["env"]["environmentSource"] == "identity"
    # 取用:键 = 声明条目 fin-dev,取用 = merchant-b 账户,slotSource 明示偏离
    assert body["auths"][_ALIAS]["bindingId"] is not None
    assert body["auths"][_ALIAS]["slotSource"] == "exec_config"
    assert body["auths"][_ALIAS]["configuredSlot"] == "merchant-b"
    # carry:覆盖值 source=exec_config(压公共层)
    assert body["carry"][_ALIAS]["grade"] == \
        {"value": "B", "source": "exec_config"}

    # 不带 execConfigId 且无默认配置:预览回落旧链(env 无/exec_config*)
    r = await client.post("/api/runs/preview", headers=h,
                          json={"scenarioId": "sc-ec-pv"})
    body = r.json()
    assert body["env"] is None or body["env"]["environmentSource"] not in \
        ("exec_config", "exec_config_default")
    assert body["auths"][_ALIAS].get("slotSource") is None


# ── ⑨ project scope(组级批次):维护门 + 项目区 carry 链位 ─────────

async def _mk_project(name: str, *, members: dict[str, str]) -> int:
    """直插普通项目 + 成员(UPC §20 布景守卫单点:无 admin 自动补
    守夜人 —— 活跃普通项目 ≥1 有效 admin 的库层不变量)。"""
    from tests.helpers import mk_normal_project

    return await mk_normal_project(name, members)


async def test_project_scope_crud_gates(client, fresh_db):
    await register_and_login(client, "ec_pa", "pw123456")   # 项目管理员
    await register_and_login(client, "ec_pm", "pw123456")   # 成员
    await register_and_login(client, "ec_px", "pw123456")   # 局外人
    pid = await _mk_project("ec-proj", members={"ec_pa": "admin",
                                                "ec_pm": "member"})
    h_pa = await register_and_login(client, "ec_pa", "pw123456")
    h_pm = await register_and_login(client, "ec_pm", "pw123456")
    h_px = await register_and_login(client, "ec_px", "pw123456")

    # 管理员建项目变体(默认)
    r = await client.post("/api/exec-configs", headers=h_pa, json={
        "name": "项目变体", "scope": "project", "projectId": pid,
        "isDefault": True,
        "systems": [{"service": _BASE, "bindings": {},
                     "carryOverrides": {"$.pv": "proj"}}]})
    assert r.status_code == 201, r.text
    row = r.json()
    assert row["scope"] == "project" and row["isDefault"] is True

    # 成员可读;局外人 404(不泄露存在性);成员写 403
    r = await client.get("/api/exec-configs", headers=h_pm,
                         params={"projectId": pid})
    assert r.status_code == 200 and len(r.json()) == 1
    r = await client.get("/api/exec-configs", headers=h_px,
                         params={"projectId": pid})
    assert r.status_code == 404
    r = await client.delete(f"/api/exec-configs/{row['id']}", headers=h_pm)
    assert r.status_code == 403

    # scope=project 缺 projectId → 422;公共项目 → 409
    r = await client.post("/api/exec-configs", headers=h_pa, json={
        "name": "无项目", "scope": "project"})
    assert r.status_code == 422
    async with db_module.SessionLocal() as s:
        pub = (await s.execute(sa.select(sa.text("id")).select_from(
            sa.text("projects")).where(sa.text("kind = 'public'"))
        )).scalar()
    r = await client.post("/api/exec-configs", headers=h_pa, json={
        "name": "公共", "scope": "project", "projectId": pub})
    assert r.status_code == 409

    # 个人面不受影响:本人列表仍空(不含项目行)
    r = await client.get("/api/exec-configs", headers=h_pm)
    assert r.status_code == 200 and r.json() == []


async def test_project_zone_carry_chain_with_project_config(
        client, plate_mock: PlateMock, monkeypatch):
    """⑧ 项目区链:场景显式 > 显式选定个人 > 项目默认配置 > 项目层 >
    公共项目层 —— 项目配置覆盖默认生效;显式个人配置压其上。"""
    plate_mock.behaviour = "echo"
    await register_and_login(client, "ec_pc", "pw123456")
    h = await register_and_login(client, "ec_pc", "pw123456")
    uid = await _uid("ec_pc")
    env = await _default_env_id()
    await _seed_scene(client, h, "sc-ec-pc", env_id=env)
    # 场景挂进普通项目(成员本人 = 管理员,便于建项目变体)
    pid = await _mk_project("ec-pc-proj", members={"ec_pc": "admin"})
    async with db_module.SessionLocal() as s:
        from sqlalchemy import text as _text

        from app.models.composer_run_scheme import ComposerRunScheme
        from app.models.composer_scenario import ComposerScenario
        # §20.2:跨项目移动 = 专门事务(延迟复合 FK + 方案随迁)
        await s.execute(_text(
            "SET CONSTRAINTS fk_scheme_scenario_zone, "
            "fk_scheme_combo_zone DEFERRED"))
        await s.execute(sa.update(ComposerScenario).where(
            ComposerScenario.scenario_id == "sc-ec-pc"
        ).values(project_id=pid))
        await s.execute(sa.update(ComposerRunScheme).where(
            ComposerRunScheme.scenario_id == "sc-ec-pc"
        ).values(project_id=pid))
        pub = await carry_store.public_scope(s)
        await carry_store.put_bindings(
            s, _BASE, {"$.pv": "pub", "$.layer": "pub"},
            updated_by_id=None, updated_by_name="t", scope=pub)
        await carry_store.put_bindings(
            s, _BASE, {"$.pv": "proj-layer"},
            updated_by_id=None, updated_by_name="t",
            scope=("project", pid))
        await s.commit()
    await _seed_default_account(uid, "default-u", env_id=env)
    # 项目默认配置:覆盖 $.pv;个人显式配置:覆盖 $.mine + 绑定换条目
    await client.post("/api/exec-configs", headers=h, json={
        "name": "项目变体", "scope": "project", "projectId": pid,
        "isDefault": True,
        "systems": [{"service": _BASE, "bindings": {},
                     "carryOverrides": {"$.pv": "proj-cfg"}}]})
    personal = await _mk_config(
        uid, "个人显式", bindings={_ALIAS: "merchant-b"},
        carry={"mine": "personal"})
    await _seed_entry(uid, "merchant-b", "merchant-u", env_id=env)
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)

    # ① 默认链(无显式个人):项目配置覆盖生效(压项目层/公共层)
    r = await client.post("/api/runs", headers=h, json=_run_payload(
        scenarioId="sc-ec-pc", dataSetIds=[]))
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 1)
    cfg = await _last_cfg()
    assert cfg["execCarryOverrides"] == {_BASE: {"$.pv": "proj-cfg"}}

    # ② 显式选定个人配置:个人覆盖压项目配置之上(字段级合并)
    r = await client.post("/api/runs", headers=h, json=_run_payload(
        scenarioId="sc-ec-pc", dataSetIds=[], execConfigId=personal))
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 2)
    cfg = await _last_cfg()
    assert cfg["execCarryOverrides"] == {_BASE: {"$.pv": "proj-cfg",
                                                 "mine": "personal"}}


# ── ⑦ 重跑回放终值(§7:配置后改不影响历史执行)──────────────────

async def test_rerun_replays_terminal_values(
        client, plate_mock: PlateMock, monkeypatch):
    """首发后改配置(换取用条目)→ 重跑仍按首发终值注入;新行再记同一
    份终值(链式重跑不变量)。"""
    plate_mock.behaviour = "echo"
    await register_and_login(client, "ec_rr", "pw123456")
    h = await register_and_login(client, "ec_rr", "pw123456")
    uid = await _uid("ec_rr")
    env = await _default_env_id()
    await _seed_scene(client, h, "sc-ec-rr", env_id=env)
    await _seed_default_account(uid, "default-u", env_id=env)
    await _seed_entry(uid, "merchant-b", "merchant-u", env_id=env)
    await _seed_entry(uid, "auditor", "auditor-u", env_id=env)
    cid = await _mk_config(uid, "回放套", bindings={_ALIAS: "merchant-b"})
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)

    r = await client.post("/api/runs", headers=h, json=_run_payload(
        scenarioId="sc-ec-rr", dataSetIds=[], execConfigId=cid))
    assert r.status_code == 201, r.text
    ex_id = r.json()["executionId"
                     ] if "executionId" in r.json() else r.json()["execution_id"]
    await _wait(lambda: len(cases) >= 1)
    assert cases[0]["config"]["users"][_ALIAS]["username"] == "merchant-u"
    cfg1 = await _last_cfg()
    assert cfg1["execSlotMap"] == {_ALIAS: "merchant-b"}

    # 首发后改配置:绑定换 auditor 条目
    r = await client.patch(f"/api/exec-configs/{cid}", headers=h, json={
        "systems": [{"service": _BASE, "bindings": {_ALIAS: "auditor"},
                     "carryOverrides": {}}]})
    assert r.status_code == 200, r.text

    # 重跑:仍按首发终值(merchant-u),不回查改过的配置行
    r = await client.post(f"/api/executions/{ex_id}/rerun", headers=h)
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 2)
    assert cases[1]["config"]["users"][_ALIAS]["username"] == "merchant-u"
    cfg2 = await _last_cfg()
    assert cfg2["execSlotMap"] == {_ALIAS: "merchant-b"}
    assert cfg2["execConfigId"] == cid


# ── ⑧ 入口排除:集成/定时不吃执行配置(同指纹不变量)─────────────

async def test_integration_never_resolves_exec_config(
        client, monkeypatch, plate_mock: PlateMock):
    """集成链手动执行全过程中,执行配置解析入口(load_choice)不被触达
    —— 「同一模板全订阅者同一指纹」不变量的结构性守卫。"""
    from app.services import exec_config as _ec
    from .test_integration import STEPS_GET, _mk_scenario, _task_body

    calls: list[int] = []

    async def _spy(db, user_id, config_id):
        calls.append(user_id)
        return await _load_choice_orig(db, user_id, config_id)

    _load_choice_orig = _ec.load_choice
    monkeypatch.setattr(_ec, "load_choice", _spy)
    # run_dispatcher 以 ``from .exec_config import ... load_choice`` 局部
    # 导入 —— spy 落在模块属性上即可命中(dispatch_target 每次现取)
    from app.services import integration_runner as ir
    from app.services import plate_client as pc

    h = await register_and_login(client, "ec_ig", "pw123456")
    sid = await _mk_scenario(client, h, "sc-ec-ig", STEPS_GET)
    # 执行人持有默认执行配置(有值可吃也不吃)
    uid = await _uid("ec_ig")
    await _mk_config(uid, "集成不吃", is_default=True,
                     bindings={_ALIAS: "merchant-b"})
    r = await client.post("/api/integration/tasks", headers=h,
                          json=_task_body(sid, identityMode="personal"))
    assert r.status_code in (200, 201), r.text
    tid = r.json()["id"]

    async def _fake_convert(scenario):
        return {"consumer": "platform", "converted": dict(scenario)}
    monkeypatch.setattr(pc, "convert", _fake_convert)

    class _FakeResult:
        launch_status = "ok"
        exit_code = 0
        error = ""
        details = [{"scenario_id": "sc-ig", "outputs": {}}]

    class _FakeChannels:
        async def run_case(self, case_path):
            return _FakeResult()

        async def reap_idle(self):
            return 0
    monkeypatch.setattr(ir, "channels", _FakeChannels())
    monkeypatch.setattr(
        ir, "materialize_run_copy",
        lambda converted, **kw: dict(converted))

    r = await client.post(f"/api/integration/tasks/{tid}/run", headers=h)
    assert r.status_code == 200, r.text
    assert calls == []    # 集成链从未触达执行配置解析
