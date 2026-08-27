"""Unit tests for phase5 step-control minimal subset.

测试覆盖:
  [1] RuntimeControl 默认构造与字段
  [2] ScenarioRunResult 新增 halted / halt_reason 字段
  [3] RunResult 新增 halted 字段 (整型聚合)
  [4] Engine.run 接收并透传 runtime_control
  [5] ScenarioRunner.run 在 halt_at 触发时:
      - 立即停止 for 循环
      - status = "halted"
      - halted = True
      - halt_reason 已填充
      - step_results 末尾追加 __scenario_halted__ 标记 step
      - 已执行 step 不被破坏
  [6] RuntimeControl.halt_at=None 时不触发 halt
  [7] halt_at 越过所有 step 时全程跑完（不触发 halt）
"""
import pytest

from gimbal.core.runner import RunResult


# [1]
def test_runtime_control_default_construction():
    """默认构造：halt_at=None，halt_reason 是默认值（可读即可，不强制固定）。"""
    from gimbal.core.scenario_runner import RuntimeControl

    rc = RuntimeControl()
    assert rc.halt_at is None
    assert rc.halt_reason == "user-requested"


def test_runtime_control_explicit_construction():
    """显式构造：字段透传，无校验。"""
    from gimbal.core.scenario_runner import RuntimeControl

    rc = RuntimeControl(halt_at=5, halt_reason="custom-reason")
    assert rc.halt_at == 5
    assert rc.halt_reason == "custom-reason"


def test_runtime_control_allows_halt_at_zero():
    """halt_at=0 是合法值（"执行到第 0 个 step 后停止"，等同于"不跑任何 step"）。"""
    from gimbal.core.scenario_runner import RuntimeControl

    rc = RuntimeControl(halt_at=0)
    assert rc.halt_at == 0


# [2]
def test_scenario_run_result_has_halted_field():
    """ScenarioRunResult 新增 halted/halt_reason 字段，默认 False/None。"""
    from gimbal.core.scenario_runner import ScenarioRunResult

    r = ScenarioRunResult(scenario_id="s1", status="passed")
    assert r.halted is False
    assert r.halt_reason is None


# [3]
def test_run_result_has_halted_field():
    """RunResult 新增 halted 字段，默认 0（聚合用）。"""
    r = RunResult()
    assert r.halted == 0


# [4] / [5] — 真实走 ScenarioRunner
@pytest.fixture
def fake_dispatcher_and_ctx_factory():
    """构造一组能跑通的 fake dispatcher / ctx_manager / suite_ctx。

    我们的目标不是测 step 执行的细节（已经有 plate 测试覆盖），
    而是验证：halt_at 触发后，
      - status == "halted" 且 passed == False
      - halted 标记正确
      - 未执行 step 不出现在 step_results 中
      - 已执行 step 仍然保留

    因此 fake StepRunner 跑第 1..N-1 个时返回 passed 假结果，
    跑到第 N 个（halt_at 位置）时不应进入（已 break）。
    """
    from gimbal.core.scenario_runner import (
        RuntimeControl, ScenarioRunner, ScenarioRunResult, StepRunResult,
    )
    from gimbal.statemachine.engine import StepRunResult as SmStepRunResult

    class FakeStep:
        def __init__(self, idx: int, api: object = None):
            self.api = api if api is not None else object()
            self.idx = idx
            self.request = type("R", (), {"body": {}})()
            self.strategy: list = []

    class FakeStepRunner:
        """被 ScenarioRunner 替换的最简化 StepRunner，绕过 StepStateMachine。

        接受 ScenarioRunner 传入的所有 kwargs（dispatcher / ctx_manager / service_base_url / ...），
        但只记录被请求执行的 step index。
        """
        def __init__(self, **kwargs):
            self.executed_indexes: list[int] = []
            self.kwargs = kwargs

        def run(self, step_schema, scenario_ctx, step_index):
            self.executed_indexes.append(step_index)
            return SmStepRunResult(
                step_id=f"step-{step_index:03d}",
                status="passed",
                duration_ms=1.0,
            )

    class FakeDispatcher:
        pass

    class FakeCtxManager:
        def derive_scenario_context(self, suite_ctx, scenario_id, scenario_name, description):
            class _Ctx:
                pass
            ctx = _Ctx()
            ctx.scenario_id = scenario_id
            ctx.config = suite_ctx.config
            ctx._timeout_seconds = None
            return ctx

        def finalize_scenario(self, ctx, status):
            pass

    class FakeSuiteCtx:
        def __init__(self):
            class _Cfg:
                def __init__(self):
                    self.scenario_timeout = None
            self.config = _Cfg()

    class FakePreprocessor:
        """绕过真实 preprocessor，直接返回传入的 steps。"""
        def __init__(self, scenario_schema, **kwargs):
            self._steps = scenario_schema.steps

        def run(self):
            return (self._steps, "http://fake")

    fake_steps = []
    for i in range(5):
        fake_steps.append(FakeStep(idx=i))

    class FakeScenario:
        def __init__(self):
            self.scenarioId = "test-scenario"
            self.steps = fake_steps
            self.meta = type("M", (), {"name": "fake", "description": "", "model_dump": staticmethod(lambda mode="json": {})})()

    return {
        "ScenarioRunner": ScenarioRunner,
        "FakeStepRunner": FakeStepRunner,
        "FakeDispatcher": FakeDispatcher,
        "FakeCtxManager": FakeCtxManager,
        "FakeSuiteCtx": FakeSuiteCtx,
        "FakePreprocessor": FakePreprocessor,
        "FakeScenario": FakeScenario,
        "sm_result": SmStepRunResult,
    }


