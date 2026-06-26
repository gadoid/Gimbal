"""Plate 服务端(Phase 2 / PR-2.3)。

设计原则:
  - 严格按 PR-2.1 §2 协议响应(URL / schema / 错误码)
  - 数据源 = 本地 Plate registry(就地取材)
  - 零第三方依赖(stdlib http.server + json + urllib)
  - 服务端是"只读视图"——不修改 registry 状态

业务流:
  1. HTTP 请求进来 → 路由匹配
  2. 提取 version query param → PlateVersion.parse()
  3. 调对应 handler 拿数据 → json_response()
  4. 异常 → error_response() 返回错误码

对应设计:PR-2.1 协议草案 + PR-2.3 §2.4 + A5 协议先于实现。
"""
from __future__ import annotations

import importlib
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from Plate import registry
from Plate.manifest import PlateManifest
from Plate.version import PlateVersion
from Plate.server.response import json_response, error_response

# ── 服务端支持的版本(本 PR: 单一固定版本) ──
DEFAULT_VERSION: PlateVersion = PlateVersion(1, 0, 0)
SUPPORTED_VERSIONS: tuple[PlateVersion, ...] = (DEFAULT_VERSION,)
SUPPORTED_SERVICES: tuple[str, ...] = ("fin",)


def _collect_specs_for_service(service: str) -> list[Any]:
    """直接拉取某 service 的全部 EndpointSpec 实例 — 不依赖 registry._index。

    设计动机(对应 PR-2.3 §1.2 "数据源 = 本地 registry"):
      server 是只读视图,需要"某 service 的全部 spec"。
      直接走 ``importlib.import_module + vars(module).values()`` 而非
      ``registry.collect + _index`` 可避开:
        - registry._index 与 sys.modules 状态不一致(测试间 reset 导致)
        - collect 内部锁与 HTTPServer 多线程交互的边角案例

    返回 EndpointSpec 实例列表(供 handler 直接 ``s.to_dict()``)。
    不存在的 service → ImportError(由 caller 处理)。
    """
    # ensure service 目录存在 & 能 import
    module = importlib.import_module(f"Plate.{service}")
    return [
        attr for attr in vars(module).values()
        if type(attr).__name__ == "EndpointSpec"
    ]


def _ensure_service_loaded(service: str) -> None:
    """确保 service 子包已 import(server 进程期内只 import 一次)。"""
    importlib.import_module(f"Plate.{service}")


def _parse_version(s: str | None) -> PlateVersion | None:
    """从 query 解析 version。

    None = 缺参数(让 caller 报 400);
    ValueError → None(让 caller 报 400 INVALID_VERSION_FORMAT)。
    """
    if s is None:
        return None
    try:
        return PlateVersion.parse(s)
    except ValueError:
        return None


# ── Handlers ──


def handle_healthz(handler: Any, **kwargs: Any) -> tuple[bytes, int, dict[str, str]]:
    return json_response({"status": "ok", "version": str(DEFAULT_VERSION)})


def handle_version_list(handler: Any, **kwargs: Any) -> tuple[bytes, int, dict[str, str]]:
    return json_response({
        "supported_versions": [v.to_dict() for v in SUPPORTED_VERSIONS],
        "default": DEFAULT_VERSION.to_dict(),
    })


def handle_manifest(handler: Any, version: PlateVersion | None = None, **kwargs: Any) -> tuple[bytes, int, dict[str, str]]:
    """GET /v1/manifest — 返回默认版本 manifest(对应 PR-2.1 §2.1)。"""
    return handle_manifest_pinned(handler, DEFAULT_VERSION)


def handle_manifest_pinned(
    handler: Any,
    version: PlateVersion,
    **kwargs: Any,
) -> tuple[bytes, int, dict[str, str]]:
    """GET /v1/manifest/{version} — 返回指定版本 manifest。

    本 PR:固定单一版本,不存在的版本 → 404 + VERSION_NOT_FOUND。
    """
    if version not in SUPPORTED_VERSIONS:
        return error_response(
            "VERSION_NOT_FOUND",
            f"version {version} not on server",
            404,
            extra={"available_versions": [v.to_dict() for v in SUPPORTED_VERSIONS]},
        )
    # Eagerly collect 每个 supported service(按需加载 — server 是只读视图)。
    import sys
    from Plate.spec import EndpointSpec as _ES
    from Plate.core import EndpointSpec as _ES_CORE
    print(
        f"[DEBUG-CORE] _ES id={id(_ES)} _ES_CORE id={id(_ES_CORE)} "
        f"same={_ES is _ES_CORE}",
        file=sys.stderr,
    )
    services: dict[str, list[dict]] = {}
    for svc in SUPPORTED_SERVICES:
        # DEBUG: 直接调用 _collect_locked 的内循环逻辑(无锁)
        if "Plate.fin" in sys.modules:
            fin_mod = sys.modules["Plate.fin"]
            spec_attrs = [
                (n, a) for n, a in vars(fin_mod).items()
                if type(a).__name__ == "EndpointSpec"
            ]
            print(
                f"[DEBUG-LOOP] svc={svc} "
                f"spec_attrs_n={len(spec_attrs)}",
                file=sys.stderr,
            )
            added_my = 0
            added_core = 0
            for name, attr in spec_attrs:
                if type(attr) is _ES:
                    added_my += 1
                if type(attr) is _ES_CORE:
                    added_core += 1
            print(
                f"[DEBUG-LOOP-DONE] my={added_my} core={added_core}",
                file=sys.stderr,
            )
        registry.collect(svc)
        svc_specs = [
            s.to_dict() for k, s in registry._index.items() if k.service == svc
        ]
        services[svc] = svc_specs
        print(
            f"[DEBUG-AFTER] svc={svc} "
            f"total index={len(registry._index)} "
            f"svc_specs={len(svc_specs)} "
            f"loaded={sorted(registry._loaded)}",
            file=sys.stderr,
        )
    manifest = PlateManifest.from_services(version, services)
    return json_response(
        manifest.to_dict(),
        headers={"X-Plate-Version": str(version)},
    )


