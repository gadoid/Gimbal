"""FastAPI application factory for the plate HTTP service."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from gimbal_plate.http.envelope import (
    PlateHTTPError,
    err_response,
)
from gimbal_plate.http.grammar import ErrorCode
from gimbal_plate.http.routes_grammar import router as grammar_router
from gimbal_plate.registry import PlateRegistry, registry as default_registry


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Ensure the systems tree + all dims are loaded on startup（A2 统一加载器）.

    When an external registry is injected via ``create_app(registry=...)`` this
    step is skipped so the caller controls its own state.

    启动流程(owned 模式)——全部收敛到 :func:`gimbal_plate.loader.load_registry`:
    1. 按「路径列表」发现系统(缺省 ``systems/``,``PLATE_SYSTEMS_PATH`` 覆盖);
    2. 解析 Markdown 方言,注册新栈 EndpointSpec(F3:重复路由键注册即报错
       —— 取代旧 system 自检);system.md 声明系统/服务并播种默认模板 dim;
    3. 9 个 dim 全局挂载一次(数据 dim + 框架 dim,修订四)。
    """
    if getattr(app.state, "registry_owned", True):
        from gimbal_plate.loader import load_registry

        # 装载进默认 registry(create_app 已把它挂到 app.state.registry);
        # reset 防陈旧单例,加载失败(fenced 块坏了)启动即炸,不静默少半。
        default_registry.reset()
        load_registry(reg=default_registry)
        # 快照标识(G5/7.1):working 阶段无 release,标 @working
        app.state.snapshot_label = "working"
    yield


def create_app(
    *,
    registry: PlateRegistry | None = None,
    mount_prefix: str = "",
) -> FastAPI:
    """Create a FastAPI app exposing the M6 grammar surface (ADR 0002 §D1).

    Parameters
    ----------
    registry:
        Optional registry instance. When provided, it is stored on
        ``app.state.registry`` and the lifespan hook will NOT auto-register
        the bundled fin system into the global default registry. This is the
        expected integration point for embedding plate into another service.
    mount_prefix:
        Reserved for future use; the routers already use absolute paths.
    """
    _ = mount_prefix  # reserved for future use
    app = FastAPI(
        title="Plate Structure Service",
        version="0.1.0",
        lifespan=_lifespan,
    )

    if registry is None:
        app.state.registry = default_registry
        app.state.registry_owned = True
        app.state.snapshot_label = "working"
    else:
        app.state.registry = registry
        app.state.registry_owned = False
        app.state.snapshot_label = "working"

    # G5(7.2,已定):每个响应标明所读快照。统一在响应出口注入,信封构造
    # 点(ok_response)零改动;非信封响应(healthz 等)不受影响。
    @app.middleware("http")
    async def _snapshot_middleware(request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/api/") and response.status_code == 200:
            label = getattr(request.app.state, "snapshot_label", "working")
            # JSON body 重写仅在确为信封时进行(content-type 判定,流式响应跳过)
            ctype = response.headers.get("content-type", "")
            if "application/json" in ctype:
                import json as _json
                body = b"".join([chunk async for chunk in response.body_iterator])
                try:
                    data = _json.loads(body)
                except Exception:  # noqa: BLE001 — 非信封 JSON 原样放行
                    return Response(
                        content=body, status_code=200,
                        media_type="application/json",
                        headers={k: v for k, v in response.headers.items()
                                 if k.lower() != "content-length"})
                if isinstance(data, dict) and "ok" in data and "snapshot" not in data:
                    data["snapshot"] = label
                # 丢弃原 content-length:重序列化后长度必变(补了 snapshot 字段),
                # 沿用旧值会被 uvicorn 以「body 长于声明」拒掉(TestClient 不校验,
                # 真 ASGI 服务器校验——8765 实跑暴露)。Response 自会重算。
                headers = {k: v for k, v in response.headers.items()
                           if k.lower() != "content-length"}
                return Response(content=_json.dumps(data, ensure_ascii=False),
                                status_code=200, media_type="application/json",
                                headers=headers)
        return response

    @app.exception_handler(PlateHTTPError)
    async def _plate_http_error_handler(
        _request: Request, exc: PlateHTTPError
    ) -> JSONResponse:
        body, status = err_response(
            code=exc.code,
            message=exc.message,
            http_status=exc.http_status,
            details=exc.details,
        )
        return JSONResponse(status_code=status, content=body)

    @app.exception_handler(Exception)
    async def _unhandled(_request: Request, exc: Exception) -> JSONResponse:
        body, status = err_response(
            code=ErrorCode.INTERNAL_ERROR,
            message=str(exc) or exc.__class__.__name__,
            http_status=500,
        )
        return JSONResponse(status_code=status, content=body)

    @app.get("/healthz", include_in_schema=False)
    async def _healthz() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(grammar_router)

    return app


__all__ = ["create_app"]