"""契约漂移检测：plate 里登记的 platform 端点必须都是平台真有的路由。

**单向**（declared ⊆ actual）：平台多出来的端点不算漂移 —— 契约是地板不是天花板；
但契约里登记了、平台却没了的端点算漂移，因为用例编排会拿着这个 path 去打真实 HTTP。

两层：
1. 静态层 —— 拿平台自己的 /openapi.json 对账。无副作用、无需登录，CI 可直接跑。
2. 实测层 —— 用提权后的自举账号真打几个 GET，确认不只是 schema 上有、而是真能通。
   没有 GIMBAL_SB_USERNAME 就跳过。
"""

from __future__ import annotations

import os

import pytest

from gimbal_bootstrap.contract_gen import fetch_openapi
from gimbal_plate.systems.platform.endpoints import ALL_PLATFORM_ENDPOINTS

# 实测层挑的端点：全是 GET，admin 才能过，不产生任何写。
LIVE_PROBES = [
    ("GET", "/api/health"),
    ("GET", "/api/users/roster"),
    ("GET", "/api/scenarios"),
    ("GET", "/api/constants"),
]


def _declared_routes() -> set[tuple[str, str]]:
    out = set()
    for ep in ALL_PLATFORM_ENDPOINTS:
        out.add((ep.api.method.upper(), ep.api.path))
    return out


def _openapi_routes(openapi: dict) -> set[tuple[str, str]]:
    out = set()
    for path, item in (openapi.get("paths") or {}).items():
        for method in item:
            if method.upper() in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}:
                out.add((method.upper(), path))
    return out


@pytest.fixture(scope="module")
def openapi() -> dict:
    return fetch_openapi()


def test_every_declared_route_exists_on_the_platform(openapi):
    """契约登记的每条路由，平台都得有 —— 否则用例编排打过去就是 404。"""
    missing = _declared_routes() - _openapi_routes(openapi)
    assert not missing, "契约里登记但平台没有的路由：\n" + "\n".join(
        f"  {m} {p}" for m, p in sorted(missing)
    )


def test_declared_route_count_is_sane(openapi):
    """防呆：契约被清空或生成器退化成空产物时，这门会响。"""
    declared, actual = _declared_routes(), _openapi_routes(openapi)
    assert len(declared) > 100, f"契约只剩 {len(declared)} 条端点，生成器多半坏了"
    assert declared <= actual


def test_no_declared_endpoint_reuses_a_route(openapi):
    """plate 的 by_route 是后写覆盖先写 —— 两条端点撞同一 (service,method,path)
    会静默吃掉一条。登记时就该炸。"""
    from gimbal_bootstrap.contract_gen import check_collisions

    specs = [
        {
            "id": ep.id,
            "service": ep.api.service,
            "api": {"method": ep.api.method, "path": ep.api.path},
        }
        for ep in ALL_PLATFORM_ENDPOINTS
    ]
    check_collisions(specs)  # 不抛即通过


@pytest.mark.skipif(
    not os.environ.get("GIMBAL_SB_USERNAME"),
    reason="没设 GIMBAL_SB_USERNAME，跳过实测层（需要一个提权到 admin 的自举账号）",
)
def test_declared_get_routes_answer_over_real_http():
    from gimbal_bootstrap.platform_client import Platform, PlatformError

    client = Platform("http://127.0.0.1:8000", os.environ["GIMBAL_SB_TOKEN"])
    dead = []
    for method, path in LIVE_PROBES:
        try:
            client.request(method, path)
        except PlatformError as exc:
            if exc.status == 404:
                dead.append(f"{method} {path} -> 404")
    assert not dead, "平台真打不通的已登记端点：\n" + "\n".join(dead)
