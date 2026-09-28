"""策略分发器（Dispatcher / Registry）。

维护 kind → StrategyExecutor 的映射，对外提供 dispatch() 接口。
框架内置 executor 在模块加载时自动注册；外部插件通过 register() 注入。
"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, Optional

from .executor_base import StrategyExecutor, StrategyResult, StrategyStatus
from gimbal.core.hooks import HookPoint
from gimbal.core.registry import Registry
from gimbal.exceptions import StrategyError
from gimbal.log import get_logger

if TYPE_CHECKING:
    from pydantic import BaseModel
    from gimbal.context.views import StrategyContextView
    from gimbal.schema.strategy import StrategyBase

logger = get_logger(__name__)


class StrategyDispatcher:
    """策略分发器。

    用法::

        dispatcher = StrategyDispatcher()
        dispatcher.register(ExtractExecutor(), params=Extract)
        dispatcher.register(AssignExecutor(), params=Assign)
        dispatcher.register(AssertionExecutor(), params=Assertion)

        result = dispatcher.dispatch(spec, view)

    可选埋点：
        dispatcher = StrategyDispatcher(hook_registry=registry)

    注册面收敛（S-1）：kind 表由泛型 Registry 承载 —— 身份、参数模型、
    describe 导出统一走 core.registry；params_of 供 ext/平台取参数 schema。
    """

    def __init__(self, hook_registry: Optional[Any] = None) -> None:
        """初始化 dispatcher：空 executor 注册表，可选 hook_registry 用于 STRATEGY_BEFORE/AFTER 埋点。"""
        self._table: Registry[StrategyExecutor] = Registry("strategy")
        self._hooks = hook_registry
        # 协议注册表（protocol → executor，与 kind 表联动）；
        # 由 build_default_dispatcher 装配，Engine/ScenarioRunner/状态机经此透传
        self.protocols: Any = None

    def register(
        self,
        executor: StrategyExecutor,
        params: Optional["type[BaseModel]"] = None,
    ) -> None:
        """注册一个 executor，以其 kind 为键。

        params 为该策略的参数模型（ext 导出 / 表单生成用）；缺省时回退读
        executor.params_model 类属性，两者皆无则该条目 params_schema=None。
        """
        if not executor.kind:
            raise StrategyError(f"{type(executor).__name__} must declare a non-empty `kind`")
        resolved = params or getattr(executor, "params_model", None)
        self._table.register(executor.kind, executor, params=resolved)
        logger.debug("[StrategyDispatcher] Executor registered: kind={} executor={} params={}",
                     executor.kind, type(executor).__name__,
                     getattr(resolved, "__name__", None))

    def unregister(self, kind: str) -> bool:
        """按 kind 注销 executor（插件热卸载路径）。返回是否原本存在。"""
        # Registry 表设计为注册期写、运行期读；插件热卸载需要移除，
        # 经内部表操作（同包协作），不外泄到 Registry 公共面。
        with self._table._lock:  # noqa: SLF001
            existed = self._table._items.pop(kind, None) is not None  # noqa: SLF001
        if existed:
            logger.debug("[StrategyDispatcher] Executor unregistered: kind={}", kind)
        return existed

    def kinds(self) -> list[str]:
        """已注册的 executor kind 列表（快照）。"""
        return self._table.names()

    def params_of(self, kind: str) -> Optional["type[BaseModel]"]:
        """按 kind 取参数模型；未注册或无模型返回 None（ext/平台消费）。"""
        return self._table.params_of(kind)

    def describe(self) -> list[dict]:
        """strategy 表 describe 导出（ext list --json 口径）。"""
        return self._table.describe()

    def dispatch(
        self,
        spec: "StrategyBase",
        view: "StrategyContextView",
    ) -> StrategyResult:
        """根据 spec.kind 找到对应 executor，执行并返回结果。

        框架在这里统一做：
          - 跳过 disabled 的策略
          - 触发 STRATEGY_BEFORE hook（可改写 spec/view）
          - 计时
          - 触发 STRATEGY_AFTER hook（可改写 result）
          - 兜底异常捕获（executor 内部不应抛出，但双保险）
        """
        kind = getattr(spec, "kind", None)
        strategy_id = getattr(spec, "name", None) or kind or "unknown"

        # 1. disabled 跳过
        if not getattr(spec, "enabled", True):
            logger.debug("[StrategyDispatcher] Strategy skipped (disabled): strategy_id={}", strategy_id)
            return StrategyResult(
                status=StrategyStatus.SKIPPED,
                strategy_id=strategy_id,
                message="strategy disabled",
            )
        # 2. 查找 executor
        try:
            _params, executor = self._table.get(kind)
        except KeyError:
            logger.error("[StrategyDispatcher] No executor registered: kind={} strategy_id={}", kind, strategy_id)
            return StrategyResult(
                status=StrategyStatus.ERROR,
                strategy_id=strategy_id,
                message=f"No executor registered for kind={kind!r}",
                error=f"UnregisteredKind: {kind}",
            )

        # 3. STRATEGY_BEFORE hook（可被 hook 抛出 STOP 来短路此 strategy）
        if self._hooks is not None:
            payload = {"strategy_name": strategy_id, "kind": kind, "spec": spec, "view": view}
            result_hook = self._hooks.trigger(HookPoint.STRATEGY_BEFORE, payload)
            if result_hook.stopped:
                logger.info(
                    "[StrategyDispatcher] STRATEGY_BEFORE blocked: strategy_id={} plugin={} reason={}",
                    strategy_id, result_hook.stop_plugin, result_hook.stop_reason,
                )
                return StrategyResult(
                    status=StrategyStatus.SKIPPED,
                    strategy_id=strategy_id,
                    message=f"blocked by hook: {result_hook.stop_reason}",
                )

        # 4. 执行（含计时 + 兜底捕获）
        t0 = time.monotonic()
        try:
            result = executor.execute(spec, view)
        except Exception as exc:  # noqa: BLE001
            logger.exception("[StrategyDispatcher] Unexpected exception in executor: strategy_id={}", strategy_id)
            result = StrategyResult(
                status=StrategyStatus.ERROR,
                strategy_id=strategy_id,
                message=f"Unexpected exception in executor: {exc}",
                error=repr(exc),
            )
        result.duration_ms = (time.monotonic() - t0) * 1000
        result.strategy_id = result.strategy_id or strategy_id
        # 软失败标记：spec.onFailure != ABORT 时，即使失败也仅记录不中止
        from gimbal.schema.strategy import FailurePolicy
        on_failure = getattr(spec, "onFailure", FailurePolicy.ABORT)
        if result.failed and on_failure != FailurePolicy.ABORT:
            result.soft = True
            logger.debug(
                "[StrategyDispatcher] Strategy marked soft-fail: strategy_id={} onFailure={}",
                strategy_id, on_failure.value,
            )
        logger.debug("[StrategyDispatcher] Strategy executed: strategy_id={} status={} duration_ms={:.2f} soft={}",
                    strategy_id, result.status.value, result.duration_ms, result.soft)

        # 5. STRATEGY_AFTER hook（可改写 result）
        if self._hooks is not None:
            payload = {
                "strategy_name": strategy_id,
                "kind": kind,
                "result": result,
                "view": view,
            }
            self._hooks.trigger(HookPoint.STRATEGY_AFTER, payload)

        return result

    def dispatch_phase(
        self,
        phase: str,
        strategies: list["StrategyBase"],
        view: "StrategyContextView",
    ) -> list[StrategyResult]:
        """执行属于指定 phase 的所有策略，按 order 排序后顺序执行。

        遇到 hard-fail（onFailure=ABORT 且结果为 FAILED/ERROR）时提前终止。
        软失败（onFailure=CONTINUE/WARN）则记录并继续。

        Returns:
            已执行策略的结果列表（包括提前终止前已完成的部分）。
        """
        from gimbal.schema.strategy import FailurePolicy

        # 过滤出属于当前阶段的策略，按 order 排序
        phase_specs = sorted(
            (s for s in strategies if getattr(s, "phase", None) == phase),
            key=lambda s: getattr(s, "order", 0),
        )

        results: list[StrategyResult] = []
        logger.debug("[StrategyDispatcher] Phase dispatch starting: phase={} strategy_count={}", phase, len(phase_specs))
        for spec in phase_specs:
            result = self.dispatch(spec, view)
            results.append(result)

            # 失败时根据 onFailure 决定是否继续
            if result.failed:
                on_failure = getattr(spec, "onFailure", FailurePolicy.ABORT)
                if on_failure == FailurePolicy.ABORT:
                    logger.warning("[StrategyDispatcher] Phase aborting due to failure: phase={} strategy_id={}",
                                 phase, result.strategy_id)
                    break   # 硬中止，后续策略不再执行

        logger.debug("[StrategyDispatcher] Phase dispatch completed: phase={} result_count={}", phase, len(results))
        return results


def build_default_dispatcher(
    hook_registry: Optional[Any] = None,
    *,
    event_bus: Optional[Any] = None,
    auth_registry: Optional[Any] = None,
) -> StrategyDispatcher:
    """构造并注册内置所有 executor 的 dispatcher。

    2026-09-27 协议中立化：CallExecutor 以 http 协议执行器身份进 ProtocolRegistry
    （第一员）。S-2 起协议与策略表解耦：协议不进本 dispatcher 的 kind 表
    （kinds() 只含策略），d.protocols 仅作为组合接线引用（Engine/状态机
    透传用），注册表构造时注入埋点设施。
    """
    from gimbal.strategy.builtin.extract import ExtractExecutor
    from gimbal.strategy.builtin.assign import AssignExecutor
    from gimbal.strategy.builtin.assertion import AssertionExecutor
    from gimbal.schema.strategy import Assign, Assertion, Extract
    from gimbal.protocols.registry import build_default_protocol_registry

    d = StrategyDispatcher(hook_registry=hook_registry)
    d.protocols = build_default_protocol_registry(
        hook_registry=hook_registry, event_bus=event_bus, auth_registry=auth_registry,
    )
    d.register(ExtractExecutor(), params=Extract)
    d.register(AssignExecutor(), params=Assign)
    d.register(AssertionExecutor(), params=Assertion)
    return d