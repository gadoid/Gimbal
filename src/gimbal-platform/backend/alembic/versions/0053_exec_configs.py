"""执行配置分层①(设计方案 §4/§10):新表 ``exec_configs``。

执行配置 = 场景外部支撑的跨场景载体(在哪/以谁/带什么业务参数):
一套默认 + 若干命名,子配置按系统分组(bindings + carryOverrides
内联)。零凭证值零地址值 —— 只存引用键。

* ``(scope, scope_id)`` 通用维度(同 carry_binding,无 FK):v1 只落
  ``user`` 行,``project`` 随组级批次 ⑧(模型同构先行);
* ``environment_id`` FK environments SET NULL(环境删除后配置存活,
  环境链回落,与 projects.default_environment_id 同款);
* 同 scope name 唯一;默认配置部分唯一索引至多一行。

fresh 链守卫:baseline 按当前模型建表(本迁移的形状已存在)→ 内省后
空转。downgrade 删表。
"""
import sqlalchemy as sa
from alembic import op

revision = "0053_exec_configs"
down_revision = "0052_project_tokens"
branch_labels = None
depends_on = None


def _has_table(bind, table: str) -> bool:
    return table in set(sa.inspect(bind).get_table_names())


def upgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "exec_configs"):
        return
    op.create_table(
        "exec_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scope", sa.String(16), nullable=False),
        sa.Column("scope_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False,
                  server_default=sa.false()),
        sa.Column("environment_id", sa.Integer(),
                  sa.ForeignKey("environments.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("scope", "scope_id", "name",
                            name="uq_exec_configs_scope_name"),
    )
    op.create_index("ix_exec_configs_scope_id", "exec_configs", ["scope_id"])
    bind.execute(sa.text(
        "CREATE UNIQUE INDEX uq_exec_configs_default ON exec_configs "
        "(scope, scope_id) WHERE is_default"))


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "exec_configs"):
        return
    bind.execute(sa.text("DROP INDEX IF EXISTS uq_exec_configs_default"))
    op.drop_table("exec_configs")
