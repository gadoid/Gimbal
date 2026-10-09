"""权限域二期 P2:引用分享 share_refs + 场景副本来源三列。

《Suite成员层、引用分享与浏览镜头-设计方案》§7.2/§7.3/§13.4-债1:
- share_refs:场景与 suite 统一的引用表(CHECK 双方言通用,不存 owner_id
  ——分享者由资源当前属主推导,转让时引用天然随行);
- composer_scenarios 补 forked_from_id/owner_name/at 三列(§13.4 已核:
  copy_scenario 此前不写来源,P2 起场景与 suite 副本共用此套字段);
- G5 轻档视图 v_scenarios_readable 补两条 EXISTS(§7.6 三处同步之三;
  纯 DB 直连消费面,应用层无消费方)。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0013_shares"
down_revision = "0012_suites"
branch_labels = None
depends_on = None


def _is_pg() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    op.create_table(
        "share_refs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("grantee_user_id", sa.Integer,
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        # 可空双外键 + CHECK(§7.2):恰好指向一种资源,级联保留
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

    # composer_scenarios 副本来源三列(§13.4 债1 收口)
    with op.batch_alter_table("composer_scenarios") as batch:
        batch.add_column(sa.Column("forked_from_id",
                                   sa.String(128), nullable=True))
        batch.add_column(sa.Column("forked_from_owner_name",
                                   sa.String(128), nullable=True))
        batch.add_column(sa.Column("forked_from_at",
                                   sa.DateTime(timezone=True), nullable=True))

    # G5 轻档视图补引用分支(§7.6 第三处;security_invoker 直连消费)
    if _is_pg():
        op.execute(
            "CREATE OR REPLACE VIEW v_scenarios_readable WITH "
            "(security_invoker = true) AS "
            "SELECT * FROM composer_scenarios c WHERE c.visibility = 'public' "
            "  OR c.owner_id = NULLIF(current_setting('app.uid', true), '')::int "
            "  OR current_setting('app.role', true) = 'admin' "
            "  OR EXISTS (SELECT 1 FROM share_refs r "
            "    WHERE r.scenario_id = c.scenario_id "
            "      AND r.grantee_user_id = "
            "          NULLIF(current_setting('app.uid', true), '')::int) "
            "  OR EXISTS (SELECT 1 FROM share_refs r "
            "    JOIN suite_members m ON m.suite_id = r.suite_id "
            "    WHERE m.scenario_id = c.scenario_id "
            "      AND r.grantee_user_id = "
            "          NULLIF(current_setting('app.uid', true), '')::int)")


def downgrade() -> None:
    if _is_pg():
        op.execute(
            "CREATE OR REPLACE VIEW v_scenarios_readable WITH "
            "(security_invoker = true) AS "
            "SELECT * FROM composer_scenarios "
            "WHERE visibility = 'public' "
            "   OR owner_id = NULLIF(current_setting('app.uid', true), '')::int "
            "   OR current_setting('app.role', true) = 'admin'")
    with op.batch_alter_table("composer_scenarios") as batch:
        batch.drop_column("forked_from_at")
        batch.drop_column("forked_from_owner_name")
        batch.drop_column("forked_from_id")
    op.drop_table("share_refs")
