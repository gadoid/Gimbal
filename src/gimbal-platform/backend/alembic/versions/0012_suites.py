"""2026-10-09 权限域二期 P1:suite 成员层地基(《Suite成员层、引用分享
与浏览镜头-设计方案》§6.3)。

- ``suites`` / ``suite_members`` 建表;成员表两条组合外键
  (DEFERRABLE INITIALLY DEFERRED + ON DELETE CASCADE)在库层钉死
  「suite 只放属主自己的场景」—— 绕过应用层直写也会被约束拒绝;
  转让路径据此要求 suite/场景/成员三表 owner_id 同一事务改写。
- ``composer_scenarios`` 补 UNIQUE(scenario_id, owner_id) 作为组合
  外键目标(scenario_id 本身已唯一,组合键唯一性恒成立,纯 FK 目的);
  用唯一索引而非约束,SQLite 免 batch 重建表。
- ``share_refs``(引用分享)留 P2 另立迁移;本迁移不动它。

fresh 链守卫:baseline ``create_all`` 已含两表 → 内省后空转(同
0006/0008/0009)。部署硬顺序:先 upgrade 再起新代码。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0012_suites"
down_revision = "0011_role_tier_rename"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _indexes(table: str) -> set[str]:
    return {ix["name"] for ix in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    # 顺序硬约束:组合唯一索引必须先于 suite_members 建表 —— PG 要求
    # FK 目标列在**建 FK 时**已有唯一约束/索引(先建表后补索引会
    # InvalidForeignKey)。
    if "uq_composer_sid_owner" not in _indexes("composer_scenarios"):
        op.create_index("uq_composer_sid_owner", "composer_scenarios",
                        ["scenario_id", "owner_id"], unique=True)
    if "suites" not in _tables():
        op.create_table(
            "suites",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(128), nullable=False),
            sa.Column("description", sa.String(512), nullable=False,
                      server_default=""),
            # 不加 ON DELETE:未处置的用户删不掉(处置流程负责删 suite)
            sa.Column("owner_id", sa.Integer,
                      sa.ForeignKey("users.id"), nullable=False),
            sa.Column("visibility", sa.String(16), nullable=False,
                      server_default="private"),
            sa.Column("mode", sa.String(32), nullable=False,
                      server_default="aggregate"),
            sa.Column("mode_config", sa.JSON(), nullable=False),
            sa.Column("forked_from_id", sa.Integer, nullable=True),
            sa.Column("forked_from_owner_name", sa.String(128), nullable=True),
            sa.Column("forked_from_at", sa.DateTime(timezone=True),
                      nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.func.now()),
        )
        op.create_index("uq_suites_owner_name", "suites",
                        ["owner_id", "name"], unique=True)
        op.create_index("uq_suites_id_owner", "suites",
                        ["id", "owner_id"], unique=True)
        op.create_index("ix_suites_owner_id", "suites", ["owner_id"])
    if "suite_members" not in _tables():
        op.create_table(
            "suite_members",
            sa.Column("suite_id", sa.Integer, primary_key=True),
            sa.Column("scenario_id", sa.String(128), primary_key=True),
            sa.Column("owner_id", sa.Integer, nullable=False),
            sa.Column("sort", sa.Integer, nullable=False, server_default="0"),
            sa.Column("added_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.func.now()),
            sa.ForeignKeyConstraint(
                ["suite_id", "owner_id"], ["suites.id", "suites.owner_id"],
                ondelete="CASCADE", deferrable=True, initially="DEFERRED",
                name="fk_suite_members_suite"),
            sa.ForeignKeyConstraint(
                ["scenario_id", "owner_id"],
                ["composer_scenarios.scenario_id",
                 "composer_scenarios.owner_id"],
                ondelete="CASCADE", deferrable=True, initially="DEFERRED",
                name="fk_suite_members_scenario"),
        )
        op.create_index("ix_suite_members_scenario", "suite_members",
                        ["scenario_id"])


def downgrade() -> None:
    if "suite_members" in _tables():
        op.execute("DROP TABLE suite_members")
    if "suites" in _tables():
        op.execute("DROP TABLE suites")
    if "uq_composer_sid_owner" in _indexes("composer_scenarios"):
        op.drop_index("uq_composer_sid_owner", "composer_scenarios")
