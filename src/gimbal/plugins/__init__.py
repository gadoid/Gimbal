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

The Plugin base class lives in `gimbal.core.plugin` to avoid circular imports
(core depends on plugins, plugins depends on core for Plugin).
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
from .loader import PluginLoader, ENTRY_POINT_GROUP
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
    "ENTRY_POINT_GROUP",
    # Manifest
    "find_manifest",
    "parse_manifest_file",
    "ManifestError",
    "MANIFEST_FILENAMES",
    # 发现
    "discover_entry_points",
]
