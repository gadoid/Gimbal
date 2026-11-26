"""UPC-03(M1):项目可见性与授权关系解析(v2.10 §6)。

三件事,项目列表(GET /projects)、/auth/me、详情与 context、对象读取
全部同源,AC-51 对照的就是这里:

* :func:`visible_projects_clause` —— SQL 可见性谓词(单点):
  private 属主 ∨ normal 成员 ∨ public。**无 Admin+ 全量旁路** —— 平台
  管理员不因平台角色看见他人私有空间(§6 授权矩阵:「Private 其他
  用户(含平台管理员)」全否;§15 /auth/me、/projects 按授权过滤)。
* :func:`project_relation` —— 关系解析:Owner 是所有权关系(owner_id),
  Admin 是授权角色(成员行);同一事实不重复存储。
* :func:`effective_permissions` —— 主体 × 容器的有效权限投影(§9
  ProjectContext.effectivePermissions);能力开关(§7 矩阵)由
  :mod:`app.policies` 独立求值,二者相乘才是最终判定,此处不重复登记。

对象级权限(场景/套件 CRUD)仍走 routers/_ownership.py 表 B,M2
资源迁移时统一收编;本模块先立项目级口径。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from ..models.project import Project, ProjectMember
from . import zone


def visible_projects_clause(viewer_id: int) -> ColumnElement[bool]:
    """项目可见性 SQL 谓词 —— 列表、/auth/me、详情与对象可见性同源。

    private: 仅所有者可见(默认拒绝;委托授权是未来扩展,§4 可见性行);
    normal:  成员可见(角色任一);
    public:  全员可见(平台授权范围,§6)。
    """
    my_memberships = select(ProjectMember.project_id).where(
        ProjectMember.user_id == viewer_id)
    return or_(
        and_(Project.kind == Project.KIND_PRIVATE,
             Project.owner_id == viewer_id),
        Project.id.in_(my_memberships),
        Project.kind == Project.KIND_PUBLIC,
    )


async def can_view_project(
    db: AsyncSession, user_id: int, project: Project,
) -> bool:
    """对象级可见判定 —— 与 :func:`visible_projects_clause` 同口径(AC-51:
    列表返回的 ID 集合与逐项目读取结果一致;不可见统一 404)。"""
    if project.kind == Project.KIND_PRIVATE:
        return project.owner_id == user_id
    if project.kind == Project.KIND_PUBLIC:
        return True
    return project.id in await zone.my_project_roles(db, user_id)


def project_relation(user_id: int, project: Project,
                     my_role: str | None) -> str | None:
    """关系解析(§6):owner | member:<role> | public_reader | None。

    无关系 = 未授权(默认拒绝);平台角色(public 治理、Admin+)不是
    项目关系,由 :func:`effective_permissions` 独立叠加。"""
    if project.kind == Project.KIND_PRIVATE:
        return "owner" if project.owner_id == user_id else None
    if project.kind == Project.KIND_PUBLIC:
        return "public_reader"
    if my_role is not None:
        return f"member:{my_role}"
    return None


def effective_permissions(
    user: Any, project: Project, my_role: str | None,
) -> dict[str, bool]:
    """主体 × 容器的有效权限(§6 授权矩阵的项目级投影)。

    生命周期:status ≠ active 时新写入与新执行一律关(§13.1 归档禁止
    新写入和新执行,历史按授权可读)。平台 ops.write 只叠加公共项目
    治理(public 治理者),**不给任何私有/普通项目旁路**(§6 Control
    Plane / Data Plane 分离)。

    口径与已实现 API 对齐:归档/删除状态机端点随 M2 生命周期交付,
    本期 delete 表达「已实现删除闸的通过者」(private 属主非默认空间;
    normal 仍为平台 ops.write —— §4「授权删除」与「授权创建」同一
    授权面);archive 键随端点落地再加入,不提前许诺。
    """
    active = project.status == Project.STATUS_ACTIVE
    relation = project_relation(user.id, project, my_role)
    is_ops = getattr(user, "role", None) in ("admin", "super_admin")
    perms: dict[str, bool] = {
        "project.read": relation is not None,
        "project.update": False,
        "project.delete": False,
        "project.member.manage": False,
        "project.execute": False,
        "project.content.write": False,
        "project.credential.manage": False,
        "project.token.manage": False,
        "project.govern": False,
    }

    if project.kind == Project.KIND_PRIVATE:
        if relation == "owner":
            perms.update({
                "project.read": True,
                "project.update": True,
                # 默认空间删除受专门闸保护(§4:默认空间不得直接删除)
                "project.delete": not project.is_default,
                "project.execute": active,
                "project.content.write": active,
            })
    elif project.kind == Project.KIND_PUBLIC:
        if relation == "public_reader":
            perms["project.read"] = True
        if is_ops:  # 公共项目治理(发布/下架/公共 Carry 基线,§6/§7)
            perms.update({"project.read": True, "project.govern": True})
    else:  # normal:成员治理(§6:Admin=授权角色,与所有权无关)
        if my_role == ProjectMember.ROLE_ADMIN:
            perms.update({
                "project.read": True,
                "project.update": True,
                # §4「授权删除」= 平台授权面(与授权创建同口径)
                "project.delete": is_ops,
                "project.member.manage": True,
                "project.execute": active,
                "project.content.write": active,
                "project.credential.manage": active,
                "project.token.manage": active,
            })
        elif my_role == ProjectMember.ROLE_MEMBER:
            perms.update({
                "project.read": True,
                "project.execute": active,
                "project.content.write": active,
            })
        elif my_role == ProjectMember.ROLE_USER:
            # M2b Q1 项目用户:只读 + 执行
            perms.update({"project.read": True, "project.execute": active})
    return perms
