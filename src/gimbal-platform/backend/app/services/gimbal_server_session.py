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

# 入库级别序(与 execution_store.query_events 的 level_min 同一序;泵处
# 只做门槛比较,读侧序表独立维护)
_LOG_LEVEL_ORDER = ("TRACE", "DEBUG", "INFO", "SUCCESS",
                    "WARNING", "ERROR", "CRITICAL")


async def _pump_stderr(stderr, log, on_log: "Callable[[dict], None] | None",
                       min_level: str) -> None:
    """stderr 泵:逐行落文件(全量原始字节) + 解析 JSON 行回调 on_log。

    结构化日志设计 AD2/AD3:
    - 文件面:所有行原样写入(审计兜底,含未入库级别与非 JSON 行);
    - 入库面:仅 JsonSink 的 JSON 行且级别 ≥ min_level 才回调;非 JSON
      (早期彩色/uvicorn/reporter 汇总等)与低于门槛的行不入库;
    - 回调异常捕获记日志,不阻断泵(on_event 同惯例)。
    可独立单测(fake stderr 的 readline)。
    """
    if stderr is None:
        return
    min_idx = (_LOG_LEVEL_ORDER.index(min_level.upper())
               if min_level.upper() in _LOG_LEVEL_ORDER else 2)
    while True:
        raw = await stderr.readline()
        if not raw:
            break
        text = raw.decode("utf-8", errors="replace")
        if log:
            log.write(text)
        if on_log is None:
            continue
        line = text.strip()
        if not line.startswith("{"):
            continue
        try:
            d = json.loads(line)
        except ValueError:
            continue
        lv = str(d.get("level") or "").upper()
        if lv not in _LOG_LEVEL_ORDER:
            continue
        if _LOG_LEVEL_ORDER.index(lv) < min_idx:
            continue
        try:
            on_log(d)
        except Exception:  # noqa: BLE001
            logger.warning("ServerSession: on_log 回调异常(已忽略)")
    if log:
        log.close()


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
                    cwd: "Path | str | None" = None,
                    on_log: "Callable[[dict], None] | None" = None) -> None:
        import socket as _s
        with _s.socket() as sk:
            sk.bind(("127.0.0.1", 0))
            self._port = sk.getsockname()[1]
        argv = [*_base_argv(), "run", "server",
                "--host", "127.0.0.1", "--port", str(self._port)]
        # NO_COLOR=1(AD8):引擎两条日志初始化路径由 gimbal 配置层自读该
        # 环境变量(与 loguru 版本无关)——stderr 文件面的 ANSI 乱码源头
        env = {**os.environ, "PYTHONIOENCODING": "utf-8",
               "GIMBAL_SERVER_TOKEN": self.token, "NO_COLOR": "1"}
        creationflags = 0x08000000 if sys.platform == "win32" else 0
        log_fh = (engine_log_path.open("w", encoding="utf-8", newline="")
                  if engine_log_path else None)

        try:
            proc = await asyncio.create_subprocess_exec(
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
        self._proc = proc

        # D1(2026-10-13):泵闭包捕获本地 proc/stderr —— 不再触碰
        # self._proc(close() 置空后泵仍能收尾,engine.log 尾部不丢)。
        self._stderr_task = asyncio.get_event_loop().create_task(
            _pump_stderr(proc.stderr, log_fh, on_log,
                         settings.EXEC_INGEST_LOG_LEVEL))
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
        """终止进程树（terminate → wait → kill；无残留）。

        D1(2026-10-13):先收 stderr 泵任务再置空 _proc —— 此前先
        ``self._proc = None``,泵的 ``assert self._proc`` 随即 AttributeError,
        每次关会话记一条 "Task exception was never retrieved",engine.log
        尾部(进程终止前的 stderr 突发)可能丢、log 句柄不关。
        """
        proc = self._proc
        task, self._stderr_task = self._stderr_task, None
        self._proc = None
        if proc is None:
            if task is not None:
                await _quiet(task)
            return
        try:
            proc.terminate()
            await asyncio.wait_for(proc.wait(), timeout=5.0)
        except Exception:  # noqa: BLE001
            try:
                proc.kill()
                await proc.wait()
            except Exception:  # noqa: BLE001
                pass
        if task is not None:
            await _quiet(task)


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
        m2_info: "dict | None" = None,
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
        # M10 改形(M2 §2.3):执行参数收进 options
        options: dict[str, Any] = {"n_runs": n_runs, "parallel": parallel}
        if halt_at is not None:
            options["step_to"] = halt_at     # halt_at 并入 step_to
        if debug is not None:
            options["debug"] = debug
        body: dict[str, Any] = {"target": target, "options": options}
        if m2_info is not None:
            body["m2"] = m2_info            # M2 §5.1 代际门
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


async def _quiet(task: "asyncio.Task") -> None:
    """等 stderr 泵收尾并吞掉已预期的异常(管道 EOF/取消)。"""
    try:
        await asyncio.wait_for(task, timeout=3.0)
    except Exception:  # noqa: BLE001 — 进程被杀后泵的收尾异常皆预期
        pass


class ServerSessionPool:
    """P3.5-1（方案 A）：并发槽位实例池。

    引擎 ``/runs`` 是单 run 设计（并发第二个 POST 直接 409），多行执行
    且 parallel>1 时每个并发槽位各持一个 server 实例：``start`` 冷启动
    槽位 0（沿用 C12 的 fanout 期 fail-fast 语义），``run_case`` 借出
    空闲实例（无则按需冷启动至 size 上限，锁外并行），用毕归还；
    单行/调试（size=1）退化为旧的单实例语义。``close`` 收口全部实例。
    """

    def __init__(self, *, size: int) -> None:
        self._size = max(1, int(size))
        self._idle: "asyncio.Queue[ServerSession]" = asyncio.Queue()
        self._live: list[ServerSession] = []
        self._started = 0            # 已冷启动槽位数（含失败回退）
        self._engine_log_path: "Path | None" = None
        self._cwd: "Path | str | None" = None
        # 结构化日志 AD2:池生命周期=执行生命周期(决策 15),回调绑定本执行
        # 的 ingester 不存在跨执行路由错配;懒启动槽位在 _spawn 透传
        self._on_log: "Callable[[dict], None] | None" = None
        self._lock = asyncio.Lock()

    @property
    def first(self) -> "ServerSession | None":
        """槽位 0 实例（调试会话注册用；``start`` 之后必有）。"""
        return self._live[0] if self._live else None

    def _log_path(self, slot: int) -> "Path | None":
        if self._engine_log_path is None:
            return None
        # 槽位 0 沿用 server-engine.log（单实例/调试的历史名），其余加序号
        if slot == 0:
            return self._engine_log_path
        return self._engine_log_path.parent / (
            f"{self._engine_log_path.stem}-{slot}{self._engine_log_path.suffix}")

    async def start(self, *, engine_log_path: "Path | None" = None,
                    cwd: "Path | str | None" = None,
                    on_log: "Callable[[dict], None] | None" = None) -> None:
        """冷启动槽位 0（引擎不可用在此 fail-fast，与 C12 行为一致）。

        占位 ``_started=1`` —— 不占位的话首个 ``_acquire`` 会再起一个
        slot 0 实例,两个实例同写 server-engine.log("w" 互截)。
        ``on_log``(AD2)在池启动处传入(绑定本执行 ingester),懒启动
        槽位经 ``_spawn`` 透传。
        """
        self._engine_log_path = engine_log_path
        self._cwd = cwd
        self._on_log = on_log
        async with self._lock:
            if self._started > 0:
                return                    # 已预热(幂等)
            self._started = 1             # 槽位 0 由本方法占用
        try:
            s = await self._spawn(0)
        except Exception:
            async with self._lock:
                self._started -= 1        # 归还槽位,后续 acquire 重试
            raise
        self._idle.put_nowait(s)

    async def _spawn(self, slot: int) -> ServerSession:
        s = ServerSession()
        await s.start(engine_log_path=self._log_path(slot), cwd=self._cwd,
                      on_log=self._on_log)
        self._live.append(s)
        return s

    async def _acquire(self) -> ServerSession:
        spawn_slot: "int | None" = None
        async with self._lock:
            if not self._idle.empty():
                return self._idle.get_nowait()
            if self._started < self._size:
                spawn_slot = self._started
                self._started += 1     # 预占槽位，冷启动放锁外并行
        if spawn_slot is None:
            return await self._idle.get()   # 池满 → 等归还
        try:
            return await self._spawn(spawn_slot)
        except Exception:
            async with self._lock:
                self._started -= 1     # 归还槽位，后续行重试冷启动
            raise

    async def run_case(self, case_path: "Path | str", **kwargs: Any) -> LaunchResult:
        """借槽位实例执行一个 case（借出 → run_case → 归还）。"""
        s = await self._acquire()
        try:
            return await s.run_case(case_path, **kwargs)
        finally:
            self._idle.put_nowait(s)

    async def close(self) -> None:
        """收口全部实例（terminate → kill；无残留）。"""
        for s in self._live:
            try:
                await s.close()
            except Exception:  # noqa: BLE001
                pass
        self._live.clear()
