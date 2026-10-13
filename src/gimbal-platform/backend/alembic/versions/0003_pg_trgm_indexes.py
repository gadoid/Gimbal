"""pg_trgm 检索索引(M3,PG迁移方案 §7 M3 / §2.2)。

q 子串检索在 PG 用 ILIKE;无 trgm 索引时 ILIKE 退化为全表顺序扫。
本 revision 建 pg_trgm 扩展 + name/description/scenario_id 三个 GIN
trgm 索引(§0 原则 5:「ILIKE + 元数据列起步,pg_trgm 索引」)。

SQLite:无对应概念,本 revision 为 no-op(本地量小,Python 兜底)。
"""
from __future__ import annotations

from alembic import op

revision = "0003_pg_trgm_indexes"
down_revision = "0002_role_authority_flip"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    # gimbal 用户是库 owner(docker compose POSTGRES_USER),可建扩展
    # 扩展是库级唯一且 relocatable:false 场景下不可重装到任意 schema ——
    # 统一装在 public,索引算子类显式 public. 限定(⑤ 2026-10-13:空库门
    # PG 面在临时 schema 单搜索路径下建库时,不限定会解析不到算子类)。
    # 扩展侧必须 WITH SCHEMA public:不指定时装进 search_path 首位(临时
    # schema),public.gin_trgm_ops 在干净库上不存在,CI postgres:16 一跑即红
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_composer_name_trgm "
        "ON composer_scenarios USING gin (name public.gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_composer_description_trgm "
        "ON composer_scenarios USING gin (description public.gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_composer_sid_trgm "
        "ON composer_scenarios USING gin (scenario_id public.gin_trgm_ops)"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("DROP INDEX IF EXISTS ix_composer_sid_trgm")
    op.execute("DROP INDEX IF EXISTS ix_composer_description_trgm")
    op.execute("DROP INDEX IF EXISTS ix_composer_name_trgm")
