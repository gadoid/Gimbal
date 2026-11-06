"""角色更名 + must_change_password 列 + token_owner_ineligible 恢复(authz W1/W5/W6)

三级角色重命名(权限边界不变,沿用 2026-09-29 更名先例):
user 不动、member → admin、admin → super_admin;``__platform__``
(is_system)不参与更名。同一迁移还承载:

* ``users.must_change_password`` 列(W6 管理员重置密码后的强制改密门;
  全后端原不存在,实测 0 命中);
* W5 恢复 SQL(纯 SQL,不 import 应用代码——评审 R9):
  ``token_owner_ineligible`` 暂停的集成实例恢复为 idle。字段口径对照
  ``revive_paused_instances``(state='idle' + paused_reason 清空 +
  next_run_at=now);范围仅实例(``template_id IS NOT NULL``,函数同款
  ——评审 E4)。SQL 恢复不发恢复通知,与函数恢复的这一差异可接受
  (迁移测试注明)。

Revision ID: 0036_role_rename
Revises: 0035_execution_steps
Create Date: 2026-11-07
"""
from alembic import op
import sqlalchemy as sa

revision = "0036_role_rename"
down_revision = "0035_execution_steps"
branch_labels = None
depends_on = None


def _has_column(bind, table: str, column: str) -> bool:
    return any(c["name"] == column
               for c in sa.inspect(bind).get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()
    # ① 角色更名:顺序固定 —— 先 admin→super_admin,再 member→admin
    #    (反序会让 member→admin 的产物被误当作原 admin)。
    #    三件事(更名/加列/恢复)在迁移测试里分别断言(评审 R10)。
    bind.execute(sa.text(
        "UPDATE users SET role = 'super_admin', updated_at = now() "
        "WHERE role = 'admin' AND is_system = false"))
    bind.execute(sa.text(
        "UPDATE users SET role = 'admin', updated_at = now() "
        "WHERE role = 'member'"))
    # ② W6:强制改密标记列(fresh 链守卫,同 0035 口径)。
    if not _has_column(bind, "users", "must_change_password"):
        op.add_column(
            "users",
            sa.Column("must_change_password", sa.Boolean(),
                      nullable=False, server_default=sa.text("false")))
    # ③ W5:恢复 token_owner_ineligible 暂停的实例(仅实例,不动模板)。
    bind.execute(sa.text(
        "UPDATE integration_tasks SET state = 'idle', "
        "paused_reason = '', next_run_at = now() "
        "WHERE state = 'paused' "
        "AND paused_reason = 'token_owner_ineligible' "
        "AND template_id IS NOT NULL"))


def downgrade() -> None:
    bind = op.get_bind()
    # 角色回填:与 upgrade 反序 —— 先 admin→member(此时 admin 只剩原
    # member),再 super_admin→admin(原 admin 归位)。仅回滚更名与列;
    # ③ 恢复过的实例不回滚(数据修复无逆语义)。
    bind.execute(sa.text(
        "UPDATE users SET role = 'member', updated_at = now() "
        "WHERE role = 'admin' AND is_system = false"))
    bind.execute(sa.text(
        "UPDATE users SET role = 'admin', updated_at = now() "
        "WHERE role = 'super_admin' AND is_system = false"))
    if _has_column(bind, "users", "must_change_password"):
        op.drop_column("users", "must_change_password")
