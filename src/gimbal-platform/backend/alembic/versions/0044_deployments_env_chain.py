"""authz M2a S2.0:部署表 + 环境链数据模型。

* 新表 ``deployments``: ``(base_service, env_id) → base_url``(地址
  链第 ③ 层新数据源,D11 键 = plate 基础服务名);删环境级联删部署行。
* ``environments.is_default``:默认环境恰一行(D2:链路末位兜底),
  部分唯一索引钉死;存量恰 1 个环境时迁移即置默认。
* ``projects.default_environment_id``:环境链第三位(SET NULL)。
* 删 ``environments.visibility``(零逻辑消费,环境是团队共享配置)。
* 回填:别名地址按 (基础服务, 环境) 聚合成部署行 —— 挂环境的别名落其
  环境,没挂环境的落默认环境(无默认则不落);同键地址不一致的键不落
  (冲突留给 Admin 裁定,运行时各别名回退自带地址,D2「S2 上线当天
  地址逐字节不变」)。

fresh 链守卫:baseline 按当前模型建表(本迁移的形状已存在)→ 各步
内省后空转。downgrade 删表删列、回加 visibility(默认 private)。
"""
from alembic import op
import sqlalchemy as sa

revision = "0044_deployments_env_chain"
down_revision = "0043_drop_visibility"
branch_labels = None
depends_on = None


def _has_table(bind, table: str) -> bool:
    return table in set(sa.inspect(bind).get_table_names())


def _has_column(bind, table: str, column: str) -> bool:
    return column in {
        c["name"] for c in sa.inspect(bind).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()

    # ① 新表 deployments(fresh 链 baseline 已建)
    if not _has_table(bind, "deployments"):
        op.create_table(
            "deployments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("base_service", sa.String(128), nullable=False),
            sa.Column("env_id", sa.Integer(),
                      sa.ForeignKey("environments.id", ondelete="CASCADE"),
                      nullable=False),
            sa.Column("base_url", sa.String(512), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True)),
            sa.Column("updated_at", sa.DateTime(timezone=True)),
            sa.UniqueConstraint("base_service", "env_id",
                                name="uq_deployments_service_env"),
        )
        op.create_index(
            "ix_deployments_env_id", "deployments", ["env_id"])

    # ② environments.is_default(部分唯一索引:至多一行默认)
    if not _has_column(bind, "environments", "is_default"):
        op.add_column("environments", sa.Column(
            "is_default", sa.Boolean(), nullable=False,
            server_default=sa.false()))
        bind.execute(sa.text(
            "CREATE UNIQUE INDEX uq_environments_default "
            "ON environments (is_default) WHERE is_default"))

    # ③ projects.default_environment_id(SET NULL)
    if not _has_column(bind, "projects", "default_environment_id"):
        op.add_column("projects", sa.Column(
            "default_environment_id", sa.Integer(),
            sa.ForeignKey("environments.id", ondelete="SET NULL"),
            nullable=True))

    # ④ 删 environments.visibility(S2:零逻辑消费)
    if _has_column(bind, "environments", "visibility"):
        op.drop_column("environments", "visibility")

    # ⑤ 存量恰 1 个环境 → 置为默认(D2:Admin 可后改)
    bind.execute(sa.text(
        "UPDATE environments SET is_default = true "
        "WHERE (SELECT count(*) FROM environments) = 1"))

    # ⑥ 部署行回填:别名地址按 (基础服务, 环境) 聚合 —— 挂环境的别名
    #   落其环境;没挂环境的别名落默认环境(无默认则不落)。**同键地址
    #   不一致(冲突)的键不落行**:该基础服务在该环境下各别名运行时各自
    #   回退自带地址(逐字节不变,D2),由 Admin 在部署表页显式裁定
    # fresh 链守卫:0006 会补回 base_url,但 environment_id 只在存量库有
    # (0047 删列后 baseline 无此列)—— 两列齐全才是存量形态
    if (_has_column(bind, "service_aliases", "base_url")
            and _has_column(bind, "service_aliases", "environment_id")):
        bind.execute(sa.text("""
            INSERT INTO deployments
                (base_service, env_id, base_url, created_at, updated_at)
            SELECT src.base_service, src.env_id, min(src.base_url),
                   now(), now()
            FROM (
                SELECT base_service, environment_id AS env_id, base_url
                FROM service_aliases
                WHERE base_url IS NOT NULL AND environment_id IS NOT NULL
                UNION ALL
                SELECT a.base_service, e.id AS env_id, a.base_url
                FROM service_aliases AS a, environments AS e
                WHERE a.base_url IS NOT NULL AND a.environment_id IS NULL
                  AND e.is_default
            ) AS src
            GROUP BY src.base_service, src.env_id
            HAVING count(DISTINCT src.base_url) = 1
            ON CONFLICT (base_service, env_id) DO NOTHING
        """))


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_table("deployments")
    op.drop_column("projects", "default_environment_id")
    # is_default 连同其部分唯一索引一并移除
    bind.execute(sa.text(
        "DROP INDEX IF EXISTS uq_environments_default"))
    op.drop_column("environments", "is_default")
    if not _has_column(bind, "environments", "visibility"):
        op.add_column("environments", sa.Column(
            "visibility", sa.String(16), nullable=False,
            server_default="private"))
