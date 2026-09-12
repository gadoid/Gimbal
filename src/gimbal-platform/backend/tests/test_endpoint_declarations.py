"""声明面取数(spec v3.1 §3):契约 request.declarations 的 path 全集,
进程缓存 + TTL + fail-soft。"""
from __future__ import annotations

import asyncio

import httpx
import pytest

from app.core.config import settings
from app.services import plate_client
from app.services.carry_injection import _endpoint_declarations
from app.services.endpoint_declarations import (
    _reset_declared_paths_cache, declared_paths_of,
)


@pytest.fixture(autouse=True)
def _install_transport(monkeypatch):
    """plate 单例换成可编程 MockTransport;每例前清缓存。"""
    calls: list[str] = []
    payload = {
        "ok": True, "dim": "endpoint",
        "data": {"item": {"request": {"declarations": [
            {"name": "bl_no", "path": "$.bl_no", "state": "form", "required": True},
            {"name": "cid", "path": "$.customer_id", "state": "carry", "required": True},
            {"name": "items", "path": "$.items", "state": "form", "required": False,
             "children": [{"name": "sku", "path": "$.items.sku", "state": "form", "required": True}]},
        ]}}},
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, json=payload)

    plate_client.set_client_for_tests(
        httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://plate-test")
    )
    _reset_declared_paths_cache()
    monkeypatch.setattr(settings, "DECLARED_PATHS_TTL_SEC", 300.0)
    yield calls
    plate_client.set_client_for_tests(None)


async def test_declared_paths_of_returns_flat_path_set(_install_transport):
    paths = await declared_paths_of("fin.order.add")
    assert paths is not None
    assert {"$.bl_no", "$.customer_id", "$.items", "$.items.sku"} <= set(paths)
    assert len(_install_transport) == 1


async def test_second_call_hits_cache(_install_transport):
    await declared_paths_of("fin.order.add")
    await declared_paths_of("fin.order.add")
    assert len(_install_transport) == 1          # 缓存命中,只拉一次


async def test_ttl_zero_refetches(monkeypatch, _install_transport):
    await declared_paths_of("fin.order.add")
    monkeypatch.setattr(settings, "DECLARED_PATHS_TTL_SEC", 0.0)
    await declared_paths_of("fin.order.add")
    assert len(_install_transport) == 2


async def test_concurrent_cold_calls_coalesce_to_one_fetch(_install_transport):
    """在飞收敛:冷缓存并发同端点 → 只打一次 plate,两者同一结果。"""
    a, b = await asyncio.gather(
        declared_paths_of("fin.order.add"),
        declared_paths_of("fin.order.add"),
    )
    assert len(_install_transport) == 1          # 收敛为同一在飞请求
    # == 而非 is:缓存的是原始声明列表,path 集每次调用派生(见模块设计),
    # 但两者必等值 —— 收敛要保的是「同一次取数」,不是同一个对象。
    assert a is not None and a == b
    assert {"$.bl_no", "$.customer_id", "$.items", "$.items.sku"} <= set(a)


async def test_carry_delegate_and_paths_share_one_fetch(_install_transport):
    """跨消费者共用取数:carry 侧门面与 declared_paths_of 只打一次 plate。"""
    decls = await _endpoint_declarations("fin.order.add")
    assert isinstance(decls, list) and len(decls) == 3   # carry 侧拿到原始列表
    paths = await declared_paths_of("fin.order.add")
    assert len(_install_transport) == 1                  # 合并生效:只打一次
    assert paths == frozenset(
        {"$.bl_no", "$.customer_id", "$.items", "$.items.sku"}
    )


async def test_failure_returns_none_and_does_not_cache(monkeypatch):
    state = {"fail": True, "calls": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        state["calls"] += 1
        if state["fail"]:
            return httpx.Response(503, json={"ok": False})
        return httpx.Response(200, json={
            "ok": True, "dim": "endpoint",
            "data": {"item": {"request": {"declarations": [
                {"name": "a", "path": "$.a", "state": "form", "required": True}]}}},
        })

    plate_client.set_client_for_tests(
        httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://plate-test")
    )
    _reset_declared_paths_cache()
    assert await declared_paths_of("ep-x") is None      # 失败 → 降级信号
    state["fail"] = False
    assert await declared_paths_of("ep-x") == frozenset({"$.a"})   # 失败不入缓存 → 可重试
    assert state["calls"] == 2
    plate_client.set_client_for_tests(None)
