"""builtin/platform_uploader.py - PlatformUploader (HTTP 上传 artifact 到内部平台)."""
from __future__ import annotations
import base64
import json
import time
from pathlib import Path
from typing import Any
from gimbal.core.runner import RunResult
from gimbal.reporter.base import ReportArtifact, ReporterBase


class PlatformUploader(ReporterBase):
    """把本 run 的所有 ReportArtifact 上传到内部测试平台。

    配置示例 (gimbal.yaml):
        plugin_configs:
          platform_uploader:
            platform_url: https://test-platform.example.com/api/v1/runs
            api_token: xxx
            timeout: 30
            max_retries: 3
    """

    name = "platform_uploader"

    def __init__(self) -> None:
        self._platform_url: str = ""
        self._api_token: str = ""
        self._timeout: float = 30.0
        self._max_retries: int = 3

    def begin(self, ctx) -> None:
        self._platform_url = str(ctx.user("platform_url", ""))
        self._api_token = str(ctx.user("api_token", ""))
        self._timeout = float(ctx.user("timeout", 30.0))
        self._max_retries = int(ctx.user("max_retries", 3))
        # 不订阅事件
        super().begin(ctx)

    def finalize(self, run_result: RunResult, ctx) -> ReportArtifact:
        # 注意:此处拿不到所有 reporter 产出的 artifact 列表（runtime 暂未提供 collector），
        # 改为扫描 ctx.report_dir 下的常见文件类型（junit-*.xml / *.json / *.html）。
        artifacts = _collect_artifacts(ctx.report_dir)

        body = {
            "run_id": ctx.framework_ctx.run_id,
            "env": ctx.framework_ctx.environment,
            "mode": ctx.framework_ctx.mode,
            "framework_version": ctx.framework_ctx.framework_version,
            "summary": {
                "total": run_result.total,
                "passed": run_result.passed,
                "failed": run_result.failed,
                "error": run_result.error,
                "skipped": run_result.skipped,
                "exit_code": run_result.exit_code,
            },
            "artifacts": artifacts,
        }

        if not self._platform_url:
            # 未配置 URL：仅落盘请求体，便于调试
            debug_path = ctx.report_dir / "platform-upload-debug.json"
            debug_path.write_text(
                json.dumps(body, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            return ReportArtifact(
                name=self.name,
                path=debug_path,
                media_type="application/json",
                metadata={"uploaded": False, "reason": "platform_url not set"},
            )

        upload_url = self._do_upload(body)
        return ReportArtifact(
            name=self.name,
            path=None,
            content=json.dumps({"uploaded": True, "url": upload_url}, ensure_ascii=False),
            media_type="application/json",
            metadata={"uploaded": True, "upload_url": upload_url},
        )

    def _do_upload(self, body: dict) -> str:
        import urllib.request
        import urllib.error

        data = json.dumps(body, ensure_ascii=False, default=str).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_token}" if self._api_token else "",
        }
        last_err: str = ""
        for attempt in range(1, self._max_retries + 1):
            try:
                req = urllib.request.Request(self._platform_url, data=data, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                    payload = json.loads(resp.read().decode("utf-8") or "{}")
                    return str(payload.get("url") or payload.get("run_url") or self._platform_url)
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
                last_err = f"{type(exc).__name__}: {exc}"
                if attempt < self._max_retries:
                    time.sleep(min(2 ** attempt, 10))
        return f"{self._platform_url} (failed: {last_err})"


def _collect_artifacts(report_dir: Path) -> list[dict]:
    """扫描 report_dir，收集常见 artifact。"""
    out: list[dict] = []
    if not report_dir.exists():
        return out
    for p in report_dir.rglob("*"):
        if not p.is_file():
            continue
        # 简单类型判定
        suffix = p.suffix.lower()
        if suffix in (".xml", ".json", ".html", ".txt"):
            try:
                content_b64 = base64.b64encode(p.read_bytes()).decode("ascii")
            except Exception:
                continue
            out.append({
                "name": p.name,
                "rel_path": str(p.relative_to(report_dir)),
                "media_type": {
                    ".xml": "application/xml",
                    ".json": "application/json",
                    ".html": "text/html",
                    ".txt": "text/plain",
                }.get(suffix, "application/octet-stream"),
                "size": p.stat().st_size,
                "content_base64": content_b64[:200000],   # 限流 200KB 防止 payload 爆炸
            })
    return out


def factory(user_config: dict) -> PlatformUploader:
    return PlatformUploader()
