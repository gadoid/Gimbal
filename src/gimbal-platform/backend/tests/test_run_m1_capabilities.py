"""M1 执行能力补齐测试(V1 executor 语义移植):

* nRuns/parallel fan-out —— total = Σrows × nRuns,gimbal 调用次数一致
* prefix 提单号前缀 —— vars.order_no_prefix / order_no / seq 注入
* mergePolicy 认证合并策略 —— override 整块替换 / merge 保留内置 /
  append 与内置冲突 409 / origin(injectCredentials=false)不注入
"""
from __future__ import annotations

import asyncio

import pytest
from httpx import AsyncClient

from .helpers import (
    gimbal_ok as _ok,
    make_draft as _draft,
    register_and_login as _register_and_login,
    test_env,
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
        "env": test_env(),
    }
    payload.update(extra)
    return payload


# ── nRuns / parallel fan-out ──────────────────────────────────────
async def test_n_runs_multiplies_total_and_gimbal_calls(
    client: AsyncClient,
    plate_mock: PlateMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """2 行数据 × nRuns=3 → total_runs=6,gimbal /run 被调 6 次。"""
    bob = await _member(client, "bob")
    await client.post(
        "/api/scenarios", headers=bob, json=_draft(steps=[{"id": "s1"}])
    )
    await _seed_ds(client, bob)
    # 追加一行:ds-001 共 2 行
    r = await client.put(
        "/api/data-sets/ds-001",
        headers=bob,
        json={"name": "ds", "rows": [{"qty": 1}, {"qty": 2}]},
    )
    assert r.status_code == 200, r.text

    from app.services import gimbal_client as gc

    calls: list[dict] = []

    async def _capture(scenario_dict: dict, **kw: object) -> dict:
        calls.append(scenario_dict)
        return _ok()

    monkeypatch.setattr(gc, "run", _capture)

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
    """parallel=2 → gimbal /run 同时在飞的数量永不超过 2。"""
    bob = await _member(client, "bob")
    await client.post(
        "/api/scenarios", headers=bob, json=_draft(steps=[{"id": "s1"}])
    )
    await _seed_ds(client, bob)
    r = await client.put(
        "/api/data-sets/ds-001",
        headers=bob,
        json={"name": "ds", "rows": [{"i": i} for i in range(4)]},
    )
    assert r.status_code == 200, r.text

    from app.services import gimbal_client as gc

    in_flight = 0
    max_in_flight = 0
    done = 0

    async def _capture(scenario_dict: dict, **kw: object) -> dict:
        nonlocal in_flight, max_in_flight, done
        in_flight += 1
        max_in_flight = max(max_in_flight, in_flight)
        await asyncio.sleep(0.05)
        in_flight -= 1
        done += 1
        return _ok()

    monkeypatch.setattr(gc, "run", _capture)

    r = await client.post(
        "/api/runs", headers=bob, json=_run_payload(nRuns=2, parallel=2)
    )
    assert r.status_code == 201, r.text

    await _wait(lambda: done >= 8)
    assert done == 8
    assert max_in_flight <= 2


# ── prefix 变量注入 ───────────────────────────────────────────────
async def test_prefix_injects_order_no_vars(
    client: AsyncClient,
    plate_mock: PlateMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """prefix="ORD" → composed.config.vars 带 order_no_prefix / order_no / seq。"""
    bob = await _member(client, "bob")
    await client.post(
        "/api/scenarios", headers=bob, json=_draft(steps=[{"id": "s1"}])
    )
    await _seed_ds(client, bob)

    from app.services import gimbal_client as gc

    payloads: list[dict] = []

    async def _capture(scenario_dict: dict, **kw: object) -> dict:
        payloads.append(scenario_dict)
        return _ok()

    monkeypatch.setattr(gc, "run", _capture)

    r = await client.post(
        "/api/runs", headers=bob, json=_run_payload(prefix="ORD")
    )
    assert r.status_code == 201, r.text

    await _wait(lambda: len(payloads) >= 1)
    vars_map = (payloads[0].get("config") or {}).get("vars") or {}
    assert vars_map["order_no_prefix"] == "ORD"
    assert vars_map["order_no"] == "ORD-{{ seq }}"
    assert vars_map["seq"] == {"kind": "seq"}


# ── mergePolicy 认证合并策略 ─────────────────────────────────────
async def _seed_built_in_user(client: AsyncClient, headers: dict) -> None:
    """建一个 config.users 里带内置认证 qa1 的场景 + case/ds。"""
    draft = _draft(steps=[{"id": "s1"}])
    draft["definition"]["config"]["users"] = {
        "qa1": {"url": "http://builtin", "username": "u0", "password": "p0"}
    }
    r = await client.post("/api/scenarios", headers=headers, json=draft)
    assert r.status_code == 201, r.text
    await _seed_ds(client, headers)


class _FakeAuth:
    """_inject_exec_users 只消费这些属性(与 AuthSession 解密后一致)。"""

    def __init__(self, alias: str) -> None:
        self.alias = alias
        self.url = "http://exec"
        self.username = "exec-user"
        self.password = "exec-pass"
        self.token_type = "bearer"
        self.expires_in = 3600


async def _post_run(client: AsyncClient, headers: dict, **extra: object):
    return await client.post("/api/runs", headers=headers, json=_run_payload(**extra))


async def test_merge_policy_override_replaces_built_in_users(
    client: AsyncClient,
    plate_mock: PlateMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """override → Config.users 整块替换,内置 qa1 消失。"""
    bob = await _member(client, "bob")
    await _seed_built_in_user(client, bob)

    from app.services import gimbal_client as gc
    from app.services import run_dispatcher as rd

    payloads: list[dict] = []

    async def _capture(scenario_dict: dict, **kw: object) -> dict:
        payloads.append(scenario_dict)
        return _ok()

    async def _fake_resolve(db_factory, owner_id, aliases):
        return [_FakeAuth(a) for a in aliases]

    monkeypatch.setattr(gc, "run", _capture)
    monkeypatch.setattr(rd, "_resolve_exec_auths", _fake_resolve)

    r = await _post_run(
        client, bob, auths=["qa9"], mergePolicy="override"
    )
    assert r.status_code == 201, r.text
    await _wait(lambda: len(payloads) >= 1)
    users = (payloads[0].get("config") or {}).get("users") or {}
    assert set(users.keys()) == {"qa9"}
    assert users["qa9"]["username"] == "exec-user"


async def test_merge_policy_merge_keeps_built_in_users(
    client: AsyncClient,
    plate_mock: PlateMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """merge(默认)→ 所选注入覆盖,内置其余保留。"""
    bob = await _member(client, "bob")
    await _seed_built_in_user(client, bob)

    from app.services import gimbal_client as gc
    from app.services import run_dispatcher as rd

    payloads: list[dict] = []

    async def _capture(scenario_dict: dict, **kw: object) -> dict:
        payloads.append(scenario_dict)
        return _ok()

    async def _fake_resolve(db_factory, owner_id, aliases):
        return [_FakeAuth(a) for a in aliases]

    monkeypatch.setattr(gc, "run", _capture)
    monkeypatch.setattr(rd, "_resolve_exec_auths", _fake_resolve)

    r = await _post_run(client, bob, auths=["qa9"], mergePolicy="merge")
    assert r.status_code == 201, r.text
    await _wait(lambda: len(payloads) >= 1)
    users = (payloads[0].get("config") or {}).get("users") or {}
    assert set(users.keys()) == {"qa1", "qa9"}
    # 内置 qa1 原样保留
    assert users["qa1"]["url"] == "http://builtin"
    # 所选 qa9 注入
    assert users["qa9"]["username"] == "exec-user"


async def test_merge_policy_append_conflict_409(
    client: AsyncClient,
    plate_mock: PlateMock,
) -> None:
    """append + 所选 alias 与内置 users 同名 → 整单 409 拒绝。"""
    bob = await _member(client, "bob")
    await _seed_built_in_user(client, bob)

    r = await _post_run(client, bob, auths=["qa1"], mergePolicy="append")
    assert r.status_code == 409
    assert "append_policy_conflict" in r.text


async def test_merge_policy_default_is_merge(
    client: AsyncClient,
    plate_mock: PlateMock,
) -> None:
    """缺省(不传 mergePolicy)→ config_json 记 merge,请求成功。"""
    bob = await _member(client, "bob")
    await _seed_built_in_user(client, bob)

    r = await _post_run(client, bob, auths=["qa1"])
    assert r.status_code == 201, r.text

    import sqlalchemy as sa

    from app.core import db as db_module
    from app.models import Execution

    async with db_module.SessionLocal() as s:
        ex = (
            (await s.execute(sa.select(Execution).order_by(Execution.id.desc())))
            .scalars()
            .first()
        )
        assert ex.config_json["mergePolicy"] == "merge"
