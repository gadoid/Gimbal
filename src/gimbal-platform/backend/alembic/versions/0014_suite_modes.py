"""Suite 层重构第 1 步:成员角色 + 乐观锁 + 编排执行归属。

《Suite 层重构设计方案》「数据模型(迁移 0014)」:
- suite_members.role(main/before/after):前置/后置也是成员(约束 1,
  推翻 P2 设计 §6.1「模式角色写模式配置、成员表不加列」);
- suites.rev(乐观锁):composition 整体保存带版本号,任何改动成员
  或编排的路径都推进;
- executions.kind(scenario/suite_graph)+ 可空 suite_id —— 不加 FK:
  执行台账归执行人,历史不随 Suite 删除消失(21 页对已删 Suite 降级
  为纯文本名)。kind 与队列层 execution_jobs.kind(cases/graph/debug)
  同名不同层、值域互斥。
无数据迁移:Suite 未正式使用,存量行落默认值即正确语义
(全部现有成员 = main、全部现有执行 = scenario)。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0014_suite_modes"
down_revision = "0013_shares"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("suite_members") as batch:
        batch.add_column(sa.Column("role", sa.String(16), nullable=False,
                                   server_default="main"))
    with op.batch_alter_table("suites") as batch:
        batch.add_column(sa.Column("rev", sa.Integer, nullable=False,
                                   server_default="0"))
    with op.batch_alter_table("executions") as batch:
        batch.add_column(sa.Column("kind", sa.String(32), nullable=False,
                                   server_default="scenario"))
        batch.add_column(sa.Column("suite_id", sa.Integer, nullable=True))
    op.create_index("ix_executions_suite", "executions", ["suite_id"])


def downgrade() -> None:
    op.drop_index("ix_executions_suite", table_name="executions")
    with op.batch_alter_table("executions") as batch:
        batch.drop_column("suite_id")
        batch.drop_column("kind")
    with op.batch_alter_table("suites") as batch:
        batch.drop_column("rev")
    with op.batch_alter_table("suite_members") as batch:
        batch.drop_column("role")
