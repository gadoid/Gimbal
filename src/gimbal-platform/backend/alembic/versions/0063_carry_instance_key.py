"""carry 实例档(redesign §8.9;2026-11-19 系统档 → 实例档)。

按部署差异化(测试/预发布/生产同字段不同值)落**实例档**:
``instance_env_id`` 非零行 = (config_key=系统名, 环境) 实例键;原「系统名」
粗档退场(跨部署同值场景罕见,且前端写入口已随项目配置页手写退场撤空)。
层内新链序:条目 > 实例(system, env) > 服务 > 层默认。

与 §8.4(0058)退役的「任意键 env 覆盖」语义不同:那是 env 维覆盖任意
档,这是独立实例档 —— 环境只作实例键坐标,不构成覆盖层。

1. 守卫报告并删除纯系统键行(``config_key ∈ services.system 且 ∉
   services.name``;同名碰撞按服务档保留不误删。系统档无前端写入口、
   0057 存量 238 行全落服务档,预计 0 行 —— 删除量打日志备查);
2. 加列 ``instance_env_id Integer NOT NULL server_default '0'``
   (sentinel 0 = 条目/服务档基线行,避开 NULL 唯一性陷阱);
3. 重建五键唯一约束 ``uq_carry_svc_path``。

fresh 链守卫:空库走 baseline create_all(模型已是五键终态)+ stamp
head,本迁移在列已存在时整体空转。downgrade 不可逆(决策 8 口径,
回滚走 dump 重放)。
"""
import loguru
import sqlalchemy as sa
from alembic import op

revision = "0063_carry_instance_key"
down_revision = "0062_executions_project_id_index"
branch_labels = None
depends_on = None


def _has_column(bind, table: str, column: str) -> bool:
    return column in {
        c["name"] for c in sa.inspect(bind).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    if _has_column(bind, "carry_service_bindings", "instance_env_id"):
        return  # fresh 链:baseline create_all 已是五键终态

    # ① 守卫报告 + 删除纯系统键行(服务名 ∪ 系统名 同名时按服务档保留)
    n = bind.execute(sa.text("""
        SELECT count(*) FROM carry_service_bindings
        WHERE config_key IN (SELECT system FROM services WHERE system IS NOT NULL)
          AND config_key NOT IN (SELECT name FROM services)
    """)).scalar() or 0
    if n:
        loguru.logger.info(
            "0063: 删除纯系统档 carry 行 {} 条(系统档退场,§8.9)", n)
        bind.execute(sa.text("""
            DELETE FROM carry_service_bindings
            WHERE config_key IN (SELECT system FROM services WHERE system IS NOT NULL)
              AND config_key NOT IN (SELECT name FROM services)
        """))
    # ② 实例坐标列(sentinel 0 = 基线行)
    op.add_column("carry_service_bindings", sa.Column(
        "instance_env_id", sa.Integer(), nullable=False,
        server_default=sa.text("0")))
    # ③ 四键 → 五键唯一约束(沿用约束名)
    op.drop_constraint("uq_carry_svc_path", "carry_service_bindings",
                       type_="unique")
    op.create_unique_constraint(
        "uq_carry_svc_path", "carry_service_bindings",
        ["scope", "scope_id", "config_key", "field_path",
         "instance_env_id"])


def downgrade() -> None:
    raise NotImplementedError(
        "开发环境直切(决策 8);回滚走迁移前 dump 重放")
