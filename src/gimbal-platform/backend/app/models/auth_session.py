"""AuthSession model — user-owned credential pool (Spec-2 §4.4 D).

Each AuthSession represents a target system's login that the platform
can use to mint bearer tokens at execution time.  Decoupled from any
yaml file: the platform injects ``Config.users[<slot>]`` into a temp
yaml at execution time (Spec-2-2), not at case-upload time.

Encryption: username + password are Fernet-encrypted at rest so a
database dump doesn't leak credentials.  The Fernet key is loaded
from ``settings.FERNET_KEY`` (auto-generated dev-only fallback).

authz M2a S3 — 槽位绑定:权威键 = ``(owner_id, system, env_id, slot)``
(NULLS NOT DISTINCT;env 空 = 不限环境,存量全落这层)。

- ``slot`` = 注入键 / 模板引用名(``${auth.X}`` / ``call.user=X`` /
  绑定 authAlias=X);**不可改名**(改名 = 重建,引用全断)。
- ``alias`` 保留为展示名;应用层仍按 (owner, alias) 唯一 —— 所有按名
  消费的缝(引用面板 / query_view 缓存 / drop_credential)保持无歧义。
- ``system`` = 基础服务名;``''`` = 未归类(存量推断不出/待认领)。
- ``account_fields`` = 账号级字段(orgNo/opId 等;明文非密)—— 引擎
  UserCredential 六字段 extra=forbid(F6),只能经 ``${slot.X.field}``
  在派发前解析(S4/S5 消费,S3 只存取)。
- ``is_default`` = 每槽至多一个默认(部分唯一索引):名字解析与环境
  未命中时的取用行;存量行迁移时全部置默认。

authz M2a S8 — 项目凭证:归属维度 = ``owner_id``(个人池)与
``project_id``(项目池)**恰一非空**(CHECK)。两个唯一键都并入
``project_id``(NULLS NOT DISTINCT):个人行 project_id 恒 NULL,与旧键
逐行同义;项目行 owner_id NULL → 个人面 ``owner_id == uid`` 的查询天然
排除项目行。项目凭证只有项目管理员能写,成员只能选用(无明文出口)。
"""
from __future__ import annotations

from datetime import datetime

from ._types import JsonVar, UtcDateTime
from sqlalchemy import (
    Boolean, CheckConstraint, ForeignKey, Index, Integer, String, Text,
    UniqueConstraint, func, text,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (
        # 槽位绑定键(S3;S8 并入归属项目):env/owner/project 可空进键
        # —— NULLS NOT DISTINCT(PG15+)
        UniqueConstraint("owner_id", "project_id", "system", "env_id", "slot",
                         name="uq_auth_owner_system_env_slot",
                         postgresql_nulls_not_distinct=True),
        # 每池每槽至多一个默认绑定
        Index("uq_auth_slot_default", "owner_id", "project_id", "slot",
              unique=True, postgresql_where=text("is_default"),
              postgresql_nulls_not_distinct=True),
        # S8:归属恰一(个人池 xor 项目池)
        CheckConstraint("(owner_id IS NULL) <> (project_id IS NULL)",
                        name="ck_auth_owner_xor_project"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # NO ACTION DEFERRABLE(§2.1):删除用户的处置由 Python 显式管
    # (P1a 最小显式级联随 M2 同车),FK 是校验器不是级联器。
    # S8:可空 —— 项目凭证行 owner_id NULL(归属 project_id)
    owner_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="NO ACTION", deferrable=True, initially="DEFERRED"),
        index=True, nullable=True,
    )
    # S8 项目凭证:归属项目(无 FK —— 同 Execution.project_id 快照口径,
    # baseline 不带跨表依赖;项目删除由路由显式删除项目凭证)
    project_id: Mapped[int | None] = mapped_column(
        Integer, index=True, nullable=True)
    alias: Mapped[str] = mapped_column(String(64))
    # S3:基础服务名;'' = 未归类(存量推断不出,由用户认领)
    system: Mapped[str] = mapped_column(String(128), nullable=False,
                                        default="", server_default=text("''"))
    # S3:环境维度(空 = 不限环境;存量层)
    env_id: Mapped[int | None] = mapped_column(
        ForeignKey("environments.id", ondelete="SET NULL"), nullable=True)
    # S3:槽名 = 注入键;ORM 缺省取同 INSERT 的 alias(名字兼容缝:
    # 直接构造 AuthSession(alias=X) 的调用方零改动);SQL 侧缺省 ''
    # (存量行由 0045 回填 slot=alias)
    slot: Mapped[str] = mapped_column(
        String(64), nullable=False,
        default=lambda ctx: (ctx.current_parameters.get("alias") or ""),
        server_default=text("''"))
    # S3:账号级字段(明文非密;F6:只能经 ${slot.X.field} 消费)
    account_fields: Mapped[dict] = mapped_column(JsonVar, default=dict,
                                                  server_default=text("'{}'"))
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false"))
    url: Mapped[str] = mapped_column(Text)
    username_enc: Mapped[str] = mapped_column(Text)  # Fernet ciphertext(长度随密码变)
    password_enc: Mapped[str] = mapped_column(Text)  # Fernet ciphertext(长度随密码变)
    token_type: Mapped[str] = mapped_column(String(32), default="Bearer")
    expires_in: Mapped[int] = mapped_column(Integer, default=7200)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now(), onupdate=func.now()
    )
