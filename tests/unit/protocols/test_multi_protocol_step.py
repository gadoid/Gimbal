"""协议中立状态机 — 多协议步骤端到端 + HTTP 钩子契约保持。

覆盖：
  - 自定义协议（echo）经 ProtocolRegistry 分派，状态机全流程流转
    （PREPARE → INVOKING → EXTRACTING → VERIFYING → PASSED）；
  - Extract/Assertion 用 JSONPath 消费自定义协议写下的 scratch（统一查询方法）；
  - 中立层钩子 CALL_BEFORE_SEND / CALL_AFTER_RECV 触发；
  - CallExchangeEvent（protocol 信封）发布；
  - 未注册协议 → 显式 ERROR（列出已注册协议）；
  - 状态枚举别名：中立名与历史名同值（事件/报告零回归）；
  - HTTP 兼容契约：HTTP_BEFORE_SEND 原地改写 headers 影响真实请求
    （已随批次 F-2b 退役）。
"""
import dataclasses
import os
import sys
from dataclasses import dataclass, field
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from gimbal.core.hooks import HookPoint, HookRegistry
from gimbal.events.bus import InMemoryEventBus
from gimbal.protocols.base import ProtocolCallContext, ProtocolExecutor
from gimbal.protocols.result import CallResult
from gimbal.schema.call import Call
from gimbal.schema.request import Request
from gimbal.schema.step import Step
from gimbal.schema.strategy import Assertion, AssertOperator, Extract
from gimbal.statemachine.engine import StepStateMachine
from gimbal.statemachine.states import StepState
from gimbal.strategy.dispatcher import build_default_dispatcher
from gimbal.strategy.executor_base import StrategyResult, StrategyStatus


# ── 测试用自定义协议执行器 ───────────────────────────────────

@dataclass
class EchoSpec:
    kind: str = "_call:echo"
    message: str = ""
    name: Optional[str] = "echo_call"
    phase: Optional[str] = None
    order: int = 0
    enabled: bool = True
    onFailure: str = "abort"
    tags: list = dataclasses.field(default_factory=list)
    pctx: Optional[ProtocolCallContext] = None


class EchoProtocolExecutor(ProtocolExecutor):
    """echo 协议（v2.1 批次 A 契约样板）：仅实现 build_spec + send。

    scratch 双写由基类模板完成：``call`` 键（统一证据形状）+ 旧键
    （response_status / response_body）。
    """

    protocol = "echo"

    def build_spec(self, call, pctx: ProtocolCallContext):
        return EchoSpec(message=getattr(call, "message", ""), pctx=pctx)

    def send(self, spec, view) -> CallResult:
        return CallResult.build(
            protocol=self.protocol,
            request={"message": spec.message},
            status=0,
            body={"echo": spec.message, "ok": True},
        )


class _StubView:
    """最小 view 替身：覆盖状态机/执行器实际用到的 scratch 读写。"""

    def __init__(self) -> None:
        self._scratch: dict = {}

    def read_scratch(self, key, default=None):
        return self._scratch.get(key, default)

    def write_scratch(self, key, value) -> None:
        self._scratch[key] = value

    def get_scratch_dict(self) -> dict:
        return dict(self._scratch)

    def read_variable(self, *a, **k):
        return None

    def promote_variable(self, *a, **k):
        return None

    def record_assertion(self, *a, **k):
        return None

    def attach_artifact(self, *a, **k):
        return None


def _make_sm(step: Step, hooks: HookRegistry = None, bus: InMemoryEventBus = None):
    # S-2：埋点设施（hooks/bus）经注册表注入执行器，不经 pctx 塞传
    dispatcher = build_default_dispatcher(hook_registry=hooks, event_bus=bus)
    dispatcher.protocols.register(EchoProtocolExecutor())
    return StepStateMachine(
        step_id="step-000",
        step_schema=step,
        dispatcher=dispatcher,
        view=_StubView(),
        hook_registry=hooks,
        event_bus=bus,
        protocol_registry=dispatcher.protocols,
    )


# ── 多协议全流程 ─────────────────────────────────────────────

