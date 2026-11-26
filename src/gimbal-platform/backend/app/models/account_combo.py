"""AccountCombo 模型 —— 账户组合(UPC-02 / 账户组合 v4 §4.1、v2.10 §5)。

组合 = 一组**服务 → 已登记身份条目**的映射(``payload.entries``:
``[{service, alias}]``,alias = ``ServiceIdentity.alias_name``,一条一
服务),跨场景、跨方案复用的**基础默认**身份层:运行方案经显式列
``composer_run_schemes.account_combo_id`` 引用(§20.2 —— 唯一持久化
事实源,JSON payload 不再保存绑定)。

**组合是注册表的纯引用集**:不存 envId(条目自带环境)、不存账户
(条目引用账户)、不存地址与明文、不存凭证池 —— 池仍由
``credentialSource`` 链决定(组合零池规则,v4 §3.3)。归属是真实
容器 ``project_id``(§5:NOT NULL FK;v4 的 (scope, scope_id) 多态
归属随 UPC 收敛为单列,公共项目不建组合 —— §7 能力矩阵)。

* 项目内名称唯一(§20 ``UNIQUE(project_id, name)``);
* 每项目至多一个默认组合(部分唯一索引;语义 = 「推荐默认」——
  新建/另存方案预选,不静默自动写入绑定);
* ``(project_id, id)`` 候选键(§20.2 复合 FK 的目标,非延迟);
* ``revision`` 仅条目(entries)变化 +1(改名/描述只动 updated_at +
  审计)—— 执行快照与订阅指纹记录 id+name+revision 溯源;
* ``updated_by_id`` 项目组合多成员改动溯源。

引用中的组合不可直接删除(§5.1;删除保护在服务层 409
``account_combo_in_use``,引用统计直接查方案显式列,不扫 payload)。
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
        # 项目内名称唯一(§20;替代 v4 的 (scope, scope_id, name))
        UniqueConstraint("project_id", "name",
                         name="uq_account_combos_project_name"),
        # §20.2 复合 FK 目标候选键(非延迟):fk_scheme_combo_zone
        Index("uq_combo_project_id", "project_id", "id", unique=True),
        # 每项目至多一个默认组合(「推荐默认」:预选不自动写)
        Index("uq_account_combos_default", "project_id", unique=True,
              postgresql_where=text("is_default")),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # 真实容器归属(§5:NOT NULL FK;不加 ON DELETE —— 项目删除先过
    # 内容闸,组合是内容的一部分)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"), nullable=False, index=True)
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
