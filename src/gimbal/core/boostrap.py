from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

from gimbal.cli.context import CLIContext
from gimbal.config.loader import ConfigLoader, BootstrapConfig

if TYPE_CHECKING :
    from gimbal.context.manager import ContextManager


@dataclass(frozen=True)
class Configuration:
    """bootstrap 的唯一产出。

    持有：
        - cfg：合并后的完整配置快照（frozen）
        - 基础设施引用：ctx_manager / dispatcher / event_bus / archive

    不持有任何层级 Context（framework/suite/scenario/step），
    这些在 Engine.run() 时按执行生命周期创建。

    frozen=True：产出后不可修改，Engine 只读取，不覆盖。
    """
    cfg: BootstrapConfig
    ctx_manager: ContextManager
    dispatcher: Any
    # 以下两个供需要直接访问基础设施的场景（reporter、plugin 等）
    event_bus: Any
    archive: Any

logger = logging.getLogger(__name__)


def bootstrap(cli_ctx: CLIContext) -> Configuration:
    """框架启动唯一入口。
    加载优先级 gimbal.yaml -> env -> mode -> cli -> 环境变量

    职责：
        1. 多来源配置合并 → BootstrapConfig
        2. 配置日志系统
        3. 初始化基础设施
        4. 返回 Configuration

    不创建任何层级 Context（由 Engine.run() 负责）。
    """
    # 1. 配置合并
    cfg = ConfigLoader().load(cli_ctx)


    # 2. 日志（最先，后续所有日志才能正确输出）
    _configure_logging(cfg)


    logger.debug(
        "[bootstrap] env=%s mode=%s log_level=%s",
        cfg.env, cfg.mode, cfg.log_level,
    )

    # 3. 基础设施
    from gimbal.events.bus import InMemoryEventBus
    from gimbal.repository.backends.filesystem import InMemoryArchive
    from gimbal.context.manager import ContextManager
    from gimbal.strategy.dispatcher import build_default_dispatcher

    event_bus = InMemoryEventBus()
    archive   = InMemoryArchive()
    return Configuration(
        cfg=cfg,
        ctx_manager=ContextManager(archive=archive, event_bus=event_bus),
        dispatcher=build_default_dispatcher(),
        event_bus=event_bus,
        archive=archive,
    )


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
