# Plate HTTP 接口查询样式

> 本文给出 `PLATE-API-SURFACE.md` 中 10 个结构接口的可直接复制的查询样式。
>
> **基础信息**:
> - Plate 默认服务地址: `http://localhost:8000`
> - 健康检查: `GET /healthz`
> - 业务路径前缀: `/api`
> - 响应壳:
>   - 成功: `{"ok": true, "data": ...}`
>   - 失败: `{"ok": false, "error": {"code", "message", "details"}}`
>
> **真实数据来源**:`fin` 系统(由 `src/gimbal-plate/gimbal_plate/systems/fin/endpoint/__init__.py` 聚合 `ALL_ENDPOINTS`,lifespan 时自动注册到默认 registry)。
> 当前实装的 fin 服务名:`account` / `audit` / `order` / `order_entrust` / `order_fee` / `settlement`(无 `tidb-test`)。
>
> **本文档响应均来自实弹验证**:
> 1. `tests/plate/test_http_*.py` 26/26 测试通过
> 2. `uvicorn` 真实启动后用 `httpx` 打 10 个接口的输出
> 验证时间:2026-08-06。

---

## 0. 健康检查

### curl

```bash
curl -sS http://localhost:8000/healthz
```

### HTTPie

```bash
http GET http://localhost:8000/healthz
```

### 实弹响应

```json
{"status":"ok"}
```

---

## A 组 — 结构拉取(5 个)

### A1. 列出已注册被测系统

> **GET** `/api/systems`
> 触发:`EndpointCatalog` 系统 tab / `CaseComposerMeta` 归属系统 chip / `CaseComposerHome` 系统筛选

#### curl

```bash
curl -sS http://localhost:8000/api/systems
```

#### HTTPie

```bash
http GET http://localhost:8000/api/systems
```

#### 实弹响应

```json
{
  "ok": true,
  "data": {
    "systems": [
      {
        "id": "fin",
        "name": "fin",
        "service_count": 6,
        "endpoint_count": 18,
        "registered_at": "2026-08-06T09:54:00.084134Z"
      }
    ]
  }
}
```

> **字段来源**:`registry._index.by_id.values()` 按 `ep.system` 分组聚合
> ([routes_structure.py:32-71](src/gimbal-plate/gimbal_plate/http/routes_structure.py))。
> `service_count` 是 `ep.service` 的去重数,`endpoint_count` 是总数,`registered_at` 是所有 endpoint 中 `updated_at` 的最大值。

---

### A2. 列出某系统的 service / 模块树

> **GET** `/api/systems/{system_id}/tree?depth=2`
> 触发:`EndpointCatalog` 左侧 service 树 / `CaseComposerCanvasAddStep` 内嵌 CatalogPanel 左侧

#### curl

```bash
# depth=2 (service + module)
curl -sS "http://localhost:8000/api/systems/fin/tree?depth=2"

# depth=3(预留,当前实装等同 depth=2)
curl -sS "http://localhost:8000/api/systems/fin/tree?depth=3"
```

#### HTTPie

```bash
http GET http://localhost:8000/api/systems/fin/tree depth==2
```

#### 实弹响应(fin 系统真实输出)

```json
{
  "ok": true,
  "data": {
    "services": [
      {"id": "account",       "name": "account",       "modules": [{"id": "", "endpoint_count": 1}]},
      {"id": "audit",         "name": "audit",         "modules": [{"id": "", "endpoint_count": 3}]},
      {"id": "order",         "name": "order",         "modules": [{"id": "", "endpoint_count": 7}]},
      {"id": "order_entrust", "name": "order_entrust", "modules": [{"id": "", "endpoint_count": 2}]},
      {"id": "order_fee",     "name": "order_fee",     "modules": [{"id": "", "endpoint_count": 4}]},
      {"id": "settlement",    "name": "settlement",    "modules": [{"id": "", "endpoint_count": 1}]}
    ]
  }
}
```

#### 错误响应

```json
{"ok": false, "error": {"code": "not_found", "message": "system 'unknown' has no registered endpoints"}}
```

