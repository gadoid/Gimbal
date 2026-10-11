"""release 冻结（版本模型 v1.4）：内容寻址构件 + manifest + 构件分支提交。"""
from gimbal_plate.release.release import (
    DIALECT_VERSION,
    M2_VERSION,
    ReleaseResult,
    latest_revision_manifest,
    release_system,
    resolve_artifacts_root,
)

__all__ = [
    "DIALECT_VERSION",
    "M2_VERSION",
    "ReleaseResult",
    "latest_revision_manifest",
    "release_system",
    "resolve_artifacts_root",
]
