"""标签解析链 + 地址第 ③ 层(redesign §8.2)。

**标签**(= 轻量部署标签,``environments`` 表):解析链 =
**有效调用身份标签 > 项目默认 > 平台默认**。

* 有效身份 = 换用后实际取用的身份条目名集(执行配置 slot_map /
  行级 ``@slot`` 覆盖由调用方归并后传入);身份条目的 ``env_id``
  即其标签;
* 多身份标签不一致 → :class:`EnvMixed`(混拼,dispatch 映射 409
  ``env_mixed``,无逃生口 —— 显式 ``environmentId`` 注入通道不复存在,
  ADR-0003 #13/#21);
* 无身份/身份无标签 → 项目默认(``projects.default_environment_id``)
  → 平台默认(``environments.is_default``);全空 → :data:`NO_ENV`
  (预检 ``env_unspecified`` 根因);
* 旧链位(方案环境 / 执行配置环境 / 个人偏好 / 本次显式)与
  :class:`EnvironmentNotFound` 已退役(ADR-0003 #21);``EnvChoice``
  形状不变,派发仍落 ``config_json``(重跑按快照回放,历史 source
  原样透出)。

**地址 ③**(数据源;优先级裁决仍在 ``run_materialize._apply_services``):
服务键先映射到基础服务(条目表 ``base_service``,非条目名即自身),
再查部署表 ``deployments[(base_service, 标签)]``。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.deployment import Deployment
from ..models.environment import Environment
from ..models.project import Project


class EnvMixed(Exception):
    """有效身份的部署标签不一致(混拼 —— 预检/派发硬拦截)。"""

    def __init__(self, entries: dict[str, int]) -> None:
        # 条目名 → 标签 id(展示按名排序,报错稳定)
        self.entries = dict(sorted(entries.items()))
        pairs = "、".join(
            f"{alias}(标签#{env_id})" for alias, env_id in self.entries.items())
        super().__init__(
            f"env_mixed: 有效身份的部署标签不一致:{pairs} —— "
            "同一次执行的地址/登录口/版本线必须落同一标签;请统一这些"
            "身份条目的标签,或改用项目/平台默认")


@dataclass(frozen=True)
class EnvChoice:
    """标签链解析结果:``env_id`` 可空(全链皆空 = 无 ③ 层)。

    ``source`` ∈ ``identity | project | default``;历史快照里的
    ``explicit/scheme/exec_config/...`` 仅出现在重放回放面,原样透出。
    """
    env_id: int | None = None
    source: str | None = None

    @classmethod
    def from_snapshot(cls, snap: dict | None) -> "EnvChoice | None":
        """配方/快照 → 选择(缺键 / 空 = None,即无 ③)。"""
        if not snap or snap.get("environmentId") is None:
            return None
        return cls(int(snap["environmentId"]), snap.get("environmentSource"))

    def snapshot(self) -> dict:
        """``config_json`` 落档形态(无标签时空 dict,键缺席)。"""
        if self.env_id is None:
            return {}
        return {"environmentId": self.env_id,
                "environmentSource": self.source}


NO_ENV = EnvChoice()


async def resolve_execution_tag(
    db: AsyncSession,
    *,
    identity_names: Iterable[str] | None = None,
    project_id: int | None = None,
) -> EnvChoice:
    """按链路取本次执行的部署标签:**身份 > 项目默认 > 平台默认**。

    ``identity_names`` = 换用后实际取用的身份条目名集(调用方归并
    slot_map / 行级覆盖后的取用集合);条目缺行(悬空名)不参与标签
    判定 —— 它们在凭证解析里另有 missing 分类,不在这里连坐。
    """
    names = {n for n in (identity_names or ()) if n}
    if names:
        from ..models.service_identity import ServiceIdentity

        rows = (await db.execute(
            select(ServiceIdentity.alias_name, ServiceIdentity.env_id)
            .where(ServiceIdentity.alias_name.in_(names)))).all()
        entries = dict(rows)
        tags = set(entries.values())
        if len(tags) == 1:
            return EnvChoice(tags.pop(), "identity")
        if len(tags) > 1:
            raise EnvMixed(entries)
    if project_id is not None:
        pid = (await db.execute(select(Project.default_environment_id).where(
            Project.id == project_id))).scalar()
        if pid is not None:
            return EnvChoice(pid, "project")   # FK SET NULL:非空即存在
    default = (await db.execute(select(Environment.id).where(
        Environment.is_default.is_(True)))).scalar()
    if default is not None:
        return EnvChoice(default, "default")
    return NO_ENV


async def instance_lines(db: AsyncSession, env_id: int | None) -> dict[str, str]:
    """标签的版本线声明(重构 §1.2:版本线在 ``system_env_instances.line``,
    ADR-0003 #17;空 = 未声明)。"""
    if env_id is None:
        return {}
    from ..models.system_env_instance import SystemEnvInstance

    rows = (await db.execute(select(
        SystemEnvInstance.system, SystemEnvInstance.line).where(
        SystemEnvInstance.env_id == env_id))).all()
    return {s: ln for s, ln in rows if ln}


async def deployment_urls(
    db: AsyncSession, raw_names: list[str], env_id: int,
) -> dict[str, str]:
    """服务键 → 该标签部署地址(命中才出现;基名解析切条目表)。"""
    if not raw_names:
        return {}
    from ..models.service_identity import ServiceIdentity

    alias_base = dict((await db.execute(
        select(ServiceIdentity.alias_name, ServiceIdentity.base_service).where(
            ServiceIdentity.alias_name.in_(raw_names)))).all())
    base_of = {n: (alias_base.get(n) or n) for n in raw_names}
    rows = dict((await db.execute(
        select(Deployment.base_service, Deployment.base_url).where(
            Deployment.env_id == env_id,
            Deployment.base_service.in_(set(base_of.values()))))).all())
    return {n: rows[b] for n, b in base_of.items() if rows.get(b)}
