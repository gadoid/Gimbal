"""platform 作为被测系统接入 plate 的注册正确性。"""

from gimbal_plate.dialect import EndpointSpec
from tests.plate.conftest import SYSTEMS_ROOT
from gimbal_plate.loader import load_registry

_REG = load_registry([SYSTEMS_ROOT])
ALL_ENDPOINTS = [e for e in _REG.list_endpoints() if isinstance(e, EndpointSpec)]
ALL_FIN = [e for e in ALL_ENDPOINTS if e.system == 'fin']

import pytest

from gimbal_plate.http.app import create_app
from gimbal_plate.registry import PlateRegistry
PLATFORM_SYSTEM = 'platform'
ALL_PLATFORM = [e for e in ALL_ENDPOINTS if e.system == 'platform']


@pytest.fixture
def reg() -> PlateRegistry:
    r = PlateRegistry()
    _ = r  # A2:platform 系统由统一加载器从 systems/platform/ 装载
    return r


def test_endpoints_non_empty(reg):
    assert len(ALL_PLATFORM) >= 100


def test_every_endpoint_belongs_to_platform_system(reg):
    wrong = [e.id for e in ALL_PLATFORM if e.system != PLATFORM_SYSTEM]
    assert not wrong, f"system 不一致: {wrong[:5]}"


def test_ids_unique_and_match_plate_charset(reg):
    import re

    ids = [e.id for e in ALL_PLATFORM]
    assert len(ids) == len(set(ids)), "endpoint id 重复"
    bad = [i for i in ids if not re.match(r"^[a-z][a-z0-9_.\-]{1,63}$", i)]
    assert not bad, f"id 不合规: {bad[:5]}"


def test_every_endpoint_declares_200(reg):
    missing = [e.id for e in ALL_PLATFORM if "200" not in e.responses]
    assert not missing, f"缺 responses[200]: {missing[:5]}"


def test_no_route_collisions(reg):
    seen: dict[tuple, str] = {}
    for e in ALL_PLATFORM:
        key = (e.service, e.binding.method, e.binding.path)
        assert key not in seen, f"by_route 碰撞 {key}: {seen[key]} vs {e.id}"
        seen[key] = e.id


def test_service_is_isolated_from_fin(reg):
    services = {e.service for e in ALL_PLATFORM}
    assert "fin-service" not in services


def test_health_endpoint_is_no_auth(reg):
    by_path = {e.binding.path: e for e in ALL_PLATFORM}
    assert by_path["/api/health"].binding.auth == "none"
    assert by_path["/api/auth/login"].binding.auth == "none"
    assert by_path["/api/scenarios"].binding.auth == "bearer"


def test_app_lifespan_registers_platform_system():
    """owned 模式下 lifespan 自检必须放行 platform（此前硬编码只认 fin）。"""
    from fastapi.testclient import TestClient

    app = create_app()
    with TestClient(app) as client:
        systems = client.get("/api/system").json()
    ids = [s["id"] for s in systems["data"]["items"]]
    assert ids.count(PLATFORM_SYSTEM) == 1, f"platform 应恰好出现一次，实际 {ids}"
    assert "fin" in ids
