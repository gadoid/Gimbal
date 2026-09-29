"""2026-09-29 P3 收尾：execution_events.payload → JSONB + endpoint 列。

* payload：0008 建表用 sa.JSON（PG 上是 json 文本），与模型 JsonVar
  （JSON().with_variant(JSONB)）漂移 → PG ALTER 为 jsonb（可索引/去空白）；
  SQLite 的 JSON 本就是 TEXT，无需变更；
* endpoint：调用边界端点标识（信封完整：view_hints.endpoint_id 或
  service/method/path 推导），与 module/service/protocol 同级标签列。

fresh 链守卫：baseline ``create_all`` 按当前模型建表（payload 已是
JSONB 变体、endpoint 列存在）→ 内省后空转（同 0006/0008/0009）。
部署硬顺序：先 upgrade 再起新代码。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0010_events_jsonb_endpoint"
down_revision = "0009_execution_queue"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    insp = sa.inspect(op.get_bind())
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    cols = _columns("execution_events")
    if not cols:
        return  # 表不存在（理论不可达：0008 必建）
    if "endpoint" not in cols:
        op.add_column("execution_events",
                      sa.Column("endpoint", sa.String(128), nullable=True))
    # payload → JSONB 仅 PG（SQLite JSON==TEXT 本地无 JSONB 概念）
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE execution_events "
            "ALTER COLUMN payload TYPE JSONB USING payload::jsonb")


def downgrade() -> None:
    cols = _columns("execution_events")
    if not cols:
        return
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE execution_events "
            "ALTER COLUMN payload TYPE JSON USING payload::json")
    if "endpoint" in cols:
        op.drop_column("execution_events", "endpoint")
