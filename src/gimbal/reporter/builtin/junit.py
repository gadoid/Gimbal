"""builtin/junit.py — JUnitReporter（CI 集成）。"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gimbal.core.runner import RunResult
from gimbal.reporter.base import ReportArtifact, ReporterBase


class JUnitReporter(ReporterBase):
    """JUnit / xUnit 格式报告（被 Jenkins / GitLab CI / GitHub Actions 直接消费）。

    顶层 <testsuites>，每个 scenario 一个 <testsuite>，
    每个 step 视作 <testcase>。
    """

    name = "junit"

    def __init__(self) -> None:
        self._suite_name: str = "Gimbal"

    def begin(self, ctx) -> None:
        self._suite_name = str(ctx.user("suite_name", "Gimbal"))
        super().begin(ctx)

    def finalize(self, run_result: RunResult, ctx) -> ReportArtifact:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        out_path = ctx.report_dir / f"junit-{ts}.xml"

        testsuites = ET.Element("testsuites")
        # CI 友好：每个 scenario 一个 <testsuite>
        for d in run_result.details or []:
            sid = d.get("scenario_id", "unknown")
            status = d.get("status", "passed")
            dur = float(d.get("duration_ms", 0) or 0)
            module = d.get("module", "default")

            suite = ET.SubElement(testsuites, "testsuite")
            suite.set("name", f"{self._suite_name}.{sid}")
            suite.set("tests", "1")
            suite.set("skipped", "0" if status != "skipped" else "1")
            suite.set("failures", "0" if status not in ("failed", "error") else "1")
            suite.set("errors", "1" if status == "error" else "0")
            suite.set("time", f"{dur / 1000.0:.3f}")
            suite.set("timestamp", str(d.get("started_at", "")))
            suite.set("hostname", "gimbal-runner")

            case = ET.SubElement(suite, "testcase")
            case.set("name", sid)
            case.set("classname", module)
            case.set("time", f"{dur / 1000.0:.3f}")

            if status in ("failed", "error"):
                fail = ET.SubElement(case, "failure" if status == "failed" else "error")
                fail.set("type", status)
                fail.set("message", d.get("error", ""))
                fail.text = (d.get("traceback", "") or d.get("error", ""))[:4000]
            elif status == "skipped":
                ET.SubElement(case, "skipped")

        # 顶层 suites 汇总
        root_count = len(testsuites.findall("testsuite"))
        testsuites.set("tests", str(root_count))
        testsuites.set("failures", str(run_result.failed))
        testsuites.set("errors", str(run_result.error))
        testsuites.set("skipped", str(run_result.skipped))
        testsuites.set("time", f"{_total_seconds(run_result):.3f}")

        # 写入（pretty 模式）
        ET.indent(testsuites, space="  ", level=0)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(testsuites, encoding="unicode"),
            encoding="utf-8",
        )
        return ReportArtifact(
            name=self.name,
            path=out_path,
            media_type="application/xml",
            metadata={
                "suites": root_count,
                "tests": run_result.total,
                "failures": run_result.failed,
            },
        )


def _total_seconds(run_result: RunResult) -> float:
    return sum(float(d.get("duration_ms", 0) or 0) for d in (run_result.details or [])) / 1000.0


def factory(user_config: dict[str, Any]) -> JUnitReporter:
    return JUnitReporter()
