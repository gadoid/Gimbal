"""v2.1 批次 A 契约测试：CallResult / render-send / 双写 / 补丁 / 脱敏 / 截断。

覆盖验收门（v2.1 实施案 §五）：
  2. 新证据路径端到端：``$.call.response.body.*`` 的 Extract/Assertion
     在 http（mock 传输）与 echo（自定义协议）双场景；
  3. 契约样板 + scratch 双写（``call`` 键 + 旧键）；
  4. CALL_BEFORE 可补丁：钩子原地改写请求字段影响真实发送；
  5. 脱敏与截断：敏感头不出现在 CallResult.request/CallExchangeEvent；
     超限 body 截断带标记；
  外加：传输失败 → ERROR StrategyResult（历史文案保持）。
"""
import dataclasses
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Optional
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from gimbal.core.hooks import HookPoint, HookRegistry
from gimbal.events.bus import InMemoryEventBus
from gimbal.protocols.base import ProtocolCallContext, ProtocolExecutor, ProtocolTransportError
from gimbal.protocols.result import CallResult, truncate_oversize
from gimbal.schema.call import Call
from gimbal.schema.step import Step
from gimbal.schema.strategy import AssertOperator, Assertion, Extract, StrategyPhase
from gimbal.statemachine.engine import StepStateMachine
from gimbal.statemachine.states import StepState
from gimbal.strategy.builtin.call import CallExecutor
from gimbal.strategy.dispatcher import build_default_dispatcher
from gimbal.strategy.executor_base import StrategyResult, StrategyStatus


class _StubView:
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


class EchoExecutor(ProtocolExecutor):
    """最小实现样板：只有 build_spec + send。"""

    protocol = "echo"

    def build_spec(self, call, pctx):
        return EchoSpec(message=getattr(call, "message", ""), pctx=pctx)

    def send(self, spec, view):
        return CallResult.build(
            protocol=self.protocol,
            request={"message": spec.message},
            status=0,
            body={"echo": spec.message},
        )


def _mock_httpx(status=200, body=None):
    mock_response = MagicMock()
    mock_response.status_code = status
    if body is not None:
        mock_response.json.return_value = body
    else:
        mock_response.json.side_effect = Exception("not json")
        mock_response.text = ""
    mock_response.headers = {"Content-Type": "application/json"}
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.request = MagicMock(return_value=mock_response)
    return patch("httpx.Client", return_value=mock_client), mock_client


class TestDualWriteScratch:

    def test_http_call_key_only(self):
        """v2.1 批次 F 定稿：``call`` 是唯一 scratch 证据键（旧键已退役）。"""
        from gimbal.schema.call import Call
        from gimbal.schema.request import Request

        step = Step(
            call=Call(protocol="http", service="svc", method="POST", path="/o", headers={"X-A": "1"}),
            request=Request(body={"k": 1}),
            strategy=[],
        )
        dispatcher = build_default_dispatcher(hook_registry=HookRegistry())
        view = _StubView()
        sm = StepStateMachine(
            step_id="s", step_schema=step, dispatcher=dispatcher, view=view,
            services={"svc": "https://svc.example"},
            protocol_registry=dispatcher.protocols,
        )
        with _mock_httpx(200, {"code": 0, "data": {"id": 9}})[0]:
            result = sm._do_call()

        assert result.status == StrategyStatus.PASSED
        # 唯一证据键：call（统一证据形状）
        call_ev = view.read_scratch("call")
        assert call_ev["protocol"] == "http"
        assert call_ev["response"]["status"] == 200
        assert call_ev["response"]["body"]["data"]["id"] == 9
        assert call_ev["request"]["method"] == "POST"
        # 旧键已退役（F 批删除，下游一律经 $.call.* 导航）
        assert view.read_scratch("response_status") is None
        assert view.read_scratch("response_body") is None
        assert view.read_scratch("request_method") is None

    def test_new_path_extract_assertion_end_to_end_http(self):
        """新证据路径 ``$.call.response.body.*`` 的 Extract + Assertion 端到端（http）。"""
        from gimbal.schema.call import Call
        from gimbal.schema.request import Request

        step = Step(
            call=Call(protocol="http", service="svc", method="GET", path="/o"),
            request=Request(body={}),
            strategy=[
                Extract(name="t", expression="$.call.response.body.data.id", target="oid"),
                Assertion(name="c", target="$.oid", operator=AssertOperator.EQ, expected=9),
            ],
        )
        dispatcher = build_default_dispatcher(hook_registry=HookRegistry())
        view = _StubView()
        sm = StepStateMachine(
            step_id="s", step_schema=step, dispatcher=dispatcher, view=view,
            services={"svc": "https://svc.example"},
            protocol_registry=dispatcher.protocols,
        )
        with _mock_httpx(200, {"code": 0, "data": {"id": 9}})[0]:
            result = sm.run()
        assert result.status == "passed", result.error

    def test_new_path_extract_assertion_end_to_end_echo(self):
        """自定义协议同路径端到端（echo 样板只实现 build_spec/send）。"""
        step = Step(
            call=Call(protocol="echo", message="ping"),
            strategy=[
                Extract(name="t", expression="$.call.response.body.echo", target="got"),
                Assertion(name="c", target="$.got", operator=AssertOperator.EQ, expected="ping"),
            ],
        )
        dispatcher = build_default_dispatcher(hook_registry=HookRegistry())
        dispatcher.protocols.register(EchoExecutor())
        view = _StubView()
        sm = StepStateMachine(
            step_id="s", step_schema=step, dispatcher=dispatcher, view=view,
            protocol_registry=dispatcher.protocols,
        )
        result = sm.run()
        assert result.status == "passed", result.error
        # F 定稿：只有 call 键
        assert view.read_scratch("call")["response"]["body"]["echo"] == "ping"
        assert view.read_scratch("response_body") is None


