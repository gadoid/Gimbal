"""标签解析链 + 地址 ③ 层(§8.2,2026-11-17 环境降级轮重写 s21)。

链路:**有效调用身份标签 > 项目默认 > 平台默认**;显式 environmentId
与方案/执行配置/偏好链位全部退役(旧链用例随轮改写)。S6 起地址只
来自部署表(无标签 = 无 ③)。集成模板的标签由模板(身份/项目)决定
—— 同一模板全订阅者同一指纹。
"""
from __future__ import annotations

import sqlalchemy as sa

from app.core import db as db_module
from app.models import (
    Deployment, Environment, Execution, IntegrationTask, Project,
)
from app.models.composer_scenario import ComposerScenario
from app.models import Service as MService
from app.models.service_identity import ServiceIdentity
from app.services import integration_runner, scheme_store
from app.services import service_aliases
from app.services.env_chain import (
    NO_ENV, EnvChoice, EnvMixed, resolve_execution_tag,
)

from .helpers import make_draft as _draft, wait_until as _wait
from .test_run_m1_capabilities import _patch_launch_capture, _run_payload
from .test_scenario_composer_plate_integration import PlateMock, plate_mock  # noqa: F401
from .test_scenario_visibility_and_copy import _member

_BASE = "fin-service"           # 基础服务(部署表键)
_ALIAS = "fin-dev"              # 引用它的别名(步骤 call.service)
_STEP = {"kind": "step",
         "call": {"service": _ALIAS, "method": "GET", "path": "/x"},
         "request": {"kind": "request", "body": {}}, "strategy": []}


async def _env(s, name: str, *, is_default: bool = False) -> int:
    env = Environment(name=name, description="",
                      is_default=is_default)
    s.add(env)
    await s.flush()
    return env.id


async def _seed_scenario(client, h, sid: str) -> None:
    r = await client.post("/api/scenarios", headers=h,
                          json=_draft(sid, steps=[_STEP]))
    assert r.status_code in (200, 201), r.text


async def _seed_addresses(env_name: str, *,
                          deploy_url: str | None) -> int:
    """建环境 + 条目(标签钉该环境)+ 主档 + 该环境的部署行 + 实例
    登录口(M3 §8.5 派发硬门 login_missing 口径);返回环境 id。"""
    async with db_module.SessionLocal() as s:
        from app.models import SystemEnvInstance
        env_id = await _env(s, env_name)
        if (await s.execute(sa.select(MService.id).where(
                MService.name == _BASE))).scalar_one_or_none() is None:
            s.add(MService(name=_BASE, system=_BASE, kind="plate"))
        s.add(ServiceIdentity(alias_name=_ALIAS, base_service=_BASE,
                              env_id=env_id, ref_mode="default"))
        s.add(SystemEnvInstance(system=_BASE, env_id=env_id,
                                login_url=f"http://login-{env_id}"))
        if deploy_url:
            s.add(Deployment(base_service=_BASE, env_id=env_id,
                             base_url=deploy_url))
        await s.commit()
        return env_id


async def _seed_pool_account(username: str, env_id: int,
                             *, system: str = _BASE) -> None:
    """执行人池账户(条目 default-ref 的取用行;S5 失败即中止)。"""
    from app.core.security import fernet_encrypt
    from app.models.auth_account import AuthAccount

    async with db_module.SessionLocal() as s:
        uid = (await s.execute(sa.text(
            "SELECT id FROM users WHERE username = :u"),
            {"u": username})).scalar_one()
        s.add(AuthAccount(owner_id=uid, system=system, env_id=env_id,
                          username="s21-u",
                          password_enc=fernet_encrypt("p"),
                          is_default=True))
        await s.commit()


async def _last_config_json() -> dict:
    async with db_module.SessionLocal() as s:
        ex = (await s.execute(sa.select(Execution).order_by(
            Execution.id.desc()))).scalars().first()
        return ex.config_json, ex.id


# ── ① resolve_execution_tag 链路优先级(§8.2)──────────────────────

