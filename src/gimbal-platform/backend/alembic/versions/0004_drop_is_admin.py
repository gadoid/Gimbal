"""is_admin 列删除(M6-3,权限方案 §1.2 的过渡镜像退场)。

M2.5 起 role 是唯一权威、应用写侧恒等镜像 is_admin = (role == 'admin')
—— 一个版本过渡后删列。读侧:API 字段 ``is_admin`` 保留(前端旧缓存
fallback 口径),由 UserPublic 派生自 role,不再有物理列。

双方言:
* PG:直接 DROP COLUMN;
* SQLite:batch_alter_table DROP COLUMN(旧 SQLite 的 ALTER 限制由
  batch 重建吸收)。

不可逆成分:列删除后 is_admin 的历史值不再可恢复 —— 但 M2.5 起该列
恒等于 role=='admin',无独立信息,无损。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_drop_is_admin"
down_revision = "0003_pg_trgm_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("users")}
    if "is_admin" not in cols:
        return  # M6-3 后的 fresh 链:baseline 已无该列
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE users DROP COLUMN is_admin")
    else:
        with op.batch_alter_table("users") as batch:
            batch.drop_column("is_admin")


def downgrade() -> None:
    # is_admin 恒等于 role=='admin'(M2.5 起无独立信息)→ 按派生关系重建
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT false"
        )
        op.execute("UPDATE users SET is_admin = (role = 'admin')")
    else:
        with op.batch_alter_table("users") as batch:
            batch.add_column(
                sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false())
            )
        op.execute("UPDATE users SET is_admin = (role = 'admin')")
