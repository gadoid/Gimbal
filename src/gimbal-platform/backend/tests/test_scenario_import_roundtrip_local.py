"""场景导入 · 真实 plate 回环(local-only,场景导入 v2.3 §8/W6)。

conftest 的 autouse 封闭桩被显式 ``set_client_for_tests(None)`` 脱离,
走本机真实 plate(127.0.0.1:8765);plate 不可达(CI/无本地服务)自动
skip —— 该用例是导出→导入→再导出的端到端行为基线,PlateMock 用例
(test_scenario_import_pipeline / test_export_w1_alignment)覆盖分支,
本用例覆盖「真 convert 产物可回环」这一 mock 证不了的事实。
"""
from __future__ import annotations

import secrets

import httpx
import pytest
from sqlalchemy import select

from app.core import db as db_module
from app.core.config import settings
from app.models.composer_run_scheme import ComposerRunScheme
from app.services import plate_client

from .helpers import make_draft, register_and_login


async def _plate_alive() -> bool:
    try:
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{settings.PLATE_BASE_URL}/api/system/fin/lines",
                            timeout=3)
            return r.status_code == 200
    except Exception:  # noqa: BLE001
        return False


async def _latest_fin_ref() -> str | None:
    try:
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{settings.PLATE_BASE_URL}/api/system/fin/lines",
                            timeout=3)
            items = (r.json().get("data") or {}).get("items") or []
            return items[0].get("latest") if items else None
    except Exception:  # noqa: BLE001
        return None


async def test_real_plate_export_import_roundtrip(client):
    if not await _plate_alive():
        pytest.skip("真实 plate 不可达 —— local-only 回环用例,CI 默认跳过")
    ref = await _latest_fin_ref()
    if not ref:
        pytest.skip("真实 plate fin 线不可读")

    # 脱离 conftest 封闭桩:本用例内 plate_client 走真实服务
    plate_client.set_client_for_tests(None)

    h = await register_and_login(client, "rtadmin", "pw123456")
    draft = make_draft("sc-rt-src", plate={"fin": ref}, steps=[{
        "kind": "step",
        "call": {"kind": "call", "protocol": "http", "service": "svc",
                 "method": "GET", "path": "/rt"},
        "request": {"kind": "request", "body": {"note": "keep"}},
        "strategy": [],
    }])
    r = await client.post("/api/scenarios", headers=h, json=draft)
    assert r.status_code in (200, 201), r.text

    # ① 导出 = 可执行形态(真实 /convert 产物)
    r = await client.get("/api/scenarios/sc-rt-src/export", headers=h)
    assert r.status_code == 200, r.text
    exported = r.json()
    assert exported["scenarioId"] == "sc-rt-src"
    assert (exported.get("meta") or {}).get("plate") == {"fin": ref}

    # ② 预检:同 ID 冲突 + suggestedId;不阻塞
    r = await client.post("/api/scenarios/import/precheck", headers=h,
                          json={"bundle": exported})
    assert r.status_code == 200, r.text
    pre = r.json()
    assert pre["blocking"] is False, pre
    assert pre["idConflict"] is True
    assert pre["suggestedId"]

    # ③ 落库:new 模式回传 newId(P4/R7:展示 = 最终)
    new_id = f"sc-rt-{secrets.token_hex(3)}"
    r = await client.post("/api/scenarios/import", headers=h, json={
        "bundle": exported, "mappings": [],
        "idMode": "new", "newId": new_id})
    assert r.status_code == 201, r.text
    assert r.json()["scenarioId"] == new_id

    # ④ 回环:新场景再导出 —— 步骤形状等价;config.users 不落库(P2);
    #    默认方案已物化(首建态)
    r = await client.get(f"/api/scenarios/{new_id}/export", headers=h)
    assert r.status_code == 200, r.text
    re_exported = r.json()
    assert re_exported["scenarioId"] == new_id
    assert re_exported["steps"][0]["call"]["path"] == "/rt"
    # P2:无凭证落库(真实 convert 会把 config 归一化补 users:{} 空键,
    # 断言口径 = 内容为空,而非键缺席)
    assert not (re_exported.get("config") or {}).get("users")

    async with db_module.SessionLocal() as db:
        schemes = (await db.execute(select(ComposerRunScheme).where(
            ComposerRunScheme.scenario_id == new_id))).scalars().all()
        assert schemes and all(s.is_default for s in schemes) and len(schemes) == 1
