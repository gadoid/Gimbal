"""批次 E 测试：Decision 通道 / 整步重跑与 repaired / skip / patch / step_from /
debugger 会话端到端 / server 调试端点鉴权与 SSE。"""
import dataclasses
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

import pytest

from gimbal.auth.registry import AuthRegistry
from gimbal.config.models import BootstrapConfig
from gimbal.context.archive import InMemoryArchive
from gimbal.context.manager import ContextManager
from gimbal.core.bootstrap import Configuration
from gimbal.core.decisions import Decision, ask_decision
from gimbal.core.debugger import DebuggerPlugin, ScriptedSession
from gimbal.core.hooks import HookPoint, HookRegistry
from gimbal.core.runner import Engine
from gimbal.events.bus import InMemoryEventBus
from gimbal.plugins import PluginRegistry
from gimbal.protocols.base import ProtocolCallContext, ProtocolExecutor
from gimbal.protocols.result import CallResult
from gimbal.schema.call import Call
from gimbal.schema.scenario import Config as ScenarioConfig, Meta, Scenario, SuiteGraph, UnitDecl
from gimbal.schema.step import Step
from gimbal.strategy.dispatcher import build_default_dispatcher


@dataclass
class EchoSpec:
    kind: str = "call:echo"
    name: Optional[str] = "echo_call"
    phase: Optional[str] = None
    order: int = 0
    enabled: bool = True
    onFailure: str = "abort"
    tags: list = dataclasses.field(default_factory=list)
    pctx: Optional[ProtocolCallContext] = None


class ProgEcho(ProtocolExecutor):
    protocol = "echo"

    def __init__(self, send_fn=None):
        super().__init__()
        self.send_fn = send_fn or (lambda s, v: CallResult.build(
            protocol="echo", request={}, status=0, body={"msg": "ok"}))

    def build_spec(self, call, pctx):
        return EchoSpec(pctx=pctx)

    def send(self, spec, view):
        return self.send_fn(spec, view)


def _make_engine(send_fn=None, executor=None):
    bus = InMemoryEventBus()
    archive = InMemoryArchive()
    hooks = HookRegistry()
    dispatcher = build_default_dispatcher(hook_registry=hooks)
    dispatcher.protocols.register(executor or ProgEcho(send_fn))
    ctx_manager = ContextManager(archive=archive, event_bus=bus)
    cfg = BootstrapConfig(env="test", mode="local", log_level="error")
    conf = Configuration(
        cfg=cfg, auth_registry=AuthRegistry(), ctx_manager=ctx_manager,
        dispatcher=dispatcher, event_bus=bus, archive=archive,
        hook_registry=hooks, plugin_registry=PluginRegistry(), plugins=(),
        reporter_runtime=None, protocols=dispatcher.protocols,
    )
    return Engine(conf), hooks, bus


def _scenario(sid, steps_msg="ok", assert_val="ok", n_steps=1) -> Scenario:
    return Scenario(
        scenarioId=sid,
        meta=Meta(name=sid, description="d", module="m", priority=1, author="a",
                  owner="o", tags=[], version="1.0",
                  createTime=datetime.now(timezone.utc), expire=False,
                  requirementRef=[]),
        config=ScenarioConfig(),
        resource={},
        steps=[Step(call=Call(protocol="echo", message=f"{sid}-{i}"),
                    strategy=[{"kind": "assertion", "name": "c",
                               "target": "$.call.response.body.msg",
                               "operator": "eq", "expected": assert_val}])
               for i in range(n_steps)],
    )


# ── Decision 通道 ───────────────────────────────────────────

