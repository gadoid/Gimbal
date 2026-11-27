"""UPC(M3)§5/§11.2/§20:ExecConfig 单表显式互斥 FK —— principal_id /
project_id 恰一非空,两真实 FK + XOR CHECK;退役无外键的
(scope, scope_id) 多态列。

backfill:user 行 → principal_id = scope_id、project_id = NULL;
project 行反之。孤儿行(主体/项目已删的存量数据)先显式清理,
否则 FK 建不上 —— 与 0068 方案悬挂行「中止」不同:此处孤儿是
旧形状允许的合法残留(无外键时代的孤儿配置),清理属形状收编,
不携带业务语义。

时代守卫(与 0069 同纪律):fresh 链 baseline 按当前模型 create_all
—— 新形状列/约束/索引已天然就位,本迁移逐项按存在性守卫空转;
链路径(0053 建表形态)真实执行换形。§20.4 双路径终态一致由既有
断言套件验证(test_upc_dual_path 增列 exec_configs 对照)。
不提供 downgrade(0066+ 同款):目标形态即权威。
"""
from alembic import op
import sqlalchemy as sa

revision = "0070_exec_config_owner_fk"
down_revision = "0069_exec_config_scope_shape"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("exec_configs")}
    legacy = "scope" in cols

    # ── ① 加列(先于一切;回填基于旧列)────────────────────────────
    if "principal_id" not in cols:
        op.add_column("exec_configs",
                      sa.Column("principal_id", sa.Integer(), nullable=True))
    if "project_id" not in cols:
        op.add_column("exec_configs",
                      sa.Column("project_id", sa.Integer(), nullable=True))

    if legacy:
        # ── ② 回填(旧列 → 新列;恰一非空的形状由旧 scope 保证)─────
        op.execute("UPDATE exec_configs SET principal_id = scope_id "
                   "WHERE scope = 'user' AND principal_id IS NULL")
        op.execute("UPDATE exec_configs SET project_id = scope_id "
                   "WHERE scope = 'project' AND project_id IS NULL")
        # ── ③ 孤儿清理(无外键时代的合法残留;不按数值猜测,直接删除)
        op.execute("DELETE FROM exec_configs WHERE principal_id IS NOT NULL "
                   "AND principal_id NOT IN (SELECT id FROM users)")
        op.execute("DELETE FROM exec_configs WHERE project_id IS NOT NULL "
                   "AND project_id NOT IN (SELECT id FROM projects)")

    # ── ④ 真实 FK(命名显式 —— §20.4 按名比对;守卫幂等)────────────
    fks = {fk["name"] for fk in insp.get_foreign_keys("exec_configs")}
    if "fk_exec_configs_principal" not in fks:
        op.create_foreign_key("fk_exec_configs_principal", "exec_configs",
                              "users", ["principal_id"], ["id"],
                              ondelete="NO ACTION")
    if "fk_exec_configs_project" not in fks:
        op.create_foreign_key("fk_exec_configs_project", "exec_configs",
                              "projects", ["project_id"], ["id"],
                              ondelete="NO ACTION")

    # ── ⑤ XOR CHECK(替换 0069 的 scope 枚举闸)────────────────────
    checks = {c["name"] for c in insp.get_check_constraints("exec_configs")}
    if legacy and "ck_exec_configs_scope" in checks:
        op.drop_constraint("ck_exec_configs_scope", "exec_configs",
                           type_="check")
    if "ck_exec_configs_owner_shape" not in checks:
        op.create_check_constraint(
            "ck_exec_configs_owner_shape", "exec_configs",
            "(principal_id IS NULL) <> (project_id IS NULL)")

    # ── ⑥ 同侧唯一/默认部分唯一索引(守卫幂等)──────────────────────
    idx = {i["name"] for i in insp.get_indexes("exec_configs")}
    for name, columns, where, unique in (
        ("uq_exec_configs_principal_name", ["principal_id", "name"],
         "principal_id IS NOT NULL", True),
        ("uq_exec_configs_project_name", ["project_id", "name"],
         "project_id IS NOT NULL", True),
        ("uq_exec_configs_principal_default", ["principal_id"],
         "is_default AND principal_id IS NOT NULL", True),
        ("uq_exec_configs_project_default", ["project_id"],
         "is_default AND project_id IS NOT NULL", True),
        # 模型 index=True 的普通列索引(era 摘除 CASCADE 掉,链腿补挂)
        ("ix_exec_configs_principal_id", ["principal_id"], None, False),
        ("ix_exec_configs_project_id", ["project_id"], None, False),
    ):
        if name in idx:
            continue
        kw = {"unique": True, "postgresql_where": sa.text(where)} \
            if unique else {}
        op.create_index(name, "exec_configs", columns, **kw)

    # ── ⑦ 退役旧形状(唯一键/默认索引/CHECK/两列;仅旧形状链腿)────
    if legacy:
        if "uq_exec_configs_default" in idx:
            op.drop_index("uq_exec_configs_default", "exec_configs")
        uniques = {u["name"] for u in insp.get_unique_constraints(
            "exec_configs")}
        if "uq_exec_configs_scope_name" in uniques:
            op.drop_constraint("uq_exec_configs_scope_name", "exec_configs",
                               type_="unique")
        op.drop_column("exec_configs", "scope")
        op.drop_column("exec_configs", "scope_id")
