"""进程内滑动窗口限流(auth 加固批,known-issue auth/login-rate-limit-gap 落地步)。

设计边界与三个实现口径:

- **进程内即权威**:部署边界是单后端进程(README「部署与运行边界」),
  无 Redis / 无跨进程聚合 —— 重启丢窗口态是可接受的(限流是防爆破
  的成本抬升,不是精确配额)。
- **客户端 IP 取值**:nginx(gimbal.conf)恒重写 ``X-Real-IP`` 为
  ``$remote_addr``,反代后客户端无法伪造该头 —— 优先取之;无反代直连
  时退 ``X-Forwarded-For`` 末跳(单层反代假设)与对端地址。**直连后端
  端口可伪造头键**绕过 IP 面 —— 部署约定 nginx 为唯一入口(内网边界,
  见 known-issue 记录 §1)。
- **免锁**:消费方全是 async 路由,事件环单线程;窗口 dict/deque 操作
  不含 await 点,天然原子,不加锁。
"""
from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Request


class RateLimited(Exception):
    """窗口预算耗尽;携带 Retry-After 秒数(最早的命中滑出窗口为止)。"""

    def __init__(self, retry_after: float) -> None:
        super().__init__(f"rate limited, retry after {retry_after:.0f}s")
        self.retry_after = retry_after


# key = (action, face, value);face ∈ {"ip", "acct"}
_windows: dict[tuple[str, str, str], deque[float]] = defaultdict(deque)

_now = time.monotonic


def client_ip(request: Request) -> str:
    """见模块 docstring:X-Real-IP → XFF 末跳 → 对端地址(全缺 = unknown)。"""
    real = request.headers.get("x-real-ip")
    if real:
        return real.strip()
    xff = request.headers.get("x-forwarded-for")
    if xff:
        # $proxy_add_x_forwarded_for 会把客户端自带的 XFF 原样保留在
        # 前面 —— 单层可信反代下,末跳才是反代追加的真实来源地址。
        return xff.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def check(
    action: str,
    *,
    ip: str,
    account: str | None = None,
    ip_max: int,
    ip_window_s: float,
    acct_max: int | None = None,
    acct_window_s: float = 0.0,
    now: float | None = None,
) -> None:
    """双键滑动窗口:任一面预算耗尽即抛 ``RateLimited``。

    只在**放行**时记窗(拒绝不记 —— 连续重试不无限延长封锁);
    ``Retry-After`` = 最早命中滑出窗口的剩余秒数。账号面记窗在 IP 面
    之前:爆破同一账号时先耗账号预算,别账号不受连坐。
    """
    if account and acct_max:
        _check_face(
            (action, "acct", account), acct_max, acct_window_s, now=now)
    _check_face((action, "ip", ip), ip_max, ip_window_s, now=now)


def _check_face(
    key: tuple[str, str, str], max_: int, window_s: float,
    *, now: float | None,
) -> None:
    t = _now() if now is None else now
    w = _windows[key]
    # deque 头 = 最早命中;滑出窗口的旧命中出队
    while w and w[0] <= t - window_s:
        w.popleft()
    if len(w) >= max_:
        raise RateLimited(w[0] + window_s - t)
    w.append(t)


# 测试面:窗口态重置(进程内单例,跨测试必须显式清)
def reset() -> None:
    _windows.clear()
