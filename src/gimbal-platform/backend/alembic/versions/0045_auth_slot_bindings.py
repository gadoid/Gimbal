"""authz M2a S3.0:auth_sessions 槽位绑定改键。

* 加五列:``system``(基础服务;``''`` = 未归类)、``env_id``(空 =
  不限环境)、``slot``(槽名 = 注入键;存量 = 原别名)、
  ``account_fields``(账号级字段,S4/S5 经 ``${slot.X.field}`` 消费)、
  ``is_default``(每槽至多一个默认,部分唯一索引)。
* 唯一键 ``(owner_id, alias)`` → ``(owner_id, system, env_id, slot)``
  (NULLS NOT DISTINCT,PG15+)。**行 id 不变、不重建表** ——
  ``access_token_scopes.auth_id`` 的 CASCADE 不会触发,令牌范围原样
  存活(F7 的迁移面零动作;行为面由迁移测试钉住)。
* service_aliases 加 ``slot``,回填 = ``credential_alias``(写面同步
  维护,credential_alias 本体是 S6 删除项)。
* 存量回填:slot=alias;system 从引用该凭证的别名的基础服务推断
  (唯一值 → 该服务;零个或冲突 → ``''`` 未归类,由用户认领);env 空;
  is_default=true(存量每槽恰一行 = 名字解析的取用行)。

fresh 链守卫:baseline 按当前模型建表(新列与新键已存在)→ 各步内省
后空转;downgrade 回删列并还原旧唯一键。
"""
from alembic import op
import sqlalchemy as sa

revision = "0045_auth_slot_bindings"
down_revision = "0044_deployments_env_chain"
branch_labels = None
depends_on = None


def _has_column(bind, table: str, column: str) -> bool:
    return column in {
        c["name"] for c in sa.inspect(bind).get_columns(table)}


def _has_index(bind, table: str, index: str) -> bool:
    return index in {
        i["name"] for i in sa.inspect(bind).get_indexes(table)}


def _has_unique_constraint(bind, table: str, name: str) -> bool:
    return name in {
        c["name"] for c in sa.inspect(bind).get_unique_constraints(table)}


def upgrade() -> None:
    bind = op.get_bind()

    # ① auth_sessions 加列(fresh 链 baseline 已带)
    if not _has_column(bind, "auth_sessions", "system"):
        op.add_column("auth_sessions", sa.Column(
            "system", sa.String(128), nullable=False,
            server_default=sa.text("''")))
    if not _has_column(bind, "auth_sessions", "env_id"):
        op.add_column("auth_sessions", sa.Column(
            "env_id", sa.Integer(),
            sa.ForeignKey("environments.id", ondelete="SET NULL"),
            nullable=True))
    if not _has_column(bind, "auth_sessions", "slot"):
        op.add_column("auth_sessions", sa.Column(
            "slot", sa.String(64), nullable=False,
            server_default=sa.text("''")))
    if not _has_column(bind, "auth_sessions", "account_fields"):
        from sqlalchemy.dialects.postgresql import JSONB
        op.add_column("auth_sessions", sa.Column(
            "account_fields", JSONB(), nullable=False,
            server_default=sa.text("'{}'::jsonb")))
    if not _has_column(bind, "auth_sessions", "is_default"):
        op.add_column("auth_sessions", sa.Column(
            "is_default", sa.Boolean(), nullable=False,
            server_default=sa.false()))

    # ② 换唯一键:先回填新键列,再换约束
    bind.execute(sa.text(
        "UPDATE auth_sessions SET slot = alias WHERE slot = ''"))
    # system 推断:引用该凭证的别名的基础服务唯一 → 该服务;
    # 零个或冲突 → 保持 ''(未归类,由用户认领)。fresh 链守卫:0047 删
    # credential_alias 后 baseline 无此列(无存量可推断)
    _has_cred = _has_column(bind, "service_aliases", "credential_alias")
    if _has_cred:
        bind.execute(sa.text("""
            UPDATE auth_sessions a SET system = sub.bs
            FROM (SELECT credential_alias AS ca, min(base_service) AS bs,
                         count(DISTINCT base_service) AS n
                  FROM service_aliases
                  WHERE credential_alias IS NOT NULL
                  GROUP BY credential_alias) AS sub
            WHERE sub.ca = a.alias AND sub.n = 1
        """))
    # 存量行 = 各槽唯一绑定 → 全部置默认(名字解析的取用行)
    bind.execute(sa.text(
        "UPDATE auth_sessions SET is_default = true"))
    # 回填 UPDATE 会在本事务留下延迟触发器(owner FK DEFERRABLE),
    # 挂起的触发事件会拦住后续 ALTER TABLE —— 先转立即把待查触发掉
    bind.execute(sa.text("SET CONSTRAINTS ALL IMMEDIATE"))
    if _has_unique_constraint(bind, "auth_sessions",
                              "uq_auth_owner_alias"):
        op.drop_constraint("uq_auth_owner_alias", "auth_sessions",
                           type_="unique")
    if not _has_unique_constraint(bind, "auth_sessions",
                                  "uq_auth_owner_system_env_slot"):
        bind.execute(sa.text(
            "ALTER TABLE auth_sessions ADD CONSTRAINT "
            "uq_auth_owner_system_env_slot UNIQUE NULLS NOT DISTINCT "
            "(owner_id, system, env_id, slot)"))
    if not _has_index(bind, "auth_sessions", "uq_auth_slot_default"):
        bind.execute(sa.text(
            "CREATE UNIQUE INDEX uq_auth_slot_default "
            "ON auth_sessions (owner_id, slot) WHERE is_default"))

    # ③ service_aliases.slot = credential_alias(声明槽位)
    if not _has_column(bind, "service_aliases", "slot"):
        op.add_column("service_aliases", sa.Column(
            "slot", sa.String(64), nullable=True))
    if _has_cred:
        bind.execute(sa.text(
            "UPDATE service_aliases SET slot = credential_alias "
            "WHERE credential_alias IS NOT NULL AND slot IS NULL"))


def downgrade() -> None:
    bind = op.get_bind()
    # 无回填 UPDATE,但防御同款:清挂起触发事件再 ALTER
    bind.execute(sa.text("SET CONSTRAINTS ALL IMMEDIATE"))
    # 回删默认索引/新键,还原旧唯一键(同 owner 同 alias 无重复 ——
    # 应用层一直按名唯一,存量形状可回)
    bind.execute(sa.text("DROP INDEX IF EXISTS uq_auth_slot_default"))
    bind.execute(sa.text(
        "ALTER TABLE auth_sessions DROP CONSTRAINT IF EXISTS "
        "uq_auth_owner_system_env_slot"))
    op.drop_column("service_aliases", "slot")
    for col in ("is_default", "account_fields", "slot", "env_id", "system"):
        if _has_column(bind, "auth_sessions", col):
            op.drop_column("auth_sessions", col)
    if not _has_unique_constraint(bind, "auth_sessions",
                                  "uq_auth_owner_alias"):
        bind.execute(sa.text(
            "ALTER TABLE auth_sessions ADD CONSTRAINT "
            "uq_auth_owner_alias UNIQUE (owner_id, alias)"))
