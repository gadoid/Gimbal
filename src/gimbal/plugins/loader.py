"""PluginLoader — discover, resolve, load, activate plugins.

Discovery sources (in order):
  1. Filesystem: `<plugins_dir>/<plugin_name>/plugin.yaml`
  2. Entry points: `gimbal.plugins` group (for installed packages)
  3. Inline: programmatically registered plugins

Pipeline:
    discover()      → list[PluginSpec]
    resolve_deps()  → list[PluginSpec] in dependency order
    load_all()      → list[Plugin]   (instances created, on_load called)
    activate_all()  → registers event/hook/strategy via PluginContext
    deactivate_all()→ reverse order, returns DeactivateReport

Each stage is independently re-runnable (e.g. for hot reload).
"""
from __future__ import annotations
import importlib
import importlib.metadata as importlib_metadata
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Union

from .spec import PluginSpec
from .categories import PluginCategory
from .manifest import find_manifest, parse_manifest_file, ManifestError
from .registry import PluginRegistry

from gimbal.core.plugin import Plugin, PluginContext, PluginManifest, PluginState

logger = logging.getLogger(__name__)


# ── 卸载结果报告 ─────────────────────────────────────────────

@dataclass
class DeactivateReport:
    """插件卸载结果报告。

    不吞异常：单个插件的卸载失败（包括 on_deactivate 抛异常、
    hook/event 清理失败）都会被记录到 failed 列表中。
    调用方根据 succeeded/failed 决定后续动作。
    """
    succeeded: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)   # (plugin_name, error_message)

    @property
    def all_ok(self) -> bool:
        return not self.failed

    def __str__(self) -> str:  # pragma: no cover
        ok = len(self.succeeded)
        bad = len(self.failed)
        if self.all_ok:
            return f"DeactivateReport(ok={ok})"
        return f"DeactivateReport(ok={ok} failed={bad} failures={self.failed})"


# ── Entry point group name (用于 pip 安装的插件) ─────────────────────
ENTRY_POINT_GROUP = "gimbal.plugins"