async def test_chain_identity_project_default(fresh_db):
    async with db_module.SessionLocal() as s:
        dflt = await _env(s, "s21-default", is_default=True)
        dev = await _env(s, "s21-dev")
        sit = await _env(s, "s21-sit")
        if (await s.execute(sa.select(MService.id).where(
                MService.name == _BASE))).scalar_one_or_none() is None:
            s.add(MService(name=_BASE, system=_BASE, kind="plate"))
        proj = Project(name="s21-proj", default_environment_id=dev)
        s.add(proj)
        await s.flush()
        # 条目挂 sit:身份位胜出(项目默认 dev 不抢)
        s.add(ServiceIdentity(alias_name=_ALIAS, base_service=_BASE,
                              env_id=sit, ref_mode="default"))
        await s.commit()
        pid = proj.id

        assert await resolve_execution_tag(s, identity_names=[_ALIAS],
                                           project_id=pid) == \
            EnvChoice(sit, "identity")
        # 无身份 → 项目默认
        assert await resolve_execution_tag(s, project_id=pid) == \
            EnvChoice(dev, "project")
        # 无身份无项目 → 平台默认
        assert await resolve_execution_tag(s) == EnvChoice(dflt, "default")
        # 悬空名不参与判定(凭证解析另有 missing 分类)
        assert await resolve_execution_tag(s, identity_names=["ghost"],
                                           project_id=pid) == \
            EnvChoice(dev, "project")


async def test_chain_mixed_identities_raise(fresh_db):
    async with db_module.SessionLocal() as s:
        dev = await _env(s, "s21-mix-dev", is_default=True)
        sit = await _env(s, "s21-mix-sit")
        if (await s.execute(sa.select(MService.id).where(
                MService.name == _BASE))).scalar_one_or_none() is None:
            s.add(MService(name=_BASE, system=_BASE, kind="plate"))
        s.add(ServiceIdentity(alias_name="a-dev", base_service=_BASE,
                              env_id=dev, ref_mode="default"))
        s.add(ServiceIdentity(alias_name="a-sit", base_service=_BASE,
                              env_id=sit, ref_mode="default"))
        await s.commit()
        try:
            await resolve_execution_tag(s, identity_names=["a-dev", "a-sit"])
        except EnvMixed as e:
            assert set(e.entries) == {"a-dev", "a-sit"}
        else:
            raise AssertionError("EnvMixed not raised")


async def test_chain_none_when_nothing_set(fresh_db):
    async with db_module.SessionLocal() as s:
        await _env(s, "s21-plain")
        await s.commit()
        assert await resolve_execution_tag(s) is NO_ENV


# ── ② 地址 ③:部署表单源(S6)───────────────────────────────────────

async def test_base_urls_for_env_aware(fresh_db):
    dev = await _seed_addresses("s21-dev", deploy_url="http://dep-dev")
    async with db_module.SessionLocal() as s:
        # 无标签:无 ③(别名自带地址已退役)
        assert await service_aliases.base_urls_for(s, [_ALIAS]) == {}
        # 身份位 / 默认兜底同口径:别名 → 基础服务 → 部署行
        for src in ("identity", "default"):
            assert await service_aliases.base_urls_for(
                s, [_ALIAS], env=EnvChoice(dev, src)) == \
                {_ALIAS: "http://dep-dev"}
        # 非别名键 = 基础服务本身
        assert await service_aliases.base_urls_for(
            s, [_BASE], env=EnvChoice(dev, "identity")) == \
            {_BASE: "http://dep-dev"}


# ── ③ 派发:快照 + 物化地址 + 重跑回放 ─────────────────────────────

