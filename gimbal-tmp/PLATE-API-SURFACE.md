# Plate 结构请求面（API Surface）

> 调研笔记。回答一个核心问题：**平台为了渲染 14 屏原型 + PRD v1.0 中的字段，需要向 plate 发起哪些结构请求？**
>
> **重要边界**：用例（Scenario）的存储 / CRUD / 编辑由 platform 自身实现。**Plate 只提供结构数据**（被测系统、接口契约、字段定义）。本文档只列 Plate 的职责范围。

---

## 1. Plate 职责边界

```
┌─ Plate ─────────────────────────────┐
│  被测系统注册与版本管理               │
│  接口契约 (EndpointSpec) 存储          │
│  IOFieldBinding 字段元信息              │
│  request_body_samples / schema-only 字段│
│  preconditions / success_criteria /   │
│    failed_criteria / business_notes    │
│  assertable_paths（响应侧）             │
│  failed_criteria × assertable 解析     │
│  自动提取路径候选（用于 Auto-Extract） │
└──────────────────────────────────────┘
         ↑ 只读 / 只解析
         │ （HTTPS / gRPC）
┌─ Platform Backend ─────────────────┐
│  Scenario JSON 存储                     │
│  Scenario CRUD（保存 / 复制 / 删除）     │
│  Scenario 跨系统 / schema 校验           │
│  Scenario ↔ Endpoint 转换             │
│  用例执行与运行（gimbal）              │
└──────────────────────────────────────┘
         ↑
┌─ Platform Frontend ────────────────┐
│  14 屏原型（基于 PRD v1.0）            │
└──────────────────────────────────────┘
```

Platform 不直接访问 gimbal 引擎；Scenario 运行由 platform 自己调度（可调 gimbal）。

---

## 2. 接口分组

按用途分为 3 组：

| 组 | 接口数 | 触发场景 |
|---|---|---|
| **A. 结构拉取** | 5 | 启动 / 刷新 / 进入目录 / 进入详情 |
| **B. 结构搜索** | 3 | @ 浮层 / 跨系统校验 / 自动提取路径 |
| **C. 系统管理** | 2 | 注册被测系统 / 同步结构版本 |

**总计 10 个接口**。

> 不包含：Scenario CRUD / Scenario 复制 / Scenario 删除 / 模板提取 / 同步用例到 plate —— 这些是 Platform 的职责。

---

## 3. A 组 — 结构拉取

### A1. 列出已注册被测系统
- **触发**：`EndpointCatalog` 系统 tab / `CaseComposerMeta` 归属系统 chip / `CaseComposerHome` 系统筛选
- **请求**：`GET /api/systems`
- **响应**：
  ```json
  {
    "systems": [
      {"id": "fin", "name": "财务", "service_count": 3, "endpoint_count": 48, "registered_at": "..."},
      {"id": "logi", "name": "物流", ...},
      {"id": "common", "name": "公共", ...}
    ]
  }
  ```
- **缓存**：启动拉一次 + 修改时刷新

### A2. 列出某系统的 service / 模块树
- **触发**：`EndpointCatalog` 左侧 service 树 / `CaseComposerCanvasAddStep` 内嵌 CatalogPanel 左侧
- **请求**：`GET /api/systems/{system_id}/tree?depth=2`
- **响应**：
  ```json
  {
    "services": [
      {"id": "tidb-test", "name": "tidb-test-service", "modules": [
        {"id": "order", "endpoint_count": 12},
        {"id": "settlement", "endpoint_count": 8}
      ]},
      ...
    ]
  }
  ```

### A3. 列出某系统某服务的 endpoint（轻量索引）
- **触发**：`EndpointCatalog` 卡片网格 / `CaseComposerCanvasAddStep` 嵌入 CatalogPanel 右侧
- **请求**：`GET /api/systems/{system_id}/services/{service}/endpoints?module=&method=&q=`
- **响应**：
  ```json
  {
    "endpoints": [
      {
        "id": "fin.order_entrust.order_add",
        "name": "orderAdd",
        "method": "POST",
        "path": "/api/order/orderEntrust/orderAdd",
        "description": "订单新增委托 · 限保缴纳",
        "system": "fin",
        "service": "tidb-test",
        "module": "order",
        "tags": ["order", "entrust", "smoke"],
        "priority": 1,
        "version": "1.0.0"
      },
      ...
    ],
    "total": 12
  }
  ```
- **缓存**：service 树懒加载，访问过的 service 缓存 5 分钟

