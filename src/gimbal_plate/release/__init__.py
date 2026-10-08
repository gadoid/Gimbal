"""release 冻结（批次 B）：内容寻址构件 + manifest + call 投影。"""
from gimbal_plate.release.release import (
    DIALECT_VERSION,
    M2_VERSION,
    PlateRelease,
    ReleaseResult,
    release_system,
)

__all__ = [
    "DIALECT_VERSION",
    "M2_VERSION",
    "PlateRelease",
    "ReleaseResult",
    "release_system",
]
