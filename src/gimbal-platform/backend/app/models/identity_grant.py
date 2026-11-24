"""identity_project_grants —— promotion 身份授权表(决策 1 阶段 4;
identity-registry §5「共享即授权」)。

条目本体**不拷贝**(``alias_name`` 全局唯一 + 引用键稳定决策,拷贝在
技术上就是死路):共享(私有 → 项目 promotion)引用了哪些全局身份
条目,落本表 = 「该条目已授权进该项目」的管理面事实。三消费面:

* **analyze/裁决面板**:身份条目分区(授权状态 + 账户就绪);
* **项目侧呈现**:项目配置页/就绪度面板把「共享带来的条目」标出
  (授权表 join);
* **审计**:``source_promotion_id`` 溯源(哪次共享带进来的)。

**执行解析不查授权表**(照默认口径)—— 身份按
全局注册表解析照旧,授权是纯管理面概念(可见性/呈现/审计)。将来若
要「项目只能动用被授权的身份」硬边界,在 §4 白名单叠加授权过滤即可。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base
from ._types import UtcDateTime


class IdentityProjectGrant(Base):
    __tablename__ = "identity_project_grants"
    __table_args__ = (
        # 授权幂等键:同条目同项目一行(批量 upsert 落这里)
        UniqueConstraint("identity_id", "project_id",
                         name="uq_identity_grant_identity_project"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    identity_id: Mapped[int] = mapped_column(
        ForeignKey("service_identities.id", ondelete="CASCADE"),
        nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False, index=True)
    # 溯源:哪次 promotion 带进来的(手工授权/早于本表的共享 = NULL)
    source_promotion_id: Mapped[int | None] = mapped_column(
        ForeignKey("project_promotions.id", ondelete="SET NULL"),
        nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=datetime.utcnow)
