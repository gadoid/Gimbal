# Plate HTTP 接口测试执行报告

> 测试运行时间：2026-08-11
> 测试范围：`tests/plate/test_http_*.py`（HTTP 接口相关的全部测试）
> 执行结果：**107 / 107 通过**，耗时 2.59 s

## 一、测试概况

### 1.1 覆盖文件清单（18 个）

| 文件 | 测试数 | 主要职责 |
| --- | ---: | --- |
| `test_http_health.py` | 1 | `/healthz` 健康检查 |
| `test_http_systems.py` | 1 | `/api/system` 系统列表 |
| `test_http_tree.py` | 2 | `/api/system/{system}/tree` 系统视图树 |
| `test_http_envelope.py` | 5 | 响应信封/错误模型单元测试 |
| `test_http_endpoints_list.py` | 4 | `/api/endpoint` 列表 + service/method/q 过滤 |
| `test_http_endpoint_detail.py` | 2 | `/api/endpoint/{id}` minimal view |
| `test_http_failed_resolved.py` | 1 | `POST /api/endpoint/{id}/action/failed-criteria` |
| `test_http_resolve_paths.py` | 3 | `POST /api/endpoint/{id}/action/resolve-paths` |
| `test_http_field_defaults.py` | 2 | `GET /api/endpoint/{id}/action/field-defaults` |
| `test_http_system_from_service.py` | 3 | `POST /api/system/action/from-service` |
| `test_http_admin_not_implemented.py` | 2 | `GET/POST /api/admin/*` → 501 stub |
| `test_http_references.py` | 13 | `/api/{dim}/{id}/references` 反向引用 |
| `test_http_full_endpoint.py` | 8 | `/full` endpoint 契约 |
| `test_http_full_config.py` | 9 | `/full` config 契约（含 password） |
| `test_http_full_resource.py` | 8 | `/full` resource 契约（含 image/portMapping） |
| `test_http_full_scenario.py` | 8 | `/full` scenario 契约（含 meta/steps） |
| `test_http_full_system_scoped.py` | 16 | system-scoped `/full` 成员判定 |
| `test_http_scenario_convert.py` | 15 | `POST /api/scenario/action/convert` |
| **合计** | **107** | |

### 1.2 执行命令

```
python -m pytest tests/plate/test_http_*.py -v --tb=short
```

最终一行：

```
================ 107 passed in 2.59s ================
```

## 二、接口清单（按 URL 类别）

ADR 0002 §D 规定的 M6 URL 文法：

| 段位 | 模板 | 含义 |
| --- | --- | --- |
| 1 | `/api/{dim}/...` | 顶层 dim 路由 |
| 2 | `/api/{dim}/{id}/...` | 单个 item 的 object-action / detail / references / full |
| 3 | `/api/{dim}/action/{name}` | dim-node action（不需要 `{id}`） |
| 4 | `/api/{dim}/{id}/action/{name}` | object-action（需要 `{id}`） |
| 5 | `/api/systems/{system}/{dim}/...` | system-scoped 视图 |

### 2.1 系统路由（system-tree）

| # | Method | URL | Handler |
| --- | --- | --- | --- |
| A1 | GET | `/healthz` | `app.py:create_app` |
| A2 | GET | `/api/system` | `routes_grammar.py:list_systems` |
| A3 | GET | `/api/systems/{system}/system/tree` | `routes_grammar.py:get_system_tree` |
| A4 | POST | `/api/system/action/from-service` | `routes_grammar.py:action_system_from_service` |

### 2.2 Dim 列表/详情（light view）

| # | Method | URL | 备注 |
| --- | --- | --- | --- |
| B1 | GET | `/api/endpoint` | 支持 `?service=` `?method=` `?q=` |
| B2 | GET | `/api/endpoint/{id}` | minimal view（仅 `id`/`service`/`method`/`module`/`tags`/`version`） |
| B3 | GET | `/api/systems/{system}/endpoint` | list_for_system |
| B4 | GET | `/api/systems/{system}/endpoint/{id}` | detail_for_system |

其他 dim（`config`/`resource`/`scenario`/`service`/`system`/`meta`）同样通过统一的 dim 路由器暴露，shape 与 endpoint 对称（参见 B1/B2 行）。

