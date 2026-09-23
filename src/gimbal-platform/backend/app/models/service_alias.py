"""ServiceAlias model — 服务别名注册表(服务画像方案 §4.1/§5.3)。

别名是「配置的最小锚点」的显式登记:命名规则复用编排引擎既有的
``<服务名>-<后缀>`` 识别(``derive_base``,最后一个 ``-`` 切分、前缀
必须落在 Plate 目录内)—— 本表只是把隐式推导变成可管理的登记面,
不新起一套匹配规则。

* ``alias_name`` PK;``base_service`` 由 ``derive_base`` 派生,冗余存
  一份便于按服务聚合查询(目录改名会漂移,读侧以派生为准);
* ``credential_alias`` 引用**执行者本人** auth_sessions.alias(owner
  隔离池,方案 §4.1 拍板)—— 同一别名行被不同人执行时各拿各的凭证;
* ``owner_user_id`` 非空 = 个人默认,空 = 团队共享;
* ``carry_profile_ref``(取值集引用)按挂起清单 §5.6 不建列 —— 别名级
  carry 差异用 ``carry_bindings`` 别名键直接落(CarryServiceBinding 的
  service_name 本就是自由字符串,稀疏覆盖语义在 carry_injection 合并)。
"""
from __future__ import annotations

from datetime import datetime

from ._types import UtcDateTime
from sqlalchemy import ( ForeignKey, Index, String, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base


class ServiceAlias(Base):
    __tablename__ = "service_aliases"
    __table_args__ = (
        # 服务信息管理页按服务聚合的查询面
        Index("ix_service_alias_base", "base_service"),
    )

    alias_name: Mapped[str] = mapped_column(String(128), primary_key=True)
    base_service: Mapped[str] = mapped_column(String(128))
    # 环境级端点默认层(2026-09-23 批次 F4 方案 B):物化优先级链
    # 「显式绑定 > 场景声明 > 本列 > 缺口引擎报错」的第三层。NULL =
    # 该别名不提供 URL 默认,行为与加列前完全一致。别名表是 base_url
    # 的唯一权威(服务器迁移一处改),不在前端/场景 payload 冗余存。
    base_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # 横向分组标签(环境只是常见用法之一);可空 = 未分组
    group_tag: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # 引用认证管理的凭证;可空 = 不绑,执行时走场景显式绑定/无凭证
    credential_alias: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # 非空 = 个人默认,空 = 团队共享;用户注销时置空(共享化)
    # NO ACTION DEFERRABLE —— 显式推翻模型旧注释「注销时置空(共享化)」
    # (PG迁移方案第八轮第 3 条):FK 从未生效、该意图从未执行过,且
    # 「注销即共享化」该由人显式决定;不处置就删号当场报错(处置见
    # 权限方案 §4.3,P1a 保守默认=删除)。
    owner_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="NO ACTION", deferrable=True, initially="DEFERRED"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now(), onupdate=func.now()
    )
