"""AccountCombo model —— 账户组合(账户组合设计方案 §4.1,定稿 05)。

组合 = 一组**服务 → 已登记身份条目**的映射(``payload.entries``:
``[{service, alias}]``,alias = ``ServiceIdentity.alias_name``,一条一
服务),跨场景复用的**基础默认**身份层:场景经 ``definition.config.
accountCombo`` 引用(服务端托管键,§4.2),执行时各装配面把组合条目
垫底进既有绑定合并(组合永远垫底,不重排任何面内覆盖序)。

**组合是注册表的纯引用集**:不存 envId(条目自带环境)、不存账户
(条目引用账户)、不存地址与明文、不存凭证池 —— 池仍由
``credentialSource`` 链决定(组合零池规则,§3.4)。scope 管「谁能治理
这份映射」,与池两维正交。

scope 两型同构:``'user' | 'project'``;(scope, scope_id) 同
``exec_configs`` 的通用维度口径(无 FK)。同 scope 内 name 唯一;默认
组合每 (scope, scope_id) 至多一行(部分唯一索引,语义 = 「推荐默认」
—— 新建场景预选,不静默自动写入)。

``revision`` 仅条目(entries)变化 +1(改名/描述等元数据只动
updated_at + 审计)—— 执行快照与订阅指纹记录 id+name+revision 溯源。
``updated_by_id`` 项目组合多成员改动溯源(个人组合 = 属主自身)。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base
from ._types import JsonVar, UtcDateTime


class AccountCombo(Base):
    __tablename__ = "account_combos"
    __table_args__ = (
        UniqueConstraint("scope", "scope_id", "name",
                         name="uq_account_combos_scope_name"),
        # 默认组合每 scope 至多一行(「推荐默认」:新建场景预选用,
        # 不静默自动写入绑定 —— 置默认由路由原子切换)
        Index("uq_account_combos_default", "scope", "scope_id", unique=True,
              postgresql_where=text("is_default")),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    scope: Mapped[str] = mapped_column(String(16), default="user")
    # (scope, scope_id) 通用维度,同 exec_configs:无 FK(组合行先于
    # 项目删除内容闸拦截,成员行随项目 CASCADE,不悬空)
    scope_id: Mapped[int] = mapped_column(Integer, index=True)
    name: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(Text, default="")
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false"))
    # {"entries": [{"service": 目录服务名, "alias": 身份条目名}]}
    # —— 一条一服务;条目校验复用 validate_binding_aliases(保存面),
    # 组合自身新增码只留形状/重复类(account_combo_entry_invalid)。
    payload: Mapped[dict[str, Any]] = mapped_column(
        JsonVar, nullable=False, default=dict)
    # 仅条目变化 +1;溯源用(执行快照与订阅指纹记录 id+name+revision)
    revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1"))
    # 项目组合多成员改动溯源;成员删除不牵连(SET NULL,名字快照在审计)
    updated_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now(), onupdate=func.now())
