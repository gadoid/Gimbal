"""gimbal run server —— 作为常驻服务接收任务并执行。"""
from __future__ import annotations

from typing import Annotated

import typer

from gimbal.cli.common import AuthMode, ServerMode
from gimbal.cli.context import CLIContext
from gimbal.core.server import ServerConfig, start_server


def server(
    ctx: typer.Context,
    # ========== 网络监听 ==========
    host: Annotated[
        str,
        typer.Option("--host", help="监听地址。生产环境用 0.0.0.0。", rich_help_panel="网络监听"),
    ] = "127.0.0.1",
    port: Annotated[
        int,
        typer.Option("--port", min=1, max=65535, help="监听端口。", rich_help_panel="网络监听"),
    ] = 8765,
    unix_socket: Annotated[
        str | None,
        typer.Option(
            "--unix-socket",
            help="使用 unix socket 替代 TCP。",
            rich_help_panel="网络监听",
            dir_okay=False,
        ),
    ] = None,
    # ========== 协议与认证 ==========
    mode: Annotated[
        ServerMode,
        typer.Option("--mode", help="通信协议。", rich_help_panel="协议与认证"),
    ] = ServerMode.http,
    auth: Annotated[
        AuthMode,
        typer.Option("--auth", help="认证方式。", rich_help_panel="协议与认证"),
    ] = AuthMode.none,
    token_file: Annotated[
        str | None,
        typer.Option(
            "--token-file",
            help="token 文件路径，配合 --auth=token。",
            rich_help_panel="协议与认证",
            exists=True, dir_okay=False,
        ),
    ] = None,
    allow_origin: Annotated[
        list[str] | None,
        typer.Option("--allow-origin", help="CORS 允许的 origin，可重复。", rich_help_panel="协议与认证"),
    ] = None,
    # ========== 集群与可观测 ==========
    health_port: Annotated[
        int | None,
        typer.Option("--health-port", min=1, max=65535, help="健康检查独立端口。", rich_help_panel="集群与可观测"),
    ] = None,
    # ========== 生命周期 ==========
    graceful_timeout: Annotated[
        int,
        typer.Option("--graceful-timeout", min=0, max=3600, help="优雅关闭等待时间（秒）。", rich_help_panel="生命周期"),
    ] = 30,
) -> None:
    """Typer 命令：构造 ServerConfig 后阻塞调用 start_server 启动常驻服务，Ctrl-C 触发优雅关闭。"""
    """作为服务监听端口，接收任务并执行。

    [bold]示例：[/bold]

      gimbal run server --port=8765
      gimbal run server --host=0.0.0.0
      gimbal run server --health-port=8080
      gimbal run server --auth=token --token-file=/etc/gimbal/token
    """
    cli_ctx: CLIContext = ctx.obj

    if auth == AuthMode.token and not token_file:
        raise typer.BadParameter("--auth=token 需要同时指定 --token-file。")

    config = ServerConfig(
        host=host,
        port=port,
        unix_socket=unix_socket,
        mode=mode.value,
        auth=auth.value,
        token_file=token_file,
        allow_origins=allow_origin or [],
        health_port=health_port,
        graceful_timeout=graceful_timeout,
    )

    try:
        exit_code = start_server(cli_ctx, config)
        raise typer.Exit(code=exit_code)
    except KeyboardInterrupt:
        typer.echo("\nShutting down gracefully...")
        raise typer.Exit(code=0)