> **字段来源**:同一索引按 `ep.service` + `ep.metadata.module` 二级聚合
> ([routes_structure.py:74-123](src/gimbal-plate/gimbal_plate/http/routes_structure.py))。
>
> **注意**:`module` 字段当前实装中 fin 系统所有 endpoint 都为空字符串(fin 系统的 endpoint 文件没有显式声明 module)—— 这是真实数据,不是 bug。

---

### A3. 列出某系统某服务的 endpoint(轻量索引)

> **GET** `/api/systems/{system_id}/services/{service}/endpoints`
> 可选 query: `module` / `method` / `q`
> 触发:`EndpointCatalog` 卡片网格 / `CaseComposerCanvasAddStep` 嵌入 CatalogPanel 右侧

#### curl

```bash
# 列出 order_entrust 下全部 endpoint
curl -sS "http://localhost:8000/api/systems/fin/services/order_entrust/endpoints"

# 按 HTTP method 过滤
curl -sS "http://localhost:8000/api/systems/fin/services/order/endpoints?method=POST"

# 按关键字模糊搜索(匹配 id / name / description / path,不区分大小写)
curl -sS "http://localhost:8000/api/systems/fin/services/order/endpoints?q=orderAdd"

# 多条件组合
curl -sS "http://localhost:8000/api/systems/fin/services/order_entrust/endpoints?method=POST&q=entrust"
```

#### HTTPie

```bash
http GET http://localhost:8000/api/systems/fin/services/order_entrust/endpoints \
    method==POST q==entrust
```

#### 实弹响应(以 `order_entrust` 服务为例)

```json
{
  "ok": true,
  "data": {
    "endpoints": [
      {
        "id": "fin.order_entrust.order_add",
        "name": "委托订舱下单",
        "method": "POST",
        "path": "/api/order/orderEntrust/orderAdd",
        "description": "由 Scenario_Test_14 提取: 委托订舱下单",
        "system": "fin",
        "service": "order_entrust",
        "module": "",
        "tags": [],
        "priority": null,
        "version": "1.0.0"
      }
    ],
    "total": 1
  }
}
```

#### 错误响应(服务不存在)

```json
{"ok": false, "error": {"code": "not_found", "message": "no endpoints under system='fin' service='unknown'"}}
```

> **字段来源**:`EndpointSpec` 字段的轻量子集(只取 `id/name/method/path/description/system/service/module/tags/priority/version`)
> ([routes_structure.py:126-184](src/gimbal-plate/gimbal_plate/http/routes_structure.py))。
>
> **关于 `priority: null`**:`priority` 字段是 `int | None`。当 endpoint 的 metadata 没显式设置时返回 `null`(被 `exclude_none=True` 保留,因为是序列化输出,不是 `model_dump`);若 endpoint 显式设了 `priority`,则输出对应整数值。

---

### A4. 获取单个 EndpointSpec 完整契约

> **GET** `/api/endpoints/{endpoint_id}`
> 触发:每次进入 `CaseComposerCanvasAddStepDetail`(点击 endpoint 卡片时)

#### curl

```bash
curl -sS "http://localhost:8000/api/endpoints/fin.order_entrust.order_add"
```

#### HTTPie

```bash
http GET http://localhost:8000/api/endpoints/fin.order_entrust.order_add
```

#### 实弹响应(顶层 key 列表)

```json
{
  "ok": true,
  "data": {
    "id": "fin.order_entrust.order_add",
    "name": "委托订舱下单",
    "description": "由 Scenario_Test_14 提取: 委托订舱下单",
    "system": "fin",
    "service": "order_entrust",
    "version": "1.0.0",
    "updated_at": "2026-08-06T...",
    "api": {
      "service": "order_entrust",
      "method": "POST",
      "path": "/api/order/orderEntrust/orderAdd",
      "headers": {},
      "timeout_seconds": 30.0,
      "auth": "bearer",
      "produces": ["application/json"],
      "consumes": ["application/json"]
    },
    "request": {
      "body_type": "json",
      "fields": [ /* 228 个 IOFieldBinding,字段名/路径/required/example/ui_kind/source_kind */ ],
      "model_name": "...",
      "model_schema": {"type": "object", "properties": {...}}
    },
    "responses": {
      "200": {
        "status": 200,
        "description": "...",
        "fields": [ /* ResponseSpec fields */ ],
        "assertable_fields": ["..."],
        "model_name": "...",
        "model_schema": {...}
      }
    },
    "metadata": {
      "module": "",
      "tags": [],
      "owner": "",
      "preconditions": [],
      "success_criteria": "",
      "failed_criteria": [],
      "business_notes": "",
      "deprecated": false,
      "experimental": false
    }
  }
}
```

