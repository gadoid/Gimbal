"""访问令牌(webhook v4 §4)

* 新表 ``access_tokens``(``gtk_`` 单一令牌:个人绑属主、平台绑
  ``__platform__``)与 ``access_token_scopes``(范围按对象外键存,
  删除即收回授权、别名改名级联);
* ``users`` 加 ``token_version``(改密「退出其他会话」的 tv);
* ``executions`` / ``integration_tasks``:调用方台账 ``caller_alias_
  name`` + ``grant_id`` 换成 ``token_id``(FK SET NULL);v3 平台未上线,
  旧列直接删、无数据迁移;
* ``webhook_deliveries``:``alias_name`` 换 ``token_id``(SET NULL)
  + ``token_name`` 快照;
* ``service_aliases`` 删入站/回调四列;删表 ``inbound_credentials`` /
  ``inbound_grants``(v3 入站存储整体退役,不留兼容层);
* ``audit_logs`` 补 ``(resource_type, resource_id)`` 索引(令牌
  「最近调用」查询面)。

Revision ID: 0033_access_tokens
Revises: 0032_webhook_deliveries
Create Date: 2026-11-04
"""
from alembic import op
import sqlalchemy as sa

revision = "0033_access_tokens"
down_revision = "0032_webhook_deliveries"
branch_labels = None
depends_on = None


def _has_table(bind, name: str) -> bool:
    return sa.inspect(bind).has_table(name)


def _has_column(table: str, column: str) -> bool:
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}
    return column in cols


def _drop_columns(table: str, columns: tuple[str, ...]) -> None:
    for col in columns:
        if _has_column(table, col):
            op.drop_column(table, col)


