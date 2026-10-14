"""S12 精简堆栈帧 + AD8 引擎侧两小项(结构化日志设计批 5 捎带)。

- JsonSink exception 序列化:默认不带 frames;GIMBAL_LOG_STACK_FRAMES
  开(帧数可配);DEBUG 级自动开;帧形 {file,line,function};
- reporter console `_no_color` 非 tty 兜底(AD8 层 3);
- setup._silence_noisy_loggers 覆盖 uvicorn.access(AD8 层 2 配套)。
"""
import json
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from datetime import datetime, timezone


def _record(level_name: str, exception=None):
    return {
        "time": datetime.now(timezone.utc),
        "level": type("L", (), {"name": level_name, "no": {"DEBUG": 10}.get(level_name, 20)})(),
        "name": "gimbal.core.x",
        "function": "f", "line": 1, "message": "m",
        "extra": {"name": "gimbal.core.x"}, "exception": exception,
    }


def _exc():
    try:
        raise ValueError("boom")
    except ValueError:
        import sys as _s
        return _s.exc_info()


class TestStackFrames:

    def test_default_off_info_level(self, monkeypatch):
        monkeypatch.delenv("GIMBAL_LOG_STACK_FRAMES", raising=False)
        from gimbal.log.formatters import JsonSink
        payload = json.loads(JsonSink()._serialize(_record("INFO", _exc())))
        assert payload["exception"]["type"] == "ValueError"
        assert "frames" not in payload["exception"]

    def test_env_gate_with_frame_count(self, monkeypatch):
        monkeypatch.setenv("GIMBAL_LOG_STACK_FRAMES", "2")
        from gimbal.log.formatters import JsonSink
        payload = json.loads(JsonSink()._serialize(_record("ERROR", _exc())))
        frames = payload["exception"]["frames"]
        assert 1 <= len(frames) <= 2
        assert set(frames[0]) == {"file", "line", "function"}

    def test_env_truthy_non_numeric_defaults_8(self, monkeypatch):
        monkeypatch.setenv("GIMBAL_LOG_STACK_FRAMES", "yes")
        from gimbal.log.formatters import JsonSink
        payload = json.loads(JsonSink()._serialize(_record("ERROR", _exc())))
        assert "frames" in payload["exception"]

    def test_debug_level_auto_on(self, monkeypatch):
        monkeypatch.delenv("GIMBAL_LOG_STACK_FRAMES", raising=False)
        from gimbal.log.formatters import JsonSink
        payload = json.loads(JsonSink()._serialize(_record("DEBUG", _exc())))
        assert "frames" in payload["exception"]


class TestAd8EngineSide:

    def test_reporter_no_color_non_tty_fallback(self, monkeypatch):
        monkeypatch.setattr(sys.stderr, "isatty", lambda: False, raising=False)
        from gimbal.reporter.builtin.console import ConsoleReporter

        class _Bus:
            def subscribe(self, *a, **kw):
                return len(getattr(self, "ids", [])) + 1

        class _Ctx:
            config = type("C", (), {"no_color": False})()
            bus = _Bus()
            subscription_mode = "sync"
            subscription_priority = 0
            subscription_ids: list = []
            user_data: dict = {}

            def user(self, key, default=None):
                return self.user_data.get(key, default)

        r = ConsoleReporter()
        r.begin(_Ctx())
        assert r._no_color is True

    def test_uvicorn_access_silenced(self):
        from gimbal.log.setup import _silence_noisy_loggers
        _silence_noisy_loggers()
        assert logging.getLogger("uvicorn.access").level == logging.WARNING
