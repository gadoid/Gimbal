"""执行配置分层⑥(决策 8):个人 carry 层一次性迁移(0054)+ 停读。

迁移:('user', uid) 绑定行 → 默认执行配置 systems[].carryOverrides
(按服务分组,键冲突以配置现有值为准);run.environment 偏好 → 默认配置
environment_id(仅配置缺省时);迁后删个人层行(不做双源回落)。
停读:carry 链个人层不再构成 tier;carry API scope=user 422 指路。
"""
from __future__ import annotations

import json

from alembic import command

from .test_migrations import _cfg, _revision, temp_schema
from .helpers import register_and_login
from app.core import db as db_module
from app.services.carry_injection import build_carry_context


def _sync(sync_url: str, stmts: list[tuple[str, dict]]) -> None:
    from sqlalchemy import create_engine, text

    eng = create_engine(sync_url)
    try:
        with eng.begin() as conn:
            for sql, params in stmts:
                conn.execute(text(sql), params)
    finally:
        eng.dispose()


def _sync_all(sync_url: str, sql: str):
    from sqlalchemy import create_engine, text

    eng = create_engine(sync_url)
    try:
        with eng.begin() as conn:
            return conn.execute(text(sql)).all()
    finally:
        eng.dispose()


def test_0054_migrates_user_layer_into_default_config():
    """个人层绑定+环境偏好 → 默认配置 systems 覆盖 + environment_id;
    已有默认配置时并进(键冲突以配置现有值为准);迁后个人层行删除。"""
    with temp_schema() as (_schema, sync_url):
        command.upgrade(_cfg(sync_url), "0053_exec_configs")
        # 造数:用户 + 环境偏好 + 个人层绑定(两服务)+ 已有默认配置
        # (无环境、fin-service 已带 grade=A 的覆盖)
        uid = _sync_all(sync_url,
                        "INSERT INTO users (username, password_hash,"
                        " display_name, role, is_active, is_system,"
                        " created_at, updated_at)"
                        " VALUES ('mig6', 'x', 'mig6', 'user', true,"
                        " false, now(), now()) RETURNING id")[0][0]
        env_id = _sync_all(sync_url,
                           "INSERT INTO environments (name, description,"
                           " lines, is_default, created_at, updated_at)"
                           " VALUES ('mig-env', '', '{}', false, now(),"
                           " now()) RETURNING id")[0][0]
        pub = _sync_all(sync_url,
                        "SELECT id FROM projects WHERE kind='public'")[0][0]
        _sync(sync_url, [
            ("INSERT INTO user_prefs (user_id, key,"
             " value) VALUES (:u, 'run.environment',"
             " CAST(:v AS JSONB))",
             {"u": uid, "v": json.dumps({"environmentId": env_id})}),
            ("INSERT INTO carry_service_bindings (service_name, scope,"
             " scope_id, field_path, value, updated_by_id,"
             " updated_by_name)"
             " VALUES ('fin-service', 'user', :u, '$.grade', 'B', NULL, 't'),"
             "        ('crm-service',  'user', :u, '$.city', 'SZ', NULL, 't')",
             {"u": uid}),
            ("INSERT INTO exec_configs (scope, scope_id, name, is_default,"
             " environment_id, payload, created_at, updated_at)"
             " VALUES ('user', :u, '我的默认', true, NULL,"
             " CAST(:p AS JSONB), now(), now())",
             {"u": uid, "p": json.dumps({"systems": [
                 {"service": "fin-service", "bindings": {},
                  "carryOverrides": {"$.grade": "A"}}]})}),
        ])

        command.upgrade(_cfg(sync_url), "head")
        assert _revision(sync_url) is not None

        row = _sync_all(sync_url,
                        "SELECT environment_id, payload FROM exec_configs"
                        " WHERE scope='user' AND scope_id="
                        f"{uid} AND is_default")[0]
        assert row[0] == env_id                    # 偏好 → 配置环境(配置缺省)
        payload = row[1] if isinstance(row[1], dict) else json.loads(row[1])
        systems = payload["systems"]
        by_svc = {s["service"]: s for s in systems}
        # 键冲突以配置现有值为准($.grade 保持 A);新服务整体并入
        assert by_svc["fin-service"]["carryOverrides"]["$.grade"] == "A"
        assert by_svc["crm-service"]["carryOverrides"] == {"$.city": "SZ"}
        # 迁后个人层行删除(不做双源回落)
        n = _sync_all(sync_url,
                      "SELECT count(*) FROM carry_service_bindings"
                      " WHERE scope='user'")[0][0]
        assert n == 0


