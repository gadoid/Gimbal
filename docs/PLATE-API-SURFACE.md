# Plate 结构请求面（API Surface）

> 调研笔记。回答一个核心问题：**平台为了渲染 14 屏原型 + PRD v1.0 中的字段，需要向 plate 发起哪些结构请求？**
>
> 版本：v2.1（与 http-api.md M6 对齐：13 个直接可用 + 6 个 v2.x 待实现；v2.1 新增 strategy 语法 dim 两接口）
>
> **重要边界**：
> - **Plate 提供**「**EndpointSpec 抽象**」 — 一个被测系统接口的结构定义（method / path / 请求字段 / 响应字段 / 失败参考 / 业务备注）
> - **Platform 自己组装**「**Scenario 序列化文件**」 — 用例的具体内容（meta / config / resource / steps[]）。**Scenario 由 Platform 自身存储**
> - Platform 在调用 Plate 拿到的 EndpointSpec 之上，**Platform自己负责**把多个 step 拼成 Scenario 存到自己的存储
>
> **关键概念区分**：
> - **EndpointSpec** = 一个接口的"模板"（Plate 提供） — 例：orderAdd 的 method / path / 18 个请求字段 / 6 个响应字段
> - **Step** = Scenario 里的一步 — 例：`{api: EndpointSpec.api, request: {body: {filled_values}}, strategy: [...]}`
> - **Scenario** = 整个用例的 JSON 序列（Platform 存储） — 例：`{meta, config, resource, steps: [Step1, Step2, ...]}`
>
> **URL path 命名约定（v1.3 起）**：
> - **`/api/systems/{system_name}/...`** — 使用业务名（"fin" / "logi" / "common"）
> - **不使用** `/api/systems/{system_id}/...` — 避免维护 id ↔ name 索引一致性
> - **理由**：
>   1. Plate 当前 schema `EndpointSpec.system: str`（无独立 system_id 抽象），URL 用 name 与 schema 对齐
>   2. 用户 UI 上看到 "fin" / "logi" / "common"，URL 一致可读
>   3. 无映射开销 — 不需要 `GET /api/systems?system_name=fin → {system_id}` 之类的反查
>   4. 改名是低频操作 — 系统注册后基本不动
> - **未来需要 system_id 的场景**（当前不需要）：
>   1. 系统要改名不破坏外链
>   2. 多租户隔离（不同租户 system_name 可能重名）
>   3. 与外部系统通过稳定 id 对接

---


## 1. Plate 与 Platform 职责边界

```
┌─ Plate ─────────────────────────────────────┐
│  EndpointSpec 集合（一个或多个被测系统）       │
│  - ApiSpec（method / path / auth / timeout） │
│  - RequestSpec（body_type / fields[]）        │
│  - ResponseSpec（status / fields[]）          │
│  - EndpointMetadata（preconditions /          │
│    success_criteria / failed_criteria /      │
│    business_notes）                           │
│  - 失败参考 × assertable 解析（计算）        │
│  - 响应路径候选（Auto-Extract 用）           │
│  - 字段默认值填充建议（基于 ui_kind）        │
└────────────────────────────────────────────┘
         ↑ 只读 / 只计算
         │ （HTTPS / gRPC）
┌─ Platform Backend ────────────────────────┐
│  ❌ 不存储 EndpointSpec（从 Plate 拉）          │
│  ✅ 存储 Scenario JSON（自己组装）            │
│  ✅ Scenario CRUD（保存 / 复制 / 删除）        │
│  ✅ 加 step 草稿：调 A4a 拿字段定义，        │
│       调 A5 拿默认值，Platform 拼 Step JSON    │
│  ✅ Scenario 校验（schema / 跨系统）          │
│  ✅ 调度 gimbal 执行（传 D1 转换结果）        │
└────────────────────────────────────────────┘
         ↑
┌─ Platform Frontend ─────────────────────┐
│  14 屏原型（基于 PRD v1.0）                  │
└────────────────────────────────────────────┘
```

**总结**：Plate 提供**一个接口一份数据**（per-endpoint），Platform 自己**组合**多个 endpoint 数据为 Scenario。

---

## 2. 接口分组

按用途分为 3 组 + 1 个 v2.x 待实现队列：

| 组 | 接口数 | 触发场景 |
|---|---|---|
| **A. 结构拉取（per-endpoint）** | 4 | 启动 / 刷新 / 进入目录 / 进入详情 / 字段编辑 |
| **B. 结构计算（per-endpoint）** | 3 | @ 浮层 / 跨系统校验 / 自动提取路径 |
| **C. 系统管理** | 2 | 注册被测系统 / 同步结构版本 |
| **S. 策略语法（grammar-level）** | 2 | Canvas 策略区渲染 / "添加策略"下拉 |
| **D. v2.x 待实现** | 6 | 聚合视图 / 白名单 / 预设集 / Scenario 转换 / 联动计算 |

**总计 13 个直接可用 + 6 个 v2.x 待实现**（A 组 4 + B 组 3 + C 组 2 + S 组 2 + 6 v2.x）。

> v2.0 起：11 个接口与 http-api.md M6 现状完全对齐。
> v2.x 待实现：6 个需要 Plate 抽象扩展（聚合 / 白名单 / 预设集 / Scenario 转换 / 联动计算）。

> **不包含** Scenario CRUD、Scenario 复制、Scenario 删除、模板提取、同步用例到 plate —— 这些是 Platform 自己实现，**不属于 Plate 职责**。

---

## 3. A 组 — 结构拉取（per-endpoint）

> v2.0 起：**4 个接口**，与 http-api.md M6 完全对齐。
> 移除：A2（service 树）、A4a / A4b（轻量切分）、A6 / A7（聚合）、A8 / A9（白名单 / 预设集）—— 这些要么由 Platform 聚合（A2/A6/A7），要么由 Platform 自己维护（A8/A9），要么合并到 A4 完整契约（A4a/A4b）。

### A1. 列出已注册被测系统
- **触发**：`EndpointCatalog` 系统 tab / `CaseComposerMeta` 归属系统 chip / `CaseComposerHome` 系统筛选
- **请求**：`GET /api/system`（http-api 用单数 dim 名；items 内含 `name` 字段）
- **响应**：
  ```json
  {
    "ok": true,
    "dim": "system",
    "data": {
      "items": [{"name": "fin"}, {"name": "logi"}, {"name": "common"}],
      "total": 3
    }
  }
  ```
- **缓存**：启动拉一次 + 修改时刷新
- **注意**：url 是 `/api/system`（dim 名单数）而不是 `/api/systems`（http-api 实际路由）

### A2（v2.0 移除）— service 树由 Platform 聚合
- **替代方案**：Platform 调 A1 + `GET /api/systems/{system}/service` + `GET /api/endpoint?service=fin-service&...` 在内存里聚合
- **理由**：http-api 没有 service 树聚合接口（A2 树是 v1.x 设计，M6 改成"按 service 列表"）
- **使用场景**：`EndpointCatalog` 左侧树 / `CaseComposerCanvasAddStep` 嵌入 CatalogPanel 左侧

