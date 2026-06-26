# PR-2.3: 服务部署形态 + E2E 验证

> **状态**:待执行
>
> **PR 范围**:
> 1. 服务端骨架实现(`src/Plate/server/`)—— 严格按 [PR-2.1 协议](PR-2.1.md)响应
> 2. 部署形态选择(进程模式 + 端口)
> 3. E2E 验证(本地起服务 → SDK 拉 → 字节级 pin 验证)
> 4. 健康检查端点
>
> **前置依赖**:**PR-2.0**(序列化)+ **PR-2.1**(协议)+ **PR-2.2**(SDK 骨架)
>
> **关键设计**:本 PR **不引入第三方 Web 框架**(`http.server` stdlib 已够),
> 服务端是"只读视图"——数据全在本地 registry,server 只负责按 URL 路由
> 返回 JSON。
>
> **对应设计**:[PR-2.1 协议草案](PR-2.1.md)+ A5 协议先于实现 +
> 不变承诺 1-5

---

## 1. 业务动机

### 1.1 业务需求

**核心问题**:Phase 2 设计 §3 任务 1 明确"远端权威服务",但 PR-2.1 只定协议,
**本 PR 必须落地真实可运行的服务端**,否则:
- SDK(PR-2.2)无真实服务端可对接
- E2E 验证只能 mock,无法验证真实 HTTP 流
- PR-2.4(GIMBAL 切换)无下游依赖

**本 PR 服务端必须做到**:
1. **严格按 PR-2.1 协议响应**:URL 路由 / JSON schema / 错误码一致
2. **零依赖**:只用 stdlib(`http.server` + `json` + `urllib`),GIMBAL 主框架不引入新依赖
3. **冷热端点分离**:`/v1/spec/*` 与 `/v1/doc/*` 路由独立
4. **健康检查**:`/healthz` 用于 K8s liveness probe
5. **E2E 测试可启动**:pytest fixture 起进程,SDK 客户端拉数据,字节级 pin 验证

### 1.2 关键决策

- **stdlib `http.server` 而非 Flask/FastAPI**:Phase 2 量小,引入 Web 框架增加依赖;
  Phase 3 MCP 再统一依赖;本 PR 服务端是"演示性"——证明协议可行,非生产级
- **进程模式而非线程池**:`http.server` 单线程足够(QPS < 100);
  Phase 3 再升级到多进程 / 异步
- **数据源 = 本地 `Plate` registry**(就地取材):服务端进程就是 GIMBAL 主进程,
  起子线程监听 HTTP;服务拉数据不绕远路
- **部署方式 = subprocess**:E2E 测试用 `subprocess.Popen` 起服务,fixture scope=session
- **端口 = 动态分配**:E2E 测试用 `socket.bind(('', 0))` 拿空闲端口,避免硬编码冲突

---

## 2. 代码实现要点

### 2.1 改动文件清单

| 文件 | 改动 |
|---|---|
| `src/Plate/server/__init__.py` | 新建:`PlateServer` 类 + `PlateRequestHandler` |
| `src/Plate/server/router.py` | 新建:URL 路由分发表 |
| `src/Plate/server/response.py` | 新建:JSON 响应 + 错误响应工具 |
| `tests/plate/test_server.py` | 新建:服务端单元测试(≥ 10) |
| `tests/plate/test_server_e2e.py` | 新建:E2E 启动服务 + SDK 拉数据(≥ 5) |
| `tests/plate/test_invariants.py` | 加 1 条:服务端协议 byte-equal 不变量 |

### 2.2 路由分发表

```python
# src/Plate/server/router.py
"""URL 路由分发表(严格对应 PR-2.1 §2.1)。

每条路由 = (path_pattern, handler_function)。
handler 签名: ``(handler, version: PlateVersion | None) -> dict``
返回 dict(响应体)+ status(响应码)。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Awaitable

from Plate.version import PlateVersion


@dataclass(frozen=True)
class Route:
    pattern: str          # 路径模式,带 {param} 占位
    method: str           # HTTP 方法
    handler: Callable     # 处理函数
    requires_version: bool  # 是否需要 ?version=


# 路由表(顺序敏感 — 精确匹配优先于泛匹配)
ROUTES: tuple[Route, ...] = (
    Route("/healthz", "GET", handle_healthz, requires_version=False),
    Route("/v1/manifest", "GET", handle_manifest_default, requires_version=True),
    Route("/v1/manifest/{version}", "GET", handle_manifest_pinned, requires_version=False),
    Route("/v1/version", "GET", handle_version_list, requires_version=False),
    Route("/v1/spec/{service}", "GET", handle_spec_service, requires_version=True),
    Route("/v1/spec/{service}/{method}/{path:path}", "GET", handle_spec_endpoint, requires_version=True),
    Route("/v1/doc/{service}", "GET", handle_doc_service, requires_version=True),
    Route("/v1/doc/{service}/{method}/{path:path}", "GET", handle_doc_endpoint, requires_version=True),
)
```

