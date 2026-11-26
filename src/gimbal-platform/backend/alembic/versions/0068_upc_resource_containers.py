"""UPC-02(M2):资源容器收口 —— 真实 project_id + §20.2/§20.6 复合 FK +
Scheme 绑定显式列与修复状态 + AccountCombo 落表(v2.10 §5、§16.1、§20)。

存量数据让位于架构设计(§14.3:DDL 迁移允许按依赖清理旧测试数据,
不要求恢复其内容):

* **对象表 ``project_id`` 非空真实 FK**(§5/AC-04):旧「project_id
  空 = 私有区」语义退役 —— 私有区内容回填到**所有者的默认私有空间**
  (0067 已就位);无主/无空间的孤儿行按依赖清理(数据集/方案/成员/
  端点引用/收藏先行收口)。
* **AccountCombo 落表**(§5/§20.2):``project_id NOT NULL FK``、
  项目内名称唯一、每项目至多一个默认(部分唯一索引)、``(project_id,
  id)`` 候选键。
* **§20.2 Scheme 双复合 FK**:``composer_run_schemes`` 新增从父场景
  派生的 ``project_id`` 校验键 + ``account_combo_id`` 显式绑定列 +
  ``scheme_uid`` 不可复用身份 + §20.3 修复状态(``ck_scheme_combo_repair``)
  + ``revision`` 乐观锁;旧单列 scenario FK 退役(复合边完全覆盖)。
* **§20.6 SuiteMember 双父同区**:``suite_members`` 增非空
  ``project_id`` + 两条复合外键(DEFERRABLE INITIALLY IMMEDIATE,
  CASCADE 收口),**取代** 0042 同区触发器与旧单列外键;suites 名称
  唯一换轴 ``UNIQUE(project_id, name)`` + ``(project_id, id)`` 候选键。
* **§20.5 中止闸**:升级前检查 ``composer_run_schemes.payload`` 有无
  非空 ``accountComboId`` 的旧 JSON 绑定证据 —— main 主线无此契约,
  发现即**终止并回滚整笔**(AC-43:不得按默认组合或数值 ID 猜测)。
* **integration_tasks 归属形状 CHECK**:模板行必须挂真实项目(§5
  「IntegrationTemplate project_id NOT NULL」的 M2 落法;实例行恒空,
  principal 域对象 —— 拆表随后续阶段)。

fresh 链(baseline 按当前模型 create_all)列/约束/索引天然就位,本迁移
守卫空转;复合 FK 在链路径由 0042 先挂的同区触发器(恒在本步摘除)让
位于结构约束,两路径终态一致(§20.4 双路径断言验证)。
不提供 downgrade(0066/0067 同款):目标形态即权威,回退 = 重新制造漂移。
"""
from alembic import op
import sqlalchemy as sa

revision = "0068_upc_resource_containers"
down_revision = "0067_project_container"
branch_labels = None
depends_on = None


def _columns(bind, table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(bind).get_columns(table)}


def _indexes(bind, table: str) -> set[str]:
    return {i["name"] for i in sa.inspect(bind).get_indexes(table)}


def _constraints(bind, table: str) -> set[str]:
    insp = sa.inspect(bind)
    names = {c["name"] for c in insp.get_check_constraints(table)}
    names |= {u["name"] for u in insp.get_unique_constraints(table)}
    names |= {i["name"] for i in insp.get_indexes(table)}
    return {n for n in names if n}


def _fk_names(bind, table: str) -> set[str]:
    return {f["name"] for f in sa.inspect(bind).get_foreign_keys(table)
            if f["name"]}


def _has_table(bind, name: str) -> bool:
    return sa.inspect(bind).has_table(name)


# ── §20.5 中止闸:旧 JSON 绑定证据 → 整笔回滚 ─────────────────────

def _guard_no_legacy_binding_evidence(bind) -> None:
    """main 主线无持久化组合绑定契约;payload 里的非空 accountComboId
    是异常输入(§20.5)—— 终止并报告数量,保留原始数据供显式处置,
    不按默认组合或数值 ID 猜测。异常抛出即整笔回滚。"""
    n = bind.execute(sa.text("""
        SELECT count(*) FROM composer_run_schemes
         WHERE payload ? 'accountComboId'
           AND payload->>'accountComboId' IS NOT NULL
           AND payload->>'accountComboId' <> 'null'
    """)).scalar_one()
    if n:
        raise RuntimeError(
            f"upc_0068_legacy_binding_evidence: 发现 {n} 行 "
            "composer_run_schemes.payload 携带非空 accountComboId —— "
            "非主线绑定证据(§20.5),迁移终止并回滚;请显式处置后再升级")


