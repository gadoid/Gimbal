"""UPC-01(M1):Project 容器统一 —— private/public/normal 真实容器(v2.10 §4、§20)。

存量数据让位于架构:旧「project_id 空 = 私有区」的对象表语义随 M2 资源
迁移收口,本迁移先把 ``projects`` 表本身收敛为唯一容器事实源:

* 新列:``project_uid``(不可复用身份,gen_random_uuid 回填存量)、
  ``owner_id``(private 所有权;public/normal 恒空)、``is_default``
  (仅 private)、``status``(§13.1 生命周期);
* 约束:kind/形状/默认/状态 CHECK、每用户默认私有空间部分唯一索引、
  名称分域唯一(private 所有者域 / normal 平台域),全局 ``name`` 唯一
  随之退役(名称不是身份);
* 数据归一(依赖清理,§14.3 允许):每个非系统用户回填一个默认私有
  空间;活跃 normal 缺有效管理员的项目置 archived(§13「最后一个
  有效管理员离职前必须交接或归档」的迁移面收口);
* 触发器:``app.models.project.PROJECT_CONTAINER_DDL`` 单源
  (private/public 无成员行、kind 不可改、活跃 normal ≥1 有效 admin
  延迟约束、用户停用连带、非系统用户默认私有空间延迟约束)。

fresh 链(baseline 按当前模型 create_all)列/约束/索引天然就位,本迁移
守卫空转;触发器在 fresh 路径由 ``ensure_schema_sync`` 同单源补挂。
不提供 downgrade(0066 同款):目标形态即权威,回退 = 重新制造漂移。
"""
from alembic import op
import sqlalchemy as sa

revision = "0067_project_container"
down_revision = "0066_incremental_model_align"
branch_labels = None
depends_on = None

from app.models.project import PROJECT_CONTAINER_DDL  # noqa: E402


def _columns(bind, table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(bind).get_columns(table)}


def _drop_legacy_name_unique(bind) -> None:
    """退役全局唯一:单列 name 的唯一约束/索引(非部分索引)。

    模型历史上 ``name: mapped_column(String(128), unique=True)`` →
    create_all 落 ``projects_name_key`` 唯一约束;链上同形态。新契约按
    kind 分域唯一,全局唯一不再成立(不同用户可同名的私有空间)。
    """
    insp = sa.inspect(bind)
    for uc in insp.get_unique_constraints("projects"):
        if uc["column_names"] == ["name"]:
            op.drop_constraint(uc["name"], "projects", type_="unique")
    for ix in insp.get_indexes("projects"):
        if (ix["column_names"] == ["name"] and ix["unique"]
                and not ix.get("dialect_options", {}).get(
                    "postgresql.where")):
            op.drop_index(ix["name"], table_name="projects")


def _backfill_default_spaces() -> None:
    """每个非系统用户至少一个默认私有空间(§4 创建入口之一 = 迁移)。

    name/description 是 Python 侧 default,裸 SQL 必须显式给值;
    project_uid/status/is_default 有 server_default,显式写等值。
    """
    op.execute("""
        INSERT INTO projects
            (project_uid, name, kind, description, owner_id,
             is_default, status, created_at)
        SELECT gen_random_uuid(), '默认空间', 'private', '', u.id,
               true, 'active', now()
          FROM users u
         WHERE NOT u.is_system
           AND NOT EXISTS (
                SELECT 1 FROM projects p
                 WHERE p.kind = 'private' AND p.owner_id = u.id
                   AND p.is_default)
    """)


def _archive_unmanaged_normal_projects() -> None:
    """活跃 normal 无有效管理员 → archived(§20 不变量「活跃 Normal 至少
    一有效 Admin」的存量归一;归档可逆,处置路径 = 补管理员后恢复)。"""
    op.execute("""
        UPDATE projects p
           SET status = 'archived'
         WHERE p.kind = 'normal' AND p.status = 'active'
           AND NOT EXISTS (
                SELECT 1 FROM project_members m
                JOIN users u ON u.id = m.user_id
                 WHERE m.project_id = p.id AND m.role = 'admin'
                   AND u.is_active AND NOT u.is_system)
    """)


