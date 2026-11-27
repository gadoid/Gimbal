"""ExecConfig model —— 执行配置(执行配置与运行方案分层-设计方案 §4;
v2.10 §5/§11.2/§20 统一归属形状)。

执行配置管「在哪、以谁、带什么业务参数」:场景的外部支撑,跨场景
共享 → 挂人/项目。一套默认 + 若干命名;子配置按系统分组内联 carry
覆盖(内联式,独立 carry 套装对象已撤销)。

**零凭证值、零地址值**(§4 薄束性质):凭证由池按 (system, 标签,
条目) 解析、地址由部署表按 (目录服务, 标签) 解析,本表只存引用键
—— 条目名是名字,跨区可移植(「商户B@UAT」私有空间跑解析个人池、
项目里跑解析项目池,引用不用换)。

归属(§5「单表显式互斥 FK」/ §20 不变量):``principal_id`` 与
``project_id`` 恰一非空,两真实 FK + XOR CHECK —— 个人行挂主体、
项目行挂容器,禁止无外键的多态 scope 列(0069 的 (scope, scope_id)
形状随 0070 退役)。个人配置仍可在任何有权执行的项目中显式使用;
项目配置仅当前项目可用。同归属侧内 name 唯一;默认配置每侧至多
一行(部分唯一索引,置默认由路由原子切换)。
**执行配置不携带环境链位(ADR-0003 #21,§8.2)** —— 执行
配置不再决定执行标签(迁移 0060 删列)。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base
from ._types import JsonVar, UtcDateTime


class ExecConfig(Base):
    __tablename__ = "exec_configs"
    __table_args__ = (
        # §5/§20:单表显式互斥 FK —— 个人/项目恰一非空(XOR),
        # 归属类型由字段及约束明确
        CheckConstraint(
            "(principal_id IS NULL) <> (project_id IS NULL)",
            name="ck_exec_configs_owner_shape"),
        # 同侧 name 唯一(替代旧 (scope, scope_id, name) 复合唯一)
        Index("uq_exec_configs_principal_name", "principal_id", "name",
              unique=True,
              postgresql_where=text("principal_id IS NOT NULL")),
        Index("uq_exec_configs_project_name", "project_id", "name",
              unique=True,
              postgresql_where=text("project_id IS NOT NULL")),
        # 默认配置每侧至多一行(部分唯一索引;谓词须钉住本侧非空 ——
        # 单列部分唯一索引对 NULL 互不冲突,否则两侧默认可并存)
        Index("uq_exec_configs_principal_default", "principal_id",
              unique=True,
              postgresql_where=text(
                  "is_default AND principal_id IS NOT NULL")),
        Index("uq_exec_configs_project_default", "project_id",
              unique=True,
              postgresql_where=text(
                  "is_default AND project_id IS NOT NULL")),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # 个人归属(principal 语义,§3):恰与 project_id 之一非空。
    # NO ACTION(§2.1 同旧凭证行):用户/项目删除显式处置,FK 是校验器
    principal_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", name="fk_exec_configs_principal",
                   ondelete="NO ACTION"), index=True)
    # 容器归属:项目行 project_id(公共项目由创建闸拒绝,§7 能力矩阵;
    # §20「项目资源归属 NOT NULL + FK RESTRICT」+ 处置面显式清理)
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", name="fk_exec_configs_project",
                   ondelete="NO ACTION"), index=True)
    name: Mapped[str] = mapped_column(String(64))
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false"))
    # {"systems": [{"service": 目录服务名,
    #               "aliases": [圈定调用身份条目名],
    #               "bindings": {身份面(别名全名): 条目名},
    #               "carryOverrides": {字段: 值},
    #               "carryRemovals": [remove 指针(§11.4)]}],
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
