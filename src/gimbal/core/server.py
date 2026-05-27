"""Server 模式入口。占位实现。"""
from __future__ import annotations

from dataclasses import dataclass, field

import typer

from gimbal.cli.context import CLIContext
from gimbal.log import get_logger

logger = get_logger(__name__)


@dataclass
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 8765
    unix_socket: str | None = None
    workers: int = 4
    max_concurrent: int = 10
    queue_size: int = 100
    mode: str = "http"
    auth: str = "none"
    token_file: str | None = None
    allow_origins: list[str] = field(default_factory=list)
    register_to: str | None = None
    heartbeat_interval: int = 30
    health_port: int | None = None
    metrics_port: int | None = None
    graceful_timeout: int = 30
    pidfile: str | None = None


def start_server(ctx: CLIContext, config: ServerConfig) -> int:
    """启动服务。占位实现。

    实际实现建议：
      - HTTP 模式用 FastAPI + uvicorn
      - 任务队列用 asyncio.Queue 或外接 Redis
      - worker 池可用 ProcessPoolExecutor
      - 注册到调度中心后台维持心跳协程
    """
    listen = config.unix_socket or f"{config.host}:{config.port}"
    logger.info("[Server] Starting: listen={} mode={} auth={}", listen, config.mode, config.auth)
    logger.info("[Server] Configuration: workers={} max_concurrent={} queue_size={}",
                config.workers, config.max_concurrent, config.queue_size)
    if config.register_to:
        logger.info("[Server] Will register to: {}", config.register_to)
    typer.echo(typer.style(f"[Server] Starting on {listen}", fg=typer.colors.GREEN, bold=True))
    typer.echo(f"[Server] mode={config.mode}, auth={config.auth}")
    typer.echo(f"[Server] workers={config.workers}, max_concurrent={config.max_concurrent}")
    if config.register_to:
        typer.echo(f"[Server] Will register to {config.register_to}")
    typer.echo(typer.style("[Server] (placeholder, not actually serving)", fg=typer.colors.YELLOW))
    logger.warning("[Server] Running in placeholder mode - not actually serving requests")
    return 0