### A3. 列出 endpoint（带筛选）
- **触发**：`EndpointCatalog` 卡片网格 / `CaseComposerCanvasAddStep` 嵌入 CatalogPanel 右侧
- **请求**：`GET /api/endpoint?system=&service=&method=&tag=&q=`（dim 名单数 + 标准 query 筛选）
- **响应**：
  ```json
  {
    "ok": true,
    "dim": "endpoint",
    "data": {
      "items": [
        {"id": "fin.order_entrust.order_add", "name": "orderAdd", "method": "POST", "path": "/api/order/orderEntrust/orderAdd", "system": "fin", "service": "fin-service", "module": "order", "tags": [...], "priority": 1, "version": "1.0.0"}
      ],
      "total": 12
    }
  }
  ```
- **缓存**：service 懒加载，5min

### A4. 获取单个 EndpointSpec 完整契约（合并 A4a + A4b）
- **触发**：`CaseComposerCanvasAddStepDetail` Hero 渲染 + `CaseComposerCanvas` 字段编辑器加载 step
- **请求**：`GET /api/endpoint/{endpoint_id}/full`（v2.0 合并了原来的 A4/A4a/A4b 三段）
- **响应**：返回 `EndpointDetailView.from_spec` 全部字段
  ```json
  {
    "ok": true,
    "dim": "endpoint",
    "data": {
      "item": {
        "id": "fin.order_entrust.order_add",
        "system": "fin", "service": "fin-service", "name": "orderAdd",
        "description": "...",
        "api": {"service": "...", "method": "POST", "path": "...", "headers": {}, "timeout_seconds": 30.0, "auth": "bearer"},
        "request": {
          "body_type": "json",
          "fields": [
            {"name": "client_expand_name", "path": "$.client_expand_name", "required": true, "ui_kind": "text", "source_kind": "independent", "default": null, "example": "张三", "description": "客户拓展员名称", "enum": null},
            ...
          ],
          "schema_": {...}
        },
        "responses": {"200": {"status": 200, "fields": [...], "assertable_fields": ["$.code", "$.data.order_id"]}, "400": {...}, "500": {...}},
        "metadata": {
          "preconditions": [...], "success_criteria": "...",
          "failed_criteria": ["401 ...", "403 ...", "422 ..."],
          "business_notes": "...", "module": "order", "tags": [...], "owner": "codfish", "priority": 1, "deprecated": false, "experimental": false, "version": "1.0.0"
        },
        "version": "1.0.0", "updated_at": "..."
      }
    }
  }
  ```
- **说明**：v2.0 合并 A4 + A4a + A4b 为单个 `/full` 接口（牺牲轻量切分，换与 http-api.md 一致）
- **缓存**：endpoint 缓存，结构变更失效
- **使用场景**：
  - `CaseComposerCanvasAddStepDetail` Hero（从 item.metadata 拿失败参考 / 前置条件 / 业务备注）
  - `CaseComposerCanvas` 字段编辑器（从 item.request.fields 拿字段定义）

### A5. 字段默认值填充建议
- **触发**：`CaseComposerCanvas` 字段编辑器加载 step
- **请求**：`POST /api/endpoint/{endpoint_id}/action/field-defaults`（action 形态，不是 GET）
- **请求 body**：`{}`
- **响应**：
  ```json
  {
    "ok": true,
    "dim": "endpoint",
    "data": {
      "item": {
        "id": "fin.order_entrust.order_add",
        "defaultFields": {
          "requestBody": [
            {"name": "client_expand_name", "kind": "literal", "value": "张三"},
            {"name": "bl_no", "kind": "scenario_var", "value": "${var.bl_no}"},
            {"name": "supplier", "kind": "lookup", "value": "${auth.codfish.suppliers}"},
            {"name": "etd", "kind": "generated", "value": "auto · date policy"}
          ],
          "responseBody": [...]
        }
      }
    }
  }
  ```
- **缓存**：endpoint 缓存绑定

### A6（v2.x 待实现）— 系统 module / priority 聚合
- **替代方案（v2.0 阶段）**：Platform 调 A3 结果在内存聚合 module / priority 集合，自己 cache
- **未来**：Plate 抽象增强后，可加 `GET /api/systems/{system}/module-priorities` 单接口
- **使用场景**：`CaseComposerMeta` 模块 / 优先级下拉

### A7（v2.x 待实现）— 系统 tag 聚合
- **替代方案（v2.0 阶段）**：Platform 调 A3 结果在内存聚合 tag 集合
- **未来**：Plate 加 `GET /api/systems/{system}/tags` 单接口
- **使用场景**：`CaseComposerMeta` Tags 输入推荐

### A8（v2.x 待实现）— Mock 容器镜像白名单
- **替代方案（v2.0 阶段）**：**Platform 自己维护** 镜像白名单（与 Plate 解耦）
- **未来**：Plate 抽象增强后，可加 `GET /api/systems/{system}/mock-images`
- **使用场景**：`CaseComposerResource` Mock.image 输入下拉
- **代价**：镜像兼容性更新需要 Platform 同步（不与 Plate 联动）

### A9（v2.x 待实现）— timePolicy / retry 预设策略集
- **替代方案（v2.0 阶段）**：**Platform 自己维护** 预设策略集
- **未来**：Plate 抽象增强后，可加 `GET /api/policy-presets`
- **使用场景**：`CaseComposerConfig` timePolicy / retry 选项
- **代价**：预设策略更新需要 Platform 同步

---

## 4. B 组 — 结构计算（per-endpoint）

> v2.0 起：3 个 action 接口，与 http-api.md M6 完全对齐。
> B2（联动）改为 Platform 调 action 拿原始 failed_criteria，自己与 assertable_paths 交叉。

### B1. 解析响应路径候选（Auto-Extract 用）
- **触发**：`CaseComposerCanvas` 字段框 @ 浮层"上游响应"组
- **请求**：`POST /api/endpoint/{endpoint_id}/action/resolve-paths`
- **请求 body**：`{"response_body_sample": {...}}`
- **响应**：
  ```json
  {
    "ok": true,
    "dim": "endpoint",
    "data": {
      "item": {
        "paths": ["data.order_id", "data.shipping.method", "code"]
      }
    }
  }
  ```
- **说明**：从 sample / schema 反推所有可访问的 JSONPath
- **缓存**：endpoint 缓存绑定

### B2. 失败参考 × assertable 联动（v2.0 改为 Platform 计算）
- **触发**：`CaseComposerCanvasAddStepDetail` Hero 渲染
- **请求**：`POST /api/endpoint/{endpoint_id}/action/failed-criteria`
- **请求 body**：`{}`
- **响应**（http-api 现状 — 只返回原始 failed_criteria 字符串）：
  ```json
  {
    "ok": true,
    "dim": "endpoint",
    "data": {
      "item": {"criteria": ["401 未登录 → response.code = 10001", "403 无权限 → response.code = 10003", "422 客户不存在 → response.code = 10022"]}
    }
  }
  ```
