"""reporter/protocol.py — Reporter 协议 + ReportContext。

Reporter 协议采用 ``typing.Protocol``，与 ``EventBusProtocol`` / ``HookRegistryProtocol``
保持同一设计风格。第三方插件可以走 duck typing 直接实现，无需继承 ReporterBase。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Protocol, runtime_checkable, TYPE_CHECKING

if TYPE_CHECKING:
    from gimbal.core.runner import RunResult
    from gimbal.context.framework import FrameworkContext
    from gimbal.events.types import FrameworkEvent
    from gimbal.events.subscription import SubscriptionMode
    from gimbal.reporter.base import ReportArtifact


# ── ReportContext ──────────────────────────────────────────────────────────────

@dataclass
class ReportContext:
    """Reporter 运行时上下文。

    由 ``ReporterRuntime.begin_all()`` 构造并注入到每个 reporter。
    Reporter 不应自己创建此对象。

    Attributes:
        framework_ctx:        框架级 Context（含 run_id / env / mode / version / config）。
        bus:                  EventBus Protocol（reporter 可在 begin() 中额外订阅）。
        config:               BootstrapConfig 快照。
        report_dir:           用户配置的 --report-dir。
        user_config:          来自 ``plugin_configs[self.name]`` 的子字典。
        artifacts_dir:        ``{report_dir}/artifacts/`` 共享子目录（Allure/HTML 共用）。
        subscription_ids:     runtime 记录的订阅 id 列表，shutdown 时统一 unsubscribe。
        subscription_mode:    订阅模式（默认 SYNC，避免阻塞主流程）。
        subscription_priority: 订阅优先级。
    """

    framework_ctx: "FrameworkContext"
    bus: Any                                 # EventBusProtocol
    config: Any                              # BootstrapConfig
    report_dir: Path
    user_config: dict[str, Any]
    artifacts_dir: Path
    subscription_ids: list[str] = field(default_factory=list)
    subscription_mode: Any = None           # SubscriptionMode.SYNC by default
    subscription_priority: int = 200        # 晚于一般插件（默认 100），确保其他观察者先消费

    def user(self, key: str, default: Any = None) -> Any:
        """从 user_config 取单个字段的便捷方法。"""
        return self.user_config.get(key, default)


# ── Reporter Protocol ─────────────────────────────────────────────────────────

@runtime_checkable
class Reporter(Protocol):
    """Reporter 协议。

    一个 Reporter 由两个生命周期阶段组成：
      1. 流式（可选）：``on_event()`` 被事件总线逐条回调，reporter 累积中间状态。
         不实现或返回 None 即"只关心终结点"。
      2. 终结（必选）：``finalize()`` 拿到 RunResult，输出 ReportArtifact。

    协议而非 ABC 的理由：
      - 与 EventBusProtocol / HookRegistryProtocol 设计一致
      - 第三方插件（甚至非 ReporterBase 子类）可以 duck typing 接入
      - 运行时 ``isinstance(obj, Reporter)`` 即可检查
    """

    name: str

    def begin(self, ctx: ReportContext) -> None:
        """Reporter 启动钩子。runtime 在 RUN_START 之前调用一次。"""
        ...

    def on_event(self, event: "FrameworkEvent") -> None:
        """流式事件回调（可选实现）。"""
        ...

    def finalize(
        self,
        run_result: "RunResult",
        ctx: ReportContext,
    ) -> "ReportArtifact":
        """生成最终产物。"""
        ...
