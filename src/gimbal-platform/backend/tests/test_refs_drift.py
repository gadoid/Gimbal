"""refs_drift 漂移 diff(2026-09-20)— 倒排索引 endpoint 面 vs plate 清单。

三类口径与 carry_drift 同构:悬空(refs 有、plate 无)/ 零引用(plate
有、refs 无)/ plateReachable 信号(不可达时清单不可信,先看信号)。
"""
from __future__ import annotations

from app.core import db as db_module
from app.schemas.scenario_composer import ScenarioDraft
from app.services import scenario_store

from .helpers import make_draft
from .test_carry_api import _admin

EP_REFFED = "fin.order.add"   # 场景引用(有字段行)
EP_ANCHOR = "fin.order.get"   # 场景引用(仅锚点行,零字段步)
EP_PLATE_ONLY = "fin.order.book"  # plate 有、无场景引用


async def _seed():
    async with db_module.SessionLocal() as s:
        from .helpers import ensure_fk_users

        await ensure_fk_users(s, 1, 2, make_admin=1)  # 直插 owner_id=1/2;id=1 造成可登录 admin
        await scenario_store.create(
            s,
            ScenarioDraft.model_validate(make_draft("sc-drift", steps=[
                {"api": {"view_hints": {"endpoint_id": EP_REFFED}, "headers": {}},
                 "request": {"body": {"amount": 1}}},
                {"api": {"view_hints": {"endpoint_id": EP_ANCHOR}, "headers": {}},
                 "request": {"body": {}}},
            ])),
            owner="alice", owner_id=1,
        )


async def test_refs_drift_two_classes(client, plate):
    await _seed()
    plate.items = [
        {"id": EP_REFFED, "version": "1.0.0", "updated_at": None},
        {"id": EP_PLATE_ONLY, "version": "1.0.0", "updated_at": None},
    ]
    from .helpers import FK_ADMIN_PASSWORD, login_user

    admin = await login_user(client, "fkuser1", FK_ADMIN_PASSWORD)
    r = await client.get("/api/adaptations/refs-drift", headers=admin)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["plateReachable"] is True
    # EP_ANCHOR:refs 有、plate 清单无 → 悬空(锚点行口径也计入 refs 面)
    assert body["dangling"] == [EP_ANCHOR]
    # EP_PLATE_ONLY:plate 有、refs 无 → 全网零引用(网格「无覆盖」口径)
    assert body["zeroRef"] == [EP_PLATE_ONLY]


async def test_refs_drift_aligned(client, plate):
    await _seed()
    plate.items = [
        {"id": EP_REFFED, "version": "1.0.0", "updated_at": None},
        {"id": EP_ANCHOR, "version": "1.0.0", "updated_at": None},
    ]
    from .helpers import FK_ADMIN_PASSWORD, login_user

    admin = await login_user(client, "fkuser1", FK_ADMIN_PASSWORD)
    r = await client.get("/api/adaptations/refs-drift", headers=admin)
    body = r.json()
    assert body == {"dangling": [], "zeroRef": [], "plateReachable": True}


async def test_refs_drift_plate_down_flags_and_degrades(client, plate):
    """plate 清单不可达 → plateReachable=False + 面视为空(refs 全成
    dangling)— 面板先看信号再渲染,防把不可达误读成漂移(carry_drift 纪律)。"""
    await _seed()
    plate.down = True
    from .helpers import FK_ADMIN_PASSWORD, login_user

    admin = await login_user(client, "fkuser1", FK_ADMIN_PASSWORD)
    r = await client.get("/api/adaptations/refs-drift", headers=admin)
    body = r.json()
    assert body["plateReachable"] is False
    assert sorted(body["dangling"]) == sorted([EP_REFFED, EP_ANCHOR])
    assert body["zeroRef"] == []
