"""AuthAccount model — 账户(重构 §1.4;替代 auth_sessions 的凭证行)。

账户 = 登录信息实体:密码只存一份,(pool, system, env,
username) 唯一 —— **一处改密处处生效**(领域不变式:同一账号在一个
系统上的调用都用同一份登录信息)。身份条目(service_identities)按
ref 引用本表;条目不再内嵌任何凭据。

* ``system`` = **系统名**(plate system 口径,非服务名)—— 同系统
  多服务共享登录账户(用户心智:系统 = 登录主体);原 auth_sessions
  .system 存的是服务名,迁移时经 services 主档翻译;
* ``env_id`` **必填**(登录打到具体环境实例;执行环境链兜底「平台
  默认环境」,无环境在预检期明确报,不留 env 空回退分支);
* ``username`` **明文**(String 进唯一键;敏感度 = 账号名,管理面
  本就展示;password 仍 Fernet 密文 —— 加密预算留给真正的秘密);
* ``url`` 退役:登录口上提 system_env_instances.login_url;
* ``alias``/``slot`` 退役:引用键移居身份条目;
* ``is_default`` = 每池每 (system, env) 至多一个默认账户
  (ref_mode=default 的取用位;部分唯一索引钉死);
* 归属 xor(owner_id 个人池 / project_id 项目池;项目池
  成员只见 username 不见明文,同旧语义)。

环境删除策略:条目/部署行级联,账户**不级联**(密文资产)—— 路由
删环境前检查账户引用,有则 409 提示先处置。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean, CheckConstraint, ForeignKey, Index, Integer, String, Text,
    UniqueConstraint, func, text,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base
from ._types import JsonVar, UtcDateTime


class AuthAccount(Base):
    __tablename__ = "auth_accounts"
    __table_args__ = (
        # 账户实体键:同池同系统同环境同账号恰一行(NULLS NOT DISTINCT,
        # S8 并入归属项目口径沿用)
        UniqueConstraint("owner_id", "project_id", "system", "env_id",
                         "username", name="uq_account_pool_system_env_user",
                         postgresql_nulls_not_distinct=True),
        # 每池每 system 至多一个默认账户(§8.3:
        # default 引用取 system 唯一默认;迁移 0059 重建索引)
        Index("uq_account_default", "owner_id", "project_id", "system",
              unique=True, postgresql_where=text("is_default"),
              postgresql_nulls_not_distinct=True),
        # S8 归属恰一(个人池 xor 项目池)
        CheckConstraint("(owner_id IS NULL) <> (project_id IS NULL)",
                        name="ck_account_owner_xor_project"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # NO ACTION DEFERRABLE(§2.1 同旧凭证行):删除用户显式管,FK 是校验器
    owner_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="NO ACTION",
                   deferrable=True, initially="DEFERRED"),
        index=True, nullable=True)
    project_id: Mapped[int | None] = mapped_column(
        Integer, index=True, nullable=True)
    # 系统名(plate system 口径;条目经 base_service→services.system 派生后对齐)
    system: Mapped[str] = mapped_column(String(128), nullable=False)
    env_id: Mapped[int] = mapped_column(
        ForeignKey("environments.id", ondelete="NO ACTION"), nullable=False)
    username: Mapped[str] = mapped_column(String(128), nullable=False)
    password_enc: Mapped[str] = mapped_column(Text)  # Fernet ciphertext
    token_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="Bearer",
        server_default=text("'Bearer'"))
    expires_in: Mapped[int] = mapped_column(
        Integer, nullable=False, default=7200, server_default=text("7200"))
    # 账号级字段(明文非密;F6:只能经 ${slot.X.field} 消费,键 = 引用条目名)
    account_fields: Mapped[dict] = mapped_column(
        JsonVar, nullable=False, default=dict, server_default=text("'{}'"))
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now(), onupdate=func.now())