def handle_spec_service(
    handler: Any,
    service: str,
    version: PlateVersion,
    **kwargs: Any,
) -> tuple[bytes, int, dict[str, str]]:
    """GET /v1/spec/{service}?version=X — 单 service 全部 spec。"""
    if service not in SUPPORTED_SERVICES:
        return error_response(
            "SERVICE_NOT_FOUND",
            f"service {service!r} not on server",
            404,
            extra={"available_services": list(SUPPORTED_SERVICES)},
        )
    registry.collect(service)
    specs = [
        s.to_dict() for k, s in registry._index.items() if k.service == service
    ]
    payload = {
        "service": service,
        "version": version.to_dict(),
        "checksum": PlateManifest.compute_checksum(version, {service: specs}),
        "specs": sorted(specs, key=lambda s: (s["method"], s["path"])),
    }
    return json_response(payload, headers={"X-Plate-Version": str(version)})


def handle_spec_endpoint(
    handler: Any,
    service: str,
    method: str,
    path: str,
    version: PlateVersion,
    **kwargs: Any,
) -> tuple[bytes, int, dict[str, str]]:
    """GET /v1/spec/{service}/{method}/{path:path}?version=X — 单端点 spec。"""
    if service not in SUPPORTED_SERVICES:
        return error_response(
            "SERVICE_NOT_FOUND",
            f"service {service!r} not on server",
            404,
            extra={"available_services": list(SUPPORTED_SERVICES)},
        )
    full_path = "/" + path
    try:
        spec = registry.resolve(service, method, full_path)
    except LookupError as e:
        return error_response("ENDPOINT_NOT_FOUND", str(e), 404)
    return json_response(
        {
            "service": service,
            "version": version.to_dict(),
            "spec": spec.to_dict(),
        },
        headers={"X-Plate-Version": str(version)},
    )


def handle_doc_service(
    handler: Any,
    service: str,
    version: PlateVersion,
    **kwargs: Any,
) -> tuple[bytes, int, dict[str, str]]:
    """GET /v1/doc/{service}?version=X — 单 service L2 doc dict。

    L2 是热数据(对应 A3 冷热分层),本 PR 直接 dict 形态返回。
    """
    if service not in SUPPORTED_SERVICES:
        return error_response(
            "SERVICE_NOT_FOUND",
            f"service {service!r} not on server",
            404,
            extra={"available_services": list(SUPPORTED_SERVICES)},
        )
    docs = _get_docs_for_service(service)
    return json_response(
        {
            "service": service,
            "version": version.to_dict(),
            "docs": docs,
        },
        headers={"X-Plate-Version": str(version)},
    )


def handle_doc_endpoint(
    handler: Any,
    service: str,
    method: str,
    path: str,
    version: PlateVersion,
    **kwargs: Any,
) -> tuple[bytes, int, dict[str, str]]:
    """GET /v1/doc/{service}/{method}/{path:path}?version=X — 单端点 doc。"""
    if service not in SUPPORTED_SERVICES:
        return error_response(
            "SERVICE_NOT_FOUND",
            f"service {service!r} not on server",
            404,
            extra={"available_services": list(SUPPORTED_SERVICES)},
        )
    full_path = "/" + path
    docs = _get_docs_for_service(service)
    doc = docs.get(full_path)
    if doc is None:
        return error_response("DOC_NOT_FOUND", f"no doc for {full_path}", 404)
    return json_response(
        {
            "service": service,
            "version": version.to_dict(),
            "path": full_path,
            "doc": doc,
        },
        headers={"X-Plate-Version": str(version)},
    )


def _get_docs_for_service(service: str) -> dict[str, dict]:
    """返回某 service 的 L2 doc dict。

    本 PR:fin 服务有 _DOCS,其他 service → 空 dict。
    """
    if service == "fin":
        from Plate.fin.dannotations import _DOCS
        return {k: dict(v.__dict__) for k, v in _DOCS.items()}
    return {}


# ── HTTP server ──


