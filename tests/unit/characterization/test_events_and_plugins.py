"""特征化：事件形状与插件引擎级端到端（批次 F 插件改造的行为基准）。

事件形状钉死 collector 的消费面（http.request/http.response/call.exchange/
scenario.end）；认证注入走原生适配器（批次 F-2b：auth_headers /
引擎 + mock httpx 传输（改造前后行为必须一致）。
"""
import dataclasses
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from gimbal.auth.registry import AuthRegistry
from gimbal.config.models import BootstrapConfig
from gimbal.context.archive import InMemoryArchive
from gimbal.context.manager import ContextManager
from gimbal.core.bootstrap import Configuration
from gimbal.core.hooks import HookRegistry
from gimbal.core.plugin import PluginContext
from gimbal.core.runner import Engine
from gimbal.events.bus import InMemoryEventBus
from gimbal.plugins import PluginRegistry
from gimbal.schema.call import Call
from gimbal.schema.call import Call
from gimbal.schema.request import Request
from gimbal.schema.scenario import Config as ScenarioConfig, Meta, Scenario
from gimbal.schema.step import Step
from gimbal.schema.strategy import AssertOperator, Assertion
from gimbal.strategy.dispatcher import build_default_dispatcher


def make_engine(auth_session=None):
    bus = InMemoryEventBus()
    archive = InMemoryArchive()
    hooks = HookRegistry()
    auth_registry = AuthRegistry()
    # S-2：埋点设施（bus/auth）经注册表注入协议执行器，顺序先行构造
    dispatcher = build_default_dispatcher(
        hook_registry=hooks, event_bus=bus, auth_registry=auth_registry,
    )
    ctx_manager = ContextManager(archive=archive, event_bus=bus)
    cfg = BootstrapConfig(env="test", mode="local", log_level="error")
    if auth_session is not None:
        tag, session = auth_session
        auth_registry.set(tag, session)
    conf = Configuration(
        cfg=cfg, auth_registry=auth_registry, ctx_manager=ctx_manager,
        dispatcher=dispatcher, event_bus=bus, archive=archive,
        hook_registry=hooks, plugin_registry=PluginRegistry(), plugins=(),
        reporter_runtime=None, protocols=dispatcher.protocols,
    )
    return Engine(conf), bus, archive, hooks, dispatcher, auth_registry


def http_scenario(sid="ev-sc", strategy=None, service="svc", path="/p"):
    return Scenario(
        scenarioId=sid,
        meta=Meta(name=sid, description="d", module="m", priority=1, author="a",
                  owner="o", tags=[], version="1.0",
                  createTime=datetime.now(timezone.utc), expire=False,
                  requirementRef=[]),
        config=ScenarioConfig(services={service: "https://svc.example"}),
        resource={},
        steps=[Step(call=Call(protocol="http", service=service, method="POST", path=path),
                    request=Request(kind="request", body={"b": 1}),
                    strategy=strategy or [])],
    )


def mock_httpx(status=200, body=None):
    resp = MagicMock()
    resp.status_code = status
    if body is not None:
        resp.json.return_value = body
    else:
        resp.json.side_effect = Exception("not json")
        resp.text = "<html/>"
    resp.headers = {"Content-Type": "application/json"}
    client = MagicMock()
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    client.request = MagicMock(return_value=resp)
    return patch("httpx.Client", return_value=client), client


