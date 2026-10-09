"""外部系统集成 P1:功能(模板/实例两层)表 + 平台系统用户。

《GIMBAL-外部系统集成架构设计》§3/§4(评审 2026-10-09 定稿口径):
- ``integration_tasks``:模板行(template_id NULL)存定义,实例行存
  运行状态;平台模式实例 holder = 平台系统用户;
- ``users.is_system``:平台系统用户标记(登录拒绝、用户列表过滤);
  种子用户 ``__platform__`` 持有平台凭证池(owner_id 指向它,凭证
  仍存 auth_sessions,复用加密/连通测试/登录器);
- 评审 E6:target_type + suite_id 预留(Suite 已收官,scenario 先行);
- 评审 E7:removed_at 软删。
"""
from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op
from passlib.context import CryptContext

revision = "0015_integration_tasks"
down_revision = "0014_suite_modes"
branch_labels = None
depends_on = None

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("is_system", sa.Boolean(), nullable=False,
                                   server_default=sa.false()))
    op.create_table(
        "integration_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("owner_id", sa.Integer(),
                  sa.ForeignKey("users.id"), nullable=False),
        sa.Column("visibility", sa.String(16), nullable=False,
                  server_default="private"),
        sa.Column("identity_mode", sa.String(16), nullable=False,
                  server_default="platform"),
        sa.Column("target_type", sa.String(16), nullable=False,
                  server_default="scenario"),
        sa.Column("scenario_id", sa.String(128), nullable=True),
        sa.Column("suite_id", sa.Integer(), nullable=True),
        sa.Column("scheme_id", sa.String(128), nullable=True),
        sa.Column("target_system", sa.String(64), nullable=False,
                  server_default=""),
        sa.Column("trigger_cron", sa.String(64), nullable=False,
                  server_default="*/5 * * * *"),
        sa.Column("result_policy", sa.String(16), nullable=False,
                  server_default="latest"),
        sa.Column("card_template", sa.String(16), nullable=False,
                  server_default="status"),
        sa.Column("output_mapping", sa.JSON(), nullable=False,
                  server_default="{}"),
        sa.Column("state_mapping", sa.JSON(), nullable=False,
                  server_default="{}"),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("template_id", sa.Integer(),
                  sa.ForeignKey("integration_tasks.id"), nullable=True),
        sa.Column("holder_id", sa.Integer(),
                  sa.ForeignKey("users.id"), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False,
                  server_default=sa.true()),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("state", sa.String(16), nullable=False,
                  server_default="idle"),
        sa.Column("paused_reason", sa.String(32), nullable=False,
                  server_default=""),
        sa.Column("running_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status", sa.String(16), nullable=False,
                  server_default=""),
        sa.Column("last_error", sa.Text(), nullable=False,
                  server_default=""),
        sa.Column("last_outputs", sa.JSON(), nullable=False,
                  server_default="{}"),
        sa.Column("state_vars", sa.JSON(), nullable=False,
                  server_default="{}"),
        sa.Column("last_manual_run_at", sa.DateTime(timezone=True),
                  nullable=True),
        sa.Column("fail_streak", sa.Integer(), nullable=False,
                  server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("uq_integration_instance", "integration_tasks",
                    ["template_id", "holder_id"], unique=True)
    op.create_index("ix_integration_due", "integration_tasks",
                    ["state", "enabled", "next_run_at"])
    op.create_index("ix_integration_templates", "integration_tasks",
                    ["owner_id", "removed_at"])
    # 种子:平台系统用户(不可登录 —— 随机口令哈希,且 is_system 登录闸
    # 双保险;用户列表/登录路由按 is_system 过滤)
    _seed_pw = _pwd.hash(f"system-user-not-loginable:{uuid.uuid4().hex}")
    op.execute(
        sa.text(
            "INSERT INTO users (username, display_name, password_hash, "
            "role, is_active, is_system) "
            "VALUES ('__platform__', '平台系统', :pw, 'user', true, true)"
        ).bindparams(pw=_seed_pw)
    )


def downgrade() -> None:
    op.drop_index("ix_integration_templates", table_name="integration_tasks")
    op.drop_index("ix_integration_due", table_name="integration_tasks")
    op.drop_index("uq_integration_instance", table_name="integration_tasks")
    op.drop_table("integration_tasks")
    op.execute(sa.text("DELETE FROM users WHERE is_system = true"))
    with op.batch_alter_table("users") as batch:
        batch.drop_column("is_system")
