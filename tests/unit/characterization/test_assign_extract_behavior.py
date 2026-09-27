"""批次 F 前置：特征化测试（安全绳）。

目的：把**现行行为**钉死成可执行断言——批次 F 的兼容回收（删 api 糖/
旧 scratch 键/HTTP 钩子/插件改造）之后，这些用例经迁移脚本转换必须得到
一致结果。覆盖总案 6.1 开工门槛要求的四条 + 事件形状 + 插件引擎级端到端：

  1. assign 取值流（source 三形态 × scope × config.vars/CLI 覆盖）
  2. extract promote（STEP/SCENARIO/SESSION × default/required）
  3. halt_at / per-step 路由（已有 pytest 化用例，见 runtime_control/engine 目录）
  4. 认证注入原生契约（F-2b：auth_headers/response_body_extract 插件退役；
     collector / test_report 由事件形状用例间接钉住其消费面）
"""
import dataclasses
import json
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
from gimbal.core.runner import Engine
from gimbal.events.bus import InMemoryEventBus
from gimbal.plugins import PluginRegistry
from gimbal.protocols.base import ProtocolCallContext, ProtocolExecutor
from gimbal.protocols.result import CallResult
from gimbal.schema.call import Call
from gimbal.schema.scenario import Config as ScenarioConfig, Meta, Scenario
from gimbal.schema.step import Step
from gimbal.strategy.dispatcher import build_default_dispatcher


# ── 引擎脚手架（echo 协议：message 原样回写）─────────────────

@dataclass
class EchoSpec:
    kind: str = "_call:echo"
    name: Optional[str] = "echo_call"
    phase: Optional[str] = None
    order: int = 0
    enabled: bool = True
    onFailure: str = "abort"
    tags: list = dataclasses.field(default_factory=list)
    pctx: Optional[ProtocolCallContext] = None


class EchoExecutor(ProtocolExecutor):
    protocol = "echo"

    def build_spec(self, call, pctx):
        return EchoSpec(pctx=pctx)

    def send(self, spec, view):
        return CallResult.build(
            protocol="echo", request={"message": getattr(spec.pctx.call, "message", "")},
            status=0, body={"msg": getattr(spec.pctx.call, "message", "")})


def make_engine(*, cli_vars=None, scenario_vars=None):
    bus = InMemoryEventBus()
    archive = InMemoryArchive()
    hooks = HookRegistry()
    dispatcher = build_default_dispatcher(hook_registry=hooks)
    dispatcher.protocols.register(EchoExecutor())
    ctx_manager = ContextManager(archive=archive, event_bus=bus)
    cfg = BootstrapConfig(env="test", mode="local", log_level="error",
                          vars=cli_vars or {})
    conf = Configuration(
        cfg=cfg, auth_registry=AuthRegistry(), ctx_manager=ctx_manager,
        dispatcher=dispatcher, event_bus=bus, archive=archive,
        hook_registry=hooks, plugin_registry=PluginRegistry(), plugins=(),
        reporter_runtime=None, protocols=dispatcher.protocols,
    )
    return Engine(conf), bus, archive, hooks, dispatcher


def make_scenario(sid, steps, vars=None) -> Scenario:
    return Scenario(
        scenarioId=sid,
        meta=Meta(name=sid, description="d", module="m", priority=1, author="a",
                  owner="o", tags=[], version="1.0",
                  createTime=datetime.now(timezone.utc), expire=False,
                  requirementRef=[]),
        config=ScenarioConfig(vars=vars or {}),
        resource={},
        steps=steps,
    )


def echo_step(message, strategy=None):
    return Step(call=Call(protocol="echo", message=message),
                strategy=strategy or [])


def run_steps(sid, steps, **kw):
    engine, *_ = make_engine(**kw)
    return engine.run(make_scenario(sid, steps, vars=kw.get("scenario_vars")))


# ══ 1. assign 取值流 ════════════════════════════════════════
#
# 现行语义（特征化事实，勿凭直觉改用例）：
#   - assign 默认 phase=BEFORE_REQUEST，在协议调用**前**执行 —— 读不到响应数据；
#   - assign 的写入是 **step 局部 scratch**（步末清空，跨步不可见）；
#   - 跨步变量传递唯一通道：extract scope=SCENARIO 提升（channels）→
#     下一步 assign `$.x` STEP 作用域回退读取 / 断言裸键回退；
#   - 同一步内 assign（BEFORE_REQUEST）写、assertion（VERIFYING）读共享 scratch。

