"""环境链 + 地址第 ③ 层(authz M2a S2.1)。

**环境**:本次显式 > 方案 > 项目默认 > 个人偏好 > 默认环境(D2,Admin
指定)> 无。:func:`resolve_environment` 产出 :class:`EnvChoice`(环境
id + 来源),派发时落 ``config_json``(重跑按快照回放)。

**地址 ③**(数据源;优先级裁决仍在 ``run_materialize._apply_services``):
服务键先映射到基础服务(别名行的 ``base_service``,非别名即自身,
D11),再查部署表 ``deployments[(base_service, env)]``。S6 起部署表是
唯一来源(别名自带 ``base_url`` 与影子期合并分支已随 0047 退役)。
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.composer_scenario import ComposerScenario
from ..models.deployment import Deployment
from ..models.environment import Environment
from ..models.permission import UserPref
from ..models.project import Project
from ..models.service_alias import ServiceAlias

# 个人偏好键(user_preferences 白名单同名;值 = 环境 id)
PREF_KEY = "run.environment"

class EnvironmentNotFound(LookupError):
    """本次显式指定的环境不存在(调用方映射 422)。"""

    def __init__(self, env_id: int) -> None:
        super().__init__(f"environment not found: {env_id}")
        self.env_id = env_id


@dataclass(frozen=True)
class EnvChoice:
    """环境链解析结果:``env_id`` 可空(全链皆空 = 旧行为)。"""
    env_id: int | None = None
    source: str | None = None

    @classmethod
    def from_snapshot(cls, snap: dict | None) -> "EnvChoice | None":
        """配方/快照 → 选择(缺键 / 空 = None,即无 ③)。"""
        if not snap or snap.get("environmentId") is None:
            return None
        return cls(int(snap["environmentId"]), snap.get("environmentSource"))

    def snapshot(self) -> dict:
        """``config_json`` 落档形态(无环境时空 dict,键缺席)。"""
        if self.env_id is None:
            return {}
        return {"environmentId": self.env_id,
                "environmentSource": self.source}


NO_ENV = EnvChoice()


async def _exists(db: AsyncSession, env_id: int) -> bool:
    return (await db.execute(select(Environment.id).where(
        Environment.id == env_id))).scalar() is not None


def _as_env_id(value) -> int | None:
    """偏好/方案里的环境值容错解析(非正整数 → 无)。"""
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str) and value.isdigit() and int(value) > 0:
        return int(value)
    return None


async def resolve_environment(
    db: AsyncSession,
    *,
    explicit: int | None = None,
    scheme_env=None,
    project_id: int | None = None,
    user_id: int | None = None,
) -> EnvChoice:
    """按链路取第一个有效环境。

    显式指定的环境不存在 → :class:`EnvironmentNotFound`(调用方要的是
    「我选的环境」,静默落到下一位会让用户以为生效了);方案 / 项目 /
    偏好里悬空的环境(环境被删)视同未设置,落到下一位。
    """
    if explicit is not None:
        if not await _exists(db, explicit):
            raise EnvironmentNotFound(explicit)
        return EnvChoice(explicit, "explicit")
    sid = _as_env_id(scheme_env)
    if sid is not None and await _exists(db, sid):
        return EnvChoice(sid, "scheme")
    if project_id is not None:
        pid = (await db.execute(select(Project.default_environment_id).where(
            Project.id == project_id))).scalar()
        if pid is not None:
            return EnvChoice(pid, "project")   # FK SET NULL:非空即存在
    if user_id is not None:
        raw = (await db.execute(select(UserPref.value).where(
            UserPref.user_id == user_id,
            UserPref.key == PREF_KEY))).scalar()
        if isinstance(raw, dict):   # 偏好白名单形状 {environmentId}
            raw = raw.get("environmentId")
        uid_env = _as_env_id(raw)
        if uid_env is not None and await _exists(db, uid_env):
            return EnvChoice(uid_env, "preference")
    default = (await db.execute(select(Environment.id).where(
        Environment.is_default.is_(True)))).scalar()
    if default is not None:
        return EnvChoice(default, "default")
    return NO_ENV


async def resolve_for_scenario(
    db: AsyncSession,
    scenario_id: str | None,
    *,
    user_id: int | None,
    explicit: int | None = None,
    scheme_env=None,
) -> EnvChoice:
    """场景执行面的便捷入口:项目默认按场景所属项目取。"""
    project_id = None
    if scenario_id:
        project_id = (await db.execute(select(
            ComposerScenario.project_id).where(
                ComposerScenario.scenario_id == scenario_id))).scalar()
    return await resolve_environment(
        db, explicit=explicit, scheme_env=scheme_env,
        project_id=project_id, user_id=user_id)


async def deployment_urls(
    db: AsyncSession, raw_names: list[str], env_id: int,
) -> dict[str, str]:
    """服务键 → 该环境部署地址(命中才出现)。"""
    if not raw_names:
        return {}
    alias_base = dict((await db.execute(
        select(ServiceAlias.alias_name, ServiceAlias.base_service).where(
            ServiceAlias.alias_name.in_(raw_names)))).all())
    base_of = {n: (alias_base.get(n) or n) for n in raw_names}
    rows = dict((await db.execute(
        select(Deployment.base_service, Deployment.base_url).where(
            Deployment.env_id == env_id,
            Deployment.base_service.in_(set(base_of.values()))))).all())
    return {n: rows[b] for n, b in base_of.items() if rows.get(b)}
