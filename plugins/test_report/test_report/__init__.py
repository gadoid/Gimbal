"""gimbal test-report plugin.

包入口；PluginLoader 通过 ``test_report.plugin:ReportPlugin`` 拿到插件类。
"""
from .plugin import ReportPlugin

__all__ = ["ReportPlugin"]
