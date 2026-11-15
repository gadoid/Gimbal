"""clientRef 幂等索引(入站执行参数设计 2026-11-13 决策 8)。

外部投递天然 at-least-once,网络重试 = 重复业务订单 —— (身份,
client_ref) 部分唯一约束兜底派发侧预查:

* ``(token_id, client_ref)`` WHERE 两者非空(令牌维度);
* ``(owner_id, client_ref)`` WHERE token_id 为空且 client_ref 非空
  (JWT 维度)。

存量重复容错(设计 §9「0056 建索引前查重容错」):建索引前按同口径
分组,保留最早一条(id 最小 = 首投,409 回显语义指向它),其余重复行
client_ref 置 NULL —— 台账行保留,仅去引用键。

fresh 链守卫(同 0055 口径):baseline create_all 已建同名索引时空转。

Revision ID: 0056_client_ref_unique
Revises: 0055_service_meta
Create Date: 2026-11-15
"""
from alembic import op
import sqlalchemy as sa

revision = "0056_client_ref_unique"
down_revision = "0055_service_meta"
branch_labels = None
depends_on = None

_TOKEN_WHERE = "token_id IS NOT NULL AND client_ref IS NOT NULL"
_USER_WHERE = "token_id IS NULL AND client_ref IS NOT NULL"


def _has_index(bind, name: str) -> bool:
    return name in {ix["name"] for ix in sa.inspect(bind)
                    .get_indexes("executions")}


def upgrade() -> None:
    bind = op.get_bind()
    # 存量查重容错:同 (token_id, client_ref) / (owner_id, client_ref)
    # 保留 id 最小(首投),其余置 NULL —— 不删台账行,只去幂等键。
    op.execute(sa.text("""
        UPDATE executions AS e SET client_ref = NULL
        WHERE token_id IS NOT NULL AND client_ref IS NOT NULL
          AND id <> (SELECT MIN(id) FROM executions AS e2
                     WHERE e2.token_id = e.token_id
                       AND e2.client_ref = e.client_ref)
    """))
    op.execute(sa.text("""
        UPDATE executions AS e SET client_ref = NULL
        WHERE token_id IS NULL AND client_ref IS NOT NULL
          AND id <> (SELECT MIN(id) FROM executions AS e2
                     WHERE e2.token_id IS NULL
                       AND e2.owner_id = e.owner_id
                       AND e2.client_ref = e.client_ref)
    """))
    # fresh 链守卫:create_all(模型已声明同名部分唯一索引)后空转
    if not _has_index(bind, "uq_executions_token_client_ref"):
        op.create_index(
            "uq_executions_token_client_ref", "executions",
            ["token_id", "client_ref"], unique=True,
            postgresql_where=sa.text(_TOKEN_WHERE),
            sqlite_where=sa.text(_TOKEN_WHERE))
    if not _has_index(bind, "uq_executions_user_client_ref"):
        op.create_index(
            "uq_executions_user_client_ref", "executions",
            ["owner_id", "client_ref"], unique=True,
            postgresql_where=sa.text(_USER_WHERE),
            sqlite_where=sa.text(_USER_WHERE))


def downgrade() -> None:
    bind = op.get_bind()
    if _has_index(bind, "uq_executions_token_client_ref"):
        op.drop_index("uq_executions_token_client_ref", "executions")
    if _has_index(bind, "uq_executions_user_client_ref"):
        op.drop_index("uq_executions_user_client_ref", "executions")