### A4. 获取单个 EndpointSpec 完整契约
- **触发**：每次进入 `CaseComposerCanvasAddStepDetail`（点击 endpoint 卡片时）
- **请求**：`GET /api/endpoints/{endpoint_id}`
- **响应**（这是 Plate 提供的**核心结构对象**）：
  ```json
  {
    "id": "fin.order_entrust.order_add",
    "name": "orderAdd",
    "system": "fin",
    "service": "tidb-test",
    "module": "order",
    "tags": [...],
    "version": "1.0.0",
    "api": {
      "method": "POST",
      "path": "/api/order/orderEntrust/orderAdd",
      "auth": "bearer",
      "timeout_seconds": 30,
      "produces": ["application/json"],
      "consumes": ["application/json"],
      "headers": {}
    },
    "request": {
      "body_type": "json",
      "fields": [
        {
          "name": "client_expand_name",
          "path": "$.client_expand_name",
          "required": true,
          "ui_kind": "text",
          "source_kind": "independent",
          "example": "张三",
          "description": "客户拓展员名称"
        },
        ...
      ],
      "schema_": {...}  // schema-only 字段（Type C）
    },
    "responses": {
      "200": {
        "status": 200,
        "fields": [...],
        "assertable_fields": ["$.code", "$.data.order_id", "$.data.order_no"]
      },
      "400": {...}
    },
    "metadata": {
      "module": "order",
      "tags": [...],
      "owner": "codfish",
      "priority": 1,
      "preconditions": ["需已登录 fin.codfish", "客户 customer_id=320 存在且启用"],
      "success_criteria": "状态码 200, data.code = 0",
      "failed_criteria": [
        "401 未登录 / token 过期 → response.code = 10001",
        "403 无权限访问该订单 → response.code = 10003",
        "422 客户不存在或已禁用 → response.code = 10022 · 校验 customer_id"
      ],
      "business_notes": "限保缴纳场景专用：单订单 ≤ 50 万 CNY；超限走线下流程，平台不承载...",
      "deprecated": false,
      "experimental": false
    },
    "updated_at": "2026-08-01T10:00:00Z"
  }
  ```
- **缓存**：单接口缓存，结构变更时失效

### A5. 获取 endpoint 的字段填充建议（用于字段编辑器默认值）
- **触发**：`CaseComposerCanvas` 字段编辑器加载 step 时（替代原 D1）
- **请求**：`GET /api/endpoints/{endpoint_id}/field-defaults` body `{step_index?, scenario_vars?}`
- **响应**：
  ```json
  {
    "field_defaults": [
      {"name": "client_expand_name", "kind": "literal", "value": "张三"},
      {"name": "bl_no", "kind": "scenario_var", "value": "${var.bl_no}"},
      {"name": "supplier", "kind": "lookup", "value": "${auth.codfish.suppliers}"},
      {"name": "etd", "kind": "generated", "value": "auto · date policy"}
    ],
    "carry_fields": [
      {"name": "customer_tax_number", "type": "string", "carry": true, "default": ""},
      {"name": "customer_address_cn", "type": "string", "carry": true, "default": ""},
      {"name": "internal_note", "type": "string", "carry": true, "default": ""}
    ]
  }
  ```
- **说明**：基于 IOFieldBinding.ui_kind + source_kind + example/default，plate 给出"该填什么"的建议值。`scenario_var` 引用让 platform 拼上 `${var.x}`，`lookup` 让 platform 拼上 `${auth.x.token}`。
- **缓存**：endpoint 缓存绑定

---

## 4. B 组 — 结构搜索 / 计算

### B1. 解析响应路径候选（Auto-Extract 候选）
- **触发**：`CaseComposerCanvas` 字段框 @ 浮层"上游响应"组
- **请求**：`POST /api/endpoints/{endpoint_id}/resolve-paths` body `{response_body_sample, path_prefix?}`
- **响应**：
  ```json
  {
    "paths": [
      {"path": "$.data.order_id", "depth": 2, "extracted_by_default": false},
      {"path": "$.data.shipping.method", "depth": 3, "extracted_by_default": false}
    ]
  }
  ```
- **说明**：从 sample / schema 反推所有可访问的 JSONPath，平台从中选出未声明 Extract 的给用户选。
- **缓存**：endpoint 缓存绑定

### B2. 失败参考 × assertable 联动解析
- **触发**：`CaseComposerCanvasAddStepDetail` Hero 渲染
- **请求**：`POST /api/endpoints/{endpoint_id}/failed-criteria-resolved`
- **响应**：
  ```json
  {
    "failed_criteria": [
      {"code": 401, "description": "未登录", "field": "$.code=10001", "assertable": true},
      {"code": 403, "description":": "无权限", "field": "$.code=10003", "assertable": true},
      {"code": 422, "description": "客户不存在", "field": "$.code=10022", "assertable": false}
    ]
  }
  ```