class TestAssignValueFlow:
    """钉死 assign 的现行取值通道（迁移脚本改写路径后行为必须一致）。"""

    def test_literal_source_visible_within_same_step(self):
        steps = [Step(call=Call(protocol="echo", message="m"), strategy=[
            {"kind": "assign", "name": "a", "source": "hello", "target": "plain_key"},
            {"kind": "assertion", "name": "c", "target": "$.plain_key",
             "operator": "eq", "expected": "hello"},
        ])]
        assert run_steps("assign-lit", steps).passed == 1

    def test_jsonpath_target_nested_write(self):
        steps = [Step(call=Call(protocol="echo", message="m"), strategy=[
            {"kind": "assign", "name": "a", "source": "v1", "target": "$.order.meta"},
            {"kind": "assertion", "name": "c", "target": "$.order.meta",
             "operator": "eq", "expected": "v1"},
        ])]
        assert run_steps("assign-nested", steps).passed == 1

    def test_assign_runs_before_call_cannot_read_response(self):
        """assign 在调用前执行：读 $.response_body.* 必 miss（回退 SCENARIO 层也是
        None）——default 兜底是现行模式。"""
        steps = [Step(call=Call(protocol="echo", message="m"), strategy=[
            {"kind": "assign", "name": "a", "source": "$.response_body.msg",
                     "target": "got", "default": "not-yet", "required": False},
            {"kind": "assertion", "name": "c", "target": "$.got",
             "operator": "eq", "expected": "not-yet"},
        ])]
        assert run_steps("assign-precall", steps).passed == 1

    def test_assign_writes_request_body_visible_same_step(self):
        """B2.1 契约（step 内可见性面）：assign 写 scratch.request_body。"""
        steps = [Step(call=Call(protocol="echo", message="m"), strategy=[
            {"kind": "assign", "name": "a", "source": "B", "target": "request_body"},
            {"kind": "assertion", "name": "c", "target": "$.request_body",
             "operator": "eq", "expected": "B"},
        ])]
        assert run_steps("assign-reqbody", steps).passed == 1

    def test_var_template_resolved_from_config_vars(self):
        steps = [Step(call=Call(protocol="echo", message="m"), strategy=[
            {"kind": "assign", "name": "a", "source": "${var.who}", "target": "who"},
            {"kind": "assertion", "name": "c", "target": "$.who",
             "operator": "eq", "expected": "alice"},
        ])]
        result = run_steps("assign-var", steps, scenario_vars={"who": "alice"})
        assert result.passed == 1, result.details

    def test_cli_vars_override_scenario_vars(self):
        """CLI vars 赢（BootstrapConfig.vars 覆盖 scenario.config.vars）。"""
        steps = [Step(call=Call(protocol="echo", message="m"), strategy=[
            {"kind": "assign", "name": "a", "source": "${var.who}", "target": "who"},
            {"kind": "assertion", "name": "c", "target": "$.who",
             "operator": "eq", "expected": "cli-wins"},
        ])]
        result = run_steps("assign-cli", steps,
                           scenario_vars={"who": "alice"}, cli_vars={"who": "cli-wins"})
        assert result.passed == 1, result.details

    def test_step_scope_fallback_to_scenario_layer(self):
        """STEP 作用域 $.x 先查 scratch，miss 后回退 SCENARIO 层（extract 提升值）。"""
        steps = [
            echo_step("TOK", [
                {"kind": "extract", "name": "e", "expression": "$.call.response.body.msg",
                 "target": "shared_tok", "scope": "scenario"},
            ]),
            Step(call=Call(protocol="echo", message="m"), strategy=[
                {"kind": "assign", "name": "a", "source": "$.shared_tok",
                 "target": "local"},
                {"kind": "assertion", "name": "c", "target": "$.local",
                 "operator": "eq", "expected": "TOK"},
            ]),
        ]
        assert run_steps("assign-fallback", steps).passed == 1

    def test_default_when_source_missing(self):
        steps = [Step(call=Call(protocol="echo", message="m"), strategy=[
            {"kind": "assign", "name": "a", "source": "$.no_such_key",
                     "target": "d", "default": "fallback", "required": False},
            {"kind": "assertion", "name": "c", "target": "$.d",
             "operator": "eq", "expected": "fallback"},
        ])]
        assert run_steps("assign-default", steps).passed == 1

    def test_required_missing_fails_step(self):
        steps = [echo_step("m", [
            {"kind": "assign", "name": "a", "source": "$.no_such_key",
                     "target": "d", "required": True},
        ])]
        result = run_steps("assign-required", steps)
        assert result.failed == 1


# ══ 2. extract promote ══════════════════════════════════════

