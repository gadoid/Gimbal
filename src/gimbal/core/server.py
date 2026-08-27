"""Server 模式入口 —— 常驻 HTTP 服务,接收 Scenario dict 并执行。

最小实现(#4 运行链路):单进程 uvicorn + FastAPI,一个端点
``POST /run``。每个请求走与 CLI ``run launch`` 完全一致的生命周期:
``bootstrap → Scenario.model_validate → Engine.run → shutdown``
(每请求独立 bootstrap,无跨请求共享状态;Engine.run 内部保证每次
run 相互独立)。执行经 ``asyncio.to_thread`` 下放线程,事件循环
不被阻塞;``asyncio.Lock`` 串行 —— 引擎的插件/事件设施按单 run
设计,并发 run 的安全性未验证前先不放开。

默认端口 8766:8765 已被 gimbal-plate 实占(run_plate.py)。
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import typer

from gimbal.cli.context import CLIContext
from gimbal.log import get_logger

logger = get_logger(__name__)


@dataclass
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 8766
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


# ─── 请求/响应模型(模块级:FastAPI 签名解析不支持函数内局部类) ──

def _define_models() -> tuple[type, type]:
    """惰性定义(导入期不依赖 fastapi)+ 模块级注册,见 _RunRequest。"""
    from pydantic import BaseModel, Field

    class RunRequest(BaseModel):
        """POST /run 请求体。

        ``scenario`` 是 gimbal ``Scenario`` 的 dict 形态(平台侧由
        plate convert 产出的 gimbal 可执行 dict);``halt_at`` /
        ``halt_reason`` 对应 CLI ``--step-to`` / 调试暂停语义。
        """
        scenario: dict = Field(..., description="gimbal Scenario dict")
        halt_at: int | None = Field(None, description="执行到该 step index(0-based,含)后停")
        halt_reason: str = Field("server-request", description="halt 原因记录")

    class RunResponse(BaseModel):
        exitCode: int
        total: int
        passed: int
        failed: int
        skipped: int
        halted: int
        details: list[dict] = Field(default_factory=list)
        runId: str = Field("", description="引擎生成的 run_id")

    return RunRequest, RunResponse


_MODELS = _define_models()
RunRequest = _MODELS[0]
RunResponse = _MODELS[1]


# ─── app 工厂 ─────────────────────────────────────────────────────

def create_app(cli_ctx: CLIContext) -> "FastAPI":
    """构建 FastAPI 应用。暴露 create_app 便于测试(TestClient)与
    未来其它托管方式(uvicorn worker / 容器)复用。"""
    from fastapi import FastAPI, HTTPException

    app = FastAPI(title="Gimbal runner", version="0.1.0")
    # 引擎设施(EventBus/插件/Reporter)按单 run 设计 → 串行执行
    run_lock = asyncio.Lock()

    @app.post("/run", response_model=RunResponse)
    async def run(req: RunRequest) -> RunResponse:
        from gimbal.core.scenario_runner import RuntimeControl
        from gimbal.schema.scenario import Scenario

        # 校验放锁外:快失败不占执行通道
        try:
            scenario = Scenario.model_validate(req.scenario)
        except Exception as exc:  # noqa: BLE001 - pydantic ValidationError 统一翻译
            raise HTTPException(status_code=422, detail=f"scenario validation failed: {exc}") from exc

        runtime_control = None
        if req.halt_at is not None:
            runtime_control = RuntimeControl(
                halt_at=req.halt_at, halt_reason=req.halt_reason
            )

        # bootstrap→run→shutdown 整体放线程(同步代码),锁保证串行
        def _execute() -> "RunResult":
            from gimbal.core.bootstrap import bootstrap, shutdown
            from gimbal.core.runner import Engine, RunResult

            configuration = bootstrap(cli_ctx)
            engine = Engine(configuration)
            try:
                return engine.run(scenario, runtime_control=runtime_control)
            finally:
                shutdown(configuration)

        async with run_lock:
            result = await asyncio.to_thread(_execute)

        return RunResponse(
            exitCode=result.exit_code,
            total=result.total,
            passed=result.passed,
            failed=result.failed,
            skipped=result.skipped,
            halted=result.halted,
            details=result.details,
            runId="",
        )

    @app.get("/healthz")
    async def healthz() -> dict:
        return {"ok": True}

    return app  # type: ignore[return-value]


def start_server(ctx: CLIContext, config: ServerConfig) -> int:
    """启动 uvicorn 阻塞服务。Ctrl-C / SIGTERM 由 uvicorn 处理退出。"""
    import uvicorn

    app = create_app(ctx)
    listen = config.unix_socket or f"{config.host}:{config.port}"
    logger.info("[Server] Starting: listen={} mode={} auth={}", listen, config.mode, config.auth)
    typer.echo(typer.style(f"[Server] Serving on {listen}", fg=typer.colors.GREEN, bold=True))
    if config.auth != "none":
        # 阶段 1 只实现 auth=none(本机回环默认);token 模式留给后续。
        logger.warning("[Server] auth={} requested but not implemented yet; serving without auth", config.auth)

    uvicorn.run(
        app,  # type: ignore[arg-type]
        host=config.host,
        port=config.port,
        # 引擎单请求串行,多 worker 只会复制进程不带来吞吐,默认 1。
        workers=1,
        log_level="info",
    )
    return 0
