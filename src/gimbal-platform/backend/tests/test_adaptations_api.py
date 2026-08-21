"""adaptations 路由 API 测试:admin 门控(403/401)、diff 502、impact 只读。"""
from __future__ import annotations

from .helpers import register_and_login


async def test_diff_requires_login(client, plate):
    r = await client.post("/api/adaptations/catalog/diff")
    assert r.status_code == 401


async def test_diff_admin_only(client, plate):
    admin = await register_and_login(client, "boss", "bosspass123")   # uid 1 → 自动 admin
    member = await register_and_login(client, "peon", "peonpass123")  # uid 2 → 普通用户
    denied = await client.post("/api/adaptations/catalog/diff", headers=member)
    assert denied.status_code == 403

    plate.items = [{"id": "fin.order.add", "version": "1.0.0",
                    "updated_at": "2026-01-01T00:00:00Z"}]
    plate.fulls = {"fin.order.add": {"id": "fin.order.add", "version": "1.0.0",
                                     "request": {"fields": []}}}
    ok = await client.post("/api/adaptations/catalog/diff", headers=admin)
    assert ok.status_code == 200
    assert ok.json() == {"pending": [], "anomalies": [], "baselinedNow": 1}


async def test_diff_plate_unavailable_502(client, plate):
    admin = await register_and_login(client, "boss", "bosspass123")
    plate.down = True
    r = await client.post("/api/adaptations/catalog/diff", headers=admin)
    assert r.status_code == 502
    assert r.json()["detail"]["code"] == "plate_unavailable"


async def test_impact_readonly_and_admin_only(client, plate):
    await register_and_login(client, "boss", "bosspass123")
    member = await register_and_login(client, "peon", "peonpass123")
    denied = await client.get("/api/adaptations/impact",
                              params={"endpointId": "fin.order.add"},
                              headers=member)
    assert denied.status_code == 403
    admin = await register_and_login(client, "boss", "bosspass123")
    ok = await client.get("/api/adaptations/impact",
                          params={"endpointId": "fin.order.add"}, headers=admin)
    assert ok.status_code == 200
    assert ok.json() == []
