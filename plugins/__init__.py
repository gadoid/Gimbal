"""插件层"""
from plugins.base import Plugin
from plugins.response_time import ResponseTimePlugin

__all__ = ["Plugin", "ResponseTimePlugin"]
