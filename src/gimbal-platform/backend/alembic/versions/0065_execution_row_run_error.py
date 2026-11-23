"""execution_rows 加 run_error 列(登记册 B3 遗留工程项)。

行级失败原因入库:此前仅存于工件(两击可达),执行详情顶层 error 只
覆盖 dispatcher 级 —— 行级原因(引擎结果错误/派发层异常)随行终态
落库,行页/报告可直接呈现。

fresh 链守卫:空库走 baseline create_all(模型已含本列)+ stamp head,
列已存在时整体空转。downgrade 删列(纯加列,无数据语义)。
"""
import sqlalchemy as sa
from alembic import op

revision = "0065_execution_row_run_error"
down_revision = "0064_identity_project_grants"
branch_labels = None
depends_on = None


def _has_column(bind, table: str, column: str) -> bool:
    cols = {c["name"] for c in sa.inspect(bind).get_columns(table)}
    return column in cols


def upgrade() -> None:
    if _has_column(op.get_bind(), "execution_rows", "run_error"):
        return  # fresh 链:baseline create_all 已含本列
    op.add_column(
        "execution_rows",
        sa.Column("run_error", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    if not _has_column(op.get_bind(), "execution_rows", "run_error"):
        return
    op.drop_column("execution_rows", "run_error")
