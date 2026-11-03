"""core/proc_guard.py — 子进程「父死子亡」stdin 守卫(2026-11-03 泄漏复盘)。

背景:平台以子进程形态驱动引擎(server 链 ``run server`` / launch 链
``run launch``),旧回收只有父进程配合一途 —— 父被硬杀(SIGKILL/Bash
超时/带会话退出)时无人 terminate。两链两种泄漏形态(实证):

- server 常驻空转:无任何自退路径,永久泄漏(21 个执行器 PPID=1 空转
  两周);
- launch「盲跑僵尸」:stdout/stderr 写断管道的 BrokenPipeError 被
  事件总线 ``_safe_call`` 与 loguru 层层吞掉(Python 默认 SIGPIPE=
  SIG_IGN,写失败只抛异常不杀进程),用例继续跑完才退,且平台的
  GIMBAL_TIMEOUT_SEC 超时上限随父进程一起消失 —— 无主流量持续打到
  被测系统。

本模块给出与父进程配合解耦的死亡通道:spawn 方给 stdin=PIPE 并持有
写端(父进程无论怎么死,内核都会关闭它持有的 fd),本端起线程阻塞读
stdin —— EOF 即「父进程不在了」,回调动作由各命令自定义(server:
优雅停服;launch:置协作取消后正常收口)。

tty/devnull/文件不布防(devnull 打开即 EOF/文件读完 EOF/tty 的 EOF
是用户 Ctrl-D,都不是「父进程死亡」),手动运行与 pytest 捕获 stdin
的场景不受影响。跨平台:Windows 无 PDEATHSIG,这是唯一守卫;Linux
另有平台 spawn 侧的 PR_SET_PDEATHSIG 即时兜底(gimbal_launcher.
_arm_pdeathsig)。
"""
from __future__ import annotations

import os
import stat
import sys
import threading
from typing import Callable

from gimbal.log import get_logger

logger = get_logger(__name__)


def stdin_is_pipe(fd: int = 0) -> bool:
    """stdin 是否为管道(FIFO)。只有管道才布防 EOF 守卫:tty 的 EOF 是
    用户 Ctrl-D、devnull 立即 EOF、文件读完即 EOF —— 都不是「父进程死亡」。"""
    try:
        return stat.S_ISFIFO(os.fstat(fd).st_mode)
    except (OSError, ValueError):
        return False


def start_stdin_guard(on_parent_gone: Callable[[], None]) -> "threading.Thread | None":
    """stdin 为管道时起守卫线程:阻塞读到 EOF → ``on_parent_gone()``。

    父进程无论怎么死(SIGKILL 也一样)内核都会关闭它持有的管道写端,
    本端 ``read`` 随即返回空 —— 不依赖父进程配合,是最可靠的跨平台
    「父死子亡」通道。父进程从不往 stdin 写(写了也只是被丢弃)。
    非管道不布防,返回 None。
    """
    if not stdin_is_pipe():
        return None

    def _watch() -> None:
        try:
            buf = sys.stdin.buffer
            while buf.read(1):
                pass
        except Exception:  # noqa: BLE001 — stdin 已关/不可读,同样视为父进程不在
            pass
        logger.info("[proc_guard] stdin EOF(父进程已退出/关闭管道),触发自退动作")
        on_parent_gone()

    t = threading.Thread(target=_watch, name="gimbal-stdin-guard", daemon=True)
    t.start()
    return t