- **v2.0 行为**：Platform 调此接口 + A4（拿到 assertable_paths），**Platform 自己**做交叉：
  ```js
  // Platform frontend 计算
  failed_criteria.map(c => {
    const match = c.field.match(/response\.code\s*=\s*(\d+)/)
    const code = match ? parseInt(match[1]) : null
    const assertable = code !== null && assertable_paths.some(p => p.includes('code'))
    return { ...c, assertable }
  })
  ```
- **说明**：计算从 Plate 移到 Platform，**违反 v1.5 边界**（v1.5 计划 B2 在 Plate 内部算）。v2.0 妥协于 http-api 现状
- **未来**：v2.x Plate 可加 `failed-criteria-resolved` action，v2.0 阶段 Platform 自己算

### B3. 跨系统归属计算（per-service）
- **触发**：`CaseComposerMeta` 选中归属系统 chip / `CaseComposerCanvas` 步骤流系统着色
- **请求**：`POST /api/system/action/from-service`（dim 名单数 + global）
- **请求 body**：`{"services": ["fin.fin-service"]}`（列表，每项为全限定名 `<system>.<service>`，纯命名约定解析）
- **响应**：
  ```json
  {
    "ok": true,
    "dim": "system",
    "data": {
      "systems": [{"service": "fin.fin-service", "system": "fin"}]
    }
  }
  ```
- **说明**：`"fin.fin-service"` → "fin"；不带点的名字无法消歧，`system` 为空串
- **缓存**：与 A1 同步

---

## 5. C 组 — 系统管理

### C1. 注册 / 更新被测系统（管理员）
- **触发**：管理员在 `EndpointCatalog` 顶部点"+ 注册被测系统"
- **请求**：`POST /api/systems` body `{name, source_url, auth_method, sync_mode}`
- **响应**：`201 {system_name}` + 触发 A1 刷新
- **权限**：管理员

### C2. 同步结构版本（管理员）
- **触发**：管理员在系统管理点"重新同步"
- **请求**：`POST /api/systems/{system}/system/action/sync`
- **响应**（v2.0 阶段）：`501 admin_not_implemented`（Plate 一期未实现）
- **说明**：从被测系统的 source_url 拉最新 EndpointSpec 集合，diff 后更新本地。触发 A1-A4 缓存失效。
- **未来响应**：`200 {synced_at, new_endpoints_count, updated_endpoints_count, removed_endpoints_count}`（Plate 二期实现）

---

## 5S. S 组 — 策略语法（grammar-level dim）

> v2.1 新增。strategy 是 M6 的第 8 个 dim —— 与 endpoint/system 等**数据 dim 不同**，它是**语法级**的：
> items 不是数据实例，而是从 `StrategyUnion`（plate schema）内省出的 kind 描述符。
> 回答的问题是："策略有哪些 kind、每个 kind 有哪些字段" —— 策略*实例*仍存在 Scenario 的
> `steps[].strategy` 里（Platform 存储），本组接口只提供"添加策略"的结构渲染契约。
>
> `strategy_ref` 是预埋字段（待重设计），**不在** dim 输出中。

### S1. 列出策略 kind
- **触发**：`CaseComposerCanvas` 挂载（策略区初始化）→ 失败则降级 extract 专用 UI
- **请求**：`GET /api/strategy`
- **响应**：
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
- **缓存**：会话级（语法全局不变）
- **平台代理**：`GET /api/strategy-catalog`（unwrap `data.items` 后返回 list）

