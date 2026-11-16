"""Service model — 服务主档(服务注册重构 2026-11-16,docs/service-registry-redesign.md §1.1)。

注册簿制:显式集合,**不是 plate 目录镜像** —— plate 新服务不自动进
(页面对账条提示可拉入),plate 改名可对账出漂移,external 服务自足
登记(不受 plate 可达性影响)。对账状态运行时算,不落库。

* ``name`` = plate 基础服务名(uq;external 可自由命名);
* ``system`` = 归属系统名(从 plate 目录带出;账户按系统聚池 ——
  同系统多服务共享登录、改密一处生效);
* ``kind`` 三态沿用(plate|external|integration,别名录三态口径);
* ``description`` 收编原 service_meta(说明列退役)。

写 ops.write / 读全员(与原 service_meta 同权面)。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base
from ._types import UtcDateTime


class Service(Base):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    # 归属系统名(plate system 口径;登记时从目录带出,external 手填)
    system: Mapped[str] = mapped_column(
        String(128), nullable=False, default="", server_default=text("''"))
    kind: Mapped[str] = mapped_column(
        String(16), nullable=False, default="plate",
        server_default=text("'plate'"))
    abbr: Mapped[str] = mapped_column(
        String(64), nullable=False, default="", server_default=text("''"))
    description: Mapped[str] = mapped_column(
        String(1024), nullable=False, default="", server_default=text("''"))
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
