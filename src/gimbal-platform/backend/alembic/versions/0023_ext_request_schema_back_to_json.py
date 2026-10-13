"""0023:external_endpoints.request_schema 回转 json(2-4,2026-10-13)。

0022 把 14 列 json→jsonb 时,这一列被一并转换 —— 但它是**顺序敏感**列:
``properties`` 键序派生编排表单的 declarations 顺序,JSONB 按键长/字节序
重排(PG 测试 test_catalog_full_ext_branch_isomorphic 实测复现:force 被
排到 title 前)。

处置 = 双保险:
* 列回 json(本迁移),保插入序兜底;
* 写侧统一盖章 ``x-order``(external_endpoints._ensure_order),读侧
  ``_props_to_nodes`` 按 x-order 排序 —— 顺序不依赖存储层行为。

dev 库 0022 已转过、但 external_endpoints 为 0 行(实测),无数据修复面。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0023_ext_schema_json"
down_revision = "0022_json_to_jsonb"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    actual = {c["name"]: str(c["type"]).upper()
              for c in sa.inspect(bind).get_columns("external_endpoints")}
    if actual.get("request_schema") == "JSONB":
        op.execute(
            "ALTER TABLE external_endpoints ALTER COLUMN request_schema "
            "TYPE JSON USING request_schema::json")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    actual = {c["name"]: str(c["type"]).upper()
              for c in sa.inspect(bind).get_columns("external_endpoints")}
    if actual.get("request_schema") == "JSON":
        op.execute(
            "ALTER TABLE external_endpoints ALTER COLUMN request_schema "
            "TYPE JSONB USING request_schema::jsonb")
