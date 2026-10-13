"""0020: executions 加入库标准三列(版本模型 4.3 / A-3 / W7)。

- baseline_eligible(bool,存量 false):严格门 —— 无受管系统 working ∧
  钉定修订下用到的接口全已评审 ∧ 无 external 服务;
- baseline_block(working | unreviewed | external):首要阻塞原因,
  external 按桶单独统计(不入基线分母);
- baseline_evidence(JSONB):多因全量证据(与执行器事件流无关的
  平台侧合成判定)。
"""
from alembic import op
import sqlalchemy as sa

revision = "0020_execution_baseline"
down_revision = "0019_service_alias_kind"


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _has_column(table: str, column: str) -> bool:
    return column in {
        c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    # fresh 链守卫(2026-10-13 A-1):baseline 已含本列 → 空转。
    if not _has_column("executions", "baseline_eligible"):
        op.add_column("executions", sa.Column(
            "baseline_eligible", sa.Boolean(), nullable=False,
            server_default=sa.false()))
        op.add_column("executions", sa.Column(
            "baseline_block", sa.String(16), nullable=True))
        # 与 0016 plate_pins 同款 sa.JSON(迁移自包含,不引 app 类型)
        op.add_column("executions", sa.Column(
            "baseline_evidence", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("executions", "baseline_evidence")
    op.drop_column("executions", "baseline_block")
    op.drop_column("executions", "baseline_eligible")
