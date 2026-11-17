"""派发侧标签口径回归(2026-11-17 M3 前置修复,P1-1/P1-2/P1-3)。

钉住三处派发快照语义(redesign §8.2 与 dispatch 注释的对齐):
* **P1-1 adhoc**:执行标签 = 身份标签(非平台默认)—— 校验过的
  地址/版本线与实际执行同一套;case.json 地址按身份标签取;
* **P1-2 graph**:顶层快照记空(单元自治)—— config_json 无
  environmentId、job 配方 env_snapshot 空、worker 物化收到的 env=None
  (逐单元解析可达;修复前顶层解析恒非空,被当重放快照钉整图);
* **P1-3 rerun**:按首发快照回放环境 —— 标签源(默认位)变化不影响
  重跑(修复前 environmentId 经已退役的 RunRequest 字段传键,被
  pydantic 静默丢弃,重跑实为重新解析)。
"""
from __future__ import annotations

import asyncio

import sqlalchemy as sa

from app.core import db as db_module
from app.models import (
    AuthAccount, Deployment, Environment, Execution, ExecutionJob, Service,
    ServiceIdentity, SystemEnvInstance,
)
from app.services import run_dispatcher as rd
from tests.helpers import make_draft, register_and_login, wait_until as _wait

from ._fanout_stub import _capture_fanout
from .inbound_fixtures import mk_user
from .test_access_tokens import GET_STEP, _user_id
from . import test_adhoc_run as _ad
from . import test_scenario_composer_plate_integration as _plate_it

# pytest 按对象上的 fixture 标记注册(名称仍为 plate_mock);走模块属性
# 而非 from-import,避免测试参数同名触发 pyflakes 的重定义告警。
PlateMock = _plate_it.PlateMock
plate_mock = _plate_it.plate_mock

EP, SYSTEM, SERVICE, SVC = _ad.EP, _ad.SYSTEM, _ad.SERVICE, _ad.SVC
UAT_URL = "https://settle.uat.local"


async def _execution(ex_id: int) -> Execution:
    async with db_module.SessionLocal() as s:
        return await s.get(Execution, ex_id)


async def _wait_terminal_like(ex_id: int, statuses: tuple[str, ...],
                              timeout_s: float = 15.0) -> Execution:
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout_s
    while loop.time() < deadline:
        ex = await _execution(ex_id)
        if ex.status in statuses:
            return ex
        await asyncio.sleep(0.1)
    raise TimeoutError(f"execution {ex_id} not in {statuses}")


async def _seed_two_tags() -> tuple[int, int]:
    """双标签布景:SIT(平台默认)与 UAT(条目钉定);部署地址按标签
    区分(校验侧与执行侧分得开才测得出错位)。返回 (sit_id, uat_id)。"""
    async with db_module.SessionLocal() as s:
        sit = Environment(name="SIT", is_default=True)
        s.add(sit)
        await s.flush()
        uat = Environment(name="UAT")
        s.add(uat)
        await s.flush()
        s.add(Service(name=SERVICE, system=SYSTEM, kind="plate"))
        s.add(ServiceIdentity(alias_name=SVC, base_service=SERVICE,
                              env_id=uat.id, ref_mode="default"))
        for env_id, line in ((uat.id, "2.1"), (sit.id, "1.0")):
            s.add(SystemEnvInstance(system=SYSTEM, env_id=env_id, line=line))
        s.add(Deployment(base_service=SERVICE, env_id=uat.id, base_url=UAT_URL))
        s.add(Deployment(base_service=SERVICE, env_id=sit.id,
                         base_url=_ad.BASE_URL))
        await s.commit()
        return sit.id, uat.id


class TestAdhocDispatchTag:
    async def test_snapshot_and_case_use_identity_tag(
            self, client, plate_mock: PlateMock, monkeypatch):
        """P1-1:临时调用执行标签 = 条目标签(UAT),非平台默认(SIT);
        执行器 case.json 的服务地址也按条目标签取(校验=执行同套)。"""
        _sit_id, uat_id = await _seed_two_tags()
        await mk_user("ad_tag")
        # 账户落 SIT(默认环境)—— §8.3 凭证解耦,跨标签仍按 system 唯一解析
        async with db_module.SessionLocal() as s:
            uid = await _user_id("ad_tag")
            env = (await s.execute(sa.select(Environment.id).where(
                Environment.is_default.is_(True)))).scalar()
            s.add(AuthAccount(
                owner_id=uid, system=SYSTEM, env_id=env, username="qa-tag",
                password_enc=_ad.fernet_encrypt("p"), is_default=True))
            await s.commit()
        h = await _ad._personal(client, "ad_tag", scope_aliases=(SVC,),
                                cred_usernames=("qa-tag",))
        _ad._plate_ready(plate_mock)
        cases: list[dict] = []
        _ad._patch_launch(monkeypatch, cases)

        r = await _ad._post(client, h, _ad._body())
        assert r.status_code == 201, r.text
        ex_id = r.json()["executionId"]
        ex = await _wait_terminal_like(ex_id, ("done", "failed"))
        assert ex.status == "done", ex.config_json

        # 派发快照:标签 = 身份(UAT),非平台默认(SIT)
        assert ex.config_json["environmentId"] == uat_id
        assert ex.config_json["environmentSource"] == "identity"
        # 执行器收到的地址按条目标签(UAT 部署行)
        assert cases, "launch 未被调用"
        assert cases[0]["config"]["services"][SVC] == UAT_URL


