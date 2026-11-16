"""服务注册与凭证底座重构(docs/service-registry-redesign.md §1/§5)。

一次到位(开发环境直切,决策 8):
* 建四新表:services(主档)/system_env_instances(实例,含版本线收口)/
  service_identities(身份条目)/auth_accounts(账户);
* 清理(授权 2026-11-16):非 admin(id=1)凭证行删除(测试数据);
* 转换:主档初始化(服务名兼作 system 占位,对账页校正)、凭证→账户
  (username 解密明文化,密码密文直拷)、别名+凭证 alias→条目
  (env=默认环境兜底,ref 回指账户)、凭证 url→实例 login_url 候选
  (每 (system,env) 取 is_default 行)、environments.lines JSON→实例行;
* carry 坐标:service_name→config_key,+env_id(空=全环境基线),
  唯一键重建(含 env,NULLS NOT DISTINCT);
* 退役 drop:service_aliases/auth_sessions/service_meta、
  environments.lines 列。

Revision ID: 0057_registry_rework
Revises: 0056_client_ref_unique
"""
from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0057_registry_rework"
down_revision = "0056_client_ref_unique"
branch_labels = None
depends_on = None

ADMIN_USER_ID = 1  # 数据清理保留线(2026-11-16 授权:其余为测试用户)


def _decrypt(value: str) -> str:
    """username_enc 密文 → 明文(账户实体键;失败给占位符由人工重录)。"""
    from app.core.security import fernet_decrypt
    try:
        return fernet_decrypt(value)
    except Exception:  # noqa: BLE001 — 密钥轮换防御
        return f"<undecryptable:{value[:12]}…>"