- **说明**：把 `failed_criteria` 里的失败字段路径与 `assertable_fields` 做交叉，得到每条是否能被平台自动断言（✓ vs ○ 标记的来源）。
- **缓存**：endpoint 缓存绑定

### B3. 跨系统归属计算（不校验，只计算）
- **触发**：`CaseComposerMeta` 选中归属系统 chip 时 / `CaseComposerCanvas` 步骤流着色
- **请求**：`POST /api/resolve/system-from-service` body `{services: ["fin.tidb-test", "logi.mysql-svc"]}`
- **响应**：
  ```json
  {
    "systems": [
      {"service": "fin.tidb-test", "system": "fin"},
      {"service": "logi.mysql-svc", "system": "logi"}
    ]
  }
  ```
- **说明**：用 `service.split(".")[0]` 反推系统。这是纯计算，无需后端持久化，但放在 Plate 是因为命名空间约定是 Plate 的语义。

---

## 5. C 组 — 系统管理

### C1. 注册 / 更新被测系统（管理员）
- **触发**：管理员在 `EndpointCatalog` 顶部点"+ 注册被测系统"
- **请求**：`POST /api/systems` body `{name, source_url, auth_method, sync_mode}`
- **响应**：`201 {system_id}` + 触发 A1 刷新
- **权限**：管理员（PRD 3 节）

### C2. 同步结构版本（管理员）
- **触发**：管理员在系统管理点"重新同步"
- **请求**：`POST /api/systems/{system_id}/sync`
- **响应**：`200 {synced_at, new_endpoints_count, updated_endpoints_count, removed_endpoints_count}`
- **说明**：从被测系统的 source_url 拉最新 EndpointSpec，diff 后更新本地。触发 A1-A4 缓存失效。

---

## 6. 接口 ↔ 触发屏幕矩阵

| 接口 | 触发的屏幕 / 交互 |
|---|---|
| A1 列出系统 | `EndpointCatalog` 系统 tab · `CaseComposerMeta` 归属系统 chip · `CaseComposerHome` 系统筛选 |
| A2 列出 service 树 | `EndpointCatalog` 左侧 · `CaseComposerCanvasAddStep` 嵌入 CatalogPanel 左侧 |
| A3 列出 endpoint | `EndpointCatalog` 卡片网格 · `CaseComposerCanvasAddStep` 嵌入 CatalogPanel 右侧 |
| A4 获取 endpoint 完整契约 | `CaseComposerCanvasAddStepDetail` 嵌入 DetailPanel |
| A5 获取字段填充建议 | `CaseComposerCanvas` 字段编辑器加载 step |
| B1 解析响应路径候选 | `CaseComposerCanvas` 字段框 @ 浮层"上游响应"组 |
| B2 失败参考解析 | `CaseComposerCanvasAddStepDetail` Hero 渲染 |
| B3 跨系统归属计算 | `CaseComposerMeta` 归属系统 chip · `CaseComposerCanvas` 步骤流系统着色 |
| C1 注册被测系统 | 管理员 `EndpointCatalog` 顶部 |
| C2 同步结构版本 | 管理员 系统管理 |

---

## 7. 请求频率估算（生产）

| 接口 | 频率 | 备注 |
|---|---|---|
| A1 | 启动 1 次 / 修改 1 次 | 重 cache |
| A2 | 进入 Catalog 1 次 | 重 cache |
| A3 | 进入 Catalog 1 次 | service 缓存 5min |
| A4 | 进入 AddStepDetail 1 次 | endpoint 缓存 |
| A5 | 进入 Canvas 字段编辑 1 次 / step 切换 | endpoint 缓存 |
| B1 | 用户触发 @ 浮层时 | endpoint 缓存 |
| B2 | 进入 AddStepDetail 1 次 | endpoint 缓存 |
| B3 | 进入 Meta / Canvas 1 次 | 短 cache |
| C1/C2 | 管理员手动 | 实时 |

预期 QPS 由 A 系列启动 / 浏览场景驱动，编辑场景主要是 B 系列。

---

## 8. 鉴权与权限

| 接口 | 权限 |
|---|---|
| A1-A5, B1-B3 | 登录用户可读 |
| C1, C2 | 管理员 |

---

## 9. 与 PRD / 原型的对应关系

