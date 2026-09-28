"""F-2a 修复的专项测试：run_materialize 在 plate call 形态产物上的行为。

背景（盲区）：平台执行链测试用 PlateMock 的 echo 行为把输入场景原样回灌为
converted —— 存储场景的 steps 是平台形态（带 api），所以 referenced_services/
_apply_carry 在测试里仍能看到 api。真 plate 的 call 产物从未被这两条断言路径
覆盖。本文件用 **call 形态的 converted dict** 直接测试物化纯函数。
"""
import os
import sys

# backend 路径必须 append 到尾部:insert(0) 会让 backend/tests(正式包)
# 遮蔽仓库根的命名空间包 tests,合跑 tests/plate 时 tests.plate 解析失败
_BACKEND = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                        "src", "gimbal-platform", "backend")
if _BACKEND not in sys.path:
    sys.path.append(_BACKEND)

import pytest

from app.services.run_materialize import referenced_services


def _call_step(service: str, **extra) -> dict:
    return {
        "kind": "step",
        "call": {"kind": "call", "protocol": "http", "service": service,
                 "method": "GET", "path": "/x", **extra},
        "request": {"kind": "request", "body": {}},
        "strategy": [],
    }


class TestReferencedServices:
    """call 唯一形态(api 兜底已随 api→call 清理退役)。"""

    def test_call_form_services_extracted(self):
        steps = [_call_step("fin"), _call_step("order"), _call_step("fin")]
        assert referenced_services(steps) == ["fin", "order"]

    def test_no_service_key(self):
        steps = [{"kind": "step", "call": {"kind": "call", "protocol": "echo",
                                           "message": "x"},
                  "strategy": []}]
        assert referenced_services(steps) == []

    def test_non_dict_steps_ignored(self):
        assert referenced_services([None, "junk", _call_step("ok")]) == ["ok"]


class TestApplyServicesCallForm:
    """_apply_services 消费 referenced_services 的结果——call 形态下绑定链 intact。"""

    def test_call_form_binding_url_materialized(self):
        from app.services.run_materialize import _apply_services
        cfg = {"services": {}}
        steps = [_call_step("fin")]
        _apply_services(cfg, steps=steps, bindings={"fin": {"url": "https://bound"}})
        assert cfg["services"]["fin"] == "https://bound"

    def test_call_form_alias_fallback(self):
        from app.services.run_materialize import _apply_services
        cfg = {"services": {}}
        steps = [_call_step("fin")]
        _apply_services(cfg, steps=steps, bindings={},
                        alias_base_urls={"fin": "https://alias"})
        assert cfg["services"]["fin"] == "https://alias"

    def test_call_form_gap_left_for_engine(self):
        """未绑定且无别名 → 缺口留给引擎显式报错（D2 语义）。"""
        from app.services.run_materialize import _apply_services
        cfg = {"services": {}}
        steps = [_call_step("orphan")]
        _apply_services(cfg, steps=steps, bindings={}, alias_base_urls={})
        assert "orphan" not in cfg["services"]
