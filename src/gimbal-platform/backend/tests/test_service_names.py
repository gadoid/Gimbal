"""derive_base 后端移植(spec §4.2)—— 前端 service-alias.ts 的同逻辑。"""
from __future__ import annotations

import httpx

from app.services import service_names
from app.services import plate_client


def test_direct_catalog_hit():
    names = {"fin-service", "fin-order-service"}
    assert service_names.derive_base("fin-service", names) == "fin-service"


def test_alias_suffix_stripped_at_last_dash():
    names = {"fin-service"}
    # 最后一个 "-" 切分:目录名自身可含 "-",base 永远是最长候选
    assert service_names.derive_base("fin-service-qa1", names) == "fin-service"
    # 后缀含 "-" = 非构造性别名键 → 裸声明 None,不猜
    # (brief 原断言写 == "fin-service",与前端 service-alias.test.ts
    #  「fin-order-service-x-1 → null(D5 固定切分)」相反 — 以前端为准修正)
    assert service_names.derive_base("fin-service-x-y", names) is None


def test_bare_declaration_returns_null_no_guess():
    assert service_names.derive_base("unknown-svc", {"fin-service"}) is None
    assert service_names.derive_base("", {"fin-service"}) is None


async def test_catalog_service_names_fetches_plate():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/service"
        return httpx.Response(200, json={
            "ok": True, "dim": "service",
            "data": {"items": [{"name": "fin-service"},
                               {"name": "track-trace-service"}],
                     "total": 2},
        })

    plate_client.set_client_for_tests(httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://plate-test"))
    try:
        names = await service_names.catalog_service_names()
    finally:
        plate_client.set_client_for_tests(None)
    assert names == {"fin-service", "track-trace-service"}


async def test_catalog_unavailable_degrades_to_empty():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    plate_client.set_client_for_tests(httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://plate-test"))
    try:
        assert await service_names.catalog_service_names() == set()
    finally:
        plate_client.set_client_for_tests(None)


async def test_catalog_non_200_degrades_to_empty():
    """非 200(如 503 过载)→ 空集,不上抛。"""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="overloaded")

    plate_client.set_client_for_tests(httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://plate-test"))
    try:
        assert await service_names.catalog_service_names() == set()
    finally:
        plate_client.set_client_for_tests(None)


async def test_catalog_malformed_200_envelope_degrades_to_empty():
    """垃圾 200 体:json() 抛 ValueError / 信封非 dict → AttributeError —
    统一降级空集(T9 控制器裁定:垃圾 200 不得打断 carry 预解析)。"""
    malformed = (
        httpx.Response(200, text="<html>not-json</html>"),   # ValueError
        httpx.Response(200, json=[1, 2]),                    # AttributeError
    )
    for resp in malformed:
        def handler(request: httpx.Request, _r=resp) -> httpx.Response:
            return _r

        plate_client.set_client_for_tests(httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="http://plate-test"))
        try:
            assert await service_names.catalog_service_names() == set()
        finally:
            plate_client.set_client_for_tests(None)
