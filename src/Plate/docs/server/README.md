# server 模块(Plate HTTP 服务端)

> 路径:`src/Plate/server/`
> 文档版本:对应源码 commit `e0be7bf` 之后
> 文档目标读者:第一次接触 Plate HTTP 端的工程师 / E2E 测试作者 / 远程消费方开发者

## 0. 写在最前面(给"完全不了解的人"的话)

如果你从没听过 `Gimbal` / `Plate` / `Plate server`,先读 [../overview.md](../overview.md)。读完你应该能理解:

> **"server 模块是 Plate 子系统的只读 HTTP 视图(Phase 2 落地)。它把本地 Python 进程内的 registry 暴露成 7 个 RESTful 端点,供远程消费方查询 manifest / spec / doc,且全程零第三方依赖(只用 stdlib 的 `http.server`)。"**

简单讲,server 的全部职责可以浓缩为一句话:

> **"我有一个 Python 进程内有 31 个 EndpointSpec,我想让别的进程能 HTTP 查它们。"**

下面是这份文档的目录。

```
1. 模块定位与目录结构
2. response.py   ─ JSON 响应 / 错误响应工具
3. router.py     ─ URL 路由分发表
4. __init__.py   ─ handlers + PlateRequestHandler + PlateServer
5. 7 个 URL 端点全清单
6. 请求/响应/错误码全谱
7. 设计哲学与决策记录
8. 典型使用示例(启动 server、curl、Python 客户端)
9. 不变量总结
10. 设计权衡与未来工作
```

---

## 1. 模块定位与目录结构

`Plate/server/` 把"本地 registry 的 31 个 spec"包装成 HTTP 服务端,这是 Plate **PHASE 架构** 中的 Phase 2(参见 [../overview.md](../overview.md)):

| Phase  | 形态        | 谁消费                            |
| ------ | ----------- | --------------------------------- |
| Phase 1| 本地 Python | mock 脚本、单元测试                |
| Phase 2| HTTP 服务端 | **本模块** — 跨进程、跨语言、跨主机 |
| Phase 3| MCP 网关    | AI agent(尚未落地)               |

server 模块有三个物理文件:

```
Plate/server/
├── __init__.py   ← handlers + PlateRequestHandler + PlateServer(进程入口)
├── router.py     ← URL 路由分发表(占位符 → 正则 → handler)
└── response.py   ← JSON / 错误响应构造工具
```

> **为什么不拆 handler 到独立文件?**
> Handler 数量只有 7 个,且每个 handler 只有 10–30 行,拆成独立模块反而增加 import 成本。**handler 留在 `__init__.py` 里,路由分发表在 `router.py`,响应工具在 `response.py`** — 这种"按职责切分,而不是按 handler 数量切分"是 python 社区的主流做法。

---

## 2. `response.py` ── JSON 响应 / 错误响应工具

**职责**:统一 HTTP 响应的"二进制打包"(把 dict 序列化成 bytes + 设置 Content-Type / Content-Length)。这个文件是 server 唯一和"字节/编码"打交道的模块。

### 2.1 物理结构(60 行,2 个函数)

| 行号 | 函数            | 作用                                |
| ---- | --------------- | ----------------------------------- |
| L13  | `json_response` | 把任意 JSON 对象打包成 (body, status, headers) |
| L43  | `error_response`| 把错误码 + 消息 + 额外字段打包成错误响应 |

### 2.2 `json_response(body, status=200, headers=None)` 详解

```python
def json_response(
    body: Any,
    status: int = 200,
    headers: dict[str, str] | None = None,
) -> tuple[bytes, int, dict[str, str]]:
    payload = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    h: dict[str, str] = {
        "Content-Type": "application/json; charset=utf-8",
        "Content-Length": str(len(payload)),
    }
    if headers:
        h.update(headers)
    return payload, status, h
```

**返回值结构**:`(payload_bytes, http_status, headers_dict)` — 三元组是 **handler 的统一签名**,每个 handler 都返回这种三元组。这样 `PlateRequestHandler._write(body, status, headers)` 就可以无差别地处理所有响应(成功、错误都走同一路径)。

**3 个关键约定**:

| 约定                              | 为什么这样                                                     |
| --------------------------------- | -------------------------------------------------------------- |
| `sort_keys=True`                  | 同一个 dict 多次序列化得到**字节完全相同**的字符串             |
| `separators=(",", ":")`           | 不用 `, ` 和 `: ` 的人类可读分隔符,省字节 + 字节级稳定         |
| `Content-Length` 必带             | `BaseHTTPRequestHandler` 不自动算长度,必须手写,否则 client 端可能 hang |
| `Content-Type: application/json; charset=utf-8` | RFC 7159 标准,声明字符集是 UTF-8                  |

> **"byte-equal" 的意义**: 多个 Plate server 实例(比如 CI 多副本)对同一份 registry 序列化得到的 HTTP 响应**字节级相同** → 便于 `diff` / 缓存 / 镜像对比 / 跨进程测试断言。这是 server 端"零状态、纯函数"哲学的体现。

### 2.3 `error_response(code, message, status, extra=None)` 详解

```python
def error_response(
    code: str,
    message: str,
    status: int,
    extra: dict | None = None,
) -> tuple[bytes, int, dict[str, str]]:
    body: dict = {"error": code, "message": message}
    if extra:
        body.update(extra)
    return json_response(body, status=status)
```

**错误响应体形态**:

```json
{
  "error": "ENDPOINT_NOT_FOUND",
  "message": "no spec for fin POST /api/order/order/orderDetailXXX",
  "available_services": ["fin"]      // ← 可选 extra 字段
}
```

**为什么 error 体只有 `error` + `message` + `extra`?**

- `error`:机器读,稳定的字符串码(`ENDPOINT_NOT_FOUND` / `SERVICE_NOT_FOUND` / `VERSION_NOT_FOUND` / `INVALID_VERSION_FORMAT` / `NOT_FOUND` / `INTERNAL_ERROR`)
- `message`:人读,可变的人类可读字符串(可能含 path / service / version 等具体值)
- `extra`:可选字典,放"该错误能给出的额外信息"(比如 `available_services` / `available_versions`)

**为什么不把 status 编码进 body?** HTTP status 本身就在 wire 上,重复编码是冗余。

### 2.4 7 个错误码(全谱)

server 模块错误码稳定集合(从代码 grep):

