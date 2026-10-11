"""0016: 环境组表 + plate_pins 执行记录列（Release v4.4 §11 V5 已定按 B / 4.4）。

- environments：环境组表（V5/D-7）——环境声明「每个系统部署的是哪条版本线」
- service_aliases.group_tag → environment_id 外键（存量值迁移为同名环境）
- executions 加 plate_pins（生效修订表 JSON）与 m2_hash 列（RS3/4.4）

迁移纪律：默认演练、先备份、单事务、可重复执行。
"""
from alembic import op
import sqlalchemy as sa

revision = "0016_environments"
down_revision = "0015_integration_tasks"


def upgrade() -> None:
    # ── environments 表 ──
    op.create_table(
        "environments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False, unique=True),
        sa.Column("description", sa.String(256), default=""),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"),
                  nullable=True),
        sa.Column("visibility", sa.String(16), default="private"),
        # lines: JSON {系统名: 版本线}（如 {"fin": "1.0", "platform": "1.0"}）
        sa.Column("lines", sa.JSON(), default=dict),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
    )

    # ── service_aliases.group_tag → environment_id ──
    op.add_column("service_aliases",
                  sa.Column("environment_id", sa.Integer(),
                            sa.ForeignKey("environments.id"),
                            nullable=True))
    # 存量迁移:同名 group_tag 值 → 环境组
    op.execute("""
        INSERT INTO environments (name, description, lines)
        SELECT DISTINCT tag, '存量 group_tag 迁移', '{}'::jsonb
        FROM (
            SELECT DISTINCT group_tag AS tag FROM service_aliases
            WHERE group_tag IS NOT NULL AND group_tag != ''
        ) AS tags
    """)
    op.execute("""
        UPDATE service_aliases sa
        SET environment_id = (
            SELECT e.id FROM environments e
            WHERE e.name = sa.group_tag
        )
        WHERE sa.group_tag IS NOT NULL AND sa.group_tag != ''
    """)
    # 不保留双轨（V5 已定按 B）——group_tag 列删除
    op.drop_column("service_aliases", "group_tag")

    # ── executions 加 plate_pins / m2_hash ──
    op.add_column("executions",
                  sa.Column("plate_pins", sa.JSON(), nullable=True))
    op.add_column("executions",
                  sa.Column("m2_hash", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("executions", "m2_hash")
    op.drop_column("executions", "plate_pins")
    # 恢复 group_tag
    op.add_column("service_aliases",
                  sa.Column("group_tag", sa.String(64), nullable=True))
    op.execute("""
        UPDATE service_aliases sa
        SET group_tag = (
            SELECT e.name FROM environments e
            WHERE e.id = sa.environment_id
        )
    """)
    op.drop_column("service_aliases", "environment_id")
    op.drop_table("environments")
