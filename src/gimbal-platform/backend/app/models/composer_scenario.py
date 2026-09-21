"""SQLAlchemy model for the V3 Scenario Composer Scenario row.

A Scenario is the "structural definition layer" and owns 1:N DataSets.
``payload`` carries the full draft container
``{definition, orchestration}``; ``definition`` is the plate
Scenario structure (steps included) and lives in a JSON column because
the per-step shape is heterogeneous — M2 起列表侧的 meta 投影由下方
STORED 生成列自算(不再"从 SQL 查进 step 字段")。

M2(PG迁移方案 §2.2):七个 meta 投影 = STORED 生成列,DB 写入时自算,
应用写入侧一行不改,双写漂移物理上不可能(「payload 是唯一可写源」的
机构化表达)。表达式经 ``_json_path`` 按方言渲染(PG ``->/->>``,
SQLite ``json_extract``)。``users.role`` 不进 models(生成列方向翻转:
代码零读零写,回滚物理安全)。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    cast,
    func,
    literal,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base
from ._json_path import json_path_json, json_path_text
from ._types import JsonVar


def _meta(*keys: str):
    """``payload->definition->meta-><keys...>`` 的字面量路径段。"""
    return (literal("definition"), literal("meta"), *(literal(k) for k in keys))


class ComposerScenario(Base):
    """A Scenario row (V3 composer).  ``payload`` carries the full draft."""

    __tablename__ = "composer_scenarios"
    __table_args__ = (
        # 列表分页锚(§2.2:排序 updated_at DESC + visibility 桶)
        Index("ix_composer_vis_updated", "visibility", "updated_at"),
        # GIN 仅 PG 生效(JSONB 路径索引);SQLite 侧渲染为普通 btree
        #(本地量小,无害)。M3 检索 SQL 化时按需补 trgm。
        Index(
            "ix_composer_tags_gin",
            "tags",
            postgresql_using="gin",
            postgresql_ops={"tags": "jsonb_path_ops"},
        ),
        Index(
            "ix_composer_system_gin",
            "system",
            postgresql_using="gin",
            postgresql_ops={"system": "jsonb_path_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    scenario_id: Mapped[str] = mapped_column(
        String(128), unique=True, index=True
    )  # matches meta.scenarioId
    # 属主字符串快照(展示;原 ``owner`` 列升正位为三件套规范命名)。
    # 归属判断的唯一权威是 owner_id。
    owner_name: Mapped[str] = mapped_column(
        String(128), default="", index=True
    )
    # 稳定属主(int user.id)。M2:FK + SET NULL —— 人走场景留(转公共库
    # 或转让,处置流程见权限方案 §4.3;历史 owner_id=0 行由 ETL 映射 NULL)。
    owner_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    visibility: Mapped[str] = mapped_column(
        String(16), default="private", index=True
    )
    # Full draft container: {definition, orchestration} — the single
    # source of truth for meta/steps/config/resource.  列表侧的 meta 投影
    # 由下方生成列自算(源存果算,DB 物化,应用不可写)。
    payload: Mapped[dict] = mapped_column(JsonVar, default=dict)

    # ── 查询投影:STORED 生成列(§2.2;表达式按方言渲染)───────────────
    # 落库 meta 恒为归一后形态(scenario_store.create/update 写回校验后
    # 的 model_dump),SQL 抽取 1:1 复现 Python 读取,无第二口径。
    name: Mapped[str | None] = mapped_column(
        String(64), Computed(json_path_text(payload, *_meta("name")), persisted=True)
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        Computed(json_path_text(payload, *_meta("description")), persisted=True),
    )
    module: Mapped[str | None] = mapped_column(
        String(64), Computed(json_path_text(payload, *_meta("module")), persisted=True)
    )
    # 作者筛选用 meta.author(FilterPopover 维度),非 owner 快照。
    author: Mapped[str | None] = mapped_column(
        String(128), Computed(json_path_text(payload, *_meta("author")), persisted=True)
    )
    # int 0-3:priority 是必填 int(meta 校验先行;preccheck 对存量逐行核)。
    priority: Mapped[int | None] = mapped_column(
        SmallInteger,
        Computed(cast(json_path_text(payload, *_meta("priority")), Integer), persisted=True),
    )
    system: Mapped[list | None] = mapped_column(
        JsonVar, Computed(json_path_json(payload, *_meta("system")), persisted=True)
    )
    tags: Mapped[list | None] = mapped_column(
        JsonVar, Computed(json_path_json(payload, *_meta("tags")), persisted=True)
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
