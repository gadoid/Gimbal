"""authz M2b Q2:项目令牌 —— ``access_tokens`` 增加项目 / 负责人维度。

* ``user_id`` 改可空(项目令牌恒 NULL;个人面 ``user_id == uid`` 查询天然
  排除项目令牌,签发人被删不会 CASCADE 掉项目令牌);
* ``project_id``(无 FK —— 同 S8 ``auth_sessions.project_id``:baseline 按
  当前模型建表,带 FK 会破 0040/0041 迁移用例;项目删除路由显式吊销);
* ``holder_id`` / ``holder_pending_id`` FK users ON DELETE SET NULL(负责人 /
  换绑待确认);
* CHECK ``ck_token_kind_shape``:个人令牌 = 属主非空 ∧ 无项目;项目令牌 =
  属主空 ∧ 有项目。存量全是个人令牌(0038 删尽平台令牌)→ 无回填。

fresh 链守卫:baseline 按当前模型建表(新列 / CHECK 已在)→ 内省后空转。
downgrade:先删项目令牌行(范围行 CASCADE),再删列、还原 NOT NULL。
"""
from alembic import op
import sqlalchemy as sa

revision = "0052_project_tokens"
down_revision = "0051_project_credentials"
branch_labels = None
depends_on = None

_CHECK = ("(kind = 'personal' AND user_id IS NOT NULL"
          " AND project_id IS NULL)"
          " OR (kind = 'project' AND user_id IS NULL"
          " AND project_id IS NOT NULL)")


def _cols(bind) -> set[str]:
    return {c["name"] for c in sa.inspect(bind).get_columns("access_tokens")}


def _has_check(bind, name: str) -> bool:
    return name in {c["name"] for c in
                    sa.inspect(bind).get_check_constraints("access_tokens")}


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("SET CONSTRAINTS ALL IMMEDIATE"))
    cols = _cols(bind)
    if "project_id" not in cols:
        op.add_column("access_tokens", sa.Column(
            "project_id", sa.Integer(), nullable=True))
        op.create_index("ix_access_tokens_project_id", "access_tokens",
                        ["project_id"])
    if "holder_id" not in cols:
        op.add_column("access_tokens", sa.Column(
            "holder_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    if "holder_pending_id" not in cols:
        op.add_column("access_tokens", sa.Column(
            "holder_pending_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.alter_column("access_tokens", "user_id", nullable=True)
    if not _has_check(bind, "ck_token_kind_shape"):
        op.create_check_constraint("ck_token_kind_shape", "access_tokens",
                                   _CHECK)


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("SET CONSTRAINTS ALL IMMEDIATE"))
    bind.execute(sa.text(
        "DELETE FROM access_tokens WHERE kind = 'project'"))
    if _has_check(bind, "ck_token_kind_shape"):
        op.drop_constraint("ck_token_kind_shape", "access_tokens",
                           type_="check")
    cols = _cols(bind)
    if "holder_pending_id" in cols:
        op.drop_column("access_tokens", "holder_pending_id")
    if "holder_id" in cols:
        op.drop_column("access_tokens", "holder_id")
    if "project_id" in cols:
        bind.execute(sa.text(
            "DROP INDEX IF EXISTS ix_access_tokens_project_id"))
        op.drop_column("access_tokens", "project_id")
    op.alter_column("access_tokens", "user_id", nullable=False)
