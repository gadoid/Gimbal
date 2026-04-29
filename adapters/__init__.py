"""副作用适配器层 - 隔离 IO 操作"""
from adapters.http import HttpClient
from adapters.database import DbClient

__all__ = ["HttpClient", "DbClient"]