def test_runtime_control_halt_at_triggers_halt(fake_dispatcher_and_ctx_factory):
    """halt_at=2 时，跑到 idx=2 停止：已跑 idx=0,1 共 2 个 step。"""
    F = fake_dispatcher_and_ctx_factory

    # 替换 ScenarioPreprocessor 为 fake
    import gimbal.core.scenario_runner as sr_module
    original_pp = sr_module.ScenarioPreprocessor if hasattr(sr_module, "ScenarioPreprocessor") else None

    # 若 scenario_runner 没有 import 过的 ScenarioPreprocessor，需要手工 mock
    # scenario_runner 在 run() 内部 import 它，看代码：
    #   from gimbal.preprocessor.scenario_preprocessor import ScenarioPreprocessor
    # 我们直接在 import system 上动
    class _CatchedPreprocessor(F["FakePreprocessor"]):
        pass

    import sys, types
    fake_pre_mod = types.ModuleType("gimbal.preprocessor.scenario_preprocessor")
    fake_pre_mod.ScenarioPreprocessor = _CatchedPreprocessor
    sys.modules["gimbal.preprocessor.scenario_preprocessor"] = fake_pre_mod

    # 替换 StepRunner 为 fake
    sr_module.StepRunner = F["FakeStepRunner"]

    try:
        runner = sr_module.ScenarioRunner(
            dispatcher=F["FakeDispatcher"](),
            ctx_manager=F["FakeCtxManager"](),
            hook_registry=None,
            event_bus=None,
            auth_registry=None,
            asset_store=None,
        )
        sc = F["FakeScenario"]()
        suite_ctx = F["FakeSuiteCtx"]()

        runtime_control = F["ScenarioRunner"].__module__ and (
            __import__("gimbal.core.scenario_runner", fromlist=["RuntimeControl"]).RuntimeControl(
                halt_at=2,
                halt_reason="test-halt",
            )
        )

        # 注意：ScenarioRunner().run() 内部用的是它自己的 namespace 里的 StepRunner
        # 我替换 sr_module.StepRunner 已经达到了 patch 作用

        result = runner.run(sc, suite_ctx, runtime_control=runtime_control)

        assert result.status == "halted"
        assert result.halted is True
        assert result.halt_reason == "test-halt"
        assert result.passed is False
        # 真实 step（idx=0,1）被保留，idx=2..4 没跑
        # step_results 应包含 2 个真实 step + 1 个 marker
        assert len(result.step_results) == 3, (
            f"expected 3 (2 real + 1 marker), got {len(result.step_results)}: "
            f"{[s.step_id for s in result.step_results]}"
        )
        assert result.step_results[0].step_id == "step-000"
        assert result.step_results[1].step_id == "step-001"
        # marker
        marker = result.step_results[2]
        assert marker.step_id == "__scenario_halted__"
        assert marker.status == "halted"
        assert marker.error_phase == "halted"
        assert "test-halt" in (marker.error or "")

        # 已执行 step 不被破坏：idx=0,1 的真实 step 出现在 step_results 前两位
        # 后续 idx=2,3,4 不应出现（被 halt 阻止）
        assert "step-002" not in [s.step_id for s in result.step_results], (
            "halt 后不应出现 step-002（idx=2 是 halt_at=2 处）"
        )
        assert "step-003" not in [s.step_id for s in result.step_results]
        assert "step-004" not in [s.step_id for s in result.step_results]
        # 已跑两步：idx=0 (step-000) 和 idx=1 (step-001)
        real_steps = [s for s in result.step_results if not s.step_id.startswith("__scenario_")]
        assert len(real_steps) == 2
        assert [s.step_id for s in real_steps] == ["step-000", "step-001"]
    finally:
        sys.modules.pop("gimbal.preprocessor.scenario_preprocessor", None)
        # 恢复 StepRunner 不必要（test process 不复用）


