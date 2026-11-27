"""M1 执行能力补齐测试(V1 executor 语义移植):

* nRuns/parallel fan-out —— total = Σrows × nRuns,launch 调用次数一致
* serviceBindings 绑定注入 —— 绑定选条目注入 users(固定 merge 语义,
  场景内置 users 保留);prefix/mergePolicy 已随 RunRequest 收敛退役;
  env.baseUrl 补缺层已随执行环境退役(D2)

V3.2→B6③:执行 mock 落位 ``tests/_fake_engine.launch`` —
capture 读落盘的 case.json(引擎子进程的真实输入)。
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from httpx import AsyncClient

from .helpers import (
    launch_ok as _ok,
    make_draft as _draft,
    register_and_login as _register_and_login,
    wait_until as _wait,
)
from .test_scenario_composer_plate_integration import (
    PlateMock,
    plate_mock,  # noqa: F401  pytest fixture re-export
)
from .test_scenario_visibility_and_copy import _member, _seed_ds


def _run_payload(**extra: object) -> dict:
    payload = {
        "scenarioId": "sc-test",
        "dataSetIds": ["ds-001"],
    }
    # W19:执行参数平铺键(nRuns/parallel/stepTo)收进 runOptions
    flat = {k: extra.pop(k) for k in ("nRuns", "parallel", "stepTo")
            if k in extra}
    if flat:
        snake = {"nRuns": "n_runs", "parallel": "parallel",
                 "stepTo": "step_to"}
        payload["runOptions"] = {snake[k]: v for k, v in flat.items()}
    payload.update(extra)
    return payload


def _patch_launch_capture(
    monkeypatch: pytest.MonkeyPatch, sink: list[dict]
) -> None:
    """把 ``gimbal_launcher.launch`` 换成读 case.json 并捕获的假实现。"""

    async def _capture(case_path, *, step_to=None, report_dir=None,
                       cwd=None, timeout=None, engine_log_path=None,
                       on_event=None, on_log=None, log_counters=None,
                       n_runs=1, retry=0):
        sink.append(json.loads(Path(case_path).read_text(encoding="utf-8")))
        return _ok()

    from tests import _fake_engine as fe  # B6③:假引擎缝(legacy 链退役)
    monkeypatch.setattr(fe, "launch", _capture)


# ── nRuns / parallel fan-out ──────────────────────────────────────
async def test_n_runs_multiplies_total_and_gimbal_calls(
    client: AsyncClient,
    plate_mock: PlateMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P2-05 乘法下沉:2 行 × nRuns=3 → 2 次 launch(各带 n_runs=3),
    total_runs=2(单元口径),行 attempts=3(展开计数入列)。"""
    bob = await _member(client, "bob")
    await client.post(
        "/api/scenarios",
        headers=bob,
        json=_draft(steps=[{"id": "s1"}], vars_map={"qty": 1}),
    )
    await _seed_ds(client, bob)
    # 追加一行:ds-001 共 2 行
    r = await client.put(
        "/api/data-sets/ds-001",
        headers=bob,
        json={"name": "ds", "rows": [{"qty": 1}, {"qty": 2}]},
    )
    assert r.status_code == 200, r.text

    calls: list[dict] = []
    kw: list[dict] = []

    async def _capture_nruns(case_path, *, step_to=None, report_dir=None,
                             cwd=None, timeout=None, engine_log_path=None,
                             on_event=None, on_log=None, log_counters=None, n_runs=1, retry=0):
        calls.append(json.loads(Path(case_path).read_text(encoding="utf-8")))
        kw.append({"n_runs": n_runs, "retry": retry})
        return _ok()

    from tests import _fake_engine as fe
    monkeypatch.setattr(fe, "launch", _capture_nruns)

    r = await client.post(
        "/api/runs", headers=bob, json=_run_payload(nRuns=3, parallel=2)
    )
    assert r.status_code == 201, r.text

    await _wait(lambda: len(calls) >= 2)
    assert len(calls) == 2                       # 每 spawn 一次,乘法在执行器
    assert [k["n_runs"] for k in kw] == [3, 3]   # n_runs 经 --n-runs 下沉透传

    import sqlalchemy as sa

    from app.core import db as db_module
    from app.models import Execution

    async with db_module.SessionLocal() as s:
        ex = (
            (await s.execute(sa.select(Execution).order_by(Execution.id.desc())))
            .scalars()
            .first()
        )
        assert ex.total_runs == 2                # 单元口径(nRuns 不再展开)
        assert ex.config_json["runOptions"]["n_runs"] == 3
        assert ex.config_json["runOptions"]["parallel"] == 2