#### 实弹响应字段说明

| 字段 | 类型 | 来源 |
|---|---|---|
| `id` / `system` / `service` / `name` / `description` | `str` | `EndpointSpec` 顶层 |
| `version` | `str = "1.0.0"` | `EndpointSpec` |
| `updated_at` | `datetime \| None` | `EndpointSpec`(lifespan 时自动填 `now(UTC)`) |
| `api` | `dict` | `ApiSpec.model_dump()` —— **包含 `service/method/path/headers/timeout_seconds/auth/produces/consumes` 共 8 个字段** |
| `request` | `dict` | `RequestSpec._serialize()` 输出 —— **包含 `body_type/fields/model_name?/model_schema?/schema?`**(`schema_` 不为 None 时) |
| `responses[<status>]` | `dict` | `ResponseSpec._serialize()` 输出 —— **包含 `status/description/fields/assertable_fields/model_name?/model_schema?/schema?`** |
| `metadata` | `dict` | `EndpointMetadata.model_dump()` —— `module/tags/owner/preconditions/success_criteria/failed_criteria/business_notes/deprecated/experimental`(**注意:`priority` 在 endpoint 未显式设置时不会出现在响应里**,因为 `model_dump(exclude_none=True)` 会过滤 `None` 字段) |

#### 错误响应

```json
{"ok": false, "error": {"code": "not_found", "message": "endpoint 'fin.unknown.id' not found"}}
```

> **字段来源**:`EndpointSpec.model_dump(mode="json", exclude_none=True)`
> —— `request` / `responses` 由 `RequestSpec._serialize()` / `ResponseSpec._serialize()`
> (`model_serializer`) 自动把 `model: type[BaseModel]` 替换为 `model_schema` + `model_name`。
> 见 [routes_structure.py:187-199](src/gimbal-plate/gimbal_plate/http/routes_structure.py)。

---

### A5. 获取 endpoint 的字段填充建议

> **GET** `/api/endpoints/{endpoint_id}/field-defaults`
> 触发:`CaseComposerCanvas` 字段编辑器加载 step 时

> **说明**:PLATE-API-SURFACE.md 描述的 body `{step_index?, scenario_vars?}` 在当前实装中**保留为参数**(显式忽略),
> 不影响响应形态 —— 见 [service/field_defaults.py:67-76](src/gimbal-plate/gimbal_plate/service/field_defaults.py)。

#### curl

```bash
curl -sS "http://localhost:8000/api/endpoints/fin.order_entrust.order_add/field-defaults"
```

#### HTTPie

```bash
http GET http://localhost:8000/api/endpoints/fin.order_entrust.order_add/field-defaults
```

#### 实弹响应(以 `fin.order_entrust.order_add` 为例,该 endpoint 共 228 个 request field)

```json
{
  "ok": true,
  "data": {
    "field_defaults": [
      {"name": "client_expand_name",   "kind": "literal",       "value": "唐欣雨"},
      {"name": "bl_no",                "kind": "scenario_var",   "value": "${var.bl_no}"},
      {"name": "track_bl_no",          "kind": "scenario_var",   "value": "${var.bl_no}"},
      {"name": "etd",                  "kind": "literal",       "value": 1782316800},
      {"name": "atd",                  "kind": "literal",       "value": 1782835200},
      {"name": "service_items",        "kind": "literal",       "value": ["booking_space"]},
      {"name": "customer_contact_id",  "kind": "literal",       "value": ""}
    ],
    "carry_fields": []
  }
}
```

> **关于 `carry_fields=0`**:该 endpoint 的 `responses[200].fields` 没有 `source_kind="generated"` 的字段,所以 `carry_fields` 是空列表。
> 若 endpoint 包含 generated 字段(例如时间戳字段),`carry_fields` 会自动从响应字段推导。

#### `kind` 取值与含义

