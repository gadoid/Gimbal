# Plate HTTP API 参考(M6 路由语法 · ADR 0002)

> 适用版本:`gimbal-plate` 一期落地后 + Phase β `references` 端点 · 路由语法遵循 ADR 0002 §D-D1/D-D2/D-D3/D-D5
> 最近一次端到端验证:**396/396 pytest 通过**(330 旧 + 49 新 `/full` + 17 新 `/references`) + uvicorn + curl 全部 16 处理器(14 旧 + 2 新 `/{dim}/{id}/references`) / 4 错误类 / 4 `/full` 路径 × 4 形态 / `/references` × 7 dim 均已确认。
>
> **Phase β 已落地**(ADR §后果负面 / §D-D2):
> - N2 私有字段访问债务(11 个 `# noqa: SLF001`)已全部消除:`PlateRegistry` 新增 6 个公开方法(`iter_endpoints_global` / `iter_endpoints_for_system` / `has_system` / `count_endpoints_for_service` / `system_of_service` / `try_endpoint`),所有 Index 类(EndpointIndex / ServiceIndex / SystemIndex)以及 `_resolve_system` 改走公开 API。
> - `/api/{dim}/{id}/references` 端点已上线(7 dim 全覆盖),Phase β 范围内的"系统成员关系 + dim 局部元数据"信号全部可查。Phase γ 再考虑完整反向引用图。

---

## 1. 基础约定

### 1.1 Base URL

所有路由注册在 `prefix="/api"` 下,使用 `create_app()` 工厂构造:

```python
from gimbal_plate.http.app import create_app
app = create_app()  # 默认绑定 default_registry
```

开发期启动:

```bash
python src/gimbal-plate/run_plate.py            # 常规启动
python src/gimbal-plate/run_plate.py --reload   # 监听 gimbal_plate/ 变更自动重启
```