def upgrade() -> None:
    bind = op.get_bind()
    # ── 新表(fresh 链 create_all 已建时空转)────────────────────
    if not _has_table(bind, "access_tokens"):
        op.create_table(
            "access_tokens",
            sa.Column("id", sa.BigInteger(), autoincrement=True,
                      nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("kind", sa.String(length=16), nullable=False),
            sa.Column("name", sa.String(length=64), nullable=False,
                      server_default=""),
            sa.Column("token_hash", sa.String(length=64), nullable=False),
            sa.Column("token_hint", sa.String(length=16), nullable=False,
                      server_default=""),
            sa.Column("expires_at", sa.DateTime(timezone=True),
                      nullable=False),
            sa.Column("invalidated_at", sa.DateTime(timezone=True),
                      nullable=True),
            sa.Column("invalidated_reason", sa.String(length=16),
                      nullable=True),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("invalidation_note", sa.Text(), nullable=True),
            sa.Column("last_used_at", sa.DateTime(timezone=True),
                      nullable=True),
            sa.Column("callback_url", sa.String(length=512), nullable=True),
            sa.Column("callback_secret", sa.Text(), nullable=True),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True),
                      server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True),
                      server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"],
                                    ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"],
                                    ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("token_hash"),
        )
        op.create_index("ix_access_tokens_user", "access_tokens",
                        ["user_id", "revoked_at"])
    if not _has_table(bind, "access_token_scopes"):
        op.create_table(
            "access_token_scopes",
            sa.Column("id", sa.BigInteger(), autoincrement=True,
                      nullable=False),
            sa.Column("token_id", sa.BigInteger(), nullable=False),
            sa.Column("alias_name", sa.String(length=128), nullable=True),
            sa.Column("auth_id", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(
                ["token_id"], ["access_tokens.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["alias_name"], ["service_aliases.alias_name"],
                onupdate="CASCADE", ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["auth_id"], ["auth_sessions.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.CheckConstraint(
                "(alias_name IS NULL) <> (auth_id IS NULL)",
                name="ck_scope_exactly_one"),
        )
        op.create_index("uq_token_scope_alias", "access_token_scopes",
                        ["token_id", "alias_name"], unique=True)
        op.create_index("uq_token_scope_auth", "access_token_scopes",
                        ["token_id", "auth_id"], unique=True)

    # ── users.token_version ─────────────────────────────────────
    if not _has_column("users", "token_version"):
        op.add_column("users", sa.Column(
            "token_version", sa.Integer(), nullable=False,
            server_default="0"))

    # ── executions / integration_tasks:caller_alias → token_id ──
    for table in ("executions", "integration_tasks"):
        if not _has_column(table, "token_id"):
            op.add_column(table, sa.Column("token_id", sa.BigInteger(),
                                           nullable=True))
        # 平台未上线:旧列无数据语义,直接删
        _drop_columns(table, ("caller_alias_name", "grant_id"))
        if table == "executions":
            idx = {i["name"]
                   for i in sa.inspect(bind).get_indexes("executions")}
            if "ix_executions_caller" in idx:
                op.drop_index("ix_executions_caller", table_name="executions")
            op.create_index("ix_executions_caller", "executions",
                            ["token_id"])

    # ── webhook_deliveries:alias_name → token_id + token_name ────
    if not _has_column("webhook_deliveries", "token_id"):
        op.add_column("webhook_deliveries", sa.Column(
            "token_id", sa.BigInteger(), nullable=True))
    if not _has_column("webhook_deliveries", "token_name"):
        op.add_column("webhook_deliveries", sa.Column(
            "token_name", sa.String(length=64), nullable=False,
            server_default=""))
    _drop_columns("webhook_deliveries", ("alias_name",))

    # ── service_aliases 删入站/回调四列 ─────────────────────────
    _drop_columns("service_aliases",
                  ("inbound_enabled", "callback_enabled",
                   "callback_path", "callback_secret"))

    # ── v3 入站存储退役 ─────────────────────────────────────────
    if _has_table(bind, "inbound_grants"):
        op.drop_table("inbound_grants")
    if _has_table(bind, "inbound_credentials"):
        op.drop_table("inbound_credentials")

    # ── audit_logs:令牌「最近调用」查询索引(§7.2)──────────────
    idx = {i["name"] for i in sa.inspect(bind).get_indexes("audit_logs")}
    if "ix_audit_resource" not in idx:
        op.create_index("ix_audit_resource", "audit_logs",
                        ["resource_type", "resource_id"])


def downgrade() -> None:
    # v4 存储与 v3 无共享数据;降级 = 回到无令牌面(不重建 v3 表)。
    bind = op.get_bind()
    op.drop_index("ix_audit_resource", table_name="audit_logs")
    if _has_table(bind, "inbound_credentials"):
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
    for col in (
        sa.Column("inbound_enabled", sa.Boolean(), nullable=False,
                  server_default=sa.false()),
        sa.Column("callback_enabled", sa.Boolean(), nullable=False,
                  server_default=sa.false()),
        sa.Column("callback_path", sa.String(length=256), nullable=True),
        sa.Column("callback_secret", sa.String(length=512), nullable=True),
    ):
        if not _has_column("service_aliases", col.name):
            op.add_column("service_aliases", col)
    _drop_columns("webhook_deliveries", ("token_id", "token_name"))
    op.add_column("webhook_deliveries", sa.Column(
        "alias_name", sa.String(length=128), nullable=False,
        server_default=""))
    for table in ("integration_tasks", "executions"):
        if table == "executions":
            op.drop_index("ix_executions_caller", table_name="executions")
        _drop_columns(table, ("token_id",))
        op.add_column(table, sa.Column("caller_alias_name",
                                       sa.String(length=128), nullable=True))
        op.add_column(table, sa.Column("grant_id", sa.BigInteger(),
                                       nullable=True))
    _drop_columns("users", ("token_version",))
    op.drop_index("uq_token_scope_auth", table_name="access_token_scopes")
    op.drop_index("uq_token_scope_alias", table_name="access_token_scopes")
    op.drop_table("access_token_scopes")
    op.drop_index("ix_access_tokens_user", table_name="access_tokens")
    op.drop_table("access_tokens")
