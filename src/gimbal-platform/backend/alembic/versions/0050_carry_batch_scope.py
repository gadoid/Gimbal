"""authz M2a S7.6:carry 值表批带作用域。

``adaptation_batches`` 加 ``carry_scope``('project'|'user';NULL = 公共
项目层,与 carry_store scope=None 缺省语义同型)+ ``carry_scope_id``
(多态指向 projects/users,应用层校验,不落 FK)。存量行全是公共层
(S7.6 前 carry 批只触公共层)→ 无回填,NULL 即公共层。

fresh 链守卫:baseline 按当前模型建表(两列已在)→ 内省后空转。
downgrade 删两列(项目/个人层批次的层标记丢失,回落后批次按公共层
解析 —— 一次性降级语义,与 0049 同判)。
"""
from alembic import op
import sqlalchemy as sa

revision = "0050_carry_batch_scope"
down_revision = "0049_drop_share_refs"
branch_labels = None
depends_on = None

_COLS = ("carry_scope", "carry_scope_id")


def _missing(bind) -> list[str]:
    have = {c["name"] for c in sa.inspect(bind).get_columns("adaptation_batches")}
    return [c for c in _COLS if c not in have]


def upgrade() -> None:
    bind = op.get_bind()
    missing = _missing(bind)
    if "carry_scope" in missing:
        op.add_column("adaptation_batches", sa.Column(
            "carry_scope", sa.String(16), nullable=True))
    if "carry_scope_id" in missing:
        op.add_column("adaptation_batches", sa.Column(
            "carry_scope_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    missing = _missing(bind)
    if "carry_scope_id" not in missing:
        op.drop_column("adaptation_batches", "carry_scope_id")
    if "carry_scope" not in missing:
        op.drop_column("adaptation_batches", "carry_scope")