> **Windows 注意**:`--reload` 的重启依赖 `CTRL_C_EVENT`,只在**真实控制台**下生效(uvicorn 已知问题族,见 [uvicorn#1972](https://github.com/Kludex/uvicorn/issues/1972))。在无控制台的后台 shell/IDE runner 里,重载进程会卡在等待旧 worker 退出且不再响应后续变更——此时请用真终端运行,或套一层 `winpty python run_plate.py --reload`。

或直接用 uvicorn(factory 形式,`--reload` 同样可用):

```bash
uvicorn "gimbal_plate.http.app:create_app" --factory --host 127.0.0.1 --port 8765
```

### 1.2 M6 URL 语法

ADR 0002 定义的统一语法:

| 形态 | 模板 | 说明 |
| --- | --- | --- |
| **list / dim 节点操作** | `GET /api/{dim}` <br> `POST /api/{dim}/action/{name}` | 列举 dim 全部条目;触发 dim 级别 action |
| **detail** | `GET /api/{dim}/{id}` | 取单个条目经 `view_factory` 裁剪后的**轻量**视图 |
| **list / detail · 完整契约** | `GET /api/{dim}/full` <br> `GET /api/{dim}/{id}/full` | 同上的 `full_view_factory` 版本,每个字段都返回(含 IOFieldBinding 扩展、敏感凭据等) |
| **references** | `GET /api/{dim}/{id}/references` | Phase β(ADR §D-D2):反查信号,见 [§3.9](#39-references-反查信号-phase-β)。返回 `data.item={dim,id}` + `data.references={...}`,dim 内 dim-特定信号(systems / service / module / tags / endpoint_count / kind / 等) |
| **object action** | `POST /api/{dim}/{id}/action/{name}` | 触发指定条目的 action,body 由 action 自定义 |
| **system scoped** | `GET /api/systems/{system}/{dim}` <br> `GET /api/systems/{system}/{dim}/{id}` <br> `GET /api/systems/{system}/{dim}/full` <br> `GET /api/systems/{system}/{dim}/{id}/full` <br> `POST /api/systems/{system}/{dim}/action/{name}` | 限定 system 范围的 dim 视图;`{dim}=system` 时为该 system 的子节点视图 |

> ⚠ **占位冲突**:`system` 既是 dim 也是路由前缀的一部分。当 `dim=system` 时 URL 为 `/api/systems/{system}/system/...`,FastAPI 路由注册顺序保证 `system-scoped` 路由在 dim-node 路由之前匹配。
>
> ⚠ **/full 路由注册顺序(ADR 0002 §D-D5)**:`/full` 路径必须先于 `/{dim}/{id}` 注册,否则 `/endpoint/full` 会被解析成 `dim=endpoint, id=full`。本服务 4 个 `/full` 路由的注册顺序是:
> `GET /systems/{system}/{dim}/full` → `GET /systems/{system}/{dim}/{id}/full` → `GET /{dim}/full` → `GET /{dim}/{id}/full`。

### 1.2.1 Light vs Full 视图

每个 dim 注册时同时声明两个 view factory:

| Factory | 触发端点 | 典型字段 | 设计意图 |
| --- | --- | --- | --- |
| `view_factory` | `/{dim}` · `/{dim}/{id}` · `/{dim}/action/...` | per-dim 精简字段(endpoint 11 个 / config 2 个 / resource 2 个 / scenario 4 个 / system 6 个 / service ≈8 个 / meta 全部) | 列表/默认 detail 用,默认剔除敏感字段 |
| `full_view_factory` | `/{dim}/full` · `/{dim}/{id}/full` | 全部 schema 字段(含 `endpoint.metadata.*` / `request.fields[*].enum/ui_kind/source_kind`、`Config.users[].password` / `services` / `vars`、Resource `extra.{image,config,portMapping}`、Scenario `extra.{meta,config,resource,steps}` 等) | 代码生成器、assertion builder、运维编辑器用 |

> 当 dim 未声明 `full_view_factory` 时,`/full` 端点返回 `501 admin_not_implemented`。这是 dim 主动选择的契约(只暴露 light view)。
>
> 命名规则:`*View` = light,`*DetailView` = full。例如 `EndpointView` vs `EndpointDetailView`、`ConfigView` vs `ConfigDetailView`。

### 1.3 响应信封 (Envelope)

所有处理器共用两种信封(由 `gimbal_plate.http.envelope` 构造):

成功:

```json
{
  "ok": true,
  "dim": "<dim name>",
  "data": {
    "items": [...],   // list 形态
    "total": 18,      // list 形态
    "item": {...},    // detail 形态
    "tree": {...}     // system 树形态
  }
}
```

失败:

```json
{
  "ok": false,
  "error": {
    "code": "dim_not_found",
    "message": "dim 'xxx' 未注册",
    "details": { /* 可选,结构由错误码决定 */ }
  }
}
```

`HTTP status` 与 `error.code` 的对照见 [§1.4](#14-错误码与-http-status)。

### 1.4 错误码与 HTTP status

| ErrorCode | HTTP | 含义 | 触发场景示例 |
| --- | --- | --- | --- |
| `dim_not_found` | 404 | dim 未注册 | `GET /api/foo` 但 `foo` 不在 `reg.dims` |
| `dim_item_not_found` | 404 | dim 内 id 不存在 | `GET /api/endpoint/not-exist` |
| `system_not_found` | 404 | system 不在注册表 | `GET /api/systems/no-such/system` |
| `invalid_action` | 400 | 处理器未声明该 action | `POST /api/system/action/unknown` |
| `admin_not_implemented` | 501 | 标记 reserved,等待 C2 | `POST /api/system/action/sync` |
| `registry_unavailable` | 500 | `reg.index_for(dim)` 缺失 DimSpec | 内部装配异常 |
| `internal_error` | 500 | 兜底,异常被 envelope 捕获后回填 | 处理器未处理异常 |

错误一律经 `PlateHTTPError(http_status, code, message, details?)` 抛出,由 FastAPI `exception_handler` 转换为信封并返回。

---

## 2. Dim 总览

| dim | 形态 | 视图裁剪 | 已注册 action | 一期数据 |
| --- | --- | --- | --- | --- |
| `system` | list + detail + tree + dim/action + obj/action | 全字段 | `from-service`, `register` (501), `sync` (501) | 1 条:`fin` |
| `service` | list + detail | 全字段 | — | 1 条:`fin-service`(fin 全部 endpoint 统一归属)+ 隐式 `fin.tidb-test` / `logi.mysql-svc` |
| `endpoint` | list + detail | 全字段(按 ADR 0001) | `field-defaults`, `resolve-paths`, `failed-criteria`, `find` | 18 条(由 `conftest.py` / `_register_fin_dims` 种入) |
| `config` | list + detail | **脱敏**:丢弃 `password` / `token` / `refresh_token` / `expires_at` | — | 1 条:`fin.default` |
| `meta` | list + detail | 全字段 | — | 1 条:`fin.default` |
| `resource` | list + detail | **脱敏**:丢弃 `image` / `config` / `portMapping` | — | 1 条:`fin.tidb_test` |
| `scenario` | list + detail | **裁剪**:只暴露 `scenarioId` / `name` / `systems` | — | 1 条:`sc-fin-default` |
| `strategy` | list + detail(语法 dim,§3.8) | 内省 `StrategyUnion` 出 kind 描述符 | — | 3 条 kind:extract / assign / assertion(非存储数据) |

存储型 dim(config / meta / resource / scenario)的注册模板位于 `gimbal_plate.systems.fin.*`,可作为新 system 的种子蓝本。

---

## 3. 详细接口

> 所有 body 为空时,使用 `Content-Type: application/json` 发送 `{}` 或省略 body 均可;处理器签名均为 `body: dict[str, Any] | None = None`。

### 3.1 system

#### `GET /api/system` — 列出全部 system

```http
GET /api/system HTTP/1.1
```

响应:

```json
{
  "ok": true,
  "dim": "system",
  "data": {
    "items": [{"name": "fin"}],
    "total": 1
  }
}
```

#### `GET /api/systems/{system}/system/tree` — system 节点树

```http
GET /api/systems/fin/system/tree HTTP/1.1
```

响应:

```json
{
  "ok": true,
  "dim": "system",
  "data": {
    "tree": {
      "name": "fin",
      "services": [
        {
          "name": "fin.order",
          "title": "订单服务",
          "endpoints": [
            {"id": "fin.order.order_add", "method": "POST", "path": "/api/v1/orders"},
            {"id": "fin.order.order_get",  "method": "GET",  "path": "/api/v1/orders/{order_id}"}
          ]
        }
      ]
    }
  }
}
```

`system_not_found` → 404 + `error.code="system_not_found"`。

#### `GET /api/systems/{system}/{dim}` — system-scoped 列表

`{dim}` ∈ {`service`, `endpoint`, `config`, `meta`, `resource`, `scenario`}

```http
GET /api/systems/fin/service HTTP/1.1
```

#### `POST /api/system/action/from-service` — 由 service 名反查 system

body 传 `services` 列表,每项为全限定名 `<system>.<service>`(纯命名约定解析,不做 registry 查询):

```http
POST /api/system/action/from-service
Content-Type: application/json

{"services": ["fin.fin-service", "logi.mysql-svc"]}
```

响应:

```json
{
  "ok": true,
  "dim": "system",
  "data": {
    "systems": [
      {"service": "fin.fin-service", "system": "fin"},
      {"service": "logi.mysql-svc", "system": "logi"}
    ]
  }
}
```

`"no-dot-here"`(不带点)→ 无法消歧,`system` 为空串。

#### `POST /api/system/action/register` (501)

```http
POST /api/system/action/register
```

响应(501):

```json
{
  "ok": false,
  "error": {
    "code": "admin_not_implemented",
    "message": "structure register is reserved; C2 will own this"
  }
}
```

#### `POST /api/systems/{system}/system/action/sync` (501)

```http
POST /api/systems/fin/system/action/sync
```

响应(501):`message` 含 `'fin'`,例如 `structure sync for system 'fin' is not implemented in plate; C2 is deferred to the platform backend`。

### 3.2 service

#### `GET /api/service` — 全部 service

```http
GET /api/service HTTP/1.1
```

#### `GET /api/service/{name}` — 单个 service

```http
GET /api/service/fin.order HTTP/1.1
```

响应:

```json
{
  "ok": true,
  "dim": "service",
  "data": {
    "item": {
      "name": "fin.order",
      "title": "订单服务",
      "system": "fin"
    }
  }
}
```

> ℹ 注册表中,`service` 名称本身已含 system 前缀(`fin.order`),详情字段无独立 `system` 字段(由 name 推断)。

#### `GET /api/systems/{system}/service` — system 内 service 列表

```http
GET /api/systems/fin/service HTTP/1.1
```

### 3.3 endpoint

#### `GET /api/endpoint` — 全部 endpoint,支持筛选

| Query 参数 | 含义 |
| --- | --- |
| `system` | 限定 system |
| `service` | 限定 service(fin 全部 endpoint 统一为 `fin-service`) |
| `method` | HTTP 方法大写 |
| `tag` | 命中任一 tag |
| `q` | 模糊匹配 id / path |

```http
GET /api/endpoint?service=fin-service&method=POST&q=order_add HTTP/1.1
```

响应:

```json
{
  "ok": true,
  "dim": "endpoint",
  "data": {
    "items": [
      {"id": "fin.order.order_add",          "method": "POST", "path": "/api/v1/orders", ...},
      {"id": "fin.order_entrust.order_add",  "method": "POST", "path": "/api/v1/entrusts", ...}
    ],
    "total": 2
  }
}
```

> ℹ `q=order_add` 会同时匹配 `fin.order.order_add` 与 `fin.order_entrust.order_add`。

#### `GET /api/endpoint/{id}` — 详情

```http
GET /api/endpoint/fin.order.order_add HTTP/1.1
```

`dim_item_not_found` → 404 + `error.code="dim_item_not_found"`。

#### `GET /api/endpoint/full` / `GET /api/endpoint/{id}/full` — 完整契约

走 `EndpointDetailView.from_spec`,返回 `EndpointSpec` 的全部字段(含 `metadata` / `api.*` / `responses.*.fields` 等)。Light 视图会剔除 `metadata.*` / `request.fields[*].enum/ui_kind/source_kind` 等扩展字段;`/full` 把它们全部回填,供代码生成器 / assertion builder 直接使用。

```http
GET /api/endpoint/fin.order.order_add/full HTTP/1.1
```

响应(节选):

```json
{
  "ok": true,
  "dim": "endpoint",
  "data": {
    "item": {
      "id": "fin.order.order_add",
      "system": "fin",
      "service": "fin-service",
      "name": "order_add",
      "description": "...",
      "api": {
        "service": "fin-service",
        "method": "POST",
        "path": "/api/order/order/orderAdd",
        "headers": {},
        "timeout_seconds": 30.0,
        "auth": "bearer"
      },
      "request": {
        "body_type": "json",
        "fields": [
          {
            "name": "customer_id",
            "path": "$.customer_id",
            "required": true,
            "default": null,
            "example": "320",
            "ui_kind": "text",
            "source_kind": "independent"
          }
        ]
      },
      "responses": {"200": {"status": 200, "fields": []}},
      "metadata": {"module": "order", "tags": ["happy"], "version": "1.0.0"},
      "version": "v1",
      "updated_at": "..."
    }
  }
}
```

system-scoped /full(`/api/systems/fin/endpoint/full` 与 `/api/systems/fin/endpoint/{id}/full`)与上面等价,只是先经过 `list_for_system` / `has_system` 过滤。

#### `POST /api/endpoint/{id}/action/field-defaults`

```http
POST /api/endpoint/fin.order.order_add/action/field-defaults
Content-Type: application/json

{}
```

响应:

```json
{
  "ok": true,
  "dim": "endpoint",
  "data": {
    "item": {
      "id": "fin.order.order_add",
      "defaultFields": { "requestBody": [...], "responseBody": [...] }
    }
  }
}
```

#### `POST /api/endpoint/{id}/action/resolve-paths`

```http
POST /api/endpoint/fin.order.order_add/action/resolve-paths
Content-Type: application/json

{
  "response_body_sample": {
    "code": 0,
    "data": { "order_id": "o-1", "shipping": { "method": "air" } }
  }
}
```

响应:

```json
{
  "ok": true,
  "dim": "endpoint",
  "data": {
    "item": {
      "paths": [
        "data.order_id", "data.shipping.method", "code"
      ]
    }
  }
}
```

#### `POST /api/endpoint/{id}/action/failed-criteria`

```http
POST /api/endpoint/fin.order.order_add/action/failed-criteria
Content-Type: application/json

{}
```

响应(具体 schema 由 action 实现决定,一期固定返回 `{"criteria": [...]}`):

```json
{
  "ok": true,
  "dim": "endpoint",
  "data": {
    "item": {"criteria": ["status >= 400", "response.code != 0"]}
  }
}
```

#### `POST /api/endpoint/action/find` — 由 (service, method, path) 查 id

```http
POST /api/endpoint/action/find
Content-Type: application/json

{"service": "fin-service", "method": "POST", "path": "/api/v1/orders"}
```

响应:

```json
{
  "ok": true,
  "dim": "endpoint",
  "data": {
    "item": {"id": "fin.settlement.orders_create"}
  }
}
```

> ⚠ 本 action 的索引由 `reg.dims["endpoint"].index` 提供(已修复 `idx=item` bug,见 §6)。

### 3.4 config(脱敏视图)

#### `GET /api/config`

响应(密码/token/refresh_token/expires_at 字段已被裁剪):

```json
{
  "ok": true,
  "dim": "config",
  "data": {
    "items": [
      {
        "id": "fin.default",
        "name": "fin-default",
        "host": "10.0.0.1",
        "port": 4000
      }
    ],
    "total": 1
  }
}
```

#### `GET /api/config/{id}`

```http
GET /api/config/fin.default HTTP/1.1
```

#### `GET /api/config/full` / `GET /api/config/{id}/full` — 完整契约(含凭据)

走 `ConfigDetailView.from_config`,返回 `Config` 全部字段。Light 视图只保留 `id` / `name`;`/full` 回填 `services` / `users[tester_*].password` / `time_policy` / `vars` 等运维必需字段,**含明文凭据**(比如 `users.tester_a.password`)。

```http
GET /api/config/fin.default/full HTTP/1.1
```

响应(节选):

```json
{
  "ok": true,
  "dim": "config",
  "data": {
    "item": {
      "setup": [],
      "teardown": [],
      "services": {
        "order": "https://test-api.example.com/fin/order",
        "audit": "https://test-api.example.com/fin/audit"
      },
      "users": {
        "tester_a": {
          "username": "tester_a",
          "password": "${env.TEST_USER_A_PASSWORD}",
          "token_type": "Bearer",
          "is_authenticated": false
        }
      },
      "time_policy": {"kind": "record"},
      "vars": {
        "fin_base_url": "https://test-api.example.com/fin",
        "fin_timeout_ms": 5000
      }
    }
  }
}
```

> ⚠ 凭据回填是 admin-only 形态,**不要**把 `/full` 暴露到公共网关。命名约定:`/full` 永远携带敏感字段,认证 / 鉴权由调用方在网关层做。

### 3.5 meta

#### `GET /api/meta`

#### `GET /api/meta/{id}`

无脱敏,返回全部 `Meta` 字段。

#### `GET /api/meta/full` / `GET /api/meta/{id}/full` — 完整契约

走 `MetaDetailView.from_meta`,与 light 版字段一致(本期 `Meta` 不含敏感字段),主要用于调用方统一 dim 协议(`view_factory` + `full_view_factory` 都拿到)。

```http
GET /api/meta/fin.default/full HTTP/1.1
```

### 3.6 resource(脱敏视图)

#### `GET /api/resource`

响应(裁掉 `image` / `config` / `portMapping`):

```json
{
  "ok": true,
  "dim": "resource",
  "data": {
    "items": [{"id": "fin.tidb_test", "name": "fin.tidb_test"}],
    "total": 1
  }
}
```

#### `GET /api/resource/{id}`

#### `GET /api/resource/full` / `GET /api/resource/{id}/full` — 完整契约(含 image/config/portMapping)

走 `ResourceDetailView.from_resource`,返回 `ResourceUnion` 全部字段。Light 视图只保留 `id` / `name`;`/full` 回填 `kind` 与 `extra`(`image` / `config` / `portMapping` 容器编排字段)。

```http
GET /api/resource/fin.tidb_test/full HTTP/1.1
```

响应(节选):

```json
{
  "ok": true,
  "dim": "resource",
  "data": {
    "item": {
      "name": "fin.tidb_test",
      "kind": "mock",
      "extra": {
        "image": "pingcap/tidb:v7.1",
        "config": {"region": "test"},
        "portMapping": {"4000": 4000}
      }
    }
  }
}
```

### 3.7 scenario(裁剪视图)

#### `GET /api/scenario`

响应(只暴露 `scenarioId` / `name` / `systems`):

```json
{
  "ok": true,
  "dim": "scenario",
  "data": {
    "items": [
      {
        "scenarioId": "sc-fin-default",
        "name": "sc-fin-default",
        "systems": ["fin"]
      }
    ],
    "total": 1
  }
}
```

#### `GET /api/scenario/{id}`

#### `GET /api/scenario/full` / `GET /api/scenario/{id}/full` — 完整契约

走 `ScenarioDetailView.from_scenario`,返回 `Scenario` 全部字段(`scenario_id` / `name` / `systems` / `extra.{meta,config,resource,steps}`)。Light 视图只有 4 个精简字段;`/full` 是 Phase β 引擎真正的输入契约。

```http
GET /api/scenario/sc-fin-default/full HTTP/1.1
```

响应(节选):

```json
{
  "ok": true,
  "dim": "scenario",
  "data": {
    "item": {
      "scenario_id": "sc-fin-default",
      "name": "fin-default-case",
      "systems": ["fin"],
      "extra": {
        "kind": "scenario",
        "meta": {
          "name": "fin-default-case",
          "module": "fin",
          "priority": 1,
          "tags": ["fin"],
          "version": "1.0.0",
          "system": ["fin"]
        },
        "config": {"id": "fin.default"},
        "resource": {},
        "steps": []
      }
    }
  }
}
```

#### `POST /api/scenario/action/convert` — 结构转换(dim-node action)

调用方传入一份 Scenario dict(平台组装的完整数据)和服务端目前已注册的 consumer 名(`gimbal` / `platform`),服务端先做 `Scenario.model_validate` 校验,再交给 `gimbal_plate.export.dispatch()` 路由到对应 exporter(GimbalScenarioExporter / PlatformScenarioExporter),把中性 Scenario 翻译成目标 consumer 期望的 dict。这条端点把 `export/` 模块已实现但 HTTP 层未暴露的转换能力挂到了 M6 grammar 上。

**为什么是 dim-node action(无 `{id}`)?** 转换操作的目标是**调用方传入的整份 Scenario**,不是 plate registry 里已注册的某条 scenario 记录 —— 跟 `system.action.from-service` 是同一类(对"调用方传入的入参"做转换 / 解析)。

**复用而非重写**:handler 直接调 `export.dispatch()`,不重新实现任何转换逻辑。任何在 `export/` 下加的 consumer(新增 `ConsumerRequest` + exporter 实现 + 在 `_REQUEST_REGISTRY` 注册一行)自动通过这个 HTTP 端点对外可用 —— 零 HTTP 层修改。

请求体:

```json
{
  "consumer": "gimbal",
  "scenario": { ...平台组装的 Scenario dict... },
  "endpoints": [...],     // 可选,仅 platform consumer 使用
  "sections": [...]       // 可选,仅 platform consumer 使用(Literal 校验)
}
```

- `scenario` 缺失 → **400** `invalid_action`
- `Scenario.model_validate` 失败(字段缺失 / 类型不对)→ **400** `invalid_action`,错误信息包含 pydantic 校验详情;**关键**:不让非法结构进入 dispatch
- `consumer` 未注册 → **400** `invalid_action`,错误信息会列出 `available_consumers()`
- consumer 不接受的 kwargs(如给 `gimbal` 传 `endpoints`) → **400** `invalid_action`(consumer request model 的 `extra="forbid"` 拦截)

`consumer` 缺省时默认为 `"gimbal"`。

请求示例(gimbal):

```http
POST /api/scenario/action/convert HTTP/1.1
Content-Type: application/json

{
  "consumer": "gimbal",
  "scenario": { ...完整 Scenario... }
}
```

响应:

```json
{
  "ok": true,
  "dim": "scenario",
  "data": {
    "consumer": "gimbal",
    "converted": {
      "kind": "scenario",
      "scenarioId": "...",
      ...
    }
  }
}
```

请求示例(platform,带 sections 切片):

```http
POST /api/scenario/action/convert HTTP/1.1
Content-Type: application/json

{
  "consumer": "platform",
  "scenario": { ... },
  "endpoints": [...],
  "sections": ["endpoints"]
}
```

响应 `converted` 字段会包含 `endpoints` / `navigation` / `config_summary` 等 platform 视图字段(由 `PlatformScenarioExporter.render()` 输出)。

---

### 3.8 strategy(语法 dim,非数据)

> M6 的第 8 个 dim。与上面 7 个**数据 dim** 不同:items 不是存储的数据实例,而是
> 从 `StrategyUnion`(plate schema)内省出的 kind 描述符 —— 回答"策略有哪些 kind、
> 每个 kind 有哪些字段"。策略**实例**存在 Scenario 的 `steps[].strategy` 里(scenario dim),
> 本 dim 只提供"添加策略"的结构渲染契约(平台 Canvas 策略区)。
>
> `strategy_ref` 是预埋字段(待重设计),**不在** dim 输出中。
> 无 system-scoped 变体(语法全局,不随系统变化)。

#### `GET /api/strategy`

```json
{
  "ok": true,
  "dim": "strategy",
  "data": {
    "items": [
      {"kind": "extract",   "label": "从响应提取变量", "phase": "after_request"},
      {"kind": "assign",    "label": "准备入参赋值",   "phase": "before_request"},
      {"kind": "assertion", "label": "响应断言",       "phase": "verifying"}
    ],
    "total": 3
  }
}
```

#### `GET /api/strategy/{kind}/full`

`fields` = 该 kind 的业务字段;`base_fields` = `StrategyBase` 公共字段(name / phase /
order / enabled / onFailure / timeout / tags / view_note)。字段描述符词汇表与
`IOFieldBinding` 同名同义(name / path / required / default / description / enum /
ui_kind),但**无 `source_kind`**(值来源语义对策略无意义)。

assertion 的 `operator` 字段 `enum` = 14 个 AssertOperator、`ui_kind = "select"`。

```json
{
  "ok": true,
  "dim": "strategy",
  "data": {
    "item": {
      "kind": "assertion",
      "label": "响应断言",
      "phase": "verifying",
      "fields": [
        {"name": "target",   "path": "$.target",   "required": true,  "default": null,  "description": "断言目标 (JSONPath)", "enum": null, "ui_kind": "text"},
        {"name": "operator", "path": "$.operator", "required": true,  "default": "eq", "description": "比较符", "enum": ["eq","ne","gt","gte","lt","lte","in","not_in","contains","not_contains","exists","empty","length_eq","schema"], "ui_kind": "select"}
      ],
      "base_fields": [
        {"name": "name",      "path": "$.name",      "required": false, "default": null,        "description": "策略名",   "enum": null, "ui_kind": "text"},
        {"name": "order",     "path": "$.order",     "required": false, "default": 0,           "description": "执行顺序", "enum": null, "ui_kind": "number"}
      ]
    }
  }
}
```

(fields / base_fields 示例有截断,完整字段以 `/full` 实际响应为准)

- 未知 kind → `404 dim_item_not_found`。
- 平台代理:`/api/strategy-catalog` · `/api/strategy-catalog/{kind}/full`(unwrap envelope;plate 不可达 → `502 plate_unavailable`)。

---

## 4. Python 注册 API

### 4.1 注册自定义 dim

```python
from gimbal_plate.http.grammar import DimSpec
from gimbal_plate.registry import registry

class MyIndex:
    """实现 in-memory 索引:list / get / add / has。"""
    def __init__(self): self._by_id: dict[str, MyItem] = {}
    # 协议由 grammar 内部使用:add / get / list / has

def my_view(item: MyItem) -> dict:
    return {"id": item.id, "name": item.name}

def my_action(item_id: str, *, index, request, body):
    # body: dict[str, Any] | None
    # index: 上面的 MyIndex 实例
    return {"echo": body}

registry.register_dim("custom", DimSpec(
    name="custom",
    index=MyIndex(),
    view_factory=my_view,
    actions={"echo": my_action},
))
```

随后:

- `GET /api/custom` → 列表
- `GET /api/custom/{id}` → 详情(经 `my_view`)
- `POST /api/custom/{id}/action/echo` → 触发 `my_action`

### 4.2 便捷 API(模块级)

```python
from gimbal_plate.registry import (
    register_service, register_endpoint, register_endpoints,
    list_systems, list_services, list_endpoints,
    get_endpoint, find_endpoints, reset,
)
```

### 4.3 系统种子

`fin` 系统的种子在两处独立维护(避免 conftest 与 lifespan 共享代码产生隐式耦合):

- `gimbal_plate.http.app._register_fin_dims(reg)` — 生产路径
- `tests/plate/conftest.py:fresh_registry` — 测试路径

新增 system 时,推荐在 `gimbal_plate/systems/<sys>/` 下放 4 个 `*_template()` 工厂(config/meta/resource/scenario),然后在两处分别调用。

---

### 3.9 references(反查信号,Phase β)

> **ADR 定位**:ADR 0002 §D-D2 决策为"不要,留 Phase β"。本节是该决策的落地版。
>
> **Phase β 诚实范围**:不做完整反向图,而是把每个 dim 已经能从 registry 数据中可靠回答的"谁持有 / 谁属于"信号(`systems` + dim 局部元数据)集中返回。完整反向边(`scenarios_referenced_by` 等)留 Phase γ。

**端点**:`GET /api/{dim}/{id}/references`

**envelope**(以 endpoint 为例,实际字段因 dim 而异):

```json
{
  "ok": true,
  "dim": "endpoint",
  "data": {
    "item": { "dim": "endpoint", "id": "fin.order.order_add" },
    "references": {
      "dim": "endpoint",
      "systems": ["fin"],
      "service": "fin-service",
      "module": "fin",
      "tags": ["fin"]
    }
  }
}
```

**7 个 dim 的 references 字段差异**:

| Dim | 必含 | dim-特定信号 |
| --- | --- | --- |
| `endpoint` | `systems` | `service`, `module`, `tags` |
| `service`  | `systems` | `endpoint_count` |
| `system`   | `systems (self)` | `endpoint_count`, `service_count`(容器视图,无反向图) |
| `config`   | `systems (从 `{system}.{name}` id 前缀解析)` | `service_count` |
| `meta`     | `systems (从 `meta.system` 列表)` | — |
| `resource` | `systems (从 id 前缀)` | `kind` |
| `scenario` | `systems` | `scenarios_referenced_by = []`(Phase γ 候选) |

**错误码**:

| 触发条件 | HTTP | `error.code` |
| --- | --- | --- |
| dim 不存在 | 404 | `dim_not_found` |
| dim 内 id 不存在 | 404 | `dim_item_not_found` |

**安全**:`references` payload 永远不泄漏敏感字段(已用 `test_references_payload_never_includes_secret_like_keys` 单元测试守卫 — `password / users / services` 黑名单)。`data.item` 严格 `{dim, id}` 两字段,不暴露 dim 的完整载荷。

---

## 5. 路由表(注册顺序敏感)

> 注册顺序决定匹配优先级:系统级 → `/full` → dim 级 action → dim 全局 `/dim/{id}`。

| 顺序 | Method | Path | 处理器 |
| --- | --- | --- | --- |
| 1 | POST | `/api/system/action/from-service` | `action_system_from_service` |
| 2 | POST | `/api/system/action/register` | `action_system_register` (501) |
| 3 | POST | `/api/systems/{system}/system/action/sync` | `action_system_sync` (501) |
| 4 | GET  | `/api/systems/{system}/system/tree` | `system_tree` |
| 5 | GET  | `/api/systems/{system}/{dim}/full` | `list_full_dim_for_system` |
| 6 | GET  | `/api/systems/{system}/{dim}/{id}/full` | `get_full_dim_item_for_system` |
| 7 | GET  | `/api/systems/{system}/{dim}` | `list_dim_for_system` |
| 8 | GET  | `/api/systems/{system}/{dim}/{id}` | `detail_dim_for_system` |
| 9 | POST | `/api/systems/{system}/{dim}/action/{name}` | `run_dim_action_for_system` |
| 10 | POST | `/api/systems/{system}/{dim}/{id}/action/{name}` | `run_dim_action_for_object_for_system` |
| 11 | POST | `/api/{dim}/action/{name}` | `run_dim_action_global` |
| 12 | GET  | `/api/{dim}/full` | `list_full_dim_global` |
| 13 | GET  | `/api/{dim}/{id}/full` | `get_full_dim_item_global` |
| 13a | GET  | `/api/{dim}/{id}/references` | `get_dim_item_references` (Phase β,ADR §D-D2) |
| 14 | GET  | `/api/{dim}` | `list_dim_global` |
| 15 | GET  | `/api/{dim}/{id}` | `detail_dim` |
| 16 | POST | `/api/{dim}/{id}/action/{name}` | `run_dim_action_for_object` |

> 顺序 1 / 2 / 3 必须早于顺序 14 / 15,否则会被 `/{dim}/{id}` 之类的全局路由吞掉(`system` 与 `systems` 的复数差异在 FastAPI 路由表里不会冲突,但具体 dim 名若与 `systems` 重叠则需要前置)。
>
> 顺序 5 / 6 / 12 / 13(`/full`)必须分别早于顺序 8(`/systems/{system}/{dim}/{id}`)和顺序 15(`/{dim}/{id}`),否则 `/endpoint/full` 会被解析成 `dim=endpoint, id=full` 触发 404 `dim_item_not_found`。
> 顺序 13a(`/references`)同样早于顺序 15,确保 `/{dim}/{id}/references` 不会被 `/{dim}/{id}` 吞掉。

---

## 6. 失效 / 不再支持的 URL(迁移提示)

以下 URL 在 M5 之前存在,M6 路由语法后已 404 确认:

| 旧 URL | 替代 |
| --- | --- |
| `GET /api/systems` | `GET /api/system` |
| `GET /api/systems/fin/tree` | `GET /api/systems/fin/system/tree` |
| `GET /api/endpoints` / `/api/endpoints/{id}` | `GET /api/endpoint` / `/api/endpoint/{id}` |
| `GET /api/endpoints/{id}/field-defaults` | `POST /api/endpoint/{id}/action/field-defaults` |
| `GET /api/endpoints/{id}/resolve-paths` | `POST /api/endpoint/{id}/action/resolve-paths` |
| `GET /api/endpoints/{id}/failed-criteria` | `POST /api/endpoint/{id}/action/failed-criteria` |
| `POST /api/resolve/system-from-service` | `POST /api/system/action/from-service` |
| `POST /api/systems` (register) | `POST /api/system/action/register` (501) |
| `POST /api/systems/fin/sync` | `POST /api/systems/fin/system/action/sync` (501) |

> 端到端验证已用 curl 全部触发并确认 404/501,无 500 漏出。

---

## 7. 测试覆盖

- **pytest**:`python -m pytest tests/plate -v` → **396 passed**, 0 failed
  - 330 历史用例(9 个 M6 测试文件 + 其它 schema/registry 用例)
  - 49 新增 `/full` 单元用例(5 个 `/full` 测试文件)
  - 17 新增 `/references` 单元用例(1 个 `/references` 测试文件,7 dim × happy + 7 dim × unknown id + 1 unknown dim + 2 envelope)
- **uvicorn + curl**:`http://127.0.0.1:8765/api/...` E2E 30 用例全部 PASS:
  - 13 light 路径(系统/dim 列表/详情/actions/错误码)
  - 4 全局 `/full` 路径(endpoint / config / resource / scenario)
  - 4 system-scoped `/full` 路径(endpoint / config / resource / scenario)
  - 7 `/references` 路径(7 dim 全覆盖)
  - 1 sanity(`/healthz`)
- 15 个 M6 测试文件覆盖:
  - **light / 动作**:
    `test_http_systems.py` / `test_http_tree.py`
    `test_http_endpoints_list.py` / `test_http_endpoint_detail.py`
    `test_http_field_defaults.py` / `test_http_resolve_paths.py` / `test_http_failed_resolved.py`
    `test_http_system_from_service.py` / `test_http_admin_not_implemented.py`
    `test_http_envelope.py` / `test_http_health.py`
  - **`/full` 路径(新增)**:
    `test_http_full_endpoint.py` (8 用例) — `EndpointDetailView` 完整契约 + light 对照
    `test_http_full_config.py` (10 用例) — `ConfigDetailView` 含 `users[].password` / `extra`
    `test_http_full_resource.py` (8 用例) — `ResourceDetailView` 含 `extra.{image,config,portMapping}`
    `test_http_full_scenario.py` (8 用例) — `ScenarioDetailView` 含 `extra.{meta,config,resource,steps}`
    `test_http_full_system_scoped.py` (15 用例) — `_item_belongs_to_system` 系统归属校验
  - **`/references` 路径(Phase β 新增)**:
    `test_http_references.py` (17 用例) — 7 dim × 200 + 7 dim × unknown id 404 + 1 unknown dim 404 + 2 envelope 校验

`/full` 路径覆盖:

- 7 个 dim 全部接入(`full_view_factory` × 7),4 路径形态 × 4 dim = 16 路由 + 2 admin handler 全部验证:
  - `GET /api/{dim}/full` → 200,返回 `items[]` 的 `*DetailView` 形态
  - `GET /api/{dim}/{id}/full` → 200,返回 `item` 的 `*DetailView` 形态
  - `GET /api/systems/{system}/{dim}/full` → 200,经 `list_for_system` 过滤
  - `GET /api/systems/{system}/{dim}/{id}/full` → 200,经 `_item_belongs_to_system` 校验
- 验证 4 类关键差异:
  - **endpoint `/full`**:回填 `metadata.*` / `request.fields[*].enum/ui_kind/source_kind`
  - **config `/full`**:回填 `services` / `users[].password` / `vars`(light 已被裁剪)
  - **resource `/full`**:回填 `extra.{image,config,portMapping}`(light 只剩 `id/name`)
  - **scenario `/full`**:回填 `extra.{meta,config,resource,steps}`(light 只剩 4 个精简字段)
- 路由顺序覆盖:`/full` 路径在 `/{dim}/{id}` 之前注册,`/api/{dim}/full` 不会被解析为 `id=full`(已 E2E + 单元双向验证)。

`/references` 路径覆盖(Phase β, ADR §D-D2):

- 7 dim × happy path → 200,envelope `{ok, dim, data:{item:{dim,id}, references:{...}}}`:
  - endpoint → `systems / service / module / tags`
  - service  → `systems / endpoint_count`
  - system   → `systems (self) / endpoint_count / service_count`
  - config   → `systems (从 `{system}.{name}` id 前缀解析) / service_count`
  - meta     → `systems (从 `meta.system` 列表)`
  - resource → `systems (从 id 前缀) / kind`
  - scenario → `systems / scenarios_referenced_by=[]` (Phase γ 候选)
- 7 dim × unknown id → 404 `dim_item_not_found`
- 1 unknown dim → 404 `dim_not_found`
- envelope 校验:`data.item` 严格 `{dim, id}`(不暴露 dim 完整载荷),`references` 永远不泄漏敏感字段(`password / users / services`)
- Phase γ 候选:扫描 `scenario.config` / `scenario.resource` 引用,自动填充 `scenarios_referenced_by`。Phase β 范围内**故意不实现**全图(ADR §后果负面 / §D-D2 决策)
- 401/501 行为:dim 未声明 `full_view_factory` 时返回 501 `admin_not_implemented`(本期 7 个 dim 全部已声明,故只单元测试覆盖,未走 E2E)。
- `_item_belongs_to_system` 覆盖:`test_http_full_system_scoped.py` 验证 4 dim × 3 形态(full/light/wrong-system)= 15 用例;修复了 light 路径上 `Config` / `Mock` / `Scenario` Pydantic 模型无 `.id` 属性的隐性 bug。

未覆盖(Phase β 候选):跨 dim 复合查询、并发注册、DimSpec 协议文档化、OpenAPI schema baseline、`/full` 的 501 路径 E2E。

---

## 8. 已知限制 / Phase β 计划

| 项目 | 状态 | 备注 |
| --- | --- | --- |
| `action_endpoint_find` 索引来源 | ✅ 已修复 | 之前错误地 `idx = item`,现已改为 `idx = reg.dims["endpoint"].index` |
| `*DetailView` / `/full` 装配 | ✅ 已补齐 | 7 个 dim 全部声明 `full_view_factory`,4 路径(`/full` / `/{id}/full` / system-scoped × 2)全部接通;`tests/plate/conftest.py` 已同步注入 7 个 `*DetailView` factory,保证单测覆盖与生产装配同源 |
| system-scoped `/{id}/full` 装配 | ✅ 已补齐 | 5 个 dim(endpoint / config / resource / scenario / service)全部接通。共用 `_item_belongs_to_system` 助手,基于对象身份(`is`)作 system-membership 判定 |
| system-scoped `/{id}` 配置 / resource / scenario 系统校验 | ✅ 已修复 | 之前 `getattr(it, "id") or it.get("id")` 在 Pydantic 模型上抛 `AttributeError`(config / resource / scenario 缺少 `.id` 属性);现统一通过 `_item_belongs_to_system(spec, item, id, system)` 处理 |
| **N2:handler 私有字段访问债务** | ✅ **Phase β 已闭合** | endpoint 维度 11 个 + service 维度 3 个私有属性访问全部消除,合计 ~14 个访问点。`PlateRegistry` 新增 10 个公开方法:`iter_endpoints_global` / `iter_endpoints_for_system` / `has_system` / `count_endpoints_for_service` / `system_of_service` / `try_endpoint`(endpoint 系列),`iter_services_global` / `get_service` / `has_service` / `iter_services_for_system`(service 系列)。EndpointIndex / ServiceIndex / SystemIndex 三个 Index 类以及 routes_grammar.py 的 `_resolve_system` 全部改走公开 API,Registry 内部存储策略(`_index` / `_services` dict)再次被封装 |
| **`/references` 端点** | ✅ **Phase β 已落地** | ADR 0002 §D-D2 决策为"留 Phase β",现已上线。`GET /api/{dim}/{id}/references` × 7 dim,17 个单测 + 7 dim E2E 全 PASS。Phase β 范围内提供 `systems` + dim 局部元数据(`service / module / tags / endpoint_count / kind` 等);**不**实现完整反向引用图(`scenarios_referenced_by` 始终为空),留给 Phase γ |
| **`POST /api/scenario/action/convert` 结构转换端点** | ✅ **Phase β 已落地** | 把 `export/` 模块已实现的 `dispatch(consumer, scenario, **kwargs)` 声明式入口挂到 M6 grammar。dim-node action(无 `{id}`,调用方传整份 Scenario);handler 内部先 `Scenario.model_validate`(拦截非法结构 → 400)再 `export.dispatch()`(复用现成 GimbalScenarioExporter / PlatformScenarioExporter,零重写)。`available_consumers` 现在是 `['gimbal', 'platform']`;后续新增 consumer 只需在 `export/` 下加 `ConsumerRequest` + exporter + 在 `_REQUEST_REGISTRY` 挂一行,HTTP 层零修改自动可用。15 个单测覆盖正常路径 + 4 类 400(缺 scenario / schema 校验失败 / 未知 consumer / kwargs 越界) |
| **API 合并决策(`dims["endpoint"]` vs `PlateRegistry.get_endpoint()`)** | 🟡 **保持并存(ADR 显式承认)** | Phase β 决策:**保留两套 API**,用注释明示过渡状态(`registry.list_endpoints` / `registry.get_endpoint` 上有 ADR 引用注释);统一合并留到 Phase γ(届时 `dims["endpoint"]` 已 production 路径且稳定,合并成本低) |
| Config 脱敏边界 | ✅ 已确认 | 验证 `password` / `token` / `refresh_token` / `expires_at` 不会经 `ConfigView.from_spec` 漏出 |
| Resource 脱敏边界 | ✅ 已确认 | `image` / `config` / `portMapping` 被丢弃 |
| Scenario 裁剪边界 | ✅ 已确认 | 仅暴露 `scenarioId` / `name` / `systems` |
| 线程安全 | ❌ 一期不做 | `PlateRegistry` 不加锁;`create_app()` 在 lifespan 启动时一次性种入 |
| 持久化 | ❌ 一期不做 | 重启即丢;`reset()` 仅供测试 |
| 异步注册 | ❌ 一期不做 | 同步 API 即可覆盖一期 fixture |
| OpenAPI snapshot | 🟡 待定 | 一期无自动 baseline;Phase γ 加入 `tests/openapi/*.json` 锁定 |
| DimSpec 协议类型化 | 🟡 待定 | 现为 `Any` 规避导入循环;Phase γ 抽出 `Protocol` 替代 |
| Auth layer(Q3) | ❌ 一期不做 | 所有端点目前裸奔;Phase γ 接入 Bearer/JWT |
| Producer 机制(ADR §D-D4) | ✅ **Phase β 已落地(提前)** | 共享入口 `gimbal_plate.systems.fin.dimensions.register_fin_dims()` 同时被 `app._lifespan` 和 `tests/plate/conftest.py:fresh_registry` 调用;`test_http_failed_resolved.py` / `test_http_field_defaults.py` 也已迁移。生产 / 测试双路径不再各自维护 dim 注册代码,drift 不可能再发生。ADR §D-D4 原计划 Phase γ 才迁到 `systems/<sys>/__init__.py`,但 lifespan 入口已足够干净 — 留 Phase γ 把入口下沉到 `__init__.py` 即可,接口形状不再变 |
| 错误码 i18n | ❌ 不做 | `message` 统一英文,内部消费 |

---

## 9. 相关文档

- ADR 0002: [Plate HTTP 路由语法](./adr/0002-plate-http-routing-grammar.md)
- ADR 0001: [Endpoint ID 系统前缀](./adr/0001-endpoint-id-system-prefix.md)
- Schema 总览: [schema.md](./schema.md)
- 模块索引: [README.md](./README.md)
