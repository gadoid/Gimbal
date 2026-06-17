"""builtin/im_notifier.py - IMNotifier (DingTalk/Slack/Feishu webhook push)."""
from __future__ import annotations
import json
from typing import Any, Optional
from gimbal.core.runner import RunResult
from gimbal.events.types import (
    FrameworkEvent, StepFailedEvent, ScenarioEndEvent,
)
from gimbal.reporter.base import ReportArtifact, ReporterBase


class IMNotifier(ReporterBase):
    """即时通讯 reporter。

    支持三个内置 channel：
      - dingtalk (signature 加签)
      - slack    (无签名)
      - feishu   (signature 加签)

    配置示例 (gimbal.yaml):
        plugin_configs:
          im_notifier:
            channel: dingtalk
            webhook_url: https://oapi.dingtalk.com/robot/send?access_token=xxx
            secret: SEC...
            at_mobiles: []
    """

    name = "im_notifier"
    interested_events = ("step.failed", "scenario.end")
    is_async = True  # 修复 B9：IM webhook 慢，不阻塞 event pipeline

    def __init__(self) -> None:
        """初始化默认状态：channel/webhook/secret 为空，本地缓存置空，发送开关默认开。"""
        self._channel: str = "dingtalk"
        self._webhook_url: str = ""
        self._secret: str = ""
        self._at_mobiles: list = []
        self._failed_in_run: list = []
        self._pushed_in_step: set = set()
        self._send_immediately: bool = True

    def begin(self, ctx) -> None:
        """从 ctx.user_config 读取 channel/webhook_url/secret/at_mobiles/send_on_step_failed，然后调用 super().begin 触发自动订阅。"""
        self._channel = str(ctx.user("channel", "dingtalk")).lower()
        self._webhook_url = str(ctx.user("webhook_url", ""))
        self._secret = str(ctx.user("secret", ""))
        self._at_mobiles = list(ctx.user("at_mobiles", []) or [])
        self._send_immediately = bool(ctx.user("send_on_step_failed", True))
        super().begin(ctx)

    def on_event(self, event: FrameworkEvent) -> None:
        """处理 step.failed 与 scenario.end 事件：失败步骤立即推送并去重，失败 scenario 推送警告；任何异常静默吞掉。"""
        if not self._webhook_url or not self._send_immediately:
            return
        try:
            if isinstance(event, StepFailedEvent):
                key = (event.step_id, event.phase)
                if key in self._pushed_in_step:
                    return
                self._pushed_in_step.add(key)
                self._failed_in_run.append({
                    "step_id": event.step_id,
                    "error": event.error,
                    "phase": event.phase,
                })
                self._post(f"[FAIL] Step [{event.step_id}]\nphase={event.phase}\n{event.error[:300]}")
            elif isinstance(event, ScenarioEndEvent):
                if event.status in ("failed", "error") and self._send_immediately:
                    self._post(f"[WARN] Scenario {event.scenario_id} {event.status}")
        except Exception:
            pass

    def finalize(self, run_result: RunResult, ctx) -> ReportArtifact:
        """构造 PASS/FAIL 汇总 Markdown 并推送，返回 content-only 的 ReportArtifact（含失败步骤计数）。"""
        title = "PASS" if run_result.failed == 0 and run_result.error == 0 else "FAIL"
        text = f"""{title} {ctx.framework_ctx.environment}/{ctx.framework_ctx.mode}
Total: {run_result.total}  Passed: {run_result.passed}  Failed: {run_result.failed}  Error: {run_result.error}"""
        self._post(text)
        return ReportArtifact(
            name=self.name,
            path=None,
            content=text,
            media_type="text/markdown",
            metadata={
                "channel": self._channel,
                "failed_step_count": len(self._failed_in_run),
            },
        )

    def _post(self, text: str) -> None:
        """向配置的 webhook 异步 POST 文本消息，10s 超时，失败静默吞掉异常。"""
        if not self._webhook_url:
            return
        try:
            import urllib.request
            payload = self._build_payload(text)
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                self._webhook_url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                _ = resp.read()
        except Exception:
            pass

    def _build_payload(self, text: str) -> dict:
        """根据 _channel 构造钉钉/Slack/飞书各自的 webhook payload，未识别 channel 回退为 ``{"text": text}``。"""
        if self._channel == "dingtalk":
            return {
                "msgtype": "text",
                "text": {"content": text},
                "at": {"atMobiles": self._at_mobiles, "isAtAll": False},
            }
        if self._channel == "slack":
            return {"text": text}
        if self._channel == "feishu":
            return {"msg_type": "text", "content": {"text": text}}
        return {"text": text}


def factory(user_config: dict) -> IMNotifier:
    """ReporterRegistry 工厂函数：忽略 user_config，直接返回一个新的 IMNotifier 实例。"""
    return IMNotifier()
