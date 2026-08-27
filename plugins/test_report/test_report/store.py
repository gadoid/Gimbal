"""store.py
v2 事件聚合器：14 个 handler，覆盖 framework / run / suite / scenario /
step / step.failed / http.request / http.response / variable.promoted。

设计参考 ``plugins/collector/gimbal_collector/store.py``。

差异：
  - 多了 suite 层；scenario 可挂在 suite 下，也可挂在 RunReport 的
    ``_loose_scenarios``（向后兼容：没收到 suite.start 时走这里）
  - http.request 阶段 append 一个 ``HttpExchange`` 半成品；http.response
    阶段按 step_id 找到它并补全 status/duration/body
  - variable.promoted 直接 append 到所属 step 的 promotions 列表
  - step.failed 单独维护 ``phase`` 与 ``traceback``，区别于 step.end 的
    error_brief
"""
from __future__ import annotations

from collections import OrderedDict
from typing import Any, Optional

from .report_data import (
    HttpExchange,
    RunReport,
    ScenarioReport,
    StepReport,
    SuiteReport,
    VariablePromotion,
)


def _iso(obj: Any, attr: str = "timestamp") -> str:
    """把事件的 timestamp 字段（datetime 或 None）格式化成 ISO 字符串。"""
    val = getattr(obj, attr, None)
    if val is None:
        return ""
    try:
        return val.isoformat()
    except AttributeError:
        return str(val)


def _to_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def _to_int(v: Any, default: int = 0) -> int:
    try:
        return int(v) if v is not None else default
    except (TypeError, ValueError):
        return default


