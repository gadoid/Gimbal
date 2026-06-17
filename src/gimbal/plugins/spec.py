"""PluginSpec — runtime descriptor of a discovered plugin.

This is distinct from `core.plugin.PluginManifest`:
  - `PluginManifest` is the *static* declaration (parsed from plugin.yaml)
  - `PluginSpec`    is the *runtime* descriptor (path, entry point, resolved deps, state)
"""
from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import Any, Optional

from .categories import PluginCategory


@dataclass
class PluginSpec:
    """A discovered plugin's runtime descriptor."""
    name: str
    version: str
    entry_point: str                     # "my_pkg.module:ClassName"
    category: PluginCategory = PluginCategory.GENERIC
    description: str = ""
    author: str = ""
    homepage: str = ""
    dependencies: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    gimbal_version: str = ""
    config_schema: dict[str, Any] = field(default_factory=dict)
    default_config: dict[str, Any] = field(default_factory=dict)

    # 运行时字段（loader 填充）
    plugin_path: Optional[str] = None    # 插件根目录（用于加载本地资源）
    manifest_path: Optional[str] = None  # plugin.yaml 绝对路径
    source: str = "filesystem"           # "filesystem" | "entry_point" | "inline"
    enabled: bool = True                 # 用户在 gimbal.yaml 中可关闭

    def to_dict(self) -> dict[str, Any]:
        """将 PluginSpec 转为 dict 形式，便于序列化（list 字段会复制一份以避免外部修改）。"""
        return {
            "name": self.name,
            "version": self.version,
            "entry_point": self.entry_point,
            "category": self.category.value,
            "description": self.description,
            "author": self.author,
            "homepage": self.homepage,
            "dependencies": list(self.dependencies),
            "capabilities": list(self.capabilities),
            "gimbal_version": self.gimbal_version,
            "config_schema": self.config_schema,
            "default_config": self.default_config,
            "plugin_path": self.plugin_path,
            "manifest_path": self.manifest_path,
            "source": self.source,
            "enabled": self.enabled,
        }
