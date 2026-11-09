"""Suite — 一组用例的管理与绑定(权限域二期 P1)。

《Suite成员层、引用分享与浏览镜头-设计方案》§6.2/§6.3:
- **成员关系只存本表**(唯一真相源);模式配置以 JSON 存在
  ``suites.mode_config``、按 id 引用成员,不存成员清单 —— 不双写。
- **S1.5 同区约束取代同属主组合外键**:成员场景与套件同 project_id
  (私有区同空时同属主)—— 应用层单点 ``zone.ensure_member_same_zone``
  (422),0042 触发器兜底直插;旧组合外键与成员表冗余 ``owner_id``
  列随 0042 删除(简化 FK 保留 suite/场景删除级联)。
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
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(String(512), default="")
    # 不加 ON DELETE:未处置的用户删不掉(处置流程负责删 suite,§7.10)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), index=True)
    # visibility 列随 0043 删除(同场景口径)。
    # 项目区:空 = 私有区;同区约束(S1.5/0041)按本列判
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id"), nullable=True, index=True)
    # aggregate(默认)/chain/fanout/compose(重构方案四模式)
    mode: Mapped[str] = mapped_column(String(32), default="aggregate")
    # 按 id 引用成员的模式配置,不存成员清单(§6.2 不双写)
    mode_config: Mapped[dict] = mapped_column(JsonVar, default=dict)
    # 乐观锁(重构方案:composition 整体保存带 rev,冲突 409);
    # 任何改动成员或编排的路径都要推进
    rev: Mapped[int] = mapped_column(Integer, default=0)
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
    """suite 成员行:PK (suite_id, scenario_id)。

    S1.5 起同区约束取代旧同属主组合外键:成员场景与套件同
    ``project_id``(私有区同空时同属主)—— 应用层单点
    ``zone.ensure_member_same_zone``(422),DB 触发器(0042)兜底直插;
    旧组合外键与冗余 ``owner_id`` 列随 0042 删除。简化 FK 保留级联
    (suite/场景删除时成员行自收;scenario 侧 DEFERRED 配合删除顺序)。"""

    __tablename__ = "suite_members"
    __table_args__ = (
        ForeignKeyConstraint(
            ["suite_id"], ["suites.id"],
            ondelete="CASCADE", name="fk_suite_members_suite_id",
        ),
        ForeignKeyConstraint(
            ["scenario_id"], ["composer_scenarios.scenario_id"],
            ondelete="CASCADE", deferrable=True, initially="DEFERRED",
            name="fk_suite_members_scenario_id",
        ),
        # 反查「场景在哪些 suite」(§6.3;场景详情反查与级联提示的驱动面)
        Index("ix_suite_members_scenario", "scenario_id"),
    )

    suite_id: Mapped[int] = mapped_column(
        Integer, primary_key=True)
    scenario_id: Mapped[str] = mapped_column(
        String(128), primary_key=True)
    # 成员角色(重构方案约束 1,推翻 P2 设计 §6.1):main/before/after;
    # 前置/后置也是成员 —— 同区约束经成员表单一真相源覆盖
    role: Mapped[str] = mapped_column(String(16), default="main")
    # 组跑的默认顺序(§6.6:按 sort 遍历)
    sort: Mapped[int] = mapped_column(Integer, default=0)
    added_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now())
