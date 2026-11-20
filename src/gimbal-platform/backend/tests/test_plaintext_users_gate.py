"""凭证治理 §3.5:保存闸 plaintext_users_rejected(阶段 2;拍板 2026-11-20)。

钉子:
* 直写 API(POST/PUT)带非空 config.users → 422,提示指引改引用/走认证
  管理落池;
* 存量判定 = 行的既有形态:旧行 users 非空(§7 遗留明文基座)→ PUT
  放行不改存量;旧行空而本次带 → 422;
* 副本拍板 #5:同属主「另存为」同样清空(副本 = 新建)—— 断言在
  ``test_public_content_strips_credentials``(翻转用例),本文件钉
  副本过闸不误伤;
* 导入链上游清空,恒过闸(既有 import 测试覆盖,不重测)。
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.helpers import make_draft, role_headers

_STEP = {
    "kind": "step",
    "call": {"protocol": "http", "service": "svc",
             "method": "GET", "path": "/x", "headers": {}},
    "request": {"kind": "request", "body": {}}, "strategy": [],
}
_USERS = {"gitlab": {"username": "u", "password": "p", "token": "t"}}


def _draft(sid: str, *, users: dict | None = None) -> dict:
    draft = make_draft(sid, steps=[_STEP])
    if users is not None:
        draft["definition"]["config"]["users"] = users
    return draft


@pytest.mark.asyncio
async def test_create_with_users_rejected(client: AsyncClient):
    """直写 API 新建带明文 users → 422 plaintext_users_rejected。"""
    h = await role_headers(client, "pu_c")
    r = await client.post("/api/scenarios", headers=h, json=_draft(
        "sc-pu-1", users=dict(_USERS)))
    assert r.status_code == 422, r.text
    assert r.json()["detail"].startswith("plaintext_users_rejected")
    assert "身份条目名" in r.json()["detail"]


@pytest.mark.asyncio
async def test_update_with_users_rejected_on_new_form(
        client: AsyncClient):
    """新形态场景(创建期即干净)PUT 带明文 → 422;不带则 200。"""
    h = await role_headers(client, "pu_u")
    r = await client.post("/api/scenarios", headers=h, json=_draft("sc-pu-2"))
    assert r.status_code in (200, 201), r.text
    r = await client.put("/api/scenarios/sc-pu-2", headers=h, json=_draft(
        "sc-pu-2", users=dict(_USERS)))
    assert r.status_code == 422, r.text
    assert r.json()["detail"].startswith("plaintext_users_rejected")
    r = await client.put("/api/scenarios/sc-pu-2", headers=h,
                         json=_draft("sc-pu-2"))
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_update_legacy_row_users_allowed(client: AsyncClient):
    """存量判定:旧行 users 非空(遗留明文基座)→ PUT 放行(§7 只对
    新建生效,不锁存量编辑);显式清空也可(向新形态迁移)。"""
    from sqlalchemy import select as sa_select

    from app.core import db as db_module
    from app.models.composer_scenario import ComposerScenario
    h = await role_headers(client, "pu_l")
    r = await client.post("/api/scenarios", headers=h, json=_draft("sc-pu-3"))
    assert r.status_code in (200, 201), r.text
    async with db_module.SessionLocal() as s:
        row = (await s.execute(sa_select(ComposerScenario).where(
            ComposerScenario.scenario_id == "sc-pu-3"))).scalar_one()
        payload = dict(row.payload or {})
        defn = dict(payload.get("definition") or {})
        cfg = dict(defn.get("config") or {})
        cfg["users"] = dict(_USERS)
        defn["config"] = cfg
        payload["definition"] = defn
        row.payload = payload
        await s.commit()
    # 旧行带明文 → PUT 保持/修改都放行(存量照旧)
    r = await client.put("/api/scenarios/sc-pu-3", headers=h, json=_draft(
        "sc-pu-3", users=dict(_USERS)))
    assert r.status_code == 200, r.text
    # 显式清空 → 200(迁移到新形态)
    r = await client.put("/api/scenarios/sc-pu-3", headers=h,
                         json=_draft("sc-pu-3"))
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_same_owner_copy_passes_gate_clean(client: AsyncClient):
    """拍板 #5:同属主「另存为」副本 = 新建且上游清空 → 恒过闸,
    副本 users 为空(存量原件不动)。"""
    from sqlalchemy import select as sa_select

    from app.core import db as db_module
    from app.models.composer_scenario import ComposerScenario
    h = await role_headers(client, "pu_s")
    r = await client.post("/api/scenarios", headers=h, json=_draft("sc-pu-4"))
    assert r.status_code in (200, 201), r.text
    # 铺一个带明文的存量原件(模拟遗留行),再另存为
    async with db_module.SessionLocal() as s:
        row = (await s.execute(sa_select(ComposerScenario).where(
            ComposerScenario.scenario_id == "sc-pu-4"))).scalar_one()
        payload = dict(row.payload or {})
        defn = dict(payload.get("definition") or {})
        cfg = dict(defn.get("config") or {})
        cfg["users"] = dict(_USERS)
        defn["config"] = cfg
        payload["definition"] = defn
        row.payload = payload
        await s.commit()
    r = await client.post("/api/scenarios/sc-pu-4/copy", headers=h,
                          json={"name": "另存副本"})
    assert r.status_code == 201, r.text
    new_sid = r.json()["meta"]["scenarioId"]
    async with db_module.SessionLocal() as s:
        copy_row = (await s.execute(sa_select(ComposerScenario).where(
            ComposerScenario.scenario_id == new_sid))).scalar_one()
        cfg = ((copy_row.payload or {}).get("definition") or {}
               ).get("config") or {}
        assert not cfg.get("users")
        # 原件不动(存量明文基座仍在属主手里,§7)
        src_cfg = None
        src = (await s.execute(sa_select(ComposerScenario).where(
            ComposerScenario.scenario_id == "sc-pu-4"))).scalar_one()
        src_cfg = ((src.payload or {}).get("definition") or {}
                   ).get("config") or {}
        assert src_cfg.get("users") == _USERS
