"""M1 执行能力补齐测试(V1 executor 语义移植):

* nRuns/parallel fan-out —— total = Σrows × nRuns,launch 调用次数一致
* serviceBindings 绑定注入 —— authAlias 注入 users(固定 merge 语义,
  场景内置 users 保留);prefix/mergePolicy 已随 RunRequest 收敛退役;
  env.baseUrl 补缺层已随执行环境退役(D2)

V3.2:执行 mock 从 gimbal HTTP /run 改为 ``gimbal_launcher.launch`` —
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
    payload.update(extra)
    return payload


def _patch_launch_capture(
    monkeypatch: pytest.MonkeyPatch, sink: list[dict]
) -> None:
    """把 ``gimbal_launcher.launch`` 换成读 case.json 并捕获的假实现。"""

    async def _capture(case_path, *, step_to=None, report_dir=None,
                       cwd=None, timeout=None, engine_log_path=None):
        sink.append(json.loads(Path(case_path).read_text(encoding="utf-8")))
        return _ok()

    from app.services import gimbal_launcher as gl
    monkeypatch.setattr(gl, "launch", _capture)


# ── nRuns / parallel fan-out ──────────────────────────────────────
async def test_n_runs_multiplies_total_and_gimbal_calls(
    client: AsyncClient,
    plate_mock: PlateMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """2 行数据 × nRuns=3 → total_runs=6,gimbal launch 被调 6 次。"""
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
    _patch_launch_capture(monkeypatch, calls)

    r = await client.post(
        "/api/runs", headers=bob, json=_run_payload(nRuns=3, parallel=2)
    )
    assert r.status_code == 201, r.text

    await _wait(lambda: len(calls) >= 6)
    assert len(calls) == 6

    import sqlalchemy as sa

    from app.core import db as db_module
    from app.models import Execution

    async with db_module.SessionLocal() as s:
        ex = (
            (await s.execute(sa.select(Execution).order_by(Execution.id.desc())))
            .scalars()
            .first()
        )
        assert ex.total_runs == 6
        assert ex.config_json["nRuns"] == 3
        assert ex.config_json["parallel"] == 2


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
                       cwd=None, timeout=None, engine_log_path=None):
        nonlocal in_flight, max_in_flight, done
        in_flight += 1
        max_in_flight = max(max_in_flight, in_flight)
        await asyncio.sleep(0.05)
        in_flight -= 1
        done += 1
        return _ok()

    from app.services import gimbal_launcher as gl
    monkeypatch.setattr(gl, "launch", _capture)

    r = await client.post(
        "/api/runs", headers=bob, json=_run_payload(nRuns=2, parallel=2)
    )
    assert r.status_code == 201, r.text

    await _wait(lambda: done >= 8)
    assert done == 8
    assert max_in_flight <= 2


# ── serviceBindings 绑定注入 ─────────────────────────────────────
async def _seed_built_in_user(client: AsyncClient, headers: dict) -> None:
    """建一个 config.users 里带内置认证 qa1 的场景 + case/ds。"""
    draft = _draft(steps=[{"id": "s1"}])
    draft["definition"]["config"]["users"] = {
        "qa1": {"url": "http://builtin", "username": "u0", "password": "p0"}
    }
    draft["definition"]["config"]["vars"] = {"qty": 1}  # C1:行键须 ⊆ 标量 vars
    r = await client.post("/api/scenarios", headers=headers, json=draft)
    assert r.status_code == 201, r.text
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
    """绑定 authAlias 注入 users,场景内置 users 保留(固定 merge)。"""
    bob = await _member(client, "bob")
    await _seed_built_in_user(client, bob)

    from app.services import run_dispatcher as rd

    payloads: list[dict] = []
    _patch_launch_capture(monkeypatch, payloads)

    async def _fake_resolve(db_factory, owner_id, aliases):
        return [_FakeAuth(a) for a in aliases]

    monkeypatch.setattr(rd, "_resolve_exec_auths", _fake_resolve)

    r = await _post_run(
        client, bob, serviceBindings={"svc": {"authAlias": "qa9"}}
    )
    assert r.status_code == 201, r.text
    await _wait(lambda: len(payloads) >= 1)
    users = (payloads[0].get("config") or {}).get("users") or {}
    assert set(users.keys()) == {"qa1", "qa9"}
    # 内置 qa1 原样保留
    assert users["qa1"]["url"] == "http://builtin"
    # 所选 qa9 注入
    assert users["qa9"]["username"] == "exec-user"