class ReportStore:
    """内存中的 RunReport 累积器。线程不安全 —— gimbal 框架同进程内串行触发。"""

    def __init__(self) -> None:
        self._runs: "OrderedDict[str, RunReport]" = OrderedDict()
        # framework.init 一般在第一个 run.start 之前就发出，
        # 缓存 version，等 on_run_start 时回填。
        self._pending_framework_version: str = ""
        # run.meta 也可能在 run.start 之前到（CLI publish meta 在 bootstrap
        # 之后、Engine.run 之前）→ 缓存，等 on_run_start 时回填。
        self._pending_run_meta: dict = {}

    # ── 入口：让插件决定是否已有 RunReport ──
    def current_run(self) -> Optional[RunReport]:
        """最近一次 ``run.start`` 对应的 RunReport；未启动或已结束返回 None。"""
        for r in reversed(self._runs.values()):
            if not r.ended_at:
                return r
        return None

    def snapshot(self) -> Optional[RunReport]:
        """最近一次 run（含已结束）的快照。flush 时使用。"""
        if not self._runs:
            return None
        return next(reversed(self._runs.values()))

    # ── 1. Framework ──
    def on_framework_init(self, event: Any) -> None:
        """framework_version 在第一个 run 之前已知；缓存，等 run.start 回填。"""
        ver = getattr(event, "framework_version", "") or ""
        run = self.current_run()
        if run is not None:
            run.framework_version = ver
        else:
            self._pending_framework_version = ver

    # ── 2. Run 生命周期 ──
    def on_run_start(self, event: Any) -> None:
        rid = getattr(event, "run_id", None) or _auto_id("run")
        report = RunReport(
            run_id=rid,
            env=getattr(event, "env", "") or "",
            mode=getattr(event, "mode", "") or "",
            started_at=_iso(event),
            framework_version=self._pending_framework_version,
        )
        # 回填 pending 的 run.meta（如果 run.meta 在 run.start 之前到）
        if self._pending_run_meta:
            report.meta.update(self._pending_run_meta)
            self._pending_run_meta = {}
        self._runs[rid] = report
        # 用完清掉，避免污染下一次 run（理论上一个 process 只一个 framework）
        self._pending_framework_version = ""

    def on_run_end(self, event: Any) -> None:
        rid = getattr(event, "run_id", None)
        report = self._find_run(rid)
        if report is None:
            return
        report.ended_at = _iso(event)
        report.total = _to_int(getattr(event, "total", 0))
        report.passed = _to_int(getattr(event, "passed", 0))
        report.failed = _to_int(getattr(event, "failed", 0))
        report.error = _to_int(getattr(event, "error", 0))
        report.skipped = _to_int(getattr(event, "skipped", 0))

    def on_run_meta(self, event: Any) -> None:
        rid = getattr(event, "run_id", None)
        report = self._find_run(rid)
        meta = getattr(event, "meta", {}) or {}
        if report is None:
            # run.meta 在 run.start 之前到 → 缓存等回填
            self._pending_run_meta.update(dict(meta))
            return
        report.meta.update(dict(meta))

    # ── 3. Suite ──
    def on_suite_start(self, event: Any) -> None:
        report = self._find_run(getattr(event, "run_id", None))
        if report is None:
            return
        suite_id = getattr(event, "suite_id", "") or ""
        if not suite_id:
            return
        report.suites[suite_id] = SuiteReport(
            suite_id=suite_id,
            suite_name=getattr(event, "suite_name", "") or suite_id,
            status="running",
            started_at=_iso(event),
        )

    def on_suite_end(self, event: Any) -> None:
        report = self._find_run(getattr(event, "run_id", None))
        if report is None:
            return
        suite_id = getattr(event, "suite_id", "") or ""
        su = report.suites.get(suite_id)
        if su is None:
            return
        su.status = getattr(event, "status", "unknown") or "unknown"
        su.ended_at = _iso(event)

    # ── 4. Scenario ──
    def on_scenario_start(self, event: Any) -> None:
        report = self._find_run(getattr(event, "run_id", None))
        if report is None:
            return
        sid = getattr(event, "scenario_id", "") or ""
        if not sid:
            return
        suite_id = getattr(event, "suite_id", "") or ""
        sc = ScenarioReport(
            scenario_id=sid,
            scenario_name=getattr(event, "scenario_name", "") or sid,
            started_at=_iso(event),
            suite_id=suite_id,
        )
        self._attach_scenario(report, sc, suite_id)

    def on_scenario_end(self, event: Any) -> None:
        report = self._find_run(getattr(event, "run_id", None))
        if report is None:
            return
        sid = getattr(event, "scenario_id", "") or ""
        sc = self._find_scenario(report, sid)
        if sc is None:
            return
        sc.status = getattr(event, "status", "unknown") or "unknown"
        sc.ended_at = _iso(event)
        # 同步 suite_id（可能 scenario.start 时 suite_id 为空，end 时填充）
        e_suite = getattr(event, "suite_id", "") or ""
        if e_suite and not sc.suite_id:
            sc.suite_id = e_suite
            # 把 loose scenario 转移到 suite 下
            self._reattach_scenario(report, sc, e_suite)
        # 注入 scenario meta（来自 ScenarioEndEvent.meta）
        meta = getattr(event, "meta", {}) or {}
        if meta:
            sc.meta.update(dict(meta))

    # ── 5. Step ──
    def on_step_start(self, event: Any) -> None:
        report = self._find_run(getattr(event, "run_id", None))
        if report is None:
            return
        sid = getattr(event, "scenario_id", "") or ""
        sc = self._find_scenario(report, sid)
        if sc is None:
            return
        step_id = getattr(event, "step_id", "") or ""
        if not step_id:
            return
        sc.steps[step_id] = StepReport(
            step_id=step_id,
            step_name=getattr(event, "step_name", "") or step_id,
            status="running",
            strategy_kind=getattr(event, "strategy_kind", "") or "",
            strategy_spec=dict(getattr(event, "strategy_spec", {}) or {}),
            description=getattr(event, "description", None),
        )

    def on_step_end(self, event: Any) -> None:
        report = self._find_run(getattr(event, "run_id", None))
        if report is None:
            return
        sid = getattr(event, "scenario_id", "") or ""
        sc = self._find_scenario(report, sid)
        if sc is None:
            return
        step_id = getattr(event, "step_id", "") or ""
        st = sc.steps.get(step_id)
        if st is None:
            # step.start 没收到就 step.end —— 直接丢弃，避免凭空生成 step
            return
        st.status = getattr(event, "status", "unknown") or "unknown"
        st.duration_ms = _to_float(getattr(event, "duration_ms", 0.0))
        st.assertion_count = _to_int(getattr(event, "assertion_count", 0))
        st.assertion_passed = _to_int(getattr(event, "assertion_passed", 0))
        st.promotion_count = _to_int(getattr(event, "promotion_count", 0))
        st.retry_count = _to_int(getattr(event, "retry_count", 0))
        err = getattr(event, "error_brief", None)
        if err:
            st.error_brief = str(err)

    def on_step_failed(self, event: Any) -> None:
        report = self._find_run(getattr(event, "run_id", None))
        if report is None:
            return
        sid = getattr(event, "scenario_id", "") or ""
        step_id = getattr(event, "step_id", "") or ""

        # 优先按 (scenario_id, step_id) 找；找不到再走全 run 索引（step.failed
        # 事件本身不带 scenario_id，需要兜底）。
        st: Optional[StepReport] = None
        if sid:
            sc = self._find_scenario(report, sid)
            if sc is not None:
                st = sc.steps.get(step_id)
        if st is None and step_id:
            st = self._find_step_global(report, step_id)
        if st is None:
            # 实在找不到对应 step —— 直接丢弃（避免凭空生成 step）
            return
        phase = getattr(event, "phase", None)
        if phase:
            st.phase = str(phase)
        err = getattr(event, "error", None)
        if err and not st.error_brief:
            st.error_brief = str(err)

    # ── 6. HTTP ──
    def on_http_request(self, event: Any) -> None:
        """http 事件只有 step_id，没有 run_id / scenario_id。
        通过当前 active run 找到对应 step。
        """
        report = self.current_run()
        if report is None:
            return
        step_id = getattr(event, "step_id", "") or ""
        st = self._find_step_global(report, step_id)
        if st is None:
            return
        st.http_exchanges.append(HttpExchange(
            request_method=getattr(event, "method", "") or "",
            request_url=getattr(event, "url", "") or "",
            request_headers=dict(getattr(event, "request_headers", {}) or {}),
            request_body=getattr(event, "request_body", None),
        ))

    def on_http_response(self, event: Any) -> None:
        report = self.current_run()
        if report is None:
            return
        step_id = getattr(event, "step_id", "") or ""
        st = self._find_step_global(report, step_id)
        if st is None:
            return
        if not st.http_exchanges:
            # 没收到 request 就来了 response —— 补一条占位
            st.http_exchanges.append(HttpExchange(
                request_method=getattr(event, "method", "") or "",
                request_url=getattr(event, "url", "") or "",
            ))
        ex = st.http_exchanges[-1]
        ex.status_code = _to_int(getattr(event, "status_code", None), default=0) or None
        ex.duration_ms = _to_float(getattr(event, "duration_ms", None)) or None
        ex.response_body = getattr(event, "response_body", None)

    # ── 7. Variable Promotion ──
    def on_variable_promoted(self, event: Any) -> None:
        report = self.current_run()
        if report is None:
            return
        promo = VariablePromotion(
            key=getattr(event, "key", "") or "",
            from_layer=getattr(event, "from_layer", "") or "",
            to_layer=getattr(event, "to_layer", "") or "",
            by_step_id=getattr(event, "by_step_id", "") or "",
            by_scenario_id=getattr(event, "by_scenario_id", None),
            overwrote_previous=bool(getattr(event, "overwrote_previous", False)),
            reason=getattr(event, "reason", None),
        )
        # 优先挂在 by_step_id 对应的 step 下；找不到则按 by_scenario_id 挂
        st = self._find_step_global(report, promo.by_step_id) if promo.by_step_id else None
        if st is not None:
            st.promotions.append(promo)
            return
        # fallback：尝试 by_scenario_id
        if promo.by_scenario_id:
            sc = self._find_scenario(report, promo.by_scenario_id)
            if sc is not None:
                sc.steps.setdefault(
                    f"__promotion_only_{promo.key}",
                    StepReport(step_id=f"__promotion_only_{promo.key}",
                               step_name=f"(promotion {promo.key})"),
                ).promotions.append(promo)

    # ── 查找 helpers ──
    def _find_run(self, run_id: Optional[str]) -> Optional[RunReport]:
        if run_id and run_id in self._runs:
            return self._runs[run_id]
        return self.current_run()

    def _find_scenario(self, report: RunReport, scenario_id: str) -> Optional[ScenarioReport]:
        if not scenario_id:
            return None
        # 先查 suites，再查 loose
        for su in report.suites.values():
            sc = su.scenarios.get(scenario_id)
            if sc is not None:
                return sc
        return report._loose_scenarios.get(scenario_id)

    def _find_step_global(self, report: RunReport, step_id: str) -> Optional[StepReport]:
        """按 step_id 在整个 run 内查找（HTTP / promotion 没有 scenario_id 时用）。"""
        if not step_id:
            return None
        for sc in report.scenario_iter():
            st = sc.steps.get(step_id)
            if st is not None:
                return st
        return None

    def _attach_scenario(self, report: RunReport, sc: ScenarioReport, suite_id: str) -> None:
        """scenario 优先挂到 suite 下；没 suite_id 则走 _loose_scenarios。"""
        if suite_id and suite_id in report.suites:
            report.suites[suite_id].scenarios[sc.scenario_id] = sc
        else:
            report._loose_scenarios[sc.scenario_id] = sc

    def _reattach_scenario(self, report: RunReport, sc: ScenarioReport, suite_id: str) -> None:
        """scenario.end 时如果带了 suite_id，把它从 loose 移到 suite 下。"""
        if not suite_id or suite_id not in report.suites:
            return
        if report._loose_scenarios.get(sc.scenario_id) is sc:
            report._loose_scenarios.pop(sc.scenario_id, None)
        report.suites[suite_id].scenarios.setdefault(sc.scenario_id, sc)


_id_counter = {"n": 0}


def _auto_id(prefix: str) -> str:
    _id_counter["n"] += 1
    return f"{prefix}-{_id_counter['n']}"