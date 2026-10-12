"""0021:外部接口登记目录 + 倒排索引 via_vars(外部接口登记批 X1/X3)。

- external_endpoints 表(external 步骤锚点 ext:<alias>.<name> 的结构
  定义来源;JSON Schema 形态,OpenAPI 可导入;设计 v1.0 §2.1);
- scenario_endpoint_refs.via_vars JSONB(值内全部 ${var.NAME} 列表;
  via_var 首变量保留兼容读,D3 拍板)。
"""
from alembic import op
import sqlalchemy as sa

revision = "0021_external_registry"
down_revision = "0020_execution_baseline"


def upgrade() -> None:
    op.create_table(
        "external_endpoints",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("alias_name", sa.String(128), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("title", sa.String(256), nullable=False,
                  server_default=""),
        sa.Column("method", sa.String(8), nullable=False),
        sa.Column("path", sa.String(512), nullable=False),
        # sa.JSON 与 0016/0020 同款(迁移自包含,不引 app 类型)
        sa.Column("request_schema", sa.JSON(), nullable=True),
        sa.Column("auth", sa.String(16), nullable=False,
                  server_default="none"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["alias_name"], ["service_aliases.alias_name"],
            ondelete="CASCADE"),
        sa.UniqueConstraint("alias_name", "name",
                            name="uq_external_endpoint"),
    )
    op.create_index("ix_external_endpoint_alias",
                    "external_endpoints", ["alias_name"])
    op.add_column("scenario_endpoint_refs",
                  sa.Column("via_vars", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("scenario_endpoint_refs", "via_vars")
    op.drop_index("ix_external_endpoint_alias", table_name="external_endpoints")
    op.drop_table("external_endpoints")