| 错误码                     | HTTP status | 触发条件                                                |
| -------------------------- | ----------- | ------------------------------------------------------- |
| `NOT_FOUND`                | 404         | URL path 不匹配任何路由                                |
| `ENDPOINT_NOT_FOUND`       | 404         | service + method + path 在 registry 里查不到          |
| `DOC_NOT_FOUND`            | 404         | path 在 `_DOCS` 里查不到(只发生在 `handle_doc_endpoint`) |
| `SERVICE_NOT_FOUND`        | 404         | service 不在 `SUPPORTED_SERVICES`                       |
| `VERSION_NOT_FOUND`        | 404         | version 不在 `SUPPORTED_VERSIONS`                      |
| `INVALID_VERSION_FORMAT`   | 400         | version 字符串无法 `PlateVersion.parse`(2 个分支:缺参、格式错) |
| `INTERNAL_ERROR`           | 500         | handler 抛任何 `Exception`(兜底)                      |

### 2.5 字节级可重现的代价

`sort_keys=True` 让所有 dict 字段在 JSON 输出时按字典序排,代价是:

- **写时无序、读时有序**:`{c: 1, a: 2}` 序列化成 `{"a":2,"c":1}`,Python 3.7+ 字典本身有序,但这里强制再排一次。
- **可哈希等价物**:`json.dumps(d, sort_keys=True)` 的输出可以用 SHA256 校验,等价于"`d` 的规范化签名"。

这与 [../manifest/README.md](../manifest/README.md) 里的 SHA256 校验一致 — server 的 HTTP 响应也走同一字节级可重现规则。

---

## 3. `router.py` ── URL 路由分发表

**职责**:把 URL path 的占位符语法(`{name}` / `{name:path}`)编译成正则,提供 `match_route(path, method) → (Route | None, params)`。

### 3.1 物理结构(125 行,3 个公开符号 + 2 个内部符号)

| 符号                | 类型     | 作用                                |
| ------------------- | -------- | ----------------------------------- |
| `Route`             | dataclass| 单条路由声明(4 个字段)              |
| `HandlerType`       | type alias | handler 函数签名                  |
| `register_handlers` | 函数     | 注入 handler 字典,构建路由表        |
| `match_route`       | 函数     | 匹配 URL path + method              |
| `_placeholder_to_regex` | 内部  | 占位符 → 正则编译                    |
| `_make_routes`      | 内部     | handler 字典 → 路由表元组            |

### 3.2 `Route` dataclass 详解

```python
@dataclass(frozen=True)
class Route:
    pattern: str
    method: str
    handler: Callable[..., tuple[bytes, int, dict[str, str]]]
    requires_version: bool
```

| 字段               | 含义                                                              |
| ------------------ | ----------------------------------------------------------------- |
| `pattern`          | URL 路径模式,带 `{param}` 占位符                                |
| `method`           | HTTP 方法(本 PR 仅 `GET`,未来可能扩 POST)                       |
| `handler`          | 函数引用,签名为 `(handler, **kwargs) -> (body, status, headers)` |
| `requires_version` | 路由是否要求 `?version=` query 参数                              |

`@dataclass(frozen=True)` 让 `Route` 实例 **不可变** — 注册后路由表永远不会被修改,所有线程读到的都是同一份。这与 server 的"只读视图"哲学一致。

### 3.3 `_placeholder_to_regex(pattern)` 占位符规则

```python
def _placeholder_to_regex(pattern: str) -> re.Pattern[str]:
    """占位符规则:
      - ``{name}`` → 匹配非 '/' 字符: ``(?P<name>[^/]+)``
      - ``{name:path}`` → 匹配任意字符(含 '/'): ``(?P<name>.+)``
      - 字面字符需 regex-escape
    """
```

**为什么有两种占位符?**

- `{name}`(默认):用于"路径段"语义,例如 `{service}` `{method}`,匹配到第一个 `/` 就停
- `{name:path}`(通配):用于"路径里可能有 `/`"的语义,例如 `{path:path}` 透传 `api/order/order/orderDetail` 这种 wire path

**为什么不直接全用 `{name:path}`?** 那样会过度宽松 — `/v1/spec/fin/POST/foo/bar` 会被错误解析成 `service=fin, method=POST, path=foo/bar`,但合法语义应该是 `service=fin, method=POST, path=foo/bar`(无 service 段第二段) — 用 `{name}` + `{name:path}` 组合能强制"service + method 必须是单段,path 才是剩余全部"。

**字面字符用 `re.escape` 的意义**: 路由表里可能出现 `:` `.` 等 regex 元字符(虽然本 server 没用到),用 `re.escape` 保险,不会因为未来加新路由就 regex 注入。

### 3.4 路由表(7 条,顺序敏感)

```python
return (
    Route("/healthz", "GET", handlers["healthz"], requires_version=False),
    Route("/v1/version", "GET", handlers["version_list"], requires_version=False),
    Route("/v1/manifest", "GET", handlers["manifest_default"], requires_version=False),
    Route("/v1/manifest/{version}", "GET", handlers["manifest_pinned"], requires_version=False),
    Route("/v1/spec/{service}", "GET", handlers["spec_service"], requires_version=True),
    Route("/v1/spec/{service}/{method}/{path:path}", "GET", handlers["spec_endpoint"], requires_version=True),
    Route("/v1/doc/{service}", "GET", handlers["doc_service"], requires_version=True),
    Route("/v1/doc/{service}/{method}/{path:path}", "GET", handlers["doc_endpoint"], requires_version=True),
)
```

**顺序为什么敏感?** 假设两条路由:
- `A: /v1/manifest/{version}`(精确度:中)
- `B: /v1/manifest`(精确度:高)

按 Python `tuple` 顺序遍历,如果 B 在 A 后,访问 `/v1/manifest` 会被 A 错误匹配(把 `manifest` 当成 version 段,后续 `PlateVersion.parse("manifest")` 抛错 → 400)。

