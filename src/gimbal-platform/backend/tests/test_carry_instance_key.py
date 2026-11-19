"""carry 实例档(redesign §8.9,2026-11-19)— 系统档 → 实例档。

钉住:
  * 键序:条目 > 实例(system, 执行标签 env) > 服务 > 层默认 —— 执行链
    ``build_carry_context`` 与预览 ``resolve_effective_config`` 同序
    (预览此前漏粗档,本批补齐既有口径差);
  * store:实例行(instance_env_id>0)与基线行同 config_key 并存,
    两侧整表替换互不波及;
  * API:实例值端点(GET/PUT /bindings/{system}/instances/{envId})门与
    404(无系统/无实例行)、裸系统键 422、同名碰撞(服务名=系统名按
    服务档放行);
  * 漂移:实例行单列报告(instanceEnvId 标注,face = 系统成员并集);
  * 迁移 0063:时代造形(四键 + 系统键行)→ 列/五键约束/纯系统键行
    删除、同名服务档行保留。
"""
from __future__ import annotations

from sqlalchemy import text

from app.core import db as db_module
from app.services import carry_store

from .helpers import register_and_login
from .test_scenario_visibility_and_copy import _member


async def _admin(client):
    return await register_and_login(client, "carry_admin", "pw123456")


def _svc_step(service: str = "fin-service") -> dict:
    return {"kind": "step",
            "call": {"service": service, "path": "/x"},
            "request": {"kind": "request", "body": {}}}


# ── store:实例档读写与基线行隔离 ──────────────────────────────────
async def test_store_instance_roundtrip_and_isolation(fresh_db):
    async with db_module.SessionLocal() as db:
        await carry_store.put_bindings(
            db, "fin", {"$.a": "svc"},
            updated_by_id=None, updated_by_name="u")
        await carry_store.put_instance_bindings(
            db, "fin", 2, {"$.a": "inst", "$.n": None},
            updated_by_id=None, updated_by_name="u")
        await db.commit()
        # 两档并存:基线读只见基线,实例读只见实例(env 坐标精确)
        assert await carry_store.get_bindings(db, "fin") == {"$.a": "svc"}
        assert await carry_store.get_instance_bindings(db, "fin", 2) == \
            {"$.a": "inst", "$.n": None}
        assert await carry_store.get_instance_bindings(db, "fin", 1) == {}
        # 基线整表替换不波及实例行(同名碰撞:键同为 "fin")
        await carry_store.put_bindings(
            db, "fin", {"$.a": "svc2"},
            updated_by_id=None, updated_by_name="u")
        inst = await carry_store.get_instance_bindings(db, "fin", 2)
        assert inst["$.a"] == "inst"
        # 实例整表替换不波及基线
        await carry_store.put_instance_bindings(
            db, "fin", 2, {"$.x": "1"},
            updated_by_id=None, updated_by_name="u")
        assert await carry_store.get_bindings(db, "fin") == {"$.a": "svc2"}
        await db.commit()


async def test_store_is_pure_system_key(fresh_db):
    from app.models import Service

    async with db_module.SessionLocal() as db:
        db.add(Service(name="fin-service", system="fin"))
        db.add(Service(name="pay", system="pay"))  # 同名:服务名 = 系统名
        await db.commit()
        assert await carry_store.is_pure_system_key(db, "fin-service") is False
        assert await carry_store.is_pure_system_key(db, "fin") is True
        # 同名碰撞按服务名判定 → 不是系统裸键
        assert await carry_store.is_pure_system_key(db, "pay") is False
        assert await carry_store.is_pure_system_key(db, "unknown") is False


