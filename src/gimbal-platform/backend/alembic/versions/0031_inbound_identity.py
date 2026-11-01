"""入站身份(webhook 设计 v3 P1 §7.1–7.4)

* ``service_aliases`` 加入站/回调四列(inbound_enabled /
  callback_enabled / callback_path / callback_secret —— secret 为
  Fernet 密文,v3 定案 D4);
* 新表 ``inbound_credentials``(gic_ 入站凭证)/ ``inbound_grants``
  (ggt_ 用户授权),库中只存 sha256;
* ``executions`` 与 ``integration_tasks``(模板行)加调用方台账四列
  (caller_alias_name 加索引 / grant_id / client_ref /
  callback_path_override),均不建外键 —— 台账不随别名删除消失。

Revision ID: 0031_inbound_identity
Revises: 0030_integration_consent
Create Date: 2026-11-01
"""
from alembic import op
import sqlalchemy as sa

revision = "0031_inbound_identity"
down_revision = "0030_integration_consent"
branch_labels = None
depends_on = None

_ALIAS_COLUMNS = (
    sa.Column("inbound_enabled", sa.Boolean(), nullable=False,
              server_default=sa.false()),
    sa.Column("callback_enabled", sa.Boolean(), nullable=False,
              server_default=sa.false()),
    sa.Column("callback_path", sa.String(length=256), nullable=True),
    sa.Column("callback_secret", sa.String(length=512), nullable=True),
)

# executions 与 integration_tasks(模板行)共用的调用方台账列
_CALLER_COLUMNS = (
    sa.Column("caller_alias_name", sa.String(length=128), nullable=True),
    sa.Column("grant_id", sa.BigInteger(), nullable=True),
    sa.Column("client_ref", sa.String(length=128), nullable=True),
    sa.Column("callback_path_override", sa.String(length=256), nullable=True),
)


def _has_table(bind, name: str) -> bool:
    return sa.inspect(bind).has_table(name)


def _has_column(table: str, column: str) -> bool:
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}
    return column in cols


def upgrade() -> None:
    # fresh 链守卫(同 0024/0030 口径):baseline create_all 按当前模型
    # 建库时已含这些列/表,本迁移空转;存量库(0030 及之前)逐一补。
    bind = op.get_bind()
    for col in _ALIAS_COLUMNS:
        if not _has_column("service_aliases", col.name):
            op.add_column("service_aliases", col)
    if not _has_table(bind, "inbound_credentials"):
        op.create_table(
            "inbound_credentials",
            sa.Column("id", sa.BigInteger(), autoincrement=True,
                      nullable=False),
            sa.Column("alias_name", sa.String(length=128), nullable=False),
            sa.Column("token_hash", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=64), nullable=False,
                      server_default=""),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True),
                      server_default=sa.func.now(), nullable=False),
            sa.Column("last_used_at", sa.DateTime(timezone=True),
                      nullable=True),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(
                ["alias_name"], ["service_aliases.alias_name"],
                onupdate="CASCADE", ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("token_hash"),
        )
    if not _has_table(bind, "inbound_grants"):
        op.create_table(
            "inbound_grants",
            sa.Column("id", sa.BigInteger(), autoincrement=True,
                      nullable=False),
            sa.Column("alias_name", sa.String(length=128), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("token_hash", sa.String(length=64), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True),
                      nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True),
                      server_default=sa.func.now(), nullable=False),
            sa.Column("last_used_at", sa.DateTime(timezone=True),
                      nullable=True),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(
                ["alias_name"], ["service_aliases.alias_name"],
                onupdate="CASCADE", ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"],
                                    ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("token_hash"),
        )
        op.create_index("ix_inbound_grants_alias", "inbound_grants",
                        ["alias_name"])
    for col in _CALLER_COLUMNS:
        if not _has_column("executions", col.name):
            op.add_column("executions", col)
    if _has_column("executions", "caller_alias_name"):
        bind = op.get_bind()
        idx = {i["name"] for i in sa.inspect(bind).get_indexes("executions")}
        if "ix_executions_caller" not in idx:
            op.create_index("ix_executions_caller", "executions",
                            ["caller_alias_name"])
    for col in _CALLER_COLUMNS:
        if not _has_column("integration_tasks", col.name):
            op.add_column("integration_tasks", col)


def downgrade() -> None:
    for col in reversed(_CALLER_COLUMNS):
        op.drop_column("integration_tasks", col.name)
    op.drop_index("ix_executions_caller", table_name="executions")
    for col in reversed(_CALLER_COLUMNS):
        op.drop_column("executions", col.name)
    op.drop_index("ix_inbound_grants_alias", table_name="inbound_grants")
    op.drop_table("inbound_grants")
    op.drop_table("inbound_credentials")
    for col in reversed(_ALIAS_COLUMNS):
        op.drop_column("service_aliases", col.name)
