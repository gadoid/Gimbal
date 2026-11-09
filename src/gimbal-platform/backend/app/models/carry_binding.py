"""carry 值层存储(spec §3.1):服务绑定表 + 全局默认表。

null 语义(写死):行存在即声明注入,value=NULL 注入 JSON null(显式空);
行不存在才是"未配置",走降级链。配置页 placeholder 依赖此语义。
值统一存 str(模板 ${var.x} 原样),注入时按契约 type 宽松转换。

authz M2a S4 作用域分层(D3 + 区模型收敛):
* scope ∈ {'project', 'user'} —— **没有独立 global**(裁定:全局默认 =
  公共项目的项目层,scope_id = 公共项目 id);
* 运行时 tier 序:公共项目层 < (项目层 ∨ 执行人个人层;普通项目区
  不吃个人层),层内沿用键层级(别名键 > 基础服务键;默认表兜底);
* ``scope_id`` 多态指向 projects.id / users.id,应用层校验,不落 FK。
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
        UniqueConstraint("scope", "scope_id", "service_name", "field_path",
                         name="uq_carry_svc_path"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # 绑定键取值域 = base 目录服务名 ∪ 别名全名(配套方案 §2.3 放宽)。
    # 读侧必须归一:别名键按 derive_base 解析到 base,与 carry_injection
    # 的层内链(精确别名键 > base 服务键 > 层默认)同构;写侧整表
    # 替换按原始键操作。
    service_name: Mapped[str] = mapped_column(String(128))
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
