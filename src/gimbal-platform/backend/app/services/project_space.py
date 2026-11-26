"""UPC M1:项目容器生命周期服务(§4 私有空间 / §13 用户处置)。

私有空间是真实 Project 容器(UPC-01):每个非系统用户恰一个默认
空间(注册/建号/迁移三入口同事务创建,延迟约束触发器兜底),可另建
多个非默认空间(名称在所有者域内唯一)。所有权由 ``owner_id`` 表达,
不落成员行 —— Owner 是所有权关系,Admin 是授权角色(§6)。
"""
from __future__ import annotations

from sqlalchemy import delete, func, select
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


async def dispose_private_containers(db: AsyncSession, user_id: int) -> int:
    """用户删除处置(§13「仅处置其私有容器及主体资源」):删其私有空间。

    M1 期容器内尚无对象资源(对象表 project_id 迁移随 M2);资源迁入
    后此处置升级为依赖处置计划(§13 表:Scenario/Suite 先迁移或
    Purge)。成员行不可能存在(private 不落成员行,触发器钉死)。
    """
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
