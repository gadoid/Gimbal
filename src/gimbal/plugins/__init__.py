"""Plugin subsystem — discovery, manifest, registry, loader.

Public API:
  - Plugin (base class)               — from gimbal.core.plugin
  - PluginContext                     — from gimbal.core.plugin
  - PluginManifest                    — from gimbal.core.plugin
  - PluginSpec                        — runtime descriptor
  - PluginCategory (+ string consts)  — categories
  - PluginRegistry                    — runtime registry
  - PluginLoader                      — discover/load/activate pipeline
  - parse_manifest_file               — manifest parser

注：Plugin 基类目前住在 `gimbal.core.plugin`（历史原因），不构成 import 环。
   实际依赖图是 DAG：
       core.bootstrap → gimbal.plugins → core.plugin → events/hooks
   core.plugin 不 import 任何 gimbal.plugins.* 模块，所以加载顺序没问题。
   后续重构（若 Plugin 迁到 plugins/base.py）需要同步更新 plugins/loader.py、
   core/bootstrap.py、文档及第三方插件示例。
"""
from .categories import (
    PluginCategory,
    STRATEGY, REPORTER, RESOURCE_PROVIDER, AI_PROVIDER,
    AUTH, OBSERVABILITY, VALIDATOR, NOTIFIER, GENERIC,
)
from .spec import PluginSpec
from .registry import PluginRegistry
from .manifest import (
    find_manifest, parse_manifest_file, ManifestError,
    MANIFEST_FILENAMES,
)
from .loader import PluginLoader, DeactivateReport, ENTRY_POINT_GROUP
from .discovery import discover_entry_points  # re-export below

# 重新导出 Plugin 相关（从 core.plugin 透传，避免在多个地方都 import）
from gimbal.core.plugin import (
    Plugin, PluginContext, PluginManifest, PluginState,
)

__all__ = [
    # 类别
    "PluginCategory",
    "STRATEGY", "REPORTER", "RESOURCE_PROVIDER", "AI_PROVIDER",
    "AUTH", "OBSERVABILITY", "VALIDATOR", "NOTIFIER", "GENERIC",
    # 描述
    "PluginSpec",
    "PluginManifest",
    # 抽象
    "Plugin",
    "PluginContext",
    "PluginState",
    # 注册表
    "PluginRegistry",
    # 加载
    "PluginLoader",
    "DeactivateReport",
    "ENTRY_POINT_GROUP",
    # Manifest
    "find_manifest",
    "parse_manifest_file",
    "ManifestError",
    "MANIFEST_FILENAMES",
    # 发现
    "discover_entry_points",
]
