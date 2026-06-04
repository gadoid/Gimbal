"""Repository backend implementations.

当前：
    LocalFsContentStore  —— 本地文件系统（开发/单机/测试用）

未来：
    PostgresContentStore —— PostgreSQL 远程 backend（多机/生产用）
    S3ContentStore       —— S3-compatible 对象存储（可选）
"""
from .filesystem import LocalFsContentStore

__all__ = ["LocalFsContentStore"]
