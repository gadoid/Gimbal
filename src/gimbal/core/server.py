"""Server 模式入口 —— 常驻 HTTP 服务,接收 Scenario dict 并执行。

最小实现(#4 运行链路):单进程 uvicorn + FastAPI,一个端点
``POST /run``。每个请求走与 CLI ``run launch`` 完全一致的生命周期:
``bootstrap → Scenario.model_validate → Engine.run → shutdown``
(每请求独立 bootstrap,无跨请求共享状态;Engine.run 内部保证每次
run 相互独立)。执行经 ``asyncio.to_thread`` 下放线程,事件循环
不被阻塞;``asyncio.Lock`` 串行 —— 引擎的插件/事件设施按单 run
设计,并发 run 的安全性未验证前先不放开。

默认端口 8766:8765 已被 gimbal-plate 实占(run_plate.py)。

进程自守卫(2026-11-03 执行器泄漏复盘):平台每次执行 spawn 一个本服务,
回收只有协作式 ``close()`` 一条路 —— 父进程被硬杀(SIGKILL/Bash 超时/
pytest 带会话退出)就没人 terminate,21 个旧执行器以 PPID=1 空转两周。
本模块自带两道与父进程生死解耦的退出路径,任一触发即 ``Server.should_exit``
优雅收口(在飞 run 跑完、SSE 发完 done 再退):
  - **stdin 守卫**:stdin 是管道(平台 spawn 时 ``stdin=PIPE``)才布防,
    读到 EOF = 父进程死亡/显式关管道 → 退出。tty/devnull/文件不布防,
    手动运行与 pytest 捕获 stdin 的场景不受影响;跨平台(Windows 无
    PDEATHSIG,这是唯一守卫);
  - **空闲 TTL**:无在飞 run 且距最近一次 run 启动/收口 ≥ ``idle_timeout``
    即退出(默认 1800s,``--idle-timeout 0`` 关闭)。调试会话挂起时 run
    仍是 running,不会被判闲置;收口也计活动 —— 长 run 结束瞬间不会被
    「启动时刻 + TTL」误判。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI

import asyncio
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import typer

from gimbal.cli.context import CLIContext
from gimbal.core.proc_guard import start_stdin_guard
from gimbal.schema import RunOptions  # noqa: F401（RunsRequest 类型引用）
from gimbal.log import get_logger
from gimbal.version import __version__

logger = get_logger(__name__)

# server cancel 端点接受的 scope 集合(graph 单元级取消方案 §6「可」项):
# healthz 据此上报能力位 —— 旧执行器 body 无 cancel_scopes 键 = 空能力,
# 平台按「不可单元级取消」处理(409)而非把 scope=unit 当 step 执行
# (旧实现带 A0 缺陷:取消会跳过 after 括号)。
SERVER_CANCEL_SCOPES = ("step", "unit")


@dataclass
class ServerConfig:
    """v2.1 批次 F：舰队参数（workers/queue_size/register_to/heartbeat/
    metrics_port/pidfile/max_concurrent）已删除——server 收窄为
    单 run + 调试会话端点；舰队管理属否决项（总案 X 清单）。"""
    host: str = "127.0.0.1"
    port: int = 8766
    unix_socket: str | None = None
    mode: str = "http"
    auth: str = "none"
    token_file: str | None = None
    allow_origins: list[str] = field(default_factory=list)
    health_port: int | None = None
    graceful_timeout: int = 30
    # 空闲自退(秒;≤0 关闭)。见模块 docstring「进程自守卫」。
    idle_timeout: float = 1800.0


# 空闲 TTL 检查周期(秒;测试可 patch 缩短)
_IDLE_CHECK_INTERVAL_SEC = 15.0


# ─── 进程自守卫(父进程生死解耦的退出路径) ─────────────────────────
# stdin 守卫实现在 gimbal.core.proc_guard(launch 链同款共用);本模块
# 只保留 server 特有的空闲 TTL 判定与看门狗。

def _idle_should_exit(app: Any, timeout_s: float, now: "float | None" = None) -> bool:
    """真闲判定:无在飞 run 且距最近活动(run 启动/收口)≥ timeout。

    注册表与活动时刻由 server_debug.register_debug_endpoints 挂在
    ``app.state``(runs_registry / runs_lock / runs_last_activity)。
    """
    if timeout_s <= 0:
        return False
    st = app.state
    with st.runs_lock:
        busy = any(e.get("status") == "running" for e in st.runs_registry.values())
        last = st.runs_last_activity
    if busy:
        return False
    return (time.monotonic() if now is None else now) - last >= timeout_s


def _start_idle_watchdog(app: Any, timeout_s: float,
                         on_idle: Callable[[], None]) -> "threading.Thread | None":
    """空闲 TTL 看门狗线程:周期判定 ``_idle_should_exit`` → ``on_idle()``。"""
    if timeout_s <= 0:
        return None
    # 检查周期:TTL 很小时相应缩短(短 TTL 多为测试/精确收口场景,等满
    # 15s 粒度没意义);默认 TTL 下就是 _IDLE_CHECK_INTERVAL_SEC。
    interval = min(_IDLE_CHECK_INTERVAL_SEC, max(timeout_s / 4.0, 1.0))

    def _watch() -> None:
        while True:
            time.sleep(interval)
            try:
                if _idle_should_exit(app, timeout_s):
                    break
            except Exception:  # noqa: BLE001 — 看门狗自身异常不伤服务,下轮再看
                logger.warning("[Server] 空闲看门狗判定异常(已忽略)")
        logger.info("[Server] 空闲 {}s 无 run,执行器自退", int(timeout_s))
        on_idle()

    t = threading.Thread(target=_watch, name="gimbal-idle-watchdog", daemon=True)
    t.start()
    return t


# ─── 请求/响应模型(模块级:FastAPI 签名解析不支持函数内局部类) ──

def _define_models() -> tuple[type, ...]:
    """惰性定义(导入期不依赖 fastapi)+ 模块级注册,见 _RunRequest。"""
    from pydantic import BaseModel, Field

    from gimbal.schema.debug import DebugCommand  # noqa: F401（N6 结构化命令）

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

    class M2Info(BaseModel):
        """M2 §5.1 代际门：请求携带的构建身份（plate /convert 响应附带）。"""
        hash: str = Field("", description="m2_hash")
        generation: int = Field(0, description="m2_generation")

    class RunsRequest(BaseModel):
        """POST /runs（M2 §2.3 M10 改形）：``{target, options, m2?}``。

        执行参数全部收进 ``options: RunOptions``（M2 A 类，D1 落实）；
        ``halt_at`` 并入 ``options.step_to``。
        """
        target: dict = Field(..., description="Scenario/Suite/Graph dict（按 kind 分派）")
        options: "RunOptions | None" = Field(
            None, description="执行指令（M2 RunOptions；缺省全默认）")
        m2: M2Info | None = Field(
            None, description="构建身份（代际门，M2 §5.1）")

    class RunsCreated(BaseModel):
        runId: str
        debugEnabled: bool = False

    class DebugCommandRequest(BaseModel):
        """N6（P3-04）：结构化调试命令（pydantic 校验即红线）。"""
        command: "DebugCommand" = Field(..., description="调试命令（continue/step/abort/read/write/patch/retry/skip）")

    class DebugCommandResponse(BaseModel):
        accepted: bool
        output: list[str] = Field(default_factory=list)

    class CancelRequest(BaseModel):
        """POST /runs/{id}/cancel 可选请求体（graph 单元级取消方案 2026-11-02 E1）。

        scope=step（缺省,C12 既有行为）:在飞场景在步骤边界停、未启动主体单元
        短路;scope=unit:只停调度 —— 在飞单元跑完(含其 n_runs × retry),未
        启动的主体单元记 cancelled,after 括号照常。同一 run 先 unit 后 step
        按更强的 step 生效,反向忽略。
        """
        scope: str = Field("step", pattern="^(step|unit)$")

    class CancelResponse(BaseModel):
        """POST /runs/{id}/cancel：协作取消已请求（步骤边界/未启动单元生效）。"""
        accepted: bool
        runId: str
        scope: str = "step"

    class DebugCommandResponse(BaseModel):
        accepted: bool
        output: list[str] = Field(default_factory=list)

    return (RunsRequest, RunsCreated,
            DebugCommandRequest, DebugCommandResponse, CancelResponse,
            CancelRequest)


_MODELS = _define_models()
(RunsRequest, RunsCreated,
 DebugCommandRequest, DebugCommandResponse, CancelResponse,
 CancelRequest) = _MODELS


# ─── app 工厂 ─────────────────────────────────────────────────────

def create_app(cli_ctx: CLIContext) -> "FastAPI":
    """构建 FastAPI 应用。暴露 create_app 便于测试(TestClient)与
    未来其它托管方式(uvicorn worker / 容器)复用。"""
    from fastapi import FastAPI, HTTPException

    app = FastAPI(title="Gimbal runner", version=__version__)
    # 引擎设施(EventBus/插件/Reporter)按单 run 设计 → 串行执行
    run_lock = asyncio.Lock()

    # M10（M2 §3）：POST /run 旧端点已删除——平台已改用 POST /runs，
    # 第二种参数形状（halt_at 裸传）不留（不为旧端点保留兼容形态）。

    # ── v2.1 批次 E：异步 run + 调试会话 + SSE（独立模块，同 app 挂载）──
    from gimbal.core.server_debug import register_debug_endpoints
    register_debug_endpoints(app, cli_ctx, (
        RunsRequest, RunsCreated, DebugCommandRequest, DebugCommandResponse,
    ))

    @app.get("/healthz")
    async def healthz() -> dict:
        # 能力上报:平台 ServerSession.start 建连时轮询本端点(只看 200 →
        # 现在也读 body),据此记录执行器版本与 cancel 能力位。
        return {"ok": True, "version": __version__,
                "cancel_scopes": list(SERVER_CANCEL_SCOPES)}

    return app  # type: ignore[return-value]


def start_server(ctx: CLIContext, config: ServerConfig) -> int:
    """启动 uvicorn 阻塞服务。Ctrl-C / SIGTERM 由 uvicorn 处理退出。"""
    import uvicorn

    app = create_app(ctx)
    listen = config.unix_socket or f"{config.host}:{config.port}"
    logger.info("[Server] Starting: listen={} mode={} auth={}", listen, config.mode, config.auth)
    typer.echo(typer.style(f"[Server] Serving on {listen}", fg=typer.colors.GREEN, bold=True))
    import os as _os
    _token = _os.environ.get("GIMBAL_SERVER_TOKEN") or None
    if config.auth == "token" and _token is None:
        # S-6:token 模式必须显式提供令牌,缺令牌直接拒绝启动(不再静默裸跑)
        logger.error("[Server] auth=token 但 GIMBAL_SERVER_TOKEN 未配置;拒绝启动")
        typer.secho("[Server] auth=token 需要 GIMBAL_SERVER_TOKEN 环境变量", fg=typer.colors.RED, err=True)
        return 2
    if _token is not None:
        typer.echo("[Server] token auth enabled (GIMBAL_SERVER_TOKEN): /runs 家族端点要求 Bearer/X-Gimbal-Token")
    elif config.host not in ("127.0.0.1", "localhost", "::1"):
        typer.echo("[Server] warning: 无 token 且监听非回环地址,POST /runs 将拒绝非回环来源(403)")

    # uvicorn.Server 直控(不用 uvicorn.run 便捷封装):守卫线程需要
    # ``server.should_exit`` 句柄 —— 置位即 uvicorn 官方优雅收口(拒绝
    # 新连接,在飞请求/SSE 跑完再退),与 Ctrl-C/SIGTERM 同一条路径。
    # Server 本就单进程,uvicorn.run(workers=1) 语义等价。
    uconfig = uvicorn.Config(
        app,  # type: ignore[arg-type]
        host=config.host,
        port=config.port,
        log_level="info",
        # AD8:不装 uvicorn 自带彩色 logging 配置 —— 其日志改经 root →
        # InterceptHandler 桥进 loguru,输出 JSON 行(顺带可入库)。桥接行
        # 无 exec_context,category 落 core,按 unit/step 过滤时自然排除。
        # access log 由 _silence_noisy_loggers 压到 WARNING。
        log_config=None,
    )
    server = uvicorn.Server(uconfig)
    # 进程自守卫(模块 docstring):任一触发 → should_exit 优雅自退。
    start_stdin_guard(lambda: setattr(server, "should_exit", True))
    _start_idle_watchdog(app, config.idle_timeout,
                         lambda: setattr(server, "should_exit", True))
    server.run()
    return 0
