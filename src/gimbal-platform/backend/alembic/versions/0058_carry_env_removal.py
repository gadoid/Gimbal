"""carry env 覆盖维退役(redesign §8.4;2026-11-17 环境降级轮 M1)。

环境只做轻量部署标签,不再承载 carry 配置层(多服务共享一层配置时
同名字段必然打架;需要「同服务不同部署不同值」时挂实例,不回环境层)。
生产实量 238 行绑定 ``env_id`` 全 NULL(0 覆盖行)—— 维度整体删除:

1. 防御去重:同 (scope, scope_id, config_key, field_path) 多行时保留
   id 最大行(覆盖行后写;全基线时任一,值本应相同);
2. drop 旧四键唯一约束(含 env_id)与 env_id FK → drop 列;
3. 重建三键唯一约束。

fresh 链守卫:空库走 baseline create_all(已是终态)+ stamp head,
本迁移在无 env_id 列时整体空转。downgrade 不可逆(决策 8 口径,
回滚走 dump 重放)。
"""
import sqlalchemy as sa
from alembic import op

revision = "0058_carry_env_removal"
down_revision = "0057_registry_rework"
branch_labels = None
depends_on = None


def _has_column(bind, table: str, column: str) -> bool:
    return column in {
        c["name"] for c in sa.inspect(bind).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_column(bind, "carry_service_bindings", "env_id"):
        return  # fresh 链:baseline create_all 已是三键终态

    # ① 防御去重(生产应为 0 行;dev 库若有覆盖行,保留 id 最大者)
    op.execute(sa.text("""
        DELETE FROM carry_service_bindings a
        USING carry_service_bindings b
        WHERE a.id < b.id
          AND a.scope = b.scope AND a.scope_id = b.scope_id
          AND a.config_key = b.config_key
          AND a.field_path = b.field_path
    """))
    # ② 旧四键唯一约束(0057 终态:NND 含 env_id)
    op.drop_constraint("uq_carry_svc_path", "carry_service_bindings",
                       type_="unique")
    # ③ env_id FK(按内省定位,PG 默认名 ..._env_id_fkey)
    for fk in sa.inspect(bind).get_foreign_keys("carry_service_bindings"):
        cols = fk.get("constrained_columns") or []
        if "env_id" in cols and fk.get("referred_table") == "environments":
            op.drop_constraint(fk["name"], "carry_service_bindings",
                               type_="foreignkey")
    op.drop_column("carry_service_bindings", "env_id")
    # ④ 三键唯一约束(NND 已无意义 —— 三列皆 NOT NULL;沿用约束名)
    op.create_unique_constraint(
        "uq_carry_svc_path", "carry_service_bindings",
        ["scope", "scope_id", "config_key", "field_path"])


def downgrade() -> None:
    raise NotImplementedError(
        "开发环境直切(决策 8);回滚走迁移前 dump 重放")
