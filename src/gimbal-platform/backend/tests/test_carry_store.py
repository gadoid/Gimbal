"""carry 值层两表 — 行存在即注入;value=None 显式 null;行不存在=未配置(spec §3.1)。"""
from __future__ import annotations

from app.core import db as db_module
from app.services import carry_store


async def test_put_get_bindings_roundtrip(fresh_db):
    async with db_module.SessionLocal() as db:
        await carry_store.put_bindings(db, "fin-service",
                                       {"$.remark": "压测-张三",
                                        "$.notifyUsers": None}, "alice")
        await db.commit()
    async with db_module.SessionLocal() as db:
        got = await carry_store.get_bindings(db, "fin-service")
    assert got == {"$.remark": "压测-张三", "$.notifyUsers": None}


async def test_put_replaces_whole_row_set(fresh_db):
    async with db_module.SessionLocal() as db:
        await carry_store.put_bindings(db, "s", {"$.a": "1", "$.b": "2"}, "u")
        await carry_store.put_bindings(db, "s", {"$.a": "1x"}, "u")
        await db.commit()
        assert await carry_store.get_bindings(db, "s") == {"$.a": "1x"}


async def test_defaults_null_semantics(fresh_db):
    async with db_module.SessionLocal() as db:
        await carry_store.put_defaults(db, {"$.appCode": "TRACE-V2",
                                            "$.remark": None}, "bob")
        await db.commit()
        defaults = await carry_store.get_defaults(db)
    assert defaults == {"$.appCode": "TRACE-V2", "$.remark": None}
    # 行不存在才是"未配置":键不在 dict 里
    assert "$.absent" not in defaults
