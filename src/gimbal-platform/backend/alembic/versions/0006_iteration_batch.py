"""2026-09-23 迭代批次:分发/事件日志/别名 URL 默认层。

一车四件(方案 docs/superpowers/plans/2026-09-23-some_feature .md v2,
影响评估见 docs/deployment/sqlite-to-pg-migration.md §8):

* ``notifications`` +resource_type/resource_id/payload 三可空列(F1
  分发悬浮标签;payload=JSONB,存发送方/原名等结构化数据);
* ``service_aliases`` +base_url 可空列(F4 方案 B 的 URL 默认层第三档,
  优先级链「显式绑定 > 场景声明 > base_url > 缺口引擎报错」);
* ``activity_events`` 新表 + 两索引(F3 时间线事件日志,actor SET NULL
  与 AuditLog 同款)。

全部加法、零回填:可空列无 server default,PG 上 ADD COLUMN 是纯元数据
操作毫秒级;存量行 NULL = 行为不变。**部署硬顺序:先 upgrade 再起新代码**
(反向 ORM SELECT 带新列 → UndefinedColumn → 通知接口 500)。
SQLite 回滚源不跑本迁移(旧代码不认新列,天然无冲突)。

fresh 链守卫:baseline 对空库走 ``Base.metadata.create_all``,0006 的新
列/新表已被当前模型带入 → 本 revision 内省后空转(与 0004 对 is_admin
的「baseline 已无该列」同款处理)。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_iteration_batch"
down_revision = "0005_interaction_fields"
branch_labels = None
depends_on = None


def _cols(table: str) -> set[str]:
    insp = sa.inspect(op.get_bind())
    if not insp.has_table(table):
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def _add_column_if_missing(table: str, column: str, ddl_type: str) -> None:
    if column in _cols(table):
        return  # fresh 链:baseline 已从当前模型建出该列
    op.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}")


def upgrade() -> None:
    pg = op.get_bind().dialect.name == "postgresql"

    # ── notifications 三列(双方言同语法;JSON 列方言分叉)────────────
    _add_column_if_missing("notifications", "resource_type", "VARCHAR(32)")
    _add_column_if_missing("notifications", "resource_id", "VARCHAR(128)")
    _add_column_if_missing(
        "notifications", "payload", "JSONB" if pg else "TEXT")

    # ── service_aliases.base_url(F4 默认层)──────────────────────────
    _add_column_if_missing("service_aliases", "base_url", "VARCHAR(512)")

    # ── activity_events 新表(F3)────────────────────────────────────
    # id:PG BIGSERIAL ↔ SQLite INTEGER PK(rowid 自增);created_at 与
    # notifications.created_at 同款 server default(UTC 口径由模型层
    # UtcDateTime 绑定矫正兜底,DDL 侧只管默认值)。
    if "activity_events" not in sa.inspect(op.get_bind()).get_table_names():
        if pg:
            op.execute("""
                CREATE TABLE activity_events (
                    id BIGSERIAL PRIMARY KEY,
                    actor_id INTEGER REFERENCES users (id) ON DELETE SET NULL,
                    kind VARCHAR(64) NOT NULL,
                    resource_type VARCHAR(32) NOT NULL,
                    resource_id VARCHAR(128) NOT NULL,
                    detail JSONB NOT NULL DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """)
        else:
            op.execute("""
                CREATE TABLE activity_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    actor_id INTEGER REFERENCES users (id) ON DELETE SET NULL,
                    kind VARCHAR(64) NOT NULL,
                    resource_type VARCHAR(32) NOT NULL,
                    resource_id VARCHAR(128) NOT NULL,
                    detail JSON NOT NULL DEFAULT '{}',
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_activity_events_actor_created "
        "ON activity_events (actor_id, created_at)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_activity_events_resource "
        "ON activity_events (resource_type, resource_id)")


def _drop_column_if_present(table: str, column: str) -> None:
    if column in _cols(table):
        op.execute(f"ALTER TABLE {table} DROP COLUMN {column}")


def downgrade() -> None:
    # activity_events 是纯派生日志,可弃(要留先导出)。
    op.execute("DROP INDEX IF EXISTS ix_activity_events_resource")
    op.execute("DROP INDEX IF EXISTS ix_activity_events_actor_created")
    op.execute("DROP TABLE IF EXISTS activity_events")
    _drop_column_if_present("service_aliases", "base_url")
    _drop_column_if_present("notifications", "payload")
    _drop_column_if_present("notifications", "resource_id")
    _drop_column_if_present("notifications", "resource_type")
