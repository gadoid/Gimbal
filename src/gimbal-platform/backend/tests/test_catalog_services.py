"""M5-1 服务目录聚合端点(/api/catalog/services,债 11)。"""
from __future__ import annotations

from tests.conftest import EndpointPlateMock
from tests.helpers import register_and_login


async def test_catalog_services_aggregates_and_caches(client, plate):
    plate.items = [
        {"id": "fin.order.add", "service": "fin-service", "system": "fin"},
        {"id": "fin.order.get", "service": "fin-service", "system": "fin"},
        {"id": "wms.stock.list", "service": "wms-service", "system": "wms"},
        # 脏行:缺 service/system → 不进聚合
        {"id": "bad.row", "service": "", "system": "fin"},
    ]
    h = await register_and_login(client, "m5cat", "pw123456")

    from app.routers import catalog as catalog_router
    catalog_router.reset_catalog_cache_for_tests()

    r = await client.get("/api/catalog/services", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["plateReachable"] is True
    assert body["services"] == [
        {"name": "fin-service", "system": "fin", "endpointCount": 2},
        {"name": "wms-service", "system": "wms", "endpointCount": 1},
    ]
    got = {e["id"]: e["service"] for e in body["endpoints"]}
    assert got["fin.order.add"] == "fin-service"
    assert got["wms.stock.list"] == "wms-service"
    assert "bad.row" not in got

    # 30s TTL:改 plate 目录后 30s 内仍回缓存值(计数不变)
    plate.items.append(
        {"id": "fin.order.del", "service": "fin-service", "system": "fin"})
    r2 = await client.get("/api/catalog/services", headers=h)
    fin = next(s for s in r2.json()["services"] if s["name"] == "fin-service")
    assert fin["endpointCount"] == 2  # 缓存命中


async def test_catalog_services_plate_down_degrades(client, plate):
    plate.down = True
    h = await register_and_login(client, "m5cat2", "pw123456")

    from app.routers import catalog as catalog_router
    catalog_router.reset_catalog_cache_for_tests()

    r = await client.get("/api/catalog/services", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["plateReachable"] is False
    assert body["services"] == [] and body["endpoints"] == []

    # 不可达的结果**不进 TTL 缓存**——plate 恢复后立刻能拿到真实目录
    plate.down = False
    plate.items = [{"id": "e1", "service": "s1", "system": "sys1"}]
    r2 = await client.get("/api/catalog/services", headers=h)
    assert r2.json()["plateReachable"] is True
    assert len(r2.json()["services"]) == 1


async def test_catalog_services_requires_auth(client):
    r = await client.get("/api/catalog/services")
    assert r.status_code == 401
