"""导入重锚定(2026-10-15 #323):可执行形态无锚点步骤的锚点回填。

#323 根因:导出产物(引擎形态,endpoint 被 reproject 剥离)原样落库 →
步骤无锚点 → dispatch carry 降级门控注入服务绑定全表 → orderPage 被灌
customer_id/status/supplier → fin ES terms 400 → extract None 硬失败。
本组锁死反查口径:匹配/别名消歧/歧义不猜/钉定修订复核/清单被拒降级/
输入不可变;管线级落库断言(锚点落库 + binding 派生字段被存储闸剥离)
在 test_scenario_import_pipeline 的重锚定用例。
"""
from __future__ import annotations

import copy

import pytest

from app.services.endpoint_anchoring import (
    is_anchored, reanchor_import_definition)

from .test_scenario_composer_plate_integration import PlateMock, plate_mock  # noqa: F401


@pytest.fixture
def pm(plate_mock: PlateMock) -> PlateMock:
    """短名别名 —— 本文件用例全部依赖可编程 PlateMock 桩。"""
    return plate_mock


def _defn(steps: list[dict], plate: dict | None = None) -> dict:
    return {
        "scenarioId": "sc-anchor-1",
        "meta": {"scenarioId": "sc-anchor-1", "name": "A",
                 "plate": plate if plate is not None else {"fin": "working"}},
        "steps": steps,
    }


def _raw_step(service: str = "fin-service", method: str = "POST",
              path: str = "/api/order/orderEntrust/orderPage") -> dict:
    """可执行形态步骤(endpoint 被 reproject 剥离,call 带派生字段)。"""
    return {
        "kind": "step",
        "call": {"kind": "call", "protocol": "http", "service": service,
                 "method": method, "path": path, "timeout": 30,
                 "headers": {"Authorization": "${auth.a.token}"}},
        "request": {"kind": "request", "body": {"page_no": 1}},
        "strategy": [],
    }


def _fin_endpoints(*items: dict) -> list[dict]:
    default_path = "/api/order/orderEntrust/orderPage"
    return [{"id": it["id"], "service": it.get("service", "fin-service"),
             "method": it.get("method", "POST"),
             "path": it.get("path", default_path)}
            for it in items]


async def test_matched_working_ref_anchors(pm: PlateMock):
    pm.system_endpoints["fin"] = _fin_endpoints(
        {"id": "fin.order_entrust.order_page",
         "path": "/api/order/orderEntrust/orderPage"})
    src = _defn([_raw_step()])
    before = copy.deepcopy(src)
    out, report = await reanchor_import_definition(src)
    assert out["steps"][0]["endpoint"] == "fin.order_entrust.order_page"
    assert src == before                      # 输入不可变
    assert report == [{"index": 0, "service": "fin-service",
                       "method": "POST",
                       "path": "/api/order/orderEntrust/orderPage",
                       "endpoint": "fin.order_entrust.order_page",
                       "reason": None}]
    assert is_anchored(report[0]) is True


async def test_method_match_case_insensitive(pm: PlateMock):
    pm.system_endpoints["fin"] = _fin_endpoints(
        {"id": "fin.ep", "method": "post",
         "path": "/api/order/orderEntrust/orderPage"})
    out, report = await reanchor_import_definition(
        _defn([_raw_step(method="POST")]))
    assert out["steps"][0]["endpoint"] == "fin.ep"
    assert report[0]["endpoint"] == "fin.ep"


async def test_alias_service_matches_base(pm: PlateMock):
    """call.service 是别名式引用 → derive_base 归一后与目录服务相等即匹配。"""
    pm.services = [{"name": "fin-service"}]
    pm.system_endpoints["fin"] = _fin_endpoints({"id": "fin.ep"})
    out, report = await reanchor_import_definition(
        _defn([_raw_step(service="fin-service-qa")]))
    assert out["steps"][0]["endpoint"] == "fin.ep"
    assert report[0]["reason"] is None


async def test_unrelated_service_not_anchored(pm: PlateMock):
    """服务既非直等也非别名归一 → 不锚(错锚比不锚更糟)。"""
    pm.services = [{"name": "fin-service"}]
    pm.system_endpoints["fin"] = _fin_endpoints({"id": "fin.ep"})
    out, report = await reanchor_import_definition(
        _defn([_raw_step(service="other-service")]))
    assert "endpoint" not in out["steps"][0]
    assert report[0]["endpoint"] is None
    assert report[0]["reason"] == "not_in_catalog"


