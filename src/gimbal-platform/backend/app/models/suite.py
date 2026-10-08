"""Suite — 一组用例的管理与绑定(权限域二期 P1)。

《Suite成员层、引用分享与浏览镜头-设计方案》§6.2/§6.3:
- **成员关系只存本表**(唯一真相源);模式配置以 JSON 存在
  ``suites.mode_config``、按 id 引用成员,不存成员清单 —— 不双写。
- **组合外键是唯一的安全设计点**:suite 里只能放属主自己的场景,
  由库层保证、admin 也不例外;应用层先校验返回 404(不泄露存在性),
  库约束兜底(绕过应用层直写也会被拒)。
- **约束延迟到提交时检查**(DEFERRABLE INITIALLY DEFERRED),配合
  离职转让路径:suite / 场景 / 成员表三处 owner_id 同一事务改写,
  单独转让 suite 内某一个场景会被提交拒绝,迫使处置整体进行。
- **``suites.owner_id`` 不加 ON DELETE**:用户在处置完成前删不掉,
  作为「必须先走处置」的兜底(§7.10)。
- visibility 与场景同口径;P1 无 suite 发布入口(恒 private,
  发布联动随 P2)。mode P1 只有 aggregate,mode_config 恒 {}。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    ForeignKey, ForeignKeyConstraint, Index, Integer, String,
)
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base
from ._types import JsonVar, UtcDateTime


class Suite(Base):
    __tablename__ = "suites"
    __table_args__ = (
        # 同属主组名不重(§6.3)
        Index("uq_suites_owner_name", "owner_id", "name", unique=True),
        # 组合外键目标:成员表 FK 引用 (id, owner_id)
        Index("uq_suites_id_owner", "id", "owner_id", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(String(512), default="")
    # 不加 ON DELETE:未处置的用户删不掉(处置流程负责删 suite,§7.10)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), index=True)
    # 与场景同口径;P1 恒 private(发布入口随 P2)
    visibility: Mapped[str] = mapped_column(String(16), default="private")
    # aggregate(默认)/1:N/拼接/地图…;P1 只有 aggregate
    mode: Mapped[str] = mapped_column(String(32), default="aggregate")
    # 按 id 引用成员的模式配置,不存成员清单(§6.2 不双写)
    mode_config: Mapped[dict] = mapped_column(JsonVar, default=dict)
    # 副本溯源(P2 的 suite 深拷贝使用;handoff 已有同名字段则复用)
    forked_from_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    forked_from_owner_name: Mapped[str | None] = mapped_column(
        String(128), nullable=True)
    forked_from_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now(), onupdate=func.now())


class SuiteMember(Base):
    """suite 成员行:PK (suite_id, scenario_id);owner_id 为组合外键的
    冗余属主列 —— 与 suite 属主、场景属主三方一致由库层钉死。"""

    __tablename__ = "suite_members"
    __table_args__ = (
        # 组合外键(§6.3 安全设计点):成员必须属于 suite 属主自己的
        # 场景;CASCADE = suite/场景删除时成员行自收;DEFERRED 配合
        # 转让路径的三表同事务 owner 改写。
        ForeignKeyConstraint(
            ["suite_id", "owner_id"],
            ["suites.id", "suites.owner_id"],
            ondelete="CASCADE", deferrable=True, initially="DEFERRED",
            name="fk_suite_members_suite",
        ),
        ForeignKeyConstraint(
            ["scenario_id", "owner_id"],
            ["composer_scenarios.scenario_id", "composer_scenarios.owner_id"],
            ondelete="CASCADE", deferrable=True, initially="DEFERRED",
            name="fk_suite_members_scenario",
        ),
        # 反查「场景在哪些 suite」(§6.3;场景详情反查与级联提示的驱动面)
        Index("ix_suite_members_scenario", "scenario_id"),
    )

    suite_id: Mapped[int] = mapped_column(
        Integer, primary_key=True)
    scenario_id: Mapped[str] = mapped_column(
        String(128), primary_key=True)
    # 冗余属主列(组合外键用;与 suite.owner_id / 场景.owner_id 一致)
    owner_id: Mapped[int] = mapped_column(Integer)
    # 组跑的默认顺序(§6.6:按 sort 遍历)
    sort: Mapped[int] = mapped_column(Integer, default=0)
    added_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now())
