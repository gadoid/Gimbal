"""core/server_debug.py — 异步 run + 调试会话 + SSE 事件流（v2.1 批次 E）。

挂在 create_app 产出的 FastAPI 应用上（server.py 调 register_debug_endpoints）：

  POST /runs                异步启动（单 run；立即返回 runId）
  GET  /runs/{id}           状态与摘要
  POST /runs/{id}/debug     调试命令（continue/step/retry/skip/abort/read/write/patch）
  GET  /runs/{id}/events    SSE 事件流（id=序号；批次 F 补 Last-Event-ID 续传）

鉴权（S-6）：
  - POST /runs：GIMBAL_SERVER_TOKEN 已配置 → Bearer/X-Gimbal-Token 匹配
    （401）；未配置 → 仅回环（127.0.0.1/::1/localhost）可启动，非回环 403；
  - debug / events 端点：要求 GIMBAL_SERVER_TOKEN 已配置且匹配（403/401）。
  - debug 请求校验：目标必须单单元（与 CLI --debug 同一条校验），否则 422。
注册表回收（S-6）：run 终态后 _REAP_TTL_SEC（默认 600s）由后台 Timer
回收条目（GET /runs/{id} 此后 404）。
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any

from fastapi import Request

from gimbal.log import get_logger

logger = get_logger(__name__)

# 类型注解需模块级可见（FastAPI get_type_hints 按函数所在模块的全局名解析；
# server.py 在 create_app() 内延迟导入本模块，此时 server 模块已初始化完毕）
from gimbal.core.server import (  # noqa: E402
    RunsRequest, RunsCreated, DebugCommandRequest, DebugCommandResponse,
)

NL = chr(10)

# run 终态后的注册表/事件缓冲回收时限（S-6;测试可 patch）
_REAP_TTL_SEC = 600.0


def register_debug_endpoints(app, cli_ctx, models=None) -> dict:
    """注册 /runs 家族端点；返回运行注册表（测试可注入/检查）。"""
    from fastapi import HTTPException, Header
    from fastapi.responses import StreamingResponse
    import os


    registry: dict[str, dict[str, Any]] = {}
    reg_lock = threading.Lock()

    def _require_token(authorization: str | None, x_token: str | None) -> None:
        token = os.environ.get("GIMBAL_SERVER_TOKEN") or None
        if token is None:
            raise HTTPException(
                status_code=403,
                detail="debug endpoints require GIMBAL_SERVER_TOKEN to be set",
            )
        supplied = x_token or (
            authorization[7:]
            if authorization and authorization.startswith("Bearer ")
            else None
        )
        if supplied != token:
            raise HTTPException(status_code=401, detail="invalid debug token")

    def _require_start_auth(request: "Any", authorization: str | None,
                            x_token: str | None) -> None:
        """POST /runs 鉴权（S-6）：token 配置 → 校验;未配置 → 仅回环。"""
        token = os.environ.get("GIMBAL_SERVER_TOKEN") or None
        if token is not None:
            supplied = x_token or (
                authorization[7:]
                if authorization and authorization.startswith("Bearer ")
                else None
            )
            if supplied != token:
                raise HTTPException(status_code=401, detail="invalid server token")
            return
        host = (request.client.host if request.client else "") or ""
        if host not in ("127.0.0.1", "::1", "localhost"):
            raise HTTPException(
                status_code=403,
                detail="POST /runs without GIMBAL_SERVER_TOKEN is loopback-only",
            )

    @app.post("/runs", response_model=RunsCreated)
    async def start_run(
        req: RunsRequest,
        request: Request,
        authorization: str | None = Header(default=None),
        x_gimbal_token: str | None = Header(default=None, alias="X-Gimbal-Token"),
    ) -> Any:
        from pydantic import TypeAdapter
        from gimbal.schema.scenario import RunUnion

        _require_start_auth(request, authorization, x_gimbal_token)
        try:
            target = TypeAdapter(RunUnion).validate_python(req.target)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=422, detail=f"target validation failed: {exc}"
            ) from exc

        # debug 单单元校验（S-6:与 CLI --debug 同一条校验函数）
        if req.debug is not None:
            from gimbal.core.debugger import debug_unit_count
            if debug_unit_count(target) != 1:
                raise HTTPException(
                    status_code=422,
                    detail="debug requires a single-unit target "
                           "(suite-level debug is not supported)",
                )

        with reg_lock:
            if any(e["status"] == "running" for e in registry.values()):
                raise HTTPException(
                    status_code=409, detail="one run at a time (single-run server)"
                )
            run_id = str(uuid.uuid4())
            # 调试会话在启动时就创建（不等 run 线程装载 debugger）：
            # 调用方可立即 POST debug 命令，命令入队等暂停点消费
            from gimbal.core.debugger import QueueSession
            session = QueueSession(
                timeout=req.debug.wait_timeout or 300.0) if req.debug else None
            registry[run_id] = {"status": "running", "result": None, "error": None,
                                "debugger": None, "session": session, "events": []}

        from gimbal.core.scenario_runner import RuntimeControl
        runtime_control = None
        if req.halt_at is not None or req.step_from is not None or req.debug is not None:
            runtime_control = RuntimeControl(
                halt_at=req.halt_at,
                halt_reason="server-request",
                step_from=req.step_from,
                debug_mode=req.debug is not None,   # 调试挂起不计 scenario 超时
            )

        entry = registry[run_id]

        def _execute():
            from gimbal.core.bootstrap import bootstrap, shutdown
            from gimbal.core.runner import Engine
            from gimbal.core.debugger import DebuggerPlugin, QueueSession

            configuration = bootstrap(cli_ctx)
            debugger = None
            try:
                # 事件缓冲：订阅全部事件到注册表（SSE 推流源）
                sub_id = configuration.event_bus.subscribe(
                    lambda e: entry["events"].append(_event_dict(e))
                )
                try:
                    if req.debug is not None:
                        debugger = DebuggerPlugin(
                            pause=req.debug.pause,
                            breakpoints=req.debug.breakpoints,
                            session=entry["session"],
                            event_bus=configuration.event_bus,
                            wait_timeout=req.debug.wait_timeout,
                        )
                        debugger.activate(configuration.hook_registry)
                        entry["debugger"] = debugger
                    engine = Engine(configuration)
                    entry["result"] = engine.run(
                        target, runtime_control=runtime_control)
                finally:
                    configuration.event_bus.unsubscribe(sub_id)
            finally:
                if debugger is not None:
                    debugger.deactivate(configuration.hook_registry)
                shutdown(configuration)

        def _reap(rid: str) -> None:
            """终态 TTL 后回收注册表条目与事件缓冲（S-6）。"""
            with reg_lock:
                e = registry.get(rid)
                if e is not None and e["status"] != "running":
                    del registry[rid]
                    logger.info("[Server] run 注册表回收: {}", rid)

        def _watch():
            try:
                _execute()
            except Exception as exc:  # noqa: BLE001
                logger.exception("[Server] run 执行异常")
                entry["error"] = str(exc)
            finally:
                entry["status"] = "finished"
                timer = threading.Timer(_REAP_TTL_SEC, _reap, args=(run_id,))
                timer.daemon = True
                timer.start()

        threading.Thread(target=_watch, daemon=True,
                         name=f"gimbal-run-{run_id[:8]}").start()
        return RunsCreated(runId=run_id, debugEnabled=req.debug is not None)

    @app.get("/runs/{run_id}")
    async def run_status(run_id: str) -> dict:
        entry = registry.get(run_id)
        if entry is None:
            raise HTTPException(status_code=404, detail="unknown run")
        result = entry.get("result")
        return {
            "runId": run_id,
            "status": entry["status"],
            "error": entry.get("error"),
            "summary": None if result is None else {
                "exitCode": result.exit_code, "total": result.total,
                "passed": result.passed, "failed": result.failed,
                "blocked": result.blocked, "repaired": result.repaired,
            },
        }

    @app.post("/runs/{run_id}/debug", response_model=DebugCommandResponse)
    async def debug_command(
        run_id: str,
        req: DebugCommandRequest,
        authorization: str | None = Header(default=None),
        x_gimbal_token: str | None = Header(default=None, alias="X-Gimbal-Token"),
    ) -> Any:
        _require_token(authorization, x_gimbal_token)   # 改值是特权面
        entry = registry.get(run_id)
        if entry is None:
            raise HTTPException(status_code=404, detail="unknown run")
        session = entry.get("session")
        if session is None:
            raise HTTPException(status_code=409, detail="run not started with debug")
        if entry["status"] != "running":
            return DebugCommandResponse(accepted=False, output=session.drain_output())
        session.submit(req.command)
        import asyncio
        await asyncio.sleep(0.05)   # 给执行线程一点时间产出输出(S-6:不阻塞事件循环)
        return DebugCommandResponse(accepted=True, output=session.drain_output())

    @app.get("/runs/{run_id}/events")
    async def run_events(
        run_id: str,
        last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
        authorization: str | None = Header(default=None),
        x_gimbal_token: str | None = Header(default=None, alias="X-Gimbal-Token"),
    ):
        """SSE 事件流：id = 事件 seq（S-5）；Last-Event-ID 续传从 seq+1 起。"""
        _require_token(authorization, x_gimbal_token)
        entry = registry.get(run_id)
        if entry is None:
            raise HTTPException(status_code=404, detail="unknown run")

        resume_seq = 0
        if last_event_id:
            try:
                resume_seq = int(last_event_id)
            except ValueError:
                resume_seq = 0

        async def stream():
            nonlocal resume_seq
            import asyncio
            import json
            while True:
                events = [e for e in entry["events"]
                          if int(e.get("seq") or 0) > resume_seq]
                for ev in events:
                    payload = json.dumps(ev, ensure_ascii=False, default=str)
                    yield ("id: " + str(ev.get("seq", 0)) + NL
                           + "data: " + payload + NL + NL)
                    resume_seq = max(resume_seq, int(ev.get("seq") or 0))
                if entry["status"] != "running" and not [
                        e for e in entry["events"]
                        if int(e.get("seq") or 0) > resume_seq]:
                    yield ("event: done" + NL + "data: {}" + NL + NL)
                    return
                await asyncio.sleep(0.2)

        return StreamingResponse(stream(), media_type="text/event-stream")

    return registry


def _event_dict(event: Any) -> dict:
    """事件 → 可 JSON 化 dict（取 event_type 与顶层标量字段）。"""
    try:
        if hasattr(event, "model_dump"):
            return event.model_dump(mode="json")
    except Exception:  # noqa: BLE001
        pass
    return {"event_type": getattr(event, "event_type", type(event).__name__)}
