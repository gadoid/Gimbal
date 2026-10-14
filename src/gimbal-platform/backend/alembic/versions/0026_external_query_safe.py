"""集成线 v2 / I4:external_endpoints 加 query_safe 列(方案 §3.2)。

平台模式只读口径的目录级标记:Jira ``POST /search``、MeterSphere 分页
查询这类「POST 实现的查询」标了它即可进平台模式(与 plate 端点元数据
``metadata.query_safe`` 同形状的第二来源)。存量回填 false —— 标记只能
admin 显式落(误标意味着平台账号可能执行写操作),OpenAPI 导入也不
自动标记。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0026_external_query_safe"
down_revision = "0025_drop_integration_last"


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _has_column(table: str, column: str) -> bool:
    return column in {
        c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    # fresh 链守卫:baseline(当前模型)已含本列 → 空转
    if _has_table("external_endpoints") \
            and not _has_column("external_endpoints", "query_safe"):
        op.add_column("external_endpoints", sa.Column(
            "query_safe", sa.Boolean(), nullable=False,
            server_default=sa.false()))


def downgrade() -> None:
    if _has_table("external_endpoints") \
            and _has_column("external_endpoints", "query_safe"):
        op.drop_column("external_endpoints", "query_safe")
