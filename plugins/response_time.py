"""ResponseTimePlugin - 响应时间监控插件"""
from plugins.base import Plugin
from runtime.events import Event, EventType


class ResponseTimePlugin(Plugin):
    """响应时间监控插件，统计 HTTP 响应时间"""

    def __init__(self, threshold_ms: float = 1000):
        self.threshold_ms = threshold_ms
        self.response_times: list[dict[str, float]] = []

    def on_event(self, event: Event):
        """处理事件，提取响应时间"""
        if event.type == EventType.STEP_COMPLETED:
            data = event.data
            if "result" in data and isinstance(data["result"], dict):
                elapsed = data["result"].get("elapsed_ms")
                if elapsed is not None:
                    self.response_times.append(
                        {
                            "step_name": data.get("step_name"),
                            "elapsed_ms": elapsed,
                            "passed": elapsed < self.threshold_ms,
                        }
                    )

    def on_start(self):
        """开始时清空记录"""
        self.response_times.clear()

    def on_end(self):
        """结束时输出统计"""
        if self.response_times:
            avg_time = sum(r["elapsed_ms"] for r in self.response_times) / len(self.response_times)
            max_time = max(r["elapsed_ms"] for r in self.response_times)
            slow_steps = [r for r in self.response_times if not r["passed"]]
            print(f"\n[ResponseTimePlugin] Avg: {avg_time:.2f}ms, Max: {max_time:.2f}ms")
            if slow_steps:
                print(f"[ResponseTimePlugin] Slow steps: {[s['step_name'] for s in slow_steps]}")