def test_runtime_control_none_halt_at_skips_halt(fake_dispatcher_and_ctx_factory):
    """runtime_control 为 None 或 halt_at=None 时，正常跑完全部 step。"""
    F = fake_dispatcher_and_ctx_factory

    import sys, types
    fake_pre_mod = types.ModuleType("gimbal.preprocessor.scenario_preprocessor")
    fake_pre_mod.ScenarioPreprocessor = F["FakePreprocessor"]
    sys.modules["gimbal.preprocessor.scenario_preprocessor"] = fake_pre_mod

    import gimbal.core.scenario_runner as sr_module
    sr_module.StepRunner = F["FakeStepRunner"]

    try:
        runner = sr_module.ScenarioRunner(
            dispatcher=F["FakeDispatcher"](),
            ctx_manager=F["FakeCtxManager"](),
            hook_registry=None,
            event_bus=None,
            auth_registry=None,
            asset_store=None,
        )
        sc = F["FakeScenario"]()
        suite_ctx = F["FakeSuiteCtx"]()

        # 不传 runtime_control
        result = runner.run(sc, suite_ctx)
        assert result.status == "passed"
        assert result.halted is False
        assert result.halt_reason is None
        assert len(result.step_results) == 5

        # 传 None halt_at
        runtime_control = F["FakeScenario"].__module__ and (
            __import__("gimbal.core.scenario_runner", fromlist=["RuntimeControl"]).RuntimeControl(halt_at=None)
        )
        result2 = runner.run(sc, suite_ctx, runtime_control=runtime_control)
        assert result2.status == "passed"
        assert result2.halted is False
    finally:
        sys.modules.pop("gimbal.preprocessor.scenario_preprocessor", None)


def test_runtime_control_halt_at_beyond_step_count_does_not_trigger(fake_dispatcher_and_ctx_factory):
    """halt_at 超过 step 总数时不应触发 halt，正常跑完。"""
    F = fake_dispatcher_and_ctx_factory

    import sys, types
    fake_pre_mod = types.ModuleType("gimbal.preprocessor.scenario_preprocessor")
    fake_pre_mod.ScenarioPreprocessor = F["FakePreprocessor"]
    sys.modules["gimbal.preprocessor.scenario_preprocessor"] = fake_pre_mod

    import gimbal.core.scenario_runner as sr_module
    sr_module.StepRunner = F["FakeStepRunner"]

    try:
        runner = sr_module.ScenarioRunner(
            dispatcher=F["FakeDispatcher"](),
            ctx_manager=F["FakeCtxManager"](),
            hook_registry=None,
            event_bus=None,
            auth_registry=None,
            asset_store=None,
        )
        sc = F["FakeScenario"]()
        suite_ctx = F["FakeSuiteCtx"]()
        # 5 个 step，halt_at=100 永不触发
        runtime_control = __import__(
            "gimbal.core.scenario_runner", fromlist=["RuntimeControl"]
        ).RuntimeControl(halt_at=100, halt_reason="never-triggered")

        result = runner.run(sc, suite_ctx, runtime_control=runtime_control)
        assert result.status == "passed"
        assert result.halted is False
        assert len(result.step_results) == 5
    finally:
        sys.modules.pop("gimbal.preprocessor.scenario_preprocessor", None)
