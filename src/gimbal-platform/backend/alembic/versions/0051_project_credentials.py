"""authz M2a S8:项目凭证 —— 槽位绑定增加归属维度(个人 / 项目)。

* ``auth_sessions``:``owner_id`` 改可空;加 ``project_id``(无 FK ——
  同 Execution.project_id 快照口径;项目删除由路由显式删除项目凭证);CHECK
  ``ck_auth_owner_xor_project`` 归属恰一;唯一键与默认索引并入
  ``project_id``(NULLS NOT DISTINCT)—— 存量行全是个人行(project_id
  NULL),新键与旧键逐行同义,**行 id 不变**(令牌范围 CASCADE 不触发)。
* ``integration_tasks``:实例行加 ``credential_source``('project' |
  NULL = 持有人个人凭证)。存量实例全是个人来源 → 无回填。

fresh 链守卫:baseline 按当前模型建表(新列/新键已在)→ 内省后空转。
downgrade:先删项目凭证行(个人键无法容纳 owner NULL 的行),再还原
旧键/旧索引、owner_id NOT NULL,删两列。
"""
from alembic import op
import sqlalchemy as sa

revision = "0051_project_credentials"
down_revision = "0050_carry_batch_scope"
branch_labels = None
depends_on = None


def _cols(bind, table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(bind).get_columns(table)}


def _uq_cols(bind, name: str) -> list[str] | None:
    for c in sa.inspect(bind).get_unique_constraints("auth_sessions"):
        if c["name"] == name:
            return list(c["column_names"])
    return None


def _idx_cols(bind, name: str) -> list[str] | None:
    for i in sa.inspect(bind).get_indexes("auth_sessions"):
        if i["name"] == name:
            return list(i["column_names"])
    return None


def _has_check(bind, name: str) -> bool:
    return name in {c["name"] for c in
                    sa.inspect(bind).get_check_constraints("auth_sessions")}


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("SET CONSTRAINTS ALL IMMEDIATE"))

    # ① auth_sessions.project_id + owner_id 可空
    if "project_id" not in _cols(bind, "auth_sessions"):
        op.add_column("auth_sessions", sa.Column(
            "project_id", sa.Integer(), nullable=True))
        op.create_index("ix_auth_sessions_project_id", "auth_sessions",
                        ["project_id"])
    op.alter_column("auth_sessions", "owner_id", nullable=True)

    # ② 唯一键 / 默认索引并入 project_id(列序与模型一致即视为已换)
    want_uq = ["owner_id", "project_id", "system", "env_id", "slot"]
    if _uq_cols(bind, "uq_auth_owner_system_env_slot") != want_uq:
        bind.execute(sa.text(
            "ALTER TABLE auth_sessions DROP CONSTRAINT IF EXISTS "
            "uq_auth_owner_system_env_slot"))
        bind.execute(sa.text(
            "ALTER TABLE auth_sessions ADD CONSTRAINT "
            "uq_auth_owner_system_env_slot UNIQUE NULLS NOT DISTINCT "
            "(owner_id, project_id, system, env_id, slot)"))
    if _idx_cols(bind, "uq_auth_slot_default") != [
            "owner_id", "project_id", "slot"]:
        bind.execute(sa.text("DROP INDEX IF EXISTS uq_auth_slot_default"))
        bind.execute(sa.text(
            "CREATE UNIQUE INDEX uq_auth_slot_default ON auth_sessions "
            "(owner_id, project_id, slot) NULLS NOT DISTINCT "
            "WHERE is_default"))
    if not _has_check(bind, "ck_auth_owner_xor_project"):
        op.create_check_constraint(
            "ck_auth_owner_xor_project", "auth_sessions",
            "(owner_id IS NULL) <> (project_id IS NULL)")

    # ③ integration_tasks.credential_source
    if "credential_source" not in _cols(bind, "integration_tasks"):
        op.add_column("integration_tasks", sa.Column(
            "credential_source", sa.String(16), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("SET CONSTRAINTS ALL IMMEDIATE"))
    if "credential_source" in _cols(bind, "integration_tasks"):
        op.drop_column("integration_tasks", "credential_source")
    if "project_id" in _cols(bind, "auth_sessions"):
        # 项目凭证行无个人属主,旧键容纳不了 —— 一次性降级语义:删除
        bind.execute(sa.text(
            "DELETE FROM auth_sessions WHERE project_id IS NOT NULL"))
    bind.execute(sa.text(
        "ALTER TABLE auth_sessions DROP CONSTRAINT IF EXISTS "
        "ck_auth_owner_xor_project"))
    bind.execute(sa.text("DROP INDEX IF EXISTS uq_auth_slot_default"))
    bind.execute(sa.text(
        "ALTER TABLE auth_sessions DROP CONSTRAINT IF EXISTS "
        "uq_auth_owner_system_env_slot"))
    if "project_id" in _cols(bind, "auth_sessions"):
        bind.execute(sa.text(
            "DROP INDEX IF EXISTS ix_auth_sessions_project_id"))
        op.drop_column("auth_sessions", "project_id")
    op.alter_column("auth_sessions", "owner_id", nullable=False)
    bind.execute(sa.text(
        "ALTER TABLE auth_sessions ADD CONSTRAINT "
        "uq_auth_owner_system_env_slot UNIQUE NULLS NOT DISTINCT "
        "(owner_id, system, env_id, slot)"))
    bind.execute(sa.text(
        "CREATE UNIQUE INDEX uq_auth_slot_default "
        "ON auth_sessions (owner_id, slot) WHERE is_default"))
