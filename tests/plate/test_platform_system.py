"""platform 作为被测系统接入 plate 的注册正确性。"""

import pytest

from gimbal_plate.http.app import create_app
from gimbal_plate.registry import PlateRegistry
from gimbal_plate.systems.platform.endpoints import ALL_PLATFORM_ENDPOINTS
from gimbal_plate.systems.platform.system_info import PLATFORM_SYSTEM


@pytest.fixture
def reg() -> PlateRegistry:
    r = PlateRegistry()
    r.register_endpoints(ALL_PLATFORM_ENDPOINTS)
    return r


def test_endpoints_non_empty(reg):
    assert len(ALL_PLATFORM_ENDPOINTS) >= 100


def test_every_endpoint_belongs_to_platform_system(reg):
    wrong = [e.id for e in ALL_PLATFORM_ENDPOINTS if e.system != PLATFORM_SYSTEM]
    assert not wrong, f"system 不一致: {wrong[:5]}"


def test_ids_unique_and_match_plate_charset(reg):
    import re

    ids = [e.id for e in ALL_PLATFORM_ENDPOINTS]
    assert len(ids) == len(set(ids)), "endpoint id 重复"
    bad = [i for i in ids if not re.match(r"^[a-z][a-z0-9_.\-]{1,63}$", i)]
    assert not bad, f"id 不合规: {bad[:5]}"


def test_every_endpoint_declares_200(reg):
    missing = [e.id for e in ALL_PLATFORM_ENDPOINTS if 200 not in e.responses]
    assert not missing, f"缺 responses[200]: {missing[:5]}"


def test_no_route_collisions(reg):
    seen: dict[tuple, str] = {}
    for e in ALL_PLATFORM_ENDPOINTS:
        key = (e.api.service, e.api.method, e.api.path)
        assert key not in seen, f"by_route 碰撞 {key}: {seen[key]} vs {e.id}"
        seen[key] = e.id


def test_service_is_isolated_from_fin(reg):
    services = {e.service for e in ALL_PLATFORM_ENDPOINTS}
    assert "fin-service" not in services


def test_health_endpoint_is_no_auth(reg):
    by_path = {e.api.path: e for e in ALL_PLATFORM_ENDPOINTS}
    assert by_path["/api/health"].api.auth == "none"
    assert by_path["/api/auth/login"].api.auth == "none"
    assert by_path["/api/scenarios"].api.auth == "bearer"


def test_app_lifespan_registers_platform_system():
    """owned 模式下 lifespan 自检必须放行 platform（此前硬编码只认 fin）。"""
    from fastapi.testclient import TestClient

    app = create_app()
    with TestClient(app) as client:
        systems = client.get("/api/system").json()
    ids = [s["id"] for s in systems["data"]["items"]]
    assert ids.count(PLATFORM_SYSTEM) == 1, f"platform 应恰好出现一次，实际 {ids}"
    assert "fin" in ids
