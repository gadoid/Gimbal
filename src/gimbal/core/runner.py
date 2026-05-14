"""core/runner.py

职责分离：

    initial_ctx = bootstrap(cli_ctx)      # 配置合并 + 基础设施初始化
    engine      = Engine(initial_ctx)     # 持有初始化上下文，等待执行请求
    result      = engine.run(scenario)    # 此时才创建 framework/suite 层级 context

bootstrap：
    - 调用 ConfigLoader 完成多来源配置合并 → FrameworkConfig
    - 配置日志系统
    - 初始化基础设施（EventBus / Archive / ContextManager / Dispatcher）
    - 产出 Configuration（不可变，安全传递）

Engine.run()：
    - 接收 Scenario 或 Suite 数据对象
    - 用 Configuration 中的 ctx_manager 创建本次执行的层级 context
        （FrameworkContext → SuiteContext，生命周期属于"一次执行"）
    - 分发到 ScenarioRunner 执行
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from gimbal.cli.context import CLIContext
from gimbal.config.loader import ConfigLoader, FrameworkConfig
from gimbal.schema.scenario import Scenario, Suite

from .boostrap import bootstrap

logger = logging.getLogger(__name__)


# ── RunResult ─────────────────────────────────────────────────────────────────

@dataclass
class RunResult:
    exit_code: int = 0
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    error: int = 0
    details: list[dict[str, Any]] = field(default_factory=list)



# ── Engine ────────────────────────────────────────────────────────────────────

class Engine:
    """执行引擎。

    __init__ 只存引用，不做任何 I/O 或状态初始化。
    所有执行相关的状态都在 run() 内部创建，保证每次 run() 相互独立。
    """

    def __init__(self, initial_ctx: Configuration) -> None:
        self._ictx = initial_ctx

    def run(self, target: Scenario | Suite) -> RunResult:
        """执行入口。

        在此方法内创建本次执行的层级 context：
            1. FrameworkContext  —— 全量配置写入，run_id 在此生成
            2. SuiteContext      —— 单 scenario 执行时用 __default__ 占位
        然后分发到 ScenarioRunner。
        """
        ictx = self._ictx
        cfg = ictx.cfg

        # 1. 创建 FrameworkContext（每次 run 独立的 run_id）
        framework_ctx = ictx.ctx_manager.create_framework_context(
            run_id=str(uuid.uuid4()),
            framework_version=cfg.framework_version,
            environment=cfg.env,
            config={
                "env":             cfg.env,
                "mode":            cfg.mode,
                "log_level":       cfg.log_level,
                "no_color":        cfg.no_color,
                "mongo_uri":       cfg.mongo_uri,
                "minio_endpoint":  cfg.minio_endpoint,
                "plugins":         list(cfg.plugins),
                "reporters":       list(cfg.reporters),
                "report_dir":      cfg.report_dir,
                "fail_fast":       cfg.fail_fast,
                "default_timeout": cfg.default_timeout,
                "default_retry":   cfg.default_retry,
                **cfg.extras,
            },
        )
        logger.info("[Engine] run_id=%s env=%s", framework_ctx.run_id, cfg.env)

        if isinstance(target, Scenario):
            return self._run_scenario(target, framework_ctx, ictx)
        elif isinstance(target, Suite):
            return self._run_suite(target, framework_ctx, ictx)
        else:
            logger.error("[Engine] 收到未展开的 Ref: %s", type(target).__name__)
            return RunResult(exit_code=3, error=1)

    # ── 内部分发 ─────────────────────────────────────────────────────────────

    def _run_scenario(
        self,
        scenario: Scenario,
        framework_ctx: Any,
        ictx: Configuration,
    ) -> RunResult:
        from gimbal.core.scenario_runner import ScenarioRunner
        # 2. 为单 scenario 执行创建默认 SuiteContext
        suite_ctx = ictx.ctx_manager.derive_suite_context(
            framework_ctx,
            suite_id="__default__",
            suite_name="Default Suite",
            tags=[],
            plugins={},
        )
        result = ScenarioRunner(ictx.dispatcher, ictx.ctx_manager).run(
            scenario, suite_ctx
        )
        return RunResult(
            exit_code=0 if result.passed else 1,
            total=1,
            passed=1 if result.passed else 0,
            failed=0 if result.passed else 1,
            details=[{
                "scenario_id": result.scenario_id,
                "status":      result.status,
                "duration_ms": result.duration_ms,
                "steps": [
                    {
                        "step_id":     s.step_id,
                        "status":      s.status,
                        "duration_ms": s.duration_ms,
                    }
                    for s in result.step_results
                ],
            }],
        )

    def _run_suite(
        self,
        suite: Suite,
        framework_ctx: Any,
        ictx: Configuration,
    ) -> RunResult:
        from gimbal.core.scenario_runner import ScenarioRunner

        # 2. Suite 执行时用 Suite 自身信息创建 SuiteContext
        suite_ctx = ictx.ctx_manager.derive_suite_context(
            framework_ctx,
            suite_id=getattr(suite, "suiteId", "__suite__"),
            suite_name=getattr(suite, "name", "Suite"),
            tags=[],
            plugins={},
        )

        runner = ScenarioRunner(ictx.dispatcher, ictx.ctx_manager)
        cfg = ictx.cfg
        total = passed = failed = error = 0
        details: list[dict[str, Any]] = []

        for scenario in suite.suite:
            result = runner.run(scenario, suite_ctx)
            total += 1
            if result.passed:
                passed += 1
            elif result.status == "error":
                error += 1
            else:
                failed += 1
            details.append({
                "scenario_id": result.scenario_id,
                "status":      result.status,
                "duration_ms": result.duration_ms,
            })
            if cfg.fail_fast and not result.passed:
                logger.warning("[Engine] fail_fast：在 %s 后停止", result.scenario_id)
                break

        return RunResult(
            exit_code=0 if (failed + error) == 0 else 1,
            total=total, passed=passed,
            failed=failed, error=error,
            details=details,
        )

