"""authz M2a S7.4:引用分享退役 —— 删 ``share_refs`` 表。

存量引用须先经 ``scripts/retire_share_refs.py --apply`` 一次性转为
被分享人的私有副本(Q2 裁定):**表非空即拒绝本迁移**,防漏跑转换
静默丢引用。downgrade 不还原(退役是一次性决策,回滚面 = 整个 S7.4;
需要时从备份恢复 + 手工重建,0013 有原始定义)。
"""
from alembic import op
import sqlalchemy as sa

revision = "0049_drop_share_refs"
down_revision = "0048_project_promotions"


def _has_table(bind) -> bool:
    return bool(bind.execute(sa.text(
        "SELECT to_regclass('share_refs') IS NOT NULL")).scalar())


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind):
        return          # fresh 链(模型已删,create_all 不再建本表)
    n = bind.execute(sa.text("SELECT count(*) FROM share_refs")).scalar()
    if n:
        raise RuntimeError(
            f"share_refs 非空({n} 行):先跑 python scripts/retire_share_refs.py"
            " --apply 把存量引用转私有副本,再执行本迁移")
    # drop_table 连带索引/FK/CHECK/唯一约束(0013 定义)
    op.drop_table("share_refs")


def downgrade() -> None:
    # schema 按 0013 还原(迁移链可逆性;数据不随 downgrade 恢复 ——
    # 退役是一次性决策,行需从备份人工回灌)
    if _has_table(op.get_bind()):
        return
    op.create_table(
        "share_refs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("grantee_user_id", sa.Integer,
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scenario_id", sa.String(128), nullable=True),
        sa.Column("suite_id", sa.Integer, nullable=True),
        sa.Column("granted_by_name", sa.String(128), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["scenario_id"], ["composer_scenarios.scenario_id"],
            ondelete="CASCADE", name="fk_share_refs_scenario"),
        sa.ForeignKeyConstraint(
            ["suite_id"], ["suites.id"],
            ondelete="CASCADE", name="fk_share_refs_suite"),
        sa.CheckConstraint(
            "(scenario_id IS NULL) <> (suite_id IS NULL)",
            name="ck_share_refs_exactly_one"),
        sa.UniqueConstraint("grantee_user_id", "scenario_id",
                            name="uq_share_refs_user_scenario"),
        sa.UniqueConstraint("grantee_user_id", "suite_id",
                            name="uq_share_refs_user_suite"),
    )
    op.create_index("ix_share_refs_grantee", "share_refs",
                    ["grantee_user_id"])
    op.create_index("ix_share_refs_scenario", "share_refs", ["scenario_id"])
    op.create_index("ix_share_refs_suite", "share_refs", ["suite_id"])
