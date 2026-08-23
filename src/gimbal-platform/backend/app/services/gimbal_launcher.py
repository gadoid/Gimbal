"""Subprocess launcher for ``gimbal run launch {case-path}`` (V3.2 执行链).

执行调用的唯一形态是 CLI 子进程(设计见
docs/superpowers/specs/2026-08-24-run-launch-subprocess-design.md):
平台把逐行合成的数据驱动用例落盘为 scenario.json,交给
``gimbal run launch <case> -o json`` 执行,同步收 JSON RunResult。

与被退役的 gimbal_client(HTTP POST /run)的关键差异:子进程不会
"不可达"——spawn 失败 / 超时 / 引擎崩溃都归一为 LaunchResult 上的
``launch_status`` 字段,由调用方(run_dispatcher)映射为行级状态,
不再需要 typed errors。

可执行文件:``settings.GIMBAL_BIN``(如 .env 的
``D:\\Gimbal\\Scripts\\gimbal.exe``);空值回退
``[sys.executable, "-m", "gimbal"]`` —— 同 venv 部署时最稳,不依赖
PATH 激活状态。

测试缝:``_base_argv()`` 可 monkeypatch 成假命令
(``[sys.executable, "-c", "..."]``),``launch()`` 整体可被
dispatcher 级测试替换(继承原 ``gimbal_client.run`` 的 mock 模式)。
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

from ..core.config import settings


# ─── result value object ──────────────────────────────────────────
@dataclass(frozen=True, slots=True)
class LaunchResult:
    """一次 ``gimbal run launch`` 子进程的结果。

    ``launch_status``:

    * ``ok``      — 进程正常退出(退出码含义见引擎 exit_codes.py:
      0=passed / 1=测试失败 / 2=校验拒绝 / 3-5=引擎侧错误;计数来自
      ``-o json`` 的 stdout,解析失败退化为仅退出码)。
    * ``timeout`` — 超时被 kill(``GIMBAL_TIMEOUT_SEC``)。
    * ``error``   — spawn 失败(OSError)等未得到引擎答复的故障。

    行级 passed/failed 判定由 run_dispatcher 按 launch_status +
    exit_code 做;本对象只如实上报。
    """

    launch_status: str  # ok | timeout | error
    exit_code: int | None = None
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    error: str = ""
    # stdout 原文(诊断用;引擎日志走 stderr,stdout 只有 JSON 报告,
    # 但防御性保留原文以防未来混入噪声)。
    stdout: str = ""
    argv: list[str] = field(default_factory=list)

    @property
    def run_result(self) -> dict[str, Any]:
        """JSONL ``runResult`` 字段的形状(与旧 HTTP RunResponse 对齐)。"""
        return {
            "exitCode": self.exit_code,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
        }


# ─── argv assembly ────────────────────────────────────────────────
def _base_argv() -> list[str]:
    """可执行前缀:GIMBAL_BIN 直传,空值回退同解释器 ``-m gimbal``。"""
    if settings.GIMBAL_BIN:
        return [settings.GIMBAL_BIN]
    return [sys.executable, "-m", "gimbal"]


def build_argv(
    case_path: Path | str,
    *,
    step_to: int | None = None,
    report_dir: Path | str | None = None,
) -> list[str]:
    """组装 ``gimbal run launch`` 命令行。

    * ``-o json`` — stdout 输出机器可读 RunResult
      (引擎 console sink 走 stderr,stdout 不受日志污染)。
    * ``--step-to`` — 0-based 含端点,与平台 RunRequest.stepTo 同语义,
      直接透传引擎 RuntimeControl.halt_at。
    * ``--report-dir`` — 引擎原生报告目录(逐 case 隔离,防并发互踩)。
    """
    argv = [*_base_argv(), "run", "launch", str(case_path), "-o", "json"]
    if step_to is not None:
        argv += ["--step-to", str(step_to)]
    if report_dir is not None:
        argv += ["--report-dir", str(report_dir)]
    return argv


# ─── stdout parsing ───────────────────────────────────────────────
def parse_run_result(stdout: str) -> dict[str, int] | None:
    """解析 ``-o json`` 的 stdout 为计数 dict;失败返回 None。

    引擎 typer.echo 把 JSON 写在 stdout 末尾;正常情况 stdout 就是
    单个 JSON 对象。防御性策略:整段解析失败时,从每个行首 ``{`` 起
    尝试后缀解析(兼容 stdout 前部混入噪声行的情况),取最后一个能
    解析出 ``exit_code`` 键的对象。
    """
    text = stdout.strip()
    if not text:
        return None
    candidates: list[str] = [text]
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip() == "{":
            candidates.append("\n".join(lines[i:]))
    for cand in reversed(candidates):
        try:
            data = json.loads(cand)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(data, dict) and "exit_code" in data:
            return {
                "exit_code": int(data.get("exit_code") or 0),
                "total": int(data.get("total") or 0),
                "passed": int(data.get("passed") or 0),
                "failed": int(data.get("failed") or 0),
                "skipped": int(data.get("skipped") or 0),
            }
    return None


# ─── subprocess execution ─────────────────────────────────────────
async def launch(
    case_path: Path | str,
    *,
    step_to: int | None = None,
    report_dir: Path | str | None = None,
    cwd: Path | str | None = None,
    timeout: float | None = None,
) -> LaunchResult:
    """执行 ``gimbal run launch <case_path>``,同步返回 LaunchResult。

    ``timeout`` 缺省取 ``settings.GIMBAL_TIMEOUT_SEC``;到点 kill 进程,
    返回 ``launch_status="timeout"``(进程残留不可能——kill 后仍 await)。
    """
    argv = build_argv(case_path, step_to=step_to, report_dir=report_dir)
    timeout = settings.GIMBAL_TIMEOUT_SEC if timeout is None else timeout

    # Windows: 不弹控制台窗;其他平台无该 flag。
    creationflags = 0
    if sys.platform == "win32":  # pragma: no cover - platform-specific
        creationflags = 0x08000000  # CREATE_NO_WINDOW

    # 子进程 stdio 强制 UTF-8:引擎 JSON 报告 ensure_ascii=False、错误信息
    # 含中文,Windows 管道缺省走 locale 码页(GBK),不强制则会乱码。
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}

    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd) if cwd else None,
            env=env,
            creationflags=creationflags,
        )
    except OSError as e:
        logger.error(
            "gimbal_launcher: spawn failed for {}: {}", argv[:1], e
        )
        return LaunchResult(
            launch_status="error",
            error=f"spawn failed: {type(e).__name__}: {e}",
            argv=argv,
        )

    try:
        stdout_b, stderr_b = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
    except asyncio.TimeoutError:
        # kill 后仍 communicate() 收尸,避免进程/管道残留。
        try:
            proc.kill()
        except ProcessLookupError:  # pragma: no cover - race with exit
            pass
        try:
            await proc.communicate()
        except Exception:  # noqa: BLE001 - best-effort reaping
            pass
        logger.warning(
            "gimbal_launcher: launch timed out after {}s: {}", timeout, case_path
        )
        return LaunchResult(
            launch_status="timeout",
            error=f"launch timeout after {timeout}s",
            argv=argv,
        )

    stdout = stdout_b.decode("utf-8", errors="replace")
    stderr = stderr_b.decode("utf-8", errors="replace")
    exit_code = proc.returncode

    counts = parse_run_result(stdout)
    if counts is None:
        # 引擎没有给出可解析的 JSON 报告:退化为仅退出码。
        # 常见原因:exit 2(校验拒绝走 typer.secho err)或引擎崩溃。
        detail = stderr.strip().splitlines()
        err_tail = detail[-1] if detail else ""
        return LaunchResult(
            launch_status="ok",
            exit_code=exit_code,
            error=err_tail[:500],
            stdout=stdout,
            argv=argv,
        )

    return LaunchResult(
        launch_status="ok",
        exit_code=counts["exit_code"],
        total=counts["total"],
        passed=counts["passed"],
        failed=counts["failed"],
        skipped=counts["skipped"],
        stdout=stdout,
        argv=argv,
    )
