"""builtin/allure_reporter.py - AllureReporter (Allure 2 JSON protocol)."""
from __future__ import annotations
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from gimbal.core.runner import RunResult
from gimbal.events.types import (
    FrameworkEvent, HttpRequestEvent, HttpResponseEvent,
    ScenarioEndEvent, ScenarioStartEvent, StepEndEvent, StepFailedEvent,
    StepStartEvent, VariablePromotedEvent,
)
from gimbal.reporter.base import ReportArtifact, ReporterBase


def _now() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _uid() -> str:
    return uuid.uuid4().hex


class AllureReporter(ReporterBase):
    name = "allure"
    interested_events: tuple = (
        "scenario.start", "scenario.end",
        "step.start", "step.end",
        "step.failed", "http.request",
        "http.response", "variable.promoted",
    )

    def __init__(self) -> None:
        self._results_dir: Path = Path("allure-results")
        self._scenario_meta: dict = {}
        self._current_step_uid: str = ""

    def begin(self, ctx) -> None:
        self._results_dir = ctx.report_dir / "allure-results"
        self._results_dir.mkdir(parents=True, exist_ok=True)
        super().begin(ctx)

    def on_event(self, event: FrameworkEvent) -> None:
        try:
            if isinstance(event, ScenarioStartEvent):
                self._open_scenario(event)
            elif isinstance(event, StepStartEvent):
                self._open_step(event)
            elif isinstance(event, StepEndEvent):
                self._close_step(event, status="passed")
            elif isinstance(event, StepFailedEvent):
                self._close_step_failed(event)
            elif isinstance(event, HttpRequestEvent):
                self._attach_request(event)
            elif isinstance(event, HttpResponseEvent):
                self._attach_response(event)
            elif isinstance(event, ScenarioEndEvent):
                self._close_scenario(event)
            elif isinstance(event, VariablePromotedEvent):
                self._record_promotion(event)
        except Exception:
            pass

    def finalize(self, run_result, ctx) -> ReportArtifact:
        summary_path = self._results_dir / "gimbal-summary.json"
        summary_path.write_text(
            json.dumps({
                "run_id": ctx.framework_ctx.run_id,
                "env": ctx.framework_ctx.environment,
                "mode": ctx.framework_ctx.mode,
                "summary": {
                    "total": run_result.total,
                    "passed": run_result.passed,
                    "failed": run_result.failed,
                    "error": run_result.error,
                    "skipped": run_result.skipped,
                },
            }, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        return ReportArtifact(
            name=self.name,
            path=summary_path,
            media_type="application/json",
            metadata={"results_dir": str(self._results_dir)},
        )

    def _open_scenario(self, ev):
        uid = _uid()
        self._scenario_meta[ev.scenario_id] = {"uid": uid, "name": ev.scenario_name, "step_uids": []}
        self._write_json(f"{uid}-container.json", {"uuid": uid, "name": ev.scenario_name, "children": []})

    def _close_scenario(self, ev):
        meta = self._scenario_meta.pop(ev.scenario_id, None)
        if not meta: return
        path = self._results_dir / f"{meta['uid']}-container.json"
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                data["children"] = meta["step_uids"]
                data["stop"] = _now()
                self._write_json(f"{meta['uid']}-container.json", data)
            except Exception:
                pass

    def _open_step(self, ev):
        uid = _uid()
        self._current_step_uid = uid
        result = {
            "uuid": uid,
            "name": ev.step_name or ev.step_id,
            "status": "running",
            "stage": "running",
            "start": _now(),
            "labels": [{"name": "framework", "value": "gimbal"}, {"name": "step_id", "value": ev.step_id}],
            "steps": [], "attachments": [], "parameters": [],
        }
        if ev.description:
            result["description"] = ev.description
        meta = self._scenario_meta.get(ev.scenario_id or "")
        if meta is not None: meta["step_uids"].append(uid)
        self._write_json(f"{uid}-result.json", result)

    def _close_step(self, ev, status):
        uid = self._current_step_uid
        if not uid: return
        path = self._results_dir / f"{uid}-result.json"
        if not path.exists(): return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            data["status"] = status
            data["stage"] = "finished"
            data["stop"] = _now()
            self._write_json(f"{uid}-result.json", data)
        except Exception:
            pass

    def _close_step_failed(self, ev):
        uid = self._current_step_uid
        if not uid: return
        path = self._results_dir / f"{uid}-result.json"
        if not path.exists(): return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            data["status"] = "failed" if ev.phase != "error" else "broken"
            data["stage"] = "finished"
            data["stop"] = _now()
            data["statusDetails"] = {"message": ev.error[:1000], "trace": (ev.error + "\n")[:2000]}
            self._write_json(f"{uid}-result.json", data)
        except Exception:
            pass

    def _attach_request(self, ev):
        self._attach_text("request.txt", f"{ev.method} {ev.url}\n\n{ev.request_body!r}")

    def _attach_response(self, ev):
        self._attach_text(f"response-{ev.status_code}.txt", f"status={ev.status_code} duration_ms={ev.duration_ms:.2f}\n\n{ev.response_body!r}")

    def _record_promotion(self, ev):
        pass

    def _write_json(self, filename, obj):
        path = self._results_dir / filename
        path.write_text(json.dumps(obj, ensure_ascii=False, default=str), encoding="utf-8")

    def _attach_text(self, name, content):
        if not self._current_step_uid: return
        uid = _uid()
        path = self._results_dir / f"{uid}-attachment.txt"
        path.write_text(content, encoding="utf-8")
        result_path = self._results_dir / f"{self._current_step_uid}-result.json"
        if result_path.exists():
            try:
                data = json.loads(result_path.read_text(encoding="utf-8"))
                data.setdefault("attachments", []).append({"name": name, "source": f"{uid}-attachment.txt", "type": "text/plain"})
                self._write_json(f"{self._current_step_uid}-result.json", data)
            except Exception:
                pass


def factory(user_config):
    return AllureReporter()