### S2. 获取单个策略 kind 的字段契约
- **触发**：选中某 kind 渲染表单（懒加载 + 会话缓存）；Canvas 挂载时预取全部 3 个
- **请求**：`GET /api/strategy/{kind}/full`
- **响应**（assertion 示例，fields 是该 kind 的业务字段，base_fields 是 StrategyBase 公共字段）：
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
          {"name": "target",    "path": "$.target",    "required": true,  "default": null,  "description": "断言目标 (JSONPath)",     "enum": null,           "ui_kind": "text"},
          {"name": "operator",  "path": "$.operator",  "required": true,  "default": "eq", "description": "比较符",                    "enum": ["eq","ne","gt","gte","lt","lte","in","not_in","contains","not_contains","exists","empty","length_eq","schema"], "ui_kind": "select"},
          {"name": "expected",  "path": "$.expected",  "required": false, "default": null,  "description": "期望值",                   "enum": null,           "ui_kind": "unknown"},
          {"name": "message",   "path": "$.message",   "required": false, "default": null,  "description": "失败信息",                 "enum": null,           "ui_kind": "text"},
          {"name": "soft",      "path": "$.soft",      "required": false, "default": false, "description": "软断言 (仅告警不中断)",     "enum": null,           "ui_kind": "boolean"}
        ],
        "base_fields": [
          {"name": "name",      "path": "$.name",      "required": false, "default": null,             "description": "策略名",        "enum": null,  "ui_kind": "text"},
          {"name": "phase",     "path": "$.phase",     "required": false, "default": "verifying",      "description": "执行阶段",      "enum": null,  "ui_kind": "text"},
          {"name": "order",     "path": "$.order",     "required": false, "default": 0,                "description": "执行顺序",      "enum": null,  "ui_kind": "number"},
          {"name": "enabled",   "path": "$.enabled",   "required": false, "default": true,             "description": "是否启用",      "enum": null,  "ui_kind": "boolean"},
          {"name": "onFailure", "path": "$.onFailure", "required": false, "default": "abort",          "description": "失败策略",      "enum": null,  "ui_kind": "text"},
          {"name": "timeout",   "path": "$.timeout",   "required": false, "default": null,             "description": "超时秒数",      "enum": null,  "ui_kind": "number"},
          {"name": "tags",      "path": "$.tags",      "required": false, "default": null,             "description": "标签",          "enum": null,  "ui_kind": "json"},
          {"name": "view_note", "path": "$.view_note", "required": false, "default": null,             "description": "视图注释",      "enum": null,  "ui_kind": "text"}
        ]
      }
    }
  }
  ```
- **词汇表**：与 `IOFieldBinding` 同名同义（name/path/required/default/description/enum/ui_kind），但**无 `source_kind`**（值来源语义对策略无意义）。前端 StrategyForm 补 `'independent'` 默认值即可复用 FieldForm。
- **base_fields 第一版不渲染**：添加策略骨架 = `{kind}` + 按 `fields` 的 `default` 展开；base 字段走默认值。
- **平台代理**：`GET /api/strategy-catalog/{kind}/full`（unwrap `data.item`）；plate 不可达 → `502 plate_unavailable`，404 → `strategy_kind_not_found`

---



---

---

---

## 6. 接口 ↔ 触发屏幕矩阵

| 接口 | 触发的屏幕 / 交互 |
|---|---|
| A1 列出系统 | `EndpointCatalog` 系统 tab · `CaseComposerMeta` 归属系统 chip · `CaseComposerHome` 系统筛选 |
| A2 列出 service 树 | `EndpointCatalog` 左侧 · `CaseComposerCanvasAddStep` 嵌入 CatalogPanel 左侧 |
| A3 列出 endpoint | `EndpointCatalog` 卡片网格 · `CaseComposerCanvasAddStep` 嵌入 CatalogPanel 右侧 |
| **A4** 端点元信息 + API 坐标 | `CaseComposerCanvasAddStepDetail` 嵌入 DetailPanel 的 Hero / 失败参考 / 前置条件 / 业务备注 |
| **A4a** 请求字段定义 | `CaseComposerCanvas` 字段编辑器主区 |
| **A4b** 响应字段定义 | `CaseComposerCanvasAddStepDetail` 响应字段表 · `CaseComposerCanvas` Auto-Extract 候选 |
| A5 获取字段填充建议 | `CaseComposerCanvas` 字段编辑器加载 step |
| B1 解析响应路径候选 | `CaseComposerCanvas` 字段框 @ 浮层"上游响应"组 |
| B2 失败参考解析 | `CaseComposerCanvasAddStepDetail` Hero（✓/○ 标记） |
| B3 跨系统归属计算 | `CaseComposerMeta` 归属系统 chip · `CaseComposerCanvas` 步骤流系统着色 |
| C1 注册被测系统 | 管理员 `EndpointCatalog` 顶部 |
| C2 同步结构版本 | 管理员 系统管理 |
| **S1** 列出策略 kind | `CaseComposerCanvas` 挂载（策略区 kinds）→ "添加策略"下拉 |
| **S2** 策略 kind 字段契约 | `CaseComposerCanvas` 策略表单渲染（懒加载 + 挂载预取） |
| **D1** Scenario → 执行体转换 | `CaseComposerCanvasRunner` "▶ 运行"按钮 |

---

## 7. 请求频率估算（生产）

| 接口 | 频率 | 备注 |
|---|---|---|
| A1 | 启动 1 次 / 修改 1 次 | 重 cache |
| A2 | 进入 Catalog 1 次 | 重 cache |
| A3 | 进入 Catalog 1 次 | service 缓存 5min |
| A4 | 进入 AddStepDetail 1 次 | endpoint 缓存 |
| A4a | 进入 Canvas 字段编辑 1 次 / step 切换 | endpoint 缓存 |
| A4b | 进入 AddStepDetail 1 次 + 字段编辑 Auto-Extract 触发 | endpoint 缓存 |
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
| A1-A5, A4a, A4b, B1-B3 | 登录用户可读 |
| C1, C2 | 管理员 |

---

## 9. 与 PRD / 原型的对应关系

| 接口 | PRD 章节 | 原型屏 |
|---|---|---|
| A1 | 6.1 (Home 系统筛选) + 6.5 (Canvas 归属系统) | CaseComposerHome, CaseComposerMeta |
| A2 | 6.7 (AddStep 内嵌 CatalogPanel 左侧) | CaseComposerCanvasAddStep |
| A3 | 6.7 (AddStep 内嵌 CatalogPanel 右侧卡片网格) | CaseComposerCanvasAddStep |
| **A4** | 6.5 (Canvas 字段编辑器按 ui_kind 渲染) + 6.8 (AddStepDetail Hero + 元信息 + 响应字段) | CaseComposerCanvas, CaseComposerCanvasAddStepDetail |
| A5 | 6.5 (Canvas 字段编辑器默认值) | CaseComposerCanvas |
| A6 / A7 | 6.6 (Meta 模块/优先级/tags 聚合) | CaseComposerMeta（**v2.0 由 Platform 聚合**） |
| A8 | 6.7 (Resource Mock 镜像白名单) | CaseComposerResource（**v2.0 Platform 自己维护**） |
| A9 | 6.8 (Config timePolicy / retry 预设) | CaseComposerConfig（**v2.0 Platform 自己维护**） |
| B1 | 5.7 (@ 浮层 + Auto-Extract) | CaseComposerCanvas 字段框 |
| B2 | 5.8 (失败参考 × assertable 联动) | CaseComposerCanvasAddStepDetail Hero |
| B3 | 5.1 / 5.3 (跨系统识别) | CaseComposerMeta, CaseComposerCanvas |
| C1 | 6.2 (EndpointCatalog 注册) | 管理操作 |
| C2 | 系统管理 | 管理操作 |

---

## 10. 总结

**Plate 只需提供 12 个接口**，全部是 **per-endpoint**（针对一个 EndpointSpec）：

- **A 组**（4 个）：结构拉取（系统 / endpoint 列表 / **endpoint 完整契约 /full** / 字段默认值）
- **B 组**（3 个）：结构计算（响应路径候选 / 失败参考解析 / 系统归属计算）
- **C 组**（2 个）：系统管理（注册 / 同步版本）

### EndpointSpec 拆分原则（per-endpoint）

A4 拆为 3 块（`meta-and-api` / `request-spec` / `response-specs`），因为：
- **场景 Hero 渲染**只需要元信息 + API 坐标（method / path / 失败参考 / 前置条件 / 业务备注）→ A4
- **字段编辑器渲染**只需要 RequestSpec → A4a
- **响应表 / Auto-Extract 渲染**只需要 ResponseSpec → A4b
- 拆分后**网络开销降低**（每次进入 AddStepDetail 不必拉整个 EndpointSpec 包含的几十个 IOFieldBinding），**缓存粒度更细**（结构变更时只失效相关子集）

### EndpointSpec 与 Scenario 的关系（关键）

| 概念 | 角色 | 谁拥有 | 例子 |
|---|---|---|---|
| **EndpointSpec** | 抽象 — 一个接口的结构 | **Plate** | `orderAdd` 的 method/path/18 字段定义 |
| **Step** | 一个接口调用 + 值 + 策略 | **Platform 组装** | `{api: ..., request: {body: {填充值}}, strategy: [...]}` |
| **Scenario** | 用例（meta + config + resource + steps[]） | **Platform 存储** | `{meta, config, resource, steps: [Step1, Step2, Step3]}` |

Platform 调 Plate 的 A4a / A4b / A5 / B1 拿 **EndpointSpec 抽象**，**Platform 自己组装 Step**，**Platform 自己的存储**存 Scenario 序列化文件。

### 最关键的 3 个接口

1. **A4a** `GET /api/endpoints/{id}/request-spec` — 每次进入字段编辑器时调用，驱动 `CaseComposerCanvas` 主区（最频繁、最大对象）
2. **A4** `GET /api/endpoints/{id}/meta-and-api` — 每次进入 AddStepDetail 时调用，驱动 Hero（中等对象）
3. **B1** `POST /api/endpoints/{id}/resolve-paths` — @ 浮层触发，驱动 Auto-Extract 候选路径生成

### Plate 与 Platform 的边界

| 职责 | 归属 |
|---|---|
| EndpointSpec 存储（被测系统 / 服务 / 接口 / 字段） | ✅ Plate |
| failed_criteria × assertable 联动计算 | ✅ Plate |
| 响应路径候选解析（Auto-Extract 用） | ✅ Plate |
| 字段默认值填充建议（基于 ui_kind + example） | ✅ Plate |
| 跨系统归属计算（service → system） | ✅ Plate |
| **Scenario 序列化文件存储 / CRUD** | ❌ **Platform** |
| **Step 组装（多 endpoint → Scenario）** | ❌ **Platform** |
| **Scenario 校验（schema / 跨系统）** | ❌ **Platform** |
| **Scenario 执行 / 调度 gimbal** | ❌ **Platform** |

### 性能 / 缓存建议

| 类型 | 接口 | 缓存 |
|---|---|---|
| 重 cache | A1-A5, A4a, A4b, B1, B2 | endpoint 缓存，结构变更时失效 |
| 短 cache | A1, B3 | 30s |
| 实时 | C1, C2 | 管理员手动触发 |

### Platform 内部如何用 Plate 能力

- **加入 step 草稿** = Platform 调 A4a 拿字段定义 + 调 A5 拿默认值 + Platform 自己拼 Step JSON
- **Scenario 保存** = Platform 写自己的存储 + Platform 自己校验
- **Schema 校验** = Platform 调 A4a 拿 schema + 自己用 pydantic 校验
- **跨系统校验** = Platform 调 B3 拿服务→系统映射 + 自己比对
- **字段编辑器渲染** = Platform 调 A4a 拿字段定义 + 按 ui_kind 渲染控件
- **Hero 渲染** = Platform 调 A4 拿元信息 + API 坐标
- **响应表 / Auto-Extract** = Platform 调 A4b + B1 自己筛

---

## 11. 与旧版本的差异（重要）

之前的 v0 / v1 文档中，我**错误地把 `Scenario` 当成"被拆分的接口"**（A4 是整个 Scenario 的子集拆分）。这是**根本性错误**。

正确理解：
- **Plate 的 A4 拆的是「一个 EndpointSpec 的子集」**（元信息 / 请求字段 / 响应字段）— 不是一个 Scenario 的拆分
- **Scenario 不在 Plate 接口范围** — Platform 自己组装、自己存

如果后端实现参考了更早的版本，请按 v1.2 调整：

- ❌ 错误理解：`GET /api/scenarios/{id}/meta` / `.../config` / `.../resource` / `.../steps` — **这些不是 Plate 接口**
- ✅ 正确理解：`GET /api/endpoints/{id}/meta-and-api` / `.../request-spec` / `.../response-specs` — 这些是 Plate 接口（针对一个 EndpointSpec）

- ❌ 删除：`POST /api/scenarios` / `PUT /api/scenarios/{id}` / `DELETE /api/scenarios/{id}` / `POST /api/scenarios/{id}/clone` — Scenario CRUD 是 Platform 职责
- ❌ 删除：`POST /api/validate/scenario` — Scenario 校验是 Platform 职责
- ❌ 删除：`POST /api/endpoints/{id}/draft-step` — Step 组装是 Platform 职责
- ❌ 删除：`POST /api/validate/cross-system` — 跨系统校验是 Platform 职责

- ✅ 拆分：`GET /api/endpoints/{id}` → `GET /api/endpoints/{id}/meta-and-api` + `GET /api/endpoints/{id}/request-spec` + `GET /api/endpoints/{id}/response-specs`（针对一个 EndpointSpec）

## 12. v1.3 变更（URL 使用 system_name）

v1.2 之前用 `system_id`（自增/UUID）作为 URL path 段，但这增加了不必要的索引一致性维护成本。v1.3 改为 `system_name`：

| 旧 v1.2 | 新 v1.3 |
|---|---|
| `GET /api/systems/{system_id}/tree?depth=2` | `GET /api/systems/{system_name}/tree?depth=2` |
| `GET /api/systems/{system_id}/services/{service}/endpoints?...` | `GET /api/systems/{system_name}/services/{service}/endpoints?...` |
| `POST /api/systems` 返回 `{system_id}` | `POST /api/systems` 返回 `{system_name}` |
| `POST /api/systems/{system_id}/sync` | `POST /api/systems/{system}/system/action/sync` |

**为什么用 name 而非 id**：

1. **schema 对齐** — Plate 当前 `EndpointSpec.system: str`（无独立 system_id），URL 用 name 与 schema 一致
2. **无映射开销** — 不需要维护 `system_id ↔ system_name` 索引
3. **URL 可读** — `/api/systems/fin/tree` 比 `/api/systems/0a3f.../tree` 更直观
4. **改名低频** — 系统注册后基本不动名

**未来需要 system_id 的场景**（当前不需要）：

- 系统要改名不破坏外链
- 多租户隔离（不同租户 system_name 可能重名）
- 与外部系统通过稳定 id 对接

如果后端实现已在用 v1.2 的 system_id，按 v1.3 调整即可。

## 13. 接口 ↔ 页面功能映射

按 14 屏逐一列出每个接口在该屏**支撑的具体功能**。同一接口可能在多屏触发。

---

### Screen 1 · CaseComposerHome（编排任务列表）

| 接口 | 支撑的功能元素 |
|---|---|
| **A1** 列出系统 | 顶部系统筛选下拉（按 system 过滤） |
| A1 | 行内"被测系统"列的 chip 列表（fin / logi / common · 复用 A1 缓存） |
| _（无 Plate 接口）_ | 其余列（名称 / 模块 / 优先级 / 作者 / 步骤数 / 变量数 / 编辑时间）由 Platform 自己存储的 Scenario 读出 |

**不调 Plate 的部分**：列表数据本身（用例名 / 作者 / 时间）从 Platform 自己的存储读，**Plate 不参与列表的 CRUD**。

---

### Screen 2 · 独立 EndpointCatalog（已删除 / 旧场景保留）

> 已被 `CaseComposerCanvasAddStep` 内嵌 CatalogPanel 取代。独立全屏仅在非编排浏览场景使用。

| 接口 | 支撑的功能元素 |
|---|---|
| A1 列出系统 | 顶部"系统 tab"（common / fin / logi / wms / mall） |
| A2 列出 service 树 | 左侧 service / module 树 |
| A3 列出 endpoint | 右侧 endpoint 卡片网格（method + path + tags + 优先级 + 描述） |
| A4 / A4a / A4b | 不调用 — Catalog 不展示字段详情 |
| A5 / B1-B3 | 不调用 — Catalog 不涉及编辑 |
| C1 注册被测系统 | 顶部"+ 注册被测系统"按钮 |

---

### Screen 3 · 独立 EndpointDetail（已删除 / 旧场景保留）

> 已被 `CaseComposerCanvasAddStepDetail` 内嵌 DetailPanel 取代。

| 接口 | 支撑的功能元素 |
|---|---|
| A4 meta-and-api | Hero 区：method / path / 系统 chip / ID chip / tags / Hero 头部 |
| A4 meta-and-api | 成功标准（绿卡） |
| A4 meta-and-api | 失败参考（红卡 · 3 行：401/403/422） |
| A4 meta-and-api | 前置条件（蓝卡） |
| A4 meta-and-api | 业务备注（紫卡） |
| A4a request-spec | 请求字段表（按 ui_kind 渲染控件，缺省按 text） |
| A4a request-spec | "仅 schema 字段"折叠区（Type C 字段） |
| A4b response-specs | 响应字段表（200/400/500 tabs） |
| A4b response-specs | assertable_paths 高亮 ★ |
| B2 failed-criteria-resolved | 每行失败参考的 ✓/○ assertable 标记 |

---

### Screen 4 · CaseComposerCanvas（Scenario ④ 步骤编辑 · 核心）

| 接口 | 支撑的功能元素 |
|---|---|
| **A4a request-spec** | 中间 FieldEditor 主区 — 每个字段的 ui_kind 渲染（text/number/select/textarea/json） |
| A4a request-spec | 字段必填红点 ● / 选填空心 ○（基于 `required: bool`） |
| A4a request-spec | source_kind chip（literal / scenario_var / lookup / generated） |
| A4a request-spec | 仅 schema-only 字段（Type C）识别 + 折叠区 "附带字段 · N" 入口条 |
| **A5 field-defaults** | 字段编辑器加载时填充默认值（张三 / 320 / ${var.bl_no} 等） |
| A5 field-defaults | 字段值 ${var.x} / ${auth.x.token} 模板的初始猜测（用户后续可改） |
| A5 field-defaults | 附带字段（schema-only）默认开启/关闭的初始状态 |
| A4b response-specs | 响应字段表（200/400/500 tabs · AddStepDetail 已有 · Canvas 也复用） |
| **B1 resolve-paths** | 字段框 @ 浮层"上游响应"组的所有候选 path |
| B1 resolve-paths | Auto-Extract 候选 — 未声明 Extract 的 path 显示 ⚠ 标记 |
| **B3 system-from-service** | 左侧 StepList 每个 step 卡片左侧系统色竖条 |
| B3 system-from-service | 左侧 StepList 跨系统步骤间"→ 切换到 X"虚线连接符 |
| B3 system-from-service | 顶部 chip 列表中"fin · logi · common" |
| _（无 Plate 接口）_ | 字段框 4 种视觉标识（literal / static / dynamic / auto-extract）由 Platform 自己计算 |
| _（无 Plate 接口）_ | Strategy 链（Extract / Assign / Assertion）由 Platform 自己保存 |

---

### Screen 5 · CaseComposerCanvasRunner（Scenario ④ 子态 · 运行态）

| 接口 | 支撑的功能元素 |
|---|---|
| _（无 Plate 接口）_ | 进度条（N/M 完成度）由 Platform 自己驱动（运行态由 Platform 调度） |
| _（无 Plate 接口）_ | 步骤响应/请求/断言结果由 Platform 调度 gimbal 后回填 |
| _（无 Plate 接口）_ | 变量轨迹由 Platform 跟踪 Extract / Assign 结果 |

**Runner 不直接调 Plate** — 它依赖 Platform 内部的执行引擎，**Plate 只在编排时参与**（Canvas / AddStepDetail）。

---

### Screen 6 · CaseComposerMeta（Scenario ① 基本信息）

| 接口 | 支撑的功能元素 |
|---|---|
| **A1** 列出系统 | 归属系统 chip 列表 — "归属被测系统"行（多选） |
| A1 | 系统切换器（fin / logi / wms / mall / common） |
| **A6** module-priorities | "模块"下拉选择（order / settlement / refund / logistics） |
| **A6** module-priorities | "优先级"下拉选择（P1 / P2 / P3） |
| **A7** tags | "Tags"输入推荐下拉（按系统聚合的 tag 列表） |
| _（无 Plate 接口）_ | scenarioId / name / description / author / owner / version / requirementRef / expire 由 Platform 自己的存储读 + 写 |

**v2.0 状态**：Meta 调 **A1**（系统列表）。A6（module/priority 下拉）和 A7（tag 推荐）当前**由 Platform 调 A3 聚合**。

---

### Screen 7 · CaseComposerResource（Scenario ② 资源）

| 接口 | 支撑的功能元素 |
|---|---|
| **A8** mock-images | Mock.image 输入下拉数据来源（与被测系统兼容的容器镜像白名单） |
| _（无 Plate 接口）_ | File 列表 / Mock 的 config 和 portMapping 字段是 Platform 自己的存储（Scenario.resource） |

**v2.0 状态**：Resource 调 **A1**（系统）+ **A3**（endpoint 列表）。A8（Mock 镜像白名单）当前**由 Platform 自己维护**。

---

### Screen 8 · CaseComposerConfig（Scenario ③ 配置）

| 接口 | 支撑的功能元素 |
|---|---|
| **A9** policy-presets | “时间策略”radio 选项数据来源（record / timeout 两种） |
| **A9** policy-presets | “重试策略”选项数据来源（默认重试 3 次 / 失败重试 5 次 等预设） |
| _（无 Plate 接口）_ | setup / teardown / services / users / vars 由 Platform 自己的存储读 + 写 |

**v2.0 状态**：Config 调 **A1**（系统）。A9（timePolicy / retry 预设）当前**由 Platform 自己维护**。

---

### Screen 9 · CaseComposerCanvasAddStep（Scenario ④ 子态 · 选接口）

> 内嵌在 Canvas 内（替代原独立 EndpointCatalog）。

| 接口 | 支撑的功能元素 |
|---|---|
| A1 列出系统 | 顶部系统 tab（common / fin / logi / wms / mall） |
| A2 列出 service 树 | 左侧 service / module 树 |
| A3 列出 endpoint | 右侧 endpoint 卡片网格（method + path + tags） |
| _（无 Plate 接口）_ | 步骤流（左侧 StepList）保留 — 不需要 Plate 数据 |

---

### Screen 10 · CaseComposerCanvasAddStepDetail（Scenario ④ 子态 · 详情）

| 接口 | 支撑的功能元素 |
|---|---|
| **A4** meta-and-api | Hero 区：method badge / path code block / 系统 chip / ID / tags / 成功标准 / 失败参考 / 前置条件 / 业务备注 |
| A4 meta-and-api | 失败参考 3 行（401/403/422 · 每行带状态码 chip + 描述 + 失败字段路径） |
| A4 meta-and-api | + 加入到编排画布按钮：触发 Platform 调 A4a + A5 拼 Step + 写入 Scenario |
| **B2** failed-criteria-resolved | 每行失败参考的 ✓ assertable / ○ 未声明 标记 |
| _（无 Plate 接口）_ | "加入后会发生什么"Summary 区域由 Platform 拼 |

---

### Screen 11 · 公共 CaseComposerHome（折叠的"公共编排"Tab）

> 复用 Screen 1 的 1 接口 A1，无额外 Plate 调用。

| 接口 | 支撑的功能元素 |
|---|---|
| A1 列出系统 | 系统筛选下拉（公共 Tab 用同一缓存） |

---

### Screen 12 · 错误状态 / 空状态 / 加载状态

> 所有屏幕通用 — 由 Platform 自己处理，不调 Plate。

| 接口 | 支撑的功能元素 |
|---|---|
| _（无 Plate 接口）_ | loading / empty / error 状态机由 Platform 处理 |

---

## 接口调用次数预估（每个用户使用 30 分钟）

| 接口 | 调用次数 | 备注 |
|---|---|---|
| A1 | 1-3 | 启动 1 + 系统切换 2-3 |
| A2 | 1-2 | 进入 Catalog 1 + 切换系统 1 |
| A3 | 1-3 | 进入 Catalog 1 + 切换 service 1-2 |
| A4 | 1-3 | 进入 AddStepDetail 1-3 次（加多个 step） |
| A4a | 1-10 | 进入 Canvas 1 + 切换 step 1-9 |
| A4b | 1-3 | 进入 AddStepDetail 1 + Canvas Auto-Extract 触发 2 |
| A5 | 1-10 | 进入 Canvas 1 + 切换 step 1-9 |
| B1 | 0-5 | 用户触发 @ 浮层 0-5 次 |
| B2 | 1-3 | 进入 AddStepDetail 1-3 次 |
| B3 | 1-3 | 进入 Meta / Canvas 1-3 次 |
| C1 / C2 | 0 | 管理员操作（普通用户不触发） |

**总调用次数（30 分钟）**：~30-60 次/用户 — 大量重 cache，无压力。

## 14. v1.4 变更（Meta / Resource / Config 结构依赖）

v1.3 之前我错误地把 Meta / Resource / Config 三屏归为"不调 Plate"。实际上：
- **模块 / 优先级**应该从 Plate 已注册系统聚合（A6）
- **Tags**应该从 Plate 已注册系统的 endpoint tags 聚合（A7）
- **Mock 容器镜像**应该从 Plate 的白名单中选（A8）
- **timePolicy / retry 预设**应该从 Plate 的策略集中选（A9）

新增 4 个接口：
- `GET /api/systems/{system_name}/module-priorities` （A6）
- `GET /api/systems/{system_name}/tags` （A7）
- `GET /api/systems/{system_name}/mock-images` （A8）
- `GET /api/policy-presets` （A9）

**接口总数从 12 增至 17**（A 组 4 + B 组 3 + C 组 2）。

如果后端实现参考了 v1.3 之前的版本，按 v1.4 增加这 4 个接口即可。


## 15. v1.5 变更（Scenario → 执行体转换属于 Plate）

v1.4 之前我错误地把"Scenario → gimbal 执行体转换"归到 Platform 职责。**实际上 Plate 负责这个转换**：

- 原因：gimbal 引擎只吃 `model_dump(exclude=...)` 后的纯净 dict（含 endpoints / navigation / config_summary 三个平台视图扩展字段）
- Platform 永远不"知道" gimbal 怎么执行
- **Plate 拥有所有转换知识**（它知道 platform 视图扩展字段怎么生成）
- 这是 `GimbalScenarioExporter.to_dict()` 的职责

**新增 1 个接口（D 组）**：

- `POST /api/scenarios/transform` body `{scenario}` → 返回 gimbal 可执行 dict

**接口总数从 16 增至 17**（A 组 4 + B 组 3 + C 组 2）。

如果后端实现参考了 v1.4 之前，把"Scenario → 执行体转换"从 Platform 移到 Plate。


## 16. v2.0 变更（与 http-api.md M6 对齐）

v1.5 列出 17 个接口。v2.0 把它们按"必要性"重新归类。

---

### 16.1 三档分类（按"是否必须有 Plate 提供"）

| 档 | 含义 | 数量 |
|---|---|---|
| 🟢 **必须** | 没有 Plate 数据，Platform 绝对做不出 | **6** |
| 🟡 **可补偿** | 没有 Plate 数据，Platform 凑合可做（牺牲实时性 / 完整性） | **6** |
| ⚪ **可选 / 自维护** | 没有 Plate 数据，Platform 自己做也合理 | **3** |
| **已存在总计** | | **15** |
| ⏳ **v2.x 必有** | 必须由 Plate 实现，Platform 做不出 | **1**（D1） |
| **完全总计** | | **16** |

---

### 16.2 🟢 必须的 6 个能力（Platform 绝对做不出）

> 这 6 个能力**必须有 Plate 提供**，否则 Platform 启动后什么都做不了。

| 编号 | 能力 | http-api 现状 | 关键原因 |
|---|---|---|---|
| **A1** | 列出已注册被测系统 | ✅ `GET /api/system` | 没注册表，Platform 啥都不知道 |
| **A3** | 列出 endpoint（带筛选） | ✅ `GET /api/endpoint?system=&service=&method=&tag=&q=` | 不知道有哪些接口 |
| **A4** | 单个 endpoint 完整契约 | ✅ `GET /api/endpoint/{id}/full` | 不知道字段定义（schema 知识） |
| **C1** | 注册被测系统 | ✅ `POST /api/system/action/register` | 管理员操作（501 状态） |
| **C2** | 同步结构版本 | ✅ `POST /api/systems/{system}/system/action/sync` | 管理员操作（501 状态） |
| ⏳ **D1** | Scenario → gimbal 执行体 | ❌ v2.x 必须 | 只有 schema 拥有者能做转换 |

**5 个 v2.0 可用 + 1 个 v2.x 必须**——是核心依赖，不能省。

---

### 16.3 🟡 可补偿的 6 个能力（Platform 凑合做）

> 这 6 个能力**没有 Plate 直接提供**的接口，但 Platform 调现有接口 + 本地聚合/计算能凑合做。
> 代价是网络开销大、缓存失效、计算从 Plate 移到 Platform。

| 编号 | 能力 | 凑合做法 | 代价 |
|---|---|---|---|
| A2 | service 树 | 调 A1 + `GET /api/systems/{system}/service` + A3 聚合 | 多次请求 |
| A5 | 字段默认值 | Platform 用 example/default 字段填 | 缺少跨 endpoint 标准化 |
| A6 | module/priority 聚合 | Platform 调 A3 聚合 | 缓存失效需重新聚合 |
| A7 | tags 聚合 | Platform 调 A3 聚合 | 同上 |
| B1 | 响应路径候选 | Platform 从 sample/schema 自己推 | 计算移到 Platform |
| B2 | 失败参考 × assertable 联动 | Platform 调 B2 拿 failed_criteria + A4 拿 assertable_paths，自己交叉 | 同上 |

**v2.0 状态：所有 6 个由 Platform 凑合做**。**v2.x 状态**：A6 / A7 / B1 / B2 可以挪到 Plate（更标准化），A2 / A5 留 Platform 凑合即可。

---

### 16.4 ⚪ 可选 / 自维护的 3 个能力（Platform 自己做也合理）

> 这 3 个能力**没有 Plate 数据来源**。让 Platform 自己维护是合理的——抽象层级不同：
> - Mock 镜像白名单 / 策略预设 = 平台运行时配置（不是被测系统结构）
> - 跨系统归属 = 简单的字符串解析

| 编号 | 能力 | 凑合做法 | 代价 |
|---|---|---|---|
| A8 | Mock 镜像白名单 | Platform 自己维护 | 与 Plate 失去绑定，镜像升级不同步 |
| A9 | 策略预设 | Platform自己维护 | 同上 |
| B3 | 跨系统归属 | `service.split(".")` 解析 | 失去 Plate 抽象的好处 |

**v2.0 状态**：3 个**完全由 Platform 维护**，不依赖 Plate。**v2.x 状态**：可以由 Plate 提供标准化版本（如 A8' mock-images），但**不是必须**。

---

### 16.5 总结：v2.0 必需的能力清单

**Platform 启动 → 显示 CaseComposerHome 列表 + EndpointCatalog 浏览器 + CaseComposerAddStepDetail 编辑 + CaseComposerCanvas 字段编辑器 + CaseComposerCanvasRunner 运行 —— 这 5 个屏幕最少需要 6 个 Plate 接口（A1 + A3 + A4 + C1 + C2 + D1）**：

| 编号 | 用途 | v2.0 状态 | 备注 |
|---|---|---|---|
| A1 | 列出系统 | ✅ v2.0 已有 | 必装 |
| A3 | 列出 endpoint | ✅ v2.0 已有 | 必装 |
| A4 | endpoint 完整契约 | ✅ v2.0 已有 | 必装 |
| A5 | 字段默认值 | ✅ v2.0 已有（Platform 凑合） | 可降级 |
| B1 | 响应路径候选 | ✅ v2.0 已有（Platform 凑合） | 可降级 |
| B2 | 失败参考 × assertable | ✅ v2.0 已有（Platform 凑合） | 可降级 |
| **D1** | Scenario → 执行体转换 | ❌ v2.0 缺，**v2.x 必须** | **核心** |

**5 个 v2.0 阶段必需 + 1 个 v2.x 必需 = 6 个核心接口**。

其他 10 个接口（A2 / A6 / A7 / A8 / A9 / C1 / C2 / B3 + v2.x 增强）是**便利 / 优化 / 完整性**，不是核心依赖。

---

### 16.6 实现优先级建议

| 阶段 | 接口 | 备注 |
|---|---|---|
| **v2.0 必装** | A1 / A3 / A4 / D1 | 核心 4 个，缺一不可 |
| **v2.0 优化** | A5 / B1 / B2 / C1 / C2 | 已有可凑合 / 501 |
| **v2.0 自维护** | A8 / A9 / B3 | Platform 自己做 |
| **v2.x 增强** | A6' / A7' / B2' / A8' / A9' | Plate 抽象增强（聚合 / 白名单 / 联动） |

**接口总数从 v1.5 的 17 压到 v2.0 的 11 个直接可用 + 6 个 v2.x 待实现**。v2.0 阶段 Platform 真的只需要 4 个核心 Plate 接口（+ 3 个便利），其余 3 个 Platform 自己维护。


## 17. v2.0 vs v2.x 总结：当前 Plate 实际能/不能支持的能力

> 你的问题：**"现在其实就是缺一个结构转化的接口，即从适配给平台的用例格式转换为交给gimbal执行的格式"** —— 确认。
>
> v2.0 实际**只缺 1 个 HTTP 端点** —— D1 转换接口。**核心转换逻辑 Plate 已实现**（`GimbalScenarioExporter.to_dict()`），只是没暴露 HTTP 端点。

### 17.1 核心发现

**Plate 已有的转换实现**（`gimbal_plate/export/gimbal.py`）：

```python
# 平台应这样用
from gimbal_plate.schema.scenario import Scenario
from gimbal_plate.export.gimbal import GimbalScenarioExporter

