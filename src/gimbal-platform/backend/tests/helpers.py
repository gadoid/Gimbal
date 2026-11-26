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
        "/api/auth/login", json={"username": username, "password": password},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def role_headers(
    client: AsyncClient,
    username: str,
    *,
    role: str = "user",
    password: str = "x",
) -> dict[str, str]:
    """直插指定角色用户并登录 → Bearer 头(authz T0.1 公共入口)。

    取代散在各测试文件的私有提权 helper(``_register_role`` /
    ``_admin_headers``):直插不经注册面,免「首注自动管理员」的注册
    顺序依赖。直插原语仍是 ``inbound_fixtures.mk_user``(幂等)。
    """
    from .inbound_fixtures import mk_user

    await mk_user(username, role=role)
    return await login_user(client, username, password)


def make_draft(
    scenario_id: str = "sc-test",
    *,
    steps: list | None = None,
    vars_map: dict | None = None,
    plate: dict | None | object = None,
    **meta_over: Any,
) -> dict:
    """Minimal plate-valid ScenarioDraft container (meta via ``meta_over``).

    ``vars_map`` 声明 config.vars(P2/C1 数据集行键须 ⊆ 标量声明变量);
    缺省不写 vars,保持旧调用行为不变。

    M3 定稿:步骤锚点 = ``step.endpoint``。历史种子写在
    ``call.view_hints.endpoint_id`` 的,这里统一上提为 step.endpoint
    并剥离 view_hints —— 存量测试不必逐个改。
    """
    if steps:
        steps = [_lift_view_hints(dict(st)) for st in steps]
    meta = {
        "scenarioId": scenario_id,
        "name": "Test",
        "module": "order",
        "priority": 1,
        "system": ["fin"],
    }
    meta.update(meta_over)
    # C-2(2026-10-13)保存端强制声明:缺省为锚定系统 ∪ meta.system 补
    # "working" 声明(与未声明同语义:预览执行);显式传 plate=dict 用之;
    # plate=False 表示刻意不声明(测保存闸本身的用例)。
    if plate is None and "plate" not in meta_over:
        systems = {
            *(str(st.get("endpoint", "")).split(".")[0]
              for st in (steps or [])
              if isinstance(st, dict) and st.get("endpoint")
              ),
            *(str(s) for s in meta.get("system", [])),
        }
        systems.discard("")
        if systems:
            meta["plate"] = {s: "working" for s in sorted(systems)}
    elif isinstance(plate, dict):
        meta["plate"] = plate
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


def _lift_view_hints(step: dict) -> dict:
    """call.view_hints.endpoint_id → step.endpoint(就地,幂等)。"""
    call = step.get("call")
    if isinstance(call, dict) and "view_hints" in call:
        vh = call.pop("view_hints")
        eid = vh.get("endpoint_id") if isinstance(vh, dict) else None
        if eid and not step.get("endpoint"):
            step["endpoint"] = eid
    return step


def launch_ok() -> "Any":
    """A passing case result (per-row counters all green; LaunchResult
    形态与 server 链 SSE 归一同源,B6③ 后引擎为执行器 server 实例)。"""
    from app.services.gimbal_launcher import LaunchResult

    return LaunchResult(launch_status="ok", exit_code=0, total=1, passed=1)


async def seed_legacy_users(sid: str, users: dict) -> None:
    """凭证治理 §3.5 铺底件(2026-11-20 落闸后):新建不再收明文
    config.users —— 直写行 payload 注入,模拟 §7 存量行(带明文快照
    基座的老场景:保存闸放行存量、W6 属主基座语义照常覆盖)。
    """
    from sqlalchemy import select as sa_select

    from app.core import db as db_module
    from app.models.composer_scenario import ComposerScenario

    async with db_module.SessionLocal() as s:
        row = (await s.execute(sa_select(ComposerScenario).where(
            ComposerScenario.scenario_id == sid))).scalar_one()
        payload = dict(row.payload or {})
        defn = dict(payload.get("definition") or {})
        cfg = dict(defn.get("config") or {})
        cfg["users"] = users
        defn["config"] = cfg
        payload["definition"] = defn
        row.payload = payload
        await s.commit()


