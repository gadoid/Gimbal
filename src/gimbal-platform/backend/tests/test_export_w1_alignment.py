"""W1(场景导入 v2.3 方案):/export 对齐可执行形态。

口径:GET /scenarios/{id}/export 输出 = preview-plate 默认导出(无 overlay)
同源(组装收敛在 scenarios._materialized_executable)—— carry 无条件物化、
凭证/服务绑定零注入、scenarioId 与 meta.plate 保留。真实 plate 回环
(导出→导入)随 W4/W6 落地;本文件用 PlateMock 锁行为基线。
"""
from __future__ import annotations

from app.core import db as db_module
from app.services import carry_store

from .helpers import make_draft as _draft, register_and_login
from .test_scenario_composer_plate_integration import PlateMock, plate_mock  # noqa: F401
from .test_scenario_visibility_and_copy import _member
from .test_export_overlay_equivalence import (
    _carry_step,  # noqa: F401 — 复用 carry 锚点形态(存储形态)
    _seed,
)

_SCENARIO_ID = "sc-test"


async def test_export_executable_shape_and_carry(
        client, plate_mock: PlateMock):
    """/export = 可执行形态:carry 无条件物化 + 凭证零注入 + 身份保留。"""
    plate_mock.behaviour = "echo"
    plate_mock.services = [{"name": "fin-service"}]
    plate_mock.fulls = {"fin.ep1": {"request": {"declarations": [
        {"path": "$.remark", "state": "carry", "type": "string"},
        {"path": "$.appCode", "state": "carry", "type": "string"}]}}}
    async with db_module.SessionLocal() as db:
        await carry_store.put_bindings(
            db, "fin-service", {"$.remark": "压测-张三"},
            updated_by_id=None, updated_by_name="bob")
        await carry_store.put_defaults(
            db, {"$.appCode": "TRACE-V2"},
            updated_by_id=None, updated_by_name="bob")
        await db.commit()

    bob = await _member(client, "bob")
    await _seed(client, bob, draft=_draft(
        steps=[_carry_step()], vars_map={},
        owner="bob", createTime="2026-08-27T00:00:00Z", description="",
        author="", tags=[], version="v0.1.0", expire=False, updateTime=None))

    r = await client.get(f"/api/scenarios/{_SCENARIO_ID}/export",
                         headers=bob)
    assert r.status_code == 200, r.text
    exported = r.json()
    # 可执行形态身份字段:顶层 scenarioId + meta.plate(working 缺省声明)
    assert exported.get("scenarioId") == _SCENARIO_ID
    assert (exported.get("meta") or {}).get("plate") == {"fin": "working"}
    # carry 无条件物化(绑定键 + 全局默认),与 preview-plate 默认导出同源
    body = exported["steps"][0]["request"]["body"]
    assert body["remark"] == "压测-张三"
    assert body["appCode"] == "TRACE-V2"
    # 凭证/服务绑定零注入(overlay 是唯一开关)
    config = exported.get("config") or {}
    users = config.get("users") or {}
    assert "qa1" not in users and "qa2" not in users


async def test_export_same_source_as_preview_default(
        client, plate_mock: PlateMock):
    """同源断言:同场景 /export ≡ preview-plate(无 overlay)的 converted。

    preview 输入 = 存储定义(GET 详情读回),两路 convert 输入一致,
    产物逐字段相等 —— _materialized_executable 是唯一组装点。
    """
    plate_mock.behaviour = "echo"
    bob = await _member(client, "bob")
    await _seed(client, bob, draft=_draft(
        steps=[_carry_step()], vars_map={},
        owner="bob", createTime="2026-08-27T00:00:00Z", description="",
        author="", tags=[], version="v0.1.0", expire=False, updateTime=None))

    r_exp = await client.get(f"/api/scenarios/{_SCENARIO_ID}/export",
                             headers=bob)
    assert r_exp.status_code == 200, r_exp.text

    # preview 输入 = 存储容器原样(ORM 直读;读侧 GET 是摊平形状,不适合
    # 重组)—— 保证两路 convert 输入逐字段一致
    from sqlalchemy import select

    from app.models.composer_scenario import ComposerScenario
    from app.services.scenario_store import definition_from_payload
    async with db_module.SessionLocal() as db:
        row = (await db.execute(select(ComposerScenario).where(
            ComposerScenario.scenario_id == _SCENARIO_ID))).scalar_one()
        stored_definition = definition_from_payload(row.payload or {})
        stored_ui = (row.payload or {}).get("ui") or {}

    r_prev = await client.post("/api/scenarios/preview-plate", headers=bob,
                               json={"definition": stored_definition,
                                     "ui": stored_ui})
    assert r_prev.status_code == 200, r_prev.text
    preview_converted = r_prev.json()["converted"]
    assert r_exp.json() == preview_converted


async def test_export_reader_gate_404(client, plate_mock: PlateMock):
    """读闸同详情页:非属主非 admin 的 member → 404(不泄露存在性)。"""
    plate_mock.behaviour = "echo"
    bob = await _member(client, "bob")   # 首个注册用户(admin)兼属主
    await _seed(client, bob, draft=_draft(
        steps=[_carry_step()], vars_map={}))
    carol = await register_and_login(client, "carol", "carolpass123")
    r = await client.get(f"/api/scenarios/{_SCENARIO_ID}/export",
                         headers=carol)
    assert r.status_code == 404
