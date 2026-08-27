"""Shared HTTP-layer test helpers (converged from per-file copies).

Anything exercised through the ASGI ``client`` fixture by more than one
test module belongs here instead of being copy-pasted — the copies had
already drifted once (defaults, meta fields).
"""
from __future__ import annotations

import asyncio
from typing import Any, Callable

from httpx import AsyncClient


async def register_and_login(
    client: AsyncClient,
    username: str = "alice",
    password: str = "alicepass123",
) -> dict[str, str]:
    """Register (ignoring duplicate) + login → Bearer headers."""
    await client.post(
        "/api/auth/register",
        json={"username": username, "password": password, "display_name": username},
    )
    r = await client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def make_draft(
    scenario_id: str = "sc-test",
    *,
    steps: list | None = None,
    vars_map: dict | None = None,
    **meta_over: Any,
) -> dict:
    """Minimal plate-valid ScenarioDraft container (meta via ``meta_over``).

    ``vars_map`` 声明 config.vars(P2/C1 数据集行键须 ⊆ 标量声明变量);
    缺省不写 vars,保持旧调用行为不变。
    """
    meta = {
        "scenarioId": scenario_id,
        "name": "Test",
        "module": "order",
        "priority": 1,
        "system": ["fin"],
    }
    meta.update(meta_over)
    config: dict = {"timePolicy": {"kind": "record"}}
    if vars_map is not None:
        config["vars"] = vars_map
    return {
        "definition": {
            "kind": "scenario",
            "scenarioId": scenario_id,
            "meta": meta,
            "config": config,
            "resource": {},
            "steps": steps if steps is not None else [],
        },
        "orchestration": {"steps": [], "resourceMeta": {}},
    }


def launch_ok() -> "Any":
    """A passing ``gimbal run launch`` result (per-row counters all green)."""
    from app.services.gimbal_launcher import LaunchResult

    return LaunchResult(launch_status="ok", exit_code=0, total=1, passed=1)


async def wait_until(
    predicate: Callable[[], bool], timeout_s: float = 5.0, interval: float = 0.05
) -> None:
    """Poll ``predicate`` until true or timeout (async fan-out tests)."""
    for _ in range(int(timeout_s / interval)):
        if predicate():
            return
        await asyncio.sleep(interval)
