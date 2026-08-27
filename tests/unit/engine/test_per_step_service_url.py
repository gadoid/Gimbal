"""D7 per-step base_url:api.service 查 scenario.config.services 声明 dict,
未命中回落兼容 base_url,双缺失显式报错(spec 2026-08-27 §4)。

pytest 化子目录(testpaths 收录);手法与 tests/unit/test_defect_fixes.py
的 _make_sm_with_api 一致:StepStateMachine.__new__ 直填字段,dispatcher
用 MagicMock 捕获 call_spec.url。
"""
import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from gimbal.schema.api import Api
from gimbal.schema.request import Request
from gimbal.schema.step import Step
from gimbal.strategy.executor_base import StrategyResult, StrategyStatus
from gimbal.statemachine import engine as sm_engine


def _make_sm(service: str, base_url: str, services: dict | None = None):
    """最小 StepStateMachine 替身:只填 _do_http_call 触达的字段。"""
    sm = sm_engine.StepStateMachine.__new__(sm_engine.StepStateMachine)
    sm._step_id = "s1"
    sm._step_schema = Step(
        kind="step",
        api=Api(kind="api", service=service, method="GET", path="/x",
                headers={}, timeout=30.0),
        request=Request(kind="request", body={}),
        strategy=[],
    )
    sm._dispatcher = MagicMock()
    sm._dispatcher.dispatch.return_value = StrategyResult(
        status=StrategyStatus.PASSED, strategy_id="_call",
        message="mock ok", duration_ms=0.0,
    )
    sm._view = MagicMock()
    sm._service_base_url = base_url
    sm._services = services or {}
    sm._on_transition = None
    sm._hooks = None
    sm._bus = None
    sm._state = sm_engine.StepState.CALLING
    sm._phase_results = []
    sm._error = None
    sm._error_phase = None
    sm._handlers = {}
    return sm


def _called_url(sm) -> str:
    return sm._dispatcher.dispatch.call_args[0][0].url


def test_per_step_lookup_beats_fallback_base_url():
    """声明 dict 命中 → 用声明值,不用回落 base_url(D7 主路径)。"""
    sm = _make_sm("fin-service", base_url="https://fallback.example",
                  services={"fin-service": "https://fin.example"})
    result = sm._do_http_call()
    assert result.status == StrategyStatus.PASSED
    assert _called_url(sm) == "https://fin.example/x"


def test_two_services_route_independently():
    """多服务场景:两个 service 各自查表,不再共享一个 base_url(旧错路由修复)。"""
    sm_a = _make_sm("fin-service", base_url="https://fallback.example",
                    services={"fin-service": "https://a.example",
                              "order-svc": "https://b.example"})
    sm_b = _make_sm("order-svc", base_url="https://fallback.example",
                    services={"fin-service": "https://a.example",
                              "order-svc": "https://b.example"})
    assert sm_a._do_http_call().status == StrategyStatus.PASSED
    assert sm_b._do_http_call().status == StrategyStatus.PASSED
    assert _called_url(sm_a) == "https://a.example/x"
    assert _called_url(sm_b) == "https://b.example/x"


def test_missing_key_falls_back_to_base_url():
    """声明 dict 未含该键 → 回落 _service_base_url(兼容路径)。"""
    sm = _make_sm("unknown-svc", base_url="https://fallback.example",
                  services={"fin-service": "https://fin.example"})
    result = sm._do_http_call()
    assert result.status == StrategyStatus.PASSED
    assert _called_url(sm) == "https://fallback.example/x"


def test_both_missing_keeps_explicit_error():
    """dict 未命中且 base_url 为空 → 保留 #6 显式报错(消息不变)。"""
    sm = _make_sm("orphan-svc", base_url="", services={"fin-service": "https://x"})
    result = sm._do_http_call()
    assert result.status == StrategyStatus.ERROR
    assert "no service_base_url configured" in result.message
    assert "orphan-svc" in result.message
    assert sm._dispatcher.dispatch.call_count == 0


def test_empty_services_dict_identical_to_legacy():
    """services 空 dict → 行为与旧版逐字节一致(单服务回归底线)。"""
    sm = _make_sm("fin-service", base_url="https://only.example", services={})
    result = sm._do_http_call()
    assert result.status == StrategyStatus.PASSED
    assert _called_url(sm) == "https://only.example/x"


def test_preprocessor_run_returns_declared_services():
    """run() 三元组:第三项 = 场景声明 dict 原样(不合并 bootstrap)。"""
    from datetime import datetime, timezone

    from gimbal.auth.registry import AuthRegistry
    from gimbal.config.models import BootstrapConfig
    from gimbal.preprocessor.scenario_preprocessor import ScenarioPreprocessor
    from gimbal.schema.scenario import Config as ScenarioConfig
    from gimbal.schema.scenario import Meta, Scenario

    def _step(service_name: str):
        return Step(
            kind="step",
            api=Api(kind="api", service=service_name, method="GET", path="/x",
                    headers={}, timeout=30.0),
            request=Request(kind="request", body={}),
            strategy=[],
        )

    scenario = Scenario(
        scenarioId="sc1",
        meta=Meta(name="t", description="d", module="m", priority=1,
                  author="a", owner="o", tags=[], version="1.0",
                  createTime=datetime.now(timezone.utc), expire=False,
                  requirementRef=[]),
        config=ScenarioConfig(services={
            "user-svc": "https://user.example.com",
            "order-svc": "https://order.example.com",
        }),
        resource={},
        steps=[_step("user-svc"), _step("order-svc")],
    )
    pre = ScenarioPreprocessor(
        scenario_schema=scenario,
        bootstrap_config=BootstrapConfig(env="dev", mode="local", log_level="info"),
        auth_registry=AuthRegistry(),
    )
    resolved, base_url, services = pre.run()
    assert services == {"user-svc": "https://user.example.com",
                        "order-svc": "https://order.example.com"}
    # base_url 兼容路径仍在(_pick_base_url 多键取其一)。注意:多键分支的
    # next(iter(set)) 迭代顺序受 PYTHONHASHSEED 随机化影响,两个服务谁被
    # 取中跨进程不稳定 —— 只断言取值来自声明 dict,不断言具体是哪一个。
    assert base_url in {"https://user.example.com", "https://order.example.com"}
    assert len(resolved) == 2