async def test_parallel_limits_concurrency(
    client: AsyncClient,
    plate_mock: PlateMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """parallel=2 → gimbal launch 同时在飞的数量永不超过 2。"""
    bob = await _member(client, "bob")
    await client.post(
        "/api/scenarios",
        headers=bob,
        json=_draft(steps=[{"id": "s1"}], vars_map={"qty": 1, "i": 0}),
    )
    await _seed_ds(client, bob)
    r = await client.put(
        "/api/data-sets/ds-001",
        headers=bob,
        json={"name": "ds", "rows": [{"i": i} for i in range(4)]},
    )
    assert r.status_code == 200, r.text

    in_flight = 0
    max_in_flight = 0
    done = 0

    async def _capture(case_path, *, step_to=None, report_dir=None,
                       cwd=None, timeout=None, engine_log_path=None,
                       on_event=None, on_log=None, log_counters=None,
                       n_runs=1, retry=0):
        nonlocal in_flight, max_in_flight, done
        in_flight += 1
        max_in_flight = max(max_in_flight, in_flight)
        await asyncio.sleep(0.05)
        in_flight -= 1
        done += 1
        return _ok()

    from tests import _fake_engine as fe
    monkeypatch.setattr(fe, "launch", _capture)

    r = await client.post(
        "/api/runs", headers=bob, json=_run_payload(nRuns=2, parallel=2)
    )
    assert r.status_code == 201, r.text

    # P2-05:4 行 × nRuns=2 → 4 次 spawn(乘法在执行器)
    await _wait(lambda: done >= 4)
    assert done == 4
    assert max_in_flight <= 2


# ── serviceBindings 绑定注入 ─────────────────────────────────────
async def _seed_built_in_user(client: AsyncClient, headers: dict) -> None:
    """建一个 config.users 里带内置认证 qa1 的场景 + case/ds。步骤引用
    服务 svc(S6:绑定只对 steps 实际引用的服务键选别名)。"""
    draft = _draft(steps=[{"id": "s1", "kind": "step",
                           "call": {"service": "svc", "path": "/x"}}])
    draft["definition"]["config"]["vars"] = {"qty": 1}  # C1:行键须 ⊆ 标量 vars
    r = await client.post("/api/scenarios", headers=headers, json=draft)
    assert r.status_code == 201, r.text
    # §3.5 闸(2026-11-20)后:内置 users 走存量注入(W6 属主基座口径不变)
    from tests.helpers import seed_legacy_users
    await seed_legacy_users("sc-test", {
        "qa1": {"url": "http://builtin", "username": "u0", "password": "p0"}})
    await _seed_ds(client, headers)


class _FakeAuth:
    """materialize_run_copy(_apply_users)只消费这些属性(与 AuthSession
    解密后一致)。"""

    def __init__(self, alias: str) -> None:
        self.alias = alias
        self.url = "http://exec"
        self.username = "exec-user"
        self.password = "exec-pass"
        self.token_type = "bearer"
        self.expires_in = 3600


async def _post_run(client: AsyncClient, headers: dict, **extra: object):
    return await client.post("/api/runs", headers=headers, json=_run_payload(**extra))


async def test_service_binding_auth_merge_keeps_built_in(
    client: AsyncClient,
    plate_mock: PlateMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """绑定选条目(S6:svc → svc-qa9;注入键 = 条目名)注入 users。
    v2.10 §11.1:执行链不吃内置凭证 —— 场景内置 users 不再保留
    (明文仅剩导出面 10-14 口径),users 唯一来源 = 凭证池解析。"""
    bob = await _member(client, "bob")
    await _seed_built_in_user(client, bob)
    # S5 失败即中止:绑定条目须在执行人池可解(dispatch 取用检查不走
    # 下面的 fake resolve)—— 四件套一次布景
    from app.core import db as _dbm
    from .conftest import seed_identity_fixture
    from sqlalchemy import text as _txt
    async with _dbm.SessionLocal() as _s:
        _uid = (await _s.execute(_txt(
            "SELECT id FROM users WHERE username = 'bob'"))).scalar()
        await seed_identity_fixture(
            _s, alias="svc-qa9", username="exec-user", password="p",
            service="svc", owner_id=_uid)
        await _s.commit()

    from app.services import run_dispatcher as rd

    payloads: list[dict] = []
    _patch_launch_capture(monkeypatch, payloads)

    async def _fake_resolve(db_factory, owner_id, aliases, *, env_id=None,
                            cred_project_id=None, slot_map=None):
        # S3.1:resolve_exec_auths 增环境参数(fanout 传入配方快照环境);
        # S8:增项目凭证池参数;分层②:增槽位取用覆盖(标签→取用槽)参数
        return [_FakeAuth(a) for a in aliases]

    monkeypatch.setattr(rd, "resolve_exec_auths", _fake_resolve)

    r = await _post_run(
        client, bob, serviceBindings={"svc": {"alias": "svc-qa9"}}
    )
    assert r.status_code == 201, r.text
    await _wait(lambda: len(payloads) >= 1)
    users = (payloads[0].get("config") or {}).get("users") or {}
    # 内置 qa1 不再进执行产物(§11.1);所选条目注入保留(键 = 条目名)
    assert set(users.keys()) == {"svc-qa9"}
    assert users["svc-qa9"]["username"] == "exec-user"


async def test_dispatch_backfills_m2_hash(
    client: AsyncClient,
    plate_mock: PlateMock,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """W21/挂账二.1:/convert 响应的 M2 构建身份 → executions.m2_hash 回填。

    整执行同源:多行也只写一次;PlateMock 的 convert 恒带 m2 身份
    (与真实 plate /convert 响应同形)。"""
    bob = await _member(client, "bob")
    await client.post(
        "/api/scenarios", headers=bob,
        json=_draft(steps=[{"id": "s1"}], vars_map={"qty": 1}),
    )
    await _seed_ds(client, bob)

    calls: list[dict] = []
    _patch_launch_capture(monkeypatch, calls)

    r = await client.post(
        "/api/runs", headers=bob, json=_run_payload())
    assert r.status_code == 201, r.text
    eid = r.json()["executionId"]
    await _wait(lambda: len(calls) >= 1)

    import sqlalchemy as sa

    from app.core import db as db_module
    from app.models import Execution

    async with db_module.SessionLocal() as s:
        ex = await s.get(Execution, eid)
        assert ex.m2_hash == "mock-m2-hash-0001"
