"""authz M2a S2.1:环境选择链 + 地址 ③ 层切部署表。

链路:本次显式(RunRequest/图级)> 方案 > 项目默认 > 个人偏好 > 默认
环境;S6 起地址只来自部署表(别名自带地址与影子期合并规则随 0047
退役;无环境 = 无 ③)。集成模板的环境不吃个人偏好(同一模板全订阅者
同一指纹)。
"""
from __future__ import annotations

import pytest
import sqlalchemy as sa

from app.core import db as db_module
from app.models import (
    Deployment, Environment, Execution, IntegrationTask, Project,
)
from app.models.composer_scenario import ComposerScenario
from app.models.permission import UserPref
from app.models.service_alias import ServiceAlias
from app.services import env_chain, integration_runner, scheme_store
from app.services import service_aliases
from app.services.env_chain import (
    NO_ENV, EnvChoice, EnvironmentNotFound, resolve_environment,
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
    env = Environment(name=name, description="", lines={},
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
    """建环境 + 别名 + 该环境的部署行;返回环境 id。"""
    async with db_module.SessionLocal() as s:
        env_id = await _env(s, env_name)
        s.add(ServiceAlias(alias_name=_ALIAS, base_service=_BASE))
        if deploy_url:
            s.add(Deployment(base_service=_BASE, env_id=env_id,
                             base_url=deploy_url))
        await s.commit()
        return env_id


async def _last_config_json() -> dict:
    async with db_module.SessionLocal() as s:
        ex = (await s.execute(sa.select(Execution).order_by(
            Execution.id.desc()))).scalars().first()
        return ex.config_json, ex.id


# ── ① resolve_environment 链路优先级 ───────────────────────────────

async def test_chain_explicit_wins_and_missing_raises(fresh_db):
    async with db_module.SessionLocal() as s:
        await _env(s, "s21-dev", is_default=True)
        sit = await _env(s, "s21-sit")
        await s.commit()
        assert await resolve_environment(s, explicit=sit) == \
            EnvChoice(sit, "explicit")
        with pytest.raises(EnvironmentNotFound):
            await resolve_environment(s, explicit=99999)


async def test_chain_scheme_project_preference_default(client, fresh_db):
    await _member(client, "s21chain")
    async with db_module.SessionLocal() as s:
        uid = (await s.execute(sa.text(
            "SELECT id FROM users WHERE username = 's21chain'"))).scalar()
        dflt = await _env(s, "s21-default", is_default=True)
        dev = await _env(s, "s21-dev")
        sit = await _env(s, "s21-sit")
        proj = Project(name="s21-proj", default_environment_id=dev)
        s.add(proj)
        s.add(UserPref(user_id=uid, key=env_chain.PREF_KEY, value=sit))
        await s.commit()
        pid = proj.id

        # 方案 > 项目 > 个人偏好 > 默认
        assert await resolve_environment(
            s, scheme_env=sit, project_id=pid, user_id=uid) == \
            EnvChoice(sit, "scheme")
        assert await resolve_environment(
            s, project_id=pid, user_id=uid) == EnvChoice(dev, "project")
        assert await resolve_environment(s, user_id=uid) == \
            EnvChoice(sit, "preference")
        assert await resolve_environment(s) == EnvChoice(dflt, "default")
        # 悬空的方案环境视同未设置,落到下一位
        assert await resolve_environment(
            s, scheme_env=99999, project_id=pid) == EnvChoice(dev, "project")


async def test_chain_none_when_nothing_set(fresh_db):
    async with db_module.SessionLocal() as s:
        await _env(s, "s21-plain")
        await s.commit()
        assert await resolve_environment(s) is NO_ENV


# ── ② 地址 ③:部署表单源(S6)───────────────────────────────────────

async def test_base_urls_for_env_aware(fresh_db):
    dev = await _seed_addresses("s21-dev", deploy_url="http://dep-dev")
    async with db_module.SessionLocal() as s:
        # 无环境:无 ③(别名自带地址已退役)
        assert await service_aliases.base_urls_for(s, [_ALIAS]) == {}
        # 显式 / 默认兜底同口径:别名 → 基础服务 → 部署行
        for src in ("explicit", "default"):
            assert await service_aliases.base_urls_for(
                s, [_ALIAS], env=EnvChoice(dev, src)) == \
                {_ALIAS: "http://dep-dev"}
        # 非别名键 = 基础服务本身
        assert await service_aliases.base_urls_for(
            s, [_BASE], env=EnvChoice(dev, "explicit")) == \
            {_BASE: "http://dep-dev"}


# ── ③ 派发:快照 + 物化地址 + 重跑回放 ─────────────────────────────

async def test_dispatch_explicit_env_snapshot_and_address(
        client, plate_mock: PlateMock, monkeypatch):
    plate_mock.behaviour = "echo"
    h = await _member(client, "s21run")
    await _seed_scenario(client, h, "sc-s21-run")
    dev = await _seed_addresses("s21-run-dev", deploy_url="http://dep-dev")
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)

    r = await client.post("/api/runs", headers=h, json=_run_payload(
        scenarioId="sc-s21-run", dataSetIds=[], environmentId=dev))
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 1)
    assert cases[0]["config"]["services"][_ALIAS] == "http://dep-dev"
    cfg, ex_id = await _last_config_json()
    assert cfg["environmentId"] == dev
    assert cfg["environmentSource"] == "explicit"

    # 不带环境(无默认环境):无 ③,地址留缺口(引擎显式报错),快照键缺席
    r = await client.post("/api/runs", headers=h, json=_run_payload(
        scenarioId="sc-s21-run", dataSetIds=[]))
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 2)
    assert _ALIAS not in cases[1]["config"]["services"]
    cfg, _ = await _last_config_json()
    assert "environmentId" not in cfg

    # 重跑按快照回放(第一次执行的显式环境)
    r = await client.post(f"/api/executions/{ex_id}/rerun", headers=h)
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 3)
    assert cases[2]["config"]["services"][_ALIAS] == "http://dep-dev"


