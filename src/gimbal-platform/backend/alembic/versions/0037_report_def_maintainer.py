"""authz W9-2:公共报告定义建维护者。

公共态从「owner_id IS NULL」改为独立 visibility 列;owner_id 保留
(新建公共定义恒带维护者,编辑权 = 维护者,Admin+ 仅可下架)。
回填:存量无主行(owner_id IS NULL = 旧公共态)→ visibility='public',
owner 保持 NULL(遗留行全员可读、编辑面冻结 —— 无人是维护者)。
"""
from alembic import op
import sqlalchemy as sa

revision = "0037_report_def_maintainer"
down_revision = "0036_role_rename"
branch_labels = None
depends_on = None


def _has_column(bind, table: str, column: str) -> bool:
    return any(c["name"] == column
               for c in sa.inspect(bind).get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()
    # ① 加列(fresh 链守卫,同 0035/0036 口径)
    if not _has_column(bind, "report_definitions", "visibility"):
        op.add_column(
            "report_definitions",
            sa.Column("visibility", sa.String(16), nullable=False,
                      server_default="private"))
    # ② 回填公共态:旧口径「无主 = 公共」→ visibility=public
    bind.execute(sa.text(
        "UPDATE report_definitions SET visibility = 'public' "
        "WHERE owner_id IS NULL"))


def downgrade() -> None:
    # owner_id 未动过 —— drop 列即回旧口径(无主行重新等于公共态)
    bind = op.get_bind()
    if _has_column(bind, "report_definitions", "visibility"):
        op.drop_column("report_definitions", "visibility")
