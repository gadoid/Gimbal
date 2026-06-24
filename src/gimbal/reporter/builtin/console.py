"""builtin/console.py — ConsoleReporter（实时进度 + 终态高亮摘要）。"""
from __future__ import annotations

import sys
from typing import Any

from gimbal.core.runner import RunResult
from gimbal.events.types import (
    FrameworkEvent,
    HttpRequestEvent,
    HttpResponseEvent,
    ScenarioEndEvent,
    ScenarioStartEvent,
    StepEndEvent,
    StepFailedEvent,
    StepStartEvent,
)
from gimbal.reporter.base import ReportArtifact, ReporterBase


_RESET = "\x1b[0m"
_BOLD = "\x1b[1m"
_DIM = "\x1b[2m"
_RED = "\x1b[31m"
_GREEN = "\x1b[32m"
_YELLOW = "\x1b[33m"
_CYAN = "\x1b[36m"
_GREY = "\x1b[90m"


def _color(text: str, code: str, enabled: bool) -> str:
    return f"{code}{text}{_RESET}" if enabled else text


class ConsoleReporter(ReporterBase):
    """终端控制台 reporter。"""

    name = "console"
    stream_to_stderr = True

    interested_events: tuple[str, ...] = (
        "scenario.start",
        "scenario.end",
        "step.start",
        "step.end",
        "step.failed",
    )

    def __init__(self) -> None:
        self._current_scenario: str = ""
        self._current_step: str = ""
        self._http_count: int = 0
        self._failed_steps: list[dict[str, Any]] = []
        self._no_color: bool = False
        self._verbosity: str = "normal"

    def begin(self, ctx) -> None:
        self._no_color = bool(getattr(ctx.config, "no_color", False)) or bool(ctx.user("no_color", False))
        self._verbosity = str(ctx.user("verbosity", "normal"))
        if self._verbosity == "verbose":
            for et in ("http.request", "http.response"):
                sid = ctx.bus.subscribe(
                    self.on_event, event_type=et,
                    mode=ctx.subscription_mode,
                    plugin_name=f"reporter.{self.name}",
                    priority=ctx.subscription_priority,
                )
                ctx.subscription_ids.append(sid)
        super().begin(ctx)

    def on_event(self, event: FrameworkEvent) -> None:
        nc = self._no_color
        try:
            if isinstance(event, ScenarioStartEvent):
                self._current_scenario = event.scenario_id
                self._current_step = ""
                self._stream(_color(
                    f"\n[{event.scenario_id}] ▶  {event.scenario_name} (steps={event.step_count})",
                    _BOLD + _CYAN, not nc,
                ))
            elif isinstance(event, StepStartEvent):
                self._current_step = event.step_id
                self._stream(_color(
                    f"  [{event.scenario_id or self._current_scenario}/{event.step_id}] start",
                    _DIM, not nc,
                ))
                if event.description:
                    self._stream(_color(
                        f"      {event.description}",
                        _DIM, not nc,
                    ))
            elif isinstance(event, StepEndEvent):
                dur = event.duration_ms
                marker = "✓" if event.status == "passed" else ("-" if event.status == "skipped" else "✗")
                color = _GREEN if event.status == "passed" else (
                    _YELLOW if event.status == "skipped" else _RED
                )
                line = f"    {marker} {event.status:8s} {dur:7.2f}ms"
                if event.assertion_count:
                    line += f"   asserts={event.assertion_passed}/{event.assertion_count}"
                if event.promotion_count:
                    line += f"   promotions={event.promotion_count}"
                self._stream(_color(line, color, not nc))
                if event.error_brief:
                    self._stream(_color(f"      ! {event.error_brief}", _RED, not nc))
            elif isinstance(event, StepFailedEvent):
                self._failed_steps.append({
                    "step_id": event.step_id,
                    "error": event.error,
                    "phase": event.phase,
                })
                self._stream(_color(
                    f"    ! STEP FAILED phase={event.phase} step_id={event.step_id} error={event.error[:200]}",
                    _RED, not nc,
                ))
            elif isinstance(event, HttpRequestEvent):
                self._http_count += 1
                if self._verbosity == "verbose":
                    self._stream(_color(
                        f"      → {event.method} {event.url}",
                        _GREY, not nc,
                    ))
            elif isinstance(event, HttpResponseEvent):
                if self._verbosity == "verbose":
                    self._stream(_color(
                        f"      ← {event.status_code} ({event.duration_ms:.1f}ms)",
                        _GREY, not nc,
                    ))
        except Exception:
            pass

    def finalize(self, run_result: RunResult, ctx) -> ReportArtifact:
        nc = self._no_color
        lines: list[str] = []
        lines.append("")
        lines.append(_color("─" * 60, _DIM, not nc))
        if run_result.total == 0:
            lines.append(_color("WARN  no targets executed", _YELLOW + _BOLD, not nc))
        elif run_result.passed == run_result.total and run_result.failed == 0 and run_result.error == 0:
            lines.append(_color(
                f"PASS  total={run_result.total} passed={run_result.passed}",
                _GREEN + _BOLD, not nc,
            ))
        else:
            lines.append(_color(
                f"FAIL  total={run_result.total} passed={run_result.passed} "
                f"failed={run_result.failed} error={run_result.error}",
                _RED + _BOLD, not nc,
            ))
        for d in run_result.details or []:
            sid = d.get("scenario_id", "?")
            status = d.get("status", "?")
            dur = float(d.get("duration_ms", 0) or 0)
            color = {
                "passed": _GREEN,
                "failed": _RED,
                "error":  _RED,
                "skipped": _YELLOW,
            }.get(status, "")
            lines.append(_color(
                f"  - {sid}: {status} ({dur:.1f}ms)",
                color, not nc,
            ))

        if self._failed_steps:
            lines.append("")
            lines.append(_color("Failed steps:", _YELLOW + _BOLD, not nc))
            for f in self._failed_steps[:20]:
                lines.append(_color(
                    f"  - {f['step_id']} (phase={f['phase']}): {str(f['error'])[:200]}",
                    _RED, not nc,
                ))
            if len(self._failed_steps) > 20:
                lines.append(_color(f"  ... and {len(self._failed_steps) - 20} more", _DIM, not nc))

        if self._http_count:
            lines.append(_color(f"HTTP calls: {self._http_count}", _DIM, not nc))

        lines.append(_color("─" * 60, _DIM, not nc))
        text = "\n".join(lines) + "\n"
        self._stream(text)
        return ReportArtifact(
            name=self.name,
            path=None,
            content=text,
            media_type="text/plain",
            metadata={
                "total": run_result.total,
                "passed": run_result.passed,
                "failed": run_result.failed,
                "error": run_result.error,
                "http_count": self._http_count,
                "failed_step_count": len(self._failed_steps),
            },
        )

    def _stream(self, text: str) -> None:
        sys.stderr.write(text + ("\n" if not text.endswith("\n") else ""))
        sys.stderr.flush()


def factory(user_config: dict[str, Any]) -> ConsoleReporter:
    return ConsoleReporter()
