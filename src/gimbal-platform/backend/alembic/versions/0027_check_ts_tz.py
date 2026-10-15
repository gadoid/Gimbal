"""合入评估 §2-2 修复:check_changed_at / check_notified_at 补正 timestamptz。

0024 初版用 ``sa.DateTime()`` 建列,PG 上得到 ``timestamp without time
zone``,与模型 ``UtcDateTime``(timestamptz)漂移 —— ``compare_metadata``
报两列 modify_type。会话时区钉 UTC 的环境数值不偏,但漏执行
``ALTER DATABASE ... timezone`` 的环境读回会偏 8 小时,结论通知节流
(``now - check_notified_at``)随之错位。

存量值均按会话 UTC 写入(UTC 语义),转换统一用 ``AT TIME ZONE 'UTC'``
固定锚点,不受执行会话时区影响。已正确的环境(0024 修订版建的列,或
重建过的库)由守卫空转;downgrade 对称回 timestamp(同样 UTC 锚点)。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0027_check_ts_tz"
down_revision = "0026_external_query_safe"

_TABLE = "integration_tasks"
_TARGETS = ("check_changed_at", "check_notified_at")


def _column_is_tz(table: str, column: str) -> bool | None:
    """列当前是否 timestamptz;表/列不存在 → None(守卫口径)。"""
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(table):
        return None
    for c in sa.inspect(bind).get_columns(table):
        if c["name"] == column:
            return bool(getattr(c["type"], "timezone", False))
    return None


def upgrade() -> None:
    for col in _TARGETS:
        is_tz = _column_is_tz(_TABLE, col)
        if is_tz is None or is_tz:
            continue
        op.execute(
            f"ALTER TABLE {_TABLE} ALTER COLUMN {col} "
            f"TYPE timestamptz USING {col} AT TIME ZONE 'UTC'")


def downgrade() -> None:
    for col in _TARGETS:
        is_tz = _column_is_tz(_TABLE, col)
        if is_tz is None or not is_tz:
            continue
        op.execute(
            f"ALTER TABLE {_TABLE} ALTER COLUMN {col} "
            f"TYPE timestamp WITHOUT TIME ZONE "
            f"USING {col} AT TIME ZONE 'UTC'")
