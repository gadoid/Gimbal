"""builtin/json_reporter.py — JsonReporter（终结型，结构化 JSON dump）。"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gimbal.core.runner import RunResult
from gimbal.reporter.base import ReportArtifact, ReporterBase


class JsonReporter(ReporterBase):
    """将完整 RunResult 序列化为 JSON 落盘。

    包含 meta（run_id / env / mode / version）+ summary + scenarios 详情。
    可选：include_event_timeline=True 时同时序列化事件流（begin 阶段订阅所有事件累积）。
    """

    name = "json"

    def __init__(self) -> None:
        self._timeline: list[dict[str, Any]] = []
        self._include_timeline: bool = False

    def begin(self, ctx) -> None:
        self._include_timeline = bool(ctx.user("include_event_timeline", False))
        if self._include_timeline:
            # 订阅所有事件。注意：这里用 wildcard ""，依赖 InMemoryEventBus 的过滤实现
            from gimbal.events.types import EventType
            for et in EventType:
                sid = ctx.bus.subscribe(
                    self._record_event, event_type=et.value,
                    mode=ctx.subscription_mode,
                    plugin_name=f"reporter.{self.name}",
                    priority=ctx.subscription_priority,
                )
                ctx.subscription_ids.append(sid)
        super().begin(ctx)

    def _record_event(self, event) -> None:
        try:
            self._timeline.append({
                "ts": datetime.now(timezone.utc).isoformat(),
                "type": getattr(event, "event_type", type(event).__name__),
                "payload": event.model_dump() if hasattr(event, "model_dump") else str(event),
            })
        except Exception:
            pass

    def finalize(self, run_result: RunResult, ctx) -> ReportArtifact:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        out_path = ctx.report_dir / f"run-{ctx.framework_ctx.run_id}-{ts}.json"

        indent = int(ctx.user("indent", 2))
        fc = ctx.framework_ctx

        payload: dict[str, Any] = {
            "meta": {
                "run_id": fc.run_id,
                "env": fc.environment,
                "mode": fc.mode,
                "framework_version": fc.framework_version,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            "summary": {
                "exit_code": run_result.exit_code,
                "total": run_result.total,
                "passed": run_result.passed,
                "failed": run_result.failed,
                "error": run_result.error,
                "skipped": run_result.skipped,
            },
            "details": list(run_result.details or []),
        }
        if self._include_timeline:
            payload["event_timeline"] = self._timeline

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=indent, default=str),
            encoding="utf-8",
        )
        return ReportArtifact(
            name=self.name,
            path=out_path,
            media_type="application/json",
            metadata={
                "size": out_path.stat().st_size,
                "timeline_count": len(self._timeline),
            },
        )


def factory(user_config: dict[str, Any]) -> JsonReporter:
    return JsonReporter()