实际路由表里没有这种冲突,但 **顺序敏感** 是路由表设计的硬性约束,见 [§7 决策记录](#7-设计哲学与决策记录) 的"为什么路由表用 tuple 而非 dict"。

### 3.5 `register_handlers(handlers)` 与循环导入的处理

```python
def register_handlers(handlers: dict[str, HandlerType]) -> None:
    global _ROUTES, _ROUTES_BY_HANDLER
    _ROUTES_BY_HANDLER = handlers
    _ROUTES = _make_routes(handlers)
```

**为什么需要这个函数?** 因为 `router.py` 想 import `HandlerType` 来给 handler 做类型注解,但 handler 实际定义在 `server/__init__.py` 里。如果 `router.py` 直接 import `from Plate.server import handle_healthz`,会形成 **循环导入**(server init 加载 router,router 加载 server)。

**解决路径**: handler 不在 import 期绑定,而是在 **首次请求前** 通过 `register_handlers` 注入。`server/__init__.py` 里的 `_register_routes_once` 完成这个注入。

```python
def _register_routes_once() -> None:
    from Plate.server.router import register_handlers
    register_handlers({
        "healthz": handle_healthz,
        "version_list": handle_version_list,
        ...
    })
```

这是 **延迟绑定** 的典型 Python 写法 — 把"import 期耦合"转化为"运行期注入"。

### 3.6 `match_route(path, method)` 详解

```python
def match_route(path: str, method: str) -> tuple[Route | None, dict[str, Any]]:
    if _ROUTES is None:
        return None, {}
    for route in _ROUTES:
        if route.method != method:
            continue
        m = _placeholder_to_regex(route.pattern).match(path)
        if m is not None:
            return route, m.groupdict()
    return None, {}
```

**两个返回情况**:
- 匹配成功:`(Route_instance, {"service": "fin", "method": "POST", "path": "api/order/..."})`
- 匹配失败:`(None, {})`

**为什么是 `tuple[Route | None, dict]` 而不是 `Optional[Route]`?** 因为调用方在失败时仍要拿到一个空 dict,直接 `Optional[Route]` 会强迫调用方写 `if route: ... else: {}` — 用二元组让调用方总是能解构 `route, params = match_route(...)`,代码更直白。

**为什么 method 不匹配时 `continue` 而不是直接返回 None?** 因为存在 `Route("/a", "GET", ...)` 和 `Route("/a", "POST", ...)` 同时存在的可能(虽然本 server 没这种路由)。`continue` 是"通用的"语义,即使未来加了 POST 端点也无需改本函数。

### 3.7 路由表用 `tuple` 而非 `list` / `dict` 的"为什么"

- `tuple`:**不可变**,多线程安全,无锁读
- `list`:**可变**,未来万一有人 `.append()`,并发读到不一致
- `dict`:**键必须可哈希**,`Route` 是 dataclass,虽然可以哈希但意义不大(同 method + pattern 视为同 key 会丢失 handler 区分)

`tuple[Route, ...]` 是 **完美匹配**:顺序、不可变、可迭代。

---

## 4. `__init__.py` ── handlers + PlateRequestHandler + PlateServer

**职责**:这是 server 模块的"主文件",包含 7 个 handler、1 个 `BaseHTTPRequestHandler` 子类、1 个进程级 `PlateServer` 包装器、几个模块级常量。

### 4.1 模块级常量

```python
DEFAULT_VERSION: PlateVersion = PlateVersion(1, 0, 0)
SUPPORTED_VERSIONS: tuple[PlateVersion, ...] = (DEFAULT_VERSION,)
SUPPORTED_SERVICES: tuple[str, ...] = ("fin",)
```

| 常量                 | 含义                                                | 为什么这样                                   |
| -------------------- | --------------------------------------------------- | -------------------------------------------- |
| `DEFAULT_VERSION`    | 本 server 进程的"默认版本"                          | 当前只有 1.0.0,后续 PR 引入版本切换时改这里 |
| `SUPPORTED_VERSIONS` | 本 server 支持的全部版本                            | 当前只有 1 个,后续 PR 加新版本               |
| `SUPPORTED_SERVICES` | 本 server 支持的全部 service                        | 当前只有 `fin`,未来加 `home` `user` 等服务时改这里 |

**为什么 `SUPPORTED_SERVICES` 写死成 `("fin",)`?** 未来多服务时(假设加了 `home`),改成 `("fin", "home")`。Plate 选择 **"白名单" 而非"全量 reflect"** — 这样 server 进程对外的"服务面"是**确定的**,新增服务必须在 server 代码里显式登记,避免"我加了 service 包但忘记挂到 server"的隐患。

### 4.2 内部辅助函数

#### 4.2.1 `_collect_specs_for_service(service)`

```python
def _collect_specs_for_service(service: str) -> list[Any]:
    """直接拉取某 service 的全部 EndpointSpec 实例 — 不依赖 registry._index。"""
    module = importlib.import_module(f"Plate.{service}")
    return [
        attr for attr in vars(module).values()
        if type(attr).__name__ == "EndpointSpec"
    ]
```

**为什么绕过 `registry._index`?**

`server` 是 **只读视图**,但 `registry._index` 是个 **进程内 dict**,会在测试间 `reset` 时被清空。如果 server 走 `registry._index` 查 spec,可能在并发场景下:

1. 测试 A 调 `registry.reset()` → `_index = {}`
2. 同时测试 B 调 server 的 `handle_manifest_pinned` → 拿到空 manifest
3. 测试 A 失败,理由是"manifest 突然空了"

直接走 `importlib.import_module + vars(module).values()` 绕开 registry 状态机的并发边角,server 拿到的是 **"模块加载时刻的 EndpointSpec 快照"**。

**为什么用 `type(attr).__name__ == "EndpointSpec"` 而不是 `isinstance(attr, EndpointSpec)`?**

- 用 `isinstance` 需要 import `EndpointSpec`,而 `EndpointSpec` 在 `Plate.spec`,从 `Plate.server` 调它又会增加耦合
- 用类名字符串比较是一种"鸭子类型 + 类型名识别"的小技巧,避免直接 import 链

#### 4.2.2 `_ensure_service_loaded(service)`

```python
def _ensure_service_loaded(service: str) -> None:
    importlib.import_module(f"Plate.{service}")
```

**为什么是 `import_module` 而不是 `import_module` + `dir()`?** 因为 `import_module` 已经被 Python 的模块缓存系统处理 — 同一进程对同一 module 名只 import 一次,后续调用直接返回缓存。所以这个函数"调用 N 次,实际 import 1 次",server 进程期只触发一次 import 副作用。

> 实际上,这个函数在当前 `__init__.py` 代码里 **没有被任何地方调用**。它是预留给未来"server 启动时预热全部 service"场景的 — 注释里没明说,但函数留着表示意图。

#### 4.2.3 `_parse_version(s)`

```python
def _parse_version(s: str | None) -> PlateVersion | None:
    if s is None:
        return None
    try:
        return PlateVersion.parse(s)
    except ValueError:
        return None
```

**为什么把 `ValueError` 转 `None`?**

- 让 caller 用 `if version is None` 统一处理"缺参"和"格式错"两种情况
- 具体的错误信息(是缺参还是格式错)由 caller 根据 `version_str` 本身来区分

```python
# caller (PlateRequestHandler.do_GET) 里的区分逻辑:
if route.requires_version and version is None and version_str is not None:
    # 给了 version 但格式非法 → 400
    return error_response("INVALID_VERSION_FORMAT", ...)
if route.requires_version and version_str is None:
    return error_response("INVALID_VERSION_FORMAT", "missing ?version= ...", ...)
```

这是 **"把异常转成 None"** 的典型模式 — 不在低层抛错,在高层用更丰富的上下文报错。

### 4.3 7 个 handler 详解

#### 4.3.1 `handle_healthz`

```python
def handle_healthz(handler: Any, **kwargs: Any) -> tuple[bytes, int, dict[str, str]]:
    return json_response({"status": "ok", "version": str(DEFAULT_VERSION)})
```

- **URL**:`GET /healthz`
- **响应**:`{"status": "ok", "version": "1.0.0"}`
- **是否需要 version**:否
- **设计意图**:liveness probe,k8s / 负载均衡用它判断 server 是否活着
- **为什么 `handler` 参数是 `Any`?** handler 函数需要这个参数(签名一致性),但本函数完全不用它。用 `Any` 避免无谓的类型提示报错

#### 4.3.2 `handle_version_list`

```python
def handle_version_list(handler: Any, **kwargs: Any) -> tuple[bytes, int, dict[str, str]]:
    return json_response({
        "supported_versions": [v.to_dict() for v in SUPPORTED_VERSIONS],
        "default": DEFAULT_VERSION.to_dict(),
    })
```

- **URL**:`GET /v1/version`
- **响应**:`{"supported_versions": [{"major":1,"minor":0,"patch":0}], "default": {...}}`
- **用途**:消费方查"这个 server 支持哪些版本"

#### 4.3.3 `handle_manifest` 与 `handle_manifest_pinned`

```python
def handle_manifest(handler: Any, version: PlateVersion | None = None, **kwargs: Any):
    return handle_manifest_pinned(handler, DEFAULT_VERSION)


def handle_manifest_pinned(handler: Any, version: PlateVersion, **kwargs: Any):
    if version not in SUPPORTED_VERSIONS:
        return error_response("VERSION_NOT_FOUND", ..., 404, extra={"available_versions": ...})

    services: dict[str, list[dict]] = {}
    for svc in SUPPORTED_SERVICES:
        registry.collect(svc)
        svc_specs = [s.to_dict() for k, s in registry._index.items() if k.service == svc]
        services[svc] = svc_specs
    manifest = PlateManifest.from_services(version, services)
    return json_response(manifest.to_dict(), headers={"X-Plate-Version": str(version)})
```

- **URL1**:`GET /v1/manifest` → 返回默认版本 manifest
- **URL2**:`GET /v1/manifest/{version}` → 返回指定版本 manifest
- **响应体形态**(见 [../manifest/README.md](../manifest/README.md)):

```json
{
  "version": {"major": 1, "minor": 0, "patch": 0},
  "services": {
    "fin": [
      {"method": "POST", "path": "/api/order/order/orderDetail", ...},
      ...
    ]
  },
  "checksum": "sha256:abcdef..."
}
```

- **响应头**:`X-Plate-Version: 1.0.0`
- **设计意图**:这是 server 的"主要消费点" — AI skill / 远程 mock / 文档生成器**首先拉 manifest**,再用 checksum 决定是否要拉具体 spec

**为什么两个 handler 包装?** 默认版本是"最常见"用法,URL 短一些(`/v1/manifest` vs `/v1/manifest/1.0.0`);显式版本是"明确语义"用法。两者用同一函数实现,避免代码重复。

**`X-Plate-Version` header 的意义**:HTTP 协议头传递当前响应所属的版本 — 即使 URL 是 `/v1/manifest` (没指定版本),消费方也能从 header 读出"我拿到的是 1.0.0",便于日志 / 调试。

#### 4.3.4 `handle_spec_service`

```python
def handle_spec_service(handler: Any, service: str, version: PlateVersion, **kwargs: Any):
    if service not in SUPPORTED_SERVICES:
        return error_response("SERVICE_NOT_FOUND", ..., 404, ...)
    registry.collect(service)
    specs = [s.to_dict() for k, s in registry._index.items() if k.service == service]
    payload = {
        "service": service,
        "version": version.to_dict(),
        "checksum": PlateManifest.compute_checksum(version, {service: specs}),
        "specs": sorted(specs, key=lambda s: (s["method"], s["path"])),
    }
    return json_response(payload, headers={"X-Plate-Version": str(version)})
```

- **URL**:`GET /v1/spec/{service}?version=X`
- **响应**:

```json
{
  "service": "fin",
  "version": {"major": 1, "minor": 0, "patch": 0},
  "checksum": "sha256:...",
  "specs": [
    {"method": "POST", "path": "/api/order/order/orderAdd", "category": "BUSINESS", ...},
    ...
  ]
}
```

- **为什么 `specs` 要 `sorted(key=lambda s: (s["method"], s["path"]))`?** 让 HTTP 响应字节级稳定 — 同一份 registry 多次调用本端点,响应字节完全相同
- **`checksum` 字段是单 service 级别的**:不与 `handle_manifest` 共享多 service checksum,便于消费方"只下载一个 service 后做完整性校验"

#### 4.3.5 `handle_spec_endpoint`

```python
def handle_spec_endpoint(handler: Any, service: str, method: str, path: str, version: PlateVersion, **kwargs: Any):
    if service not in SUPPORTED_SERVICES:
        return error_response("SERVICE_NOT_FOUND", ..., 404, ...)
    full_path = "/" + path
    try:
        spec = registry.resolve(service, method, full_path)
    except LookupError as e:
        return error_response("ENDPOINT_NOT_FOUND", str(e), 404)
    return json_response(
        {"service": service, "version": version.to_dict(), "spec": spec.to_dict()},
        headers={"X-Plate-Version": str(version)},
    )
```

- **URL**:`GET /v1/spec/{service}/{method}/{path:path}?version=X`
- **响应**:`{service, version, spec: {...完整 EndpointSpec dict...}}`
- **`full_path = "/" + path`**:路由匹配把 `{path:path}` 段的值去掉前导 `/`(因为 URL 段间是 `/`,首段要补回),所以 `api/order/...` → `/api/order/...`,与 `EndpointSpec.path` 匹配
- **`registry.resolve` 抛 `LookupError`**:在 [../core/README.md](../core/README.md) 里,`resolve` 找不到端点时抛 `LookupError`,这里捕获并转 404 + `ENDPOINT_NOT_FOUND`

#### 4.3.6 `handle_doc_service`

```python
def handle_doc_service(handler: Any, service: str, version: PlateVersion, **kwargs: Any):
    if service not in SUPPORTED_SERVICES:
        return error_response("SERVICE_NOT_FOUND", ..., 404, ...)
    docs = _get_docs_for_service(service)
    return json_response(
        {"service": service, "version": version.to_dict(), "docs": docs},
        headers={"X-Plate-Version": str(version)},
    )
```

- **URL**:`GET /v1/doc/{service}?version=X`
- **响应**:`{service, version, docs: {path: EndpointDoc dict, ...}}`
- **L2 是热数据**:A3 冷热分层原则下,L2(人工注释)与 L1(机器重生 spec)同样在 server 端"在线",所以走一样的 HTTP 协议

#### 4.3.7 `handle_doc_endpoint`

```python
def handle_doc_endpoint(handler: Any, service: str, method: str, path: str, version: PlateVersion, **kwargs: Any):
    if service not in SUPPORTED_SERVICES:
        return error_response("SERVICE_NOT_FOUND", ..., 404, ...)
    full_path = "/" + path
    docs = _get_docs_for_service(service)
    doc = docs.get(full_path)
    if doc is None:
        return error_response("DOC_NOT_FOUND", ..., 404)
    return json_response(
        {"service": service, "version": version.to_dict(), "path": full_path, "doc": doc},
        headers={"X-Plate-Version": str(version)},
    )
```

- **URL**:`GET /v1/doc/{service}/{method}/{path:path}?version=X`
- **响应**:`{service, version, path, doc: {...}}`
- **`DOC_NOT_FOUND` 错误码**:与 spec 端点的 `ENDPOINT_NOT_FOUND` 区分,显式表达"是 L2 doc 缺失,不是 spec 缺失"

### 4.4 内部函数 `_get_docs_for_service(service)`

```python
def _get_docs_for_service(service: str) -> dict[str, dict]:
    if service == "fin":
        from Plate.fin.dannotations import _DOCS
        return {k: dict(v.__dict__) for k, v in _DOCS.items()}
    return {}
```

**为什么用 `dict(v.__dict__)` 而不是 `dataclasses.asdict(v)`?**

- `_DOCS` 的 value 是 `EndpointDoc` 实例(见 [../doc/README.md](../doc/README.md))
- `dataclasses.asdict` 会递归处理嵌套 dataclass,本场景不需要
- `__dict__` 直接拿到实例的字段 dict,扁平快速

**为什么"fin 服务有 doc,其他 service 空"这种硬编码?** 当下只有 fin 服务有 L2 doc,这是"渐进补"的现状。未来其他服务加 doc 时,把 `if service == "fin"` 改成 `if hasattr(...)` 或 dispatch table。

### 4.5 `PlateRequestHandler` 类

```python
class PlateRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        # 1. 解析 path 与 query
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        version_str = query.get("version", [None])[0]
        version = _parse_version(version_str)

        # 2. 路由匹配
        route, params = _match_route(path, self.command)
        ...

    def _write(self, body: bytes, status: int, headers: dict[str, str]) -> None:
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        """压制默认 stderr 日志(测试时静默)。"""
```

**7 步 `do_GET` 流程**:

| 步骤 | 做什么                                                                | 失败处理                                          |
| ---- | -------------------------------------------------------------------- | ------------------------------------------------- |
| 1    | `urlparse(self.path)` 拆 path 和 query                               | —                                                |
| 2    | 提取 `?version=`                                                     | —                                                |
| 3    | `_parse_version` 转 `PlateVersion` 或 `None`                         | —                                                |
| 4    | `_match_route` 找路由                                                | 无匹配 → 404 NOT_FOUND                            |
| 5    | 校验 `route.requires_version` 是否满足                               | 缺参 → 400 INVALID_VERSION_FORMAT                 |
| 6    | 校验 `version` 是否在 SUPPORTED_VERSIONS                             | 不在 → 404 VERSION_NOT_FOUND                       |
| 7    | URL 段 `version` 解析(`/v1/manifest/{version}` 的情况)               | 解析失败 → 400;不在 → 404                         |
| 8    | 调 `route.handler(self, **call_kwargs)`                              | 抛异常 → 500 INTERNAL_ERROR                        |
| 9    | `_write(body, status, headers)` 写 HTTP 响应                         | —                                                |

**为什么 `params["version"]` 是 str 而 `version` 可能是 `PlateVersion`?**

- URL 段(如 `/v1/manifest/1.0.0`)匹配出来的是 str `"1.0.0"`
- query param(已经过 `_parse_version`)可能是 `PlateVersion | None`
- handler 期望 `PlateVersion` 类型,所以在调用前 `PlateVersion.parse(url_version)` 转一下

**`log_message` 覆盖为空的方法**: `BaseHTTPRequestHandler` 默认把每次请求打到 stderr,测试时非常烦。覆盖成空方法 → 测试输出干净。

**为什么不用 FastAPI / Flask?** Plate 设计原则之一是 **"零第三方依赖"**(见 [../overview.md](../overview.md))。`http.server` 是 stdlib,部署时不需要 pip install 任何东西,适合"插件化"嵌入到其他 Python 进程内。

### 4.6 `PlateServer` 类

```python
class PlateServer:
    def __init__(self, port: int = 0, host: str = "127.0.0.1") -> None: ...
    @property
    def port(self) -> int: ...
    def start(self) -> None: ...
    def stop(self) -> None: ...
```

**`port=0` 的意义**:让 OS 动态分配空闲端口 — 测试时可以启多个 server 实例互不冲突。

**`@property port` 的双阶段返回**:

```python
@property
def port(self) -> int:
    if self._httpd is not None:
        return self._httpd.server_address[1]   # 实际分配的端口
    return self._port                            # 用户传入的(可能是 0)
```

- start() 之前:返回 `_port`(用户传入值,可能 0)
- start() 之后:返回 `self._httpd.server_address[1]`(OS 实际分配)

**`start()` 用 daemon 线程**:`threading.Thread(target=self._httpd.serve_forever, daemon=True)` — `daemon=True` 让 Python 退出时不等这个线程,避免测试结束后僵尸进程。

**`stop()` 的两步走**:

1. `self._httpd.shutdown()` — 告诉 serve_forever 退出循环
2. `self._httpd.server_close()` — 关 socket
3. `self._thread.join(timeout=2.0)` — 等线程真正退出(防止 socket TIME_WAIT 残留)

**为什么 `join` 要 `timeout=2.0`?** daemon 线程 join 不设超时,理论可能 hang 住(serve_forever 没收到 shutdown 信号)。2 秒够用,超时后 Python 进程继续 — 反正 daemon 进程退出时一起死。

### 4.7 路由注册与首次调用

```python
_ROUTES_REGISTERED: bool = False

def _register_routes_once() -> None:
    from Plate.server.router import register_handlers
    register_handlers({
        "healthz": handle_healthz,
        ...
    })

def _match_route(path: str, method: str):
    global _ROUTES_REGISTERED
    if not _ROUTES_REGISTERED:
        _register_routes_once()
        _ROUTES_REGISTERED = True
    from Plate.server.router import match_route
    return match_route(path, method)
```

**为什么首次请求时才注册?** 避免循环导入。`server/__init__.py` 顶层 import `router` 时,`router` 又想用 `from Plate.server import handle_xxx`,会爆 `ImportError`。把注册动作延迟到 `_match_route` 内部,所有 handler 都已经 import 完了,`register_handlers` 可以安全拿它们。

**`global _ROUTES_REGISTERED` 的必要性**:Python 闭包内对模块级变量赋值,需要 `global` 声明。

---

## 5. 7 个 URL 端点全清单

按"是否需要 `?version=` query"分组:

### 5.1 不需要 version 的 3 个端点(metadata 类)

| URL                       | Handler                  | 用途                                      | 错误码                              |
| ------------------------- | ------------------------ | ----------------------------------------- | ----------------------------------- |
| `GET /healthz`            | `handle_healthz`         | liveness probe                            | —                                   |
| `GET /v1/version`         | `handle_version_list`    | 列出本 server 支持的全部版本              | —                                   |
| `GET /v1/manifest`        | `handle_manifest`        | 默认版本 manifest(全部 service)          | —                                   |
| `GET /v1/manifest/{ver}`  | `handle_manifest_pinned` | 指定版本 manifest                          | `VERSION_NOT_FOUND` (404)           |

### 5.2 需要 version 的 4 个端点(spec / doc 查)

| URL                                                              | Handler                | 用途                       | 错误码                                                                 |
| ---------------------------------------------------------------- | ---------------------- | -------------------------- | ---------------------------------------------------------------------- |
| `GET /v1/spec/{service}?version=X`                              | `handle_spec_service`  | 单 service 全部 spec      | `SERVICE_NOT_FOUND` (404) / `INVALID_VERSION_FORMAT` (400) / `VERSION_NOT_FOUND` (404) |
| `GET /v1/spec/{service}/{method}/{path:path}?version=X`         | `handle_spec_endpoint` | 单端点 spec                | 同上 + `ENDPOINT_NOT_FOUND` (404)                                     |
| `GET /v1/doc/{service}?version=X`                               | `handle_doc_service`   | 单 service L2 doc         | `SERVICE_NOT_FOUND` (404) / `INVALID_VERSION_FORMAT` (400) / `VERSION_NOT_FOUND` (404) |
| `GET /v1/doc/{service}/{method}/{path:path}?version=X`          | `handle_doc_endpoint`  | 单端点 L2 doc              | 同上 + `DOC_NOT_FOUND` (404)                                          |

### 5.3 端点之间的关系

```
                ┌──────────────┐
                │  /healthz    │ (liveness)
                └──────────────┘

       ┌───────────────┴───────────────┐
       ▼                                ▼
   /v1/version                    /v1/manifest(/ver)
   (versions list)                (full registry snapshot, with checksum)
                                        │
                          ┌─────────────┴─────────────┐
                          ▼                           ▼
                  /v1/spec/{svc}               /v1/doc/{svc}
                  (all specs of a svc)         (all docs of a svc)
                          │                           │
                          ▼                           ▼
              /v1/spec/{svc}/{m}/{p}        /v1/doc/{svc}/{m}/{p}
              (single spec dict)            (single doc dict)
```

消费方典型工作流:
1. `GET /v1/version` — 查支持版本
2. `GET /v1/manifest?version=1.0.0` — 拉全 manifest,得到 checksum
3. 比对本地缓存的 checksum,决定是否要拉具体 spec
4. `GET /v1/spec/fin` — 拉 fin 服务全部 spec
5. (后续按需) `GET /v1/spec/fin/POST/api/order/order/orderDetail?version=1.0.0` — 拉单端点

---

## 6. 请求/响应/错误码全谱

### 6.1 成功响应模板

```http
HTTP/1.1 200 OK
Content-Type: application/json; charset=utf-8
Content-Length: 1234
X-Plate-Version: 1.0.0    ← (manifest / spec / doc 端点)

{"...": "..."}
```

### 6.2 错误响应模板

```http
HTTP/1.1 404 Not Found
Content-Type: application/json; charset=utf-8
Content-Length: 234

{
  "error": "ENDPOINT_NOT_FOUND",
  "message": "no spec for fin POST /api/foo",
  "available_services": ["fin"]   ← extra 字段(可选)
}
```

### 6.3 错误码索引(按 HTTP status 分组)

| status | error code                  | 触发位置                              | extra 字段(可选)         |
| ------ | --------------------------- | ------------------------------------- | ------------------------ |
| 400    | `INVALID_VERSION_FORMAT`    | `do_GET` 步骤 5、7                    | —                        |
| 404    | `NOT_FOUND`                 | `do_GET` 步骤 4                       | —                        |
| 404    | `SERVICE_NOT_FOUND`         | `handle_spec_*` / `handle_doc_*`     | `available_services`     |
| 404    | `ENDPOINT_NOT_FOUND`        | `handle_spec_endpoint`               | —                        |
| 404    | `DOC_NOT_FOUND`             | `handle_doc_endpoint`                | —                        |
| 404    | `VERSION_NOT_FOUND`         | `handle_manifest_pinned` / `do_GET`  | `available_versions`     |
| 500    | `INTERNAL_ERROR`            | `do_GET` 步骤 8(兜底)                | —                        |

---

## 7. 设计哲学与决策记录

### 7.1 零第三方依赖(为什么用 stdlib `http.server`)

- **部署简单**:`pip install gimbal` 之后 server 就可跑,不需要 `pip install fastapi uvicorn pydantic ...`
- **启动快**:`http.server` 启动时间 < 50ms,FastAPI 启动时间 ~ 1s
- **测试友好**:无第三方依赖,测试在 CI 上不会因为依赖版本冲突挂掉
- **可嵌入**:Plate server 是"可以嵌入到其他 Python 进程里跑"的(测试时 `PlateServer.start()` 启后台线程),不是 standalone 服务

**代价**:
- 无 async,无中间件机制,无自动 OpenAPI 文档生成
- 性能:`http.server` 是 BaseHTTPServer,单线程默认(本 server 走 `daemon=True` 启动 `serve_forever`,并发受 GIL 限制)

**为什么性能不是问题?** Plate server 的消费方是 AI skill / 远程 mock / 文档生成器 — 它们的请求频率 < 10 QPS,完全够用。如果未来需要高并发(>100 QPS),才考虑迁到 FastAPI / aiohttp。

### 7.2 字节级可重现(`sort_keys=True + separators=(",", ":")`)

与 [../manifest/README.md](../manifest/README.md) 的 SHA256 一致 — server 的 HTTP 响应也走同一字节级可重现规则。这给消费方带来:

- **缓存友好**:同一份 registry,响应字节完全相同,CDN / 反向代理可以无脑缓存
- **跨实例 diff 简单**:本地 server 和 CI server 响应可以直接 `diff`
- **快照测试安全**:可以拿响应字符串做 SHA256 校验

### 7.3 只读视图(server 不修改 registry)

server 全程 **只读**:
- 不调 `registry.collect` 之外的状态变更方法
- 不写文件、不写 DB、不发网络请求(除非 registry 内部自己去做)
- handler 抛异常时只回 500,不改任何状态

这是 **"测试确定性"** 哲学的体现 — server 进程在测试期间启动 + 测试 + 关闭,registry 状态与启停前完全一致。

### 7.4 路由表用 `tuple` 而非 `dict` / `list`

详见 §3.7。简短回顾:**tuple 不可变 + 多线程安全 + 顺序敏感** 三点全要。

### 7.5 `_collect_specs_for_service` 绕过 `registry._index` 的设计

详见 §4.2.1。这是 **"避免测试间 reset 干扰 server 只读视图"** 的关键决策。

### 7.6 默认版本 vs 显式版本

- `GET /v1/manifest` — 默认(最常见用法)
- `GET /v1/manifest/{version}` — 显式(明确语义)

消费方 90% 用默认路径;只有当 server 后续支持多版本(比如 1.0.0 + 2.0.0)时,显式路径才变得重要。

### 7.7 `X-Plate-Version` 响应头

即使 URL 不带 version(`/v1/manifest`),响应头仍带 `X-Plate-Version: 1.0.0` — 让消费方**有显式 channel 知道当前 server 用的版本**,不用解析 body。

### 7.8 daemon 线程的取舍

`PlateServer.start()` 用 `daemon=True` 启动 serve_forever 线程。

- **好处**:Python 主进程退出时,server 线程自动死,不需要显式 stop
- **坏处**:daemon 线程突然被 kill,正在处理的请求会"半路夭折",client 端可能看到 connection reset
- **本 server 的取舍**:测试场景下 daemon 是合理选择(测试用完即弃,夭折也无所谓);生产场景应该 `start()` 后 `stop()` 显式收尾

### 7.9 `log_message` 抑制默认日志

`BaseHTTPRequestHandler` 默认把 `127.0.0.1 - - [date] "GET /healthz HTTP/1.1" 200 -` 这种 access log 打到 stderr。Plate 覆盖成空方法,因为:

- 测试时这些 log 是 noise
- 真实场景下 Plate server 是"嵌入组件"而非"独立服务",access log 应该由宿主进程自己控制

---

## 8. 典型使用示例

### 8.1 启动 server(在测试代码里)

```python
import time
import requests
from Plate.server import PlateServer

# 1. 启动一个动态端口的 server
server = PlateServer(port=0)
server.start()
time.sleep(0.1)  # 给 server 一点启动时间

base_url = f"http://127.0.0.1:{server.port}"

# 2. 调 healthz
resp = requests.get(f"{base_url}/healthz")
assert resp.json() == {"status": "ok", "version": "1.0.0"}

# 3. 拉 manifest
resp = requests.get(f"{base_url}/v1/manifest")
manifest = resp.json()
assert "fin" in manifest["services"]
assert "checksum" in manifest

# 4. 拉 fin 服务的所有 spec
resp = requests.get(f"{base_url}/v1/spec/fin?version=1.0.0")
fin_specs = resp.json()
assert len(fin_specs["specs"]) == 31  # fin 服务当前共 31 个端点

# 5. 拉单端点
resp = requests.get(
    f"{base_url}/v1/spec/fin/POST/api/order/order/orderDetail?version=1.0.0"
)
spec = resp.json()["spec"]
assert spec["request"] == "OrderDetailRequest"

# 6. 收尾
server.stop()
```

### 8.2 命令行启动(独立进程)

Plate 暂未提供 CLI 启动方式,但 10 行代码可补:

```python
# bin/plate-server.py
from Plate.server import PlateServer

if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    server = PlateServer(port=port)
    server.start()
    print(f"Plate server listening on http://127.0.0.1:{server.port}")
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()
```

```bash
python -m bin.plate-server 8765
# 另一终端:
curl http://127.0.0.1:8765/healthz
# {"status":"ok","version":"1.0.0"}
```

### 8.3 并发启动多个 server(测试隔离)

```python
import pytest
from Plate.server import PlateServer

@pytest.fixture
def server_per_test():
    """每个测试函数一个独立 server,端口 0 互不冲突。"""
    s = PlateServer(port=0)
    s.start()
    yield s
    s.stop()

def test_health(server_per_test):
    import requests
    resp = requests.get(f"http://127.0.0.1:{server_per_test.port}/healthz")
    assert resp.status_code == 200
```

### 8.4 错误码测试

```python
def test_invalid_version():
    s = PlateServer(port=0)
    s.start()
    try:
        resp = requests.get(f"http://127.0.0.1:{s.port}/v1/spec/fin?version=abc")
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"] == "INVALID_VERSION_FORMAT"
    finally:
        s.stop()


def test_service_not_found():
    s = PlateServer(port=0)
    s.start()
    try:
        resp = requests.get(f"http://127.0.0.1:{s.port}/v1/spec/home?version=1.0.0")
        assert resp.status_code == 404
        body = resp.json()
        assert body["error"] == "SERVICE_NOT_FOUND"
        assert body["available_services"] == ["fin"]
    finally:
        s.stop()
```

---

## 9. 不变量总结

| #   | 不变量                                                                              | 守护位置                              |
| --- | ----------------------------------------------------------------------------------- | ------------------------------------- |
| 1   | 所有响应 body 是 `sort_keys=True + separators=(",", ":")` 序列化                    | `response.json_response`             |
| 2   | 所有响应 `Content-Type: application/json; charset=utf-8`                            | `response.json_response`             |
| 3   | 所有响应 `Content-Length` 必带                                                      | `response.json_response`             |
| 4   | 错误响应体形态 = `{error, message, ...extra}`                                      | `response.error_response`            |
| 5   | `SUPPORTED_SERVICES` 必须是 `tuple`(不可变)                                        | `server/__init__.py` 顶层常量         |
| 6   | `SUPPORTED_VERSIONS` 必须是 `tuple`(不可变)                                        | 同上                                  |
| 7   | 路由表 `_ROUTES` 是 `tuple[Route, ...]`(不可变)                                    | `router._ROUTES`                      |
| 8   | `Route` 是 `frozen=True` dataclass(不可变)                                          | `router.Route`                        |
| 9   | `register_handlers` 在 server 启动后最多调用一次                                    | `_ROUTES_REGISTERED` 旗标             |
| 10  | `PlateRequestHandler` 只处理 `do_GET`(无 POST/PUT/DELETE)                          | 当前 PR 限制                          |
| 11  | `PlateServer.port=0` 时由 OS 分配,start() 后可读                                    | `PlateServer.port` property          |
| 12  | `PlateServer.stop()` 后 `port` 仍可读,但 `_httpd` 为 None(若再 start 是新 server) | 状态机                                |
| 13  | `log_message` 覆盖为空,不向 stderr 打 access log                                   | `PlateRequestHandler.log_message`    |
| 14  | 任何 handler 抛异常 → 500 INTERNAL_ERROR(不挂 server)                              | `do_GET` 步骤 8 `try/except`          |
| 15  | 任何路由不匹配 → 404 NOT_FOUND(无歧义)                                             | `do_GET` 步骤 4                       |
| 16  | `version` 不在 SUPPORTED_VERSIONS → 404 VERSION_NOT_FOUND(显式告知可选项)          | `do_GET` 步骤 6/7                     |
| 17  | version query 缺参或格式错 → 400 INVALID_VERSION_FORMAT                            | `do_GET` 步骤 5                       |
| 18  | service 不在 SUPPORTED_SERVICES → 404 SERVICE_NOT_FOUND                            | `handle_spec_*` / `handle_doc_*`      |
| 19  | L1/L2 对称性:有 spec 无 doc 允许,有 doc 无 spec 报错(由 doc 模块自己保证)         | `dannotations.get_doc` 返 None         |

---

## 10. 设计权衡与未来工作

### 10.1 当前权衡

| 决策                                       | 收益                                       | 代价                                       |
| ------------------------------------------ | ------------------------------------------ | ------------------------------------------ |
| 用 stdlib `http.server` 而非 FastAPI       | 零依赖、启动快、可嵌入                     | 无 async、无中间件、需手写响应             |
| 路由表用 `tuple` 而非 `list`               | 不可变 + 多线程安全                        | 增加顺序敏感性(需手动保证精确匹配在前)    |
| `SUPPORTED_SERVICES` 写死为 `("fin",)`     | server 的"服务面"是确定白名单             | 加新服务需改 server 代码                   |
| `SUPPORTED_VERSIONS` 单一版本              | 实现简单                                   | 多版本切换要扩展                           |
| `default_version` 等于 `supported_versions[0]` | 默认路径含义清晰                        | 不支持"默认版本"和"服务实际版本"分开       |
| `_collect_specs_for_service` 绕过 registry | 测试间 reset 不影响 server                | 失去 registry 缓存(每次重新遍历 module 字段) |
| 错误体用 `{error, message, ...extra}`      | 错误码稳定 + 人类可读消息 + 可选额外信息 | 不如 RFC 7807 problem+json 标准化         |
| handler 返回 `(bytes, status, headers)` 三元组 | 与 stdlib 解耦,可单测                  | 与 `BaseHTTPRequestHandler` 原生接口不直接对应 |
| `plate-server` 无 CLI 入口                 | 极简(测试时 inline 启动)                  | 不能直接用 `python -m Plate.server` 跑 daemon |

### 10.2 未来工作

1. **多版本支持**:`SUPPORTED_VERSIONS` 改成 `(1.0.0, 1.1.0, 2.0.0)`,handler 加 `version not in SUPPORTED_VERSIONS` 校验
2. **多 service 支持**:`SUPPORTED_SERVICES` 加 `("fin", "home", "user")`,每个 service 走 `from Plate.{svc}.dannotations import _DOCS` 的 dispatch table
3. **POST/PUT/DELETE**:`Route.method` 字段已经支持,只需在 `PlateRequestHandler` 加 `do_POST` 等方法
4. **CLI 入口**:`python -m Plate.server --port 8765`,补 `__main__.py`
5. **健康检查深度**:`/healthz` 加"检查 registry 是否加载完毕"子项
6. **metrics 端点**:`/metrics` 返回 Prometheus 格式的请求计数、错误率
7. **TLS**:`HTTPServer` 换成 `http.server.HTTPServer` + ssl 包装
8. **流式响应**:对超大 manifest(>10MB)做 chunked transfer

### 10.3 与整体 Plate 哲学的一致性

| 哲学原则(见 [../overview.md](../overview.md)) | server 模块怎么落地                                              |
| -------------------------------------------- | --------------------------------------------------------------- |
| 零侵入(不污染后端代码)                       | server 是独立的 stdlib HTTP,后端 Gin 代码不需要改              |
| L1/L2 物理分离                                | spec 走 L1 端点,doc 走 L2 端点,7 个 URL 镜像分立               |
| 懒加载(拉式收集)                             | `registry.collect(svc)` 在 handler 内按需触发                   |
| 线程安全                                       | `_ROUTES` 是 tuple 不可变,handler 内读 `registry._index` 走锁  |
| 字节级可重现                                 | `sort_keys=True + separators=(",", ":")` + 排序后的 specs       |
| 契约保真                                      | wire path / method / service / version 全都 1:1 透传          |
| 声明式 + 命令式混合                           | 路由表是声明式(tuple),handler 内是命令式                        |
| 业务标注(category / mutates_state)            | server 不直接读 category / mutates_state,留给消费方按需过滤     |

---

> **完结提示**:本文件覆盖 `Plate/server/` 三文件(commit `e0be7bf` 之后)。当新增端点 / 改路由表 / 加 CLI 入口时,本文件的 §3 路由表、§5 端点清单、§6 错误码、§9 不变量需要同步更新。
