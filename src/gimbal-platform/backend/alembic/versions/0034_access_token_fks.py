"""token_id 外键补建(0033 遗漏,r10.4 §4.2)

0033 对 ``executions`` / ``integration_tasks`` / ``webhook_deliveries``
的 ``token_id`` 只 ``add_column`` 未建约束 —— FK SET NULL 仅存在于
ORM 模型,走 alembic 的存量库删除令牌行后引用列悬空而非置 NULL
(「令牌随用户删除,台账保留」的语义只在测试 create_all 面成立)。
0034 按 §4.2 补建 ``FK access_tokens ON DELETE SET NULL``。

幂等:按语义检测(指向 ``access_tokens`` 且约束列含 ``token_id``),
fresh 链 create_all 已带的同名/默认名约束都算已存在;建约束前先
清一次悬空引用(平台未上线,防御性,理论上无数据)。

Revision ID: 0034_access_token_fks
Revises: 0033_access_tokens
Create Date: 2026-11-04
"""
from alembic import op
import sqlalchemy as sa

revision = "0034_access_token_fks"
down_revision = "0033_access_tokens"
branch_labels = None
depends_on = None

_TABLES = ("executions", "integration_tasks", "webhook_deliveries")


def _has_token_fk(bind, table: str) -> bool:
    for fk in sa.inspect(bind).get_foreign_keys(table):
        cols = fk.get("constrained_columns") or []
        if "token_id" in cols and fk.get("referred_table") == "access_tokens":
            return True
    return False


def upgrade() -> None:
    bind = op.get_bind()
    for table in _TABLES:
        if _has_token_fk(bind, table):
            continue
        # 防御:加约束前清悬空引用(不存在的令牌 id → NULL)
        bind.execute(sa.text(
            f"UPDATE {table} SET token_id = NULL "
            "WHERE token_id IS NOT NULL AND token_id NOT IN "
            "(SELECT id FROM access_tokens)"))
        op.create_foreign_key(
            f"fk_{table}_token_id", table, "access_tokens",
            ["token_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    bind = op.get_bind()
    for table in _TABLES:
        if _has_token_fk(bind, table):
            op.drop_constraint(f"fk_{table}_token_id", table,
                               type_="foreignkey")
