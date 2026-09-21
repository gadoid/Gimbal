"""M6-2:user_stars 上线(收藏入库、上限 409、legacy 吸收、级联)。"""
from __future__ import annotations

from tests.helpers import make_draft, register_and_login


async def _mk(client, headers, sid: str):
    r = await client.post("/api/scenarios", headers=headers,
                          json=make_draft(sid))
    assert r.status_code == 201, r.text


async def test_star_roundtrip_and_list_projection(client):
    h = await register_and_login(client, "m6star", "pw123456")
    await _mk(client, h, "sc-st-1")
    await _mk(client, h, "sc-st-2")

    r = await client.post("/api/scenarios/sc-st-1/star", headers=h,
                          json={"starred": True})
    assert r.status_code == 204

    # 列表投影(读时)
    r = await client.get("/api/scenarios", headers=h)
    starred = {i["meta"]["scenarioId"]: i["starred"] for i in r.json()["items"]}
    assert starred == {"sc-st-1": True, "sc-st-2": False}

    # ?starred=true 服务端过滤
    r = await client.get("/api/scenarios?starred=true", headers=h)
    ids = {i["meta"]["scenarioId"] for i in r.json()["items"]}
    assert ids == {"sc-st-1"}

    # 详情投影
    d = await client.get("/api/scenarios/sc-st-1", headers=h)
    assert d.json()["starred"] is True

    # 取消
    await client.post("/api/scenarios/sc-st-1/star", headers=h,
                      json={"starred": False})
    r = await client.get("/api/scenarios?starred=true", headers=h)
    assert r.json()["total"] == 0


async def test_star_cap_20_server_side_409(client):
    h = await register_and_login(client, "m6cap", "pw123456")
    for i in range(21):
        await _mk(client, h, f"sc-cap-{i}")
    for i in range(20):
        r = await client.post(f"/api/scenarios/sc-cap-{i}/star", headers=h,
                              json={"starred": True})
        assert r.status_code == 204
    # 第 21 个:409 + 人话
    r = await client.post("/api/scenarios/sc-cap-20/star", headers=h,
                          json={"starred": True})
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "star_cap_exceeded"
    assert "20" in r.json()["detail"]["message"]
    # 重复收藏已收的不涨计数(幂等)
    r = await client.post("/api/scenarios/sc-cap-0/star", headers=h,
                          json={"starred": True})
    assert r.status_code == 204


async def test_delete_scenario_cascades_stars(client):
    h = await register_and_login(client, "m6del", "pw123456")
    await _mk(client, h, "sc-del-1")
    await client.post("/api/scenarios/sc-del-1/star", headers=h,
                      json={"starred": True})
    r = await client.delete("/api/scenarios/sc-del-1", headers=h)
    assert r.status_code == 204

    from sqlalchemy import select

    from app.core import db as db_module
    from app.models.permission import UserStar

    async with db_module.SessionLocal() as s:
        orphan = (await s.execute(
            select(UserStar).where(UserStar.scenario_id == "sc-del-1")
        )).scalar_one_or_none()
    assert orphan is None


async def test_absorb_legacy_stars_json(client, tmp_path, monkeypatch):
    """一次性吸收:stars.json → UserStar 行,吸收后文件改名,悬空 id 过滤。"""
    import json as _json

    from app.core.config import settings
    from app.core import db as db_module
    from app.services.user_stars import absorb_legacy_stars

    h = await register_and_login(client, "m6abs", "pw123456")  # id=1
    other = await register_and_login(client, "m6abs2", "pw123456")  # id=2
    await _mk(client, h, "sc-abs-1")
    await _mk(client, other, "sc-abs-2")

    (tmp_path / "stars.json").write_text(_json.dumps({
        "1": ["sc-abs-1", "sc-gone"],   # sc-gone 悬空 → 过滤
        "2": ["sc-abs-2"],
        "bogus": ["x"],                  # 坏 uid → 跳过
    }), encoding="utf-8")
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)

    async with db_module.SessionLocal() as s:
        absorbed = await absorb_legacy_stars(s)
    assert absorbed == 2
    assert not (tmp_path / "stars.json").exists()
    assert (tmp_path / "stars.json.absorbed").exists()

    # 吸收结果反映到读侧
    r = await client.get("/api/scenarios?starred=true", headers=h)
    assert {i["meta"]["scenarioId"] for i in r.json()["items"]} == {"sc-abs-1"}

    # 幂等:再跑 no-op
    async with db_module.SessionLocal() as s:
        assert await absorb_legacy_stars(s) == 0
