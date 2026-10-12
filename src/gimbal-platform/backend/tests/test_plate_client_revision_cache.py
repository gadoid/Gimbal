"""W24(B-7):plate_client 按修订读取的不可变结果缓存。

机制对齐 plate 侧修订快照缓存(b4a8bfc0):条目不设 TTL、只按容量
FIFO/LRU 淘汰 —— 修订一经签发内容不变,淘汰只是丢缓存。钉住:
1. 命中:同 (endpoint/system, ref) 二次取数不打 HTTP;
2. 隔离:不同 ref 不串;404(None)不进缓存;
3. 防污染:命中返回深拷贝,调用方改返回值不动缓存;
4. 容量:超上限淘汰,不无限增长;
5. declarations_of_at 经 get_endpoint_full_at 自动吃到缓存。
"""
from __future__ import annotations

import httpx
import pytest

from app.services import plate_client
from app.services.endpoint_declarations import declarations_of_at


@pytest.fixture(autouse=True)
def _clean_cache():
    plate_client._reset_revision_cache_for_test()
    yield
    plate_client._reset_revision_cache_for_test()


def _install_transport(handler) -> int:
    """MockTransport 装进 plate client;返回命中计数器。"""
    calls = {"n": 0}

    async def _handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return await handler(request)

    plate_client.set_client_for_tests(
        httpx.AsyncClient(transport=httpx.MockTransport(_handler),
                          base_url="http://plate-test"))
    return calls


async def test_full_at_cached_no_second_http():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["ref"] == "1.0#1"
        return httpx.Response(200, json={
            "ok": True, "data": {"item": {"id": "fin.a", "request": {
                "declarations": [{"path": "$.body.x"}]}}}})

    calls = _install_transport(handler)
    a = await plate_client.get_endpoint_full_at("fin.a", "1.0#1")
    b = await plate_client.get_endpoint_full_at("fin.a", "1.0#1")
    assert calls["n"] == 1
    assert a == b and a is not b          # 深拷贝:两次返回不是同一对象


async def test_cache_hit_returns_deep_copy_mutations_do_not_leak():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "ok": True, "data": {"item": {"id": "fin.a", "nested": {
                "k": [1, 2]}}}})

    _install_transport(handler)
    a = await plate_client.get_endpoint_full_at("fin.a", "1.0#1")
    a["nested"]["k"].append(3)
    a["id"] = "mutated"
    b = await plate_client.get_endpoint_full_at("fin.a", "1.0#1")
    assert b["id"] == "fin.a" and b["nested"]["k"] == [1, 2]


async def test_different_ref_and_404_not_cached():
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params["ref"] == "1.0#2":
            return httpx.Response(404, json={"ok": False})
        return httpx.Response(200, json={
            "ok": True, "data": {"item": {"id": "fin.a"}}})

    calls = _install_transport(handler)
    miss = await plate_client.get_endpoint_full_at("fin.a", "1.0#2")
    miss2 = await plate_client.get_endpoint_full_at("fin.a", "1.0#2")
    assert miss is None and miss2 is None
    assert calls["n"] == 2                # 404 不进缓存:两次都打了 HTTP
    hit = await plate_client.get_endpoint_full_at("fin.a", "1.0#1")
    hit2 = await plate_client.get_endpoint_full_at("fin.a", "1.0#1")
    assert hit == hit2 == {"id": "fin.a"}
    assert calls["n"] == 3                # #2 两次(404 不缓存)+ #1 一次


async def test_projection_and_revision_objects_cached():
    async def handler(request: httpx.Request) -> httpx.Response:
        if "/projection" in request.url.path:
            return httpx.Response(200, json={
                "ok": True, "data": {"item": {"method": "GET"}}})
        return httpx.Response(200, json={
            "ok": True, "data": {"item": {"objects": [
                {"id": "fin.a", "review": "reviewed"},
                {"id": "fin.b", "review": "draft"}]}}})

    calls = _install_transport(handler)
    p1 = await plate_client.get_projection("fin.a", "1.0#1")
    p2 = await plate_client.get_projection("fin.a", "1.0#1")
    assert p1 == p2 == {"method": "GET"}
    o1 = await plate_client.revision_objects("fin", "1.0#1")
    o2 = await plate_client.revision_objects("fin", "1.0#1")
    assert o1 == o2 == {"fin.a": "reviewed", "fin.b": "draft"}
    assert calls["n"] == 2                # 每类各一次


async def test_capacity_eviction_fifo():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "ok": True, "data": {"item": {"id": "x"}}})

    calls = _install_transport(handler)
    for i in range(plate_client._REVISION_CACHE_MAX + 8):
        await plate_client.get_endpoint_full_at(f"ep-{i}", "1.0#1")
    assert len(plate_client._revision_cache) == plate_client._REVISION_CACHE_MAX
    # 最早的 ep-0 已被淘汰 → 再取会重新打 HTTP(计数 = 首轮 + 1)
    before = calls["n"]
    await plate_client.get_endpoint_full_at("ep-0", "1.0#1")
    assert calls["n"] == before + 1
    # 最近访问的仍在缓存 → 不打 HTTP
    before = calls["n"]
    await plate_client.get_endpoint_full_at(
        f"ep-{plate_client._REVISION_CACHE_MAX + 7}", "1.0#1")
    assert calls["n"] == before


async def test_declarations_of_at_rides_the_cache():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "ok": True, "data": {"item": {"request": {
                "declarations": [{"path": "$.body.qty"}]}}}})

    calls = _install_transport(handler)
    d1 = await declarations_of_at("fin.a", "1.0#1")
    d2 = await declarations_of_at("fin.a", "1.0#1")
    assert d1 == d2 == [{"path": "$.body.qty"}]
    assert calls["n"] == 1                # declarations_of_at 经缓存零重复取数
