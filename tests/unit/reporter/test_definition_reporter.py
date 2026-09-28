"""P3-06/B5:定义驱动报告器(选择+投影+呈现;replay 一致性)。"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

import pytest

from gimbal.core.runner import RunResult
from gimbal.reporter.builtin.definition_reporter import DefinitionReporter, factory


class _Ctx:
    """最小 ReportContext 替身。"""
    subscription_mode = None  # SYNC 缺省
    subscription_priority = 100
    subscription_ids: list = []

    def __init__(self, report_dir: Path, definition_file: Path):
        self.report_dir = report_dir
        self._def = {"definition_file": str(definition_file)}
        self.bus = _Bus()

    def user(self, key, default=None):
        return self._def.get(key, default)


class _Bus:
    def __init__(self):
        self._handlers = []
    def subscribe(self, handler, event_type=None, **kw):
        self._handlers.append((handler, event_type))

    def publish(self, event):
        for h, et in self._handlers:
            if et is None or h.__name__ == "_on_event":
                h(event)


DEF_HTML = {
    "name": "failures",
    "description": "失败步骤 + 请求体 + 响应字段",
    "selection": {"events": ["step.end"], "where": {"status": "failed"}},
    "projection": {
        "source": "payload",
        "fields": ["seq", "step_id", "status", "error_brief", "duration_ms"],
    },
    "presentation": {"format": "html", "title": "失败分析"},
}

DEF_MD = {
    "name": "all-steps",
    "selection": {"events": ["step.*"]},
    "projection": {"fields": ["seq", "event_type", "step_id"]},
    "presentation": {"format": "markdown", "title": "步骤时序"},
}


def _step_end(seq, status, step_id="s1", error=None):
    from gimbal.events.types import StepEndEvent
    return StepEndEvent(seq=seq, step_id=step_id, status=status,
                        duration_ms=5.0, error_brief=error)


def _run_reporter(definition: dict, events: list):
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        def_file = td / "def.json"
        def_file.write_text(json.dumps(definition), encoding="utf-8")
        ctx = _Ctx(td / "reports", def_file)
        (td / "reports").mkdir(exist_ok=True)
        rep = factory({})
        rep.begin(ctx)
        for ev in events:
            ctx.bus.publish(ev)
        result = RunResult(exit_code=1, total=1, failed=1)
        art = rep.finalize(result, ctx)
        content = (Path(art.path).read_text(encoding="utf-8")
                   if art.path else (art.content or ""))
        return art, content


class TestDefinitionReporter:

    def test_html_report_selects_failed_and_projects(self):
        events = [
            _step_end(1, "passed", "s1"),
            _step_end(2, "failed", "s2", error="timeout"),
        ]
        art, content = _run_reporter(DEF_HTML, events)
        assert art.path is not None and art.path.suffix == ".html"
        assert "失败分析" in content
        assert "s2" in content and "timeout" in content
        assert "s1" not in content or "passed" not in content.split("s2")[0].split("s1")[-1]

    def test_markdown_format(self):
        events = [_step_end(1, "passed"), _step_end(2, "failed")]
        art, content = _run_reporter(DEF_MD, events)
        assert art.path.suffix == ".md"
        assert content.startswith("# 步骤时序")
        assert "| seq" in content  # markdown 表头

    def test_where_filter_excludes_non_matching(self):
        events = [_step_end(1, "passed", "s-passed"), _step_end(2, "failed", "s-failed")]
        _, content = _run_reporter(DEF_HTML, events)
        # where status=failed → passed 事件不进报告(表体无 s-passed)
        body = content.split("<tbody>")[1] if "<tbody>" in content else content
        assert "s-failed" in body
        assert "s-passed" not in body

    def test_missing_definition_file_raises(self):
        rep = factory({})
        ctx = _Ctx(Path(tempfile.mkdtemp()), Path("nonexistent.json"))
        with pytest.raises(ValueError, match="报告定义文件无效"):
            rep.begin(ctx)

    def test_replay_consistency(self):
        """同一份事件流 → 同一报告(选择/投影/呈现都是纯函数)。"""
        events = [_step_end(1, "failed", "a"), _step_end(2, "failed", "b")]
        _, c1 = _run_reporter(DEF_MD, events)
        _, c2 = _run_reporter(DEF_MD, events)
        assert c1 == c2
