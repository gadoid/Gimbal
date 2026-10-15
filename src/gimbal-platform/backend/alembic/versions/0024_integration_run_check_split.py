"""集成线 v2 / I2:integration_tasks 实例层 run/check 分立加列 +
存量映射(方案 §2.4,R-A)。

一个 last_status 承载了两个维度(能不能跑完 × 被检对象是否健康),
拆成 run_status(ok/auth/timeout/transport/contract/channel)与
check_status(pass/fail/none/unknown)。last_status 保留为双出过渡的
投影位(D11),I3 前端切换验收后随 I3.5 删除。

存量映射(R-A):
- passed            → run=ok,     check=unknown(下次执行校正)
- failed+auth_failed→ run=auth,   check=unknown(此暂停不按周期重试,
  不手动恢复永无下次执行,映射 channel 会永远错标最严重分类)
- failed(其余)     → run=channel,check=unknown
- timeout           → run=timeout,check=unknown
其余不回填推断,下次执行自愈。check_notified_status 默认 '' =
初始化静默(D9:存量迁移后首跑不产生全量通知风暴)。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0024_integration_run_check"
down_revision = "0023_ext_schema_json"


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _has_column(table: str, column: str) -> bool:
    return column in {
        c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


_COLUMNS: list[tuple[str, sa.Column]] = [
    ("run_status", sa.Column("run_status", sa.String(16), nullable=False,
                             server_default="")),
    ("check_status", sa.Column("check_status", sa.String(16), nullable=False,
                               server_default="")),
    ("check_message", sa.Column("check_message", sa.Text(), nullable=False,
                                server_default="")),
    # 时间戳列用 timestamptz(= 模型 UtcDateTime;合入评估 §2-2:原先
    # sa.DateTime() 在 PG 得 timestamp without time zone,与模型漂移,
    # 由 0027 对已执行过旧版 0024 的环境补正)
    ("check_changed_at", sa.Column(
        "check_changed_at", postgresql.TIMESTAMP(timezone=True),
        nullable=True)),
    ("check_notified_status",
     sa.Column("check_notified_status", sa.String(16), nullable=False,
               server_default="")),
    ("check_notified_at", sa.Column(
        "check_notified_at", postgresql.TIMESTAMP(timezone=True),
        nullable=True)),
]


# R-A 存量映射(§2.4):实例行(template_id 非空)按 last_status +
# paused_reason 精确判别;check 一律 unknown,下次执行自愈。
# 模块级常量:单测直接执行同一段 SQL,不复制口径。
LEGACY_MAP_SQL = [
    "UPDATE integration_tasks SET run_status='ok', check_status='unknown' "
    "WHERE template_id IS NOT NULL AND last_status='passed'",
    "UPDATE integration_tasks SET run_status='auth', check_status='unknown' "
    "WHERE template_id IS NOT NULL AND last_status='failed' "
    "AND paused_reason='auth_failed'",
    "UPDATE integration_tasks SET run_status='channel', "
    "check_status='unknown' WHERE template_id IS NOT NULL "
    "AND last_status='failed' "
    "AND COALESCE(paused_reason,'') <> 'auth_failed'",
    "UPDATE integration_tasks SET run_status='timeout', "
    "check_status='unknown' WHERE template_id IS NOT NULL "
    "AND last_status='timeout'",
]


def upgrade() -> None:
    # fresh 链守卫(同 0015/0019 口径):baseline create_all 已含本列时
    # 空转;数据映射对空表/已映射行为幂等无副作用。
    if not _has_table("integration_tasks"):
        return
    bind = op.get_bind()
    for _, col in _COLUMNS:
        if not _has_column("integration_tasks", col.name):
            op.add_column("integration_tasks", col)
    if _has_column("integration_tasks", "last_status"):
        for stmt in LEGACY_MAP_SQL:
            bind.execute(sa.text(stmt))


def downgrade() -> None:
    for name, _ in reversed(_COLUMNS):
        if _has_column("integration_tasks", name):
            op.drop_column("integration_tasks", name)