async def wait_until(
    predicate: Callable[[], bool], timeout_s: float = 5.0, interval: float = 0.05,
    msg: str = "",
) -> None:
    """Poll ``predicate`` until true;**超时抛 TimeoutError**(C-5,2026-10-13)。

    此前超时静默返回 —— 断言"某事没有发生"或断言写得宽松的用例会变成
    空断言(等待形同虚设)。测"预期不发生"的用例请用显式 sleep + 反断言,
    不要借 wait_until 的静默超时。
    """
    deadline = asyncio.get_event_loop().time() + timeout_s
    while asyncio.get_event_loop().time() < deadline:
        if predicate():
            return
        await asyncio.sleep(interval)
    raise TimeoutError(
        f"wait_until: {timeout_s}s 内条件未满足"
        f"{' — ' + msg if msg else ''} "
        f"[{getattr(predicate, '__qualname__', predicate)!r}]")


FK_ADMIN_PASSWORD = "FkAdmin-Pw-123"


async def ensure_fk_users(db: Any, *ids: int, make_admin: int | None = None) -> None:
    """垫底 FK 用户:直插 owner_id=N 的业务行前保证 users.id=N 存在。

    PG(M2 起)强制 FK —— 直插业务行前不垫 users 会以 IntegrityError
    落马(且被 create 的契约掩码成 scenario_id_exists)。
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
            role="super_admin" if admin else "user",
            is_active=True,
        ))
        # UPC §4:垫底用户同事务配默认私有空间(库层延迟约束钉死
        # 「非系统用户至少一个默认空间」)
        from app.services.project_space import (
            ensure_default_private_project,
        )

        await ensure_default_private_project(db, uid)
    await db.commit()
    if db.get_bind().dialect.name == "postgresql":
        await db.execute(text(
            "SELECT setval(pg_get_serial_sequence('users', 'id'),"
            " GREATEST((SELECT COALESCE(MAX(id), 1) FROM users), 1))"
        ))
        await db.commit()


async def seed_deployment(db: Any, base_service: str, url: str,
                          *, env_id: int | None = None) -> int:
    """authz M2a S6:地址只来自部署表 —— 在 ``env_id``(缺省 = 默认环境,
    不存在则建一个)下登记 ``base_service → url``。返回环境 id。调用方
    负责 commit。"""
    from sqlalchemy import select

    from app.models import Deployment, Environment

    if env_id is None:
        env_id = (await db.execute(select(Environment.id).where(
            Environment.is_default.is_(True)))).scalar()
        if env_id is None:
            env = Environment(name="test-default", is_default=True)
            db.add(env)
            await db.flush()
            env_id = env.id
    hit = (await db.execute(select(Deployment).where(
        Deployment.base_service == base_service,
        Deployment.env_id == env_id))).scalar_one_or_none()
    if hit is None:
        db.add(Deployment(base_service=base_service, env_id=env_id,
                          base_url=url))
    else:
        hit.base_url = url
    await db.flush()
    return env_id


async def seed_service_runtime(
    service: str, *, env_name: str = "测试",
    url: str = "https://runtime.internal",
) -> int:
    """M3 §8.5 派发硬门布景(无身份场景):默认环境 + 主档 + 部署行,
    全幂等 —— 标签链空时 ③ 层按平台默认环境部署表取地址。返回环境 id。"""
    from app.core import db as db_module
    from app.models import Environment

    async with db_module.SessionLocal() as db:
        from sqlalchemy import select as _sel
        env = (await db.execute(_sel(Environment.id).where(
            Environment.name == env_name))).scalar_one_or_none()
        if env is None:
            db.add(Environment(name=env_name, is_default=True))
            await db.flush()
            env = (await db.execute(_sel(Environment.id).where(
                Environment.name == env_name))).scalar_one()
        # 只建环境+部署行(deployments.base_service 无 FK):主档行会
        # 让「服务不在 plate 目录」类用例经主档解析成功,改变被测语义
        await seed_deployment(db, service, url, env_id=env)
        await db.commit()
        return env


# ── UPC M1 布景守卫(v2.10 §4/§20)─────────────────────────────────────

NIGHT_ADMIN = "upc_night_admin"
"""布景专用项目管理员:库层不变量「活跃普通项目 ≥1 有效 admin」要求
项目出生即有管理员;测试主角保持原角色,守夜人只满足不变量。"""


async def scenario_project_id(db, scenario_id: str) -> int:
    """父场景的容器归属(UPC M2 直插方案行:project_id 从父场景派生,
    §20.2 冗余校验键)。"""
    from sqlalchemy import select

    from app.models.composer_scenario import ComposerScenario

    return int((await db.execute(select(
        ComposerScenario.project_id).where(
        ComposerScenario.scenario_id == scenario_id))).scalar_one())


async def default_space_id(db, user_id) -> int:
    """用户的默认私有空间 id(UPC M2 直插布景:对象表 project_id NOT NULL,
    私有区内容挂所有者默认空间 —— 经注册/建号/直插用户入口必然存在)。"""
    from sqlalchemy import select

    from app.models.project import Project

    pid = (await db.execute(select(Project.id).where(
        Project.kind == "private", Project.is_default.is_(True),
        Project.owner_id == user_id))).scalar_one()
    return int(pid)


async def mk_user_with_space(username: str, *, role: str = "user") -> int:
    """直插用户 + 默认私有空间(§4:非系统用户须有默认空间,延迟约束
    触发器在提交时兜底)。经 inbound_fixtures.mk_user 单点。"""
    from .inbound_fixtures import mk_user

    return await mk_user(username, role=role)


async def mk_normal_project(name: str, members: dict[str, str]) -> int:
    """直插普通项目 + 成员 {username: role}。

    UPC §20 布景守卫:活跃普通项目须至少一名有效 admin(延迟约束触发
    器在提交时钉死)—— 成员表无 admin 时自动补守夜人,不改变测试
    主角的角色与断言。项目与首名成员同一事务提交(顺序无关)。"""
    from sqlalchemy import select as sa_select

    from app.core import db as db_module
    from app.models.project import Project, ProjectMember
    from app.models.user import User

    members = dict(members)
    if not any(r == ProjectMember.ROLE_ADMIN for r in members.values()):
        await mk_user_with_space(NIGHT_ADMIN)
        members.setdefault(NIGHT_ADMIN, ProjectMember.ROLE_ADMIN)
    async with db_module.SessionLocal() as db:
        proj = Project(name=name, kind="normal", description="")
        db.add(proj)
        await db.flush()
        for uname, role in members.items():
            uid = (await db.execute(sa_select(User.id).where(
                User.username == uname))).scalar_one()
            db.add(ProjectMember(project_id=proj.id, user_id=uid,
                                 role=role))
        await db.commit()
        return proj.id


async def add_project_admin(db, project_id: int) -> None:
    """在**同一提交内**给刚建的普通项目补守夜人 admin(§20 延迟约束:
    活跃普通项目出生即须有有效 admin —— 先建项目再补的布景会被提交
    拒绝,须与项目行同事务)。守夜人经独立会话先就位,不干扰当前事务。"""
    from sqlalchemy import select as sa_select

    from app.models.project import ProjectMember
    from app.models.user import User

    await mk_user_with_space(NIGHT_ADMIN)
    uid = (await db.execute(sa_select(User.id).where(
        User.username == NIGHT_ADMIN))).scalar_one()
    db.add(ProjectMember(project_id=project_id, user_id=uid,
                         role=ProjectMember.ROLE_ADMIN))