async def test_dispatch_identity_tag_snapshot_and_address(
        client, plate_mock: PlateMock, monkeypatch):
    """标签从有效身份解析(条目 env 即标签);请求里多发 environmentId
    被静默忽略(显式通道退役 §8.2)。"""
    plate_mock.behaviour = "echo"
    h = await _member(client, "s21run")
    await _seed_scenario(client, h, "sc-s21-run")
    dev = await _seed_addresses("s21-run-dev", deploy_url="http://dep-dev")
    await _seed_pool_account("s21run", dev)
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)

    r = await client.post("/api/runs", headers=h, json=_run_payload(
        scenarioId="sc-s21-run", dataSetIds=[], environmentId=dev))
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 1)
    assert cases[0]["config"]["services"][_ALIAS] == "http://dep-dev"
    cfg, ex_id = await _last_config_json()
    assert cfg["environmentId"] == dev
    assert cfg["environmentSource"] == "identity"

    # 不带身份的场景(未登记服务键):无标签 → 无 ③,地址留缺口 ——
    # M3 §8.5 起为派发前硬拦(address_missing 409,错误时机从引擎步骤
    # 级前移;旧行为 = 201 放行、执行期报错已退役)
    raw_step = {"kind": "step",
                "call": {"service": "s21-ghost-svc", "method": "GET",
                         "path": "/x"},
                "request": {"kind": "request", "body": {}}, "strategy": []}
    await client.post("/api/scenarios", headers=h,
                      json=_draft("sc-s21-raw", steps=[raw_step]))
    r = await client.post("/api/runs", headers=h, json=_run_payload(
        scenarioId="sc-s21-raw", dataSetIds=[]))
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "address_missing"
    assert r.json()["detail"]["services"] == ["s21-ghost-svc"]

    # 重跑按快照回放(第一次执行的标签)
    r = await client.post(f"/api/executions/{ex_id}/rerun", headers=h)
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 2)
    assert cases[1]["config"]["services"][_ALIAS] == "http://dep-dev"


async def test_dispatch_scheme_env_key_ignored(
        client, plate_mock: PlateMock, monkeypatch):
    """方案 payload 的存量 environmentId 不再消费 —— 标签按身份解析
    (来源 identity,不吃方案遗留键)。"""
    plate_mock.behaviour = "echo"
    h = await _member(client, "s21sch")
    await _seed_scenario(client, h, "sc-s21-sch")
    dev = await _seed_addresses("s21-sch-dev", deploy_url="http://dep-sch")
    await _seed_pool_account("s21sch", dev)
    sit = await _env_and_commit("s21-sch-sit")
    async with db_module.SessionLocal() as s:
        sch = await scheme_store.create_scheme(
            s, "sc-s21-sch", name="带环境",
            payload={"environmentId": sit})   # 存量键:指向另一标签,应被忽略
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)

    r = await client.post("/api/runs", headers=h, json=_run_payload(
        scenarioId="sc-s21-sch", dataSetIds=[], schemeId=sch["schemeId"]))
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 1)
    assert cases[0]["config"]["services"][_ALIAS] == "http://dep-sch"
    cfg, _ = await _last_config_json()
    assert (cfg["environmentId"], cfg["environmentSource"]) == (dev, "identity")


async def _env_and_commit(name: str) -> int:
    async with db_module.SessionLocal() as s:
        return await _env(s, name)


async def test_dispatch_environment_id_ignored(client, plate_mock: PlateMock):
    """旧客户端多发 environmentId(含不存在的 id):静默忽略,不再 404
    —— 标签一律自动解析。架构终态(2026-11-21):② 声明地址退役,
    条目 _ALIAS 落地(标签钉 s21-miss 环境 + 该环境部署行)后 201;
    客户端的 99999 被忽略,快照记录的是标签链解析出的真实环境。"""
    plate_mock.behaviour = "echo"
    h = await _member(client, "s21miss")
    env_id = await _seed_addresses("s21-miss", deploy_url="http://dep-miss")
    await _seed_pool_account("s21miss", env_id)   # 条目 default-ref 需池内账户
    draft = _draft("sc-s21-miss", steps=[_STEP])
    draft["definition"]["config"] = {"services": {_ALIAS: "http://direct"}}
    r = await client.post("/api/scenarios", headers=h, json=draft)
    assert r.status_code in (200, 201), r.text
    r = await client.post("/api/runs", headers=h, json=_run_payload(
        scenarioId="sc-s21-miss", dataSetIds=[], environmentId=99999))
    assert r.status_code == 201, r.text
    cfg, _ = await _last_config_json()
    assert cfg.get("environmentId") == env_id   # 真实标签,非客户端 99999


# ── ④ 预检:按身份标签判缺口 ───────────────────────────────────────