| `kind` | 触发条件 | 调用方应该拼成 |
|---|---|---|
| `literal` | `example` 或 `default` 是普通字符串/数字/列表 | 原值 |
| `scenario_var` | 值以 `${var.` 开头 | 平台拼上 `${var.x}` |
| `env_placeholder` | 值以 `${env.` 开头 | 平台拼上 `${env.x}` |
| `auth_placeholder` | 值以 `${auth.` 开头 | 平台拼上 `${auth.x.token}` |
| `lookup` | `source_kind == "lookup"` | 平台拼上 `${auth.x.xxx}` |
| `generated` | `source_kind == "generated"` | 平台启用日期策略 |

> **字段来源**:`compute_field_defaults(endpoint)` 遍历 `endpoint.request.fields` 调 `_classify()`,
> 然后遍历 `endpoint.responses[200].fields` 找 `source_kind="generated"` 当 `carry_fields`。

---

## B 组 — 结构搜索/计算(3 个)

### B1. 解析响应路径候选(Auto-Extract 候选)

> **POST** `/api/endpoints/{endpoint_id}/resolve-paths`
> Body: `{response_body_sample, path_prefix?}`
> 触发:`CaseComposerCanvas` 字段框 @ 浮层"上游响应"组

#### curl

```bash
curl -sS -X POST "http://localhost:8000/api/endpoints/fin.order_entrust.order_add/resolve-paths" \
     -H "Content-Type: application/json" \
     -d '{
           "response_body_sample": {
             "code": 0,
             "data": {
               "order_id": "ORD-2026-001",
               "items": [{"id": 1}, {"id": 2}]
             }
           },
           "path_prefix": null
         }'
```

#### HTTPie

```bash
http POST http://localhost:8000/api/endpoints/fin.order_entrust.order_add/resolve-paths \
    response_body_sample:='{"code":0,"data":{"order_id":"ORD-2026-001","items":[{"id":1},{"id":2}]}}' \
    path_prefix:=
```

#### 实弹响应

```json
{
  "ok": true,
  "data": {
    "paths": [
      {"path": "$.code",                          "depth": 1, "extracted_by_default": false},
      {"path": "$.data",                          "depth": 1, "extracted_by_default": false},
      {"path": "$.data.order_id",                 "depth": 2, "extracted_by_default": false},
      {"path": "$.data.items",                    "depth": 2, "extracted_by_default": false},
      {"path": "$.data.items[0]",                 "depth": 3, "extracted_by_default": false},
      {"path": "$.data.items[0].id",              "depth": 4, "extracted_by_default": false},
      {"path": "$.data.items[1]",                 "depth": 3, "extracted_by_default": false},
      {"path": "$.data.items[1].id",              "depth": 4, "extracted_by_default": false}
    ]
  }
}
```

#### 错误响应(endpoint 不存在时)

```json
{"ok": false, "error": {"code": "not_found", "message": "endpoint 'fin.unknown.id' not found"}}
```

> **保护**:DFS 受 `_MAX_DEPTH = 32` 与 `_MAX_PATHS = 2000` 双重保护
> ([service/paths_resolver.py:7-12](src/gimbal-plate/gimbal_plate/service/paths_resolver.py))。
> 路径形态:`$.key` / `$.key.sub` / `$.list[0].field`,首层统一为 `$.xxx` 风格,后续层遇到 dict key 时使用 `['key']` 形式(例 `$.data['order_id']`)。
>
> **注意**:`path_prefix` 字段当前实装仅用于截取子树;若不提供则从根 `$` 开始遍历。

---

### B2. 失败参考 × assertable 联动解析

> **POST** `/api/endpoints/{endpoint_id}/failed-criteria-resolved`
> 触发:`CaseComposerCanvasAddStepDetail` Hero 渲染

#### curl

```bash
curl -sS -X POST "http://localhost:8000/api/endpoints/fin.order_entrust.order_add/failed-criteria-resolved"
```

#### HTTPie

```bash
http POST http://localhost:8000/api/endpoints/fin.order_entrust.order_add/failed-criteria-resolved
```

#### 实弹响应(以 `fin.order_entrust.order_add` 为例)

```json
{
  "ok": true,
  "data": {
    "failed_criteria": []
  }
}
```