def test_0054_pref_only_creates_default_config():
    """只有环境偏好、无个人层行 → 也保证默认配置存在并带上环境。"""
    with temp_schema() as (_schema, sync_url):
        command.upgrade(_cfg(sync_url), "0053_exec_configs")
        uid = _sync_all(sync_url,
                        "INSERT INTO users (username, password_hash,"
                        " display_name, role, is_active, is_system,"
                        " created_at, updated_at)"
                        " VALUES ('mig7', 'x', 'mig7', 'user', true,"
                        " false, now(), now()) RETURNING id")[0][0]
        env_id = _sync_all(sync_url,
                           "INSERT INTO environments (name, description,"
                           " lines, is_default, created_at, updated_at)"
                           " VALUES ('mig7-env', '', '{}', false, now(),"
                           " now()) RETURNING id")[0][0]
        _sync(sync_url, [
            ("INSERT INTO user_prefs (user_id, key,"
             " value) VALUES (:u, 'run.environment',"
             " CAST(:v AS JSONB))",
             {"u": uid, "v": json.dumps({"environmentId": env_id})}),
        ])
        command.upgrade(_cfg(sync_url), "head")
        rows = _sync_all(sync_url,
                         "SELECT name, environment_id FROM exec_configs"
                         f" WHERE scope='user' AND scope_id={uid}")
        assert len(rows) == 1 and rows[0] == ("默认", env_id)


# ── 停读:个人层不再构成 tier + carry API 指路 ─────────────────────

async def test_user_carry_layer_no_longer_a_tier(client, fresh_db):
    """决策 8:个人层行(如有残留/直插)不再被 carry 合成读取。"""
    await register_and_login(client, "ec6t", "pw123456")
    async with db_module.SessionLocal() as s:
        from sqlalchemy import text as _t
        uid = (await s.execute(_t(
            "SELECT id FROM users WHERE username='ec6t'"))).scalar()
        # 直插一行个人层绑定(模拟残留)
        await s.execute(_t(
            "INSERT INTO carry_service_bindings (service_name, scope,"
            " scope_id, field_path, value, updated_by_name)"
            " VALUES ('fin-service', 'user', :u, '$.a', 'stale', 't')"),
            {"u": uid})
        await s.commit()

    definition = {"steps": [{"kind": "step",
                             "call": {"service": "fin-service",
                                      "method": "GET", "path": "/x"},
                             "request": {"kind": "request", "body": {}},
                             "strategy": []}]}
    async with db_module.SessionLocal() as s:
        from app.models.service_alias import ServiceAlias
        s.add(ServiceAlias(alias_name="fin-service", base_service="fin-service",
                           kind="external"))
        await s.commit()
    async with db_module.SessionLocal() as s:
        ctx = await build_carry_context(s, definition, user_id=uid)
    assert ctx.service_bindings["fin-service"] == {}   # 个人层停读


async def test_carry_api_user_scope_retired(client, fresh_db):
    await register_and_login(client, "ec6a", "pw123456")
    h = await register_and_login(client, "ec6a", "pw123456")
    r = await client.get("/api/carry/bindings/fin-service", headers=h,
                         params={"scope": "user"})
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "carry_user_scope_retired"
    r = await client.put("/api/carry/bindings/fin-service", headers=h,
                         params={"scope": "user"},
                         json={"bindings": {"$.a": "x"}})
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "carry_user_scope_retired"
    # 可见层并集不再含个人层
    r = await client.get("/api/carry/bindings", headers=h)
    assert r.status_code == 200
    assert all(row["scope"] != "user" for row in r.json()["rows"])