### 2.3 处理函数骨架

```python
# src/Plate/server/response.py
"""JSON 响应 + 错误响应工具。"""
from __future__ import annotations

import json
from typing import Any


def json_response(body: Any, status: int = 200,
                   headers: dict | None = None) -> tuple[bytes, int, dict]:
    """构造 JSON 响应。"""
    payload = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    h = {"Content-Type": "application/json; charset=utf-8",
         "Content-Length": str(len(payload))}
    if headers:
        h.update(headers)
    return payload, status, h


def error_response(code: str, message: str, status: int,
                    extra: dict | None = None) -> tuple[bytes, int, dict]:
    """构造错误响应(对应 PR-2.1 §2.4)。"""
    body = {"error": code, "message": message}
    if extra:
        body.update(extra)
    return json_response(body, status=status)
```

### 2.4 完整 handler 骨架(关键端点)

```python
# src/Plate/server/__init__.py(简化示意)
"""Plate 服务端(Phase 2 / PR-2.3)。

设计原则:
  - 严格按 PR-2.1 §2 协议响应(URL / schema / 错误码)
  - 数据源 = 本地 Plate registry(就地取材)
  - 零第三方依赖(stdlib http.server + json + urllib)
  - 服务端是"只读视图"——不修改 registry 状态

业务流:
  1. HTTP 请求进来 → 路由匹配
  2. 提取 version query param → PlateVersion.from_query()
  3. 调对应 handler 拿数据 → json_response()
  4. 异常 → error_response() 返回错误码
"""
from __future__ import annotations

import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from Plate import registry
from Plate.doc import EndpointDoc  # noqa: F401
from Plate.fin.dannotations import _DOCS
from Plate.manifest import PlateManifest
from Plate.version import PlateVersion
from Plate.server.response import json_response, error_response


# ── 服务端支持的版本(本 PR: 单一固定版本) ──
DEFAULT_VERSION: PlateVersion = PlateVersion(1, 0, 0)
SUPPORTED_VERSIONS: tuple[PlateVersion, ...] = (DEFAULT_VERSION,)


def _parse_version(s: str | None) -> PlateVersion | None:
    """从 query 解析 version。None = 缺参数(返回 None 让 caller 报 400)。"""
    if s is None:
        return None
    try:
        return PlateVersion.parse(s)
    except ValueError:
        return None


# ── Handlers ──

def handle_healthz(handler, version) -> tuple[bytes, int, dict]:
    return json_response({"status": "ok", "version": str(DEFAULT_VERSION)})


def handle_version_list(handler, version) -> tuple[bytes, int, dict]:
    return json_response({
        "supported_versions": [v.to_dict() for v in SUPPORTED_VERSIONS],
        "default": DEFAULT_VERSION.to_dict(),
    })


def handle_manifest_default(handler, version) -> tuple[bytes, int, dict]:
    """无 version 参数 → 返回默认版本 manifest(对应 PR-2.1 §2.1)。"""
    return handle_manifest_pinned(handler, DEFAULT_VERSION)


def handle_manifest_pinned(handler, version: PlateVersion) -> tuple[bytes, int, dict]:
    """返回指定版本的 manifest。本 PR:固定单一版本,不存在的版本 → 404。"""
    if version not in SUPPORTED_VERSIONS:
        return error_response(
            "VERSION_NOT_FOUND", f"version {version} not on server", 404,
            extra={"available_versions": [v.to_dict() for v in SUPPORTED_VERSIONS]},
        )
    services = {}
    for svc in SUPPORTED_SERVICES:  # ["fin", "auth", ...]
        services[svc] = [s.to_dict() for k, s in registry._index.items()
                          if k.service == svc]
    manifest = PlateManifest.from_services(version, services)
    return json_response(manifest.to_dict(),
                          headers={"X-Plate-Version": str(version)})


def handle_spec_service(handler, service: str, version: PlateVersion) -> tuple[bytes, int, dict]:
    if service not in SUPPORTED_SERVICES:
        return error_response("SERVICE_NOT_FOUND",
                                f"service {service!r} not on server", 404)
    specs = [s.to_dict() for k, s in registry._index.items() if k.service == service]
    # 排序无关字段先排序(对应 PR-2.0 byte-equal)
    from Plate.manifest import PlateManifest
    payload = {
        "service": service,
        "version": version.to_dict(),
        "checksum": PlateManifest.compute_checksum(version, {service: specs}),
        "specs": sorted(specs, key=lambda s: (s["method"], s["path"])),
    }
    return json_response(payload)


def handle_spec_endpoint(handler, service: str, method: str,
                          path: str, version: PlateVersion) -> tuple[bytes, int, dict]:
    """单端点 spec。"""
    try:
        spec = registry.resolve(service, method, "/" + path)
    except LookupError as e:
        return error_response("ENDPOINT_NOT_FOUND", str(e), 404)
    return json_response({
        "service": service,
        "version": version.to_dict(),
        "spec": spec.to_dict(),
    })


def handle_doc_service(handler, service: str, version: PlateVersion) -> tuple[bytes, int, dict]:
    """返回某 service 的 L2 doc dict。"""
    if service not in SUPPORTED_SERVICES:
        return error_response("SERVICE_NOT_FOUND", f"service {service!r}", 404)
    # L2 是热数据(PR-D3 空壳,本 PR 直接空 dict 返回)
    docs = _DOCS if service == "fin" else {}
    return json_response({
        "service": service,
        "version": version.to_dict(),
        "docs": {k: v.__dict__ for k, v in docs.items()},
    })


def handle_doc_endpoint(handler, service: str, method: str,
                         path: str, version: PlateVersion) -> tuple[bytes, int, dict]:
    """单端点 doc。"""
    full_path = "/" + path
    doc = _DOCS.get(full_path) if service == "fin" else None
    if doc is None:
        return error_response("DOC_NOT_FOUND", f"no doc for {full_path}", 404)
    return json_response({
        "service": service,
        "version": version.to_dict(),
        "path": full_path,
        "doc": doc.__dict__,
    })


SUPPORTED_SERVICES: tuple[str, ...] = ("fin",)


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
                "NOT_FOUND", f"no route for {self.command} {path}", 404,
            )
            self._write(body, status, headers)
            return

        # 3. version 校验(需要 ?version= 的端点)
        if route.requires_version and version is None:
            body, status, headers = error_response(
                "INVALID_VERSION_FORMAT",
                "missing ?version= query parameter", 400,
            )
            self._write(body, status, headers)
            return
        if version is not None and version not in SUPPORTED_VERSIONS:
            body, status, headers = error_response(
                "VERSION_NOT_FOUND", f"version {version} not on server", 404,
                extra={"available_versions": [v.to_dict() for v in SUPPORTED_VERSIONS]},
            )
            self._write(body, status, headers)
            return

        # 4. 调 handler
        try:
            body, status, headers = route.handler(self, *params, version=version)
        except Exception as e:
            body, status, headers = error_response(
                "INTERNAL_ERROR", f"{type(e).__name__}: {e}", 500,
            )
        self._write(body, status, headers)

    def _write(self, body: bytes, status: int, headers: dict) -> None:
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):  # noqa: A002
        """压制默认 stderr 日志(测试时静默)。"""
        pass


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
        return self._httpd.server_address[1] if self._httpd else self._port

    def start(self) -> None:
        import threading
        self._httpd = HTTPServer((self.host, self._port), PlateRequestHandler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None


__all__ = ["PlateServer", "PlateRequestHandler", "DEFAULT_VERSION", "SUPPORTED_VERSIONS"]
```

