"""P1-01 执行上下文标签：设置/恢复/边界清空/线程隔离。

验收（Goals P1-01）：并行度 3、repeat 2 的运行中，每个 step 执行时读到的
标签与所属单元和尝试一致。
"""
import os
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

import pytest

from gimbal.log.exec_context import (
    EXEC_LABEL_NAMES, exec_context, exec_labels, bind_exec_context,
)
from gimbal.schema.plan import Plan, PlanPolicy, Unit
from gimbal.scheduler.plan import PlanScheduler


class TestExecContextBasics:

    def test_set_and_restore(self):
        assert exec_labels() == {}
        with exec_context(run="r1", unit="u1"):
            assert exec_labels() == {"run": "r1", "unit": "u1"}
        assert exec_labels() == {}

    def test_nested_merge_and_restore(self):
        with exec_context(run="r1"):
            with exec_context(unit="u1"):
                assert exec_labels() == {"run": "r1", "unit": "u1"}
            assert exec_labels() == {"run": "r1"}
        assert exec_labels() == {}

    def test_inner_overrides_outer(self):
        with exec_context(unit="outer"):
            with exec_context(unit="inner"):
                assert exec_labels()["unit"] == "inner"
            assert exec_labels()["unit"] == "outer"

    def test_unknown_label_rejected(self):
        with pytest.raises(KeyError):
            with exec_context(nope="x"):
                pass

    def test_bind_form_undo(self):
        undo = bind_exec_context({"run": "r1"})
        assert exec_labels()["run"] == "r1"
        undo()
        assert "run" not in exec_labels()

    def test_all_label_names_settable(self):
        with exec_context(**{name: "v" for name in EXEC_LABEL_NAMES}):
            assert set(exec_labels()) == set(EXEC_LABEL_NAMES)


class TestBoundaryClearing:
    """进入边界时清空更深层标签（防线程复用串标签）。"""

    def test_unit_boundary_clears_deeper(self):
        with exec_context(scenario="stale", step="stale-step", protocol="stale-p"):
            with exec_context(unit="u1", _boundary="unit"):
                labels = exec_labels()
                assert labels["unit"] == "u1"
                assert "scenario" not in labels
                assert "step" not in labels
                assert "protocol" not in labels

    def test_scenario_boundary_clears_step_not_unit(self):
        with exec_context(step="stale", run="r", unit="u"):
            with exec_context(scenario="s1", _boundary="scenario"):
                labels = exec_labels()
                assert labels["scenario"] == "s1"
                assert labels["run"] == "r" and labels["unit"] == "u"
                assert "step" not in labels

    def test_exit_restores_cleared(self):
        with exec_context(step="old"):
            with exec_context(unit="u", _boundary="unit"):
                pass
            assert exec_labels().get("step") == "old"


def _unit(uid: str, *, n_runs: int = 1, retry: int = 0, timeout: float | None = None) -> Unit:
    """最小 Unit（真实空场景 + 指定乘法策略；调度器不解读步骤内容）。"""
    from datetime import datetime, timezone
    from gimbal.schema.plan import UnitPolicy
    from gimbal.schema.scenario import Config as SC, Meta, Scenario
    from gimbal.schema.step import Step
    from gimbal.schema.call import Call
    sc = Scenario(
        scenarioId=uid,
        meta=Meta(name=uid, description="d", module="m", priority=1, author="a",
                  owner="o", tags=[], version="1",
                  createTime=datetime.now(timezone.utc), expire=False,
                  requirementRef=[]),
        config=SC(), resource={},
        steps=[Step(call=Call(protocol="echo", message=uid), strategy=[])],
    )
    return Unit(id=uid, scenario=sc,
                policy=UnitPolicy(n_runs=n_runs, retry=retry, timeout=timeout))


class _Passed:
    passed = True


class TestSchedulerLabels:
    """调度器乘法核的标签：unit 在线程内隔离、attempt 按 n_runs/attempt 编号。"""

    def test_parallel_units_isolated_labels(self):
        """并行 3 单元：各线程读到的 unit 标签恒等于自己（无串扰）。"""
        units = [_unit(f"u{i}") for i in range(3)]
        plan = Plan(suite_id="s", mode="aggregate", units=units,
                    policy=PlanPolicy(parallel=3))
        seen: list[tuple[str, dict]] = []
        lock = threading.Lock()

        def run_unit(unit, inputs):
            # 模拟 Engine._run_unit 的 run 标签补全（unit 边界由调度器
            # _run_one 设置并清空更深层标签）
            with exec_context(run="r-test"):
                # 拉长执行窗口，制造并行重叠；期间反复自检标签稳定
                for _ in range(20):
                    labels = exec_labels()
                    assert labels.get("unit") == unit.id, (unit.id, labels)
                    time.sleep(0.001)
                with lock:
                    seen.append((unit.id, dict(labels)))
                return _Passed()

        PlanScheduler().run(plan, run_unit)
        assert sorted(u for u, _ in seen) == ["u0", "u1", "u2"]
        # 单元边界清空了更深层标签（scenario 等不存在）
        for _, labels in seen:
            assert "scenario" not in labels and "step" not in labels

    def test_attempt_label_n_runs_and_retry(self):
        """n_runs=2 + retry=1（首跑必败一次）：attempt 标签序 = 1.1, 1.2, 2.1。"""
        calls: list[tuple[str, str]] = []

        unit = _unit("flaky", n_runs=2, retry=1)
        plan = Plan(suite_id="s", mode="aggregate", units=[unit],
                    policy=PlanPolicy(parallel=1))

        state = {"count": 0}

        class Result:
            def __init__(self, passed):
                self.passed = passed

        def run_unit(u, inputs):
            with exec_context(run="r-test"):
                state["count"] += 1
                # 第 1 次 attempt 失败 → 重试；第 2 次起通过；第 1 个 run 后即过
                calls.append((u.id, exec_labels().get("attempt", "")))
                return Result(passed=state["count"] >= 2)

        PlanScheduler().run(plan, run_unit)
        assert calls == [("flaky", "1.1"), ("flaky", "1.2"), ("flaky", "2.1")]

    def test_timeout_attempt_propagates_labels(self):
        """policy.timeout 路径：attempt 池线程内标签完整（copy_context 传播）。"""
        seen: dict[str, str] = {}

        class _Slow:
            passed = True

        def run_unit(u, inputs, cancel=None):
            with exec_context(run="r-test"):
                seen.update(exec_labels())
                time.sleep(0.2)   # 超过 timeout，触发弃跑路径
                return _Slow()

        unit = _unit("slow", timeout=0.05)
        plan = Plan(suite_id="s", mode="aggregate", units=[unit],
                    policy=PlanPolicy(parallel=1))
        PlanScheduler().run(plan, run_unit)
        # 执行发生在 attempt 线程：标签经 copy_context 传播到位
        assert seen.get("run") == "r-test"
        assert seen.get("unit") == "slow"
        assert seen.get("attempt") == "1.1"