class TestCallBeforePatch:

    def test_neutral_hook_patch_modifies_outgoing_request(self):
        """CALL_BEFORE_SEND 钩子原地改写 payload['request']['headers'] 影响真实发送。"""
        from gimbal.schema.call import Call
        from gimbal.schema.request import Request

        hooks = HookRegistry()

        def patcher(payload):
            payload["request"]["headers"]["X-Patch"] = "yes"
            payload["spec"].timeout = 0.5

        hooks.register(HookPoint.CALL_BEFORE_SEND, patcher)

        step = Step(call=Call(protocol="http", service="svc", method="GET", path="/p", headers={}),
                    request=Request(body={}), strategy=[])
        dispatcher = build_default_dispatcher(hook_registry=hooks)
        view = _StubView()
        sm = StepStateMachine(
            step_id="s", step_schema=step, dispatcher=dispatcher, view=view,
            hook_registry=hooks, services={"svc": "https://svc.example"},
            protocol_registry=dispatcher.protocols,
        )
        ctx_patch, mock_client = _mock_httpx(200, {"ok": True})
        with ctx_patch:
            result = sm._do_call()

        assert result.status == StrategyStatus.PASSED
        kwargs = mock_client.request.call_args.kwargs
        assert kwargs["headers"].get("X-Patch") == "yes"


class TestRedactionAndEvidence:

    def test_sensitive_headers_redacted_in_evidence(self):
        """Authorization 不进 CallResult.request 与 CallExchangeEvent。"""
        from gimbal.schema.call import Call
        from gimbal.schema.request import Request

        bus = InMemoryEventBus()
        got = []
        bus.subscribe(lambda e: got.append(e), "call.exchange")

        step = Step(
            call=Call(protocol="http", service="svc", method="GET", path="/p",
                    headers={"Authorization": "Bearer secret-token", "X-Ok": "1"}),
            request=Request(body={}), strategy=[],
        )
        dispatcher = build_default_dispatcher(hook_registry=HookRegistry())
        view = _StubView()
        sm = StepStateMachine(
            step_id="s", step_schema=step, dispatcher=dispatcher, view=view,
            event_bus=bus, services={"svc": "https://svc.example"},
            protocol_registry=dispatcher.protocols,
        )
        with _mock_httpx(200, {"ok": True})[0]:
            sm._do_call()

        call_ev = view.read_scratch("call")
        assert call_ev["request"]["headers"]["Authorization"] == "***redacted***"
        assert call_ev["request"]["headers"]["X-Ok"] == "1"
        assert got[0].result["request"]["headers"]["Authorization"] == "***redacted***"

    def test_oversize_body_truncated_with_flag(self):
        """超限 body 截断并带 _truncated 标记（to_evidence 硬约束）。"""
        big = {"blob": "x" * (200 * 1024)}
        ev = CallResult.build(protocol="http", request={}, status=200, body=big).to_evidence(max_chars=1024)
        assert "_truncated" in ev["response"]["body"]

    def test_redact_custom_keys(self):
        from gimbal.protocols.result import redact_mapping
        out = redact_mapping({"X-Auth-Token": "t", "Keep": "v", "user_password": "p"})
        assert out["X-Auth-Token"] == "***redacted***"
        assert out["Keep"] == "v"
        assert out["user_password"] == "***redacted***"


