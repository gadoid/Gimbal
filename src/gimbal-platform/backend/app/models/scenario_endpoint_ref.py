"""场景 → 接口/字段倒排索引(派生层,spec §3.2)。

源是 composer_scenarios.payload;本表任何时刻可 drop 后由
services/endpoint_ref_index.rebuild 重建。写路径由 scenario_store
在同一事务内维护。PG 纪律:普通列,无生成列。
"""
from __future__ import annotations

from sqlalchemy import Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base


class ScenarioEndpointRef(Base):
    __tablename__ = "scenario_endpoint_refs"
    __table_args__ = (Index("ix_ser_endpoint", "endpoint_id"),)

    scenario_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    step_index: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(16), primary_key=True)  # body|headers
    field_name: Mapped[str] = mapped_column(String(255), primary_key=True)
    endpoint_id: Mapped[str] = mapped_column(String(255), nullable=False)
    # 值含 ${var.NAME} 模板时记 NAME(取第一个匹配);直填为 NULL
    via_var: Mapped[str | None] = mapped_column(Text, nullable=True)
