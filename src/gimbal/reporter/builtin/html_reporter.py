"""builtin/html_reporter.py — HtmlReporter（事件驱动 + finalize 落盘）。

订阅 scenario.* / step.* / http.* 事件，在 finalize 时把累积的状态
一次性渲染成自包含 HTML。当事件未触发（如 dry-run）时回落到
RunResult.details 以保持兼容。
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from gimbal.core.runner import RunResult
from gimbal.events.types import (
    FrameworkEvent,
    HttpRequestEvent,
    HttpResponseEvent,
    RunMetaEvent,
    ScenarioEndEvent,
    ScenarioStartEvent,
    StepEndEvent,
    StepFailedEvent,
    StepStartEvent,
)
from gimbal.reporter.base import ReportArtifact, ReporterBase


# 内嵌 CSS / JS 字符串模板；用 {{}} 转义 f-string 的花括号
_HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Gimbal Report — {title}</title>
<style>
  body {{ font: 14px/1.4 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          margin: 0; padding: 24px; background: #fafafa; color: #222; }}
  h1 {{ font-size: 20px; margin: 0 0 8px; }}
  .meta {{ color: #666; margin-bottom: 4px; font-size: 12px; }}
  .summary {{ display: flex; gap: 12px; margin: 16px 0; flex-wrap: wrap; }}
  .pill {{ padding: 6px 12px; border-radius: 999px; font-weight: 600; font-size: 13px; }}
  .pill-passed {{ background: #dcfce7; color: #166534; }}
  .pill-failed {{ background: #fee2e2; color: #991b1b; }}
  .pill-error  {{ background: #fef3c7; color: #92400e; }}
  .pill-skipped{{ background: #e5e7eb; color: #374151; }}
  .pill-total  {{ background: #dbeafe; color: #1e40af; }}
  .pill-ci     {{ background: #ede9fe; color: #5b21b6; }}
  .pill-meta   {{ background: #f1f5f9; color: #334155; }}
  .pill-tag    {{ background: #e0e7ff; color: #3730a3; font-weight: 500; }}
  .run-meta    {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px;
                 padding: 10px 14px; margin: 12px 0; }}
  .run-meta .label {{ color: #64748b; font-size: 11px; font-weight: 600;
                      text-transform: uppercase; letter-spacing: 0.5px;
                      margin-right: 4px; }}
  .scenario-meta-chips {{ display: inline-flex; gap: 4px; flex-wrap: wrap;
                          margin-left: 8px; vertical-align: middle; }}
  details.scenario {{ background: #fff; border: 1px solid #e5e7eb; border-radius: 6px;
             padding: 10px 14px; margin: 6px 0; }}
  details.scenario[open] {{ background: #f9fafb; }}
  summary {{ cursor: pointer; font-weight: 500; }}
  .filterbar {{ margin: 16px 0; }}
  .filterbar button {{ background: #fff; border: 1px solid #d1d5db; padding: 4px 10px;
                       border-radius: 4px; margin-right: 6px; cursor: pointer; }}
  .filterbar button.active {{ background: #2563eb; color: #fff; border-color: #2563eb; }}
  .step-pill {{ padding: 2px 8px; border-radius: 4px; font-family: ui-monospace, monospace;
                font-size: 12px; display: inline-block; min-width: 1.2em; text-align: center; }}
  .step-pill.passed {{ background: #dcfce7; color: #166534; }}
  .step-pill.failed {{ background: #fee2e2; color: #991b1b; }}
  .step-pill.error  {{ background: #fef3c7; color: #92400e; }}
  .step-pill.skipped{{ background: #e5e7eb; color: #374151; }}
  ol.steps {{ list-style: none; padding-left: 0; margin: 10px 0 4px; }}
  ol.steps > li {{ padding: 8px 0; border-top: 1px solid #f1f5f9; }}
  ol.steps > li:first-child {{ border-top: none; }}
  .step-line {{ display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }}
  .step-name {{ font-weight: 500; }}
  .step-id   {{ font-family: ui-monospace, monospace; color: #64748b; font-size: 12px; }}
  .step-meta {{ color: #64748b; font-size: 12px; margin-left: auto; }}
  pre {{ background: #0f172a; color: #e2e8f0; padding: 10px; border-radius: 6px;
         overflow-x: auto; font-size: 12px; margin: 6px 0 0; white-space: pre-wrap; }}
  .err  {{ color: #991b1b; font-family: ui-monospace, monospace; }}
  .http-summary {{ color: #475569; font-size: 11px; margin-top: 4px;
                   font-family: ui-monospace, monospace; background: #f8fafc;
                   padding: 4px 8px; border-radius: 4px; line-height: 1.6; }}
  .http-summary .ok  {{ color: #166534; }}
  .http-summary .bad {{ color: #991b1b; }}
  footer {{ margin-top: 32px; color: #999; font-size: 12px; text-align: center; }}
</style>
</head>
<body>
<h1>🛠 Gimbal Report</h1>
<div class="meta">
  <div>Run ID: <code>{run_id}</code></div>
  <div>Env: <code>{env}</code> &nbsp; Mode: <code>{mode}</code> &nbsp;
       Framework: <code>{framework_version}</code></div>
  <div>Generated at: {generated_at}</div>
</div>

{run_meta_html}

<div class="summary" id="summary">
  <span class="pill pill-total">Total: {total}</span>
  <span class="pill pill-passed">Passed: {passed}</span>
  <span class="pill pill-failed">Failed: {failed}</span>
  <span class="pill pill-error">Error: {error}</span>
  <span class="pill pill-skipped">Skipped: {skipped}</span>
</div>

<div class="filterbar">
  Filter:
  <button data-filter="all" class="active">All</button>
  <button data-filter="failed">Failed</button>
  <button data-filter="error">Error</button>
  <button data-filter="passed">Passed</button>
  <button data-filter="skipped">Skipped</button>
</div>

<div id="scenarios">
  {scenarios_html}
</div>

<footer>Generated by Gimbal Reporter. Embedded data: see <code>#report-data</code> below.</footer>

<script id="report-data" type="application/json">{data_json}</script>
<script>
  const filterButtons = document.querySelectorAll('.filterbar button');
  const scenariosEl = document.getElementById('scenarios');
  filterButtons.forEach(btn => {{
    btn.addEventListener('click', () => {{
      filterButtons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const f = btn.dataset.filter;
      scenariosEl.querySelectorAll('details.scenario').forEach(d => {{
        d.style.display = (f === 'all' || d.dataset.status === f) ? '' : 'none';
      }});
    }});
  }});
</script>
</body>
</html>
"""


