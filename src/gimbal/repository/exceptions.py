"""repository/exceptions.py

Asset 相关异常定义。

注意：所有异常已迁移至 gimbal.exceptions。
本模块保留用于向后兼容，请直接使用 gimbal.exceptions 中的异常类。
"""
from gimbal.exceptions import GimbalError

__all__ = ["GimbalError"]