class TestTransportError:

    def test_http_transport_error_maps_to_error_result(self):
        """传输异常 → ERROR StrategyResult（历史文案 "Request error: ..." 保持）。"""
        import httpx
        from gimbal.schema.call import Call
        from gimbal.schema.request import Request

        step = Step(call=Call(protocol="http", service="svc", method="GET", path="/p"),
                    request=Request(body={}), strategy=[])
        dispatcher = build_default_dispatcher(hook_registry=HookRegistry())
        view = _StubView()
        sm = StepStateMachine(
            step_id="s", step_schema=step, dispatcher=dispatcher, view=view,
            services={"svc": "https://svc.example"},
            protocol_registry=dispatcher.protocols,
        )
        with patch("httpx.Client", side_effect=httpx.ConnectError("refused")):
            result = sm._do_call()
        assert result.status == StrategyStatus.ERROR
        assert "Request error" in result.message

    def test_no_scratch_evidence_on_transport_failure(self):
        """v2.1 批次 F 定稿：传输失败时不留 scratch 证据（失败详情在
        StrategyResult.error / CallExchange 不发布）；Debugger 的重发语义
        走 STEP_FAILED 决策的 retry=整步重跑，不再依赖请求侧旧键。"""
        import httpx
        from gimbal.schema.call import Call
        from gimbal.schema.request import Request

        step = Step(call=Call(protocol="http", service="svc", method="GET", path="/p"),
                    request=Request(body={"b": 1}), strategy=[])
        dispatcher = build_default_dispatcher(hook_registry=HookRegistry())
        view = _StubView()
        sm = StepStateMachine(
            step_id="s", step_schema=step, dispatcher=dispatcher, view=view,
            services={"svc": "https://svc.example"},
            protocol_registry=dispatcher.protocols,
        )
        with patch("httpx.Client", side_effect=httpx.ConnectError("refused")):
            result = sm._do_call()
        assert result.status == StrategyStatus.ERROR
        assert view.read_scratch("call") is None
        assert view.read_scratch("request_method") is None

    def test_transport_error_contract_direct(self):
        """契约单测：send 抛 ProtocolTransportError → 模板转 ERROR（文案透传）。"""
        class BoomExecutor(ProtocolExecutor):
            protocol = "boom"

            def build_spec(self, call, pctx):
                return dataclasses.replace(EchoSpec(message="x", pctx=pctx), kind="_call:boom")

            def send(self, spec, view):
                raise ProtocolTransportError("Request timeout: simulated",
                                             traceback_str="tb-here")

        ex = BoomExecutor()
        spec = ex.build_spec(Call(protocol="boom"), ProtocolCallContext(call=Call(protocol="boom")))
        result = ex.execute(spec, _StubView())
        assert result.status == StrategyStatus.ERROR
        assert result.message == "Request timeout: simulated"
        assert result.error == "tb-here"


class TestSummaryCompat:

    def test_http_summary_keeps_legacy_format(self):
        """StrategyResult.message 复现历史文案 "HTTP GET url -> 200"。"""
        from gimbal.schema.call import Call
        from gimbal.schema.request import Request

        step = Step(call=Call(protocol="http", service="svc", method="GET", path="/p"),
                    request=Request(body={}), strategy=[])
        dispatcher = build_default_dispatcher(hook_registry=HookRegistry())
        view = _StubView()
        sm = StepStateMachine(
            step_id="s", step_schema=step, dispatcher=dispatcher, view=view,
            services={"svc": "https://svc.example"},
            protocol_registry=dispatcher.protocols,
        )
        with _mock_httpx(200, {"ok": 1})[0]:
            result = sm._do_call()
        assert result.message == "HTTP GET https://svc.example/p -> 200"
