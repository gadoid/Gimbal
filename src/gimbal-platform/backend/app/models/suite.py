"""Suite — 一组用例的管理与绑定(UPC M2:§20.6 双父同区复合 FK)。

《Suite成员层、引用分享与浏览镜头-设计方案》§6.2/§6.3 → UPC v2.10:

- **成员关系只存本表**(唯一真相源);模式配置以 JSON 存在
  ``suites.mode_config``、按 id 引用成员,不存成员清单 —— 不双写。
- **§20.6 同区约束(UPC M2 定稿)**:``suite_members`` 保留
  (suite_id, scenario_id) 主键与成员角色,新增非空 ``project_id``;
  两条复合外键 (project_id, suite_id) → suites(project_id, id) 与
  (project_id, scenario_id) → composer_scenarios(project_id, scenario_id)
  均 DEFERRABLE INITIALLY IMMEDIATE —— **取代** 0042 同区触发器与旧
  单列外键:跨区成员行直接拒绝,父对象整体移动经显式延迟后原子提交,
  只挪一端的非法提交完整回滚(AC-47)。父资产删除维持 CASCADE 收口。
- **``suites.project_id`` 为真实容器归属**(§5:NOT NULL FK;名称唯一
  从 (owner_id, name) 换轴为 ``UNIQUE(project_id, name)``)。
  ``owner_id`` 保留为审计/维护者快照(公共项目写权跟维护者走,表 B
  maintainer 谓词),不再是归属权威。不加 ON DELETE:项目删除先过
  内容闸(RESTRICT 兜底),用户删除先处置私有空间资产(§13)。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    ForeignKey, ForeignKeyConstraint, Index, Integer, String, UniqueConstraint,
)
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base
from ._types import JsonVar, UtcDateTime


class Suite(Base):
    __tablename__ = "suites"
    __table_args__ = (
        # §20:名称唯一按项目分域(替代旧 uq_suites_owner_name)
        UniqueConstraint("project_id", "name", name="uq_suites_project_name"),
        # §20.6 复合 FK 目标候选键(非延迟)
        Index("uq_suites_project_id", "project_id", "id", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(String(512), default="")
    # 审计/维护者快照(归属权威是 project_id;公共项目写权 = 维护者,
    # 表 B maintainer 谓词)。不加 ON DELETE:未处置的用户删不掉(§13)。
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), index=True)
    # 真实容器归属(§5:NOT NULL FK;普通项目资产 / 私有空间资产)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"), nullable=False, index=True)
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
    """suite 成员行:PK (suite_id, scenario_id) + 非空 project_id 校验键。

    §20.6(UPC M2 定稿):同区约束由两条**复合外键**表达
    (project_id, suite_id) → suites(project_id, id) 与
    (project_id, scenario_id) → composer_scenarios(project_id, scenario_id),
    均 DEFERRABLE INITIALLY IMMEDIATE、ON DELETE CASCADE(父资产删除
    成员行自收)。跨区写入直接拒绝;父对象整体移动经显式延迟后原子
    提交;只挪一端的非法提交完整回滚。旧单列外键与 0042 同区触发器
    随 0068 退役 —— 复合边是唯一事实源。"""

    __tablename__ = "suite_members"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "suite_id"], ["suites.project_id", "suites.id"],
            ondelete="CASCADE", onupdate="NO ACTION",
            name="fk_suite_members_suite_zone",
            deferrable=True, initially="IMMEDIATE",
        ),
        ForeignKeyConstraint(
            ["project_id", "scenario_id"],
            ["composer_scenarios.project_id",
             "composer_scenarios.scenario_id"],
            ondelete="CASCADE", onupdate="NO ACTION",
            name="fk_suite_members_scenario_zone",
            deferrable=True, initially="IMMEDIATE",
        ),
        # 反查「场景在哪些 suite」(§6.3;场景详情反查与级联提示的驱动面)
        Index("ix_suite_members_scenario", "scenario_id"),
    )

    suite_id: Mapped[int] = mapped_column(
        Integer, primary_key=True)
    scenario_id: Mapped[str] = mapped_column(
        String(128), primary_key=True)
    # §20.6 非空同区校验键(与套件行一致;由创建路径从套件写入)
    project_id: Mapped[int] = mapped_column(Integer, nullable=False)
    # 成员角色(重构方案约束 1,推翻 P2 设计 §6.1):main/before/after;
    # 前置/后置也是成员 —— 同区约束经成员表单一真相源覆盖
    role: Mapped[str] = mapped_column(String(16), default="main")
    # 组跑的默认顺序(§6.6:按 sort 遍历)
    sort: Mapped[int] = mapped_column(Integer, default=0)
    added_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now())