class TestMultiProtocolStep:

    def test_custom_protocol_full_flow_with_extract_assertion(self):
        """echo 协议步骤：Extract(JSONPath) → Assertion(JSONPath) 全绿。"""
        step = Step(
            call=Call(protocol="echo", message="hello"),
            strategy=[
                Extract(name="take_echo", expression="$.call.response.body.echo",
                        target="echo_value"),
                Assertion(name="check_echo", target="$.echo_value",
                          operator=AssertOperator.EQ, expected="hello"),
            ],
        )
        sm = _make_sm(step)
        result = sm.run()

        assert result.status == "passed", result.error
        assert result.error_phase is None
        # 各阶段均有产出：calling 阶段是 echo 协议调用结果
        phases = [p.phase for p in result.phase_results]
        assert "calling" in phases   # error_phase 历史口径 value 不变

    def test_state_enum_aliases_same_value(self):
        """中立名与历史名是同一成员、同 value —— 序列化零回归。"""
        assert StepState.PREPARE is StepState.BEFORE_REQUEST
        assert StepState.INVOKING is StepState.CALLING
        assert StepState.EXTRACTING is StepState.AFTER_REQUEST
        assert StepState.PREPARE.value == "before_request"
        assert StepState.INVOKING.value == "calling"
        assert StepState.EXTRACTING.value == "after_request"

    def test_neutral_hooks_fired_for_custom_protocol(self):
        """中立层钩子 CALL_BEFORE_SEND/AFTER_RECV 对所有协议触发。"""
        hooks = HookRegistry()
        seen = []
        hooks.register(HookPoint.CALL_BEFORE_SEND,
                       lambda p: seen.append(("before", p["protocol"])))
        hooks.register(HookPoint.CALL_AFTER_RECV,
                       lambda p: seen.append(("after", p["protocol"], p["result"].status)))

        step = Step(call=Call(protocol="echo", message="hi"), strategy=[])
        sm = _make_sm(step, hooks=hooks)
        result = sm.run()
        assert result.status == "passed"
        assert seen[0] == ("before", "echo")
        assert seen[1][0] == "after" and seen[1][1] == "echo"
        assert seen[1][2] == StrategyStatus.PASSED

    def test_call_exchange_event_published(self):
        """中立事件信封 CallExchangeEvent 带 protocol 字段。"""
        bus = InMemoryEventBus()
        got = []
        bus.subscribe(lambda e: got.append(e), "call.exchange")

        step = Step(call=Call(protocol="echo", message="hi"), strategy=[])
        sm = _make_sm(step, bus=bus)
        assert sm.run().status == "passed"
        assert len(got) == 1
        assert got[0].protocol == "echo"
        assert got[0].status == "passed"
        assert "call" in got[0].evidence_keys   # F 定稿：唯一证据键
        # v2.1 批次 A：事件携带脱敏后的完整 CallResult
        assert got[0].result["protocol"] == "echo"
        assert got[0].result["response"]["body"]["echo"] == "hi"

    def test_unknown_protocol_explicit_error(self):
        step = Step(call=Call(protocol="grpc", service="u"), strategy=[])
        sm = _make_sm(step)
        # 三段式第一段：注册表未命中 → 显式 ERROR（列出已注册协议便于排障）
        result = sm._do_call()
        assert result.status == StrategyStatus.ERROR
        assert "grpc" in result.message
        assert "http" in result.message

    def test_http_sugar_still_routes_via_registry(self):
        """api 糖 → 归一化 call{http} → 注册表分派到 CallExecutor（缺路由显式报错）。"""
        from gimbal.schema.call import Call
        from gimbal.schema.request import Request
        step = Step(
            call=Call(protocol="http", service="orphan", method="GET", path="/x"),
            request=Request(body={}),
            strategy=[],
        )
        sm = _make_sm(step)
        # 未配置 services/base_url → 显式路由错误（#6 修复语义保持）
        result = sm._do_call()
        assert result.status == StrategyStatus.ERROR
        assert "no service_base_url configured" in result.message
        assert "orphan" in result.message