# ── 孤儿场景清理(§14.3 依赖清理;顺序 = 引用者先走)──────────────────

def _orphan_scenario_ids(bind) -> list[str]:
    """不可归位的场景(无主,或所有者无默认私有空间 —— 例如系统用户)。
    主线数据均可达其所有者默认空间,这里只是防御性收口。"""
    rows = bind.execute(sa.text("""
        SELECT cs.scenario_id FROM composer_scenarios cs
         WHERE cs.project_id IS NULL
           AND NOT EXISTS (
                SELECT 1 FROM projects p
                 WHERE p.kind = 'private' AND p.is_default
                   AND p.owner_id = cs.owner_id)
    """)).scalars().all()
    return list(rows)


def _purge_orphan_scenarios(bind, orphan_ids: list[str]) -> None:
    if not orphan_ids:
        return
    ids = tuple(orphan_ids)
    in_clause = ", ".join(f"'{s.replace(chr(39), chr(39)*2)}'" for s in ids)
    # 依赖清理顺序:方案(NO ACTION)→ 端点引用(NO ACTION)→ 数据集
    # (NO ACTION)→ 成员行(级联亦可,显式删保序)→ 收藏(CASCADE 兜底)
    for sql in (
        f"DELETE FROM composer_run_schemes WHERE scenario_id IN ({in_clause})",
        f"DELETE FROM scenario_endpoint_refs WHERE scenario_id IN ({in_clause})",
        f"DELETE FROM composer_data_sets WHERE scenario_id IN ({in_clause})",
        f"DELETE FROM suite_members WHERE scenario_id IN ({in_clause})",
        f"DELETE FROM user_stars WHERE scenario_id IN ({in_clause})",
        f"DELETE FROM composer_scenarios WHERE scenario_id IN ({in_clause})",
    ):
        bind.execute(sa.text(sql))


# ── 回填:旧「空 = 私有区」→ 所有者默认私有空间 ──────────────────────

def _backfill_scenarios(bind) -> None:
    _purge_orphan_scenarios(bind, _orphan_scenario_ids(bind))
    bind.execute(sa.text("""
        UPDATE composer_scenarios cs
           SET project_id = p.id
          FROM users u
          JOIN projects p
            ON p.kind = 'private' AND p.is_default AND p.owner_id = u.id
         WHERE cs.project_id IS NULL
           AND cs.owner_id = u.id
    """))
    # 残余(无主场景:owner_id NULL 的历史形态)→ 依赖清理后删除
    for sql in (
        "DELETE FROM composer_run_schemes WHERE scenario_id IN ("
        " SELECT scenario_id FROM composer_scenarios"
        "  WHERE project_id IS NULL)",
        "DELETE FROM scenario_endpoint_refs WHERE scenario_id IN ("
        " SELECT scenario_id FROM composer_scenarios"
        "  WHERE project_id IS NULL)",
        "DELETE FROM composer_data_sets WHERE scenario_id IN ("
        " SELECT scenario_id FROM composer_scenarios"
        "  WHERE project_id IS NULL)",
        "DELETE FROM suite_members WHERE scenario_id IN ("
        " SELECT scenario_id FROM composer_scenarios"
        "  WHERE project_id IS NULL)",
        "DELETE FROM user_stars WHERE scenario_id IN ("
        " SELECT scenario_id FROM composer_scenarios"
        "  WHERE project_id IS NULL)",
        "DELETE FROM composer_scenarios WHERE project_id IS NULL",
    ):
        bind.execute(sa.text(sql))


def _backfill_suites(bind) -> None:
    # 套件 owner_id 恒非空;不可达默认空间的属主 → 清理套件与其成员
    bind.execute(sa.text("""
        DELETE FROM suite_members WHERE suite_id IN (
            SELECT s.id FROM suites s
             WHERE s.project_id IS NULL
               AND NOT EXISTS (
                    SELECT 1 FROM projects p
                     WHERE p.kind = 'private' AND p.is_default
                       AND p.owner_id = s.owner_id))
    """))
    bind.execute(sa.text("""
        DELETE FROM suites WHERE project_id IS NULL
           AND NOT EXISTS (
                SELECT 1 FROM projects p
                 WHERE p.kind = 'private' AND p.is_default
                   AND p.owner_id = suites.owner_id)
    """))
    bind.execute(sa.text("""
        UPDATE suites s
           SET project_id = p.id
          FROM projects p
         WHERE s.project_id IS NULL
           AND p.kind = 'private' AND p.is_default
           AND p.owner_id = s.owner_id
    """))
    if bind.execute(sa.text(
            "SELECT 1 FROM suites WHERE project_id IS NULL LIMIT 1"
    )).scalar_one_or_none() is not None:
        raise RuntimeError(
            "upc_0068_suite_unplaceable: 存在无法归位的 suite"
            "(所有者无默认私有空间);请显式处置后再升级")