class PlateRequestHandler(BaseHTTPRequestHandler):
    """HTTP 请求处理器 — 严格路由分派。"""

    def do_GET(self) -> None:  # noqa: N802
        # 1. 解析 path 与 query
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        version_str = query.get("version", [None])[0]
        version = _parse_version(version_str)

        # 2. 路由匹配
        route, params = _match_route(path, self.command)
        if route is None:
            body, status, headers = error_response(
                "NOT_FOUND",
                f"no route for {self.command} {path}",
                404,
            )
            self._write(body, status, headers)
            return

        # 3. version 校验(需要 ?version= 的端点)
        if route.requires_version and version is None and version_str is not None:
            # 给了 version 但格式非法 → 400
            body, status, headers = error_response(
                "INVALID_VERSION_FORMAT",
                f"invalid ?version={version_str!r} (expected major.minor.patch)",
                400,
            )
            self._write(body, status, headers)
            return
        if route.requires_version and version_str is None:
            body, status, headers = error_response(
                "INVALID_VERSION_FORMAT",
                "missing ?version= query parameter",
                400,
            )
            self._write(body, status, headers)
            return
        if version is not None and version not in SUPPORTED_VERSIONS:
            body, status, headers = error_response(
                "VERSION_NOT_FOUND",
                f"version {version} not on server",
                404,
                extra={"available_versions": [v.to_dict() for v in SUPPORTED_VERSIONS]},
            )
            self._write(body, status, headers)
            return

        # 4. 调 handler
        # 注意:如果 path 占位符含 {version},则 URL 段已被 params 注入,
        # 不再重复传 version=version(否则 "got multiple values")。
        # 规则:URL 段 version 优先(query param 仅作补充,本协议路由无此场景)。
        # 此外,URL 段 version 是 str,需解析为 PlateVersion 才能被 handler 用。
        call_kwargs = dict(params)
        if "version" in call_kwargs:
            url_version = call_kwargs["version"]
            try:
                call_kwargs["version"] = PlateVersion.parse(url_version)
            except ValueError:
                body, status, headers = error_response(
                    "INVALID_VERSION_FORMAT",
                    f"invalid /v1/manifest/{url_version} (expected major.minor.patch)",
                    400,
                )
                self._write(body, status, headers)
                return
            # 如果该路径要求 version,但 version 不在 SUPPORTED_VERSIONS → 404
            if call_kwargs["version"] not in SUPPORTED_VERSIONS:
                body, status, headers = error_response(
                    "VERSION_NOT_FOUND",
                    f"version {call_kwargs['version']} not on server",
                    404,
                    extra={
                        "available_versions": [
                            v.to_dict() for v in SUPPORTED_VERSIONS
                        ]
                    },
                )
                self._write(body, status, headers)
                return
        else:
            call_kwargs["version"] = version
        try:
            body, status, headers = route.handler(self, **call_kwargs)
        except Exception as e:  # noqa: BLE001
            body, status, headers = error_response(
                "INTERNAL_ERROR",
                f"{type(e).__name__}: {e}",
                500,
            )
        self._write(body, status, headers)

    def _write(self, body: bytes, status: int, headers: dict[str, str]) -> None:
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        """压制默认 stderr 日志(测试时静默)。"""


class PlateServer:
    """进程级服务实例。

    用法::

        server = PlateServer(port=0)  # 0 = 动态分配
        server.start()
        try:
            url = f"http://127.0.0.1:{server.port}"
            # ... 用 url 做 E2E ...
        finally:
            server.stop()
    """

    def __init__(self, port: int = 0, host: str = "127.0.0.1") -> None:
        self.host = host
        self._port = port
        self._httpd: HTTPServer | None = None
        self._thread = None

    @property
    def port(self) -> int:
        """实际监听端口(port=0 时由 OS 分配,start() 后可读)。"""
        if self._httpd is not None:
            return self._httpd.server_address[1]
        return self._port

    def start(self) -> None:
        import threading
        self._httpd = HTTPServer((self.host, self._port), PlateRequestHandler)
        self._thread = threading.Thread(
            target=self._httpd.serve_forever, daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
        # 等待线程真正退出(daemon 线程不强制 join 会导致 socket TIME_WAIT 残留)
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None


def _register_routes_once() -> None:
    """首次请求前注册 handler 到路由表(避免循环导入)。"""
    from Plate.server.router import register_handlers
    register_handlers({
        "healthz": handle_healthz,
        "version_list": handle_version_list,
        "manifest_default": handle_manifest,
        "manifest_pinned": handle_manifest_pinned,
        "spec_service": handle_spec_service,
        "spec_endpoint": handle_spec_endpoint,
        "doc_service": handle_doc_service,
        "doc_endpoint": handle_doc_endpoint,
    })


_ROUTES_REGISTERED: bool = False


def _match_route(path: str, method: str):  # type: ignore[no-untyped-def]
    """URL 路由匹配。委托给 router 模块以避免循环导入。"""
    global _ROUTES_REGISTERED
    if not _ROUTES_REGISTERED:
        _register_routes_once()
        _ROUTES_REGISTERED = True
    from Plate.server.router import match_route
    return match_route(path, method)


__all__ = [
    "PlateServer",
    "PlateRequestHandler",
    "DEFAULT_VERSION",
    "SUPPORTED_VERSIONS",
    "SUPPORTED_SERVICES",
]
