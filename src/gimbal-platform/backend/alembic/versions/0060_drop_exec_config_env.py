"""执行配置环境链位退役(redesign §8.2;2026-11-17 环境降级轮 M2)。

执行配置不再决定执行标签(标签 = 有效身份 > 项目默认 > 平台默认),
``exec_configs.environment_id`` 列删除(生产实量 0 行配置,纯指针列)。
fresh 链守卫:无该列即空转。downgrade 不可逆(决策 8)。
"""
import sqlalchemy as sa
from alembic import op

revision = "0060_drop_exec_config_env"
down_revision = "0059_auth_default_per_system"
branch_labels = None
depends_on = None


def _has_column(bind, table: str, column: str) -> bool:
    return column in {
        c["name"] for c in sa.inspect(bind).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_column(bind, "exec_configs", "environment_id"):
        return  # fresh 链:create_all 已是终态
    # FK(PG 默认名 ..._environment_id_fkey,按内省定位)
    for fk in sa.inspect(bind).get_foreign_keys("exec_configs"):
        cols = fk.get("constrained_columns") or []
        if "environment_id" in cols \
                and fk.get("referred_table") == "environments":
            op.drop_constraint(fk["name"], "exec_configs",
                               type_="foreignkey")
    op.drop_column("exec_configs", "environment_id")


def downgrade() -> None:
    raise NotImplementedError(
        "开发环境直切(决策 8);回滚走迁移前 dump 重放")
