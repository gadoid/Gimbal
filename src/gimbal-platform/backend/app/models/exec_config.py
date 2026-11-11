"""ExecConfig model —— 执行配置(执行配置与运行方案分层-设计方案 §4)。

执行配置管「在哪、以谁、带什么业务参数」:场景的外部支撑,跨场景
共享 → 挂人/组。一套默认 + 若干命名;子配置按系统分组内联 carry
覆盖(决策 7 内联式,独立 carry 套装对象已撤销)。

**零凭证值、零地址值**(§4 薄束性质):凭证由池按 (system, env,
slot) 解析、地址由部署表按 (目录服务, env) 解析,本表只存引用键
—— 槽位是名字,跨区可移植(「商户B@UAT」私有区跑解析个人池、
项目里跑解析项目池,引用不用换)。

scope 两型同构:``'user' | 'project'``(v1 只落 user,project 随
组级批次 ⑧);(scope, scope_id) 同 carry_binding 的通用维度口径
(无 FK)。同 scope 内 name 唯一;默认配置至多一行(部分唯一索引,
置默认由路由原子切换)。environment_id SET NULL:环境删除后配置
存活,环境链回落下一位(与 projects.default_environment_id 同款)。
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
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base
from ._types import JsonVar, UtcDateTime


class ExecConfig(Base):
    __tablename__ = "exec_configs"
    __table_args__ = (
        UniqueConstraint("scope", "scope_id", "name",
                         name="uq_exec_configs_scope_name"),
        # 默认配置每 scope 至多一行(环境/绑定的链位②/④载体)
        Index("uq_exec_configs_default", "scope", "scope_id", unique=True,
              postgresql_where=text("is_default")),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    scope: Mapped[str] = mapped_column(String(16), default="user")
    scope_id: Mapped[int] = mapped_column(Integer, index=True)
    name: Mapped[str] = mapped_column(String(64))
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false"))
    # 环境链位②/④的承载(可空 = 不设置,链跳过此位)
    environment_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("environments.id", ondelete="SET NULL"),
        nullable=True)
    # {"systems": [{"service": 目录服务名,
    #               "bindings": {身份面(别名全名): 槽位名},
    #               "carryOverrides": {字段: 值}}]}
    # (bindings 覆盖槽位解析序的配置层;carryOverrides 值内联,
    #  null = 显式注入 JSON null,与 carry_store 语义同型)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JsonVar, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now(), onupdate=func.now())
