"""authz M2a S4.0:carry 两表作用域分层。

* 两表加 ``scope``('project'|'user';**无独立 global** —— 裁定:全局
  默认 = 公共项目的项目层)+ ``scope_id``(多态指向 projects/users,
  应用层校验,不落 FK);唯一键加前缀 (scope, scope_id, …),**约束名
  沿用旧名**(模型 create_all 与迁移链同形)。
* 回填(固定顺序):
  ① 全部存量行 → ('project', 公共项目 id)(旧全局层 = 公共项目层);
  ② 个人别名键下的 bindings 行 → ('user', 别名属主)(F3:个人别名名下
     的 carry 行迁为属主个人层;运行时对他人不可见)。
* fresh 链守卫:baseline 按当前模型建表(两列与新键已存在)→ 各步内省
  后空转。downgrade:「公共层优先」去重后回删列、还原旧键(个人层行
  被丢弃 —— 属主个人配置不回落为全局,防越权扩大)。

无公共项目的存量库(异常形态防御):① 跳过、行保持 scope_id=0(应用
层视为未挂靠),由 Admin 建公共项目后手工归位 —— 0040 起迁移链保证
公共项目种子,此分支仅为不炸库。
"""
from alembic import op
import sqlalchemy as sa

revision = "0046_carry_scope"
down_revision = "0045_auth_slot_bindings"
branch_labels = None
depends_on = None


def _has_column(bind, table: str, column: str) -> bool:
    return column in {
        c["name"] for c in sa.inspect(bind).get_columns(table)}


def _has_unique_constraint(bind, table: str, name: str) -> bool:
    return name in {
        c["name"] for c in sa.inspect(bind).get_unique_constraints(table)}


def upgrade() -> None:
    bind = op.get_bind()

    for table in ("carry_service_bindings", "carry_global_defaults"):
        if not _has_column(bind, table, "scope"):
            op.add_column(table, sa.Column(
                "scope", sa.String(16), nullable=False,
                server_default=sa.text("'project'")))
        if not _has_column(bind, table, "scope_id"):
            op.add_column(table, sa.Column(
                "scope_id", sa.Integer(), nullable=False,
                server_default=sa.text("0")))

    # ① 旧全局层 → 公共项目层(无公共项目 = 防御分支,保持 0)
    for table in ("carry_service_bindings", "carry_global_defaults"):
        bind.execute(sa.text(f"""
            UPDATE {table} SET scope_id = p.id
            FROM (SELECT id FROM projects WHERE kind = 'public') AS p
            WHERE scope = 'project' AND scope_id = 0
        """))
    # ② 个人别名键下的行 → 属主个人层
    bind.execute(sa.text("""
        UPDATE carry_service_bindings b SET scope = 'user',
               scope_id = a.owner_user_id
        FROM service_aliases a
        WHERE a.alias_name = b.service_name
          AND a.owner_user_id IS NOT NULL
          AND b.scope = 'project'
    """))

    # ③ 换唯一键(scope 前缀;约束名沿用旧名 —— 与模型 create_all 同形)。
    # 同键冲突只可能来自防御分支的 scope_id=0 行:保留已挂靠行、删 0 行
    bind.execute(sa.text("SET CONSTRAINTS ALL IMMEDIATE"))
    if _has_unique_constraint(bind, "carry_service_bindings",
                              "uq_carry_svc_path"):
        op.drop_constraint("uq_carry_svc_path", "carry_service_bindings",
                           type_="unique")
    bind.execute(sa.text("""
        DELETE FROM carry_service_bindings b
        USING carry_service_bindings keep
        WHERE b.scope_id = 0 AND keep.scope_id <> 0
          AND b.service_name = keep.service_name
          AND b.field_path = keep.field_path
    """))
    bind.execute(sa.text(
        "ALTER TABLE carry_service_bindings ADD CONSTRAINT "
        "uq_carry_svc_path UNIQUE "
        "(scope, scope_id, service_name, field_path)"))
    if _has_unique_constraint(bind, "carry_global_defaults",
                              "uq_carry_default_path"):
        op.drop_constraint("uq_carry_default_path", "carry_global_defaults",
                           type_="unique")
    bind.execute(sa.text("""
        DELETE FROM carry_global_defaults d
        USING carry_global_defaults keep
        WHERE d.scope_id = 0 AND keep.scope_id <> 0
          AND d.field_path = keep.field_path
    """))
    bind.execute(sa.text(
        "ALTER TABLE carry_global_defaults ADD CONSTRAINT "
        "uq_carry_default_path UNIQUE (scope, scope_id, field_path)"))


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("SET CONSTRAINTS ALL IMMEDIATE"))
    # 公共层优先去重:非公共层行与公共层同键时丢弃
    # (个人配置不回落为全局,防越权扩大)
    bind.execute(sa.text("""
        DELETE FROM carry_service_bindings b
        USING carry_service_bindings keep, projects p
        WHERE keep.scope = 'project' AND keep.scope_id = p.id
          AND p.kind = 'public'
          AND (b.scope, b.scope_id) <> (keep.scope, keep.scope_id)
          AND b.service_name = keep.service_name
          AND b.field_path = keep.field_path
    """))
    bind.execute(sa.text("""
        DELETE FROM carry_global_defaults b
        USING carry_global_defaults keep, projects p
        WHERE keep.scope = 'project' AND keep.scope_id = p.id
          AND p.kind = 'public'
          AND (b.scope, b.scope_id) <> (keep.scope, keep.scope_id)
          AND b.field_path = keep.field_path
    """))
    bind.execute(sa.text(
        "ALTER TABLE carry_service_bindings DROP CONSTRAINT "
        "IF EXISTS uq_carry_svc_path"))
    bind.execute(sa.text(
        "ALTER TABLE carry_service_bindings ADD CONSTRAINT "
        "uq_carry_svc_path UNIQUE (service_name, field_path)"))
    bind.execute(sa.text(
        "ALTER TABLE carry_global_defaults DROP CONSTRAINT "
        "IF EXISTS uq_carry_default_path"))
    bind.execute(sa.text(
        "ALTER TABLE carry_global_defaults ADD CONSTRAINT "
        "uq_carry_default_path UNIQUE (field_path)"))
    for table in ("carry_service_bindings", "carry_global_defaults"):
        op.drop_column(table, "scope_id")
        op.drop_column(table, "scope")
