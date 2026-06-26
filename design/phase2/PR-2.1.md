# PR-2.1: 远端服务契约(HTTP 协议草案)

> **状态**:待执行
>
> **PR 范围**:为 Phase 2 服务化定义 HTTP 协议契约,**只**含
> 1. URL 形态 + HTTP 方法
> 2. 请求/响应 JSON schema
> 3. 错误码语义
> 4. 版本在 URL(不在 header)的硬约束
>
> **前置依赖**:**PR-2.0 已落地**(version + serialization 已就绪)
>
> **关键设计**:本 PR **不实现服务端**,只**定协议**。服务端实现
> 留 PR-2.3(部署形态)。SDK 实现留 PR-2.2(并行)。
>
> **对应设计**:[PLATE_EVOLUTION.md §3 Phase 2 服务化基础设施](../PLATE_EVOLUTION.md) +
> A5 协议先于实现 + A3 冷热分层在两个端点

---

## 1. 业务动机

### 1.1 业务需求

**核心问题**:Phase 2 服务化的"先决条件"是协议先行 —— 服务端和 SDK 必须
对契约达成共识,**否则**两边各做各的,集成时互相不兼容。

**本 PR 协议草案必须确定**:
1. **URL 路由**:`/v1/spec` 与 `/v1/doc` 分开(对应 A3 冷热分层)
2. **版本在 URL**:`?version=X.Y.Z` 或路径 `/v1/manifest/{version}`(A5)
3. **JSON schema**:响应字段与 PR-2.0 `to_dict()` 产物一致
4. **错误码**:离线 / 404 / 500 / 版本不存在(SDK 端优雅降级依赖错误码语义)
5. **Content-Type + ETag + Cache-Control**:协议级缓存语义

### 1.2 关键决策

- **HTTP 而非 gRPC**:服务端 / 客户端 / 测试工具都用 HTTP 是最低门槛;
  gRPC 性能高但增加 protoc 依赖,Phase 2 不必要;Phase 3 MCP 再考虑升级
- **版本在 URL 而非 header**:`?version=1.0.0` 在 URL 里 → CDN 缓存友好,
  客户端禁用 ETag 检查 → 简单;header 容易因代理丢失
- **响应 JSON 与 PR-2.0 完全一致**:`/v1/spec` 返回的 JSON 必须是
  `EndpointSpec.to_dict()` 产物,**不**做二次包装(防 SDK 解析时
  字段名漂移)
- **错误响应也用 JSON**:`{"error": "code", "message": "human readable"}`
  形态,SDK 可编程处理

---

## 2. 协议规范

### 2.1 URL 路由表

| 路径 | 方法 | 用途 | 冷/热 |
|---|---|---|---|
| `/v1/manifest` | GET | 返回完整 manifest(版本 + services + 端点 + checksum) | 冷(可缓存) |
| `/v1/manifest/{version}` | GET | 返回指定版本 manifest(404 if not exist) | 冷 |
| `/v1/spec` | GET | 返回全部 spec(dict: service → list[spec]) | 冷 |
| `/v1/spec/{service}` | GET | 返回单 service 的全部 spec | 冷 |
| `/v1/spec/{service}/{method}/{path:path}` | GET | 返回单端点 spec | 冷 |
| `/v1/doc` | GET | 返回全部 EndpointDoc dict | 热(可不缓存) |
| `/v1/doc/{service}` | GET | 返回单 service 的 EndpointDoc dict | 热 |
| `/v1/doc/{service}/{method}/{path:path}` | GET | 返回单端点 EndpointDoc | 热 |
| `/v1/version` | GET | 返回服务端支持的版本列表 | 冷 |
| `/healthz` | GET | 健康检查 | — |

**路径说明**:
- `/v1/spec/{method}/{path:path}`:path 部分用 `:path` converter,允许 `/` 透传
  (例:`/v1/spec/fin/POST/api/order/order/orderDetail`)
- `/v1/manifest` 不带版本参数 → 返回"服务端默认推荐版本"(latest stable)
- 客户端要 pin 某版本 → `/v1/manifest/1.0.0`

### 2.2 请求 schema

```
GET /v1/spec/fin?version=1.0.0
Headers:
  Accept: application/json
  (可选)If-None-Match: "<etag>"

Query:
  version: 必填(对所有 /v1/* 端点)。SDK 必须显式 pin,不允许"latest"
```

### 2.3 响应 schema

#### 2.3.1 成功响应(`/v1/spec/fin`)