class PluginLoader:
    """插件加载器。

    用法：
        loader = PluginLoader(plugins_dir=Path("./plugins"))
        specs = loader.discover()                   # 1. 发现
        specs = loader.resolve_deps(specs)          # 2. 依赖排序
        plugins = loader.load_all(specs)            # 3. 加载
        loader.activate_all(plugins, ctx_factory)   # 4. 激活
    """

    def __init__(
        self,
        plugins_dir: Optional[Union[str, Path]] = None,
        enabled_filter: Optional[set[str]] = None,
        disabled_filter: Optional[set[str]] = None,
    ) -> None:
        self.plugins_dir = Path(plugins_dir) if plugins_dir else None
        self.enabled_filter = enabled_filter     # 白名单（None 表示全开）
        self.disabled_filter = disabled_filter or set()  # 黑名单
        self._registry = PluginRegistry()

    # ── 查询 ──
    @property
    def registry(self) -> PluginRegistry:
        return self._registry

    def is_enabled(self, spec: PluginSpec) -> bool:
        if spec.name in self.disabled_filter:
            return False
        if self.enabled_filter is not None and spec.name not in self.enabled_filter:
            return False
        return spec.enabled

    # ── 1. 发现 ──
    def discover(self) -> list[PluginSpec]:
        """从所有来源发现插件。"""
        specs: list[PluginSpec] = []
        seen: set[str] = set()

        # 1a. Filesystem
        if self.plugins_dir and self.plugins_dir.is_dir():
            for child in sorted(self.plugins_dir.iterdir()):
                if not child.is_dir():
                    continue
                manifest_path = find_manifest(child)
                if not manifest_path:
                    continue
                try:
                    spec = parse_manifest_file(manifest_path)
                except ManifestError as e:
                    logger.error("[PluginLoader] bad manifest at %s: %s", manifest_path, e)
                    continue
                if spec.name in seen:
                    logger.warning("[PluginLoader] duplicate plugin name: %s", spec.name)
                    continue
                seen.add(spec.name)
                specs.append(spec)

        # 1b. Entry points
        try:
            eps = importlib_metadata.entry_points()
            # py3.10+ returns EntryPoint; py3.9 returns dict
            if hasattr(eps, "select"):
                group_eps = list(eps.select(group=ENTRY_POINT_GROUP))
            else:
                group_eps = list(eps.get(ENTRY_POINT_GROUP, []))  # type: ignore[union-attr]
            for ep in group_eps:
                name = ep.name
                if name in seen:
                    continue
                # entry point value is "module:Class" or just metadata
                entry_point = f"{ep.module}:{ep.attr}" if ep.attr else ep.value
                spec = PluginSpec(
                    name=name,
                    version=getattr(ep, "version", "0.0.0") or "0.0.0",
                    entry_point=entry_point,
                    category=PluginCategory.GENERIC,
                    source="entry_point",
                )
                seen.add(name)
                specs.append(spec)
        except Exception as e:  # noqa: BLE001
            logger.debug("[PluginLoader] entry-point discovery skipped: %s", e)

        logger.info("[PluginLoader] discovered %d plugin(s): %s",
                    len(specs), [s.name for s in specs])
        return specs

    # ── 2. 依赖排序 ──
    def resolve_deps(self, specs: list[PluginSpec]) -> list[PluginSpec]:
        """拓扑排序，确保依赖在被依赖者之后加载。

        检测到循环依赖时抛 ValueError。
        """
        by_name = {s.name: s for s in specs}
        visited: set[str] = set()
        visiting: set[str] = set()
        out: list[PluginSpec] = []

        def visit(name: str, path: list[str]) -> None:
            if name in visited:
                return
            if name in visiting:
                raise ValueError(
                    f"[PluginLoader] circular dependency: {' -> '.join(path + [name])}"
                )
            if name not in by_name:
                # 外部依赖（不在本次发现范围），跳过
                return
            visiting.add(name)
            spec = by_name[name]
            for dep in spec.dependencies:
                visit(dep, path + [name])
            visiting.remove(name)
            visited.add(name)
            out.append(spec)

        for s in specs:
            visit(s.name, [])
        return out

    # ── 3. 加载（import + 实例化 + on_load） ──
    def load_all(self, specs: list[PluginSpec]) -> list[Plugin]:
        """加载并实例化每个插件。失败的插件会被跳过。"""
        plugins: list[Plugin] = []
        for spec in specs:
            if not self.is_enabled(spec):
                logger.info("[PluginLoader] skip disabled plugin: %s", spec.name)
                continue
            try:
                plugin = self._load_one(spec)
            except Exception as e:  # noqa: BLE001
                logger.error("[PluginLoader] failed to load %s: %s", spec.name, e)
                continue
            plugins.append(plugin)
        return plugins

    def _load_one(self, spec: PluginSpec) -> Plugin:
        module_name, _, attr = spec.entry_point.partition(":")
        if not module_name or not attr:
            raise ValueError(f"invalid entry_point: {spec.entry_point!r}")

        # 让 import 找得到插件包：
        #   - 把 plugin_path 自身加入 sys.path，使得 entry_point 里只有模块名（无包前缀）也能 import
        #   - 同时把 parent 目录也加入，使得 entry_point 是 `pkg.mod:Cls` 的写法也能 import
        for p in (spec.plugin_path, str(Path(spec.plugin_path).parent) if spec.plugin_path else None):
            if p and p not in sys.path:
                sys.path.insert(0, p)

        module = importlib.import_module(module_name)
        cls = getattr(module, attr, None)
        if cls is None:
            raise ValueError(f"{spec.entry_point} not found")
        if not isinstance(cls, type) or not issubclass(cls, Plugin):
            raise TypeError(f"{spec.entry_point} is not a Plugin subclass")

        # 把 manifest 注入类（如果子类没有显式声明）
        if not hasattr(cls, "manifest") or not isinstance(getattr(cls, "manifest", None), PluginManifest):
            cls.manifest = PluginManifest(
                name=spec.name,
                version=spec.version,
                entry_point=spec.entry_point,
                description=spec.description,
                dependencies=spec.dependencies,
                capabilities=spec.capabilities,
            )

        instance = cls()
        instance.load()
        return instance

    # ── 4. 激活 ──
    def activate_all(
        self,
        plugins: list[Plugin],
        *,
        event_bus: Any,
        hook_registry: Any,
        user_configs: Optional[dict[str, dict[str, Any]]] = None,
        plugin_registry: Optional[PluginRegistry] = None,
    ) -> list[Plugin]:
        """激活所有已加载的插件。

        user_configs: {plugin_name: {key: value}} 合并 default_config 后传给插件。
        plugin_registry: 框架级的 plugin registry（默认使用 loader 内部 registry）。

        返回成功激活的插件列表（失败的已被跳过）。
        """
        user_configs = user_configs or {}
        registry = plugin_registry or self._registry
        activated: list[Plugin] = []

        for plugin in plugins:
            cfg = self._resolve_user_config(plugin, user_configs.get(plugin.name, {}))
            ctx = PluginContext(
                plugin_name=plugin.name,
                config=cfg,
                event_bus=event_bus,
                hook_registry=hook_registry,
                plugin_registry=registry,
            )
            try:
                plugin.activate(ctx)
            except Exception as e:  # noqa: BLE001
                logger.error("[PluginLoader] activate failed for %s: %s", plugin.name, e)
                continue
            registry.register(plugin, self._spec_of(plugin))
            activated.append(plugin)

        logger.info("[PluginLoader] activated %d / %d plugin(s)",
                    len(activated), len(plugins))
        return activated

    def _resolve_user_config(self, plugin: Plugin, user_cfg: dict[str, Any]) -> dict[str, Any]:
        spec = self._spec_of(plugin)
        merged: dict[str, Any] = {}
        merged.update(spec.default_config or {})
        merged.update(user_cfg or {})
        return merged

    def _spec_of(self, plugin: Plugin) -> PluginSpec:
        # 优先用 registry 中已存在的 spec（如果已注册）
        s = self._registry.get_spec(plugin.name)
        if s:
            return s
        # 否则从 plugin.manifest 构造一个临时 spec
        m = plugin.manifest
        return PluginSpec(
            name=m.name,
            version=m.version,
            entry_point=m.entry_point,
            description=m.description,
            dependencies=m.dependencies,
            capabilities=m.capabilities,
        )

    # ── 5. 卸载（反向） ──
    def deactivate_all(
        self,
        plugins: list[Plugin],
        *,
        plugin_registry: Optional[PluginRegistry] = None,
    ) -> DeactivateReport:
        """反向卸载所有插件，并清理它们在 event_bus / hook_registry /
        plugin_registry 中留下的注册。

        这是**唯一**的插件卸载入口：
            - bootstrap.shutdown()  →  loader.deactivate_all(plugins, plugin_registry=...)
            - 测试代码             →  loader.deactivate_all([plugin], plugin_registry=...)

        不吞异常：单个插件的失败（包括 on_deactivate 抛异常、
        event/hook 清理失败）都会被记录到 DeactivateReport.failed 中，
        不会中断后续插件的卸载。调用方读取 report 决定后续动作。
        """
        registry = plugin_registry or self._registry
        report = DeactivateReport()

        for plugin in reversed(plugins):
            errors: list[str] = []

            # 5a. on_deactivate 钩子 + 状态机转换
            try:
                plugin.deactivate()
            except Exception as e:  # noqa: BLE001
                errors.append(f"on_deactivate: {type(e).__name__}: {e}")

            # 5b. event/hook 注册清理（即使 5a 失败也要尝试）
            if plugin.ctx is not None:
                try:
                    if plugin.ctx.event_bus is not None:
                        plugin.ctx.event_bus.unsubscribe_plugin(plugin.name)
                except Exception as e:  # noqa: BLE001
                    errors.append(f"unsubscribe: {type(e).__name__}: {e}")
                try:
                    if plugin.ctx.hook_registry is not None:
                        plugin.ctx.hook_registry.unregister_plugin(plugin.name)
                except Exception as e:  # noqa: BLE001
                    errors.append(f"unregister_hook: {type(e).__name__}: {e}")

            # 5c. 框架级 plugin registry 注销
            try:
                registry.unregister(plugin.name)
            except Exception as e:  # noqa: BLE001
                errors.append(f"registry_unregister: {type(e).__name__}: {e}")

            # 5d. 报告
            if errors:
                report.failed.append((plugin.name, " | ".join(errors)))
                logger.error(
                    "[PluginLoader] deactivate failed: plugin=%s errors=%s",
                    plugin.name, errors,
                )
            else:
                report.succeeded.append(plugin.name)
                logger.debug("[PluginLoader] deactivated: plugin=%s", plugin.name)

        logger.info(
            "[PluginLoader] deactivate_all done: ok=%d failed=%d",
            len(report.succeeded), len(report.failed),
        )
        return report
