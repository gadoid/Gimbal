"""carry 值层存储(spec §3.1;重构 2026-11-16 坐标定死 §1.7)。

null 语义(写死):行存在即声明注入,value=NULL 注入 JSON null(显式空);
行不存在才是"未配置",走降级链。值统一存 str(模板 ${var.x} 原样),
注入时按契约 type 宽松转换。

配置坐标 = (scope, config_key, field_path):
* scope 分层(S4 沿用):公共项目层 < 项目层;``scope_id`` 多态指向
  projects.id / users.id,应用层校验,不落 FK;
* **环境维已退役(2026-11-17,redesign §8.4)**:环境只做轻量部署标签,
  不再承载 carry 配置层 —— 多服务共享一层配置时同名字段必然打架;
  需要「同服务不同部署不同值」时挂实例(服务×环境),不回到环境层。
  原 ``env_id`` 覆盖行生产为 0,迁移 0058 直接删除;
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
        UniqueConstraint("scope", "scope_id", "config_key", "field_path",
                         name="uq_carry_svc_path"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # 配置键三档(§1.7):身份条目名 > 服务名 > 系统名。读侧按层内链
    # 归一(条目键 > 服务键 > 系统键 > 默认表);写侧整表替换按
    # (scope, config_key) 坐标操作。
    config_key: Mapped[str] = mapped_column(String(128))
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
