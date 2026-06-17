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
        - auth_registry：可变的 AuthSession 容器（运行期 token 状态）
        - 基础设施引用：ctx_manager / dispatcher / event_bus / archive
        - 插件设施：hook_registry / plugin_registry
        - plugins：已激活的插件实例（仅持有引用，不调用其方法）
        - reporter_runtime：Reporter 调度器，Engine.run() 阶段驱动

    不持有任何层级 Context（framework/suite/scenario/step），
    这些在 Engine.run() 时按执行生命周期创建。

    frozen=True：产出后不可修改，Engine 只读取，不覆盖。
    唯一例外是 auth_registry——它是引用类型，引用本身不变，但其内部状态可变。
    """
    cfg: BootstrapConfig
    auth_registry: Any  # gimbal.auth.registry.AuthRegistry（不强制类型以避免循环导入）
    ctx_manager: "ContextManager"
    dispatcher: Any
    # 以下供需要直接访问基础设施的场景（reporter、plugin 等）
    event_bus: Any
    archive: Any
    # 插件设施
    hook_registry: "HookRegistry"
    plugin_registry: Any
    plugins: tuple["Plugin", ...] = field(default_factory=tuple)
    # Reporter 调度器（Engine.run() 时通过 begin_all / finalize_all 驱动）
    reporter_runtime: Any = None

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
    try:
        configure_logging_from_cli(cli_ctx)
    except Exception:
        pass  # 日志初始化失败不应阻断 bootstrap 流程

    # 2. 配置合并
    cfg = ConfigLoader().load(cli_ctx)

    # 3. 日志（用最终配置重新设置，确保 bootstrap 阶段的日志也受控制）
    from gimbal.log.integration import configure_logging_from_bootstrap
    configure_logging_from_bootstrap(cfg)
    logger.info("[bootstrap] 配置加载完成: env={} mode={}", cfg.env, cfg.mode)

    # 4. 基础设施
    logger.info("[bootstrap] 初始化基础设施...")
    from gimbal.events.bus import InMemoryEventBus
    from gimbal.context.archive import InMemoryArchive
    from gimbal.context.manager import ContextManager
    from gimbal.strategy.dispatcher import build_default_dispatcher
    from gimbal.core.hooks import HookRegistry
    from gimbal.plugins import PluginRegistry
    from gimbal.auth.registry import AuthRegistry

    event_bus = InMemoryEventBus()
    archive = InMemoryArchive()
    hook_registry = HookRegistry()
    plugin_registry = PluginRegistry()
    auth_registry = AuthRegistry()
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

    # 7. 装配 Reporter runtime（自注册所有内置 reporter）
    from gimbal.reporter.registry import ReporterRegistry
    from gimbal.reporter.runtime import ReporterRuntime
    from gimbal.reporter.builtin import register_builtin_reporters

    reporter_registry = ReporterRegistry()
    register_builtin_reporters(reporter_registry)
    reporter_runtime = ReporterRuntime(reporter_registry)
    reporter_runtime.setup(bus=event_bus, config=cfg)
    logger.info("[bootstrap] Reporter runtime 就绪: builtins={}", reporter_registry.available())

    return Configuration(
        cfg=cfg,
        auth_registry=auth_registry,
        ctx_manager=ctx_manager,
        dispatcher=dispatcher,
        event_bus=event_bus,
        archive=archive,
        hook_registry=hook_registry,
        plugin_registry=plugin_registry,
        plugins=tuple(plugins),
        reporter_runtime=reporter_runtime,
    )


def _load_plugins(
    cfg: BootstrapConfig,
    *,
    event_bus: Any,
    hook_registry: Any,
    plugin_registry: Any,
) -> list["Plugin"]:
    """插件发现 → 解析依赖 → 加载 → 激活。

    失败容错策略（分阶段、按异常类型区分）：

        1. discover()     —— 内部已对每个 manifest 单独 try/except，
                            顶层只兜底"入口点扫描异常"这种结构性故障。
        2. resolve_deps() —— 循环依赖是结构性错误，必须快速失败。
        3. load_all()     —— 内部已隔离单插件 import / 加载失败。
        4. activate_all() —— 内部已隔离单插件激活失败。

    整体约定：单插件失败绝不影响其它插件；只有"整个发现阶段崩了"
    或"循环依赖"才视为致命错误并中断 bootstrap。
    """
    from gimbal.plugins import PluginLoader

    plugins_dir = cfg.base_dir / cfg.plugins_dir
    white = set(cfg.plugins) if cfg.plugins else None   # 空 = 全部启用
    loader = PluginLoader(plugins_dir=plugins_dir, enabled_filter=white)

    # Step 1: 发现（filesystem / manifest 错误已内部隔离；入口点扫描故障回退到空）
    try:
        specs = loader.discover()
    except (OSError, ImportError) as e:
        # OSError：plugins_dir 不可访问（权限 / 消失）
        # ImportError：entry_point 解析时元数据损坏
        logger.error("[bootstrap] 插件发现结构性失败: {}: {}", type(e).__name__, e)
        return []

    # Step 2: 依赖解析（ValueError = 循环依赖，必须让用户看见）
    try:
        specs = loader.resolve_deps(specs)
    except ValueError as e:
        logger.error("[bootstrap] 依赖解析失败: {}", e)
        return []

    # Step 3 + 4: 加载 + 激活（loader 内部已做单插件隔离，无需外层 try/except）
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
    """框架关闭入口。

    步骤：
        1. 触发 FRAMEWORK_TEARDOWN 钩子
        2. 走 PluginLoader.deactivate_all() 统一卸载所有插件
           （它负责：on_deactivate + event unsubscribe + hook unregister + plugin registry unregister）
        3. 停 EventBus

    卸载的失败/成功以 DeactivateReport 形式报告，调用方按需处理。

    修复 B10：幂等性——重复调用安全，不会重复触发钩子/卸载插件/停 bus。
    """
    from gimbal.core.hooks import HookPoint
    from gimbal.plugins import PluginLoader

    # 修复 B10：幂等性检查
    # 用一个属性标记是否已 shutdown（不是用 is None，因为 Configuration 是 frozen）
    if getattr(configuration, "_gimbal_shutdown_done", False):
        logger.debug("[bootstrap] shutdown() 已调用过，跳过重复执行")
        return
    object.__setattr__(configuration, "_gimbal_shutdown_done", True)

    # 1. 触发 TEARDOWN 钩子（钩子中可改写 cleanup 顺序或补充清理）
    configuration.hook_registry.trigger(
        HookPoint.FRAMEWORK_TEARDOWN,
        {"cfg": configuration.cfg},
    )

    # 2. 统一插件卸载入口（唯一卸载路径，详见 PluginLoader.deactivate_all 文档）
    loader = PluginLoader()  # 不需要 dir / filter，只用它的 deactivate_all
    report = loader.deactivate_all(
        list(configuration.plugins),
        plugin_registry=configuration.plugin_registry,
    )
    if not report.all_ok:
        total = len(report.succeeded) + len(report.failed)
        logger.error(
            "[bootstrap] 部分插件卸载失败 ({} / {}): {}",
            len(report.failed), total, report.failed,
        )

    # 2.5 兜底清空 hook_registry。
    #     Plugin.register_hook() 会把 hook_id 记到 Plugin.registered_hook_ids 里，
    #     deactivate_all 会按这个列表 unregister。但有些代码路径会绕过
    #     Plugin.register_hook，直接调用 ctx.hook_registry.register()——
    #     这种 hook 没被任何 plugin 记录，deactivate_all 不会清掉。
    #     shutdown 时统一 clear()，保证下一次 bootstrap 启动时不残留旧 hook。
    remaining = configuration.hook_registry.list_hooks()
    if remaining:
        logger.warning(
            "[bootstrap] hook_registry 还有 {} 个未清空的 hook（绕过 Plugin.register_hook 注册的），shutdown 兜底 clear",
            len(remaining),
        )
        configuration.hook_registry.clear()

    # 3. 停 EventBus
    configuration.event_bus.stop()


def _configure_logging(cfg: BootstrapConfig) -> None:
    """根据 cfg.log_level 配置全局 logging。

    入参:
        cfg: 引导配置，使用其中的 log_level 字段。
    副作用:
        调用 logging.basicConfig(force=True) 覆盖既有配置；
        将 httpx / httpcore 的日志级别强制设为 WARNING，避免噪音。
    """
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