class TestDecisionChannel:

    def test_handler_returns_decision(self):
        hooks = HookRegistry()
        hooks.register(HookPoint.STEP_BEFORE,
                       lambda p: (Decision(action="skip", source="human")))
        d = ask_decision(hooks, HookPoint.STEP_BEFORE, {})
        assert d.action == "skip" and d.is_human

    def test_abort_decision_carries_note(self):
        """S-3：字符串 STOP 通道退役——拦截者直接返回 abort 决策。"""
        hooks = HookRegistry()
        hooks.register(HookPoint.STEP_BEFORE,
                       lambda p: Decision(action="abort", note="rate limit"))
        d = ask_decision(hooks, HookPoint.STEP_BEFORE, {})
        assert d.action == "abort" and "rate limit" in d.note

    def test_no_interceptor_continues(self):
        assert ask_decision(HookRegistry(), HookPoint.STEP_BEFORE, {}).action == "continue"
        assert ask_decision(None, "STEP_BEFORE", {}).action == "continue"

    def test_point_name_normalization(self):
        hooks = HookRegistry()
        seen = []
        hooks.register(HookPoint.CALL_BEFORE_SEND, lambda p: seen.append(1))
        ask_decision(hooks, "CALL_BEFORE_SEND", {})   # 枚举名
        ask_decision(hooks, "call.before_send", {})   # value
        assert len(seen) == 2


# ── STEP_FAILED：整步重跑 / repaired / skip ─────────────────

class TestStepFailed:

    def test_retry_reruns_whole_step_and_marks_repaired(self):
        calls = {"n": 0}

        def flaky(spec, view):
            calls["n"] += 1
            msg = "ok" if calls["n"] >= 2 else "bad"
            return CallResult.build(protocol="echo", request={}, status=0,
                                    body={"msg": msg})

        engine, hooks, _ = _make_engine(flaky)
        hooks.register(HookPoint.STEP_FAILED, lambda p: Decision(
            action="retry", source="human", note="fix-applied"))

        result = engine.run(_scenario("s"))
        assert result.passed == 1
        assert result.repaired == 1          # 人工修复标记
        assert result.details[0]["steps"][0].get("repaired") is True
        assert calls["n"] == 2               # 整步重跑（第二次 send 成功）

    def test_auto_retry_not_marked_repaired(self):
        calls = {"n": 0}

        def flaky(spec, view):
            calls["n"] += 1
            msg = "ok" if calls["n"] >= 2 else "bad"
            return CallResult.build(protocol="echo", request={}, status=0,
                                    body={"msg": msg})

        engine, hooks, _ = _make_engine(flaky)
        hooks.register(HookPoint.STEP_FAILED, lambda p: Decision(action="retry"))

        result = engine.run(_scenario("s"))
        assert result.passed == 1 and result.repaired == 0   # auto 不标

    def test_skip_continues_remaining_steps(self):
        engine, hooks, _ = _make_engine()   # 全部通过
        skipped = []
        hooks.register(HookPoint.STEP_FAILED, lambda p: (
            skipped.append(p["step_id"]) or Decision(action="skip")))
        # 但没有失败 → 决策点不触发；改用会失败第一步的 send
        def first_bad(spec, view):
            sid = getattr(spec.pctx.call, "message", "?")
            first = sid.endswith("-0")
            return CallResult.build(protocol="echo", request={}, status=0,
                                    body={"msg": "bad" if first else "ok"})

        engine2, hooks2, _ = _make_engine(first_bad)
        hooks2.register(HookPoint.STEP_FAILED, lambda p: Decision(action="skip"))
        result = engine2.run(_scenario("s", n_steps=2))
        assert result.passed == 1           # 第一步 skip，第二步照跑且过
        statuses = [s["status"] for s in result.details[0]["steps"]]
        assert statuses == ["skipped", "passed"]

    def test_continue_keeps_failure(self):
        bad = lambda spec, view: CallResult.build(   # noqa: E731
            protocol="echo", request={}, status=0, body={"msg": "bad"})
        engine, hooks, _ = _make_engine(bad)
        hooks.register(HookPoint.STEP_FAILED, lambda p: None)   # continue
        result = engine.run(_scenario("s"))
        assert result.failed == 1


# ── STEP_BEFORE skip / CALL_BEFORE patch ────────────────────

