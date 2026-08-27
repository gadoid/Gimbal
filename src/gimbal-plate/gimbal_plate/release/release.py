"""Minimal release capability skeleton."""

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