# ── 执行链键序(条目 > 实例 > 服务 > 层默认)──────────────────────
async def _seed_tier_fixture(env_name: str = "UAT") -> tuple[int, int]:
    """主档(单系统双语义)+ 两环境(仅其一有实例行)+ 三档值。"""
    from app.models import Environment, Service, SystemEnvInstance

    async with db_module.SessionLocal() as db:
        db.add(Service(name="fin-service", system="fin"))
        db.add(Environment(name=env_name))
        db.add(Environment(name="SIT"))
        await db.flush()
        envs = dict((await db.execute(
            text("SELECT name, id FROM environments"))).all())
        uat, sit = envs[env_name], envs["SIT"]
        db.add(SystemEnvInstance(system="fin", env_id=uat))
        await db.flush()
        await carry_store.put_bindings(
            db, "fin-service", {"$.a": "svc", "$.c": "svc-only"},
            updated_by_id=None, updated_by_name="u")
        await carry_store.put_instance_bindings(
            db, "fin", uat, {"$.a": "inst", "$.b": "inst-only"},
            updated_by_id=None, updated_by_name="u")
        await carry_store.put_bindings(
            db, "fin-service.qa", {"$.a": "alias"},
            updated_by_id=None, updated_by_name="u")
        await db.commit()
        return uat, sit


async def test_injection_instance_tier_order(fresh_db, plate):
    from app.services.carry_injection import build_carry_context

    plate.services = []  # 目录空 → 键解析只认主档(注册簿自足)
    uat, sit = await _seed_tier_fixture()
    definition = {"steps": [_svc_step()]}

    async with db_module.SessionLocal() as db:
        # 实例压过服务(部署差异化默认值——§8.9 核心诉求)
        ctx = await build_carry_context(db, definition, env_id=uat)
        assert ctx.service_bindings["fin-service"] == {
            "$.a": "inst", "$.b": "inst-only", "$.c": "svc-only"}
        # 条目键压过实例(绑定换名 → carry 条目键随之切换)
        ctx = await build_carry_context(
            db, definition, env_id=uat,
            bindings={"fin-service": {"alias": "fin-service.qa"}})
        assert ctx.service_bindings["fin-service"]["$.a"] == "alias"
        # env_id=None(标签链空/导入析出)→ 实例档跳过
        ctx = await build_carry_context(db, definition)
        assert ctx.service_bindings["fin-service"] == {
            "$.a": "svc", "$.c": "svc-only"}
        # 该环境无实例值(SIT 无实例行)→ 回落服务档
        ctx = await build_carry_context(db, definition, env_id=sit)
        assert ctx.service_bindings["fin-service"]["$.a"] == "svc"


async def test_preview_chain_matches_execution(fresh_db, plate):
    """预览逐值带来源,档序与执行链一致(补齐此前漏粗档的口径差)。"""
    from app.services.env_chain import EnvChoice
    from app.services.run_prepare import resolve_effective_config

    plate.services = []
    uat, _sit = await _seed_tier_fixture()
    definition = {"steps": [_svc_step()]}

    async with db_module.SessionLocal() as db:
        cfg = await resolve_effective_config(
            db, definition, environment=EnvChoice(env_id=uat, source="default"))
        merged = cfg.carry["fin-service"]
        assert merged["$.a"]["value"] == "inst"
        assert merged["$.a"]["source"].endswith(f":instance:{uat}")
        assert merged["$.c"]["source"].endswith(":base")
        assert merged["$.b"]["value"] == "inst-only"
        # 无执行标签 → 实例档不进预览(与执行链同口径)
        cfg2 = await resolve_effective_config(db, definition)
        assert "$.b" not in cfg2.carry["fin-service"]
        assert cfg2.carry["fin-service"]["$.a"]["value"] == "svc"