scenario = Scenario.model_validate(platform_dict)  # 1. 平台存的 dict → Scenario
exporter = GimbalScenarioExporter(scenario)       # 2. 包装
gimbal_dict = exporter.to_dict()                  # 3. 转换完成
```

`GimbalScenarioExporter.to_dict()` 做的事：
- 调 `scenario.model_dump(mode="json", exclude_none=True, exclude=...)`
- 排除平台视图扩展字段（endpoints / navigation / config_summary）
- 排除步骤内 view_hints / fields_meta / view_note
- 输出纯 gimbal 可执行 dict

### 17.2 v2.0 实际缺口：仅 1 个 HTTP 端点

| 缺口 | 端点 | 触发 | 影响 |
|---|---|---|---|
| **D1** | `POST /api/scenarios/transform` | `CaseComposerCanvasRunner` "▶ 运行" | Runner 完全无法启动 |

**Plate 应补的端点**（v2.x）：

```python
# 建议在 http-api 新增：
@app.post("/api/scenarios/transform")
def transform_scenario(scenario: dict, request: Request) -> Response:
    scenario_model = Scenario.model_validate(scenario)
    exporter = GimbalScenarioExporter(scenario_model)
    return JSONResponse({
        "ok": True,
        "dim": "scenario",
        "data": {"item": exporter.to_dict()}
    })