def upgrade() -> None:
    # ── ① 四新表 ────────────────────────────────────────────────
    services = op.create_table(
        "services",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False, unique=True),
        sa.Column("system", sa.String(128), nullable=False,
                  server_default=""),
        sa.Column("kind", sa.String(16), nullable=False,
                  server_default="plate"),
        sa.Column("abbr", sa.String(64), nullable=False, server_default=""),
        sa.Column("description", sa.String(1024), nullable=False,
                  server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
    )
    op.create_table(
        "system_env_instances",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("system", sa.String(128), nullable=False, index=True),
        sa.Column("env_id", sa.Integer(),
                  sa.ForeignKey("environments.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("login_url", sa.String(512), nullable=False,
                  server_default=""),
        sa.Column("line", sa.String(64), nullable=False, server_default=""),
        sa.Column("note", sa.String(256), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.UniqueConstraint("system", "env_id",
                            name="uq_instance_system_env"),
    )
    op.create_table(
        "service_identities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("alias_name", sa.String(128), nullable=False, unique=True),
        sa.Column("base_service", sa.String(128), nullable=False),
        sa.Column("env_id", sa.Integer(),
                  sa.ForeignKey("environments.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("ref_mode", sa.String(16), nullable=False,
                  server_default="default"),
        sa.Column("ref_username", sa.String(128), nullable=False,
                  server_default=""),
        sa.Column("display", sa.String(128), nullable=False,
                  server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
    )
    op.create_index("ix_identity_service_env", "service_identities",
                    ["base_service", "env_id"])
    op.create_table(
        "auth_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="NO ACTION",
                                deferrable=True, initially="DEFERRED"),
                  nullable=True, index=True),
        sa.Column("project_id", sa.Integer(), nullable=True, index=True),
        sa.Column("system", sa.String(128), nullable=False),
        sa.Column("env_id", sa.Integer(),
                  sa.ForeignKey("environments.id", ondelete="NO ACTION"),
                  nullable=False),
        sa.Column("username", sa.String(128), nullable=False),
        sa.Column("password_enc", sa.Text(), nullable=False),
        sa.Column("token_type", sa.String(32), nullable=False,
                  server_default="Bearer"),
        sa.Column("expires_in", sa.Integer(), nullable=False,
                  server_default="7200"),
        sa.Column("account_fields", JSONB(), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_default", sa.Boolean(), nullable=False,
                  server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.UniqueConstraint("owner_id", "project_id", "system", "env_id",
                            "username", name="uq_account_pool_system_env_user",
                            postgresql_nulls_not_distinct=True),
        sa.CheckConstraint("(owner_id IS NULL) <> (project_id IS NULL)",
                           name="ck_account_owner_xor_project"),
    )
    op.create_index(
        "uq_account_default", "auth_accounts",
        ["owner_id", "project_id", "system", "env_id"], unique=True,
        postgresql_where=sa.text("is_default"),
        postgresql_nulls_not_distinct=True)

    conn = op.get_bind()

    # ── ② 清理(授权:非 admin 凭证删除;项目成员关系同步清)────────
    conn.execute(sa.text(
        "DELETE FROM auth_sessions WHERE owner_id IS NULL "
        "OR owner_id != :uid"), {"uid": ADMIN_USER_ID})
    conn.execute(sa.text(
        "DELETE FROM project_members WHERE user_id != :uid"),
        {"uid": ADMIN_USER_ID})

    # ── ③ 默认环境(env 兜底)─────────────────────────────────────
    default_env = conn.execute(sa.text(
        "SELECT id FROM environments WHERE is_default "
        "ORDER BY id LIMIT 1")).scalar()
    if default_env is None:
        default_env = conn.execute(sa.text(
            "SELECT id FROM environments ORDER BY id LIMIT 1")).scalar()

    # ── ④ services 主档初始化(服务名兼作 system 占位;对账页校正)──
    names: dict[str, str] = {}  # name → kind
    for (bs,) in conn.execute(sa.text(
            "SELECT DISTINCT base_service FROM deployments")):
        if bs:
            names.setdefault(bs, "plate")
    for bs, kind in conn.execute(sa.text(
            "SELECT DISTINCT base_service, kind FROM service_aliases")):
        if bs:
            names[bs] = kind or "plate"
    for (sysname,) in conn.execute(sa.text(
            "SELECT DISTINCT system FROM auth_sessions WHERE system != ''")):
        if sysname:
            names.setdefault(sysname, "plate")
    for name, kind in sorted(names.items()):
        conn.execute(services.insert().values(
            name=name, system=name, kind=kind))
    # service_meta 说明并入(存量 0 行,通用逻辑)
    for svc, desc in conn.execute(sa.text(
            "SELECT service_name, description FROM service_meta")):
        conn.execute(services.update().where(
            sa.text("name = :n")).values(description=desc), {"n": svc})

    # ── ⑤ environments.lines → 实例行(版本线收口)───────────────
    for env_id, lines_raw in conn.execute(sa.text(
            "SELECT id, lines FROM environments")):
        lines = lines_raw if isinstance(lines_raw, dict) else {}
        try:
            lines = lines or json.loads(lines_raw or "{}")
        except (TypeError, ValueError):
            lines = {}
        for system, line in (lines or {}).items():
            if system and line:
                conn.execute(sa.text(
                    "INSERT INTO system_env_instances (system, env_id, line) "
                    "VALUES (:s, :e, :l) ON CONFLICT (system, env_id) "
                    "DO UPDATE SET line = EXCLUDED.line"),
                    {"s": system, "e": env_id, "l": str(line)})

    if default_env is not None:
        # ── ⑥ 凭证 → 账户(env 兜底默认环境;密文密码直拷)────────
        rows = conn.execute(sa.text(
            "SELECT id, owner_id, project_id, alias, system, env_id, url, "
            "username_enc, password_enc, token_type, expires_in, "
            "account_fields, is_default FROM auth_sessions "
            "ORDER BY id")).mappings().all()
        account_id_by_alias: dict[tuple[int | None, int | None, str], int] = {}
        for r in rows:
            env = r["env_id"] if r["env_id"] is not None else default_env
            system = r["system"] or ""
            username = _decrypt(r["username_enc"])
            res = conn.execute(sa.text(
                "INSERT INTO auth_accounts (owner_id, project_id, system, "
                "env_id, username, password_enc, token_type, expires_in, "
                "account_fields, is_default, created_at, updated_at) "
                "VALUES (:o, :p, :s, :e, :u, :pw, :tt, :ei, :af, :d, "
                "now(), now()) ON CONFLICT DO NOTHING "
                "RETURNING id"),
                {"o": r["owner_id"], "p": r["project_id"], "s": system,
                 "e": env, "u": username, "pw": r["password_enc"],
                 "tt": r["token_type"], "ei": r["expires_in"],
                 "af": json.dumps(r["account_fields"] or {}),
                 "d": bool(r["is_default"])})
            aid = res.scalar()
            if aid is None:
                # 撞唯一键(同键多行):弃旧取新语义 —— 取既有行
                aid = conn.execute(sa.text(
                    "SELECT id FROM auth_accounts WHERE owner_id IS NOT "
                    "DISTINCT FROM :o AND project_id IS NOT DISTINCT FROM "
                    ":p AND system = :s AND env_id = :e AND username = :u"
                ), {"o": r["owner_id"], "p": r["project_id"], "s": system,
                    "e": env, "u": username}).scalar()
            account_id_by_alias[(r["owner_id"], r["project_id"],
                                 r["alias"])] = aid
            # 凭证 url → 实例 login_url 候选(is_default 行优先,
            # 其余候选丢弃 —— 迁移报告见 note)
            if system:
                conn.execute(sa.text(
                    "INSERT INTO system_env_instances (system, env_id, "
                    "login_url) VALUES (:s, :e, :u) "
                    "ON CONFLICT (system, env_id) DO UPDATE SET login_url = "
                    "CASE WHEN EXCLUDED.login_url != '' "
                    "AND system_env_instances.login_url = '' "
                    "THEN EXCLUDED.login_url "
                    "ELSE system_env_instances.login_url END"),
                    {"s": system, "e": env, "u": r["url"] or ""})

        # ── ⑦ 条目生成:凭证 alias(自动补声明)+ 旧别名表 ─────────
        idents: dict[str, dict] = {}
        for (o, p, alias), aid in account_id_by_alias.items():
            cred = next(r for r in rows if r["owner_id"] == o
                        and r["project_id"] == p and r["alias"] == alias)
            env = cred["env_id"] if cred["env_id"] is not None \
                else default_env
            username = _decrypt(cred["username_enc"])
            idents[alias] = dict(
                base_service=cred["system"] or "", env_id=env,
                ref_mode="username", ref_username=username)
        for alias, base, slot in conn.execute(sa.text(
                "SELECT alias_name, base_service, slot FROM service_aliases")):
            if alias in idents:
                idents[alias]["base_service"] = base or \
                    idents[alias]["base_service"]
                continue
            ref_user = ""
            for (o, p, a), aid in account_id_by_alias.items():
                if a == slot and slot:
                    cred = next(r for r in rows if r["owner_id"] == o
                                and r["project_id"] == p and r["alias"] == a)
                    ref_user = _decrypt(cred["username_enc"])
                    break
            idents[alias] = dict(
                base_service=base or "", env_id=default_env,
                ref_mode=("username" if ref_user else "default"),
                ref_username=ref_user)
        for alias, spec in sorted(idents.items()):
            if not spec["base_service"]:
                continue  # 未归类凭证无服务锚,跳过(数据非保障项)
            conn.execute(sa.text(
                "INSERT INTO service_identities (alias_name, base_service, "
                "env_id, ref_mode, ref_username) VALUES (:a, :b, :e, :m, :u)"
                " ON CONFLICT (alias_name) DO NOTHING"),
                {"a": alias, "b": spec["base_service"],
                 "e": spec["env_id"], "m": spec["ref_mode"],
                 "u": spec["ref_username"]})

    # ── ⑧ carry 坐标:service_name→config_key,+env_id,唯一键重建 ──
    op.drop_constraint("uq_carry_svc_path", "carry_service_bindings",
                       type_="unique")
    op.alter_column("carry_service_bindings", "service_name",
                    new_column_name="config_key")
    op.add_column("carry_service_bindings",
                  sa.Column("env_id", sa.Integer(),
                            sa.ForeignKey("environments.id",
                                          ondelete="SET NULL"),
                            nullable=True))
    op.create_unique_constraint(
        "uq_carry_svc_path", "carry_service_bindings",
        ["scope", "scope_id", "env_id", "config_key", "field_path"],
        postgresql_nulls_not_distinct=True)

    # ── ⑨ 退役:旧表 + environments.lines 列 ─────────────────────
    # access_token_scopes 的 FK 先摘(scope 值域语义延续:条目名/账户 id),
    # drop 后重建到新表;重建前清孤儿 scope 行(测试用户令牌残留)
    op.drop_constraint("access_token_scopes_alias_name_fkey",
                       "access_token_scopes", type_="foreignkey")
    op.drop_constraint("access_token_scopes_auth_id_fkey",
                       "access_token_scopes", type_="foreignkey")
    op.drop_table("service_aliases")
    op.drop_table("auth_sessions")
    op.drop_table("service_meta")
    op.drop_column("environments", "lines")
    conn.execute(sa.text(
        "DELETE FROM access_token_scopes s WHERE s.auth_id IS NOT NULL "
        "AND NOT EXISTS (SELECT 1 FROM auth_accounts a "
        "WHERE a.id = s.auth_id)"))
    conn.execute(sa.text(
        "DELETE FROM access_token_scopes s WHERE s.alias_name IS NOT NULL "
        "AND NOT EXISTS (SELECT 1 FROM service_identities i "
        "WHERE i.alias_name = s.alias_name)"))
    op.create_foreign_key(
        "access_token_scopes_alias_name_fkey", "access_token_scopes",
        "service_identities", ["alias_name"], ["alias_name"])
    op.create_foreign_key(
        "access_token_scopes_auth_id_fkey", "access_token_scopes",
        "auth_accounts", ["auth_id"], ["id"])


def downgrade() -> None:
    raise NotImplementedError(
        "开发环境直切(重构决策 8):不提供回滚 —— 恢复走 pre-migration "
        "dump(app-pg-*.dump 惯例)")
