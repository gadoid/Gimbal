"""executions.project_id 单列索引(2026-11-18,A 级批次)。

0040 建列时漏了模型侧已声明的 index=True —— 本批项目维度聚合
(/executions/summary?projectId= 与列表 projectId 过滤)按该列扫,
补索引顺带修 model/DB drift(create_all 的测试库一直有,alembic
库没有)。

fresh 链守卫:索引已存在(空库 baseline create_all 已是终态)即空转。
"""
import sqlalchemy as sa
from alembic import op

revision = "0062_executions_project_id_index"
down_revision = "0061_instance_groups"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    idx = {i["name"] for i in sa.inspect(bind).get_indexes("executions")}
    if "ix_executions_project_id" in idx:
        return  # fresh 链:baseline create_all 已含该索引

    op.create_index("ix_executions_project_id", "executions", ["project_id"])


def downgrade() -> None:
    bind = op.get_bind()
    idx = {i["name"] for i in sa.inspect(bind).get_indexes("executions")}
    if "ix_executions_project_id" not in idx:
        return
    op.drop_index("ix_executions_project_id", table_name="executions")