class TestStepBeforeAndPatch:

    def test_step_before_skip(self):
        engine, hooks, _ = _make_engine()
        hooks.register(HookPoint.STEP_BEFORE, lambda p: Decision(action="skip"))
        result = engine.run(_scenario("s"))
        assert result.details[0]["steps"][0]["status"] == "skipped"
        # 步骤 skip 不算场景失败（未断言失败）
        assert result.passed == 1

    def test_call_before_decision_patch(self):
        from unittest.mock import MagicMock, patch
        engine, hooks, _ = _make_engine()

        from gimbal.schema.call import Call
        from gimbal.schema.request import Request

        hooks.register(HookPoint.CALL_BEFORE_SEND, lambda p: Decision(
            action="continue", source="human",
            patch={"headers": {"X-Debug": "1"}, "body": {"patched": True}}))

        step = Step(call=Call(protocol="http", service="svc", method="POST", path="/p"),
                    request=Request(body={"orig": 1}), strategy=[])
        scenario = Scenario(
            scenarioId="p", meta=Meta(name="p", description="d", module="m",
                                      priority=1, author="a", owner="o", tags=[],
                                      version="1.0",
                                      createTime=datetime.now(timezone.utc),
                                      expire=False, requirementRef=[]),
            config=ScenarioConfig(services={"svc": "https://svc.example"}),
            resource={}, steps=[step],
        )
        from gimbal.statemachine.engine import StepStateMachine

        class _View:
            def __init__(self): self._s = {}
            def read_scratch(self, k, d=None): return self._s.get(k, d)
            def write_scratch(self, k, v): self._s[k] = v

        dispatcher = build_default_dispatcher(hook_registry=hooks)
        sm = StepStateMachine(step_id="step-000", step_schema=step,
                              dispatcher=dispatcher, view=_View(),
                              hook_registry=hooks,
                              services={"svc": "https://svc.example"},
                              protocol_registry=dispatcher.protocols)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"ok": 1}
        mock_resp.headers = {}
        client = MagicMock()
        client.__enter__ = MagicMock(return_value=client)
        client.__exit__ = MagicMock(return_value=False)
        client.request = MagicMock(return_value=mock_resp)
        with patch("httpx.Client", return_value=client):
            sm._do_call()
        kw = client.request.call_args.kwargs
        assert kw["headers"].get("X-Debug") == "1"
        assert kw["json"] == {"patched": True}    # body 被 patch 覆盖


# ── step_from ───────────────────────────────────────────────

class TestStepFrom:

    def test_step_from_skips_earlier_steps(self):
        from gimbal.core.scenario_runner import RuntimeControl
        engine, _, _ = _make_engine()
        rc = RuntimeControl(step_from=1)
        from gimbal.compiler.pipeline import compile_target
        plan = compile_target(_scenario("s", n_steps=3))
        framework_ctx = engine._ictx.ctx_manager.create_framework_context(
            run_id="r-sf", cfg=engine._ictx)
        result = engine._run_plan(plan, framework_ctx, runtime_control=rc)
        # 只跑了 step-001、step-002
        statuses = [s["step_id"] for s in result.details[0]["steps"]]
        assert statuses == ["step-001", "step-002"]


# ── debugger 会话端到端 ─────────────────────────────────────

