"""plate 目录版本戳(派生层,spec §3.3)。synced_at 只在适配批次完成时推进。

spec_json:戳所指版本的完整 plate full spec(字段形状缓存)—— 字段级
diff 的"旧形状"基准;冷启动首见 endpoint 自动落基线(spec §5.1)。
派生缓存,可随时重拉 plate 重建。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base
from ._types import JsonVar


class CatalogVersion(Base):
    __tablename__ = "catalog_versions"

    endpoint_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    # 唯一经 DB 生成的时刻(§2.1 风险 2 的破口):timestamptz 下 PG 的
    # now() 存绝对时间,不再随会话时区漂移。
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    spec_json: Mapped[dict] = mapped_column(JsonVar, nullable=False, default=dict)