```

**实现成本**：< 50 行 Python（`scenario = Scenario.model_validate(body); return GimbalScenarioExporter(scenario).to_dict()`）

### 17.3 v2.0 阶段：其他能力的状态

| 档 | 能力 | v2.0 状态 | 触发屏 |
|---|---|---|---|
| 🟢 必须 + v2.0 可用 | 列出系统 / 列出 endpoint / endpoint 完整契约 / 字段默认值 | ✅ 完整 | Home · Catalog · AddStepDetail · Canvas |
| 🟢 必须 + v2.0 不可用 | **D1 Scenario → 执行体** | ❌ v2.0 缺 | **Runner** |
| 🟡 可补偿 | service 树 / module+priority 聚合 / tags 聚合 / 响应路径候选 / 失败参考联动 | Platform 凑合做 | Catalog · Meta · AddStepDetail |
| ⚪ 自维护 | Mock 镜像白名单 / 策略预设 / 跨系统归属 | Platform 自己维护 | Resource · Config |

### 17.4 v2.0 真正"运行 Runner"的最小 Plate 改造

**只补 1 个端点** —— `POST /api/scenarios/transform`：

```python
# 实现示例（v2.x 应加入 http-api.py）：
from fastapi import Request
from gimbal_plate.schema.scenario import Scenario
from gimbal_plate.export.gimbal import GimbalScenarioExporter