class TestExtractPromote:

    def test_step_scope_writes_scratch_same_step(self):
        """STEP 作用域 = 步内 scratch（同一步 VERIFYING 可见）。"""
        steps = [Step(call=Call(protocol="echo", message="V"), strategy=[
            {"kind": "extract", "name": "e", "expression": "$.call.response.body.msg",
             "target": "tmp", "scope": "step"},
            {"kind": "assertion", "name": "c", "target": "$.tmp",
             "operator": "eq", "expected": "V"},
        ])]
        assert run_steps("extract-step", steps).passed == 1

    def test_step_scope_not_visible_next_step(self):
        """步末 scratch 清空：下一步读不到上一步 STEP 作用域写入（现行事实）。"""
        steps = [
            Step(call=Call(protocol="echo", message="V"), strategy=[
                {"kind": "extract", "name": "e", "expression": "$.call.response.body.msg",
                 "target": "tmp", "scope": "step"},
            ]),
            Step(call=Call(protocol="echo", message="m"), strategy=[
                {"kind": "assertion", "name": "c", "target": "$.tmp",
                 "operator": "eq", "expected": "V"},
            ]),
        ]
        assert run_steps("extract-step-cross", steps).failed == 1

    def test_scenario_scope_promotes_and_cross_step_visible(self):
        steps = [
            echo_step("CROSS", [
                {"kind": "extract", "name": "e", "expression": "$.call.response.body.msg",
                 "target": "cross_var", "scope": "scenario"},
            ]),
            Step(call=Call(protocol="echo", message="m"), strategy=[
                {"kind": "assign", "name": "a", "source": "$.cross_var",
                         "target": "seen"},
                {"kind": "assertion", "name": "c", "target": "$.seen",
                 "operator": "eq", "expected": "CROSS"},
            ]),
        ]
        assert run_steps("extract-scenario", steps).passed == 1

    def test_plain_key_assertion_falls_back_to_scenario_layer(self):
        """断言裸键：scratch miss 后回退 SCENARIO 层（extract 提升值直读）。"""
        steps = [
            echo_step("PV", [
                {"kind": "extract", "name": "e", "expression": "$.call.response.body.msg",
                 "target": "promoted", "scope": "scenario"},
            ]),
            Step(call=Call(protocol="echo", message="m"), strategy=[
                {"kind": "assertion", "name": "c", "target": "promoted",
                 "operator": "eq", "expected": "PV"},
            ]),
        ]
        assert run_steps("extract-plainkey", steps).passed == 1

    def test_old_paths_removed_in_f(self):
        """v2.1 批次 F 定稿：旧路径 $.response_body.* 已随旧 scratch 键退役。

        这是特征化用例的**显式翻转**（删除前的行为由 git 历史与
        scripts/migrate_legacy_case.py 的存在证明）。旧路径现返回 miss：
        extract miss + required → FAILED；断言 miss → 不等 → FAILED。
        存量用例一律经迁移脚本转 $.call.response.body.*。
        """
        steps = [Step(call=Call(protocol="echo", message="OLD"), strategy=[
            {"kind": "extract", "name": "e", "expression": "$.response_body.msg",
             "target": "got", "scope": "step", "required": True},
        ])]
        assert run_steps("extract-old-path-removed", steps).failed == 1

        steps2 = [Step(call=Call(protocol="echo", message="OLD2"), strategy=[
            {"kind": "assertion", "name": "c", "target": "$.response_body.msg",
             "operator": "eq", "expected": "OLD2"},
        ])]
        assert run_steps("assert-old-path-removed", steps2).failed == 1

    def test_default_value_on_miss(self):
        steps = [Step(call=Call(protocol="echo", message="m"), strategy=[
            {"kind": "extract", "name": "e", "expression": "$.call.response.body.absent",
                     "target": "dv", "default": "D", "required": False},
            {"kind": "assertion", "name": "c", "target": "$.dv",
             "operator": "eq", "expected": "D"},
        ])]
        assert run_steps("extract-default", steps).passed == 1

    def test_required_miss_fails_step(self):
        steps = [echo_step("m", [
            {"kind": "extract", "name": "e", "expression": "$.call.response.body.absent",
                     "target": "x", "required": True},
        ])]
        assert run_steps("extract-required", steps).failed == 1

    def test_session_scope_current_behavior(self):
        """钉死 SESSION（≈SUITE）作用域的现行行为：suite policy require_reason=True，
        extract promote 不带 reason → PromotionRejected → 策略 ERROR → 步骤失败。
        （批次 F 若改变此行为，本用例必须显式更新而非静默通过。）
        """
        steps = [echo_step("m", [
            {"kind": "extract", "name": "e", "expression": "$.call.response.body.msg",
                     "target": "sv", "scope": "session"},
        ])]
        result = run_steps("extract-session", steps)
        assert result.failed == 1, (
            "现行行为：SESSION 作用域 promote 因 suite policy require_reason 被拒；"
            "若此断言失败说明行为已变，请更新本特征化用例并评估批次 F 影响"
        )