# ── API:实例端点 / 裸系统键 422 / 同名碰撞 ────────────────────────
async def test_api_instance_endpoints_gates(client, plate):
    from app.models import Environment, Service, SystemEnvInstance

    plate.services = []
    async with db_module.SessionLocal() as db:
        db.add(Service(name="fin-service", system="fin"))
        db.add(Environment(name="UAT"))
        db.add(Environment(name="SIT"))
        await db.flush()
        envs = dict((await db.execute(
            text("SELECT name, id FROM environments"))).all())
        db.add(SystemEnvInstance(system="fin", env_id=envs["UAT"]))
        await db.commit()
    admin = await _admin(client)

    # 实例档读写回环(值对该系统全部服务在本环境生效)
    r = await client.put(
        f"/api/carry/bindings/fin/instances/{envs['UAT']}", headers=admin,
        json={"bindings": {"$.a": "inst", "$.n": None}})
    assert r.status_code == 200, r.text
    r = await client.get(
        f"/api/carry/bindings/fin/instances/{envs['UAT']}", headers=admin)
    assert r.json()["bindings"] == {"$.a": "inst", "$.n": None}

    # 404:主档无该系统
    r = await client.put(
        f"/api/carry/bindings/nosys/instances/{envs['UAT']}", headers=admin,
        json={"bindings": {}})
    assert r.status_code == 404
    # 404:系统在该环境没有实例行(实例是值的宿主)
    r = await client.put(
        f"/api/carry/bindings/fin/instances/{envs['SIT']}", headers=admin,
        json={"bindings": {}})
    assert r.status_code == 404

    # 裸系统键值表端点 422(系统档退场,指路实例档)
    r = await client.get("/api/carry/bindings/fin", headers=admin)
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "carry_system_key_retired"
    r = await client.put("/api/carry/bindings/fin", headers=admin,
                         json={"bindings": {}})
    assert r.status_code == 422
    # 服务名键照旧
    r = await client.get("/api/carry/bindings/fin-service", headers=admin)
    assert r.status_code == 200

    # 写面守门:普通成员 403(与裸键写面同口径)
    member = await _member(client, "carry_inst_mem")
    r = await client.put(
        f"/api/carry/bindings/fin/instances/{envs['UAT']}", headers=member,
        json={"bindings": {}})
    assert r.status_code == 403


async def test_api_same_name_service_tier_still_writable(client, plate):
    """同名碰撞:键既是服务名又是系统名 —— 基线(服务档)与实例档
    两路都合法,行集靠 instance_env_id 区分。"""
    from app.models import Environment, Service, SystemEnvInstance

    plate.services = []
    async with db_module.SessionLocal() as db:
        db.add(Service(name="pay", system="pay"))
        db.add(Environment(name="UAT"))
        await db.flush()
        env = (await db.execute(
            text("SELECT id FROM environments LIMIT 1"))).scalar()
        db.add(SystemEnvInstance(system="pay", env_id=env))
        await db.commit()
    admin = await _admin(client)

    r = await client.put("/api/carry/bindings/pay", headers=admin,
                         json={"bindings": {"$.a": "svc"}})
    assert r.status_code == 200, r.text
    r = await client.put(
        f"/api/carry/bindings/pay/instances/{env}", headers=admin,
        json={"bindings": {"$.a": "inst"}})
    assert r.status_code == 200, r.text
    r = await client.get("/api/carry/bindings/pay", headers=admin)
    assert r.json()["bindings"] == {"$.a": "svc"}
    r = await client.get(
        f"/api/carry/bindings/pay/instances/{env}", headers=admin)
    assert r.json()["bindings"] == {"$.a": "inst"}


async def test_drift_reports_instance_rows(client, plate):
    """实例行单列报告:instanceEnvId 标注,face = 系统成员服务并集。"""
    from app.models import (Environment, Service, SystemEnvInstance)

    async with db_module.SessionLocal() as db:
        db.add(Service(name="fin-service", system="fin"))
        db.add(Service(name="fin-report", system="fin"))
        db.add(Environment(name="UAT"))
        await db.flush()
        env = (await db.execute(
            text("SELECT id FROM environments LIMIT 1"))).scalar()
        db.add(SystemEnvInstance(system="fin", env_id=env))
        await carry_store.put_instance_bindings(
            db, "fin", env, {"$.remark": "r", "$.gone": "g"},
            updated_by_id=None, updated_by_name="u")
        await db.commit()
    plate.services = [{"name": "fin-service"}, {"name": "fin-report"}]
    plate.items = [
        {"id": "fin.ep1", "version": "1.0.0", "updated_at": None,
         "service": "fin-service"},
        {"id": "rep.ep1", "version": "1.0.0", "updated_at": None,
         "service": "fin-report"},
    ]
    plate.fulls = {
        "fin.ep1": {"request": {"declarations": [
            {"path": "$.remark", "state": "carry", "type": "string"}]}},
        "rep.ep1": {"request": {"declarations": [
            {"path": "$.orgNo", "state": "carry", "type": "string"}]}},
    }
    admin = await _admin(client)
    r = await client.get("/api/carry/drift", headers=admin)
    assert r.status_code == 200, r.text
    rows = r.json()["services"]
    inst_rows = [s for s in rows if s.get("instanceEnvId") == env]
    assert len(inst_rows) == 1
    # face = 成员并集($.orgNo 来自 fin-report);$.gone 面外 → orphaned
    assert inst_rows[0]["orphaned"] == ["$.gone"]
    assert inst_rows[0]["uncovered"] == ["$.orgNo"]
    # 基线行不受实例行混入(实例行恰一条,其余行无 instanceEnvId)
    assert len([s for s in rows if s.get("instanceEnvId")]) == 1