### 2.5 E2E fixture

```python
# tests/plate/conftest.py(追加)
"""E2E 共享 fixture:起一个临时 PlateServer,所有 E2E 测试共享。"""
import pytest

from Plate.server import PlateServer


@pytest.fixture(scope="session")
def plate_server():
    """Session 级:起一次服务,所有 E2E 测试用。"""
    server = PlateServer(port=0)
    server.start()
    yield server
    server.stop()


@pytest.fixture(scope="session")
def plate_server_url(plate_server) -> str:
    return f"http://127.0.0.1:{plate_server.port}"
```

---

## 3. 测试用例设计

### 3.1 必测业务场景

| 测试 | 业务承诺 |
|---|---|
| `test_server_healthz` | GET /healthz → 200 + status:ok |
| `test_server_version_list` | GET /v1/version → supported_versions + default |
| `test_server_manifest_default` | GET /v1/manifest → 默认版本 manifest |
| `test_server_manifest_pinned` | GET /v1/manifest/1.0.0 → 该版本 manifest |
| `test_server_manifest_version_not_found` | GET /v1/manifest/99.0.0 → 404 + VERSION_NOT_FOUND |
| `test_server_spec_service` | GET /v1/spec/fin?version=1.0.0 → 31 specs |
| `test_server_spec_service_not_found` | GET /v1/spec/auth?version=1.0.0 → 404 (auth 不在 SUPPORTED) |
| `test_server_spec_endpoint` | GET /v1/spec/fin/POST/api/order/order/orderDetail → 单 spec |
| `test_server_spec_endpoint_not_found` | 404 + ENDPOINT_NOT_FOUND |
| `test_server_invalid_version_format` | ?version=1.x → 400 + INVALID_VERSION_FORMAT |
| `test_server_missing_version_param` | /v1/spec/fin 无 version → 400 |
| `test_server_doc_service_fin` | GET /v1/doc/fin → 空 docs dict(PR-D3 空壳) |
| `test_server_doc_endpoint_not_found` | GET /v1/doc/fin/POST/api/... → 404 + DOC_NOT_FOUND |
| `test_server_response_content_type_json` | Content-Type: application/json; charset=utf-8 |
| `test_server_response_x_plate_version` | 响应带 X-Plate-Version 头 |
| `test_server_response_byte_equal` | 同 URL 两次响应 byte-equal(checksum 稳定) |

