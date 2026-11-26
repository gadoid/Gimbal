"""UPC-02(M2):运行方案行 —— 组合绑定显式列 + 修复状态(v2.10 §5/§20.2/§20.3)。

A RunScheme is the complete preparation for one execution (dataset rows +
injection entries + service bindings + run params).  Formerly embedded in
``composer_scenarios.payload.orchestration.runSchemes``; promoted to its
own table for PG-friendly relational modelling — relational dimensions
(scenario ownership, name uniqueness, default flag) as indexed columns,
the config document itself as one JSON payload.

M2(UPC)新增三组物理契约:

* **§20.2 双复合 FK** — ``project_id`` 是从父 Scenario **派生**的
  归属校验键(不是独立归属):(project_id, scenario_id) →
  composer_scenarios(project_id, scenario_id) 防冗余键与父归属不一致;
  (project_id, account_combo_id) → account_combos(project_id, id)
  (MATCH SIMPLE,允许合法空绑定)保证组合与方案**同区**(§5.1 硬同区:
  ``combo.project_id == scenario.project_id``,即使两个私有空间同属一人)。
  两组 FK 均 DEFERRABLE INITIALLY IMMEDIATE —— 专门移动/发布事务可显式
  ``SET CONSTRAINTS ... DEFERRED`` 做合法原子移动,提交时必须满足;
  旧单列 scenario FK 随 0068 退役(复合边完全覆盖)。
* **§20.3 修复状态** — ``repair_status`` ∈ {ready, blocked} +
  ``repair_reason`` ∈ {combo_missing, combo_cross_zone,
  combo_dependency_invalid},``ck_scheme_combo_repair`` 钉死合法组合;
  blocked 只能经修复命令(rebind_combo / confirm_no_combo)解除,
  普通 PATCH/复制/空绑定不得清除(§20.3 状态机)。诊断授权投影见
  services/scheme_repair —— 对外只暴露 ``scheme_repair_required`` 与
  投影后原因,内部精确原因 + 源依赖标识在受限审计/诊断表。
* **不可变 UID** — ``scheme_uid`` 服务端生成,唯一非空,禁止客户端
  指定;删除重建同名/同业务 ID 的方案是新身份(订阅按 UID 悬停,
  AC-50),与 ``projects.project_uid`` 同纪律(§13.2)。

``revision``:乐观锁(修复命令 expected_revision 原子校验 + 绑定变更
同事务递增)。JSON payload 不再持久化 ``accountComboId`` —— API 同名
DTO 字段映射到显式列,不允许双事实源(§16.1)。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean, CheckConstraint, ForeignKey, ForeignKeyConstraint, Index,
    Integer, String, Uuid, func, text,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base
from ._types import JsonVar, UtcDateTime


class ComposerRunScheme(Base):
    __tablename__ = "composer_run_schemes"
    __table_args__ = (
        Index("uq_run_scheme_scenario_name", "scenario_id", "name", unique=True),
        # 每场景恰一个默认方案(partial unique index)
        Index(
            "uq_run_scheme_default",
            "scenario_id",
            unique=True,
            postgresql_where=text("is_default IS TRUE"),
        ),
        # §20.2 第一组:方案与父场景同区(冗余校验键 + 业务 ID 复合边)
        ForeignKeyConstraint(
            ["project_id", "scenario_id"],
            ["composer_scenarios.project_id", "composer_scenarios.scenario_id"],
            name="fk_scheme_scenario_zone",
            ondelete="NO ACTION", deferrable=True, initially="IMMEDIATE",
        ),
        # §20.2 第二组:方案与组合同区(MATCH SIMPLE —— account_combo_id
        # 为 NULL 表示未绑定,是合法可选关系)
        ForeignKeyConstraint(
            ["project_id", "account_combo_id"],
            ["account_combos.project_id", "account_combos.id"],
            name="fk_scheme_combo_zone",
            ondelete="NO ACTION", deferrable=True, initially="IMMEDIATE",
        ),
        Index("ix_scheme_combo_zone", "project_id", "account_combo_id"),
        Index("ix_scheme_scenario_zone", "project_id", "scenario_id"),
        # §20.3 目标 CHECK(列定义先于约束创建):ready ⇒ 无原因;
        # blocked ⇒ 无绑定 + 原因在册。未列状态即违约。
        CheckConstraint(
            "(repair_status = 'ready' AND repair_reason IS NULL) "
            "OR (repair_status = 'blocked' AND account_combo_id IS NULL "
            "AND repair_reason IS NOT NULL AND repair_reason IN ("
            "'combo_missing', 'combo_cross_zone', 'combo_dependency_invalid'))",
            name="ck_scheme_combo_repair",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    scheme_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    # §13.2 不可复用方案身份:服务端生成,唯一非空(同 project_uid 纪律)
    scheme_uid: Mapped[str] = mapped_column(
        Uuid, nullable=False, unique=True, server_default=func.gen_random_uuid())
    # §20.2 冗余校验键:从父 Scenario 派生,两组复合 FK 钉死一致性,
    # 不存在独立修改归属的合法路径(移动/复制/发布是专门操作)
    project_id: Mapped[int] = mapped_column(Integer, nullable=False)
    scenario_id: Mapped[str] = mapped_column(String(128), nullable=False)
    # §20.2 显式绑定列:绑定的唯一持久化事实(不进 payload,§16.1)
    account_combo_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True)
    # §20.3 修复状态(默认仅用于新建;旧行按 §20.5 显式分类)
    repair_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="ready", server_default="ready")
    repair_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # 乐观锁:修复命令与绑定变更 expected_revision 原子校验(§20.3)
    revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1"))
    name: Mapped[str] = mapped_column(String(64))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    payload: Mapped[dict] = mapped_column(JsonVar, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now(), onupdate=func.now()
    )
