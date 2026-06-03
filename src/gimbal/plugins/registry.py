"""PluginRegistry — runtime registry of activated plugins and their contributions.

Holds:
  - The map of plugin_name → Plugin instance
  - Indexes by category for fast lookup
  - The set of capabilities offered

The registry does NOT own plugin lifecycle (use `plugins/loader.py` for that).
It only answers "who provides X?" queries.
"""
from __future__ import annotations
import logging
from typing import Any, Optional

from .spec import PluginSpec
from .categories import PluginCategory

logger = logging.getLogger(__name__)


class PluginRegistry:
    """运行时插件注册表。

    用法：
        registry = PluginRegistry()
        registry.register(plugin, spec)              # 由 loader 调用
        p = registry.get("html-reporter")
        reporters = registry.list_by_category(PluginCategory.REPORTER)
    """

    def __init__(self) -> None:
        self._plugins: dict[str, Any] = {}        # name -> Plugin instance
        self._specs: dict[str, PluginSpec] = {}    # name -> spec
        self._by_category: dict[PluginCategory, list[str]] = {c: [] for c in PluginCategory}

    # ── 注册 / 注销 ──
    def register(self, plugin: Any, spec: PluginSpec) -> None:
        if spec.name in self._plugins:
            logger.warning("[PluginRegistry] Re-registering: %s (overwrites previous)", spec.name)
            self._by_category[spec.category] = [
                n for n in self._by_category[spec.category] if n != spec.name
            ]
        self._plugins[spec.name] = plugin
        self._specs[spec.name] = spec
        self._by_category[spec.category].append(spec.name)
        logger.debug("[PluginRegistry] Registered: %s (%s)", spec.name, spec.category.value)

    def unregister(self, name: str) -> bool:
        if name not in self._plugins:
            return False
        spec = self._specs.pop(name)
        self._plugins.pop(name)
        self._by_category[spec.category] = [
            n for n in self._by_category[spec.category] if n != name
        ]
        logger.debug("[PluginRegistry] Unregistered: %s", name)
        return True

    # ── 查询 ──
    def get(self, name: str) -> Optional[Any]:
        return self._plugins.get(name)

    def get_spec(self, name: str) -> Optional[PluginSpec]:
        return self._specs.get(name)

    def has(self, name: str) -> bool:
        return name in self._plugins

    def list_all(self) -> list[Any]:
        return list(self._plugins.values())

    def list_specs(self) -> list[PluginSpec]:
        return list(self._specs.values())

    def list_by_category(self, category: PluginCategory) -> list[Any]:
        return [self._plugins[n] for n in self._by_category[category] if n in self._plugins]

    def list_by_capability(self, capability: str) -> list[Any]:
        return [
            self._plugins[n] for n, s in self._specs.items()
            if capability in s.capabilities and n in self._plugins
        ]

    def clear(self) -> None:
        self._plugins.clear()
        self._specs.clear()
        for c in self._by_category:
            self._by_category[c].clear()
