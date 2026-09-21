"""pg_trgm 检索索引(M3,PG迁移方案 §7 M3 / §2.2)。

q 子串检索在 PG 用 ILIKE;无 trgm 索引时 ILIKE 退化为全表顺序扫。
本 revision 建 pg_trgm 扩展 + name/description/scenario_id 三个 GIN
trgm 索引(§0 原则 5:「ILIKE + 元数据列起步,pg_trgm 索引」)。

SQLite:无对应概念,本 revision 为 no-op(本地量小,Python 兜底)。
"""
from __future__ import annotations

from alembic import op

revision = "0003_pg_trgm_indexes"
down_revision = "0002_role_authority_flip"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    # gimbal 用户是库 owner(docker compose POSTGRES_USER),可建扩展
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_composer_name_trgm "
        "ON composer_scenarios USING gin (name gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_composer_description_trgm "
        "ON composer_scenarios USING gin (description gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_composer_sid_trgm "
        "ON composer_scenarios USING gin (scenario_id gin_trgm_ops)"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("DROP INDEX IF EXISTS ix_composer_sid_trgm")
    op.execute("DROP INDEX IF EXISTS ix_composer_description_trgm")
    op.execute("DROP INDEX IF EXISTS ix_composer_name_trgm")
