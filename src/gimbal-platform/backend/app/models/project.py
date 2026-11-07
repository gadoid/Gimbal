"""项目区(M2a S1):私有区 + 若干项目,其中一个是特殊的公共项目。

区模型收敛(m2a-plan 2026-11-08):三区收敛为「私有区 + 若干项目」,
公共区整体成为 ``kind='public'`` 的公共项目 —— 全员只读(表 A/B 派生),
Admin+(ops.write)是它的项目管理员;carry 不再有独立全局层,现在的
全局默认值 = 公共项目的项目层(S4)。

- ``Project``:kind ∈ {normal, public};``kind='public'`` 恰一行
  (部分唯一索引钉死,公共项目不可建不可删)。``created_by`` 可空
  —— 公共项目行由 0040 迁移种子,指向 ``__platform__`` 系统用户。
- ``ProjectMember``:**公共项目不落成员行** —— 全员只读、Admin+ 为
  项目管理员都由表 A 派生(避免每个新用户写一行);普通项目里
  role=admin 为项目管理员(成员管理、padmin 谓词)。
- 对象表的 ``project_id``(场景 / suite / 集成模板行 / 报告定义):
  空 = 私有区;``executions.project_id`` 是派发时快照(无 FK,对齐
  ``suite_id`` 先例:台账不随对象删除消失)。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    ForeignKey, Index, Integer, String, Text, func, text,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base
from ._types import UtcDateTime


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        # 公共项目恰一行:部分唯一索引(DB 层钉死「不可再建公共项目」)
        Index("uq_projects_public_kind", "kind", unique=True,
              postgresql_where=text("kind = 'public'")),
        Index("ix_projects_kind", "kind"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    # normal | public(公共项目恰一行,见上)
    kind: Mapped[str] = mapped_column(String(16), default="normal")
    description: Mapped[str] = mapped_column(Text, default="")
    # 建项目的人(S1-g:Admin+);公共项目行指 __platform__,可空防御
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now())


class ProjectMember(Base):
    """普通项目的成员行;公共项目不落行(见模块注释)。"""

    # 成员角色常量(比较单点:角色字面量守卫的清零终态不回退 ——
    # 用户角色字面量在表 A/表 B,成员角色只在模型常量)
    ROLE_ADMIN = "admin"
    ROLE_MEMBER = "member"

    __tablename__ = "project_members"
    __table_args__ = (
        # 「我的项目」反查(/auth/me.projects、visibility_clause)
        Index("ix_project_members_user", "user_id"),
    )

    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    # admin(项目管理员)| member;S1.1 的 padmin / member 谓词数据源
    role: Mapped[str] = mapped_column(String(16), default="member")
    added_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    added_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now())
