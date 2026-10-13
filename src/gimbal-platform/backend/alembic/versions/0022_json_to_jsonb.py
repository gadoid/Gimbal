"""0022:存量列 json → jsonb(⑤,2026-10-13 PG 类型漂移收口)。

模型口径 JsonVar = JSON().with_variant(JSONB(), "postgresql") —— PG 上
应为 jsonb;但 0015-0021 各迁移建列用了裸 sa.JSON,PG 落成 json
(SQLite 两态同型,空库门在 SQLite 上看不出漂移)。IntegrationTask
未注册进 models/__init__ 进一步放大了新建面缺口(已同批补注册)。

本迁移把当前为 json 的漂移列统一转 jsonb(PG-only;逐列内省守卫,
幂等可重跑)。转换 USING col::jsonb 对合法 json 文本无损。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0022_json_to_jsonb"
down_revision = "0021_external_registry"
branch_labels = None
depends_on = None

# 模型 JsonVar 列的全集(按表聚合);不在当前漂移清单里的列守卫跳过
_TARGETS: dict[str, tuple[str, ...]] = {
    "adaptation_batches": ("from_revisions", "scope"),
    "environments": ("lines",),
    "execution_event_evidence": ("evidence",),
    "execution_jobs": ("payload",),
    "executions": ("baseline_evidence", "plate_pins"),
    "external_endpoints": ("request_schema",),
    "integration_tasks": ("last_outputs", "output_mapping",
                          "state_mapping", "state_vars"),
    "scenario_endpoint_refs": ("via_vars",),
    "suites": ("mode_config",),
}


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return          # SQLite 两态同型,无漂移面
    insp = sa.inspect(bind)
    for table, columns in _TARGETS.items():
        if not insp.has_table(table):
            continue
        actual = {c["name"]: str(c["type"]).upper()
                  for c in insp.get_columns(table)}
        for col in columns:
            if actual.get(col) == "JSON":
                op.execute(
                    f'ALTER TABLE {table} ALTER COLUMN {col} '
                    f'TYPE JSONB USING {col}::jsonb')


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    insp = sa.inspect(bind)
    for table, columns in _TARGETS.items():
        if not insp.has_table(table):
            continue
        actual = {c["name"]: str(c["type"]).upper()
                  for c in insp.get_columns(table)}
        for col in columns:
            if actual.get(col) == "JSONB":
                op.execute(
                    f'ALTER TABLE {table} ALTER COLUMN {col} '
                    f'TYPE JSON USING {col}::json')