@app.post("/api/scenarios/transform")
def transform_scenario(request: Request) -> dict:
    body = request.json()
    scenario = Scenario.model_validate(body)
    exporter = GimbalScenarioExporter(scenario)
    return {"ok": True, "dim": "scenario", "data": {"item": exporter.to_dict()}}
```

调用示例（Platform → Plate）：
```bash
curl -X POST http://plate/api/scenarios/transform   -H "Content-Type: application/json"   -d @platform_scenario.json
# 返回 gimbal 可执行 dict，直接喂 gimbal 引擎
```

### 17.5 实现优先级（精简版）

| 阶段 | 端点 | 行数 | 价值 |
|---|---|---|---|
| **v2.0 必补** | `POST /api/scenarios/transform` | < 50 行 | 让 Runner 跑起来（**v2.0 唯一缺的能力**） |
| v2.0 不补 | （其他 6 个 v2.x 接口） | 几百行 | 优化 / 标准化 / 减少 Platform 补偿 |
| v2.0 不补 | A8 / A9 | 0 行 | Platform 维持自维护 |

### 17.6 结论

**v2.0 真正缺的就是 1 个端点**（D1 / `POST /api/scenarios/transform`），其他能力 Platform 可以凑合做或自维护。

如果后端实现参考了 v2.0：
- **必补 1 个端点** —— `POST /api/scenarios/transform`（包装 `GimbalScenarioExporter.to_dict()`）
- **可选 5 个 v2.x 端点** —— 聚合 / 白名单 / 预设集 / 联动 / 转换
- **不需要的 3 个** —— A8 / A9 / B3 Platform 自维护
