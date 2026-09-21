"""BoardCard model — 接口线索板的自建卡(服务画像方案 §3.3/§5.3)。

「卡只有一种(自建卡),root 是一个唯一槽位」:
* ``quadrant`` 恒有值(requirement/data/test/topology)——root 卡在槽位
  期间仍保留所属象限,降级时自动回到那里(方案:「原来占槽位的那张
  自动降回它所属象限」);
* ``is_root`` 唯一性由双方言 partial unique index 保证(先例:
  ``composer_run_schemes.uq_run_scheme_default``);
* ``subject_kind`` 当前只有 ``endpoint``(方案 §5.3 留扩展位);
* 权限边界 = 作者(``author_id``):作者可编辑/降级/删除,他人只读。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Index, String, Text, func, text,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base

QUADRANTS = ("requirement", "data", "test", "topology")


class BoardCard(Base):
    __tablename__ = "board_cards"
    __table_args__ = (
        Index("ix_board_cards_subject", "subject_kind", "subject_id"),
        # 每主体恰一个 root 槽位(SQLite/PG 双方言 partial unique index)
        Index(
            "uq_board_cards_root",
            "subject_kind", "subject_id",
            unique=True,
            sqlite_where=text("is_root = 1"),
            postgresql_where=text("is_root IS TRUE"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    subject_kind: Mapped[str] = mapped_column(String(32), default="endpoint")
    subject_id: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text, default="")
    is_root: Mapped[bool] = mapped_column(Boolean, default=False)
    quadrant: Mapped[str] = mapped_column(String(16))
    # 可空:注解的是哪个节点(决定虚线连到谁);node id 形如 "sc:xxx"
    annotates_node_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # SET NULL + 姓名快照(§2.1):协作内容不连坐,展示侧显示「已注销」;
    # 作者注销后卡片转只读(admin 接管旁路随 P2)。
    author_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    author_name: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