### 2.3 Dim-node / Object Action

| # | Method | URL | Handler |
| --- | --- | --- | --- |
| C1 | POST | `/api/{dim}/action/{name}` | 通用 dim-node action（`dim_actions` 字典驱动） |
| C2 | POST | `/api/{dim}/{id}/action/{name}` | 通用 object-action（`actions` 字典驱动） |
| C3 | POST | `/api/scenario/action/convert` | `routes_grammar.action_scenario_convert`（M6 新增） |

### 2.4 References / Full / Admin

| # | Method | URL | 备注 |
| --- | --- | --- | --- |
| D1 | GET | `/api/{dim}/{id}/references` | 反向引用信号（Phase β 范围） |
| D2 | GET | `/api/{dim}/full` | 全量列表（每 item 暴露 `extra`） |
| D3 | GET | `/api/{dim}/{id}/full` | detail 全量视图 |
| D4 | GET | `/api/systems/{system}/{dim}/full` | system-scoped 全量列表 |
| D5 | GET | `/api/systems/{system}/{dim}/{id}/full` | system-scoped detail 全量视图 |
| E1 | GET | `/api/admin/{path:path}` | 501 `admin_not_implemented`（预留桩） |

## 三、逐接口详情（接口信息 / 请求信息 / 响应信息）

> 错误响应统一信封：`{"ok": false, "error": {"code": "<code>", "message": "<msg>", "details"?: {...}}}`
> 成功响应统一信封：`{"ok": true, "data": {...}, "dim"?: "<dim>"}`（参见 `envelope.py`）

### A1. `GET /healthz`

- 接口信息：存活探针，无注册依赖
- 请求信息：无 body、无 query
- 响应信息：
  - 200：`{"status": "ok"}`
- 测试：`test_http_health.py::test_healthz_returns_ok`

### A2. `GET /api/system`

- 接口信息：枚举所有已注册系统
- 请求信息：无
- 响应信息：
  - 200：`{"ok": true, "data": {"items": [...], "total": int}}`，fin seed 至少 1 个
- 测试：`test_http_systems.py::test_systems_list_includes_fin`

### A3. `GET /api/systems/{system}/system/tree`

- 接口信息：返回 system 视图树（endpoint × service × system 关系图）
- 请求信息：`system` 段位
- 响应信息：
  - 200：`{"ok": true, "data": {"tree": {...}}}`
  - 404 `system_not_found`：未知 system
- 测试：`test_http_tree.py::test_tree_returns_200_for_fin`、`test_tree_unknown_system_returns_404`

### A4. `POST /api/system/action/from-service`

- 接口信息：dim-node action（无 `{id}`），从 service 名推导出所在 system
- 请求信息：
  ```json
  { "service": "<service_name>", "version"?: "<ver>" }
  ```
- 响应信息：
  - 200：`{"ok": true, "data": {"system": "<system_name>"}}`
  - 400 `invalid_action`：缺 `service`
  - 404 `dim_item_not_found`：service 不存在
- 测试：`test_http_system_from_service.py::test_from_service_known_service`、`test_unknown_service_404`、`test_missing_service_400`

### B1. `GET /api/endpoint`

- 接口信息：列表，支持 service / method / q 过滤
- 请求信息（query）：
  - `service?: str` — 精确匹配
  - `method?: str` — 精确匹配
  - `q?: str` — 模糊匹配
- 响应信息：
  - 200：`{"ok": true, "data": {"items": [{id, service, method, module, tags, version}, ...], "total": int}}`
- 测试：`test_http_endpoints_list.py`（共 4 条）

### B2. `GET /api/endpoint/{id}`

- 接口信息：minimal detail
- 请求信息：`id` 段位
- 响应信息：
  - 200：`{"ok": true, "dim": "endpoint", "data": {"item": {id, service, method, module, tags, version}}}`
  - 404 `dim_item_not_found`
- 测试：`test_http_endpoint_detail.py`（共 2 条）

### B3 / B4. `/api/systems/{system}/endpoint{,/{id}}`

