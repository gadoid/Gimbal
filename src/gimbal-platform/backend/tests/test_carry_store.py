"""carry 值层两表 — 行存在即注入;value=None 显式 null;行不存在=未配置(spec §3.1)。"""
from __future__ import annotations

from app.core import db as db_module
from app.models import Environment
from app.services import carry_store


async def test_put_get_bindings_roundtrip(fresh_db):
    async with db_module.SessionLocal() as db:
        await carry_store.put_bindings(db, "fin-service",
                                       {"$.remark": "压测-张三",
                                        "$.notifyUsers": None},
                                       updated_by_id=None, updated_by_name="alice")
        await db.commit()
    async with db_module.SessionLocal() as db:
        got = await carry_store.get_bindings(db, "fin-service")
    assert got == {"$.remark": "压测-张三", "$.notifyUsers": None}


async def test_put_replaces_whole_row_set(fresh_db):
    async with db_module.SessionLocal() as db:
        await carry_store.put_bindings(db, "s", {"$.a": "1", "$.b": "2"}, updated_by_id=None, updated_by_name="u")
        await carry_store.put_bindings(db, "s", {"$.a": "1x"}, updated_by_id=None, updated_by_name="u")
        await db.commit()
        assert await carry_store.get_bindings(db, "s") == {"$.a": "1x"}


async def test_defaults_null_semantics(fresh_db):
    async with db_module.SessionLocal() as db:
        await carry_store.put_defaults(db, {"$.appCode": "TRACE-V2",
                                            "$.remark": None},
                                       updated_by_id=None, updated_by_name="bob")
        await db.commit()
        defaults = await carry_store.get_defaults(db)
    assert defaults == {"$.appCode": "TRACE-V2", "$.remark": None}
    # 行不存在才是"未配置":键不在 dict 里
    assert "$.absent" not in defaults


async def test_bindings_env_overlay_beats_baseline(fresh_db):
    """§1.7 稀疏覆盖读面:env 命中行**字段级**覆盖基线;不传 env 只见基线。"""
    async with db_module.SessionLocal() as db:
        env = Environment(name="预发", is_default=False)
        db.add(env)
        await db.flush()
        await carry_store.put_bindings(db, "s", {"$.a": "base", "$.b": "1"},
                                       updated_by_id=None, updated_by_name="u")
        await carry_store.put_bindings(db, "s", {"$.a": "uat"},
                                       updated_by_id=None, updated_by_name="u",
                                       env_id=env.id)
        await db.commit()
        base_only = await carry_store.get_bindings(db, "s")
        overlaid = await carry_store.get_bindings(db, "s", env_id=env.id)
    assert base_only == {"$.a": "base", "$.b": "1"}
    # $.b 无覆盖行 → 基线值透出(稀疏:只盖写到的字段)
    assert overlaid == {"$.a": "uat", "$.b": "1"}
