"""Plugin category constants.

A plugin declares one or more categories. The framework uses these to:
  1. Route the plugin's contributions to the right subsystem
     (e.g. STRATEGY → StrategyDispatcher, REPORTER → ReporterRegistry)
  2. Filter plugin discovery (e.g. only load REPORTER for a 'run report' command)
  3. Validate that two plugins of the same category can coexist (uniqueness rules)
"""
from __future__ import annotations
from enum import Enum


class PluginCategory(str, Enum):
    """插件类别枚举。"""
    STRATEGY = "strategy"                       # 注入 strategy 实现的插件
    REPORTER = "reporter"                       # 报告/可视化插件（HTML/JUnit/Allure）
    RESOURCE_PROVIDER = "resource_provider"     # 提供 resource 后端的插件（DB/HTTP/...）
    AUTH = "auth"                               # 认证策略插件（OAuth/API-Key/...）
    AI_PROVIDER = "ai_provider"                 # AI/LLM 增强插件
    OBSERVABILITY = "observability"             # 指标/追踪导出
    VALIDATOR = "validator"                     # 校验器插件
    NOTIFIER = "notifier"                       # 通知插件（Slack/Email/...）
    GENERIC = "generic"                         # 通用：只通过 hook/event 参与


# 字符串常量（向后兼容）
STRATEGY = PluginCategory.STRATEGY.value
REPORTER = PluginCategory.REPORTER.value
RESOURCE_PROVIDER = PluginCategory.RESOURCE_PROVIDER.value
AI_PROVIDER = PluginCategory.AI_PROVIDER.value
AUTH = PluginCategory.AUTH.value
OBSERVABILITY = PluginCategory.OBSERVABILITY.value
VALIDATOR = PluginCategory.VALIDATOR.value
NOTIFIER = PluginCategory.NOTIFIER.value
GENERIC = PluginCategory.GENERIC.value
