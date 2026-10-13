"""_append_jsonl 并发收口守护(known-issues/run-journal/jsonl-append-race)。

撕裂行的复现条件 = 同进程多线程同时 append(to_thread 池等价);修复 =
进程内锁 + 单次 os.write 二进制追加。本测试并发打点后逐行 json.loads,
任何撕裂(行数短缺 / 解析失败)都会红 —— 不依赖时序,失败即确定性回归。
"""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.services.run_dispatcher import _append_jsonl


def test_concurrent_appends_stay_line_integral(tmp_path: Path):
    path = tmp_path / "runs" / "2026-10-13.jsonl"
    n_threads, per_thread = 8, 50

    def _worker(t: int) -> None:
        for i in range(per_thread):
            _append_jsonl(path, {"t": t, "i": i, "pad": "x" * 64})

    with ThreadPoolExecutor(max_workers=n_threads) as pool:
        list(pool.map(_worker, range(n_threads)))

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == n_threads * per_thread, (
        f"行数 {len(lines)} != {n_threads * per_thread}(撕裂/丢行)")
    for ln in lines:
        json.loads(ln)   # 任何残片行在此炸


def test_append_creates_parent_and_utf8(tmp_path: Path):
    path = tmp_path / "nested" / "dir" / "day.jsonl"
    _append_jsonl(path, {"msg": "中文 ✓"})
    assert json.loads(path.read_text(encoding="utf-8").strip())["msg"] == "中文 ✓"
