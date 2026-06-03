from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING, Optional

from gimbal.cli.context import CLIContext
from gimbal.config.loader import ConfigLoader, BootstrapConfig

if TYPE_CHECKING:
    from gimbal.context.manager import ContextManager
    from gimbal.core.hooks import HookRegistry
    from gimbal.plugins import Plugin


@dataclass(frozen=True)
class Configuration:
    """bootstrap 的唯一产出。

    持有：
        - cfg：合并后的完整配置快照（frozen）
        - 基础设施引用：ctx_manager / dispatcher / event_bus / archive
        - 插件设施：hook_registry / plugin_registry
        - plugins：已激活的插件实例（仅持有引用，不调用其方法）

    不持有任何层级 Context（framework/suite/scenario/step），
    这些在 Engine.run() 时按执行生命周期创建。

    frozen=True：产出后不可修改，Engine 只读取，不覆盖。
    """
    cfg: BootstrapConfig
    ctx_manager: "ContextManager"
    dispatcher: Any
    # 以下供需要直接访问基础设施的场景（reporter、plugin 等）
    event_bus: Any
    archive: Any
    # 插件设施
    hook_registry: "HookRegistry"
    plugin_registry: Any
    plugins: tuple["Plugin", ...] = field(default_factory=tuple)

from gimbal.log import get_logger
logger = get_logger(__name__)


def bootstrap(cli_ctx: CLIContext) -> Configuration:
    """框架启动唯一入口。
    加载优先级 gimbal.yaml -> env -> mode -> cli -> 环境变量

    职责：
        1. 配置日志系统（最先，在任何 logger 调用之前）
        2. 多来源配置合并 → BootstrapConfig
        3. 初始化基础设施（EventBus / Archive / ContextManager / Dispatcher / HookRegistry / PluginRegistry）
        4. 加载并激活插件
        5. 触发 FRAMEWORK_INIT hook（可被插件用来注册全局监听、初始化连接池等）
        6. 返回 Configuration

    不创建任何层级 Context（由 Engine.run() 负责）。
    """
    # 1. 日志系统（最先，在任何 logger 调用之前）
    from gimbal.log.integration import configure_logging_from_cli
    configure_logging_from_cli(cli_ctx)

    # 2. 配置合并
    cfg = ConfigLoader().load(cli_ctx)

    # 3. 日志（用最终配置重新设置，确保 bootstrap 阶段的日志也受控制）
    from gimbal.log.integration import configure_logging_from_bootstrap
    configure_logging_from_bootstrap(cfg)
    logger.info("[bootstrap] 配置加载完成: env={} mode={}", cfg.env, cfg.mode)

    # 4. 基础设施
    logger.info("[bootstrap] 初始化基础设施...")
    from gimbal.events.bus import InMemoryEventBus
    from gimbal.repository.backends.filesystem import InMemoryArchive
    from gimbal.context.manager import ContextManager
    from gimbal.strategy.dispatcher import build_default_dispatcher
    from gimbal.core.hooks import HookRegistry
    from gimbal.plugins import PluginRegistry

    event_bus = InMemoryEventBus()
    archive = InMemoryArchive()
    hook_registry = HookRegistry()
    plugin_registry = PluginRegistry()
    ctx_manager = ContextManager(archive=archive, event_bus=event_bus)
    dispatcher = build_default_dispatcher(hook_registry=hook_registry)

    logger.info(
        "[bootstrap] 基础设施初始化完成: EventBus, Archive, ContextManager, "
        "Dispatcher, HookRegistry, PluginRegistry"
    )

    # 5. 插件发现 / 加载 / 激活
    plugins = _load_plugins(
        cfg,
        event_bus=event_bus,
        hook_registry=hook_registry,
        plugin_registry=plugin_registry,
    )
    logger.info("[bootstrap] 插件加载完成: count={}", len(plugins))

    # 6. 触发 FRAMEWORK_INIT 钩子（在插件激活后；允许插件"接管"框架启动）
    from gimbal.core.hooks import HookPoint
    init_result = hook_registry.trigger(
        HookPoint.FRAMEWORK_INIT,
        {"cfg": cfg, "ctx_manager": ctx_manager, "plugin_registry": plugin_registry},
    )
    if init_result.stopped:
        logger.warning(
            "[bootstrap] FRAMEWORK_INIT 被插件中断: plugin={} reason={}",
            init_result.stop_plugin, init_result.stop_reason,
        )

    return Configuration(
        cfg=cfg,
        ctx_manager=ctx_manager,
        dispatcher=dispatcher,
        event_bus=event_bus,
        archive=archive,
        hook_registry=hook_registry,
        plugin_registry=plugin_registry,
        plugins=tuple(plugins),
    )


def _load_plugins(
    cfg: BootstrapConfig,
    *,
    event_bus: Any,
    hook_registry: Any,
    plugin_registry: Any,
) -> list["Plugin"]:
    """插件发现 → 解析依赖 → 加载 → 激活。

    失败容错：单个插件失败不影响其它插件加载。
    """
    from gimbal.plugins import PluginLoader

    plugins_dir = cfg.base_dir / cfg.plugins_dir
    white = set(cfg.plugins) if cfg.plugins else None   # 空 = 全部启用
    loader = PluginLoader(plugins_dir=plugins_dir, enabled_filter=white)

    try:
        specs = loader.discover()
    except Exception as e:  # noqa: BLE001
        logger.error("[bootstrap] 插件发现失败: {}", e)
        return []

    try:
        specs = loader.resolve_deps(specs)
    except ValueError as e:
        logger.error("[bootstrap] 依赖解析失败: {}", e)
        return []

    plugins = loader.load_all(specs)
    activated = loader.activate_all(
        plugins,
        event_bus=event_bus,
        hook_registry=hook_registry,
        user_configs=cfg.plugin_configs or {},
        plugin_registry=plugin_registry,
    )
    return activated


def shutdown(configuration: Configuration) -> None:
    """框架关闭入口：停 EventBus / 卸载插件 / 触发 FRAMEWORK_TEARDOWN。"""
    from gimbal.core.hooks import HookPoint

    hook_registry = configuration.hook_registry
    hook_registry.trigger(
        HookPoint.FRAMEWORK_TEARDOWN,
        {"cfg": configuration.cfg},
    )

    # 插件反向卸载
    for plugin in reversed(configuration.plugins):
        try:
            plugin.deactivate()
        except Exception as e:  # noqa: BLE001
            logger.error("[bootstrap] 卸载插件失败 {}: {}", plugin.name, e)
        configuration.event_bus.unsubscribe_plugin(plugin.name)
        hook_registry.unregister_plugin(plugin.name)
        configuration.plugin_registry.unregister(plugin.name)

    configuration.event_bus.stop()


def _configure_logging(cfg: BootstrapConfig) -> None:
    level = {
        "debug":   logging.DEBUG,
        "info":    logging.INFO,
        "warning": logging.WARNING,
        "error":   logging.ERROR,
    }.get(cfg.log_level.lower(), logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        force=True,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
