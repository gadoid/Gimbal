"""执行配置分层⑥(决策 8):个人 carry 层一次性迁入默认执行配置。

* ``carry_service_bindings`` 的 ``('user', uid)`` 行 → 该用户**默认执行
  配置**的 ``payload.systems[].carryOverrides``(按服务分组;已有默认
  配置则并进对应系统子配置,键冲突以配置现有值为准 —— 配置是此后唯一
  权威);迁完删除个人层行(迁后停读、不做双源回落);
* ``carry_global_defaults`` 的个人层行:新模型无家(执行配置覆盖按系统
  分组,层级默认的家是公共项目层)—— 行保留不删但全部读链已停,属
  死数据(规模为零:S4 起 dev 库无此类行);
* ``user_preferences`` 的 ``run.environment`` 偏好 → 默认配置
  ``environment_id``(仅当配置无环境时);偏好行保留(读侧兼容:无
  默认配置时回落旧偏好,§7)。

fresh 链守卫:baseline 不含个人层存量 → 空转。downgrade 不可逆
(值已并入配置 payload,按键拆回有合并歧义)—— no-op,回滚走应用层。
"""
from alembic import op
import sqlalchemy as sa

revision = "0054_exec_config_migration"
down_revision = "0053_exec_configs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("SET CONSTRAINTS ALL IMMEDIATE"))

    users = bind.execute(sa.text(
        "SELECT DISTINCT scope_id FROM carry_service_bindings"
        " WHERE scope = 'user'")).scalars().all()
    prefs: dict[int, int | None] = {}
    for uid, value in bind.execute(sa.text(
            "SELECT user_id, value FROM user_prefs"
            " WHERE key = 'run.environment'")).all():
        if isinstance(value, dict):
            value = value.get("environmentId")
        prefs[uid] = value if isinstance(value, int) and value > 0 else None

    moved: set[int] = set()
    for uid in users:
        rows = bind.execute(sa.text(
            "SELECT service_name, field_path, value FROM carry_service_bindings"
            " WHERE scope = 'user' AND scope_id = :u"
            " ORDER BY service_name, field_path"), {"u": uid}).all()
        _merge_into_default_config(bind, uid, rows, env_id=prefs.get(uid))
        moved.add(uid)
    for uid, env_id in prefs.items():
        if uid in moved or env_id is None:
            continue
        # 只有偏好、无个人层行:仍要保证默认配置存在并带上环境
        _merge_into_default_config(bind, uid, [], env_id=env_id)

    if moved:
        bind.execute(sa.text(
            "DELETE FROM carry_service_bindings WHERE scope = 'user'"))


def _merge_into_default_config(bind, uid: int, rows, *, env_id=None) -> None:
    """个人层行并进默认配置(无则建);环境仅在配置缺省时补。"""
    import json

    row = bind.execute(sa.text(
        "SELECT id, environment_id, payload FROM exec_configs"
        " WHERE scope = 'user' AND scope_id = :u AND is_default"
    ), {"u": uid}).fetchone()
    if row is None:
        payload = {"systems": []}
        bind.execute(sa.text(
            "INSERT INTO exec_configs"
            " (scope, scope_id, name, is_default, environment_id, payload,"
            "  created_at, updated_at)"
            " VALUES ('user', :u, :name, true, :env, CAST(:payload AS"
            " JSONB), now(), now())"),
            {"u": uid, "name": "默认", "env": env_id,
             "payload": json.dumps(payload)})
        row = bind.execute(sa.text(
            "SELECT id, environment_id, payload FROM exec_configs"
            " WHERE scope = 'user' AND scope_id = :u AND is_default"
        ), {"u": uid}).fetchone()

    payload = row[2] if isinstance(row[2], dict) else json.loads(row[2] or "{}")
    systems = payload.setdefault("systems", [])
    by_service = {s.get("service"): s for s in systems if isinstance(s, dict)}
    for service, field_path, value in rows:
        sub = by_service.get(service)
        if sub is None:
            sub = {"service": service, "bindings": {},
                   "carryOverrides": {}}
            systems.append(sub)
            by_service[service] = sub
        sub.setdefault("carryOverrides", {})
        # 键冲突以配置现有值为准(配置是此后唯一权威)
        sub["carryOverrides"].setdefault(field_path, value)
    new_env = row[1] if row[1] is not None else env_id
    bind.execute(sa.text(
        "UPDATE exec_configs SET payload = CAST(:payload AS JSONB),"
        " environment_id = :env, updated_at = now() WHERE id = :id"),
        {"payload": json.dumps(payload, ensure_ascii=False),
         "env": new_env, "id": row[0]})


def downgrade() -> None:
    # 不可逆:值已并入默认配置 payload(按键拆回有合并歧义);
    # 回滚走应用层(执行配置页把值搬回新家后手工恢复个人层行)。
    pass