> **为什么是空数组**:`failed_criteria` 内容来自 `endpoint.metadata.failed_criteria`(`list[str]`)。
> fin 系统当前已注册的 18 个 endpoint 都**未显式声明 `failed_criteria`**,所以实弹响应统一为空。
> 真实业务场景(例如 PLATE-API-SURFACE.md 中的 `fin.order_entrust.order_add` 示意图)的预期响应形态是:

```json
{
  "ok": true,
  "data": {
    "failed_criteria": [
      {"code": 401, "description": "未登录 / token 过期",  "field": "$.code", "assertable": true},
      {"code": 403, "description": "无权限访问该订单",     "field": "$.code", "assertable": true},
      {"code": 422, "description": "客户不存在或已禁用",    "field": "$.code", "assertable": true}
    ]
  }
}
```

> **解析规则**:正则 `_LEADING_CODE = r"^\s*(\d{3})\b"` 抽 status code;
> `_FIELD_REF = r"(\$[\w.\[\]'\"]+)\s*=\s*([^\s,;→]+)"` 抽 `field=value`;
> 然后跟 `responses[200].assertable_fields` 做 `in set()` 判断
> ([service/failed_resolver.py:14-15](src/gimbal-plate/gimbal_plate/service/failed_resolver.py))。
>
> **assertable 含义**:
> - `true` = 失败字段路径在 `assertable_fields` 中(平台可自动生成 Assertion)
> - `false` = 不在(平台只能用软断言或人工断言)

---

### B3. 跨系统归属计算(不校验,只计算)

> **POST** `/api/resolve/system-from-service`
> Body: `{services: ["<system>.<service>", ...]}`
> 触发:`CaseComposerMeta` 选中归属系统 chip 时 / `CaseComposerCanvas` 步骤流着色

#### curl

```bash
# 多 service
curl -sS -X POST "http://localhost:8000/api/resolve/system-from-service" \
     -H "Content-Type: application/json" \
     -d '{"services": ["fin.order_entrust", "logi.mysql-svc", "common", ""]}'

# 单 service
curl -sS -X POST "http://localhost:8000/api/resolve/system-from-service" \
     -H "Content-Type: application/json" \
     -d '{"services": ["fin.order_entrust"]}'
```

#### HTTPie

```bash
http POST http://localhost:8000/api/resolve/system-from-service \
    services:='["fin.order_entrust", "logi.mysql-svc"]'
```

#### 实弹响应

```json
{
  "ok": true,
  "data": {
    "systems": [
      {"service": "fin.order_entrust", "system": "fin"},
      {"service": "logi.mysql-svc",    "system": "logi"},
      {"service": "common",            "system": ""},
      {"service": "",                  "system": ""}
    ]
  }
}
```

> **解析规则**:`system_id = svc.split(".", 1)[0]`;无 `.` 或空字符串则 `system_id = ""`
> ([service/system_from_service.py:8-21](src/gimbal-plate/gimbal_plate/service/system_from_service.py))。
>
> **注意**:这是纯计算,**不读 registry**,也不校验该 system 是否真实注册。
>
> **文档-示意图修正**:PLATE-API-SURFACE.md §B3 的请求示例使用 `["fin.tidb-test", "logi.mysql-svc"]`,但 `tidb-test` 不是已注册的服务名(只是 namespace 占位符)。本接口接收任意字符串并按 `.` 拆分,实际平台应传入"系统前缀.服务短名"的拼装字符串。

---

## C 组 — 系统管理(2 个,当前全部 501 Not Implemented)

### C1. 注册 / 更新被测系统(管理员)

> **POST** `/api/systems`
> Body: `{name, source_url, auth_method, sync_mode}`
> 权限:管理员

#### curl(预期 501)

```bash
curl -sS -X POST "http://localhost:8000/api/systems" \
     -H "Content-Type: application/json" \
     -d '{"name":"fin","source_url":"https://...","auth_method":"bearer","sync_mode":"incremental"}'
```

#### HTTPie(预期 501)

```bash
http POST http://localhost:8000/api/systems \
    name=fin source_url=https://example.com auth_method=bearer sync_mode=incremental
```

#### 实弹响应(501)

```json
{
  "ok": false,
  "error": {
    "code": "admin_not_implemented",
    "message": "system registration is not implemented in plate; C1 is deferred to the platform backend"
  }
}
```

