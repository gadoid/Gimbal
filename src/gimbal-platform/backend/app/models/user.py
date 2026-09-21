"""User model。

M2(PG迁移方案 §2.2 / 权限方案 §1.2):
* ``password_hash`` 放宽 TEXT(bcrypt 密文长度随密码变,PG 的 VARCHAR
  会真报错);
* ``display_name`` 补 partial unique(``<> ''`` —— 列默认空串,普通唯一
  索引会让两个未设昵称的用户相撞);应用层 ``_name_checks`` 的
  username↔display_name 双向查重不能撤(DB 表达不了跨列双向唯一);
* ``users.role``(M2.5 权威翻转后进 models):取值
  ``member | operator | admin``,**权威**;``is_admin`` 保留一个过渡版本
  (应用写侧镜像 = role=='admin',M6 删列)。取值域见权限方案 §1;
  role 不进 JWT —— 每请求查库,升降级即时生效。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        # 未设昵称(空串)不参与唯一 —— 与应用层查重跳过空值的语义一致
        Index(
            "uq_users_display_name",
            "display_name",
            unique=True,
            sqlite_where=text("display_name <> ''"),
            postgresql_where=text("display_name <> ''"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(128), default="")
    password_hash: Mapped[str] = mapped_column(Text)
    # 三级单角色(权限方案 §1):member | operator | admin —— 权威。
    # 取值约束在应用层(UserPatchIn 的 Literal),DB 不设 CHECK 以免
    # 预留值空间被方言差异锁死(§8「superadmin 真出现再加」)。
    # (is_admin 过渡镜像列已随 M6-3 删除;API 字面由 UserPublic 派生)
    role: Mapped[str] = mapped_column(String(16), default="member")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
