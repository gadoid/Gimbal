"""renderers/html_renderer.py
v2 单文件 HTML 渲染器。零第三方依赖 —— 用 ``html.escape`` 转义用户数据，
f-string 拼装，CSS 内联（避免引入外部资源）。

v2 新增渲染内容：
  - Run meta 表格（CI/CD、git、触发人等 KV）
  - Framework version 头部展示
  - Suite 分组（每 suite 独立折叠块）
  - Step 内的 HTTP exchanges 子表（请求/响应/状态码/耗时/可选 body）
  - Step 内的 Variable promotions 子表
  - 失败 block（phase + error_brief + traceback）

接口与 ``gimbal_collector/renderers/json_renderer.py`` 对齐：
  - ``render(report, output_path, **kwargs) -> List[Path]``
  - 返回写入的文件列表（通常 1 个）
"""
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, List, Optional

from ..report_data import (
    HttpExchange,
    RunReport,
    ScenarioReport,
    StepReport,
    SuiteReport,
    VariablePromotion,
)


_STATUS_COLOR = {
    "passed": "#2e7d32",
    "failed": "#c62828",
    "error":  "#ef6c00",
    "skipped": "#757575",
    "running": "#0277bd",
    "unknown": "#424242",
}


def _badge(status: str) -> str:
    color = _STATUS_COLOR.get(status, _STATUS_COLOR["unknown"])
    return (
        f'<span class="badge" style="background:{color}">'
        f'{html.escape(status)}</span>'
    )


def _fmt_ms(ms: float) -> str:
    if ms is None:
        return "—"
    if ms < 1000:
        return f"{ms:.0f} ms"
    return f"{ms / 1000:.2f} s"


def _truncate(s: Any, max_chars: int) -> str:
    if s is None:
        return ""
    text = str(s)
    if max_chars and len(text) > max_chars:
        return text[:max_chars] + "…"
    return text


def _dump_json(value: Any, max_chars: int) -> str:
    """把 request/response body 之类的复杂值转成可读字符串。"""
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return _truncate(value, max_chars)
    try:
        return _truncate(json.dumps(value, ensure_ascii=False, default=str), max_chars)
    except (TypeError, ValueError):
        return _truncate(repr(value), max_chars)


