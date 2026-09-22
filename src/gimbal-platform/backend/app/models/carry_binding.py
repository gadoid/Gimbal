"""carry 值层存储(spec §3.1):服务绑定表 + 全局默认表。

null 语义(写死):行存在即声明注入,value=NULL 注入 JSON null(显式空);
行不存在才是"未配置",走降级链。配置页 placeholder 依赖此语义。
值统一存 str(模板 ${var.x} 原样),注入时按契约 type 宽松转换。
"""
from __future__ import annotations

from datetime import datetime

from ._types import UtcDateTime
from sqlalchemy import ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base


class CarryServiceBinding(Base):
    __tablename__ = "carry_service_bindings"
    __table_args__ = (
        UniqueConstraint("service_name", "field_path", name="uq_carry_svc_path"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # 绑定键取值域 = base 目录服务名 ∪ 别名全名(配套方案 §2.3 放宽)。
    # 读侧必须归一:别名键按 derive_base 解析到 base,与 carry_injection
    # 的三层链(精确别名键 > base 服务键 > 全局默认)同构;写侧整表
    # 替换按原始键操作。历史注释「目录服务名,非用户引用键」已废止。
    service_name: Mapped[str] = mapped_column(String(128))
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
    __tablename__ = "carry_global_defaults"
    __table_args__ = (
        UniqueConstraint("field_path", name="uq_carry_default_path"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
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