class TestDebuggerPlugin:

    def test_on_failure_retry_via_scripted_session(self):
        calls = {"n": 0}

        def flaky(spec, view):
            calls["n"] += 1
            msg = "ok" if calls["n"] >= 2 else "bad"
            return CallResult.build(protocol="echo", request={}, status=0,
                                    body={"msg": msg})

        engine, hooks, bus = _make_engine(flaky)
        session = ScriptedSession(["retry"])
        dbg = DebuggerPlugin(pause="on_failure", session=session, event_bus=bus)
        dbg.activate(hooks)
        try:
            result = engine.run(_scenario("s"))
        finally:
            dbg.deactivate(hooks)
        assert result.passed == 1
        assert result.repaired == 1            # debugger 决策 → human → repaired
        assert any("暂停" in line for line in session.log)
        # debug.* 事件已发布
        assert dbg.paused_count == 1

    def test_every_step_pauses_and_continues(self):
        engine, hooks, bus = _make_engine()
        session = ScriptedSession(["continue", "continue"])
        dbg = DebuggerPlugin(pause="every_step", session=session, event_bus=bus)
        dbg.activate(hooks)
        try:
            result = engine.run(_scenario("s", n_steps=2))
        finally:
            dbg.deactivate(hooks)
        assert result.passed == 1
        assert dbg.paused_count == 2           # 每步暂停

    def test_breakpoint_address_call_before(self):
        engine, hooks, bus = _make_engine()
        session = ScriptedSession(["continue"])
        dbg = DebuggerPlugin(pause="none", breakpoints=["step-000:call_before"],
                             session=session, event_bus=bus)
        dbg.activate(hooks)
        try:
            result = engine.run(_scenario("s", n_steps=2))
        finally:
            dbg.deactivate(hooks)
        assert result.passed == 1
        assert dbg.paused_count == 1           # 只在断点处停

    def test_wait_timeout_aborts(self):
        from gimbal.core.debugger import QueueSession
        bad = lambda spec, view: CallResult.build(   # noqa: E731
            protocol="echo", request={}, status=0, body={"msg": "bad"})
        engine, hooks, bus = _make_engine(bad)   # 会失败 → on_failure 暂停
        session = QueueSession(timeout=0.2)
        dbg = DebuggerPlugin(pause="on_failure", session=session,
                             event_bus=bus, wait_timeout=0.2)
        dbg.activate(hooks)
        try:
            result = engine.run(_scenario("s"))
        finally:
            dbg.deactivate(hooks)
        assert result.failed == 1              # 超时按 abort → 失败保留

    def test_abort_pauses_once(self):
        """P1-9：every_step 下 [q] 中止 → 只暂停一次（当前为 2）。

        step.before 发出 abort Decision → step 转 ERROR；abort 语义 =
        run 直接终止，不再触发 step.failed 二次暂停/二次询问。
        """
        engine, hooks, bus = _make_engine()
        session = ScriptedSession(["q"])
        dbg = DebuggerPlugin(pause="every_step", session=session, event_bus=bus)
        dbg.activate(hooks)
        try:
            result = engine.run(_scenario("s"))
        finally:
            dbg.deactivate(hooks)
        assert dbg.paused_count == 1            # 无 step.failed 二次暂停
        assert result.passed == 0 and result.failed == 1
        step = result.details[0]["steps"][0]
        assert "aborted" in (step["error"] or "")   # 状态反映 abort 来源

    def test_abort_continue_control_single_step(self):
        """对照：every_step 下 [c] 继续通过步 → 暂停一次，run 正常通过。"""
        engine, hooks, bus = _make_engine()
        session = ScriptedSession(["c"])
        dbg = DebuggerPlugin(pause="every_step", session=session, event_bus=bus)
        dbg.activate(hooks)
        try:
            result = engine.run(_scenario("s"))
        finally:
            dbg.deactivate(hooks)
        assert dbg.paused_count == 1
        assert result.passed == 1               # 守卫不影响正常流转


# ── P1-10：write/patch 改值命令 + retry 循环 ─────────────────