class HtmlRenderer:
    """把 :class:`RunReport` 渲染为单文件 HTML（v2 全量版）。"""

    def render(
        self,
        report: RunReport,
        output_path: Path,
        title: str = "Gimbal Test Report",
        include_passed: bool = True,
        include_http_body: bool = False,
        max_body_chars: int = 4096,
    ) -> List[Path]:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        html_text = self._build_html(
            report,
            title=title,
            include_passed=include_passed,
            include_http_body=include_http_body,
            max_body_chars=max_body_chars,
        )
        output_path.write_text(html_text, encoding="utf-8")
        return [output_path]

    # ── 内部 ──
    def _build_html(
        self,
        report: RunReport,
        title: str,
        include_passed: bool,
        include_http_body: bool,
        max_body_chars: int,
    ) -> str:
        safe_title = html.escape(title)
        head = self._head(safe_title)
        body = self._body(
            report, safe_title, include_passed,
            include_http_body=include_http_body,
            max_body_chars=max_body_chars,
        )
        return (
            '<!DOCTYPE html>\n'
            '<html lang="en">\n'
            f'{head}\n'
            f'{body}\n'
            '</html>\n'
        )

    def _head(self, title: str) -> str:
        return (
            '<head>\n'
            '<meta charset="utf-8">\n'
            f'<title>{title}</title>\n'
            '<style>\n'
            '  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",'
            ' Roboto, sans-serif; margin: 0; padding: 24px; background: #fafafa;'
            ' color: #212121; }\n'
            '  h1 { margin: 0 0 8px 0; font-size: 24px; }\n'
            '  h2 { margin: 32px 0 12px 0; font-size: 18px;'
            ' border-bottom: 1px solid #ddd; padding-bottom: 6px; }\n'
            '  h3 { margin: 16px 0 8px 0; font-size: 15px; }\n'
            '  .meta { color: #666; font-size: 13px; margin-bottom: 24px; }\n'
            '  .summary { display: flex; gap: 12px; margin-bottom: 24px;'
            ' flex-wrap: wrap; }\n'
            '  .card { padding: 12px 16px; border-radius: 6px; color: #fff;'
            ' min-width: 90px; }\n'
            '  .card.http { background: #6a1b9a; }\n'
            '  .card.promo { background: #00838f; }\n'
            f'  .card.total {{ background: {_STATUS_COLOR["running"]}; }}\n'
            f'  .card.passed {{ background: {_STATUS_COLOR["passed"]}; }}\n'
            f'  .card.failed {{ background: {_STATUS_COLOR["failed"]}; }}\n'
            f'  .card.error  {{ background: {_STATUS_COLOR["error"]}; }}\n'
            f'  .card.skipped {{ background: {_STATUS_COLOR["skipped"]}; }}\n'
            '  .card .num { font-size: 28px; font-weight: 600; }\n'
            '  .card .lbl { font-size: 12px; opacity: 0.85; }\n'
            '  details { background: #fff; border: 1px solid #e0e0e0;'
            ' border-radius: 6px; padding: 12px 16px; margin-bottom: 8px; }\n'
            '  details.suite { border-color: #90a4ae; }\n'
            '  summary { cursor: pointer; font-weight: 600; font-size: 15px;'
            ' outline: none; }\n'
            '  table { width: 100%; border-collapse: collapse; margin-top: 8px; }\n'
            '  th, td { text-align: left; padding: 6px 8px; border-bottom:'
            ' 1px solid #eee; font-size: 13px; vertical-align: top; }\n'
            '  th { background: #f5f5f5; font-weight: 600; }\n'
            '  td.duration { text-align: right; font-variant-numeric: tabular-nums;'
            ' white-space: nowrap; }\n'
            '  /* step-card：每个 step 一张独立卡片，section 之间用 divider 隔开 */\n'
            '  .step-card { background: #fff; border: 1px solid #e0e0e0;'
            ' border-radius: 6px; margin: 8px 0; padding: 0;'
            ' box-shadow: 0 1px 2px rgba(0,0,0,0.04); }\n'
            '  .step-card .step-header { display: flex; align-items: center;'
            ' gap: 12px; padding: 10px 14px; border-bottom: 1px solid #eee; }\n'
            '  .step-card .step-name { font-weight: 600; font-size: 14px;'
            ' flex: 1; }\n'
            '  .step-card .step-status { flex-shrink: 0; }\n'
            '  .step-card .step-duration { color: #666; font-size: 12px;'
            ' font-variant-numeric: tabular-nums; flex-shrink: 0; }\n'
            '  .step-card .step-meta { padding: 6px 14px 8px; color: #666;'
            ' font-size: 12px; border-bottom: 1px solid #eee; }\n'
            '  .step-card .step-section { padding: 8px 14px;'
            ' border-bottom: 1px solid #eee; }\n'
            '  .step-card .step-section:last-child { border-bottom: none; }\n'
            '  .step-card .step-section summary { cursor: pointer;'
            ' font-weight: 500; font-size: 13px; outline: none; padding: 2px 0; }\n'
            '  .step-card .step-section summary::before { content: "▸ ";'
            ' color: #999; }\n'
            '  .step-card .step-section[open] > summary::before { content: "▾ "; }\n'
            '  .step-card .step-section > details > summary { font-weight: 500;'
            ' font-size: 13px; padding: 4px 0; cursor: pointer; outline: none; }\n'
            '  .step-card .step-section > details > summary::before {'
            ' content: "▸ "; color: #999; }\n'
            '  .step-card .step-section > details[open] > summary::before {'
            ' content: "▾ "; }\n'
            '  .step-card .failure-section { background: #fff3e0;'
            ' border-left: 3px solid #c62828; padding: 10px 14px; }\n'
            '  td.error { color: #c62828; font-family: ui-monospace, monospace;'
            ' white-space: pre-wrap; word-break: break-word; }\n'
            '  td.mono, pre { font-family: ui-monospace, monospace;'
            ' white-space: pre-wrap; word-break: break-word; }\n'
            '  pre { background: #263238; color: #eceff1; padding: 10px 12px;'
            ' border-radius: 4px; font-size: 12px; overflow-x: auto; }\n'
            '  .badge { display: inline-block; padding: 2px 8px; border-radius: 10px;'
            ' color: #fff; font-size: 11px; text-transform: uppercase;'
            ' letter-spacing: 0.5px; }\n'
            '  .subtable { margin-top: 6px; background: #fafafa; }\n'
            '  .subtable th { background: #eceff1; }\n'
            '  .empty { color: #999; font-style: italic; }\n'
            '  footer { color: #999; font-size: 12px; margin-top: 32px;'
            ' text-align: center; }\n'
            '  .kv-table th { width: 200px; }\n'
            '</style>\n'
            '</head>'
        )

    def _body(
        self,
        report: RunReport,
        title: str,
        include_passed: bool,
        include_http_body: bool,
        max_body_chars: int,
    ) -> str:
        meta_parts: list[str] = []
        if report.run_id:
            meta_parts.append(f"run_id: <code>{html.escape(report.run_id)}</code>")
        if report.env:
            meta_parts.append(f"env: {html.escape(report.env)}")
        if report.mode:
            meta_parts.append(f"mode: {html.escape(report.mode)}")
        if report.framework_version:
            meta_parts.append(
                f"framework: {html.escape(report.framework_version)}"
            )
        if report.started_at:
            meta_parts.append(f"started: {html.escape(report.started_at)}")
        if report.ended_at:
            meta_parts.append(f"ended: {html.escape(report.ended_at)}")

        summary_html = (
            '<div class="summary">\n'
            f'  <div class="card total"><div class="num">{report.total}</div>'
            '<div class="lbl">TOTAL</div></div>\n'
            f'  <div class="card passed"><div class="num">{report.passed}</div>'
            '<div class="lbl">PASSED</div></div>\n'
            f'  <div class="card failed"><div class="num">{report.failed}</div>'
            '<div class="lbl">FAILED</div></div>\n'
            f'  <div class="card error"><div class="num">{report.error}</div>'
            '<div class="lbl">ERROR</div></div>\n'
            f'  <div class="card skipped"><div class="num">{report.skipped}</div>'
            '<div class="lbl">SKIPPED</div></div>\n'
            f'  <div class="card http"><div class="num">{report.http_total}</div>'
            '<div class="lbl">HTTP</div></div>\n'
            f'  <div class="card promo"><div class="num">{report.promotion_total}</div>'
            '<div class="lbl">PROMOTIONS</div></div>\n'
            '</div>'
        )

        meta_table_html = self._run_meta_table(report)
        suites_html = self._suites_section(
            report, include_passed, include_http_body, max_body_chars,
        )
        loose_html = self._loose_scenarios_section(
            report, include_passed, include_http_body, max_body_chars,
        )

        return (
            '<body>\n'
            f'<h1>{title}</h1>\n'
            f'<div class="meta">{" &middot; ".join(meta_parts) or "(no meta)"}</div>\n'
            f'{summary_html}\n'
            f'{meta_table_html}\n'
            f'{suites_html}\n'
            f'{loose_html}\n'
            '<footer>Generated by gimbal-test-report plugin · v2 full-info</footer>\n'
            '</body>'
        )

    # ── Run-level meta table ──
    def _run_meta_table(self, report: RunReport) -> str:
        if not report.meta:
            return ""
        rows = "\n".join(
            f'      <tr><th>{html.escape(k)}</th>'
            f'<td class="mono">{html.escape(_truncate(v, 200))}</td></tr>'
            for k, v in sorted(report.meta.items())
        )
        return (
            '<h2>Run meta</h2>\n'
            '<table class="kv-table">\n'
            f'  <tbody>\n{rows}\n  </tbody>\n'
            '</table>'
        )

    # ── Suites ──
    def _suites_section(
        self,
        report: RunReport,
        include_passed: bool,
        include_http_body: bool,
        max_body_chars: int,
    ) -> str:
        if not report.suites:
            return ""
        parts = ['<h2>Suites</h2>']
        for su in report.suites.values():
            parts.append(self._suite_block(
                su, include_passed, include_http_body, max_body_chars,
            ))
        return "\n".join(parts)

    def _suite_block(
        self,
        su: SuiteReport,
        include_passed: bool,
        include_http_body: bool,
        max_body_chars: int,
    ) -> str:
        name = html.escape(su.suite_name)
        sid = html.escape(su.suite_id)
        totals = (
            f'{su.total} scenarios '
            f'(<span style="color:{_STATUS_COLOR["passed"]}">{su.passed} passed</span> · '
            f'<span style="color:{_STATUS_COLOR["failed"]}">{su.failed} failed</span> · '
            f'<span style="color:{_STATUS_COLOR["error"]}">{su.errored} error</span>)'
        )

        sc_html_parts = []
        for sc in su.scenarios.values():
            sc_html_parts.append(self._scenario_block(
                sc, include_passed, include_http_body, max_body_chars,
            ))
        sc_html = "\n".join(sc_html_parts) if sc_html_parts else (
            '<p class="empty">No scenarios in this suite.</p>'
        )

        return (
            '<details class="suite" open>\n'
            f'  <summary>{name} '
            f'<span style="color:#666;font-weight:400">— {sid} · {totals}</span>'
            f' {_badge(su.status)}</summary>\n'
            f'  {sc_html}\n'
            '</details>'
        )

    # ── Loose scenarios (no suite) ──
    def _loose_scenarios_section(
        self,
        report: RunReport,
        include_passed: bool,
        include_http_body: bool,
        max_body_chars: int,
    ) -> str:
        if not report._loose_scenarios:
            return ""
        parts = ['<h2>Scenarios (no suite)</h2>']
        for sc in report._loose_scenarios.values():
            parts.append(self._scenario_block(
                sc, include_passed, include_http_body, max_body_chars,
            ))
        return "\n".join(parts)

    # ── Scenario block ──
    def _scenario_block(
        self,
        sc: ScenarioReport,
        include_passed: bool,
        include_http_body: bool,
        max_body_chars: int,
    ) -> str:
        name = html.escape(sc.scenario_name)
        sid = html.escape(sc.scenario_id)
        totals = (
            f'{sc.total} steps '
            f'(<span style="color:{_STATUS_COLOR["passed"]}">{sc.passed} passed</span> · '
            f'<span style="color:{_STATUS_COLOR["failed"]}">{sc.failed} failed</span> · '
            f'<span style="color:{_STATUS_COLOR["error"]}">{sc.errored} error</span>)'
        )

        rows: list[str] = []
        for st in sc.steps.values():
            if not include_passed and st.status == "passed":
                continue
            rows.append(self._step_block(
                st, include_http_body, max_body_chars,
            ))
        if not rows:
            rows.append('<p class="empty">No steps (or all filtered).</p>')

        meta_html = self._scenario_meta_block(sc)

        return (
            '<details open>\n'
            f'  <summary>{name} '
            f'<span style="color:#666;font-weight:400">— {sid} · {totals}</span>'
            f' {_badge(sc.status)}</summary>\n'
            f'  {meta_html}\n'
            f'  {"".join(rows)}\n'
            '</details>'
        )

    def _scenario_meta_block(self, sc: ScenarioReport) -> str:
        if not sc.meta:
            return ""
        items = []
        for k, v in sorted(sc.meta.items()):
            items.append(
                f'<span style="margin-right:12px">'
                f'<b>{html.escape(k)}</b>: {html.escape(_truncate(v, 80))}'
                f'</span>'
            )
        return (
            '<div style="margin:6px 0 10px 0;font-size:12px;color:#555">'
            f'{"".join(items)}</div>'
        )

    # ── Step card ─────────────────────────────────────────────
    def _step_block(
        self,
        st: StepReport,
        include_http_body: bool,
        max_body_chars: int,
    ) -> str:
        """渲染一张 step 卡片（v3 重构）。

        结构：
          ┌─ step-card ────────────────────────────────────┐
          │ ▶ Step name                 [status]  200ms    │  ← header 行
          │   s1 · asserts 0/1 · promotions 1              │  ← meta 行
          │ ─────────────────────────────────────────────  │  ← divider
          │ ▾ Strategy · http · ⚡ 2 retries               │  ← section 1
          │   └─ KV 表                                    │
          │ ─────────────────────────────────────────────  │  ← divider
          │ ▾ HTTP exchanges (1)                           │  ← section 2
          │   └─ 行表                                     │
          │ ─────────────────────────────────────────────  │  ← divider
          │ ▾ Variable promotions (1)                      │  ← section 3
          │   └─ 行表                                     │
          │ ─────────────────────────────────────────────  │  ← divider
          │ Failure block                                  │  ← section 4（红色背景）
          └────────────────────────────────────────────────┘
        """
        name = html.escape(st.step_name)
        sid = html.escape(st.step_id)
        dur = html.escape(_fmt_ms(st.duration_ms))

        # 头部：name + status + duration + id
        header = (
            '<div class="step-header">'
            f'<div class="step-name">{name}'
            f'<span style="color:#999;font-size:11px;font-weight:400;'
            f'margin-left:8px">{sid}</span>'
            '</div>'
            f'<div class="step-status">{_badge(st.status)}</div>'
            f'<div class="step-duration">{dur}</div>'
            '</div>'
        )

        # meta 行：asserts / promotions / description
        meta_bits: list[str] = []
        if st.assertion_count:
            meta_bits.append(
                f'asserts: {st.assertion_passed}/{st.assertion_count}'
            )
        if st.promotion_count:
            meta_bits.append(
                f'<span style="color:#00838f">'
                f'promotions: {st.promotion_count}</span>'
            )
        meta_html = ""
        if meta_bits:
            meta_html = (
                '<div class="step-meta">'
                + " &middot; ".join(meta_bits)
                + '</div>'
            )
        if st.description:
            meta_html += (
                '<div class="step-meta">'
                f'{html.escape(st.description)}'
                '</div>'
            )

        # sections：每个 sub-block 一个独立的 .step-section
        sections: list[str] = []
        if st.strategy_kind or st.strategy_spec or st.retry_count:
            # v4：_strategy_section 可能产生多个 section（step config + 每个
            # strategy 一张），用 extend 而不是 append。
            sections.extend(self._strategy_sections(st, max_body_chars))
        if st.error_brief or st.phase or st.traceback:
            sections.append(self._failure_section(st, max_body_chars))
        if st.http_exchanges:
            sections.append(self._http_section(
                st.http_exchanges, include_http_body, max_body_chars,
            ))
        if st.promotions:
            sections.append(self._promotion_section(st.promotions))

        return (
            '<div class="step-card">'
            f'{header}{meta_html}{"".join(sections)}'
            '</div>'
        )

    def _strategy_sections(self, st: StepReport, max_body_chars: int) -> list[str]:
        """v4：把 strategy_spec 拆成多个 section：

        - **Step config**（一个）：kind / description / api（请求的 method / path /
          headers / body）等 step 级别的 KV。注意 ``strategy`` 列表会从这里抠掉，
          避免与下方独立的 strategy 块重复。
        - **每个 strategy 一项**（多个）：spec["strategy"] 列表里的每个 dict 是一
          个独立的策略（assertion / extract / verify ...），各自一张折叠 section，
          summary 用 ``name``（如 ``assert_http_status_eq_200``）或退化的 ``kind``。
        - 没有 spec 时退化成单 section，只显示 kind。

        返回 ``list[str]``，可能含多个 ``<div class="step-section">``。
        """
        out: list[str] = []
        # 抠出 strategy 列表，把剩余 spec 当作 step config
        spec = dict(st.strategy_spec or {})
        strategies: list[Any] = []
        if isinstance(spec.get("strategy"), list):
            strategies = spec.pop("strategy")

        # 1) Step config section（只在有内容时出现）
        config_rows: list[str] = []
        if spec:
            config_rows.extend(self._strategy_spec_rows(spec, max_body_chars))
        elif st.strategy_kind:
            # 兼容老路径：spec 空但 kind 非空 → 至少展示一行 kind
            config_rows.append(self._strategy_spec_row(
                "kind", st.strategy_kind, max_body_chars, 0,
            ))

        if config_rows:
            out.append(self._strategy_step_config_section(
                st, len(strategies), config_rows,
            ))

        # 2) 每个 strategy 一张独立的折叠 section
        for i, s in enumerate(strategies, 1):
            out.append(self._strategy_item_section(
                i, s, max_body_chars,
            ))

        # 3) 兜底：spec / kind / strategy 都为空，但 retry_count>0 → 显示一个空
        # summary 让用户至少看到"重试过"。
        if not out:
            out.append(self._strategy_summary_only_section(st, 0))

        return out

    def _strategy_step_config_section(
        self,
        st: StepReport,
        strategy_count: int,
        config_rows: list[str],
    ) -> str:
        """Step config section —— kind / description / api（请求的 method、path、
        headers、body）等 step 级别的 KV。summary 包含 step 整体的策略名 + retry，
        strategy 计数也一并显示（让用户知道下方还有 N 个独立 strategy）。
        """
        bits: list[str] = ["Strategy"]
        if st.strategy_kind:
            bits.append(html.escape(st.strategy_kind))
        if strategy_count:
            noun = "strategy" if strategy_count == 1 else "strategies"
            bits.append(f"{strategy_count} {noun}")
        if st.retry_count:
            retry_noun = "retry" if st.retry_count == 1 else "retries"
            bits.append(f'⚡ {st.retry_count} {retry_noun}')
        summary = " · ".join(bits)

        return (
            '<div class="step-section">'
            '<details><summary style="font-weight:500">'
            f'{summary}</summary>'
            '<table class="subtable">'
            f'<tbody>{"".join(config_rows)}</tbody>'
            '</table>'
            '</details>'
            '</div>'
        )

    def _strategy_item_section(
        self,
        index: int,
        strategy: Any,
        max_body_chars: int,
    ) -> str:
        """单个 strategy 的折叠 section。summary 用 ``name`` 字段（assertion /
        extract 的语义化名字），没有就退到 ``[index] · kind``。
        """
        if not isinstance(strategy, dict):
            # 兜底：list 里有非 dict 项 —— 仍然展示但用通用标签
            return (
                '<div class="step-section">'
                '<details><summary style="font-weight:500">'
                f'Strategy [{index}]</summary>'
                '<table class="subtable"><tbody>'
                f'{self._strategy_spec_row("(value)", strategy, max_body_chars, 0)}'
                '</tbody></table>'
                '</details>'
                '</div>'
            )

        name = strategy.get("name") or ""
        kind = strategy.get("kind") or "unknown"
        if name:
            summary = f'Strategy · {html.escape(str(name))}'
            if kind and str(kind) != str(name):
                summary += f' · <span style="color:#666">{html.escape(str(kind))}</span>'
        else:
            summary = f'Strategy [{index}] · {html.escape(str(kind))}'

        # Phase / enabled / soft 等高亮字段展示在 summary 后面
        extras: list[str] = []
        phase = strategy.get("phase")
        if phase:
            extras.append(
                f'<span style="color:#666;font-size:11px;margin-left:8px">'
                f'phase: {html.escape(str(phase))}</span>'
            )
        if strategy.get("enabled") is False:
            extras.append(
                '<span style="color:#999;font-size:11px;margin-left:8px">'
                'disabled</span>'
            )
        if strategy.get("soft") is True:
            extras.append(
                '<span style="color:#0277bd;font-size:11px;margin-left:8px">'
                'soft</span>'
            )
        if strategy.get("onFailure"):
            extras.append(
                f'<span style="color:#c62828;font-size:11px;margin-left:8px">'
                f'onFailure: {html.escape(str(strategy["onFailure"]))}</span>'
            )

        # 内容：每个 strategy 一张 subtable（KV 形式），不缩进
        rows = self._strategy_spec_rows(strategy, max_body_chars, indent=0)
        return (
            '<div class="step-section">'
            '<details><summary style="font-weight:500">'
            f'{summary}{"".join(extras)}</summary>'
            '<table class="subtable">'
            f'<tbody>{"".join(rows)}</tbody>'
            '</table>'
            '</details>'
            '</div>'
        )

    def _strategy_summary_only_section(
        self, st: StepReport, strategy_count: int,
    ) -> str:
        """spec / kind 都空，但 retry_count>0（或 strategy_count>0 但 spec 异常），
        也要展示一条 summary 让用户看到。
        """
        bits: list[str] = ["Strategy"]
        if st.strategy_kind:
            bits.append(html.escape(st.strategy_kind))
        if strategy_count:
            noun = "strategy" if strategy_count == 1 else "strategies"
            bits.append(f"{strategy_count} {noun}")
        if st.retry_count:
            retry_noun = "retry" if st.retry_count == 1 else "retries"
            bits.append(f'⚡ {st.retry_count} {retry_noun}')
        summary = " · ".join(bits)
        return (
            '<div class="step-section">'
            '<details><summary style="font-weight:500">'
            f'{summary}</summary></details>'
            '</div>'
        )

    def _strategy_spec_rows(
        self, spec: Any, max_body_chars: int, indent: int = 0,
    ) -> list[str]:
        """递归把 strategy_spec 展开为 KV 行。叶子值用 _dump_json 序列化。
        indent 控制缩进（0 不缩进，1 缩进 16px ...），与 HTTP subtable 的视觉层级一致。
        """
        rows: list[str] = []
        if not isinstance(spec, dict):
            # 顶层不是 dict —— 兜底
            rows.append(self._strategy_spec_row("(value)", spec, max_body_chars, indent))
            return rows
        for k, v in spec.items():
            rows.extend(
                self._strategy_spec_kv(str(k), v, max_body_chars, indent)
            )
        return rows

    def _strategy_spec_kv(
        self, key: str, value: Any, max_body_chars: int, indent: int,
    ) -> list[str]:
        if isinstance(value, dict):
            # 嵌套对象：先打一行 "(key):"，然后缩进展开它的子项
            rows: list[str] = []
            pad = f' style="padding-left:{indent * 16 + 8}px"'
            rows.append(
                f'<tr><th{pad}>{html.escape(key)}</th>'
                f'<td style="padding-left:{indent * 16 + 8}px;color:#666">'
                '<i>(nested)</i></td></tr>'
            )
            for sk, sv in value.items():
                rows.extend(
                    self._strategy_spec_kv(sk, sv, max_body_chars, indent + 1)
                )
            return rows
        if isinstance(value, list):
            if not value:
                return [self._strategy_spec_row(key, "[]", max_body_chars, indent)]
            if all(not isinstance(v, (dict, list)) for v in value):
                # 简单 list —— 直接 inline
                text = ", ".join(_dump_json(v, 200) for v in value)
                return [self._strategy_spec_row(
                    key, f"[{text}]", max_body_chars, indent,
                )]
            # 嵌套 list —— 每项一行
            rows = [self._strategy_spec_row(
                key, f"(list, {len(value)} items)", max_body_chars, indent,
            )]
            for i, item in enumerate(value):
                rows.extend(
                    self._strategy_spec_kv(f"[{i}]", item, max_body_chars, indent + 1)
                )
            return rows
        # 叶子
        return [self._strategy_spec_row(key, value, max_body_chars, indent)]

    def _strategy_spec_row(
        self, key: str, value: Any, max_body_chars: int, indent: int,
    ) -> str:
        pad_attr = f' style="padding-left:{indent * 16 + 8}px"' if indent else ""
        return (
            f'<tr><th{pad_attr}>{html.escape(key)}</th>'
            f'<td{pad_attr}>{html.escape(_dump_json(value, max_body_chars))}</td></tr>'
        )

    def _failure_section(self, st: StepReport, max_body_chars: int) -> str:
        """v3：包在 ``<div class="step-section failure-section">`` 里。

        ``failure-section`` 这个额外 class 给一张红色背景 + 左侧红色 border-left，
        与 step-card 内其他 section 区分开来（红底提示错误）。
        """
        bits: list[str] = []
        if st.phase:
            bits.append(
                f'<span style="color:#c62828;font-size:11px">'
                f'phase: {html.escape(st.phase)}</span>'
            )
        if st.error_brief:
            bits.append(
                f'<div class="mono" style="color:#c62828;margin-top:4px">'
                f'{html.escape(_truncate(st.error_brief, max_body_chars))}</div>'
            )
        if st.traceback:
            bits.append(
                f'<pre>{html.escape(_truncate(st.traceback, max_body_chars))}</pre>'
            )
        return (
            '<div class="step-section failure-section">'
            f'{"".join(bits)}'
            '</div>'
        )

    def _http_section(
        self,
        exchanges: List[HttpExchange],
        include_http_body: bool,
        max_body_chars: int,
    ) -> str:
        """v3：包在 ``<div class="step-section">`` 里，<details> 在内部可折叠。"""
        rows: list[str] = []
        for i, ex in enumerate(exchanges, 1):
            rows.append(self._http_row(i, ex, include_http_body, max_body_chars))
        return (
            '<div class="step-section">'
            '<details><summary style="font-weight:500">'
            f'HTTP exchanges ({len(exchanges)})</summary>'
            '<table class="subtable">'
            '<thead><tr><th>#</th><th>Method</th><th>URL</th>'
            '<th>Status</th><th class="duration">Duration</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody>'
            '</table>'
            + "".join(
                self._http_body_section(i, ex, include_http_body, max_body_chars)
                for i, ex in enumerate(exchanges, 1)
            )
            + '</details>'
            '</div>'
        )

    def _http_row(
        self,
        i: int,
        ex: HttpExchange,
        include_http_body: bool,
        max_body_chars: int,
    ) -> str:
        status = ex.status_code if ex.status_code is not None else "—"
        status_color = ""
        if isinstance(ex.status_code, int):
            if 200 <= ex.status_code < 300:
                status_color = _STATUS_COLOR["passed"]
            elif ex.status_code >= 400:
                status_color = _STATUS_COLOR["failed"]
        dur = _fmt_ms(ex.duration_ms) if ex.duration_ms is not None else "—"
        return (
            '<tr>'
            f'<td>{i}</td>'
            f'<td><b>{html.escape(ex.request_method)}</b></td>'
            f'<td class="mono">{html.escape(ex.request_url)}</td>'
            f'<td style="color:{status_color or "#212121"};font-weight:600">'
            f'{html.escape(str(status))}</td>'
            f'<td class="duration">{html.escape(dur)}</td>'
            '</tr>'
        )

    def _http_body_section(
        self,
        i: int,
        ex: HttpExchange,
        include_http_body: bool,
        max_body_chars: int,
    ) -> str:
        if not include_http_body:
            return ""
        req = _dump_json(ex.request_body, max_body_chars)
        resp = _dump_json(ex.response_body, max_body_chars)
        if not req and not resp:
            return ""
        return (
            '<div style="margin:4px 0 10px 12px;font-size:12px">'
            f'<div><b>Request #{i} body</b></div>'
            f'<pre>{html.escape(req) if req else "(empty)"}</pre>'
            f'<div><b>Response #{i} body</b></div>'
            f'<pre>{html.escape(resp) if resp else "(empty)"}</pre>'
            '</div>'
        )

    def _promotion_section(self, promos: List[VariablePromotion]) -> str:
        """v3：包在 ``<div class="step-section">`` 里，<details> 在内部可折叠。"""
        rows = []
        for p in promos:
            overwrote = " ⚠ overwrite" if p.overwrote_previous else ""
            reason = (
                f' <span style="color:#666">— {html.escape(p.reason)}</span>'
                if p.reason else ""
            )
            rows.append(
                '<tr>'
                f'<td><code>{html.escape(p.key)}</code></td>'
                f'<td>{html.escape(p.from_layer)} → {html.escape(p.to_layer)}'
                f'<span style="color:#00838f">{overwrote}</span></td>'
                f'<td><code>{html.escape(p.by_step_id)}</code></td>'
                f'<td style="color:#666">{reason}</td>'
                '</tr>'
            )
        return (
            '<div class="step-section">'
            '<details><summary style="font-weight:500">'
            f'Variable promotions ({len(promos)})</summary>'
            '<table class="subtable">'
            '<thead><tr><th>Key</th><th>Path</th><th>By step</th>'
            '<th>Reason</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody>'
            '</table>'
            '</details>'
            '</div>'
        )


__all__ = ["HtmlRenderer"]