- 接口信息：list_for_system / detail_for_system
- 请求信息：system 段位 + 可选 id
- 响应信息：与 B1/B2 同 shape；额外校验 item 所属 system（`_item_belongs_to_system`）
- 测试：覆盖在 `test_http_full_system_scoped.py` 的 light path 部分

### C1. `POST /api/{dim}/action/{name}`（通用）

- 接口信息：dim-node action，由 `DimSpec.actions` 字典驱动；当前 dim 上注册：
  - `system.from-service`
  - `scenario.convert`
- 请求信息：自由 JSON，由 action 函数解析
- 响应信息：由 action 函数返回的 dict 包装为信封
- 错误：
  - 400 `invalid_action`：未知 action 名
  - 400 `dim_not_found`：未知 dim
- 测试：`test_http_scenario_convert.py::test_convert_unknown_action_returns_400`

### C2. `POST /api/{dim}/{id}/action/{name}`（通用）

- 接口信息：object-action；当前 endpoint dim 注册 3 个：
  - `failed-criteria`（POST）
  - `resolve-paths`（POST）
  - `field-defaults`（GET）
- 请求信息：`id` + action 名 + JSON body
- 响应信息：自由 shape
- 测试：`test_http_failed_resolved.py`、`test_http_resolve_paths.py`、`test_http_field_defaults.py`

### C3. `POST /api/scenario/action/convert`（M6 新增）

- 接口信息：把 `export.dispatch()` 暴露到 HTTP 层。两步处理：1) `Scenario.model_validate(raw_scenario)`；2) `export.dispatch(consumer, scenario, **kwargs)`
- 请求信息：
  ```json
  {
    "consumer": "gimbal" | "platform",   // 缺省 "gimbal"
    "scenario": {...},                   // 必填，Scenario 原始 dict
    "endpoints"?: [...],                 // platform 专用，gimbal 不接受
    "sections"?: [...]                   // platform 专用
  }
  ```
- 响应信息：
  - 200：`{"ok": true, "dim": "scenario", "data": {"consumer": "<echo>", "converted": {...}}}`
    - `gimbal` consumer 的 `converted` 等于 `GimbalScenarioExporter.to_dict()` 的输出
    - `platform` consumer 的 `converted` 含 `endpoints`/`navigation`/`config_summary`
  - 400 `invalid_action`：
    - 缺 `scenario`
    - Scenario 字段缺失/类型错误（`ValidationError`）
    - 未知 `consumer`（错误信息列出可用列表）
    - consumer 不接受的 kwarg（如 `gimbal` + `endpoints`，`extra="forbid"`）
    - `sections` 含非法字面值
- 测试：`test_http_scenario_convert.py`（共 15 条，详见下表）

| 测试名 | 用例 |
| --- | --- |
| `test_convert_gimbal_matches_direct_exporter` | gimbal 输出 byte-for-byte 等于直接 exporter |
| `test_convert_gimbal_default_consumer` | consumer 缺省时为 "gimbal" |
| `test_convert_platform_default_sections` | platform 全 sections |
| `test_convert_platform_with_endpoints_kwarg` | `endpoints=[]` 显式可空 |
| `test_convert_missing_scenario_returns_400` | 缺 scenario → 400 |
| `test_convert_empty_body_returns_400` | 空 body → 400 |
| `test_convert_invalid_senario_payload_returns_400` | 删 `scenarioId` → 400 |
| `test_convert_scenario_wrong_type_returns_400` | scenario 是字符串 → 400 |
| `test_convert_unknown_consumer_returns_400` | consumer=foo → 400 |
| `test_convert_gimbal_with_endpoints_kwarg_returns_400` | gimbal 不接受 endpoints → 400 |
| `test_convert_platform_invalid_section_returns_400` | sections=["bogus"] → 400 |
| `test_convert_route_exists_and_matches_dim_node_action` | OpenAPI template + 运行时 200 |
| `test_convert_unknown_action_returns_400` | 未知 action 名 → 400 |
| `test_default_consumer_explicit_in_response` | 响应回写 consumer |
| `test_convert_does_not_bypass_direct_exporter` | 复用 dispatch 的回归保护 |

### D1. `GET /api/{dim}/{id}/references`（Phase β）

