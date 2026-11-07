"""authz M2a S1.0:项目区数据模型(两表 + 对象表 project_id + 平台模板
标记 + 存量公开内容迁入公共项目)。

六步固定顺序(s1-detail §二;①–⑤ 见函数内注释,⑥ 是不做什么):
① ``projects`` / ``project_members`` 两表 + 公共项目种子(kind=public
   恰一行,NOT EXISTS 幂等 —— fresh 链 baseline 建表但不种数据,种子
   两条链都要跑;created_by 指 ``__platform__``,0015 保证其存在);
② 加列(全部可空 / 默认值)。``executions.project_id`` **无 FK**(对齐
   ``suite_id`` 先例:台账不随对象删除消失)且**存量不回填** —— 历史
   执行可见性保持「仅发起人」,与迁移前一致;
③ 存量公开内容迁入公共项目(S1-d 直接改归属不复制;payload 里的内置
   凭证与数据集敏感列**原样保留**,读面脱敏仍是这批行的唯一防线);
④ 平台模板标记:owner=``__platform__`` **∧ removed_at IS NULL** →
   ``is_platform_template``(软删挂靠行同属 ``__platform__``,必须靠
   removed_at 排除);
⑤ 删软删挂靠模板(D10:删用户时兜底挂到 ``__platform__`` 的行直接删)
   —— 先删其实例(template_id FK 无 ON DELETE 会拦;实例本就是
   「已移除」态死卡),软删的平台模板(步④已标记)保留。
   **④→⑤ 顺序不可倒**:先标记才能区分两类;
⑥ ``visibility`` 列本迁移不删:S1.1–S1.8 影子期(新写入同步维护),
   S1.9 / 0042 删列。

fresh 链(baseline 按当前模型建表,两表与列已存在):①② 守卫空转,
种子仍执行,③–⑤ 无存量自然空转。downgrade 还原 schema;步⑤删掉的
挂靠模板与实例不可还原(同 0038 口径:无消费面)。
"""
from alembic import op
import sqlalchemy as sa

revision = "0040_project_zone"
down_revision = "0039_drop_identity_mode"
branch_labels = None
depends_on = None

# 对象表:project_id 可空 FK(空 = 私有区);executions 除外(无 FK)
_ZONE_TABLES = ("composer_scenarios", "suites", "integration_tasks",
                "report_definitions")
