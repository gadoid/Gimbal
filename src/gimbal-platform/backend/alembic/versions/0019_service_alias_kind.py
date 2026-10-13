"""0019: service_aliases 加 kind 列(三态接入 P1.0/W2)。

plate = 落在 plate 系统 services 声明内(受管,可版本化);
external = 第三方服务(无版本管理,不触发预览/不阻塞集成,单独统计
不入基线)。存量行 server_default 回填 'plate' —— 登记强约束
(create_alias 经 derive_base 落回 plate 目录)保证存量 base 均在
目录内;后续纠偏/审计走 scripts/p1_backfill_service_kinds.py。
"""
from alembic import op
import sqlalchemy as sa

revision = "0019_service_alias_kind"
down_revision = "0018_adaptation_scope"


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _has_column(table: str, column: str) -> bool:
    return column in {
        c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    # fresh 链守卫(2026-10-13 A-1):baseline 已含本列 → 空转。
    if not _has_column("service_aliases", "kind"):
        op.add_column(
            "service_aliases",
            sa.Column("kind", sa.String(16), nullable=False,
                      server_default="plate"))


def downgrade() -> None:
    op.drop_column("service_aliases", "kind")