def upgrade() -> None:
    bind = op.get_bind()
    cols = _columns(bind, "projects")

    # ── 新列(fresh 链守卫:模型已建)──────────────────────────────
    with op.batch_alter_table("projects") as batch:
        if "project_uid" not in cols:
            batch.add_column(sa.Column(
                "project_uid", sa.Uuid(), nullable=False,
                server_default=sa.text("gen_random_uuid()")))
        if "owner_id" not in cols:
            batch.add_column(sa.Column("owner_id", sa.Integer(), nullable=True))
            batch.create_foreign_key(
                "fk_projects_owner", "users", ["owner_id"], ["id"])
        if "is_default" not in cols:
            batch.add_column(sa.Column(
                "is_default", sa.Boolean(), nullable=False,
                server_default=sa.text("false")))
        if "status" not in cols:
            batch.add_column(sa.Column(
                "status", sa.String(16), nullable=False,
                server_default=sa.text("'active'")))
    if "owner_id" not in cols:
        op.create_index("ix_projects_owner_id", "projects", ["owner_id"])

    # §13.2 不可复用身份的唯一性:模型声明 unique=True(create_all 落
    # UNIQUE 约束),增量分支此前只加列未加约束 —— 双路径结构漂移,
    # 链上补齐(守卫:已有同列唯一约束即空转)
    ucs = sa.inspect(bind).get_unique_constraints("projects")
    if not any(u["column_names"] == ["project_uid"] for u in ucs):
        # 命名随 create_all 自动名(<table>_<col>_key):UNIQUE 约束在 PG
        # 侧伴随同名唯一索引,§20.4 索引断言按名比较
        op.create_unique_constraint(
            "projects_project_uid_key", "projects", ["project_uid"])

    # ── 约束与索引(fresh 链由模型 create_all 就位;幂等守卫)────────
    _drop_legacy_name_unique(bind)
    insp = sa.inspect(bind)
    checks = {c["name"] for c in insp.get_check_constraints("projects")}
    if "ck_projects_kind" not in checks:
        op.create_check_constraint(
            "ck_projects_kind", "projects",
            "kind IN ('private', 'public', 'normal')")
    if "ck_projects_owner_shape" not in checks:
        op.create_check_constraint(
            "ck_projects_owner_shape", "projects",
            "(kind = 'private' AND owner_id IS NOT NULL) "
            "OR (kind <> 'private' AND owner_id IS NULL)")
    if "ck_projects_default_private" not in checks:
        op.create_check_constraint(
            "ck_projects_default_private", "projects",
            "NOT is_default OR kind = 'private'")
    if "ck_projects_status" not in checks:
        op.create_check_constraint(
            "ck_projects_status", "projects",
            "status IN ('active', 'archived', 'deleting', 'delete_failed')")
    indexes = {i["name"] for i in insp.get_indexes("projects")}
    if "uq_projects_private_default" not in indexes:
        op.create_index(
            "uq_projects_private_default", "projects", ["owner_id"],
            unique=True, postgresql_where=sa.text(
                "kind = 'private' AND is_default"))
    if "uq_projects_name_private" not in indexes:
        op.create_index(
            "uq_projects_name_private", "projects", ["owner_id", "name"],
            unique=True, postgresql_where=sa.text("kind = 'private'"))
    if "uq_projects_name_normal" not in indexes:
        op.create_index(
            "uq_projects_name_normal", "projects", ["name"],
            unique=True, postgresql_where=sa.text("kind = 'normal'"))
    if "ix_projects_kind" not in indexes:
        op.create_index("ix_projects_kind", "projects", ["kind"])

    # ── 存量归一(先于触发器,避免延迟约束在提交时击穿)────────────
    _backfill_default_spaces()
    _archive_unmanaged_normal_projects()

    # ── 触发器/函数(三路径单源)────────────────────────────────────
    for stmt in PROJECT_CONTAINER_DDL:
        op.execute(sa.text(stmt))
