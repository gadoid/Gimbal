"""一实例多标签:system_env_instances.group_id(2026-11-18)。

标签即环境后,同一个部署实例可以挂多枚标签(如「测试」+「联调」):
group_id 把"同一实例"的 (system, env) 行归组,组内共享登录口/版本线/
说明。存量行为每组一行(回填 'g'||id,互不共享);新建行由模型默认
生成 uuid。

fresh 链守卫:列已存在(空库 baseline create_all 已是终态)即空转。
downgrade 不可逆(决策 8 口径;回滚走 dump 重放)。
"""
import sqlalchemy as sa
from alembic import op

revision = "0061_instance_groups"
down_revision = "0060_drop_exec_config_env"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns(
        "system_env_instances")}
    if "group_id" in cols:
        return  # fresh 链:baseline create_all 已含该列

    op.add_column("system_env_instances",
                  sa.Column("group_id", sa.String(36), nullable=True))
    # 存量:每行独立成组(标签之间互不共享配置,保持既有语义)
    op.execute(sa.text(
        "UPDATE system_env_instances SET group_id = 'g' || id"))
    op.alter_column("system_env_instances", "group_id", nullable=False)
    op.create_index("ix_system_env_instances_group_id",
                    "system_env_instances", ["group_id"])