_PID = "(SELECT id FROM projects WHERE kind = 'public')"
_PLATFORM = "(SELECT id FROM users WHERE username = '__platform__')"


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # ① 两表 + 公共项目种子
    if "projects" not in insp.get_table_names():
        op.create_table(
            "projects",
            sa.Column("id", sa.Integer(), primary_key=True),
            # 匿名 unique(与模型 unique=True 同路径,PG 自动命名 ——
            # fresh 链 baseline 与存量链本迁移落下的形状一致)
            sa.Column("name", sa.String(128), nullable=False, unique=True),
            sa.Column("kind", sa.String(16), nullable=False,
                      server_default="normal"),
            sa.Column("description", sa.Text(), nullable=False,
                      server_default=""),
            sa.Column("created_by", sa.Integer(),
                      sa.ForeignKey("users.id", ondelete="SET NULL"),
                      nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True),
                      nullable=False, server_default=sa.func.now()),
        )
        op.create_table(
            "project_members",
            sa.Column("project_id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), primary_key=True),
            sa.Column("role", sa.String(16), nullable=False,
                      server_default="member"),
            sa.Column("added_by", sa.Integer(),
                      sa.ForeignKey("users.id", ondelete="SET NULL"),
                      nullable=True),
            sa.Column("added_at", sa.DateTime(timezone=True),
                      nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(
                ["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["user_id"], ["users.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_projects_kind", "projects", ["kind"])
        # 公共项目恰一行(部分唯一;SQLite 面退化为普通唯一仅测试可见)
        op.create_index(
            "uq_projects_public_kind", "projects", ["kind"], unique=True,
            postgresql_where=sa.text("kind = 'public'"))
        op.create_index(
            "ix_project_members_user", "project_members", ["user_id"])
    # 种子(fresh 与存量链同一条语句,幂等)
    bind.execute(sa.text(
        "INSERT INTO projects (name, kind, description, created_by, "
        "created_at) SELECT '公共', 'public', '', " + _PLATFORM + ", now() "
        "WHERE NOT EXISTS (SELECT 1 FROM projects WHERE kind = 'public')"))

    # ② 加列(守卫:fresh 链 baseline 已带;索引/FK 名走自动命名,
    #    与模型 index=True / ForeignKey 落下的名字一致)
    for table in _ZONE_TABLES + ("executions",):
        if "project_id" in {c["name"] for c in insp.get_columns(table)}:
            continue
        op.add_column(table, sa.Column("project_id", sa.Integer(),
                                       nullable=True))
        op.create_index(f"ix_{table}_project_id", table, ["project_id"])
        if table != "executions":  # 台账快照无 FK(suite_id 先例)
            op.create_foreign_key(
                None, table, "projects", ["project_id"], ["id"])
    if "is_platform_template" not in {
            c["name"] for c in insp.get_columns("integration_tasks")}:
        op.add_column("integration_tasks", sa.Column(
            "is_platform_template", sa.Boolean(), nullable=False,
            server_default=sa.false()))

    # ③ 存量公开内容迁入公共项目(owner_id 不动 = 维护者;实例行
    #    template_id 非空不参与 —— 集成模板只迁模板行)
    for table in ("composer_scenarios", "suites", "report_definitions"):
        bind.execute(sa.text(
            f"UPDATE {table} SET project_id = {_PID} "
            "WHERE visibility = 'public' AND project_id IS NULL"))
    bind.execute(sa.text(
        "UPDATE integration_tasks SET project_id = " + _PID +
        " WHERE template_id IS NULL AND visibility = 'public' "
        "AND project_id IS NULL"))

    # ④ 平台模板标记(removed_at IS NULL 排除软删挂靠行)
    bind.execute(sa.text(
        "UPDATE integration_tasks SET is_platform_template = true "
        "WHERE template_id IS NULL AND removed_at IS NULL "
        "AND owner_id = " + _PLATFORM))

    # ⑤ 删软删挂靠模板:先删其实例(FK 无 ON DELETE 会拦),再删模板
    #   (未标记的 __platform__ 软删行;软删的平台模板步④已标记,保留)
    bind.execute(sa.text(
        "DELETE FROM integration_tasks WHERE template_id IN ("
        "  SELECT id FROM integration_tasks"
        "  WHERE template_id IS NULL AND removed_at IS NOT NULL "
        "  AND is_platform_template = false"
        "  AND owner_id = " + _PLATFORM + ")"))
    bind.execute(sa.text(
        "DELETE FROM integration_tasks"
        " WHERE template_id IS NULL AND removed_at IS NOT NULL "
        " AND is_platform_template = false"
        " AND owner_id = " + _PLATFORM))


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    # ③ 的反向:公开内容退回「visibility 影子」判定(列仍在且值未动,
    # 行为回到 0039 代码的读法);普通项目内容随两表删除一并失去挂靠
    for table in _ZONE_TABLES + ("executions",):
        bind.execute(sa.text(f"UPDATE {table} SET project_id = NULL"))
    for table in _ZONE_TABLES + ("executions",):
        if "project_id" not in {c["name"] for c in insp.get_columns(table)}:
            continue
        op.drop_index(f"ix_{table}_project_id", table_name=table)
        if table != "executions":  # 匿名 FK:按定义找名再删
            fks = [f["name"] for f in insp.get_foreign_keys(table)
                   if f["referred_table"] == "projects"]
            for name in fks:
                op.drop_constraint(name, table, type_="foreignkey")
        op.drop_column(table, "project_id")
    if "is_platform_template" in {
            c["name"] for c in insp.get_columns("integration_tasks")}:
        op.drop_column("integration_tasks", "is_platform_template")
    # ① 反向:两表删除(公共项目行随之;步⑤删掉的挂靠模板不可还原)
    op.drop_table("project_members")
    op.drop_table("projects")