async def test_precheck_env_aware(client, fresh_db):
    h = await _member(client, "s21pre")
    await _seed_scenario(client, h, "sc-s21-pre")
    await _seed_addresses("s21-pre-dev", deploy_url="http://dep-pre")
    async with db_module.SessionLocal() as s:
        plain = await scheme_store.create_scheme(
            s, "sc-s21-pre", name="方案A", payload={})

    r = await client.post("/api/run/precheck", headers=h, json=[
        {"scenarioId": "sc-s21-pre", "schemeId": plain["schemeId"]}])
    assert r.status_code == 200, r.text
    (res,) = r.json()
    # 条目 fin-dev 挂在该标签且有部署行 → 地址就绪
    assert res["unboundServices"] == []


# ── ⑤ 导出:标签按身份解析(overlay 显式键退役)───────────────────

async def test_export_materializes_by_identity(
        client, plate_mock: PlateMock):
    plate_mock.behaviour = "echo"
    h = await _member(client, "s21exp")
    await _seed_addresses("s21-exp-dev", deploy_url="http://dep-exp")
    body = _draft("sc-s21-exp", steps=[_STEP])
    r = await client.post("/api/scenarios/preview-plate", headers=h,
                          json={**body, "overlay": {}})
    assert r.status_code == 200, r.text
    assert r.json()["converted"]["config"]["services"][_ALIAS] == \
        "http://dep-exp"


# ── ⑥ 集成模板:标签由模板(身份/项目)决定;指纹随部署地址变化 ────

async def test_template_env_by_identity_and_fingerprint_tracks(
        client, fresh_db):
    h = await _member(client, "s21fp")
    await _seed_scenario(client, h, "sc-s21-fp")
    async with db_module.SessionLocal() as s:
        uid = (await s.execute(sa.text(
            "SELECT id FROM users WHERE username = 's21fp'"))).scalar()
        dev = await _env(s, "s21-fp-dev")
        sit = await _env(s, "s21-fp-sit")
        proj = Project(name="s21-fp-proj", default_environment_id=sit)
        s.add(proj)
        await s.flush()
        s.add(ServiceIdentity(alias_name=_ALIAS, base_service=_BASE,
                              env_id=dev, ref_mode="default"))
        dep = Deployment(base_service=_BASE, env_id=dev,
                         base_url="http://dep-fp")
        s.add(dep)
        s.add(Deployment(base_service=_BASE, env_id=sit,
                         base_url="http://dep-sit"))
        scen = (await s.execute(sa.select(ComposerScenario).where(
            ComposerScenario.scenario_id == "sc-s21-fp"))).scalar_one()
        scen.project_id = proj.id
        tpl = IntegrationTask(name="s21-fp-tpl", owner_id=uid,
                              scenario_id="sc-s21-fp", target_system="fin",
                              trigger_cron="*/5 * * * *",
                              result_policy="latest")
        s.add(tpl)
        await s.commit()
        dep_id = dep.id

    async with db_module.SessionLocal() as s:
        scen = (await s.execute(sa.select(ComposerScenario).where(
            ComposerScenario.scenario_id == "sc-s21-fp"))).scalar_one()
        tpl = (await s.execute(sa.select(IntegrationTask).where(
            IntegrationTask.name == "s21-fp-tpl"))).scalar_one()
        env = await integration_runner._template_env(s, scen, {})
        # 身份位胜出(dev),项目默认(sit)不抢 —— 模板不吃任何个人维度
        assert env == EnvChoice(dev, "identity")

        fp1 = await integration_runner.consent_fingerprint_now(s, tpl, scen)
        row = await s.get(Deployment, dep_id)
        row.base_url = "http://dep-fp-v2"
        await s.commit()
        fp2 = await integration_runner.consent_fingerprint_now(s, tpl, scen)
        assert fp1 != fp2                         # 部署地址变 → 指纹变
        row = await s.get(Deployment, dep_id)
        row.base_url = "http://dep-fp"
        await s.commit()
        assert await integration_runner.consent_fingerprint_now(
            s, tpl, scen) == fp1                  # 确定性