def _backfill_report_definitions(bind) -> None:
    # 遗留无主公共行(owner NULL)在 0037/0041 已挂公共项目;残留
    # owner 非空的私有行回填默认空间;仍无归位的按依赖清理
    bind.execute(sa.text("""
        UPDATE report_definitions rd
           SET project_id = p.id
          FROM projects p
         WHERE rd.project_id IS NULL
           AND p.kind = 'private' AND p.is_default
           AND p.owner_id = rd.owner_id
    """))
    bind.execute(sa.text(
        "DELETE FROM report_definitions WHERE project_id IS NULL"))


def _backfill_integration_templates(bind) -> None:
    """模板行归位:平台/系统用户的模板 → 公共项目(平台模板本就公开
    共享);真人模板 → 默认私有空间。实例行恒空(principal 域)。"""
    bind.execute(sa.text("""
        UPDATE integration_tasks it
           SET project_id = p.id
          FROM projects p
         WHERE it.template_id IS NULL AND it.project_id IS NULL
           AND p.kind = 'public'
           AND EXISTS (SELECT 1 FROM users u
                        WHERE u.id = it.owner_id AND u.is_system)
    """))
    bind.execute(sa.text("""
        UPDATE integration_tasks it
           SET project_id = p.id
          FROM projects p
         WHERE it.template_id IS NULL AND it.project_id IS NULL
           AND p.kind = 'private' AND p.is_default
           AND p.owner_id = it.owner_id
    """))
    # 实例行(有 template_id)恒空 —— 显式归一,防历史脏行
    bind.execute(sa.text("""
        UPDATE integration_tasks SET project_id = NULL
         WHERE template_id IS NOT NULL
    """))
    if bind.execute(sa.text(
            "SELECT 1 FROM integration_tasks WHERE template_id IS NULL "
            "AND project_id IS NULL LIMIT 1"
    )).scalar_one_or_none() is not None:
        raise RuntimeError(
            "upc_0068_template_unplaceable: 存在无法归位的集成模板"
            "(所有者无默认私有空间/公共项目缺失);请显式处置后再升级")


# ── FK 工具 ─────────────────────────────────────────────────────

