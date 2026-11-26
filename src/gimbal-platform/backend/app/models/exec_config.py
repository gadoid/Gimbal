"""ExecConfig model —— 执行配置(执行配置与运行方案分层-设计方案 §4)。

执行配置管「在哪、以谁、带什么业务参数」:场景的外部支撑,跨场景
共享 → 挂人/组。一套默认 + 若干命名;子配置按系统分组内联 carry
覆盖(内联式,独立 carry 套装对象已撤销)。

**零凭证值、零地址值**(§4 薄束性质):凭证由池按 (system, 标签,
条目) 解析、地址由部署表按 (目录服务, 标签) 解析,本表只存引用键
—— 条目名是名字,跨区可移植(「商户B@UAT」私有区跑解析个人池、
项目里跑解析项目池,引用不用换)。

scope 两型同构:``'user' | 'project'``;(scope, scope_id) 同
carry_binding 的通用维度口径(无 FK)。同 scope 内 name 唯一;默认
配置至多一行(部分唯一索引,置默认由路由原子切换)。
**执行配置不携带环境链位(ADR-0003 #21,§8.2)** —— 执行
配置不再决定执行标签(迁移 0060 删列)。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
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
        # 默认配置每 scope 至多一行(绑定的链位②载体)
        Index("uq_exec_configs_default", "scope", "scope_id", unique=True,
              postgresql_where=text("is_default")),
        # §11.2 形状闸(UPC M3,库层钉死应用配对纪律):scope 只有两型,
        # user / project;(scope, scope_id) 与 carry_binding 同通用维度
        # 口径 —— user 行 scope_id = 用户 id、project 行 = 项目 id,
        # 恒非空(路由层成对写;直写违例在提交期拒,不为第三形态留缝)。
        CheckConstraint("scope IN ('user', 'project')",
                        name="ck_exec_configs_scope"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    scope: Mapped[str] = mapped_column(String(16), default="user")
    scope_id: Mapped[int] = mapped_column(Integer, index=True)
    name: Mapped[str] = mapped_column(String(64))
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false"))
    # {"systems": [{"service": 目录服务名,
    #               "aliases": [圈定调用身份条目名],
    #               "bindings": {身份面(别名全名): 条目名},
    #               "carryOverrides": {字段: 值}}],
    #  "description": 说明文本(≤2048), "tags": [标签(≤20 字,≤32 个)]}
    # (bindings 覆盖条目解析序的配置层;carryOverrides 值内联,
    #  null = 显式注入 JSON null,与 carry_store 语义同型;
    #  description/tags 为配置级元信息(v7,列表识别用),执行链不消费)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JsonVar, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now(), onupdate=func.now())
