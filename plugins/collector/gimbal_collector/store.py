"""gimbal_collector/store.py

把事件总线上的事件流聚合成 RunReport。

设计：
- 同步 handler 串行调用 store 方法；用 threading.Lock 防御 ASYNC 模式下并发写。
- _current_scenario_id / _current_step_id 跟踪"当前"位置（事件流是嵌套的）。
- _http_pending 暂存 in-flight HttpRequestEvent，等 HttpResponseEvent 来配对。
- snapshot() 返回深拷贝，避免 renderer 遍历时被新事件打乱。
"""
from __future__ import annotations

import copy
import logging
import threading
from typing import Optional

from .report_data import (
    HttpExchange,
    RunReport,
    ScenarioReport,
    StepReport,
)

logger = logging.getLogger(__name__)


class ReportStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._run: Optional[RunReport] = None
        self._current_scenario_id: Optional[str] = None
        self._current_step_id: Optional[str] = None
        # step_id -> in-flight HttpExchange (request 来了等 response)
        self._http_pending: dict[str, HttpExchange] = {}

    # ── 事件处理 ────────────────────────────────────────

    def on_run_start(self, event) -> None:
        with self._lock:
            self._run = RunReport(
                run_id=getattr(event, "run_id", "") or "",
                env=getattr(event, "env", ""),
                mode=getattr(event, "mode", ""),
                started_at=_iso(getattr(event, "timestamp", None)),
            )
            self._http_pending.clear()
            self._current_scenario_id = None
            self._current_step_id = None

    def on_run_end(self, event) -> None:
        with self._lock:
            if self._run is None:
                return
            self._run.ended_at = _iso(getattr(event, "timestamp", None))
            self._run.total = getattr(event, "total", 0)
            self._run.passed = getattr(event, "passed", 0)
            self._run.failed = getattr(event, "failed", 0)
            self._run.error = getattr(event, "error", 0)

    def on_scenario_start(self, event) -> None:
        with self._lock:
            if self._run is None:
                return
            scenario_id = getattr(event, "scenario_id", "")
            self._current_scenario_id = scenario_id
            if scenario_id and scenario_id not in self._run.scenarios:
                self._run.scenarios[scenario_id] = ScenarioReport(
                    scenario_id=scenario_id,
                    scenario_name=getattr(event, "scenario_name", ""),
                    status="running",
                    started_at=_iso(getattr(event, "timestamp", None)),
                )

    def on_scenario_end(self, event) -> None:
        with self._lock:
            if self._run is None:
                return
            sc = self._run.scenarios.get(getattr(event, "scenario_id", ""))
            if sc is None:
                return
            sc.status = getattr(event, "status", "unknown")
            sc.ended_at = _iso(getattr(event, "timestamp", None))

    def on_step_start(self, event) -> None:
        with self._lock:
            if self._run is None:
                return
            step_id = getattr(event, "step_id", "")
            self._current_step_id = step_id
            sc = self._run.scenarios.get(self._current_scenario_id or "")
            if sc is None or not step_id:
                return
            if step_id not in sc.steps:
                sc.steps[step_id] = StepReport(
                    step_id=step_id,
                    step_name=getattr(event, "step_name", ""),
                    status="running",
                )

    def on_step_end(self, event) -> None:
        with self._lock:
            if self._run is None:
                return
            sc = self._run.scenarios.get(self._current_scenario_id or "")
            if sc is None:
                return
            step_id = getattr(event, "step_id", "")
            st = sc.steps.get(step_id)
            if st is None:
                # 可能在 step_start 之前就 step_end 了（异常路径），容错
                st = StepReport(
                    step_id=step_id,
                    step_name="(unknown)",
                    status="unknown",
                )
                sc.steps[step_id] = st
            st.status = getattr(event, "status", st.status)
            st.duration_ms = getattr(event, "duration_ms", 0.0) or 0.0
            st.assertion_count = getattr(event, "assertion_count", 0) or 0
            st.assertion_passed = getattr(event, "assertion_passed", 0) or 0
            err = getattr(event, "error_brief", None)
            if err:
                st.error_brief = err

    def on_http_request(self, event) -> None:
        with self._lock:
            step_id = getattr(event, "step_id", "")
            ex = HttpExchange(
                method=getattr(event, "method", ""),
                url=getattr(event, "url", ""),
                request_body=getattr(event, "request_body", None),
                request_headers=dict(getattr(event, "request_headers", {}) or {}),
            )
            self._http_pending[step_id] = ex

    def on_http_response(self, event) -> None:
        with self._lock:
            step_id = getattr(event, "step_id", "")
            ex = self._http_pending.pop(step_id, None)
            if ex is None:
                # response 来了但没看到 request（不应该发生），新建一个
                ex = HttpExchange(
                    method=getattr(event, "method", ""),
                    url=getattr(event, "url", ""),
                )
            ex.status_code = getattr(event, "status_code", None)
            ex.response_body = getattr(event, "response_body", None)
            ex.duration_ms = getattr(event, "duration_ms", None)
            sc = self._run.scenarios.get(self._current_scenario_id or "") if self._run else None
            if sc is not None:
                st = sc.steps.get(step_id)
                if st is not None:
                    st.http_exchanges.append(ex)

    def on_variable_promoted(self, event) -> None:
        with self._lock:
            if self._run is None:
                return
            by_step = getattr(event, "by_step_id", "")
            sc = self._run.scenarios.get(self._current_scenario_id or "")
            if sc is None:
                return
            st = sc.steps.get(by_step)
            if st is None:
                return
            st.promotions.append({
                "key": getattr(event, "key", ""),
                "from_layer": getattr(event, "from_layer", ""),
                "to_layer": getattr(event, "to_layer", ""),
                "reason": getattr(event, "reason", None),
            })

    # ── 快照 ────────────────────────────────────────────

    def snapshot(self) -> Optional[RunReport]:
        with self._lock:
            if self._run is None:
                return None
            return copy.deepcopy(self._run)


def _iso(ts) -> str:
    if ts is None:
        return ""
    try:
        return ts.isoformat()
    except AttributeError:
        return str(ts)
