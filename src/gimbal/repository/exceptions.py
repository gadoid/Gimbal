"""repository/exceptions.py

Asset 相关异常的 re-export 兼容层。
真正的异常定义在 `gimbal.exceptions`（框架统一基类 GimbalError），
本模块保留用于向后兼容，外部代码可直接从 gimbal.exceptions 导入。
"""
from gimbal.exceptions import (
    AssetAlreadyExists,
    AssetDigestMismatch,
    AssetError,
    AssetNotFound,
    InvalidAssetRef,
)

__all__ = [
    "AssetError",
    "AssetNotFound",
    "AssetAlreadyExists",
    "AssetDigestMismatch",
    "InvalidAssetRef",
]