```json
{
  "service": "fin",
  "version": {"major": 1, "minor": 0, "patch": 0},
  "checksum": "09042f457bc253ffc99e8cd66f89b818b0ed2c33bf6117e3ca012556f72281db",
  "specs": [
    {
      "method": "POST",
      "path": "/api/order/order/orderDetail",
      "category": "query",
      "mutates_state": false,
      "bindings": [
        {"from_path": ["data", "audit_id"], "to_path": ["audit_id"], "required": true, "transform": null}
      ],
      "request_ref": "Plate.fin.models.OrderDetailRequest",
      "responses_ref": {"200": "Plate.fin.models.OrderDetailResponse"},
      "default_response_ref": null,
      "response_data_models_ref": {"200": "Plate.fin.models.OrderDetailData"},
      "summary": "按订单 ID 查询订单详情",
      "description": "...",
      "tags": ["order", "detail"],
      "auth_required": true,
      "response_union_ref": {},
      "mock_hook_ref": null,
      "validate_hook_ref": null,
      "build_request_hook_ref": null
    }
  ]
}
```

**字段约束**:
- `specs` 数组内每个元素 = `EndpointSpec.to_dict()` 产物(PR-2.0)
- `bindings` 数组内每个元素 = `FieldBinding.to_dict()` 产物
- `version` 是 dict(非 string):便于客户端直接 `PlateVersion.from_dict()`
- `checksum` 是单 service 内端点的 SHA256(与 manifest 的 checksum 算法一致)

#### 2.3.2 Manifest 响应(`/v1/manifest/1.0.0`)

```json
{
  "version": {"major": 1, "minor": 0, "patch": 0},
  "services": {
    "auth": [...],
    "fin": [...]
  },
  "checksum": "..."
}
```

**注**:这是 `PlateManifest.to_dict()` 产物(PR-2.0 §2.4)。

#### 2.3.3 Doc 响应(`/v1/doc/fin`)

```json
{
  "service": "fin",
  "version": {"major": 1, "minor": 0, "patch": 0},
  "docs": {
    "/api/order/order/orderDetail": {
      "summary": "按订单 ID 查询订单详情",
      "notes": ["限流:每用户 10 QPS"],
      "requires": ["已登录"],
      "see_also": ["/api/order/order/addOrder"]
    }
  }
}
```

**字段约束**:`docs[path]` 内每个对象 = `EndpointDoc.__dict__` 产物
(不含 `_SUMMARY_MAX_LEN` 等内部常量)。

### 2.4 错误响应 schema

```json
{
  "error": "VERSION_NOT_FOUND",
  "message": "version 99.0.0 not found on server",
  "available_versions": [
    {"major": 1, "minor": 0, "patch": 0}
  ]
}
```

**错误码枚举**:

| 错误码 | HTTP status | 语义 | SDK 处理 |
|---|---|---|---|
| `VERSION_NOT_FOUND` | 404 | 请求版本不存在 | 退到 fallback 版本(配置) |
| `SERVICE_NOT_FOUND` | 404 | service 名不存在 | `LookupError` 上抛 |
| `ENDPOINT_NOT_FOUND` | 404 | (method, path) 不存在 | `LookupError` 上抛 |
| `INVALID_VERSION_FORMAT` | 400 | `?version=x.y` 不是 semver | 客户端 bug,直接报错 |
| `INTERNAL_ERROR` | 500 | 服务端异常 | 重试 3 次后 fallback |
| `OFFLINE` | — | SDK 网络不可达(非服务端错误) | fallback 本地缓存 |

**关键**:错误响应**也**走 `application/json`,SDK 可统一处理。

### 2.5 HTTP 头约定

