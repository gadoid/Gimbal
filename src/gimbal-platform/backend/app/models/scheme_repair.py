"""§20.3 Scheme 组合依赖修复:事务内审计事件 + 受限诊断记录(v2.10)。

既有审计设施(services/audit.record)是 best-effort、独立提交 —— 不满足
§20.3「状态变更与审计**同事务**提交、失败全部回滚、不允许仅日志或内存
记录」。因此修复状态流转使用专用事件表:

* :class:`SchemeRepairEvent` —— 每次状态/绑定/原因变化一行,最少记录
  §20.3 清单:old/new_status、old/new_reason、old/new_combo_id、
  源依赖标识(source_combo_ref)、解析到的目标组合及项目(resolved_*,
  如已知)、old/new_revision、action、actor、request_id、created_at。
  **历史事实,不设 FK**(审计不依赖活跃资产存在,方案/组合/用户删除后
  照常可读),不保存秘密。
* :class:`SchemeRepairDiagnosis` —— 受限持久化诊断记录(每方案一行,
  当前态):repair_reason 的精确内部原因已在方案行上,本表补「源依赖
  标识 + 解析到的目标组合/项目(如已知)」—— 诊断授权投影
  (services/scheme_repair.projected_reason)与授权后的独立诊断读取
  由此取数;普通 Scheme read 不自动授予跨区诊断读取权(§20.3)。

两表均只经修复/导入/处置领域服务写入,普通 PATCH 不落(§20.3:
普通 PATCH 不得清除阻塞,也就不产生事件)。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    ForeignKey, Index, Integer, String, Text, Uuid, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base
from ._types import UtcDateTime

# §20.3 原因码全集(判定顺序:输入可解析性 → 存在性 → 同区 → 其余
# 合法性;对外投影见 services/scheme_repair)
REASON_COMBO_MISSING = "combo_missing"
REASON_COMBO_CROSS_ZONE = "combo_cross_zone"
REASON_COMBO_DEPENDENCY_INVALID = "combo_dependency_invalid"
REASONS = (REASON_COMBO_MISSING, REASON_COMBO_CROSS_ZONE,
           REASON_COMBO_DEPENDENCY_INVALID)

# 事件动作(§20.3 状态机边):导入/处置置阻塞、修复命令、重新诊断
ACTION_IMPORT_BLOCKED = "import.blocked"      # 导入/恢复:依赖缺失置 blocked
ACTION_DISPOSAL_BLOCKED = "disposal.blocked"  # 显式资产处置导致 ready→blocked
ACTION_REBIND_COMBO = "rebind_combo"          # blocked→ready(指定合法同区组合)
ACTION_CONFIRM_NO_COMBO = "confirm_no_combo"  # blocked→ready(确认无组合)
ACTION_REDIAGNOSED = "rediagnosed"            # blocked→blocked(重新诊断原因)


class SchemeRepairEvent(Base):
    """修复状态流转的行级审计(同事务写入;历史事实,无 FK)。"""

    __tablename__ = "scheme_repair_events"
    __table_args__ = (
        # 方案时间线(诊断/审计按方案倒序取最新)
        Index("ix_scheme_repair_events_scheme", "scheme_id", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # 历史事实:不设 FK —— 方案删除后审计照常可读(§20.3)
    scheme_id: Mapped[str] = mapped_column(String(128), nullable=False)
    # 不可复用方案身份快照(方案删除后仍可定位历史,AC-50 同纪律)
    scheme_uid: Mapped[str] = mapped_column(Uuid, nullable=False)
    project_id: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    old_status: Mapped[str | None] = mapped_column(String(16))
    new_status: Mapped[str | None] = mapped_column(String(16))
    old_reason: Mapped[str | None] = mapped_column(String(32))
    new_reason: Mapped[str | None] = mapped_column(String(32))
    old_combo_id: Mapped[int | None] = mapped_column(Integer)
    new_combo_id: Mapped[int | None] = mapped_column(Integer)
    old_revision: Mapped[int | None] = mapped_column(Integer)
    new_revision: Mapped[int | None] = mapped_column(Integer)
    # 源依赖标识(受授权的审计诊断数据,不作为活跃 FK,不保存秘密)
    source_combo_ref: Mapped[str | None] = mapped_column(Text)
    resolved_combo_id: Mapped[int | None] = mapped_column(Integer)
    resolved_project_id: Mapped[int | None] = mapped_column(Integer)
    # 变更理由/请求关联(修复命令 caller 提供或导入包标识)
    reason: Mapped[str | None] = mapped_column(Text)
    request_id: Mapped[str | None] = mapped_column(String(128))
    # 系统导入用明确系统主体;actor 删除后审计照常可读 → 不设 FK
    actor_id: Mapped[int | None] = mapped_column(Integer)
    actor_name: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now())


class SchemeRepairDiagnosis(Base):
    """受限持久化诊断记录(每方案一行,当前态;投影数据源,§20.3)。"""

    __tablename__ = "scheme_repair_diagnosis"

    scheme_id: Mapped[str] = mapped_column(
        String(128), primary_key=True)
    # 源依赖标识(导入包带来的原组合身份/引用,如已知)
    source_combo_ref: Mapped[str | None] = mapped_column(Text)
    # 解析到的目标组合及项目(如已知;组合不存在/不可解析则 NULL)
    resolved_combo_id: Mapped[int | None] = mapped_column(Integer)
    resolved_project_id: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now(), onupdate=func.now())
