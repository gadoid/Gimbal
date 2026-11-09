"""M2a S7.2 提升流程(私有 → 项目,D7 = 复制;Q1 = 冲突转管理员审批)。

场景 / 用例集「加入项目」:成员发起;析出分析无冲突 → 立即复制进
项目;有冲突(carry 值在两区解析不同)→ 加入申请,项目管理员逐项
裁决(保留项目层值 / 采纳原件值写入项目层),批准即以**批准那一刻**
的原件内容复制。槽位绑定不随之移动(凭证跟人走)。
"""
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base
from ._types import JsonVar, UtcDateTime


class ProjectPromotion(Base):
    __tablename__ = "project_promotions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id"), nullable=False, index=True)
    # 'scenario' | 'suite'
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    # scenario_id / str(suite.id) —— kind 判别
    source_id: Mapped[str] = mapped_column(String(128), nullable=False)
    applicant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True)
    # pending | approved | rejected | withdrawn
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", index=True)
    # 冲突清单:[{service, path, sourceValue, projectValue}]
    # (projectValue=None = 项目层缺口 —— 采纳原件值即补写)
    conflicts: Mapped[dict] = mapped_column(JsonVar, default=list)
    # 裁决结果(approved/rejected 时填):{decisions:[{service,path,use}],
    # decidedBy, decidedAt, reason}
    resolution: Mapped[dict | None] = mapped_column(
        JsonVar, nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