| Header | 服务端必发 | 客户端语义 |
|---|---|---|
| `Content-Type` | `application/json; charset=utf-8` | 客户端校验 |
| `ETag` | SHA256(checksum),带引号 | 304 缓存语义(可选) |
| `Cache-Control` | `public, max-age=86400`(/v1/spec/*) 或 `no-cache`(/v1/doc/*) | — |
| `X-Plate-Version` | 当前响应的版本(如 `1.0.0`) | 客户端二次确认 |

### 2.6 端点对照表(协议 vs 实现)

| 协议 URL | 实现层调用 | 实现位置 |
|---|---|---|
| `GET /v1/manifest` | `PlateManifest.from_services(...)` | `src/Plate/manifest.py` |
| `GET /v1/spec/fin` | `registry._index[fin]` 全部 spec.to_dict() | `src/Plate/core.py` + `src/Plate/spec.py` |
| `GET /v1/doc/fin` | `fin/dannotations/_DOCS` | `src/Plate/fin/dannotations/__init__.py` |

---

## 3. 测试用例设计

### 3.1 协议契约测试(面向规范)

```
测试                                  | 业务承诺
─────────────────────────────────────┼─────────────────────────────
test_spec_url_query_version_required  | 所有 /v1/* 必须接受 ?version=
test_spec_response_matches_to_dict   | 响应 JSON = EndpointSpec.to_dict()
test_spec_response_no_extra_fields   | 服务端不二次包装(无 wrapper)
test_manifest_response_byte_equal    | /v1/manifest 响应可被 PlateManifest.from_dict 还原
test_doc_response_matches_endpoint_doc | /v1/doc 响应 = EndpointDoc dict 形态
test_error_response_json_shape       | 错误响应 {error, message, ...} 形态
test_error_code_version_not_found    | 版本不存在 → 404 + VERSION_NOT_FOUND
test_error_code_service_not_found    | service 不存在 → 404 + SERVICE_NOT_FOUND
test_endpoint_path_not_found         | (method, path) 不存在 → 404 + ENDPOINT_NOT_FOUND
test_invalid_version_format_400      | version=x.y → 400 + INVALID_VERSION_FORMAT
test_etag_header_format              | ETag = "<sha256-hex>"
test_cache_control_spec_max_age      | /v1/spec/* max-age=86400
test_cache_control_doc_no_cache      | /v1/doc/* no-cache
test_x_plate_version_header          | 响应必带 X-Plate-Version
```

### 3.2 业务核心测试矩阵

| 业务承诺 | 测试函数 | 业务影响 |
|---|---|---|
| URL 路由完整 | `test_spec_url_*` 等 | SDK 实现依据 |
| 响应 schema 一致 | `test_spec_response_matches_*` | 防字段漂移 |
| 错误码语义清晰 | `test_error_*` | SDK 优雅降级依据 |
| HTTP 头约定 | `test_etag_*` / `test_cache_control_*` | 缓存层契约 |

---

## 4. 实现说明(本 PR **不**做)

**本 PR 只定协议,不做实现**。实现分布:

- **服务端(框架选型)**:Flask / FastAPI / Starlette 之一(待 PR-2.3 决定)
- **SDK 客户端**:留 PR-2.2
- **服务端代码**:留 PR-2.3(部署形态 + 真实路由)

**本 PR 的产出**:
1. 本协议文档(本文)
2. `tests/plate/test_protocol_contract.py`:协议契约测试
  - **Mock 测试**:用 `unittest.mock` 模拟 HTTP 响应,验证 SDK 解析逻辑正确
  - **服务端 stub**:`src/Plate/server/__init__.py` 空壳,只标记"待 PR-2.3 落地"

---

## 5. 收口验证

### 5.1 执行命令

```bash
# 1. 跑本 PR 协议契约测试
pytest tests/plate/test_protocol_contract.py -v

# 2. 跑 Phase 1 + Phase 2.0 全量不变量
pytest tests/plate/test_invariants.py tests/plate/test_zero_invasion.py -v

# 3. 跑全量基线(≥ 386 测试)
pytest tests/ -v
```

### 5.2 验收

| 项 | 值 |
|---|---|
| `test_protocol_contract.py` 测试数 | ≥ 12 |
| 协议路由文档 | 已落地(本文 §2.1) |
| 服务端 stub 模块存在 | `src/Plate/server/__init__.py`(空壳) |
| 全量测试 | ≥ 386 + 12 = ≥ 398 |

### 5.3 风险

| 风险 | 缓解 |
|---|---|
| 协议与实现漂移 | SDK 实现必须引用本协议文档,不允许"猜测字段名" |
| URL 编码歧义 | path 用 `:path` converter + URL-encode 标准 |
| 版本在 URL vs header 决策错 | 已定 URL(本 PR §1.2) |
| ETag 304 vs checksum 双语义 | ETag 仅用于 HTTP 缓存层,checksum 用于业务校验(双层不冲突) |

---

## 6. 与后续 Phase 的衔接

- **PR-2.2(SDK)**:严格按本协议实现客户端 fetcher / cache / resolver
- **PR-2.3(部署)**:服务端实现严格按本协议响应
- **PR-2.4(切换)**:SDK 走 `/v1/manifest/{version}` 拉 manifest,校验 checksum
- **Phase 3(MCP)**:本协议的 `/v1/spec/*` 端点直接包装成 MCP tool

**Phase 2.2 启动条件**:
- [ ] 本 PR 协议文档已签收(本文)
- [ ] `test_protocol_contract.py` 全过
- [ ] 错误码语义已统一(SDK 优雅降级依赖)