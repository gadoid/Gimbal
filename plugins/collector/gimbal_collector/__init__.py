"""gimbal_collector — 在测试执行过程中收集处理信息，并生成 JSON 报告。

作为 Gimbal 框架的本地开发插件，通过 `plugins/collector/plugin.yaml`
被 PluginLoader 自动发现并加载。
"""
from .plugin import CollectorPlugin
from .report_data import RunReport, ScenarioReport, StepReport, HttpExchange

__all__ = ["CollectorPlugin", "RunReport", "ScenarioReport", "StepReport", "HttpExchange"]