class TestGraphDispatchTag:
    async def test_top_level_snapshot_empty(self, client, monkeypatch):
        """P1-2:graph 顶层快照记空 —— config_json 无 environmentId、
        job 配方 env_snapshot 空、worker 物化收到 env=None(逐单元解析
        的输入;修复前恒为宿主/平台默认,被当重放快照钉整图)。"""
        headers = await register_and_login(client)
        async with db_module.SessionLocal() as s:
            s.add(Environment(name="G-ENV", is_default=True))
            await s.commit()
        r = await client.post("/api/scenarios", headers=headers, json=make_draft(
            "sc-g-tag", steps=[GET_STEP]))
        assert r.status_code in (200, 201), r.text

        seen: dict = {}

        async def _fake_materialize(session, owner_id, graph_spec, **kw):
            seen["env"] = kw.get("env")
            raise rd.GraphDispatchError("stub: 只测派发快照口径")

        from app.services import graph_dispatch as gd
        monkeypatch.setattr(gd, "materialize_graph", _fake_materialize)

        r = await client.post("/api/runs", headers=headers, json={
            "scenarioId": "sc-g-tag",
            "graph": {"mode": "aggregate",
                      "units": [{"ref": "a", "scenarioId": "sc-g-tag"}]},
        })
        assert r.status_code == 201, r.text
        ex_id = r.json()["executionId"]

        ex = await _wait_terminal_like(ex_id, ("plate_rejected", "failed",
                                               "dispatcher_error", "done"))
        assert "environmentId" not in (ex.config_json or {})   # 顶层记空
        async with db_module.SessionLocal() as s:
            job = (await s.execute(sa.select(ExecutionJob).where(
                ExecutionJob.execution_id == ex_id))).scalar_one()
        assert job.payload["args"]["env_snapshot"] == {}       # 配方记空
        assert seen["env"] is None                             # 逐单元可达


class TestRerunEnvReplay:
    async def test_rerun_replays_first_dispatch_snapshot(
            self, client, monkeypatch):
        """P1-3:重跑按首发快照回放环境 —— 平台默认位从 E1 切到 E2 后,
        rerun 的 environmentId 仍是 E1(修复前重跑实为重新解析 → E2)。"""
        headers = await register_and_login(client)
        async with db_module.SessionLocal() as s:
            e1 = Environment(name="R-E1", is_default=True)
            s.add(e1)
            await s.flush()
            e2 = Environment(name="R-E2")
            s.add(e2)
            # M3 §8.5:派发硬门要求地址落点 —— E1 带部署行(rerun 回放
            # E1 时也须过门;E2 无部署,若重解析会换到 E2 并被门拦下)
            s.add(Deployment(base_service="svc", env_id=e1.id,
                             base_url="http://rr-e1"))
            await s.commit()
            e1_id, e2_id = e1.id, e2.id

        r = await client.post("/api/scenarios", headers=headers, json=make_draft(
            "sc-rr", steps=[GET_STEP]))
        assert r.status_code in (200, 201), r.text
        cap = await _capture_fanout(monkeypatch)
        r = await client.post("/api/runs", headers=headers, json={
            "scenarioId": "sc-rr"})
        assert r.status_code == 201, r.text
        ex1 = r.json()["executionId"]
        await _wait(lambda: len(cap) == 1)
        cfg1 = (await _execution(ex1)).config_json
        assert cfg1["environmentId"] == e1_id        # 首发:平台默认 E1

        # 标签源变化:默认位切到 E2(若重解析,rerun 会拿到 E2)
        async with db_module.SessionLocal() as s:
            await s.execute(sa.text(
                "UPDATE environments SET is_default = false WHERE id = :i"),
                {"i": e1_id})
            await s.execute(sa.text(
                "UPDATE environments SET is_default = true WHERE id = :i"),
                {"i": e2_id})
            await s.commit()

        r2 = await client.post(f"/api/executions/{ex1}/rerun", headers=headers)
        assert r2.status_code == 201, r2.text
        ex2 = r2.json()["executionId"]
        await _wait(lambda: len(cap) == 2)
        cfg2 = (await _execution(ex2)).config_json
        assert cfg2["environmentId"] == e1_id        # 回放首发快照
        assert cfg2["environmentSource"] == "default"  # source 原样透出