# ── 迁移 0063:时代造形重放 ────────────────────────────────────────
def test_migration_0063_drops_system_rows_keeps_service_rows():
    """baseline 是动态 create_all(fresh 链直建终态,0063 守卫空转);
    本用例模拟「经历过 0062 的库」:升到 0062 后手动降形(去列 + 四键),
    重放 0063 验证 加列/删纯系统键行/五键约束 的真实逻辑。"""
    from alembic import command

    from .test_migrations import _cfg, _revision, _upgrade_to, temp_schema

    with temp_schema() as (_schema, sync_url):
        _upgrade_to(sync_url, "0062_executions_project_id_index")
        # temp_schema 的 sync_url 已是 postgresql+psycopg(v3)同步 URL
        # —— 仓库依赖无 psycopg2,勿改写驱动名
        eng_sql = sync_url
        from sqlalchemy import create_engine

        eng = create_engine(eng_sql)
        try:
            with eng.begin() as conn:
                # 时代降形:回到 0062 时代的四键形状(create_all 直建的
                # 终态含 instance_env_id,先拆掉)
                conn.execute(text(
                    "ALTER TABLE carry_service_bindings"
                    " DROP CONSTRAINT uq_carry_svc_path"))
                conn.execute(text(
                    "ALTER TABLE carry_service_bindings"
                    " DROP COLUMN instance_env_id"))
                conn.execute(text(
                    "ALTER TABLE carry_service_bindings ADD CONSTRAINT"
                    " uq_carry_svc_path UNIQUE"
                    " (scope, scope_id, config_key, field_path)"))
                # 主档:fin 系统(成员 fin-service)+ 同名 pay
                conn.execute(text(
                    "INSERT INTO services (name, system, kind, created_at,"
                    " updated_at) VALUES ('fin-service', 'fin', 'plate',"
                    " now(), now())"))
                conn.execute(text(
                    "INSERT INTO services (name, system, kind, created_at,"
                    " updated_at) VALUES ('pay', 'pay', 'plate',"
                    " now(), now())"))
                # 纯系统键行(迁移删除)/ 服务档行(保留)/ 同名服务档行(保留)
                for key in ("fin", "fin-service", "pay"):
                    conn.execute(text(
                        "INSERT INTO carry_service_bindings"
                        " (config_key, scope, scope_id, field_path, value,"
                        " updated_by_name)"
                        " VALUES (:k, 'project', 0, '$.a', 'v', 'seed')"),
                        {"k": key})
        finally:
            eng.dispose()
        # 重放 0063(加列 / 删纯系统键行 / 重建五键约束)
        command.upgrade(_cfg(sync_url), "0063_carry_instance_key")
        assert _revision(sync_url) == "0063_carry_instance_key"

        eng = create_engine(eng_sql)
        try:
            with eng.begin() as conn:
                rows = conn.execute(text(
                    "SELECT config_key, instance_env_id"
                    " FROM carry_service_bindings ORDER BY config_key"
                )).all()
                # 纯系统键 'fin' 被删;服务档与同名服务档保留,sentinel 0
                assert [r[0] for r in rows] == ["fin-service", "pay"]
                assert all(r[1] == 0 for r in rows)
                # 五键唯一约束在位(插同键实例行不冲突)
                conn.execute(text(
                    "INSERT INTO carry_service_bindings"
                    " (config_key, scope, scope_id, field_path, value,"
                    " updated_by_name, instance_env_id)"
                    " VALUES ('pay', 'project', 0, '$.a', 'v2', 'seed', 7)"))
                cols = conn.execute(text(
                    "SELECT constraint_name FROM information_schema"
                    ".table_constraints WHERE constraint_name ="
                    " 'uq_carry_svc_path'")).all()
                assert cols, "五键唯一约束应在位"
        finally:
            eng.dispose()
