"""ServiceMeta model — 服务级元数据(服务注册页「说明」列的落库点)。

目录(services/端点)来自 plate 代理,平台侧不可写;别名/部署表各自
承载别的维度(身份/地址)。服务级的基本信息说明(这个系统是做什么的、
负责人、注意事项)此前无家 —— 本表补上:``service_name`` PK 对齐目录
服务名(目录改名会漂移,平台侧不做外键,读侧以目录为准),``description``
单行富文本不搞(纯说明,512 封顶)。

读全员(矩阵/子页展示),写 Admin+(ops.write;对齐部署表/环境组写面)。
"""
from __future__ import annotations

from datetime import datetime

from ._types import UtcDateTime
from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base


class ServiceMeta(Base):
    __tablename__ = "service_meta"

    service_name: Mapped[str] = mapped_column(String(128), primary_key=True)
    description: Mapped[str] = mapped_column(
        String(512), nullable=False, server_default="")
    updated_by: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime, server_default=func.now(), onupdate=func.now()
    )
