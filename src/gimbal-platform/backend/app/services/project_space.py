"""UPC M1:项目容器生命周期服务(§4 私有空间 / §13 用户处置)。

私有空间是真实 Project 容器(UPC-01):每个非系统用户恰一个默认
空间(注册/建号/迁移三入口同事务创建,延迟约束触发器兜底),可另建
多个非默认空间(名称在所有者域内唯一)。所有权由 ``owner_id`` 表达,
不落成员行 —— Owner 是所有权关系,Admin 是授权角色(§6)。
"""
from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.project import Project, ProjectMember
from ..models.user import User

# 默认空间名(所有者域内唯一,不与身份挂钩 —— 名称不是身份,§4)
DEFAULT_SPACE_NAME = "默认空间"


async def get_default_private_project(
    db: AsyncSession, user_id: int,
) -> Project | None:
    return (await db.execute(
        select(Project).where(
            Project.kind == Project.KIND_PRIVATE,
            Project.owner_id == user_id,
            Project.is_default.is_(True),
        ))).scalar_one_or_none()


async def ensure_default_private_project(
    db: AsyncSession, user_id: int, *, name: str = DEFAULT_SPACE_NAME,
) -> Project:
    """幂等保证该用户有默认私有空间(§4:并发幂等,失败事务回滚)。

    查先行挡住重复调用;真正的并发权威是部分唯一索引
    ``uq_projects_private_default``(AC-01)—— 违例在提交时以
    IntegrityError 拒绝,调用方整体回滚。
    """
    existing = await get_default_private_project(db, user_id)
    if existing is not None:
        return existing
    proj = Project(
        name=name, kind=Project.KIND_PRIVATE, owner_id=user_id,
        is_default=True, status=Project.STATUS_ACTIVE, description="",
    )
    db.add(proj)
    await db.flush()
    return proj


async def create_private_space(
    db: AsyncSession, *, owner_id: int, name: str, description: str = "",
) -> Project:
    """额外私有空间(非默认;授权创建 = 所有人可建自己的,§4)。"""
    proj = Project(
        name=name, kind=Project.KIND_PRIVATE, owner_id=owner_id,
        is_default=False, status=Project.STATUS_ACTIVE,
        description=description,
    )
    db.add(proj)
    await db.flush()
    return proj


async def dispose_private_assets(db: AsyncSession, project_ids: list[int]) -> None:
    """删除项目内容(FK 依赖序;§13「删除前生成依赖处置计划」的
    私有空间处置面):方案 → 套件成员 → 套件 → 组合 → 报告定义 →
    集成模板 → 场景(数据集/端点引用/收藏随场景显式收口)。只 flush,
    与调用方同一事务。"""
    from sqlalchemy import delete as sa_delete

    from ..models.account_combo import AccountCombo
    from ..models.composer_data_set import ComposerDataSet
    from ..models.composer_run_scheme import ComposerRunScheme
    from ..models.composer_scenario import ComposerScenario
    from ..models.integration_task import IntegrationTask
    from ..models.report_definition import ReportDefinitionRow
    from ..models.suite import Suite, SuiteMember
    from ..models.user import User as _U  # noqa: F401  user_stars CASCADE

    if not project_ids:
        return
    await db.execute(sa_delete(ComposerRunScheme).where(
        ComposerRunScheme.project_id.in_(project_ids)))
    await db.execute(sa_delete(SuiteMember).where(
        SuiteMember.project_id.in_(project_ids)))
    await db.execute(sa_delete(Suite).where(
        Suite.project_id.in_(project_ids)))
    await db.execute(sa_delete(AccountCombo).where(
        AccountCombo.project_id.in_(project_ids)))
    await db.execute(sa_delete(ReportDefinitionRow).where(
        ReportDefinitionRow.project_id.in_(project_ids)))
    await db.execute(sa_delete(IntegrationTask).where(
        IntegrationTask.project_id.in_(project_ids),
        IntegrationTask.template_id.is_(None)))
    # 场景的三个 NO ACTION 引用者先收口,再删场景本体
    from ..models.permission import UserStar
    from ..models.scenario_endpoint_ref import ScenarioEndpointRef

    scen_ids = sa_select(ComposerScenario.scenario_id).where(
        ComposerScenario.project_id.in_(project_ids)).scalar_subquery()
    await db.execute(sa_delete(ScenarioEndpointRef).where(
        ScenarioEndpointRef.scenario_id.in_(scen_ids)))
    await db.execute(sa_delete(ComposerDataSet).where(
        ComposerDataSet.scenario_id.in_(scen_ids)))
    # §20.2:方案行(含默认方案,场景创建即生)先于场景本体删除
    # —— fk_scheme_scenario_zone 为 NO ACTION
    from ..models.composer_run_scheme import ComposerRunScheme

    await db.execute(sa_delete(ComposerRunScheme).where(
        ComposerRunScheme.scenario_id.in_(scen_ids)))
    await db.execute(sa_delete(UserStar).where(
        UserStar.scenario_id.in_(scen_ids)))
    await db.execute(sa_delete(ComposerScenario).where(
        ComposerScenario.project_id.in_(project_ids)))


async def dispose_private_containers(db: AsyncSession, user_id: int) -> int:
    """用户删除处置(§13「仅处置其私有容器及主体资源」):先清空各私有
    空间内容(依赖处置计划),再删容器本身。成员行不可能存在(private
    不落成员行,触发器钉死)。"""
    pids = (await db.execute(
        select(Project.id).where(
            Project.kind == Project.KIND_PRIVATE,
            Project.owner_id == user_id))).scalars().all()
    if not pids:
        return 0
    await dispose_private_assets(db, list(pids))
    res = await db.execute(
        delete(Project).where(
            Project.kind == Project.KIND_PRIVATE,
            Project.owner_id == user_id))
    return int(res.rowcount or 0)


async def count_valid_admins(db: AsyncSession, project_id: int) -> int:
    """项目有效管理员数(与触发器 project_member_admin_invariant 同口径:
    role=admin ∧ 用户在场 ∧ is_active ∧ 非系统用户)。"""
    return (await db.execute(
        select(func.count()).select_from(ProjectMember)
        .join(User, User.id == ProjectMember.user_id)
        .where(
            ProjectMember.project_id == project_id,
            ProjectMember.role == ProjectMember.ROLE_ADMIN,
            User.is_active.is_(True),
            User.is_system.is_(False),
        ))).scalar_one()


async def projects_where_sole_valid_admin(
    db: AsyncSession, user_id: int,
) -> list[int]:
    """该用户是**唯一**有效 admin 的活跃 normal 项目(§13:最后一个
    有效管理员离职前必须交接或归档)。停用/删除用户的 409 预检数据源
    —— DB 侧延迟约束触发器(0067)是权威,这里负责把 IntegrityError
    翻译成人话 409。"""
    pids = (await db.execute(
        select(Project.id).where(
            Project.kind == Project.KIND_NORMAL,
            Project.status == Project.STATUS_ACTIVE,
            Project.id.in_(select(ProjectMember.project_id).where(
                ProjectMember.role == ProjectMember.ROLE_ADMIN,
                ProjectMember.user_id == user_id)),
        ))).scalars().all()
    return [pid for pid in pids
            if await count_valid_admins(db, pid) == 1]
