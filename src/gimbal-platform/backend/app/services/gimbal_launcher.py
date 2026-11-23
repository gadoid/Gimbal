"""引擎子进程原语 + LaunchResult(server 链共用件)。

legacy ``run launch`` 逐 case 子进程链已随 B6③ 退役(2026-11-23,
登记册 B6/C3):平台执行恒走 server 链(gimbal_server_session,
``gimbal run server`` + HTTP/SSE)。本模块只保留 server 会话与测试
垫片仍消费的两件:

* ``LaunchResult`` —— 执行结果值对象(server 链 SSE ``run.finished``
  的归一形态;行级判定在 run_dispatcher);
* ``_base_argv`` / ``_arm_pdeathsig`` —— 引擎可执行前缀解析与
  PDEATHSIG 泄漏防线(server 链 spawn 与 legacy 链同款,共用至今)。

历史:执行调用曾是 CLI 子进程 ``gimbal run launch <case> -o json``
(设计 docs/implemented/specs/2026-08-24-run-launch-subprocess-design.md),
launch()/build_argv()/parse_run_result() 随双链退役删除,git 历史可溯。
"""
from __future__ import annotations

import ctypes
import signal
import sys
from dataclasses import dataclass, field
from typing import Any

from ..core.config import settings


# ─── 子进程泄漏防线(2026-11-03 复盘;launch 链事故实证,server 链同款)──
# 事故形态(实证):平台父进程被硬杀(SIGKILL/Bash 超时/带会话退出)后,
# 子进程不会死 —— stdout 写断管道的 BrokenPipeError 被引擎事件
# 总线 _safe_call 吞掉(只往同样已断的 stderr 记日志,loguru 再吞一层),
# Python 默认 SIGPIPE=SIG_IGN 也不杀进程 —— 它把用例剩余工作量全部跑完
# 才退(继续对被测系统发真实请求、写报告),且 GIMBAL_TIMEOUT_SEC 超时
# 上限随父进程失效。双守卫:
#   - stdin=PIPE:父死→内核关写端→引擎 stdin EOF 守卫置协作取消,
#     步骤边界收口后正常退出(引擎侧 core/proc_guard,Windows 唯一守卫);
#   - PR_SET_PDEATHSIG=SIGINT(评审 3.1,2026-11-04):父死→内核递 SIGINT→
#     引擎的 SIGINT handler 置协作取消旗标(与手动 Ctrl-C 同一条路)
#     ——在飞请求跑完、步骤边界停、teardown/after 括号必达、报告照写。
#     不能用 SIGTERM:Python 默认处置=立即终止,等于内核级硬杀,清理括号
#     全丢(被测系统留脏数据);SIGINT 对不装 handler 的旧引擎同样致死
#     (KeyboardInterrupt),泄漏防线语义不变。

_PR_SET_PDEATHSIG = 1

try:
    # 模块装载期解析 libc(preexec_fn 里只做一次 prctl 函数指针调用,
    # 不做 dlopen/分配 —— fork 后子进程上下文里这些不保证安全)
    _LIBC = (ctypes.CDLL("libc.so.6", use_errno=True)
             if sys.platform != "win32" else None)
except OSError:  # pragma: no cover — 非常规 libc 缺失环境
    _LIBC = None


def _arm_pdeathsig() -> None:
    """preexec_fn：子进程 exec 前置 ``PR_SET_PDEATHSIG=SIGINT``。

    内核保证「父进程死亡 → 向本进程递送 SIGINT」，父进程怎么死都成立
    （含 SIGKILL）。递 SIGINT 而非 SIGTERM（评审 3.1）：引擎装有
    SIGINT handler —— 置协作取消旗标，在飞请求跑完、步骤边界停、
    teardown/after 括号必达；SIGTERM 的默认处置是立即终止，父死=硬杀，
    清理括号全丢。注意其触发条件是**发起 fork 的线程**退出：本服务
    的 spawn 恒经事件循环(asyncio transport 同步创建)且 uvicorn 事件
    循环在主线程 —— 主线程退出=进程退出，语义恰为「父进程死亡」。
    若未来把执行挪到工作线程的事件循环，此守卫会在线程退出时误触发，
    届时依赖 stdin EOF 守卫兜底即可。
    """
    if _LIBC is not None:
        _LIBC.prctl(_PR_SET_PDEATHSIG, signal.SIGINT, 0, 0, 0)


# ─── result value object ──────────────────────────────────────────
@dataclass(frozen=True, slots=True)
class LaunchResult:
    """一次 case 执行的结果(server 链 = SSE ``run.finished`` 归一;
    历史 launch 链 = 子进程 stdout JSON,已退役)。

    ``launch_status``:

    * ``ok``      — 执行器正常答复(退出码含义见引擎 exit_codes.py:
      0=passed / 1=测试失败 / 2=校验拒绝 / 3-5=引擎侧错误)。
    * ``timeout`` — 超时被取消收口。
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
    # P2-05:n_runs/retry 展开的总执行次数(run.finished attempts 单列)。
    attempts: int = 0
    # 步骤级明细(server 链 details[];兜底路径为 [])。
    details: list[dict[str, Any]] = field(default_factory=list)
    error: str = ""
    # B6(R11 轻量版):server 链借出的槽位号。
    server_slot: int | None = None

    @property
    def run_result(self) -> dict[str, Any]:
        """JSONL ``runResult`` 字段的形状(与旧 HTTP RunResponse 对齐)。"""
        return {
            "exitCode": self.exit_code,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "attempts": self.attempts,
        }


# ─── argv assembly ────────────────────────────────────────────────
def _base_argv() -> list[str]:
    """可执行前缀:GIMBAL_BIN 直传,空值回退同解释器 ``-m gimbal``。"""
    if settings.GIMBAL_BIN:
        return [settings.GIMBAL_BIN]
    return [sys.executable, "-m", "gimbal"]
