"""role 权威翻转(P1b/M2.5,权限方案 §1.2/§7)——baseline 后第一个真 revision。

语义:users.role 从「is_admin 的 STORED 生成列」(M2 过渡形态,代码零读零写)
翻转为**可写列 + 权威**;is_admin 保留一个过渡版本(应用写侧镜像,M6 删列)。

双方言:
* PG:baseline 已建 role 为生成列 → ``ALTER COLUMN … DROP EXPRESSION``
  转可写 + DEFAULT 'member'(存量值由生成列自算,无需回填);
* SQLite 本地:baseline 按实施偏离未建 role(仅 PG 建列)→ 直接
  ADD COLUMN 普通列 + 按 is_admin 回填(比「读生成列→写普通列」的
  batch 重建简单 —— 本地方言本就没有生成列要翻转,M0-4 案③的通解
  在本库的具体形态即此)。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_role_authority_flip"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"]: c for c in insp.get_columns("users")}
    if bind.dialect.name == "postgresql":
        # M6-3 后的 fresh 链:role 由 baseline 以平列直建 → 无表达式可
        # DROP,仅补 DEFAULT(容错:两代基线都能走)。
        if "role" in cols:
            gen = sa.text(
                "SELECT attgenerated FROM pg_attribute "
                "WHERE attrelid = 'users'::regclass AND attname = 'role'"
            )
            is_generated = bind.execute(gen).scalar() == "s"
            if is_generated:
                op.execute(
                    "ALTER TABLE users ALTER COLUMN role DROP EXPRESSION")
            op.execute(
                "ALTER TABLE users ALTER COLUMN role SET DEFAULT 'member'")
    elif "role" not in cols:
        # 旧 baseline(SQLite legacy-adapt)未建 role → 补列并按 is_admin 回填
        op.execute(
            "ALTER TABLE users ADD COLUMN role VARCHAR(16) "
            "NOT NULL DEFAULT 'member'"
        )
        # 回填:is_admin=true → admin(与 PG 侧生成列自算的值同口径)
        op.execute("UPDATE users SET role = 'admin' WHERE is_admin = 1")
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_role ON users (role)")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE users ALTER COLUMN role DROP DEFAULT")
        # 翻回生成列(值由 is_admin 重算;role 侧未授权威期间的写会丢)
        op.execute(
            "UPDATE users SET is_admin = (role = 'admin') "
            "WHERE is_admin <> (role = 'admin')"
        )
        op.execute("ALTER TABLE users DROP COLUMN role")
        op.execute(
            "ALTER TABLE users ADD COLUMN role VARCHAR(16) GENERATED ALWAYS AS "
            "(CASE WHEN is_admin THEN 'admin' ELSE 'member' END) STORED"
        )
    else:
        op.execute("ALTER TABLE users DROP COLUMN role")
