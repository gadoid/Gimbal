"""P2-03(C1):launcher 流式读取 —— on_event/on_log 边运行边回调。

验收(Goals P2-03):
  - 执行尚未结束时,事件已经回调(消费者可先落库);
  - 子进程被强制杀掉时,已回调的事件不丢失;
  - stderr JSON 日志行经 on_log 回调;终态判定仍取 run.finished。
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
# backend 包根
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import gimbal_launcher
from app.services.gimbal_launcher import launch, parse_run_result


def _fake_argv(script: str) -> list[str]:
    return [sys.executable, "-c", script]


@pytest.fixture
def fake_base(monkeypatch):
    def _set(script: str):
        monkeypatch.setattr(gimbal_launcher, "_base_argv", lambda: _fake_argv(script))
    return _set


class TestStreamingEvents:

    async def test_events_streamed_while_running(self, fake_base, tmp_path):
        """逐行输出 3 事件(行间 sleep)——回调必须早于进程退出发生。"""
        fake_base(
            "import json,time,sys\n"
            "for i in (1,2,3):\n"
            "    print(json.dumps({'event_type':f'step.{i}','seq':i}),flush=True)\n"
            "    time.sleep(0.15)\n"
            "print(json.dumps({'event_type':'run.finished','seq':4,"
            "'exit_code':0,'total':1,'passed':1,'failed':0}),flush=True)\n"
        )
        seen: list[dict] = []
        late_flags: list[bool] = []

        def on_event(d):
            # 前两个事件回调时进程必然还活着(第三行未打印)
            late_flags.append(d["seq"] < 3)
            seen.append(d)

        result = await launch(tmp_path / "case.json", on_event=on_event,
                              timeout=30)
        assert result.launch_status == "ok" and result.exit_code == 0
        assert [d["event_type"] for d in seen] == ["step.1", "step.2", "step.3",
                                                   "run.finished"]
        # 前两个事件回调发生在进程结束前(流式,非结束后倒扫)
        assert late_flags[:2] == [True, True]

    async def test_killed_process_keeps_streamed_events(self, fake_base, tmp_path):
        """超时 kill:已读事件已回调(不丢失)。"""
        fake_base(
            "import json,time\n"
            "print(json.dumps({'event_type':'step.1','seq':1}),flush=True)\n"
            "time.sleep(30)\n"
        )
        seen: list[dict] = []
        result = await launch(tmp_path / "case.json",
                              on_event=lambda d: seen.append(d),
                              timeout=0.8)
        assert result.launch_status == "timeout"
        assert [d["event_type"] for d in seen] == ["step.1"]

    async def test_stderr_logs_streamed(self, fake_base, tmp_path):
        fake_base(
            "import json,sys\n"
            "print(json.dumps({'event_type':'x','seq':1}),file=sys.stdout,flush=True)\n"
            "print(json.dumps({'level':'WARNING','category':'scheduler',"
            "'message':'slow','unit':'u-1'}),file=sys.stderr,flush=True)\n"
            "print('plain noise line',file=sys.stderr,flush=True)\n"
            "print(json.dumps({'event_type':'run.finished','seq':2,"
            "'exit_code':0,'total':1,'passed':1}),flush=True)\n"
        )
        logs: list[dict] = []
        events: list[dict] = []
        result = await launch(tmp_path / "case.json",
                              on_event=events.append, on_log=logs.append,
                              timeout=30)
        assert result.launch_status == "ok"
        assert [e["event_type"] for e in events] == ["x", "run.finished"]
        # 非日志输出(普通文本/事件行混入 stderr)不回调
        assert len(logs) == 1
        assert logs[0]["category"] == "scheduler" and logs[0]["unit"] == "u-1"

    async def test_run_finished_still_decides(self, fake_base, tmp_path):
        """流式化后终态判定不变(run.finished 双读仍工作)。"""
        fake_base(
            "import json\n"
            "print('noise')\n"
            "print(json.dumps({'event_type':'run.finished','seq':1,"
            "'exit_code':1,'total':2,'passed':1,'failed':1}),flush=True)\n"
        )
        result = await launch(tmp_path / "case.json", timeout=30)
        assert result.launch_status == "ok" and result.exit_code == 1
        assert result.total == 2 and result.failed == 1

    def test_parse_run_result_unchanged(self):
        text = '{"event_type": "run.finished", "seq": 3, "exit_code": 0, "total": 1, "passed": 1}'
        d = parse_run_result(text)
        assert d and d["exit_code"] == 0 and d["total"] == 1
