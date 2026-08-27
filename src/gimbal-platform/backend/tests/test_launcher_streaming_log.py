"""流式 stderr 落盘:正常完成与超时两条路径(spec §9.2)。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from app.services import gimbal_launcher


def _fake_engine_argv(lines: int, *, hang: bool = False) -> list[str]:
    stmt = ";".join(
        ["import sys"]
        + [f"sys.stderr.write('engine line {i}\\n'); sys.stderr.flush()"
           for i in range(lines)]
        + (["import time; time.sleep(30)"] if hang else
           ["sys.stdout.write('{\"status\": \"ok\"}')"])
    )
    return [sys.executable, "-c", stmt]


@pytest.fixture
def patch_argv(monkeypatch: pytest.MonkeyPatch):
    def _install(argv: list[str]) -> None:
        monkeypatch.setattr(gimbal_launcher, "build_argv",
                            lambda *a, **k: argv)
    return _install


async def test_stderr_streamed_to_log(tmp_path: Path, patch_argv) -> None:
    patch_argv(_fake_engine_argv(3))
    log = tmp_path / "engine.log"
    await gimbal_launcher.launch(tmp_path / "case.json",
                                 timeout=15, engine_log_path=log)
    assert log.read_text(encoding="utf-8").splitlines() == [
        "engine line 0", "engine line 1", "engine line 2"]


async def test_timeout_preserves_partial_log(tmp_path: Path, patch_argv) -> None:
    patch_argv(_fake_engine_argv(2, hang=True))
    log = tmp_path / "engine.log"
    result = await gimbal_launcher.launch(tmp_path / "case.json",
                                          timeout=1.0, engine_log_path=log)
    assert result.launch_status == "timeout"
    assert log.read_text(encoding="utf-8").splitlines() == [
        "engine line 0", "engine line 1"]        # 已读部分保留