_STEP_TEMPLATE = """<li class="step-item" data-step-status="{status}">
  <div class="step-line">
    <span class="step-pill {status}">{marker}</span>
    <span class="step-id">{step_id}</span>
    <span class="step-name">{step_name}</span>
    <span class="step-meta">{meta}</span>
  </div>
  {http_block}
  {error_block}
</li>"""


_SCENARIO_TEMPLATE = """<details class="scenario" data-status="{status}" {open_attr}>
  <summary>
    <span class="step-pill {status}">{status}</span>
    <strong>{scenario_id}</strong>
    {name_span}
    {meta_chips}
    &nbsp;—&nbsp;<span class="meta">{duration_ms:.1f}ms</span>
  </summary>
  <ol class="steps">
    {steps_html}
  </ol>
  {error_block}
</details>
"""


class HtmlReporter(ReporterBase):
    """单文件 HTML 报告（事件驱动 + 嵌入式 JSON）。

    适合：邮件附件、本地归档、不需要 Allure 命令链的轻量场景。
    """

    name = "html"
    interested_events: tuple[str, ...] = (
        "scenario.start",
        "scenario.end",
        "step.start",
        "step.end",
        "step.failed",
        "http.request",
        "http.response",
        "run.meta",
    )

    def __init__(self) -> None:
        self._scenarios: dict[str, dict[str, Any]] = {}
        self._steps: dict[tuple[str, str], dict[str, Any]] = {}
        self._step_order: dict[str, list[str]] = defaultdict(list)
        self._http_calls: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        self._http_count: int = 0
        self._current_scenario: str = ""
        # RunMetaEvent 缓存（CI/CD / git / 触发人）
        self._run_meta: dict[str, Any] = {}

    # ── 流式事件 ────────────────────────────────────────────────────

    def on_event(self, event: FrameworkEvent) -> None:
        try:
            if isinstance(event, ScenarioStartEvent):
                self._current_scenario = event.scenario_id
                self._scenarios.setdefault(event.scenario_id, {
                    "scenario_id": event.scenario_id,
                    "scenario_name": event.scenario_name,
                    "status": "passed",
                    "duration_ms": 0.0,
                    "step_count_declared": event.step_count,
                    "error": None,
                })
            elif isinstance(event, ScenarioEndEvent):
                sc = self._scenarios.setdefault(event.scenario_id, {
                    "scenario_id": event.scenario_id,
                    "scenario_name": "",
                    "status": event.status,
                    "duration_ms": 0.0,
                    "step_count_declared": event.step_count,
                    "error": None,
                    "meta": {},
                })
                sc["status"] = event.status
                # ScenarioEndEvent.meta 携带 Scenario.meta 的 dump（tags/author/priority/...）
                if event.meta:
                    sc["meta"] = dict(event.meta)
            elif isinstance(event, StepStartEvent):
                sc_id = event.scenario_id or self._current_scenario
                self._upsert_step(sc_id, event.step_id, {
                    "scenario_id": sc_id,
                    "step_id": event.step_id,
                    "step_name": event.step_name,
                    "strategy_kind": event.strategy_kind,
                    "status": "passed",
                    "duration_ms": 0.0,
                    "assertion_count": 0,
                    "assertion_passed": 0,
                    "promotion_count": 0,
                    "error": None,
                })
            elif isinstance(event, StepEndEvent):
                sc_id = event.scenario_id or self._current_scenario
                rec = self._upsert_step(sc_id, event.step_id, {
                    "scenario_id": sc_id,
                    "step_id": event.step_id,
                    "step_name": "",
                    "strategy_kind": "",
                    "status": event.status,
                    "duration_ms": event.duration_ms,
                    "assertion_count": event.assertion_count,
                    "assertion_passed": event.assertion_passed,
                    "promotion_count": event.promotion_count,
                    "error": event.error_brief,
                })
                # StepEnd 已是权威结果，直接覆盖
                rec["status"] = event.status
                rec["duration_ms"] = event.duration_ms
                rec["assertion_count"] = event.assertion_count
                rec["assertion_passed"] = event.assertion_passed
                rec["promotion_count"] = event.promotion_count
                if event.error_brief:
                    rec["error"] = event.error_brief
            elif isinstance(event, StepFailedEvent):
                sc_id = self._current_scenario
                rec = self._upsert_step(sc_id, event.step_id, {
                    "scenario_id": sc_id,
                    "step_id": event.step_id,
                    "step_name": "",
                    "strategy_kind": "",
                    "status": "failed",
                    "duration_ms": 0.0,
                    "assertion_count": 0,
                    "assertion_passed": 0,
                    "promotion_count": 0,
                    "error": event.error,
                })
                rec["status"] = "failed"
                rec["error"] = event.error
            elif isinstance(event, HttpRequestEvent):
                self._http_count += 1
                sc_id = self._current_scenario
                self._http_calls[(sc_id, event.step_id)].append({
                    "kind": "request",
                    "method": event.method,
                    "url": event.url,
                })
            elif isinstance(event, HttpResponseEvent):
                sc_id = self._current_scenario
                self._http_calls[(sc_id, event.step_id)].append({
                    "kind": "response",
                    "status_code": event.status_code,
                    "duration_ms": event.duration_ms,
                })
            elif isinstance(event, RunMetaEvent):
                # 缓存 run_meta；后到的覆盖先到的（CLI 通常只发一次）
                self._run_meta = dict(event.meta or {})
        except Exception:
            # 事件处理异常不能影响主流程
            pass

    def _upsert_step(self, sc_id: str, step_id: str, defaults: dict[str, Any]) -> dict[str, Any]:
        """插入或更新 step 记录；保留 (sc_id, step_id) 的出现顺序。"""
        key = (sc_id, step_id)
        if key not in self._steps:
            self._steps[key] = dict(defaults)
            self._step_order[sc_id].append(step_id)
        else:
            rec = self._steps[key]
            for k, v in defaults.items():
                # 只在已有字段为空/None/0 时才补，避免 StepStart 的 status='passed'
                # 覆盖了 StepEnd 后的 status='failed'。
                if k in ("status", "duration_ms", "assertion_count",
                         "assertion_passed", "promotion_count", "error"):
                    continue
                if v not in (None, "", 0) and not rec.get(k):
                    rec[k] = v
        return self._steps[key]

    # ── 终结 ────────────────────────────────────────────────────────

    def finalize(self, run_result: RunResult, ctx) -> ReportArtifact:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        out_path = ctx.report_dir / f"report-{ts}.html"

        fc = ctx.framework_ctx
        scenarios_view = self._build_scenarios_view(run_result)
        scenarios_html = _render_scenarios(scenarios_view, self._http_calls)
        run_meta_html = _render_run_meta(self._run_meta)

        data = {
            "run_id": getattr(fc, "run_id", ""),
            "env": getattr(fc, "environment", ""),
            "mode": getattr(fc, "mode", ""),
            "framework_version": getattr(fc, "framework_version", ""),
            "summary": {
                "total": run_result.total,
                "passed": run_result.passed,
                "failed": run_result.failed,
                "error": run_result.error,
                "skipped": run_result.skipped,
            },
            "run_meta": dict(self._run_meta),
            "scenarios": scenarios_view,
        }
        data_json = json.dumps(data, ensure_ascii=False, default=str)

        html = _HTML_TEMPLATE.format(
            title=getattr(fc, "run_id", "gimbal"),
            run_id=getattr(fc, "run_id", ""),
            env=getattr(fc, "environment", ""),
            mode=getattr(fc, "mode", ""),
            framework_version=getattr(fc, "framework_version", ""),
            generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            total=run_result.total,
            passed=run_result.passed,
            failed=run_result.failed,
            error=run_result.error,
            skipped=run_result.skipped,
            run_meta_html=run_meta_html,
            scenarios_html=scenarios_html,
            data_json=data_json,
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(html, encoding="utf-8")
        return ReportArtifact(
            name=self.name,
            path=out_path,
            media_type="text/html",
            metadata={
                "size": len(html),
                "scenario_count": len(scenarios_view),
                "http_count": self._http_count,
                "has_run_meta": bool(self._run_meta),
            },
        )

    def _build_scenarios_view(self, run_result: RunResult) -> list[dict[str, Any]]:
        """构造渲染用的 scenarios 视图。

        优先使用事件累积；事件未触发时回落到 RunResult.details。
        """
        if not self._scenarios:
            return list(run_result.details or [])

        view: list[dict[str, Any]] = []
        for sc_id, sc in self._scenarios.items():
            steps = [self._steps[(sc_id, sid)] for sid in self._step_order.get(sc_id, [])]
            view.append({
                "scenario_id": sc["scenario_id"],
                "scenario_name": sc.get("scenario_name", ""),
                "status": sc.get("status", "passed"),
                "duration_ms": sc.get("duration_ms", 0.0),
                "error": sc.get("error"),
                "meta": sc.get("meta", {}),
                "steps": steps,
            })
        return view


# ── 渲染辅助 ─────────────────────────────────────────────────────────

def _render_run_meta(meta: dict[str, Any]) -> str:
    """把 RunMetaEvent.meta 渲染成头部"运行上下文"区块。

    显示常见 CI/CD 键（branch / commit / build_url / ci / triggered_by），
    其余键作为"扩展"行展开。未提供 meta 时返回空字符串。
    """
    if not meta:
        return ""

    primary_keys = ("branch", "commit", "build_url", "ci", "triggered_by")
    primary_pills: list[str] = []
    for k in primary_keys:
        v = meta.get(k)
        if v in (None, ""):
            continue
        klass = "pill-ci" if k == "ci" else "pill-meta"
        primary_pills.append(
            f'<span class="pill {klass}">{_e(str(k))}: {_e(str(v))}</span>'
        )

    extra_keys = [k for k in meta.keys() if k not in primary_keys]
    extra_rows: list[str] = []
    for k in extra_keys:
        v = meta.get(k)
        if v in (None, ""):
            continue
        extra_rows.append(
            f'<div><span class="label">{_e(str(k))}:</span> {_e(str(v))}</div>'
        )

    if not primary_pills and not extra_rows:
        return ""

    parts: list[str] = ['<div class="run-meta">']
    if primary_pills:
        parts.append('<div class="summary">' + "".join(primary_pills) + "</div>")
    if extra_rows:
        parts.append('<div style="margin-top:6px">' + "".join(extra_rows) + "</div>")
    parts.append("</div>")
    return "".join(parts)


def _render_meta_chips(meta: dict[str, Any]) -> str:
    """把 Scenario.meta 渲染成 summary 末尾的 chip 行。

    重点展示 tags（最常用）、author、priority、version；
    其余字段折叠成"其它"行。空 dict 返回空字符串。
    """
    if not meta:
        return ""

    chips: list[str] = []

    # tags → 一组 .pill-tag
    tags = meta.get("tags")
    if isinstance(tags, (list, tuple)):
        for t in tags:
            if t in (None, ""):
                continue
            chips.append(f'<span class="pill pill-tag">{_e(str(t))}</span>')
    elif tags not in (None, ""):
        chips.append(f'<span class="pill pill-tag">{_e(str(tags))}</span>')

    for k in ("author", "priority", "version"):
        v = meta.get(k)
        if v in (None, ""):
            continue
        chips.append(f'<span class="pill pill-meta">{_e(str(k))}: {_e(str(v))}</span>')

    if not chips:
        return ""

    return '<span class="scenario-meta-chips">' + "".join(chips) + "</span>"


def _render_scenarios(
    scenarios: list[dict[str, Any]],
    http_calls: dict[tuple[str, str], list[dict[str, Any]]],
) -> str:
    if not scenarios:
        return "<p><em>No scenarios executed.</em></p>"
    out: list[str] = []
    for d in scenarios:
        status = d.get("status", "passed")
        scenario_id = _e(d.get("scenario_id", "?"))
        scenario_name = _e(d.get("scenario_name", "") or "")
        duration_ms = float(d.get("duration_ms", 0) or 0)
        name_span = (
            f"&nbsp;—&nbsp;<span class=\"meta\">{scenario_name}</span>"
            if scenario_name else ""
        )
        meta_chips = _render_meta_chips(d.get("meta") or {})
        steps = d.get("steps") or []
        steps_html = _render_steps(steps, http_calls) if steps else "<li><em>No steps recorded.</em></li>"
        error_block = ""
        if status in ("failed", "error") and d.get("error"):
            error_block = f'<pre class="err">{_e(str(d["error"]))}</pre>'
        out.append(_SCENARIO_TEMPLATE.format(
            status=status,
            scenario_id=scenario_id,
            name_span=name_span,
            meta_chips=meta_chips,
            duration_ms=duration_ms,
            open_attr="open" if status in ("failed", "error") else "",
            steps_html=steps_html,
            error_block=error_block,
        ))
    return "\n".join(out)


def _render_steps(
    steps: list[dict[str, Any]],
    http_calls: dict[tuple[str, str], list[dict[str, Any]]],
) -> str:
    out: list[str] = []
    for s in steps:
        status = s.get("status", "passed")
        marker = {"passed": "✓", "failed": "✗", "error": "!", "skipped": "−"}.get(status, "?")
        step_id = _e(s.get("step_id", "?"))
        step_name = _e(s.get("step_name", "") or "")
        meta_parts = [f"{float(s.get('duration_ms', 0) or 0):.1f}ms"]
        if s.get("strategy_kind"):
            meta_parts.append(_e(str(s["strategy_kind"])))
        if s.get("assertion_count"):
            meta_parts.append(
                f"asserts={s.get('assertion_passed', 0)}/{s.get('assertion_count', 0)}"
            )
        if s.get("promotion_count"):
            meta_parts.append(f"promotions={s.get('promotion_count')}")
        meta = " · ".join(meta_parts)
        http_block = _render_http_calls(
            http_calls.get((s.get("scenario_id", ""), s.get("step_id", "")), [])
        )
        err = s.get("error")
        error_block = ""
        if err:
            error_block = f'<pre class="err">{_e(str(err))}</pre>'
        out.append(_STEP_TEMPLATE.format(
            status=status,
            marker=marker,
            step_id=step_id,
            step_name=step_name,
            meta=meta,
            http_block=http_block,
            error_block=error_block,
        ))
    return "\n".join(out) if out else "<li><em>No steps.</em></li>"


def _render_http_calls(calls: list[dict[str, Any]]) -> str:
    if not calls:
        return ""
    lines: list[str] = []
    for c in calls:
        if c["kind"] == "request":
            lines.append(f"&rarr; {_e(str(c.get('method', '?')))} {_e(str(c.get('url', '?')))}")
        else:
            code = int(c.get("status_code", 0) or 0)
            klass = "ok" if 200 <= code < 400 else "bad"
            dur = float(c.get("duration_ms", 0) or 0)
            lines.append(
                f"&larr; <span class=\"{klass}\">{code}</span> ({dur:.1f}ms)"
            )
    return f'<div class="http-summary">' + "<br>".join(lines) + "</div>"


def _e(s: str) -> str:
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
    )


def factory(user_config: dict[str, Any]) -> HtmlReporter:
    return HtmlReporter()
