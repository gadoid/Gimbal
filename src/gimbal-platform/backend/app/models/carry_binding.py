"""carry 值层存储(spec §3.1;重构 2026-11-16 坐标定死 §1.7)。

null 语义(写死):行存在即声明注入,value=NULL 注入 JSON null(显式空);
行不存在才是"未配置",走降级链。值统一存 str(模板 ${var.x} 原样),
注入时按契约 type 宽松转换。

配置坐标 = (scope, env?, config_key, field_path):
* scope 分层(S4 沿用):公共项目层 < 项目层;``scope_id`` 多态指向
  projects.id / users.id,应用层校验,不落 FK;
* ``env_id`` 可空 = **全环境基线**;环境命中行覆盖基线(稀疏覆盖,
  表达力保留 —— 「全环境默认 orgNo + SIT 特例」不必复制到每环境);
* ``config_key`` 三档键域(层内解析序,**细到粗**):身份条目名 >
  服务名 > 系统名 —— 系统级配置(如 orgNo)直接挂系统键,不必复制
  到每个服务;条目键 = 旧别名键(键域兼容,存量行自动落「服务」档)。
"""
from __future__ import annotations

from datetime import datetime

from ._types import UtcDateTime
from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base


class CarryServiceBinding(Base):
    __tablename__ = "carry_service_bindings"
    __table_args__ = (
        UniqueConstraint("scope", "scope_id", "env_id", "config_key",
                         "field_path", name="uq_carry_svc_path",
                         postgresql_nulls_not_distinct=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # 配置键三档(§1.7):身份条目名 > 服务名 > 系统名。读侧按层内链
    # 归一(条目键 > 服务键 > 系统键 > 默认表);写侧整表替换按
    # (scope, config_key, env) 坐标操作。
    config_key: Mapped[str] = mapped_column(String(128))
    # 环境覆盖(空 = 全环境基线;命中覆盖基线)
    env_id: Mapped[int | None] = mapped_column(
        ForeignKey("environments.id", ondelete="SET NULL"), nullable=True)
    # S4:作用域('project'|'user';公共项目行 = 旧全局层)
    scope: Mapped[str] = mapped_column(String(16), nullable=False,
                                       default="project",
                                       server_default=text("'project'"))
    scope_id: Mapped[int] = mapped_column(Integer, nullable=False,
                                          default=0,
                                          server_default=text("0"))
    field_path: Mapped[str] = mapped_column(String(255))
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 三件套规范(§2.2):溯源列 FK SET NULL + 姓名快照
    updated_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by_name: Mapped[str] = mapped_column(String(128), default="")
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now(), onupdate=func.now()
    )


class CarryGlobalDefault(Base):
    """层默认(旧名 global_defaults 保留;S4 起全局 = 公共项目层)。"""
    __tablename__ = "carry_global_defaults"
    __table_args__ = (
        UniqueConstraint("scope", "scope_id", "field_path",
                         name="uq_carry_default_path"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    field_path: Mapped[str] = mapped_column(String(255))
    scope: Mapped[str] = mapped_column(String(16), nullable=False,
                                       default="project",
                                       server_default=text("'project'"))
    scope_id: Mapped[int] = mapped_column(Integer, nullable=False,
                                          default=0,
                                          server_default=text("0"))
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 三件套规范(§2.2):溯源列 FK SET NULL + 姓名快照
    updated_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by_name: Mapped[str] = mapped_column(String(128), default="")
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now(), onupdate=func.now()
    )