### 3.2 E2E 必测

| 测试 | 业务承诺 |
|---|---|
| `test_e2e_sdk_resolve_endpoint` | SDK resolve 真实端点 → 字节级 pin |
| `test_e2e_sdk_resolve_offline_fallback` | SDK 离线 fallback(停服务后)仍可用 |
| `test_e2e_manifest_checksum_matches_local` | 服务端 manifest checksum == 本地构建 |
| `test_e2e_spec_round_trip_through_http` | spec → to_dict → HTTP → from_dict 字段相等 |
| `test_e2e_error_response_shape` | 错误响应 JSON 形态符合 PR-2.1 §2.4 |

### 3.3 业务核心测试矩阵

| 业务承诺 | 测试函数 | 业务影响 |
|---|---|---|
| 协议严格落地 | `test_server_*`(≥ 16) | 协议可执行 |
| E2E 端到端可用 | `test_e2e_*`(≥ 5) | SDK + 服务端集成 |
| 不变量扩展 | 新增 1 条 invariant | 协议 byte-equal 锁定 |

---

## 4. 收口验证

### 4.1 执行命令

```bash
# 1. 跑服务端单元测试
pytest tests/plate/test_server.py -v

# 2. 跑 E2E(起服务 + SDK 拉)
pytest tests/plate/test_server_e2e.py -v

# 3. 跑全量 Phase 1+2 不变量
pytest tests/plate/test_invariants.py tests/plate/test_zero_invasion.py -v

# 4. 跑全量基线(≥ 386 + 21 = ≥ 407)
pytest tests/ -v

# 5. 手工冒烟:起服务 + curl
python -c "
from Plate.server import PlateServer
server = PlateServer(port=18080)
server.start()
print(f'服务已起: http://127.0.0.1:{server.port}')
print(f'  GET /healthz')
print(f'  GET /v1/version')
print(f'  GET /v1/spec/fin?version=1.0.0')
print(f'  GET /v1/manifest')
server.stop()
"
```

### 4.2 验收

| 项 | 值 |
|---|---|
| `test_server.py` 测试数 | ≥ 16 |
| `test_server_e2e.py` 测试数 | ≥ 5 |
| `PlateServer` 可独立启动 | 是 |
| 不引入第三方依赖 | `grep -r 'import flask\|import fastapi\|import starlette' src/Plate/server/` 0 命中 |
| 全量测试 | ≥ 386 + 21 = ≥ 407 |

### 4.3 风险

| 风险 | 缓解 |
|---|---|
| 服务端单线程阻塞 | Phase 2 量小可接受,Phase 3 升级 |
| 端口冲突 | E2E 用 `port=0` 动态分配 |
| 协议漂移 | 测试断言按 PR-2.1 §2.4 schema 严格 match |
| 测试慢(session fixture 起服务) | 单次启动 < 1s,可接受 |

---

## 5. 与后续 Phase 的衔接

- **PR-2.4(GIMBAL 切换)**:真实服务端已就绪,GIMBAL 切 SDK 时已有目标
- **Phase 3(MCP)**:协议可直接包装成 MCP tool,服务端代码复用
- **Phase 4(CT 探测)**:服务端加 `/v1/probe/{service}/{method}/{path}` 探测端点

**Phase 2.4 启动条件**:
- [ ] 服务端 + E2E 测试全过(≥ 21)
- [ ] 协议 byte-equal 不变量成立
- [ ] 服务端可独立 `python -m Plate.server` 启动