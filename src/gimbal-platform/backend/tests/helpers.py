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


async def login_user(
    client: AsyncClient, username: str, password: str
) -> dict[str, str]:
    """Login only (no register) → Bearer headers."""
    r = await client.post(
        "/api/auth/login", json={"username": username, "password": password}
    )
    assert r.status_code == 200, r.text
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


FK_ADMIN_PASSWORD = "FkAdmin-Pw-123"


async def ensure_fk_users(db: Any, *ids: int, make_admin: int | None = None) -> None:
    """垫底 FK 用户:直插 owner_id=N 的业务行前保证 users.id=N 存在。

    SQLite 默认不强制 FK,PG(M2 起)强制 —— 同一批测试在 PG 上会以
    IntegrityError 落马(且被 create 的契约掩码成 scenario_id_exists)。
    存在即跳过(先注册后插的测试路径不受影响,不挪自增序);PG 显式
    id 插入后把序列推到 max 之后,后续 API 注册不再撞号。

    ``make_admin=N``:把 id=N 的垫底用户造成**可登录的 admin**(密码
    ``FK_ADMIN_PASSWORD``)。垫了用户后「首个 API 注册者自动 admin」
    失效 —— 需要 admin 身份调 admin-only 路由的测试改用它登录
    (``login_user(client, "fkuser1", FK_ADMIN_PASSWORD)``)。
    """
    from sqlalchemy import select, text

    from app.models import User

    if not ids:
        return
    existing = set(
        (await db.execute(select(User.id).where(User.id.in_(ids)))).scalars()
    )
    from app.core.security import hash_password

    for uid in ids:
        if uid in existing:
            continue
        admin = make_admin == uid
        db.add(User(
            id=uid, username=f"fkuser{uid}", display_name="",
            password_hash=(hash_password(FK_ADMIN_PASSWORD) if admin else "x"),
            role="admin" if admin else "member",
            is_active=True,
        ))
    await db.commit()
    if db.get_bind().dialect.name == "postgresql":
        await db.execute(text(
            "SELECT setval(pg_get_serial_sequence('users', 'id'),"
            " GREATEST((SELECT COALESCE(MAX(id), 1) FROM users), 1))"
        ))
        await db.commit()
