"""builtin/definition_reporter.py — 定义驱动的报告器(B5/P3-06)。

消费 ``schema/report_definition.ReportDefinition``:选择面(P1-04 同源
匹配)决定哪些事件进报告,投影面(JSONPath)决定提取哪些字段,呈现面
(html/markdown/table)决定输出格式。现有报告器(console/json/junit/
allure/html)保留;本报告器是「不写代码定制报告」的入口。

replay 一致性(P3-06 验收):事件经 ``gimbal events replay`` 重放后,
同一份定义产出的报告与原运行一致(时间戳字段除外)—— 选择/投影/
呈现全部是事件流的纯函数,不依赖运行时状态。
"""
from __future__ import annotations

import fnmatch
import json
from pathlib import Path
from typing import Any

from gimbal.core.runner import RunResult
from gimbal.log import get_logger
from gimbal.reporter.base import ReportArtifact, ReporterBase
from gimbal.schema.report_definition import ReportDefinition

logger = get_logger(__name__)


class DefinitionReporter(ReporterBase):
    """按 ``ReportDefinition`` 产出报告(html/markdown/table)。

    配置(gimbal.yaml ``plugin_configs`` 或 ``--reporter definition:<path>``):
        definition_file: 报告定义 JSON 文件路径(必填)
    """

    name = "definition"

    def __init__(self) -> None:
        self._definition: ReportDefinition | None = None
        self._matched: list[dict[str, Any]] = []

    def begin(self, ctx) -> None:
        """读定义文件 + 订阅全部事件(self._on_event 过滤)。"""
        import json as _json
        path_str = str(ctx.user("definition_file", ""))
        if not path_str:
            raise ValueError(
                "definition reporter 需要 definition_file 配置"
                "(JSON 文件路径,内容 = ReportDefinition)")
        try:
            raw = _json.loads(Path(path_str).read_text(encoding="utf-8"))
            self._definition = ReportDefinition.model_validate(raw)
        except Exception as e:
            raise ValueError(f"报告定义文件无效: {path_str}: {e}") from e
        self._matched = []
        # 订阅全部事件(选择面在 _on_event 内过滤)
        from gimbal.events.types import EventType
        for et in EventType:
            ctx.bus.subscribe(self._on_event, event_type=et.value,
                              mode=ctx.subscription_mode,
                              plugin_name=f"reporter.{self.name}",
                              priority=ctx.subscription_priority)
        super().begin(ctx)

    def _on_event(self, event) -> None:
        """选择面:事件类型/模式 + where 匹配(P1-04 同源)。"""
        if self._definition is None:
            return
        et = getattr(event, "event_type", "") or ""
        sel = self._definition.selection
        if not any(fnmatch.fnmatchcase(et, p) for p in sel.events):
            return
        for key, pattern in sel.where.items():
            value = getattr(event, key, None)
            if value is None or not fnmatch.fnmatchcase(str(value), pattern):
                return
        # 投影面:提取字段
        payload = event.model_dump(mode="json") if hasattr(event, "model_dump") else {}
        row: dict[str, Any] = {}
        proj = self._definition.projection
        source = payload if proj.source == "payload" else {}
        for field_path in proj.fields:
            if proj.source == "event":
                # 事件对象属性直取(dot path)
                obj = event
                for part in field_path.split("."):
                    obj = getattr(obj, part, None)
                    if obj is None:
                        break
                row[field_path] = obj
            else:
                # payload JSONPath
                row[field_path] = _dot_get(source, field_path)
        row["_seq"] = getattr(event, "seq", 0)
        row["_event_type"] = et
        self._matched.append(row)

    def finalize(self, run_result: RunResult, ctx) -> ReportArtifact:
        """呈现面:渲染为 html/markdown/table 并落盘为工件。"""
        if self._definition is None:
            return ReportArtifact(name=self.name, path=None,
                                  content="no definition loaded",
                                  media_type="text/plain")
        pres = self._definition.presentation
        if pres.format == "html":
            content, ext, media = self._render_html(run_result), "html", "text/html"
        elif pres.format == "markdown":
            content, ext, media = self._render_markdown(run_result), "md", "text/markdown"
        else:
            content, ext, media = self._render_table(run_result), "txt", "text/plain"

        out_path = ctx.report_dir / f"report-{self._definition.name}.{ext}"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
        return ReportArtifact(
            name=self.name, path=out_path, media_type=media,
            metadata={"definition": self._definition.name,
                      "matched": len(self._matched),
                      "format": pres.format},
        )

    def _render_html(self, run_result: RunResult) -> str:
        pres = self._definition.presentation
        fields = self._definition.projection.fields
        rows_html = "\n".join(
            "<tr>" + "".join(
                f"<td>{_esc(str(r.get(f, '')))}</td>" for f in fields)
            + "</tr>"
            for r in sorted(self._matched, key=lambda x: x.get("_seq", 0)))
        header = "".join(f"<th>{_esc(f)}</th>" for f in fields)
        return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{_esc(pres.title)}</title>
<style>body{{font-family:system-ui,sans-serif;margin:24px}}
table{{border-collapse:collapse;width:100%;font-size:13px}}
th,td{{border:1px solid #e4e4e7;padding:6px 10px;text-align:left}}
th{{background:#f4f4f5;font-weight:600}}
tr:nth-child(even){{background:#fafafa}}</style></head>
<body><h1>{_esc(pres.title)}</h1>
<p>exit_code={run_result.exit_code} total={run_result.total}
passed={run_result.passed} failed={run_result.failed}</p>
<table><thead><tr>{header}</tr></thead><tbody>{rows_html}</tbody></table>
</body></html>"""

    def _render_markdown(self, run_result: RunResult) -> str:
        pres = self._definition.presentation
        fields = self._definition.projection.fields
        lines = [f"# {pres.title}", "",
                 f"exit_code={run_result.exit_code} "
                 f"passed={run_result.passed}/{run_result.total}", "",
                 "| " + " | ".join(fields) + " |",
                 "|" + "---|" * len(fields)]
        for r in sorted(self._matched, key=lambda x: x.get("_seq", 0)):
            lines.append("| " + " | ".join(
                str(r.get(f, "")).replace("|", "\\|") for f in fields) + " |")
        return "\n".join(lines) + "\n"

    def _render_table(self, run_result: RunResult) -> str:
        fields = self._definition.projection.fields
        widths = [max(len(f), *(len(str(r.get(f, ""))) for r in self._matched))
                  for f in fields]
        sep = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
        header = "|" + "|".join(
            f" {f:<{w}} " for f, w in zip(fields, widths)) + "|"
        lines = [sep, header, sep]
        for r in sorted(self._matched, key=lambda x: x.get("_seq", 0)):
            lines.append("|" + "|".join(
                f" {str(r.get(f, '')):<{w}} "
                for f, w in zip(fields, widths)) + "|")
        lines.append(sep)
        return "\n".join(lines) + "\n"


def _dot_get(obj: Any, path: str) -> Any:
    """dot-path 取值($.a.b → obj['a']['b'];$ 根 → obj)。"""
    parts = path.lstrip("$").lstrip(".").split(".")
    cur = obj
    for part in parts:
        if not part:
            continue
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
        if cur is None:
            return None
    return cur


def _esc(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def factory(user_config: dict) -> DefinitionReporter:
    return DefinitionReporter()
