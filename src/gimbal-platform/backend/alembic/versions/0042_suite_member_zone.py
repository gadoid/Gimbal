"""authz M2a S1.5:suite_members 同区约束取代同属主组合外键。

顺序固定:
① 拆旧:删两条同属主组合外键(fk_suite_members_suite / _scenario,
   (suite_id, owner_id) / (scenario_id, owner_id) → 目标唯一索引)、
   删冗余 owner_id 列、删两个纯 FK 目标唯一索引(uq_suites_id_owner /
   uq_composer_sid_owner);
② 建新:两条**简化** FK —— suite_id → suites.id(CASCADE,套件删除收
   成员)、scenario_id → composer_scenarios.scenario_id(CASCADE
   DEFERRED,保持原删除顺序容错)—— 级联语义与旧组合 FK 一致;
③ 同区触发器:INSERT/UPDATE 时校验「成员与套件同 project_id;同空
   (私有区)时同属主」—— 应用层单点 zone.ensure_member_same_zone
   先行给 422,触发器兜底绕过应用层的直插。

fresh 链(baseline 按当前模型建表):①② 的对象已不存在/已就位,
全部守卫空转;③ 恒执行(幂等)。downgrade 还原组合外键形态 ——
owner_id 按「成员场景属主」回填(跨属主项目成员回填后违反套件侧
组合外键,downgrade 对 S1.5 后数据不保证成功,注释声明)。
"""
from alembic import op
import sqlalchemy as sa

revision = "0042_suite_member_zone"
down_revision = "0041_public_shadow_backfill"
branch_labels = None
depends_on = None

_TRIGGER_FN = "suite_member_same_zone"
_TRIGGER = "trg_suite_member_same_zone"


def _fk_names(bind, table: str) -> set[str]:
    insp = sa.inspect(bind)
    return {f["name"] for f in insp.get_foreign_keys(table) if f["name"]}


def _has_column(bind, table: str, column: str) -> bool:
    return column in {c["name"] for c in sa.inspect(bind).get_columns(table)}


def _has_index(bind, table: str, index: str) -> bool:
    return index in {i["name"] for i in sa.inspect(bind).get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()

    # ① 拆旧(守卫:fresh 链已无)
    for name in _fk_names(bind, "suite_members"):
        if name in ("fk_suite_members_suite", "fk_suite_members_scenario"):
            op.drop_constraint(name, "suite_members", type_="foreignkey")
    if _has_column(bind, "suite_members", "owner_id"):
        op.drop_column("suite_members", "owner_id")
    if _has_index(bind, "suites", "uq_suites_id_owner"):
        op.drop_index("uq_suites_id_owner", table_name="suites")
    if _has_index(bind, "composer_scenarios", "uq_composer_sid_owner"):
        op.drop_index("uq_composer_sid_owner", table_name="composer_scenarios")

    # ② 简化 FK(守卫:fresh 链 create_all 已建同名形态)
    fks = _fk_names(bind, "suite_members")
    if "fk_suite_members_suite_id" not in fks:
        op.create_foreign_key(
            "fk_suite_members_suite_id", "suite_members", "suites",
            ["suite_id"], ["id"], ondelete="CASCADE")
    if "fk_suite_members_scenario_id" not in fks:
        op.create_foreign_key(
            "fk_suite_members_scenario_id", "suite_members",
            "composer_scenarios", ["scenario_id"], ["scenario_id"],
            ondelete="CASCADE", deferrable=True, initially="DEFERRED")

    # ③ 同区触发器(幂等;fresh 与存量链都要;DDL 单源 zone 单点)
    from app.services.zone import SUITE_ZONE_TRIGGER_DDL

    for stmt in SUITE_ZONE_TRIGGER_DDL:
        bind.execute(sa.text(stmt))


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text(f"DROP TRIGGER IF EXISTS {_TRIGGER} ON suite_members"))
    bind.execute(sa.text(f"DROP FUNCTION IF EXISTS {_TRIGGER_FN}()"))

    fks = _fk_names(bind, "suite_members")
    for name in ("fk_suite_members_suite_id", "fk_suite_members_scenario_id"):
        if name in fks:
            op.drop_constraint(name, "suite_members", type_="foreignkey")
    if not _has_column(bind, "suite_members", "owner_id"):
        op.add_column("suite_members", sa.Column(
            "owner_id", sa.Integer(), nullable=True))
        # 回填:成员场景的属主(组合外键要求与场景行一致;跨属主的
        # 项目成员回填后违反套件侧组合外键 —— S1.5 后数据不保证可
        # downgrade,生产回滚走备份恢复口径)
        bind.execute(sa.text("""
            UPDATE suite_members sm
            SET owner_id = cs.owner_id
            FROM composer_scenarios cs
            WHERE cs.scenario_id = sm.scenario_id
        """))
    # 孤儿防御 + 兜底回填(套件属主)后 NOT NULL 化
    bind.execute(sa.text("""
        DELETE FROM suite_members sm
        WHERE sm.owner_id IS NULL
          AND NOT EXISTS (SELECT 1 FROM suites s WHERE s.id = sm.suite_id)
    """))
    bind.execute(sa.text("""
        UPDATE suite_members sm SET owner_id = s.owner_id
        FROM suites s WHERE s.id = sm.suite_id AND sm.owner_id IS NULL
    """))
    bind.execute(sa.text("""
        DELETE FROM suite_members WHERE owner_id IS NULL
    """))
    op.alter_column("suite_members", "owner_id", nullable=False)
    # 先建组合外键的目标唯一索引,再建组合外键(顺序:索引 → 外键)
    if not _has_index(bind, "suites", "uq_suites_id_owner"):
        op.create_index("uq_suites_id_owner", "suites", ["id", "owner_id"],
                        unique=True)
    if not _has_index(bind, "composer_scenarios", "uq_composer_sid_owner"):
        op.create_index("uq_composer_sid_owner", "composer_scenarios",
                        ["scenario_id", "owner_id"], unique=True)
    op.create_foreign_key(
        "fk_suite_members_suite", "suite_members", "suites",
        ["suite_id", "owner_id"], ["id", "owner_id"],
        ondelete="CASCADE", deferrable=True, initially="DEFERRED")
    op.create_foreign_key(
        "fk_suite_members_scenario", "suite_members", "composer_scenarios",
        ["scenario_id", "owner_id"], ["scenario_id", "owner_id"],
        ondelete="CASCADE", deferrable=True, initially="DEFERRED")
