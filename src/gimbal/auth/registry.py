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

    __slots__ = ("_sessions",)

    def __init__(self) -> None:
        self._sessions: dict[str, "AuthSession"] = {}

    # ── 写入 ──
    def set(self, tag: str, session: "AuthSession") -> None:
        """注册或覆盖一个 AuthSession。tag 重复时直接覆盖。"""
        self._sessions[tag] = session

    def remove(self, tag: str) -> bool:
        """移除一个 tag。返回是否存在。"""
        return self._sessions.pop(tag, None) is not None

    def clear(self) -> None:
        self._sessions.clear()

    # ── 读取 ──
    def get(self, tag: str) -> Optional["AuthSession"]:
        return self._sessions.get(tag)

    def has(self, tag: str) -> bool:
        return tag in self._sessions

    def tags(self) -> list[str]:
        return list(self._sessions.keys())

    def snapshot(self) -> dict[str, "AuthSession"]:
        """返回当前所有 session 的浅拷贝字典，用于"模板解析根"等只读场景。"""
        return dict(self._sessions)

    # ── 容器协议 ──
    def __contains__(self, tag: str) -> bool:
        return tag in self._sessions

    def __len__(self) -> int:
        return len(self._sessions)

    def __iter__(self) -> Iterator[str]:
        return iter(self._sessions)

    def __repr__(self) -> str:
        return f"AuthRegistry(tags={list(self._sessions.keys())!r})"
