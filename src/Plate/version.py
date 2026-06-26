"""版本类型(语义化版本,major.minor.patch)。

对应设计:PR-2.0 §2.2 + PLATE_EVOLUTION §3 Phase 2。

职责:定义 + 解析 + 序列化 + 字符串化。
本模块**不**依赖 spec / binding / core,纯数据类型。

业务价值:
  * 客户端 pin 某版本,保证执行可复现(同一份 scenario 在不同时间跑,依赖同一份契约字节)
  * 服务端按版本路由:老客户端请求旧版本仍可服务
  * MCP 协议升级的硬前提(Phase 3)
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import final


_VERSION_RE: re.Pattern[str] = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


@final
@dataclass(frozen=True)
class PlateVersion:
    """语义化版本。frozen=True 保证 byte-equal / 可哈希。

    字段语义(对应 semver):
      major: 破坏性变更(协议升级,需客户端主动升级)
      minor: 兼容性新增(端点新增、字段新增)
      patch: 兼容性修复(注释、默认值调整)

    解析:``PlateVersion.parse('1.2.3')`` → ``PlateVersion(1, 2, 3)``
    字符串化:``str(PlateVersion(1, 2, 3))`` → ``'1.2.3'``
    """

    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, s: str) -> "PlateVersion":
        """解析 ``'major.minor.patch'`` 字符串。

        Raises:
            ValueError: 格式错(空、非字符串、缺段、非数字)
        """
        if not isinstance(s, str):
            raise ValueError(
                f"PlateVersion: 版本字符串必须是 str,实际 {type(s).__name__}: {s!r}"
            )
        m = _VERSION_RE.match(s)
        if not m:
            raise ValueError(
                f"PlateVersion: 版本格式必须 'major.minor.patch'(纯数字),"
                f"实际 {s!r}"
            )
        return cls(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def to_dict(self) -> dict[str, int]:
        """序列化为 dict。键固定:``major`` / ``minor`` / ``patch``。

        注:不调 ``dataclasses.asdict``(避免引入额外 dict 拷贝),直接构造。
        """
        return {"major": self.major, "minor": self.minor, "patch": self.patch}

    @classmethod
    def from_dict(cls, d: dict) -> "PlateVersion":
        """从 dict 反序列化。缺失键 / 类型错抛 ValueError。

        不容错:序列化产物是契约,容错 = 接受坏契约。
        """
        if not isinstance(d, dict):
            raise ValueError(
                f"PlateVersion.from_dict: 期望 dict,实际 {type(d).__name__}"
            )
        missing = [k for k in ("major", "minor", "patch") if k not in d]
        if missing:
            raise ValueError(
                f"PlateVersion.from_dict: 缺失字段 {missing},实际 {d!r}"
            )
        try:
            return cls(
                major=int(d["major"]),
                minor=int(d["minor"]),
                patch=int(d["patch"]),
            )
        except (TypeError, ValueError) as e:
            raise ValueError(
                f"PlateVersion.from_dict: 字段类型错,实际 {d!r}: {e}"
            ) from e


__all__ = ["PlateVersion"]