> 见 [routes_admin.py:14-25](src/gimbal-plate/gimbal_plate/http/routes_admin.py)。
> PLATE-API-SURFACE.md §11 明确说明:C1/C2 由 Platform backend 实现,Plate 不实装。

---

### C2. 同步结构版本(管理员)

> **POST** `/api/systems/{system_id}/sync`
> 权限:管理员

#### curl(预期 501)

```bash
curl -sS -X POST "http://localhost:8000/api/systems/fin/sync"
```

#### HTTPie(预期 501)

```bash
http POST http://localhost:8000/api/systems/fin/sync
```

#### 实弹响应(501)

```json
{
  "ok": false,
  "error": {
    "code": "admin_not_implemented",
    "message": "structure sync for system 'fin' is not implemented in plate; C2 is deferred to the platform backend"
  }
}
```

> 见 [routes_admin.py:28-39](src/gimbal-plate/gimbal_plate/http/routes_admin.py)。

---

## 附 1:启动本地服务

```bash
# 安装(若尚未安装)
pip install -e ./src/gimbal-plate

# 启动(默认端口 8000,自带 fin 系统 18 个 endpoint 自动注册)
PYTHONPATH=src/gimbal-plate \
    python -m uvicorn "gimbal_plate.http.app:create_app" --factory \
    --host 0.0.0.0 --port 8000

# 健康检查
curl -sS http://localhost:8000/healthz
```

---

## 附 2:接口总览速查表

| 接口 | 方法 | 路径 | Body | 状态 |
|---|---|---|---|---|
| `healthz` | GET | `/healthz` | — | ✅ |
| A1 | GET | `/api/systems` | — | ✅ |
| A2 | GET | `/api/systems/{system_id}/tree?depth=2` | — | ✅ |
| A3 | GET | `/api/systems/{system_id}/services/{service}/endpoints` | — | ✅ |
| A4 | GET | `/api/endpoints/{endpoint_id}` | — | ✅ |
| A5 | GET | `/api/endpoints/{endpoint_id}/field-defaults` | — | ✅ |
| B1 | POST | `/api/endpoints/{endpoint_id}/resolve-paths` | `{response_body_sample, path_prefix?}` | ✅ |
| B2 | POST | `/api/endpoints/{endpoint_id}/failed-criteria-resolved` | — | ✅ |
| B3 | POST | `/api/resolve/system-from-service` | `{services: [...]}` | ✅ |
| C1 | POST | `/api/systems` | `{name, source_url, ...}` | ⚠️ 501 |
| C2 | POST | `/api/systems/{system_id}/sync` | — | ⚠️ 501 |

10 个接口 = 8 实装 + 2 显式 501。

---

## 附 3:验证记录

本次修正(2026-08-06)基于以下实弹验证:

| 验证项 | 命令 | 结果 |
|---|---|---|
| 模块导入 | `PYTHONPATH=src/gimbal-plate python -c "from gimbal_plate.http.app import create_app"` | ✅ |
| 依赖检查 | fastapi 0.135.2 / pydantic 2.12.5 / uvicorn 0.42.0 | ✅ |
| 测试套件 | `pytest tests/plate -k http -v` | **26/26 PASSED** |
| 启动服务 | `uvicorn "gimbal_plate.http.app:create_app" --factory --host 127.0.0.1 --port 8765` | ✅ `/healthz` 200 |
| 10 个接口实弹 | httpx.request(method, path) × 10 | ✅ 8 实装 + 2 显式 501 |

> **修正的偏差**(由 PLATE-API-SURFACE.md 示意图 → 实弹数据):
> 1. A2 service 名:由 `tidb-test` → `account/audit/order/order_entrust/order_fee/settlement`(真实注册值)
> 2. A4 `api` 字段:补齐 `timeout_seconds`(不是 `timeout`)+ `auth` + `produces` + `consumes`
> 3. A4 `metadata.priority`:在 endpoint 未显式设置时被 `exclude_none=True` 过滤 —— **代码行为正确,文档显式说明**
> 4. B2 `failed_criteria`:fin 系统当前 18 个 endpoint 均未声明,实弹响应为空数组 —— **接口行为正确,数据状态待补**