class TestWritePatchRetry:
    """总案决策 5 的会话命令全集（review P1-10）：

    - write：STEP_BEFORE 暂停时改 scratch 变量 → Decision(continue, write=...)
    - patch：CALL_BEFORE_SEND 暂停时改待发请求 → Decision(continue, patch=...)
    - retry：STEP_FAILED 循环询问——重跑仍失败则再次暂停，直至 continue/skip/abort
    """

    def test_write_changes_variable(self):
        captured: dict = {}

        def capture(spec, view):
            captured.update(view.get_scratch_dict())
            return CallResult.build(protocol="echo", request={}, status=0,
                                    body={"msg": "ok"})

        engine, hooks, bus = _make_engine(capture)
        session = ScriptedSession(['write orderId="O-9"'])
        dbg = DebuggerPlugin(pause="every_step", session=session, event_bus=bus)
        dbg.activate(hooks)
        try:
            result = engine.run(_scenario("s"))
        finally:
            dbg.deactivate(hooks)
        assert dbg.paused_count == 1
        assert captured.get("orderId") == "O-9"   # 步骤进行中已见新值
        assert result.passed == 1

    def test_write_bare_token_parses_as_string(self):
        """裸 token（非合法 JSON）按字符串回落：write orderId=O-9 → "O-9"。"""
        captured: dict = {}

        def capture(spec, view):
            captured.update(view.get_scratch_dict())
            return CallResult.build(protocol="echo", request={}, status=0,
                                    body={"msg": "ok"})

        engine, hooks, bus = _make_engine(capture)
        session = ScriptedSession(["write orderId=O-9"])
        dbg = DebuggerPlugin(pause="every_step", session=session, event_bus=bus)
        dbg.activate(hooks)
        try:
            engine.run(_scenario("s"))
        finally:
            dbg.deactivate(hooks)
        assert captured.get("orderId") == "O-9"

    def test_write_parse_error_reprompts(self):
        """缺 '=' 的 write 命令：友好提示后重新等命令，会话不崩。"""
        engine, hooks, bus = _make_engine()
        session = ScriptedSession(["write orderId", "c"])
        dbg = DebuggerPlugin(pause="every_step", session=session, event_bus=bus)
        dbg.activate(hooks)
        try:
            result = engine.run(_scenario("s"))
        finally:
            dbg.deactivate(hooks)
        assert result.passed == 1                  # 会话存活，继续执行
        assert any("用法" in line for line in session.log)

    def test_patch_changes_request(self):
        sent: dict = {}

        class BodyEcho(ProgEcho):
            """spec 预置 body：验证 JSONPath 补丁原位改写、不伤兄弟键。"""

            def build_spec(self, call, pctx):
                spec = EchoSpec(pctx=pctx)
                spec.body = {"qty": 1, "other": "x"}
                return spec

        def capture(spec, view):
            body = getattr(spec, "body", None)
            if isinstance(body, dict):
                sent.update(body)
            return CallResult.build(protocol="echo", request={}, status=0,
                                    body={"msg": "ok"})

        engine, hooks, bus = _make_engine(executor=BodyEcho(capture))
        session = ScriptedSession(["patch $.request.body.qty=5"])
        dbg = DebuggerPlugin(pause="none", breakpoints=["step-000:call_before"],
                             session=session, event_bus=bus)
        dbg.activate(hooks)
        try:
            result = engine.run(_scenario("s"))
        finally:
            dbg.deactivate(hooks)
        assert dbg.paused_count == 1
        # 适配器发送前已改写请求视图：qty 改为 5，兄弟键保留
        assert sent == {"qty": 5, "other": "x"}
        assert result.passed == 1

    def test_retry_loops_until_skip(self):
        """重跑仍失败 → 再次暂停；直至 skip（此前 retry 只重跑一次）。"""
        calls = {"n": 0}

        def always_bad(spec, view):
            calls["n"] += 1
            return CallResult.build(protocol="echo", request={}, status=0,
                                    body={"msg": "bad"})

        engine, hooks, bus = _make_engine(always_bad)
        session = ScriptedSession(["retry", "retry", "skip"])
        dbg = DebuggerPlugin(pause="on_failure", session=session, event_bus=bus)
        dbg.activate(hooks)
        try:
            result = engine.run(_scenario("s"))
        finally:
            dbg.deactivate(hooks)
        # 失败→retry→再失败→retry→再失败→skip：三次暂停
        assert dbg.paused_count == 3
        assert calls["n"] == 3                      # 初次 + 两次整步重跑
        statuses = [s["status"] for s in result.details[0]["steps"]]
        assert statuses == ["skipped"]              # 最终按 skip 落账