class TestEventShapes:
    """钉死事件形状（collector/test_report 的消费面）。"""

    def test_http_request_response_event_shapes(self):
        engine, bus, *_ = make_engine()
        got: dict[str, list] = {"http.request": [], "http.response": []}
        for et in got:
            bus.subscribe(lambda e, et=et: got[et].append(e), et)

        with mock_httpx(200, {"code": 0})[0]:
            result = engine.run(http_scenario())
        assert result.passed == 1

        req = got["http.request"][0]
        assert req.step_id == "step-000"
        assert req.method == "POST"
        assert req.url == "https://svc.example/p"
        assert req.request_body == {"b": 1}
        assert req.request_headers == {}

        resp = got["http.response"][0]
        assert resp.step_id == "step-000"
        assert resp.status_code == 200
        assert resp.response_body == {"code": 0}
        assert resp.duration_ms >= 0

    def test_call_exchange_event_shape_with_result_envelope(self):
        engine, bus, *_ = make_engine()
        got = []
        bus.subscribe(lambda e: got.append(e), "call.exchange")
        with mock_httpx(201, {"ok": 1})[0]:
            engine.run(http_scenario())
        ev = got[0]
        assert ev.protocol == "http"
        assert ev.status == "passed"
        assert ev.result["protocol"] == "http"
        assert ev.result["response"]["status"] == 201
        assert ev.result["response"]["body"] == {"ok": 1}
        assert "call" in ev.evidence_keys   # F 定稿：唯一证据键

    def test_scenario_end_meta_flattened(self):
        engine, bus, *_ = make_engine()
        got = []
        bus.subscribe(lambda e: got.append(e), "scenario.end")
        with mock_httpx(200, {"code": 0})[0]:
            engine.run(http_scenario("meta-sc"))
        # scenario.end 双发（先 ContextManager 投影、后 runner emit）是现行行为：
        # 投影事件无 meta；runner 事件携带拍平的 meta dict
        assert len(got) == 2
        projection, runner_emit = got[0], got[1]
        assert projection.scenario_id == "meta-sc" and projection.status == "passed"
        assert not (projection.meta or {})
        assert runner_emit.scenario_id == "meta-sc"
        assert runner_emit.meta["name"] == "meta-sc"

    def test_request_evidence_redacted_in_call_exchange(self):
        engine, bus, *_ = make_engine()
        got = []
        bus.subscribe(lambda e: got.append(e), "call.exchange")

        scenario = Scenario(
            scenarioId="redact-sc",
            meta=Meta(name="r", description="d", module="m", priority=1, author="a",
                      owner="o", tags=[], version="1.0",
                      createTime=datetime.now(timezone.utc), expire=False,
                      requirementRef=[]),
            config=ScenarioConfig(services={"svc": "https://svc.example"}),
            resource={},
            steps=[Step(
                call=Call(protocol="http", service="svc", method="GET", path="/p",
                        headers={"Authorization": "Bearer tok-1"}),
                request=Request(kind="request", body={}), strategy=[])],
        )
        with mock_httpx(200, {"code": 0})[0]:
            engine.run(scenario)
        assert got[0].result["request"]["headers"]["Authorization"] == "***redacted***"

    def test_archive_exchange_stores_evidence_form(self):
        """P0-3：scratch 存原值后，归档 exchange 的 ``call`` 键仍是证据形态
        （脱敏 + 截断），不携带 scratch 原值。"""
        engine, bus, archive, *_ = make_engine()
        got = []
        bus.subscribe(lambda e: got.append(e), "call.exchange")

        scenario = http_scenario(sid="arch-redact")
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"code": 0}
        resp.headers = {"Content-Type": "application/json", "accesstoken": "abc123"}
        client = MagicMock()
        client.__enter__ = MagicMock(return_value=client)
        client.__exit__ = MagicMock(return_value=False)
        client.request = MagicMock(return_value=resp)
        with patch("httpx.Client", return_value=client):
            result = engine.run(scenario)
        assert result.passed == 1

        ex = archive.get_exchange("step-000", scenario_id="arch-redact")
        assert ex is not None
        assert ex["call"]["response"]["meta"]["headers"]["accesstoken"] == "***redacted***"
        # 事件出口同口径（两处证据出口都不携带原值）
        assert got[0].result["response"]["meta"]["headers"]["accesstoken"] == "***redacted***"

    def test_archive_step_assertions_redacted_for_sensitive_target(self):
        """P0-3b：断言 target 命中敏感键 → 归档 StepContext.outcome.assertions
        的 actual/expected 为脱敏形态；判定仍按原值（run passed）。"""
        engine, bus, archive, *_ = make_engine()

        scenario = http_scenario(
            sid="arch-assert",
            strategy=[Assertion(name="tok",
                                target="$.call.response.meta.headers.accesstoken",
                                operator=AssertOperator.EQ, expected="abc123")],
        )
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"code": 0}
        resp.headers = {"Content-Type": "application/json", "accesstoken": "abc123"}
        client = MagicMock()
        client.__enter__ = MagicMock(return_value=client)
        client.__exit__ = MagicMock(return_value=False)
        client.request = MagicMock(return_value=resp)
        with patch("httpx.Client", return_value=client):
            result = engine.run(scenario)
        assert result.passed == 1

        step = archive.get_step("step-000", scenario_id="arch-assert")
        assert step is not None
        a = step.outcome.assertions[0]
        assert a.passed is True                     # 判定按 scratch 原值
        assert a.actual == "***redacted***"         # 归档出口脱敏
        assert a.expected == "***redacted***"
        assert "abc123" not in (a.message or "")