async def test_ambiguous_match_not_anchored(pm: PlateMock):
    pm.system_endpoints["fin"] = _fin_endpoints(
        {"id": "fin.ep1"}, {"id": "fin.ep2"})
    out, report = await reanchor_import_definition(_defn([_raw_step()]))
    assert "endpoint" not in out["steps"][0]
    assert report[0]["reason"] == "ambiguous"


async def test_pinned_ref_binding_match_anchors(pm: PlateMock):
    pm.system_endpoints["fin"] = _fin_endpoints({"id": "fin.ep"})
    pm.fulls["fin.ep"] = {
        "binding": {"protocol": "http", "method": "POST",
                    "path": "/api/order/orderEntrust/orderPage"},
        "request": {"declarations": []},
    }
    out, report = await reanchor_import_definition(
        _defn([_raw_step()], plate={"fin": "1.0#1"}))
    assert out["steps"][0]["endpoint"] == "fin.ep"
    assert report[0]["reason"] is None


async def test_pinned_ref_drift_not_anchored(pm: PlateMock):
    """working 命中但钉定修订里 path 已漂移 → 不锚(reproject 会按修订
    投影,锚了执行形态就与文件不符)。报告条目仍携带命中候选(endpoint
    供排查),**判定只看 reason** —— 按 endpoint 判会把漂移步骤误报成
    已锚(2026-10-15 实测发现的口径缺口)。"""
    pm.system_endpoints["fin"] = _fin_endpoints({"id": "fin.ep"})
    pm.fulls["fin.ep"] = {
        "binding": {"protocol": "http", "method": "POST",
                    "path": "/api/renamed"},
        "request": {"declarations": []},
    }
    out, report = await reanchor_import_definition(
        _defn([_raw_step()], plate={"fin": "1.0#1"}))
    assert "endpoint" not in out["steps"][0]
    assert report[0]["endpoint"] == "fin.ep"   # 命中了谁仍可见
    assert report[0]["reason"] == "not_in_revision"
    assert is_anchored(report[0]) is False     # 但不是已锚


async def test_pinned_ref_missing_full_not_anchored(pm: PlateMock):
    """/full?ref= 404(修订里没有该端点)→ 不锚。"""
    pm.system_endpoints["fin"] = _fin_endpoints({"id": "fin.ep"})
    out, report = await reanchor_import_definition(
        _defn([_raw_step()], plate={"fin": "1.0#1"}))
    assert "endpoint" not in out["steps"][0]
    assert report[0]["reason"] == "not_in_revision"


async def test_catalog_rejected_degrades_to_unresolved(pm: PlateMock):
    """清单被 plate 拒(404/4xx)→ 该系统不可反查,不阻塞。"""
    # 不注入 system_endpoints → handler 404 → PlateRejectedError
    out, report = await reanchor_import_definition(_defn([_raw_step()]))
    assert "endpoint" not in out["steps"][0]
    assert report[0]["reason"] == "catalog_unavailable"


async def test_not_in_catalog(pm: PlateMock):
    pm.system_endpoints["fin"] = _fin_endpoints(
        {"id": "fin.ep", "path": "/other"})
    out, report = await reanchor_import_definition(_defn([_raw_step()]))
    assert "endpoint" not in out["steps"][0]
    assert report[0]["reason"] == "not_in_catalog"


async def test_anchored_and_shapeless_steps_untouched(pm: PlateMock):
    """已锚步骤跳过;手写裸调用(无 method/path)无可反查形状 → 原样;
    无待锚步骤时原对象原样返回(身份相等)。"""
    pm.system_endpoints["fin"] = _fin_endpoints({"id": "fin.ep"})
    anchored = {"kind": "step", "endpoint": "fin.ep",
                "call": {"kind": "call", "protocol": "http",
                         "service": "fin-service", "method": "GET",
                         "path": "/x"},
                "request": None, "strategy": []}
    handwritten = {"kind": "step",
                   "call": {"kind": "call", "protocol": "http",
                            "service": "fin-service"},
                   "request": {"kind": "request", "body": {}},
                   "strategy": []}
    src = _defn([anchored, handwritten])
    out, report = await reanchor_import_definition(src)
    assert out is src                     # 无待锚:同对象返回
    assert report == []


async def test_mixed_steps_partial_anchor(pm: PlateMock):
    pm.system_endpoints["fin"] = _fin_endpoints(
        {"id": "fin.ep", "path": "/api/order/orderEntrust/orderPage"})
    out, report = await reanchor_import_definition(
        _defn([_raw_step(), _raw_step(path="/nope")]))
    assert out["steps"][0]["endpoint"] == "fin.ep"
    assert "endpoint" not in out["steps"][1]
    assert [r["index"] for r in report] == [0, 1]
    assert report[1]["reason"] == "not_in_catalog"
