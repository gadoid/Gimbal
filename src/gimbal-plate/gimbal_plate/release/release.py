"""⚠️ 占位实现（S1-0 B5 注）：本模块恒返回 success=False，正式实现属批次 B（内容寻址构件 + manifest + call 投影，见 claude/plate-design.md 7.1 / 8.2）。在此之前请勿依赖本入口。
Minimal release capability skeleton."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ReleaseResult:
    """Describe the result of a release operation."""

    success: bool = False
    version: str | None = None
    message: str = ""
    details: dict[str, Any] | None = None


class ReleaseManager:
    """Placeholder entry point for future release workflows."""

    def release(self, *, version: str | None = None) -> ReleaseResult:
        """Return an explicit non-success result until a backend is implemented."""
        return ReleaseResult(
            success=False,
            version=version,
            message="release backend is not implemented",
        )


__all__ = ["ReleaseManager", "ReleaseResult"]
