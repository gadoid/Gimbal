"""reporter/base.py — ReportArtifact 产物 + ReporterBase 可选基类。

设计要点：
  - ReportArtifact：所有 Reporter 的统一返回类型，path/content 至少一个非空。
  - ReporterBase：内置 Reporter 的可选基类，复用 begin 自动订阅样板代码。
    第三方插件可以走 duck typing 直接实现 ``Reporter`` Protocol（见 protocol.py），
    不必继承此基类。

注意：
  - 不在 ReporterBase 的 begin 中强制订阅，原因是部分 reporter 只想在 finalize 时
    一次性产出（例如 JUnitReporter、JsonReporter）。interested_events 留空即可。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from gimbal.core.runner import RunResult
    from gimbal.reporter.protocol import ReportContext
    from gimbal.events.types import FrameworkEvent


# ── ReportArtifact ─────────────────────────────────────────────────────────────

@dataclass
class ReportArtifact:
    """Reporter 终产物。

    Attributes:
        name:        报告名（通常 == reporter.name），便于日志关联。
        path:        文件路径（落盘场景，例如 junit.xml / allure-results/）。
        content:     字符串内容（小报告、推送 payload）。
                     path 与 content 至少一个非空——content-only 场景常见于
                     IMNotifier（推送 Markdown 卡片）。
        media_type:  MIME 类型（text/plain, application/json, application/xml, ...）。
        metadata:    任意附加信息（duration、size、upload_url、scenario_count 等）。
                     上层（PlatformUploader）可基于此决定如何处理。
    """

    name: str
    path: Optional[Path] = None
    content: Optional[str] = None
    media_type: str = "application/octet-stream"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.path is None and self.content is None:
            raise ValueError(
                f"ReportArtifact(name={self.name!r}) 必须有 path 或 content 至少一项非空"
            )

    def is_file_based(self) -> bool:
        return self.path is not None

    def to_dict(self) -> dict[str, Any]:
        """供 JsonReporter / log 等需要 dict 化的场景使用。"""
        return {
            "name": self.name,
            "path": str(self.path) if self.path else None,
            "media_type": self.media_type,
            "size": len(self.content) if self.content else None,
            "metadata": self.metadata,
        }


# ── ReporterBase ───────────────────────────────────────────────────────────────

class ReporterBase(ABC):
    """内置 Reporter 的可选基类。

    子类约定：
      1. 必须定义类属性 ``name``（注册名）。
      2. 可选定义 ``interested_events``：begin() 时自动按列表订阅。
      3. 必须实现 ``finalize()``。
      4. 可选实现 ``on_event()``（只有感兴趣的 reporter 才需要）。

    与 Protocol 关系：``ReporterBase`` 不显式继承 ``Reporter`` Protocol，但
    它实现的方法签名与 Protocol 兼容，因此 ``isinstance(r, Reporter)`` 仍然成立。
    """

    # 子类必须覆盖：注册名，例如 "console" / "junit" / "allure"
    name: str = ""

    # 子类可选覆盖：感兴趣的事件类型列表（dot.notation 字符串）
    # 留空表示该 reporter 不订阅事件，只在 finalize 时一次性产出
    interested_events: tuple[str, ...] = ()

    # 子类可选覆盖：是否打印到 stderr（仅 ConsoleReporter 默认 True）
    stream_to_stderr: bool = False

    def begin(self, ctx: "ReportContext") -> None:
        """默认 begin：根据 interested_events 自动订阅。

        子类如需自定义（例如 IMNotifier 要打开 HTTP client）可覆写，
        但应 super().begin(ctx) 以保留订阅行为。
        """
        for et in self.interested_events:
            sid = ctx.bus.subscribe(
                self.on_event,
                event_type=et,
                mode=ctx.subscription_mode,
                plugin_name=f"reporter.{self.name}",
                priority=ctx.subscription_priority,
            )
            ctx.subscription_ids.append(sid)

    # 默认 no-op；子类按需覆写
    def on_event(self, event: "FrameworkEvent") -> None:  # noqa: D401
        """流式事件回调。默认 no-op。"""
        return None

    @abstractmethod
    def finalize(
        self,
        run_result: "RunResult",
        ctx: "ReportContext",
    ) -> ReportArtifact:
        """生成最终报告产物。子类必须实现。"""
        raise NotImplementedError

    def __repr__(self) -> str:  # pragma: no cover
        return f"<{type(self).__name__} name={self.name!r}>"