async def test_dispatch_scheme_env_resolved_server_side(
        client, plate_mock: PlateMock, monkeypatch):
    """请求没带环境但带 schemeId → 服务端回查方案环境(来源 scheme)。"""
    plate_mock.behaviour = "echo"
    h = await _member(client, "s21sch")
    await _seed_scenario(client, h, "sc-s21-sch")
    dev = await _seed_addresses("s21-sch-dev", deploy_url="http://dep-sch")
    async with db_module.SessionLocal() as s:
        sch = await scheme_store.create_scheme(
            s, "sc-s21-sch", name="带环境", payload={"environmentId": dev})
    cases: list[dict] = []
    _patch_launch_capture(monkeypatch, cases)

    r = await client.post("/api/runs", headers=h, json=_run_payload(
        scenarioId="sc-s21-sch", dataSetIds=[], schemeId=sch["schemeId"]))
    assert r.status_code == 201, r.text
    await _wait(lambda: len(cases) >= 1)
    assert cases[0]["config"]["services"][_ALIAS] == "http://dep-sch"
    cfg, _ = await _last_config_json()
    assert (cfg["environmentId"], cfg["environmentSource"]) == (dev, "scheme")


async def test_dispatch_unknown_environment_404(client, plate_mock: PlateMock):
    plate_mock.behaviour = "echo"
    h = await _member(client, "s21miss")
    await _seed_scenario(client, h, "sc-s21-miss")
    r = await client.post("/api/runs", headers=h, json=_run_payload(
        scenarioId="sc-s21-miss", dataSetIds=[], environmentId=99999))
    assert r.status_code == 404, r.text
    assert "environment_not_found" in r.text


# ── ④ 预检:按方案环境判缺口 ───────────────────────────────────────

async def test_precheck_env_aware(client, fresh_db):
    h = await _member(client, "s21pre")
    await _seed_scenario(client, h, "sc-s21-pre")
    dev = await _seed_addresses("s21-pre-dev", deploy_url="http://dep-pre")
    async with db_module.SessionLocal() as s:
        plain = await scheme_store.create_scheme(
            s, "sc-s21-pre", name="无环境", payload={})
        with_env = await scheme_store.create_scheme(
            s, "sc-s21-pre", name="带环境", payload={"environmentId": dev})

    r = await client.post("/api/run/precheck", headers=h, json=[
        {"scenarioId": "sc-s21-pre", "schemeId": plain["schemeId"]},
        {"scenarioId": "sc-s21-pre", "schemeId": with_env["schemeId"]}])
    assert r.status_code == 200, r.text
    no_env, env = r.json()
    assert no_env["unboundServices"] == [_ALIAS]   # 别名无地址、无环境
    assert env["unboundServices"] == []            # 方案环境给了部署地址


# ── ⑤ 导出:overlay.environmentId 为显式位 ─────────────────────────

async def test_export_overlay_env_materializes_deployment(
        client, plate_mock: PlateMock):
    plate_mock.behaviour = "echo"
    h = await _member(client, "s21exp")
    dev = await _seed_addresses("s21-exp-dev", deploy_url="http://dep-exp")
    body = _draft("sc-s21-exp", steps=[_STEP])
    r = await client.post("/api/scenarios/preview-plate", headers=h,
                          json={**body, "overlay": {"environmentId": dev}})
    assert r.status_code == 200, r.text
    assert r.json()["converted"]["config"]["services"][_ALIAS] == \
        "http://dep-exp"
    # 不带环境(无默认环境):无 ③
    r = await client.post("/api/scenarios/preview-plate", headers=h,
                          json={**body, "overlay": {}})
    assert r.status_code == 200, r.text
    assert _ALIAS not in r.json()["converted"]["config"]["services"]


# ── ⑥ 集成模板:环境不吃个人偏好;指纹随部署地址变化 ──────────────

async def test_template_env_ignores_preference_and_fingerprint_tracks(
        client, fresh_db):
    h = await _member(client, "s21fp")
    await _seed_scenario(client, h, "sc-s21-fp")
    async with db_module.SessionLocal() as s:
        uid = (await s.execute(sa.text(
            "SELECT id FROM users WHERE username = 's21fp'"))).scalar()
        dev = await _env(s, "s21-fp-dev")
        sit = await _env(s, "s21-fp-sit")
        proj = Project(name="s21-fp-proj", default_environment_id=dev)
        s.add(proj)
        await s.flush()
        s.add(ServiceAlias(alias_name=_ALIAS, base_service=_BASE))
        dep = Deployment(base_service=_BASE, env_id=dev,
                         base_url="http://dep-fp")
        s.add(dep)
        s.add(Deployment(base_service=_BASE, env_id=sit,
                         base_url="http://dep-sit"))
        # 持有人偏好指向 sit —— 模板环境不应受影响
        s.add(UserPref(user_id=uid, key=env_chain.PREF_KEY, value=sit))
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
        assert env == EnvChoice(dev, "project")   # 项目默认,不是偏好 sit

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
