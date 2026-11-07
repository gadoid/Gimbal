"""项目区判定的共享上下文(M2a S1.1)。

三件小事,全部走 ``db.info`` 会话级缓存(请求内一次查询,谓词反复
求值不再打库):

* :func:`public_project_id` —— 公共项目 id(0040 种子,恰一行);
* :func:`my_project_roles` —— 主体在普通项目的角色表 ``{project_id:
  "admin"|"member"}``(公共项目不落成员行,天然不在表里 —— member /
  padmin 谓词因此不会把公共项目误当普通项目);
* :func:`apply_public` / :func:`apply_private` —— **影子写**(S1.1–
  S1.8):``visibility`` 与 ``project_id`` 必须同步翻转(public ⇔
  project_id=公共项目)。0040 迁入 + 0041 回填保证存量一致,新写入
  由这两个helper钉死;S1.9(0043)删 ``visibility`` 列后 ``apply_*``
  收敛为只写 ``project_id``。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.project import Project, ProjectMember

_INFO_PUBLIC = "zone:public_project_id"
_INFO_ROLES = "zone:project_roles:"


async def public_project_id(db: AsyncSession) -> int | None:
    """公共项目 id(None = 尚未种子,判定按「无公共项目」收口)。"""
    cached = db.info.get(_INFO_PUBLIC, "...")  # None 也是合法缓存值
    if cached != "...":
        return cached
    pid = (await db.execute(
        select(Project.id).where(Project.kind == "public"))).scalar_one_or_none()
    db.info[_INFO_PUBLIC] = pid
    return pid


async def my_project_roles(db: AsyncSession, user_id: int) -> dict[int, str]:
    """主体在普通项目的角色表(member / padmin 谓词数据源)。"""
    key = _INFO_ROLES + str(user_id)
    cached = db.info.get(key)
    if cached is not None:
        return cached
    rows = (await db.execute(
        select(ProjectMember.project_id, ProjectMember.role)
        .where(ProjectMember.user_id == user_id))).all()
    roles = {pid: role for pid, role in rows}
    db.info[key] = roles
    return roles


def apply_public(row: Any, public_pid: int | None) -> None:
    """影子写:置公共态(visibility=public ∧ project_id=公共项目)。"""
    row.visibility = "public"
    row.project_id = public_pid


def apply_private(row: Any) -> None:
    """影子写:置私有态(visibility=private ∧ project_id=NULL)。"""
    row.visibility = "private"
    row.project_id = None
