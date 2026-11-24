"""plate_client.convert 信封契约断言(J-1 单点收口,2026-11-24)。

200+ok 但 ``data`` / ``data.converted`` 缺失或非对象 →
:class:`plate_client.PlateInvalidResponseError`(PlateUnavailableError
子类 = plate 侧故障,502 族,endpoint_catalog 的 plate_invalid_envelope
先例之姊妹)。此前 `data.get("converted") or {}` 全链静默空,半畸形
回包以「空场景」流向物化/引擎才炸。三形态 + 合法对照 + 分类兼容钉。
"""
from __future__ import annotations

import httpx
import pytest

from app.services import plate_client


def _install(payload: dict | None) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    plate_client.set_client_for_tests(httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://plate-test"))


def teardown_function() -> None:
    plate_client.set_client_for_tests(None)


async def _convert() -> dict:
    return await plate_client.convert({"config": {"vars": {}}, "steps": []})


@pytest.mark.parametrize("payload", [
    {"ok": True, "dim": "scenario", "data": {"consumer": "gimbal"}},   # 缺 converted
    {"ok": True, "dim": "scenario"},                                   # 缺 data
    {"ok": True, "data": {"converted": [1, 2]}},                       # converted 非对象
    {"ok": True, "data": {"converted": "nope"}},                       # converted 非对象(串)
])
async def test_bad_envelopes_raise_invalid_response(payload: dict) -> None:
    _install(payload)
    with pytest.raises(plate_client.PlateInvalidResponseError,
                       match="plate_invalid_response"):
        await _convert()


async def test_valid_envelope_passes_through() -> None:
    """合法回包行为零变化:data 原样返回(converted 之外的 m2 等键保留)。"""
    _install({"ok": True, "dim": "scenario",
              "data": {"consumer": "gimbal", "converted": {"kind": "x"},
                       "m2": {"hash": "h"}}})
    data = await _convert()
    assert data["converted"] == {"kind": "x"}
    assert data["m2"] == {"hash": "h"}


def test_invalid_response_subclasses_unavailable() -> None:
    """分类兼容钉:子类化 PlateUnavailableError —— dispatcher 行 /
    integration channel / adhoc / import 等既有 `except
    PlateUnavailableError`(或兜底)位零改动继承「plate 侧故障」归类。"""
    assert issubclass(plate_client.PlateInvalidResponseError,
                      plate_client.PlateUnavailableError)
