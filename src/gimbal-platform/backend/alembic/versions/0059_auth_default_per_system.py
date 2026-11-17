"""默认账户改按 system 唯一(redesign §8.3;2026-11-17 环境降级轮 M2)。

ref_mode=default 的取用位从 (池, system, env) 收敛为 (池, system):
* 防御去重:同 (pool, system) 多个 is_default 行保留 id 最大(最新);
  生产实量 2 账户/1 环境 —— 0 冲突预期,去重为防御性;
* 重建部分唯一索引 uq_account_default 为三列形态(NND 保留:
  owner/project 可空)。

fresh 链守卫:索引已是三列形态则空转。downgrade 不可逆(决策 8)。
"""
import sqlalchemy as sa
from alembic import op

revision = "0059_auth_default_per_system"
down_revision = "0058_carry_env_removal"
branch_labels = None
depends_on = None


def _index_cols(bind) -> "set[tuple]":
    insp = sa.inspect(bind)
    for ix in insp.get_indexes("auth_accounts"):
        if ix["name"] == "uq_account_default":
            return tuple(ix["column_names"])
    return ()


def upgrade() -> None:
    bind = op.get_bind()
    if _index_cols(bind) == ("owner_id", "project_id", "system"):
        return  # fresh 链:create_all 已是三列终态

    # ① 防御去重:同 (pool, system) 多默认保留 id 最大
    op.execute(sa.text("""
        UPDATE auth_accounts a SET is_default = false
        FROM auth_accounts b
        WHERE a.is_default AND b.is_default
          AND a.id < b.id
          AND a.owner_id IS NOT DISTINCT FROM b.owner_id
          AND a.project_id IS NOT DISTINCT FROM b.project_id
          AND a.system = b.system
    """))
    # ② 重建部分唯一索引(同名三列)
    op.drop_index("uq_account_default", table_name="auth_accounts")
    op.create_index(
        "uq_account_default", "auth_accounts",
        ["owner_id", "project_id", "system"], unique=True,
        postgresql_where=sa.text("is_default"),
        postgresql_nulls_not_distinct=True)


def downgrade() -> None:
    raise NotImplementedError(
        "开发环境直切(决策 8);回滚走迁移前 dump 重放")
