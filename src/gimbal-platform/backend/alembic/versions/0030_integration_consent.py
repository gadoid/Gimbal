"""integration 订阅知情同意(个人侧方案 v1.4 §2 W0a)

* 实例行新增 consent_fingerprint / consented_at(执行前内容指纹比对,
  不一致 → 非 owner 实例 paused/template_changed;owner 自有实例跳闸);
* 存量清理(W0a②/P-1=b):删除「持有人 ≠ 模板 owner」的全部 personal
  实例行 —— 均为列表/手动执行隐式播种产生,未经订阅确认;需要者重新
  显式订阅(活库 2026-10-19 实测 0 条,防御其他环境)。

Revision ID: 0030_integration_consent
Revises: 0029_drop_external_endpoints
Create Date: 2026-10-19
"""
from alembic import op
import sqlalchemy as sa

revision = "0030_integration_consent"
down_revision = "0029_drop_external_endpoints"
branch_labels = None
depends_on = None

_COLUMNS = (
    sa.Column("consent_fingerprint", sa.String(length=64),
              nullable=False, server_default=""),
    sa.Column("consented_at", sa.DateTime(timezone=True), nullable=True),
)


def _has_column(table: str, column: str) -> bool:
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}
    return column in cols


def upgrade() -> None:
    # fresh 链守卫(同 0024 口径):baseline create_all 已含本列时空转;
    # 存量清理 DELETE 对空表/已清库幂等无副作用。
    for col in _COLUMNS:
        if not _has_column("integration_tasks", col.name):
            op.add_column("integration_tasks", col)
    op.execute("""
        DELETE FROM integration_tasks AS i
        USING integration_tasks AS t
        WHERE i.template_id = t.id
          AND t.template_id IS NULL
          AND t.identity_mode = 'personal'
          AND i.holder_id IS DISTINCT FROM t.owner_id
    """)


def downgrade() -> None:
    op.drop_column("integration_tasks", "consented_at")
    op.drop_column("integration_tasks", "consent_fingerprint")