- 接口信息：轻量反向引用信号（不构建完整跨 dim 边图）
- 请求信息：`dim` + `id`
- 响应信息：
  - 200：`{"ok": true, "dim": "<dim>", "data": {"item": {"dim", "id"}, "references": {<dim-specific>}}}`
  - 404 `dim_item_not_found`：id 未知
  - 404 `dim_not_found`：dim 未知
- per-dim 信号：
  - `endpoint` → `service`, `module`, `tags`
  - `service` → `endpoint_count`
  - `system` → `endpoint_count`, `service_count`
  - `config` → `service_count`
  - `meta` → 系统列表
  - `resource` → `kind`
  - `scenario` → `scenarios_referenced_by`（Phase γ 候选）
- 测试：`test_http_references.py`（共 13 条，参数化覆盖 7 个 dim）
- 安全约束：`references` 不会泄漏 `password`/`users`/`services` 等敏感字段

### D2 ~ D5. `/full` 契约（ADR 0002 §D-D5）

| URL | 行为 |
| --- | --- |
| `GET /api/{dim}/full` | 全量列表，每 item 暴露 `extra` |
| `GET /api/{dim}/{id}/full` | detail 全量视图 |
| `GET /api/systems/{system}/{dim}/full` | system-scoped 全量列表 |
| `GET /api/systems/{system}/{dim}/{id}/full` | system-scoped 全量 detail |

`/full` 与 light 的区别：

| dim | light view 字段 | `/full` 额外暴露 |
| --- | --- | --- |
| endpoint | `id`, `service`, `method`, `module`, `tags`, `version` | `api`, `metadata` |
| config | 不含 password、不含 extra | `users[].password` + `extra` |
| resource | `name`, `kind` | `extra{image, config, portMapping}` |
| scenario | `scenario_id`, `name`, `systems` | `extra{meta, config, resource, steps}` |

测试覆盖（`test_http_full_*.py`，共 49 条）：
- 200 detail/list
- light 不含 `extra`
- 未知 id 返回 404 `dim_item_not_found`
- system-scoped 成员判定（`_item_belongs_to_system`）
- 错 system 返回 404（`dim_item_not_found` 或 `system_not_found`）

### E1. `/api/admin/*`

- 接口信息：预留桩
- 请求信息：任意 path
- 响应信息：
  - 501 `admin_not_implemented`
- 测试：`test_http_admin_not_implemented.py`（GET/POST 各 1）

### F. 信封/错误模型单元测试

- 文件：`test_http_envelope.py`
- 覆盖：
  - `ok_response({"x":1})` → `{"ok": True, "data": {"x": 1}}`
  - `err_response("not_found", "missing", http_status=404)` → `(body, 404)`
  - `err_response(..., details={"field":"x"})` → 含 `details`
  - `PlateHTTPError` 携带 `http_status` / `code` / `message`
  - `EnvelopeOk` / `EnvelopeErr` round-trip `model_dump` 含 `ok` 字段

## 四、错误码字典

| code | 含义 | HTTP |
| --- | --- | --- |
| `invalid_action` | action 参数缺失 / 校验失败 / 未知 consumer / 非法 kwarg | 400 |
| `dim_item_not_found` | 未知 id | 404 |
| `dim_not_found` | 未知 dim | 404 |
| `system_not_found` | 未知 system | 404 |
| `internal_error` | 未捕获异常 | 500 |
| `admin_not_implemented` | 管理路由桩 | 501 |

## 五、变更追踪

- **本轮新增**：`POST /api/scenario/action/convert`（C3）+ 15 条测试
- **测试总数增长**：396 → 411 → **107 个 HTTP 接口测试** + 其余非接口测试
- **覆盖率**：所有路由模板 + 所有错误码 + system-scoped 成员判定

## 六、建议

1. dim-node action 现仅 `system.from-service`、`scenario.convert` 两例；后续若新增（如 `endpoint.export`）可复用同一模板。
2. `/references` 现阶段不构建完整跨 dim 边图，Phase γ 再扩展 `scenarios_referenced_by`。
3. `/full` 的 `extra` 形状由 `DetailView.from_*` 工厂决定；新增 dim 时记得同步更新 `ConfigDetailView`/`ResourceDetailView` 等。