def _drop_single_column_fks(bind, table: str,
                            by_columns: list[list[str]]) -> None:
    """按受限列集合删除单列 FK(名字可能是 PG 自动命名;定义等价即删)。"""
    for fk in sa.inspect(bind).get_foreign_keys(table):
        cols = list(fk.get("constrained_columns") or [])
        if cols in by_columns and fk["name"]:
            op.drop_constraint(fk["name"], table, type_="foreignkey")


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # ⓪ 预存在漂移收口(§20.4 扩大断言面后浮出):0003 的三个 trgm
    # 检索索引只在链上、不在模型(模型注释:M3 检索 SQL 化时按需再补
    # trgm)—— 按 0066「链收敛到模型」纪律摘除,双路径结构一致
    for ix in ("ix_composer_name_trgm", "ix_composer_sid_trgm",
               "ix_composer_description_trgm"):
        bind.execute(sa.text(f"DROP INDEX IF EXISTS {ix}"))

    # ① §20.5 中止闸(整笔回滚的权威位置)
    _guard_no_legacy_binding_evidence(bind)

    # ② account_combos 落表(fresh 链 create_all 已就位)
    if not _has_table(bind, "account_combos"):
        op.create_table(
            "account_combos",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("project_id", sa.Integer(),
                      sa.ForeignKey("projects.id"), nullable=False),
            sa.Column("name", sa.String(64), nullable=False),
            sa.Column("description", sa.Text(), nullable=False,
                      server_default=""),
            sa.Column("is_default", sa.Boolean(), nullable=False,
                      server_default=sa.text("false")),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("revision", sa.Integer(), nullable=False,
                      server_default=sa.text("1")),
            sa.Column("updated_by_id", sa.Integer(),
                      sa.ForeignKey("users.id", ondelete="SET NULL"),
                      nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True),
                      nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True),
                      nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("project_id", "name",
                                name="uq_account_combos_project_name"),
        )
        op.create_index("ix_account_combos_project", "account_combos",
                        ["project_id"])
        # §20.2 复合 FK 目标候选键 + 每项目默认唯一(部分索引)
        op.create_index("uq_combo_project_id", "account_combos",
                        ["project_id", "id"], unique=True)
        op.create_index(
            "uq_account_combos_default", "account_combos", ["project_id"],
            unique=True, postgresql_where=sa.text("is_default"))

    # ③ 对象表归属回填 + NOT NULL(顺序:场景 → 套件 → 报告 → 模板)
    _backfill_scenarios(bind)
    _backfill_suites(bind)
    _backfill_report_definitions(bind)
    _backfill_integration_templates(bind)

    scen_cols = _columns(bind, "composer_scenarios")
    if "project_id" in scen_cols:
        col = {c["name"]: c for c in insp.get_columns("composer_scenarios")}
        if col["project_id"]["nullable"]:
            op.alter_column("composer_scenarios", "project_id",
                            nullable=False)
        if "uq_scenario_project_scenario_id" not in _indexes(
                bind, "composer_scenarios"):
            op.create_index("uq_scenario_project_scenario_id",
                            "composer_scenarios",
                            ["project_id", "scenario_id"], unique=True)

    suite_c = _columns(bind, "suites")
    if "project_id" in suite_c:
        col = {c["name"]: c for c in insp.get_columns("suites")}
        if col["project_id"]["nullable"]:
            op.alter_column("suites", "project_id", nullable=False)
        if "uq_suites_owner_name" in _indexes(bind, "suites"):
            op.drop_index("uq_suites_owner_name", table_name="suites")
        if "uq_suites_project_name" not in _constraints(bind, "suites"):
            op.create_unique_constraint("uq_suites_project_name", "suites",
                                        ["project_id", "name"])
        if "uq_suites_project_id" not in _indexes(bind, "suites"):
            op.create_index("uq_suites_project_id", "suites",
                            ["project_id", "id"], unique=True)

    rd_col = {c["name"]: c for c in insp.get_columns("report_definitions")}
    if rd_col["project_id"]["nullable"]:
        op.alter_column("report_definitions", "project_id", nullable=False)

    if "ck_integration_task_shape" not in _constraints(
            bind, "integration_tasks"):
        op.create_check_constraint(
            "ck_integration_task_shape", "integration_tasks",
            "(template_id IS NULL AND project_id IS NOT NULL) "
            "OR (template_id IS NOT NULL AND project_id IS NULL)")

    # ④ §20.6 suite_members:非空校验键 + 双复合 FK,取代触发器与单列 FK
    sm_cols = _columns(bind, "suite_members")
    if "project_id" not in sm_cols:
        op.add_column("suite_members",
                     sa.Column("project_id", sa.Integer(), nullable=True))
    # 先摘同区触发器与单列 FK(复合 FK 取代;fresh 路径本就无)。
    # 必须先于回填 UPDATE:单列 FK 是 DEFERRABLE INITIALLY DEFERRED,
    # 回填会排队挂起触发事件,阻塞随后的 SET NOT NULL ALTER
    bind.execute(sa.text(
        "DROP TRIGGER IF EXISTS trg_suite_member_same_zone ON suite_members"))
    _drop_single_column_fks(bind, "suite_members",
                            [["suite_id"], ["scenario_id"]])
    # 回填自套件;核验两端一致(旧触发器期外的脏行 → 阻止提交,§20.6)
    bind.execute(sa.text("""
        UPDATE suite_members sm
           SET project_id = s.project_id
          FROM suites s
         WHERE s.id = sm.suite_id
    """))
    bad = bind.execute(sa.text("""
        SELECT count(*) FROM suite_members sm
         WHERE sm.project_id IS NULL
            OR sm.project_id <> (
                SELECT cs.project_id FROM composer_scenarios cs
                 WHERE cs.scenario_id = sm.scenario_id)
    """)).scalar_one()
    if bad:
        raise RuntimeError(
            f"upc_0068_suite_member_zone: 存在 {bad} 行跨区/无区 "
            "suite_members(§20.6 迁移前置核验:须从父对象回填并核验"
            "两端项目一致后才能建立复合 FK)")
    col = {c["name"]: c for c in
           sa.inspect(bind).get_columns("suite_members")}
    if col["project_id"]["nullable"]:
        op.alter_column("suite_members", "project_id", nullable=False)
    # 摘除同区触发器(复合 FK 取代;fresh 路径本就无)
    bind.execute(sa.text(
        "DROP TRIGGER IF EXISTS trg_suite_member_same_zone ON suite_members"))
    _drop_single_column_fks(bind, "suite_members",
                            [["suite_id"], ["scenario_id"]])
    sm_fks = _fk_names(bind, "suite_members")
    if "fk_suite_members_suite_zone" not in sm_fks:
        op.create_foreign_key(
            "fk_suite_members_suite_zone", "suite_members", "suites",
            ["project_id", "suite_id"], ["project_id", "id"],
            ondelete="CASCADE", onupdate="NO ACTION",
            deferrable=True, initially="IMMEDIATE")
    if "fk_suite_members_scenario_zone" not in sm_fks:
        op.create_foreign_key(
            "fk_suite_members_scenario_zone", "suite_members",
            "composer_scenarios",
            ["project_id", "scenario_id"],
            ["project_id", "scenario_id"],
            ondelete="CASCADE", onupdate="NO ACTION",
            deferrable=True, initially="IMMEDIATE")

    # ⑤ §20.2 composer_run_schemes:派生归属 + 显式绑定 + UID + 修复状态
    rs_cols = _columns(bind, "composer_run_schemes")
    if "scheme_uid" not in rs_cols:
        op.add_column("composer_run_schemes", sa.Column(
            "scheme_uid", sa.Uuid(), nullable=False,
            server_default=sa.func.gen_random_uuid()))
    if "project_id" not in rs_cols:
        op.add_column("composer_run_schemes",
                     sa.Column("project_id", sa.Integer(), nullable=True))
    if "account_combo_id" not in rs_cols:
        op.add_column("composer_run_schemes",
                     sa.Column("account_combo_id", sa.Integer(),
                               nullable=True))
    if "repair_status" not in rs_cols:
        op.add_column("composer_run_schemes", sa.Column(
            "repair_status", sa.String(16), nullable=False,
            server_default="ready"))
    if "repair_reason" not in rs_cols:
        op.add_column("composer_run_schemes", sa.Column(
            "repair_reason", sa.String(32), nullable=True))
    if "revision" not in rs_cols:
        op.add_column("composer_run_schemes", sa.Column(
            "revision", sa.Integer(), nullable=False,
            server_default=sa.text("1")))
    # §20.2:复合边取代单列 scenario FK(定义等价即删,含 PG 自动名)。
    # 必须先于回填 UPDATE:0066 期的单列 FK 是 DEFERRABLE INITIALLY
    # DEFERRED,回填会排队挂起触发事件,导致随后的 SET NOT NULL
    # ALTER 以 ObjectInUse 拒绝(PG「pending trigger events」)
    _drop_single_column_fks(bind, "composer_run_schemes", [["scenario_id"]])
    # 归属回填:从父场景派生(§20.2;方案不独立选区)
    bind.execute(sa.text("""
        UPDATE composer_run_schemes r
           SET project_id = cs.project_id
          FROM composer_scenarios cs
         WHERE cs.scenario_id = r.scenario_id AND r.project_id IS NULL
    """))
    dangling = bind.execute(sa.text("""
        SELECT count(*) FROM composer_run_schemes r
         WHERE r.project_id IS NULL
    """)).scalar_one()
    if dangling:
        raise RuntimeError(
            f"upc_0068_scheme_unplaceable: 存在 {dangling} 行无法从"
            "父场景派生 project_id 的方案(悬挂方案);请显式处置后再升级")
    col = {c["name"]: c for c in
           sa.inspect(bind).get_columns("composer_run_schemes")}
    if col["project_id"]["nullable"]:
        op.alter_column("composer_run_schemes", "project_id", nullable=False)
    rs_fks = _fk_names(bind, "composer_run_schemes")
    if "fk_scheme_scenario_zone" not in rs_fks:
        op.create_foreign_key(
            "fk_scheme_scenario_zone", "composer_run_schemes",
            "composer_scenarios",
            ["project_id", "scenario_id"],
            ["project_id", "scenario_id"],
            ondelete="NO ACTION", deferrable=True, initially="IMMEDIATE")
    if "fk_scheme_combo_zone" not in rs_fks:
        op.create_foreign_key(
            "fk_scheme_combo_zone", "composer_run_schemes", "account_combos",
            ["project_id", "account_combo_id"], ["project_id", "id"],
            ondelete="NO ACTION", deferrable=True, initially="IMMEDIATE")
    rs_ix = _indexes(bind, "composer_run_schemes")
    if "ix_scheme_combo_zone" not in rs_ix:
        op.create_index("ix_scheme_combo_zone", "composer_run_schemes",
                        ["project_id", "account_combo_id"])
    if "ix_scheme_scenario_zone" not in rs_ix:
        op.create_index("ix_scheme_scenario_zone", "composer_run_schemes",
                        ["project_id", "scenario_id"])
    if "ck_scheme_combo_repair" not in _constraints(
            bind, "composer_run_schemes"):
        op.create_check_constraint(
            "ck_scheme_combo_repair", "composer_run_schemes",
            "(repair_status = 'ready' AND repair_reason IS NULL) "
            "OR (repair_status = 'blocked' AND account_combo_id IS NULL "
            "AND repair_reason IS NOT NULL AND repair_reason IN ("
            "'combo_missing', 'combo_cross_zone', "
            "'combo_dependency_invalid'))")

    # ⑥ §20.3 审计事件 + 受限诊断记录 + §14.2 幂等台账(fresh 已就位)
    if not _has_table(bind, "scheme_repair_events"):
        op.create_table(
            "scheme_repair_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("scheme_id", sa.String(128), nullable=False),
            sa.Column("scheme_uid", sa.Uuid(), nullable=False),
            sa.Column("project_id", sa.Integer(), nullable=False),
            sa.Column("action", sa.String(32), nullable=False),
            sa.Column("old_status", sa.String(16)),
            sa.Column("new_status", sa.String(16)),
            sa.Column("old_reason", sa.String(32)),
            sa.Column("new_reason", sa.String(32)),
            sa.Column("old_combo_id", sa.Integer()),
            sa.Column("new_combo_id", sa.Integer()),
            sa.Column("old_revision", sa.Integer()),
            sa.Column("new_revision", sa.Integer()),
            sa.Column("source_combo_ref", sa.Text()),
            sa.Column("resolved_combo_id", sa.Integer()),
            sa.Column("resolved_project_id", sa.Integer()),
            sa.Column("reason", sa.Text()),
            sa.Column("request_id", sa.String(128)),
            sa.Column("actor_id", sa.Integer()),
            sa.Column("actor_name", sa.String(128), nullable=False,
                      server_default=""),
            sa.Column("created_at", sa.DateTime(timezone=True),
                      nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_scheme_repair_events_scheme",
                        "scheme_repair_events", ["scheme_id", "id"])
    if not _has_table(bind, "scheme_repair_diagnosis"):
        op.create_table(
            "scheme_repair_diagnosis",
            sa.Column("scheme_id", sa.String(128), primary_key=True),
            sa.Column("source_combo_ref", sa.Text()),
            sa.Column("resolved_combo_id", sa.Integer()),
            sa.Column("resolved_project_id", sa.Integer()),
            sa.Column("updated_at", sa.DateTime(timezone=True),
                      nullable=False, server_default=sa.func.now()),
        )
    if not _has_table(bind, "scenario_asset_imports"):
        op.create_table(
            "scenario_asset_imports",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("project_id", sa.Integer(),
                      sa.ForeignKey("projects.id"), nullable=False),
            sa.Column("package_id", sa.String(128), nullable=False),
            sa.Column("source_scenario_id", sa.String(128), nullable=False),
            sa.Column("request_digest", sa.String(64), nullable=False),
            sa.Column("restored_scenario_id", sa.String(128),
                      nullable=False),
            sa.Column("restored_scheme_ids", sa.JSON(), nullable=False),
            sa.Column("default_scheme_id", sa.String(128)),
            sa.Column("report", sa.JSON(), nullable=False),
            sa.Column("notes", sa.Text()),
            sa.Column("created_by", sa.Integer(),
                      sa.ForeignKey("users.id", ondelete="SET NULL")),
            sa.Column("created_at", sa.DateTime(timezone=True),
                      nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("project_id", "package_id",
                                "source_scenario_id",
                                name="uq_scenario_import_key"),
        )
        op.create_index("ix_scenario_imports_project",
                        "scenario_asset_imports", ["project_id"])
