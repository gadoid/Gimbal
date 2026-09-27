"""auth/registry.py

AuthSession 的可变容器。

为什么需要这个类
----------------
原本 AuthSession 存放在 BootstrapConfig.users 字典里，但 BootstrapConfig 是
frozen=True。代码通过 dict 的内部可变性绕过 frozen 约束——读 cfg.users.get(tag)
正常，但 cfg.users 本身被设计为"配置输入"，运行期写入 token 抹掉了配置与状态的边界。

把 AuthSession 拿出来放进独立的 AuthRegistry，让：
  - BootstrapConfig 保持 frozen，承载纯配置输入
  - AuthRegistry 显式可写，承载运行期认证状态
  - 调用方拿到的不再是 dict（接口不收敛），而是带语义的方法
"""
from __future__ import annotations

import threading
from typing import Iterator, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from gimbal.schema.auth import AuthSession


class AuthRegistry:
    """tag → AuthSession 的可变映射。

    使用：
        reg = AuthRegistry()
        reg.set("admin", auth_session)
        sess = reg.get("admin")

    设计要点：
      - 不继承 dict（避免破坏封装、避免暴露 .keys()/.items() 等"配置感"接口）
      - 提供 snapshot() 用于"只读"导出（例如送入模板解析 root）
      - 写入是显式的 set()，不是 __setitem__——降低误用
    """

    __slots__ = ("_sessions", "_lock", "_flight")

    def __init__(self) -> None:
        """构造空的 AuthRegistry，初始化内部 tag→AuthSession 字典。

        2026-09-27 多线程分派：并发 scenario 共享同一 registry（token 写入
        与模板解析 root 的 snapshot 读并发），以 RLock 保护。
        """
        self._sessions: dict[str, "AuthSession"] = {}
        self._lock = threading.RLock()
        # 单飞刷新状态（v2.1 批次 D）：tag → [互斥锁, 刷新代数]
        self._flight: dict[str, list] = {}

    # ── 单飞刷新（批次 D）─────────────────────────────────

    def singleflight_refresh(self, tag: str, refresh_fn) -> bool:
        """并发下同 tag 只有一个线程真正执行 refresh_fn，等待者直接复用。

        返回 True = 本次调用执行了刷新；False = 等待期间别人已刷新
        （调用方直接重读 session 即可拿到新凭证）。
        """
        state = self._flight.setdefault(tag, [threading.Lock(), 0])
        observed = state[1]
        with state[0]:
            if state[1] != observed:
                return False
            refresh_fn()
            state[1] += 1
            return True

    # ── 写入 ──
    def set(self, tag: str, session: "AuthSession") -> None:
        """注册或覆盖一个 AuthSession。tag 重复时直接覆盖，不做唯一性校验。"""
        with self._lock:
            self._sessions[tag] = session

    def remove(self, tag: str) -> bool:
        """移除指定 tag 的 AuthSession；返回是否原本存在。"""
        with self._lock:
            return self._sessions.pop(tag, None) is not None

    def clear(self) -> None:
        """清空所有 AuthSession，常用于测试或场景隔离。"""
        with self._lock:
            self._sessions.clear()

    # ── 读取 ──
    def get(self, tag: str) -> Optional["AuthSession"]:
        """按 tag 取出 AuthSession；不存在则返回 None（不抛异常）。"""
        with self._lock:
            return self._sessions.get(tag)

    def has(self, tag: str) -> bool:
        """判断指定 tag 是否已注册 AuthSession。"""
        with self._lock:
            return tag in self._sessions

    def tags(self) -> list[str]:
        """返回当前已注册的所有 tag 列表（浅拷贝，外部修改不会影响内部状态）。"""
        with self._lock:
            return list(self._sessions.keys())

    def snapshot(self) -> dict[str, "AuthSession"]:
        """返回当前所有 session 的浅拷贝字典，用于"模板解析根"等只读场景。"""
        with self._lock:
            return dict(self._sessions)

    # ── 容器协议 ──
    def __contains__(self, tag: str) -> bool:
        with self._lock:
            return tag in self._sessions

    def __len__(self) -> int:
        with self._lock:
            return len(self._sessions)

    def __iter__(self) -> Iterator[str]:
        return iter(self._sessions)

    def __repr__(self) -> str:
        return f"AuthRegistry(tags={list(self._sessions.keys())!r})"