| 接口 | PRD 章节 | 原型屏 |
|---|---|---|
| A1 | 6.1 (Home 系统筛选) + 6.5 (Canvas 归属系统) | CaseComposerHome, CaseComposerMeta |
| A2 | 6.7 (AddStep 内嵌 CatalogPanel 左侧) | CaseComposerCanvasAddStep |
| A3 | 6.7 (AddStep 内嵌 CatalogPanel 右侧卡片网格) | CaseComposerCanvasAddStep |
| A4 | 6.8 (AddStepDetail 整屏内容) | CaseComposerCanvasAddStepDetail |
| A5 | 6.5 (Canvas 字段编辑器默认值) | CaseComposerCanvas |
| B1 | 5.7 (@ 浮层 + Auto-Extract) | CaseComposerCanvas 字段框 |
| B2 | 5.8 (失败参考 × assertable 联动) | CaseComposerCanvasAddStepDetail Hero |
| B3 | 5.1 / 5.3 (跨系统识别) | CaseComposerMeta, CaseComposerCanvas |
| C1 | 6.2 (EndpointCatalog 注册) | 管理操作 |
| C2 | 系统管理 | 管理操作 |

---

## 10. 总结

**Plate 只需提供 10 个结构接口**：

- **A 组**（5 个）：结构拉取（系统 / 服务 / endpoint 列表 / endpoint 详情 / 字段默认值）
- **B 组**（3 个）：结构搜索 / 计算（响应路径候选 / 失败参考解析 / 系统归属计算）
- **C 组**（2 个）：系统管理（注册 / 同步版本）

### 最关键的 3 个接口

1. **A4** `GET /api/endpoints/{id}` — 每次进入接口详情时调用，驱动 `CaseComposerCanvasAddStepDetail` 整屏渲染（最大对象）
2. **A5** `GET /api/endpoints/{id}/field-defaults` — 进入 Canvas 字段编辑器时填充默认值（最频繁的"装配"操作）
3. **B1** `POST /api/endpoints/{id}/resolve-paths` — @ 浮层触发，驱动 Auto-Extract 候选路径生成

### Plate 与 Platform 的边界

| 职责 | Plate |
 | |---|
| EndpointSpec / IOFieldBinding / metadata 存储 | ✅ Plate |
| failed_criteria × assertable 联动计算 | ✅ Plate |
| 响应路径候选解析（Auto-Extract 用） | ✅ Plate |
| 字段默认值填充建议（基于 ui_kind + example） | ✅ Plate |
| 跨系统归属计算（service → system） | ✅ Plate |
| **Scenario JSON 存储 / CRUD** | ❌ Platform |
| **Scenario ↔ Endpoint 转换（draft-step）** | ❌ Platform |
| **Scenario schema 校验** | ❌ Platform |
| **跨系统一致性校验（meta.system vs steps.service）** | ❌ Platform |
| **Scenario 复制 / 模板提取 / 同步到 plate** | ❌ Platform |

### 性能 / 缓存建议

| 类型 | 接口 | 缓存 |
|---|---|---|
| 重 cache | A1-A5, B1, B2 | endpoint 缓存，结构变更时失效 |
| 短 cache | A1, B3 | 30s |
| 实时 | C1, C2 | 管理员手动触发 |

### 一致性

每个 Plate 接口都对应具体 PRD 章节 + 具体原型屏的渲染需求（见第 6 节矩阵）。**没有"凭空"接口**，**也没有"遗漏"接口**。

---

## 11. 与旧版本的差异

之前的 `PLATE-API-SURFACE.md` v0 把 Scenario CRUD（保存 / 复制 / 删除）也列为 Plate 接口——这是**错误**的。本次修订（v1）明确：**用例由 Platform 存储**，Plate 只提供结构数据。如果后端实现参考了 v0，请按 v1 调整：

- ❌ 删除：`POST /api/scenarios` / `PUT /api/scenarios/{id}` / `DELETE /api/scenarios/{id}` / `POST /api/scenarios/{id}/clone` — 这些由 Platform 自身实现
- ❌ 删除：`POST /api/validate/scenario` — Scenario 校验由 Platform 实现，Plate 只提供字段定义
- ❌ 删除：`POST /api/endpoints/{id}/draft-step` — 这是 Platform 的职责（基于 Plate 返回的 A4 字段定义，Platform 自己组装 step）
- ❌ 删除：`POST /api/validate/cross-system` — 这是 Platform 的职责（基于 Plate 返回的 A4 service 字段）

Platform 内部实现时可以基于以下 Plate 接口**本地组装**这些能力：
- Scenario 保存 = Platform 写自己的存储 + 调 B1/B3 校验
- 加入 step 草稿 = Platform 调 A4 拿字段定义 + 调 A5 拿字段默认值 + Platform 自己拼 step JSON
- Schema 校验 = Platform 调 A4 拿 schema + 自己用 pydantic 校验
- 跨系统校验 = Platform 调 B3 拿服务→系统映射 + 自己比对