class TestPluginsEngineLevel:
    """v2.1 批次 F-2b：认证注入原生进 http 适配器（auth_headers 插件退役）。"""

    def test_native_auth_injection_via_call_user(self):
        """原生注入契约（与退役插件 auth_headers 逐字节一致，特征化延续）：

        call.user 标签 → AuthRegistry 会话 → token = md5(token+ts) 32-hex
        + timestamp 头；无 user 标签不注入。
        """
        import re
        from gimbal.schema.auth import AuthSession
        from gimbal.schema.call import Call
        from gimbal.schema.request import Request

        engine, bus, archive, hooks, dispatcher, auth_registry = make_engine(
            auth_session=("buyer", AuthSession(token="tok-XYZ", token_type="Bearer")),
        )
        scenario = Scenario(
            scenarioId="auth-sc",
            meta=Meta(name="a", description="d", module="m", priority=1, author="a",
                      owner="o", tags=[], version="1.0",
                      createTime=datetime.now(timezone.utc), expire=False,
                      requirementRef=[]),
            config=ScenarioConfig(services={"svc": "https://svc.example"}),
            resource={},
            steps=[Step(
                call=Call(protocol="http", service="svc", method="GET", path="/p",
                          user="buyer"),
                request=Request(kind="request", body={}), strategy=[])],
        )
        ctx_patch, client = mock_httpx(200, {"code": 0})
        with ctx_patch:
            result = engine.run(scenario)
        assert result.passed == 1
        sent = client.request.call_args.kwargs["headers"]
        assert re.fullmatch(r"[0-9a-f]{32}", str(sent.get("token", "")))
        assert "timestamp" in sent

    def test_native_injection_signature_varies_with_session(self):
        """签名随会话 token 变化（不同会话 → 不同 token 头）。"""
        import re
        from gimbal.schema.auth import AuthSession
        from gimbal.schema.call import Call
        from gimbal.schema.request import Request

        def _run_with(token):
            engine, *_ = make_engine(
                auth_session=("buyer", AuthSession(token=token)))
            scenario = Scenario(
                scenarioId="sig-sc",
                meta=Meta(name="s", description="d", module="m", priority=1,
                          author="a", owner="o", tags=[], version="1.0",
                          createTime=datetime.now(timezone.utc), expire=False,
                          requirementRef=[]),
                config=ScenarioConfig(services={"svc": "https://svc.example"}),
                resource={},
                steps=[Step(
                    call=Call(protocol="http", service="svc", method="GET",
                              path="/p", user="buyer"),
                    request=Request(kind="request", body={}), strategy=[])],
            )
            _, client = mock_httpx(200, {"code": 0})
            with mock_httpx(200, {"code": 0})[0]:
                engine.run(scenario)
            # 传给 httpx 的 headers 在 mock 下不易取回 → 直接调注入函数断言差异
            headers_a = {}
            spec = type("S", (), {"pctx": None})()
            from gimbal.strategy.builtin.call import CallExecutor
            ex = CallExecutor()

            class _P:
                pass

            pc = _P()
            pc.call = Call(protocol="http", service="s", method="GET", path="/",
                           user="buyer")
            # S-2：认证注册表经执行器 bind 注入（不再经 pctx 塞传）
            ex.bind(auth_registry=engine._ictx.auth_registry)
            ex._inject_auth_headers(headers_a, pc)
            return headers_a

        h1 = _run_with("token-one")
        h2 = _run_with("token-two")
        assert re.fullmatch(r"[0-9a-f]{32}", h1["token"])
        # 同秒内 timestamp 相同 → 签名只随 token 变化
        if h1["timestamp"] == h2["timestamp"]:
            assert h1["token"] != h2["token"]

    def test_no_user_tag_no_injection(self):
        """call 无 user 标签 → 注入函数被调但不写任何头。"""
        engine, *_ = make_engine()
        scenario = http_scenario("noauth-sc")
        ctx_patch, client = mock_httpx(200, {"code": 0})
        with ctx_patch:
            result = engine.run(scenario)
        assert result.passed == 1
        sent = client.request.call_args.kwargs["headers"]
        assert "token" not in sent and "timestamp" not in sent

    def test_collector_consumes_event_stream_without_error(self):
        """collector 的消费面 = 事件订阅（批次 F-2b：事件形状用例已钉死全部
        事件契约；插件本体随 plugins 目录治理另行处置）。此处钉执行链
        在移除两个钩子型插件后仍无异常跑通。"""
        engine, bus, *_ = make_engine()
        counter = {"n": 0}
        bus.subscribe(lambda e: counter.__setitem__("n", counter["n"] + 1),
                      "call.exchange")
        with mock_httpx(200, {"code": 0})[0]:
            result = engine.run(http_scenario("col-sc"))
        assert result.passed == 1
        assert counter["n"] >= 1
