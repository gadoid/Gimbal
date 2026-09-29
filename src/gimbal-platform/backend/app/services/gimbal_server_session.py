"""services/gimbal_server_session.py — C12（P3-02）：执行器 server 进程模型。

每次执行持有一次的 ``gimbal run server`` 实例：平台生成并独占 token，
spawn 到随机空闲端口，逐 case ``POST /runs`` + SSE 消费事件（→ 平台
_EventIngester 同一入库面），取消走执行器 cancel 端点（协作取消），
结束 terminate 进程树（Windows/Linux 无残留）。

与 ``gimbal_launcher.launch()``（run launch 子进程 stdout jsonl）双链并存
（C13 灰度：``settings.EXEC_CHAIN`` / 执行配方 ``chain`` 键切换）。
"""
from __future__ import annotations

import asyncio
import json
import os
import secrets
import sys
import time
from pathlib import Path
from typing import Any, Callable

import httpx
from loguru import logger

from ..core.config import settings
from .gimbal_launcher import LaunchResult, _base_argv


class ServerSession:
    """一次执行一个执行器 server 实例（总案决策 15）。"""

    START_TIMEOUT_SEC = 20.0

    def __init__(self) -> None:
        self.token = secrets.token_urlsafe(24)
        self._proc: "asyncio.subprocess.Process | None" = None
        self._port: int | None = None
        self._base: str | None = None
        self._run_id: str | None = None      # 当前(最近)run
        self._stderr_task: "asyncio.Task | None" = None

    # ── 进程生命周期 ────────────────────────────────────────

    async def start(self, *, engine_log_path: "Path | None" = None,
                    cwd: "Path | str | None" = None) -> None:
        import socket as _s
        with _s.socket() as sk:
            sk.bind(("127.0.0.1", 0))
            self._port = sk.getsockname()[1]
        argv = [*_base_argv(), "run", "server",
                "--host", "127.0.0.1", "--port", str(self._port)]
        env = {**os.environ, "PYTHONIOENCODING": "utf-8",
               "GIMBAL_SERVER_TOKEN": self.token}
        creationflags = 0x08000000 if sys.platform == "win32" else 0
        log_fh = (engine_log_path.open("w", encoding="utf-8", newline="")
                  if engine_log_path else None)

        try:
            self._proc = await asyncio.create_subprocess_exec(
                *argv,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(cwd) if cwd else None,
                env=env, creationflags=creationflags,
            )
        except OSError as e:
            if log_fh:
                log_fh.close()
            raise RuntimeError(f"server spawn failed: {e}") from e

        async def _drain_stderr() -> None:
            assert self._proc and self._proc.stderr
            while True:
                raw = await self._proc.stderr.readline()
                if not raw:
                    break
                if log_fh:
                    log_fh.write(raw.decode("utf-8", errors="replace"))
            if log_fh:
                log_fh.close()

        self._stderr_task = asyncio.get_event_loop().create_task(_drain_stderr())
        self._base = f"http://127.0.0.1:{self._port}"

        deadline = time.monotonic() + self.START_TIMEOUT_SEC
        async with httpx.AsyncClient(timeout=2.0) as c:
            while time.monotonic() < deadline:
                if self._proc.returncode is not None:
                    if log_fh:
                        log_fh.close()
                    raise RuntimeError(
                        f"server exited early rc={self._proc.returncode}")
                try:
                    r = await c.get(f"{self._base}/healthz")
                    if r.status_code == 200:
                        return
                except Exception:  # noqa: BLE001
                    await asyncio.sleep(0.15)
        await self.close()
        raise RuntimeError("server not ready within timeout")

    async def close(self) -> None:
        """终止进程树（terminate → wait → kill；无残留）。"""
        proc, self._proc = self._proc, None
        if proc is None:
            return
        try:
            proc.terminate()
            await asyncio.wait_for(proc.wait(), timeout=5.0)
            return
        except Exception:  # noqa: BLE001
            pass
        try:
            proc.kill()
            await proc.wait()
        except Exception:  # noqa: BLE001
            pass

    @property
    def run_id(self) -> "str | None":
        return self._run_id

    # ── 执行 / 取消 / 调试 ──────────────────────────────────

    async def run_case(
        self,
        case_path: "Path | str",
        *,
        halt_at: "int | None" = None,
        n_runs: int = 1,
        parallel: int = 1,
        debug: "dict | None" = None,
        timeout: "float | None" = None,
        on_event: "Callable[[dict], None] | None" = None,
    ) -> LaunchResult:
        """一个 case：POST /runs → SSE 消费到 run.finished → LaunchResult。

        timeout：单 case 墙钟上限；超时 POST cancel 后给 3s 宽限再收口
        ``launch_status="timeout"``（在飞请求至多跑满协议超时）。
        """
        if self._proc is None:
            raise RuntimeError("ServerSession not started")
        target = json.loads(Path(case_path).read_text(encoding="utf-8"))
        body: dict[str, Any] = {"target": target, "n_runs": n_runs,
                                "parallel": parallel}
        if halt_at is not None:
            body["halt_at"] = halt_at
        if debug is not None:
            body["debug"] = debug
        to = timeout if timeout is not None else settings.GIMBAL_TIMEOUT_SEC
        counts: "dict[str, Any] | None" = None
        error_text = ""
        argv_note = [f"server:{self._port}", "POST", "/runs"]
        try:
            async with httpx.AsyncClient(
                base_url=self._base,
                timeout=httpx.Timeout(15.0, read=to + 90.0),
                headers=self._headers(),
            ) as c:
                r = await c.post("/runs", json=body)
                if r.status_code != 200:
                    return LaunchResult(
                        launch_status="ok", exit_code=2,
                        error=r.text[:400], argv=argv_note)
                self._run_id = r.json().get("runId")
                counts = await self._consume_events(
                    c, self._run_id, on_event=on_event, timeout=to)
        except Exception as e:  # noqa: BLE001
            error_text = f"{type(e).__name__}: {e}"
        if counts is None:
            try:
                await self.cancel()
                await asyncio.sleep(3.0)
            except Exception:  # noqa: BLE001
                pass
            return LaunchResult(launch_status="timeout", exit_code=None,
                                error=error_text or "no run.finished",
                                argv=argv_note)
        return LaunchResult(
            launch_status="ok",
            exit_code=int(counts.get("exit_code") or 0),
            total=int(counts.get("total") or 0),
            passed=int(counts.get("passed") or 0),
            failed=int(counts.get("failed") or 0),
            skipped=int(counts.get("skipped") or 0),
            attempts=int(counts.get("attempts") or 0),
            details=counts.get("details") or [],
            stdout="",
            argv=argv_note,
        )

    async def _consume_events(self, client: httpx.AsyncClient, run_id: str, *,
                              on_event: "Callable[[dict], None] | None",
                              timeout: float) -> dict:
        """SSE 消费到流终；run.finished 的计数返回，事件逐条回调。

        aiter_text 产出的是**任意边界 chunk**（不是行）——缓冲区按 \\n
        切行后再做 SSE 帧解析（data: 前缀 + 空行分帧）。
        """
        deadline = time.monotonic() + timeout + 30.0
        buf = ""
        data_line: "str | None" = None
        async with client.stream(
            "GET", f"/runs/{run_id}/events",
            headers={"Accept": "text/event-stream"},
        ) as resp:
            resp.raise_for_status()
            async for chunk in resp.aiter_text():
                if time.monotonic() > deadline:
                    raise TimeoutError("sse stream deadline exceeded")
                buf += chunk
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.rstrip("\r")
                    if line.startswith("data:"):
                        data_line = line[5:].strip()
                        continue
                    if line.startswith("event:"):
                        continue          # done 信号随其 data 帧到达
                    if not line and data_line is not None:
                        try:
                            ev = json.loads(data_line)
                        except ValueError:
                            ev = {"event_type": "_unparsed", "raw": data_line}
                        data_line = None
                        if on_event is not None:
                            try:
                                on_event(ev)
                            except Exception:  # noqa: BLE001
                                logger.warning(
                                    "ServerSession: on_event 回调异常(已忽略)")
                        if ev.get("event_type") == "run.finished":
                            return ev
        raise RuntimeError("sse stream ended without run.finished")

    def _headers(self) -> dict[str, str]:
        return {"X-Gimbal-Token": self.token}

    async def cancel(self) -> bool:
        """协作取消当前 run（步骤边界/未启动单元生效）。"""
        if self._run_id is None or self._proc is None:
            return False
        try:
            async with httpx.AsyncClient(base_url=self._base, timeout=5.0,
                                         headers=self._headers()) as c:
                r = await c.post(f"/runs/{self._run_id}/cancel")
                return r.status_code == 200 and bool(r.json().get("accepted"))
        except Exception:  # noqa: BLE001
            return False

    async def debug_command(self, command: dict) -> dict:
        """C6：代理结构化调试命令；返回 {accepted, output[]}。"""
        if self._run_id is None:
            return {"accepted": False, "output": []}
        async with httpx.AsyncClient(base_url=self._base, timeout=15.0,
                                     headers=self._headers()) as c:
            r = await c.post(f"/runs/{self._run_id}/debug",
                             json={"command": command})
            if r.status_code == 404:
                return {"accepted": False, "output": []}
            r.raise_for_status()
            return r.json()

    async def debug_output(self) -> "list[str]":
        """C6：取回（并清空）调试会话输出缓冲。"""
        if self._run_id is None:
            return []
        async with httpx.AsyncClient(base_url=self._base, timeout=5.0,
                                     headers=self._headers()) as c:
            r = await c.get(f"/runs/{self._run_id}/debug/output")
            if r.status_code == 404:
                return []
            r.raise_for_status()
            return r.json().get("output") or []
