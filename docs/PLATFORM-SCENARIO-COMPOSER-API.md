# Platform 场景编排 HTTP API（V3 编排 · 1:1/1:N 模型）

> 适用版本：`gimbal-platform` V3 场景编排落地（前端 9 个 Vue 页面 + 4 个共用组件）
> 范围：覆盖 `frontend/src/api/scenario-composer.ts` 的 16 个 client 方法
> 关系文档：`docs/http-api.md`（Plate 一期 M6 路由语法）、`docs/PLATFORM_REQUIREMENTS.md`、`docs/PRD-case-composer.md`
>
> 文档状态：**契约已定 · 后端实现 TODO**。所有 `IMPLEMENTATION STATUS` 字段标注 ⏳ 表示待实现。

---

## 0. 架构定位

```
┌─────────────────────────────────────────────────────────────┐
│  Platform (gimbal-platform) — 组合层                          │
│  • Scenarios / Cases / DataSets / Runs                      │
│  • 1:1 (Scenario↔Case) · 1:N (Case↔DataSet)                 │
│  • 仅做组装 + 存储 + 触发运行,不做结构校验                    │
└─────────────────────────────────────────────────────────────┘
                              │  POST /convert
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Plate (gimbal-plate) — 结构定义层                            │
│  • /api/scenario/action/convert — 一次性组装 + 校验          │
│  • V3.2 meta.system: list[str]（多系统 + common）            │
└─────────────────────────────────────────────────────────────┘
```

**关键约束**：
- Platform **不**前置校验 Scenario 结构,只在最后一步调 Plate `/convert`。
- 1:1 关系：每个 Case 恰好绑定一个 Scenario（`case.scenarioId`）。
- 1:N 关系：一个 Case 可拥有多个 DataSet,每个 DataSet 包含 `rows[]`。
- 校验流向：`Platform 拼 dict → 一次性 POST /api/scenario/action/convert → 失败回前端`。

---

## 1. 基础约定

### 1.1 Base URL

```
http://<host>:<port>/api
```

Platform 默认端口 `8000`,与 Plate `8765` 区分。

### 1.2 认证

所有路由继承现有 `auth.py` 的 Bearer 鉴权：

```http
Authorization: Bearer <access_token>
```

未登录访问 → `401 unauthorized`。`/admin/*` 路由额外要求 `is_admin=true`。

### 1.3 响应信封

**成功**直接返回数据本体（与现有 `cases.py` 一致,**不**嵌套 `data`），便于前端 `http.get<T>('/...')` 直接拿到数组：

```json
[{ ... }, { ... }]
```
或对象：
```json
{ "case_id": "sc-...", "name": "..." }
```

**失败**使用 FastAPI HTTPException，状态码 + `{ "detail": "..." }`：

```json
{ "detail": "scenario 'sc-x' 不存在" }
```

> 与 Plate 的 `{ok, data, error}` 信封**不同**——Platform 沿用 FastAPI 标准错误模型，不引入第二套信封。

### 1.4 错误码与 HTTP status

| HTTP | 触发场景 | 示例 |
| --- | --- | --- |
| 400 | 请求体字段缺失 / 字段值非法 | `scenarioId` 不符合 `^sc-[a-z0-9-]+$` |
| 401 | 缺失 / 过期 access token | Bearer 为空 |
| 403 | 无权修改他人私有场景 | `is_admin=false` 改他人 scenario |
| 404 | 资源不存在 | `GET /api/scenarios/sc-not-exist` |
| 409 | 唯一性冲突 | `scenarioId` 已存在 |
| 422 | 请求体语义被下游拒绝 | 数据集 row 缺字段（行的 keys 与首行不一致）；Plate 拒了 convert（`plate_rejected`，§4.7） |
| 502 | 网关侧调用失败 | Plate 不可达 / 超时（`plate_unavailable`）；`/full` 代理的上游非 200（§10.4） |

---

## 2. 数据模型（JSON Schema 形态）

> 与 `frontend/src/types/scenario-composer.ts` 一一对应；后端 Pydantic 模型放在 `app/schemas/scenario_composer.py`。

### 2.1 Scenario

```json
{
  "meta": {
    "scenarioId": "sc-order-create",
    "name": "订单创建",
    "description": "覆盖订单创建主链路",
    "module": "订单",
    "priority": 1,
    "author": "王",
    "owner": "王",
    "tags": ["smoke", "fin.order"],
    "system": ["fin"],
    "version": "v1.0.0",
    "expire": false
  },
  "steps": [
    {
      "id": "step-001",
      "name": "创建订单",
      "kind": "http",
      "service": "fin-order",
      "method": "POST",
      "endpoint": "/api/v1/orders",
      "headers": { "Content-Type": "application/json" },
      "body": "{ \"qty\": 1 }",
      "expectStatus": 200,
      "extractBindings": [{ "name": "order_id", "path": "$.data.id" }],
      "dependsOn": [],
      "enabled": true
    }
  ],
  "caseCount": 1,
  "dataSetCount": 3,
  "stepCount": 8,
  "tags": ["smoke", "fin.order"],
  "starred": false
}
```

### 2.2 Case

```json
{
  "caseId": "case-001",
  "scenarioId": "sc-order-create",
  "name": "order_create_正常路径",
  "description": "正常 qty=1 路径",
  "env": "test-env-A",
  "auth": { "name": "admin@fin", "type": "bearer" },
  "retry": { "maxAttempts": 0, "intervalMs": 500 },
  "dataSetIds": ["ds-001", "ds-002"],
  "lastRunStatus": "PASS",
  "lastRunAt": "2026-08-12T13:00:00Z",
  "createdBy": "王",
  "updatedAt": "2026-08-12T13:00:00Z",
  "starred": false
}
```

### 2.3 DataSet

```json
{
  "datasetId": "ds-001",
  "caseId": "case-001",
  "name": "正常订单集",
  "description": "qty=1~100 的正常路径",
  "rowCount": 10,
  "rows": [
    { "customer_id": "A001", "qty": 1, "expected_status": 200 },
    { "customer_id": "A002", "qty": 2, "expected_status": 200 }
  ],
  "lastRunStatus": "PASS",
  "lastRunAt": "2026-08-12T13:00:00Z"
}
```

### 2.4 DataSetSummary（列表用）

```json
{
  "datasetId": "ds-001",
  "caseId": "case-001",
  "caseName": "order_create_正常路径",
  "name": "正常订单集",
  "rowCount": 10,
  "lastRunStatus": "PASS",
  "lastRunAt": "2026-08-12T13:00:00Z",
  "preview": [
    { "customer_id": "A001", "qty": 1 },
    { "customer_id": "A002", "qty": 2 }
  ]
}
```

### 2.5 RunEnv

```json
{
  "envId": "test-env-A",
  "name": "test-env-A",
  "baseUrl": "http://test-a.fin.local:8000"
}
```

### 2.6 RunRequest

> 一次执行的配方（recipe）：数据集选择 / 注入条目 / service 绑定全是纯值。
> 旧 `caseId` / `env` / `auths` / `retry` 键**已退役**（Case 层解散、执行环境
> 随 D2 退役、运行级 retry 不做）。旧客户端多发的键**不报 422**：`RunRequest`
> 的 `model_config` 是 `_CAMEL`
> （`ConfigDict(populate_by_name=True, str_strip_whitespace=True)`，
> `scenario_composer.py:28`），**未设 `extra`**，走 pydantic 缺省的
> `ignore`，故只是静默失效。

```json
{
  "scenarioId": "sc-order-create",
  "dataSetSelection": [
    { "datasetId": "ds-001", "rowIndexes": [0, 2] },
    { "datasetId": "ds-002", "rowIndexes": [] }
  ],
  "dataSetIds": ["ds-001"],
  "injectionEntryIds": ["inj-1"],
  "serviceBindings": {
    "fin-order": { "authAlias": "admin@fin", "url": "http://test-a.fin.local:8000" }
  },
  "stepTo": 3,
  "nRuns": 1,
  "parallel": 2
}
```

字段与约束（行内 `:N` 指 `app/schemas/scenario_composer.py`）：

| 字段 | 类型 / 约束 | 说明 |
| --- | --- | --- |
| `scenarioId` | string，正则 `^sc-[a-z0-9-]+$`，3–128 | 必填（`:267-272`） |
| `dataSetSelection` | `DataSetSelection[]`，缺省 `[]` | **行级数据集选择的权威键**（`:276-278`） |
| `dataSetIds` | string[]，缺省 `[]` | **兼容读**：仅在新键缺省（空）时生效（`:274`） |
| `injectionEntryIds` | string[]，缺省 `[]` | 断言注入条目 id（§10.1）；空 = 不注入（`:290-291`） |
| `serviceBindings` | `{service: {authAlias?, url?}}`，缺省 `{}` | 注入清单 = 模板扫描 ∪ 绑定（`:284-286`） |
| `stepTo` | int ≥ 0，可选 | 0-based **含端点**，透传引擎 halt（`:294`） |
| `nRuns` | int，1–1000，缺省 1 | 每行数据的重复执行次数（`:297`） |
| `parallel` | int，1–200，缺省 1 | fan-out 并发度（`:299`） |

`DataSetSelection`（`:207-214`）：`datasetId`（string，1–128）+ `rowIndexes`
（int[]，缺省 `[]`）。**`rowIndexes` 缺省或为空 = 整库**（该数据集全部行）。

**两键同发的优先级**：`dataSetSelection` 是权威键。dispatcher 先按
`dataSetSelection` 归并出「数据集 → 行集」映射，**只有在这个映射为空**
（该键缺省 / 为 `[]`）**时**才回落到 `dataSetIds`（每个 id 记为整库）。即：
只要 `dataSetSelection` 选中了至少一个数据集，`dataSetIds` 就被**整键忽略**
（`run_dispatcher.py:397-411`）。反向的边界是：空 `dataSetSelection` +
非空 `dataSetIds` 仍按旧键执行。

> 执行认证：`serviceBindings[*].authAlias` ∪ 场景模板扫到的 `${auth.*}`
> 引用构成注入清单，dispatcher 按 alias 解密（fernet）后注入**仅 run 副本**
> 的 `Config.users` —— convert 那份不带明文（防凭据流进 plate 校验/日志）。
> headers 里的 `${auth.<alias>.<field>}` 在 Gimbal 运行期解析。执行记录写
> `Execution.config_json.injectedAuths`（数组 = 扫描 ∪ 绑定，
> `run_dispatcher.py:553-558`、`:581`）。

### 2.7 RunResponse

```json
{ "runId": "run-20260812-001", "executionId": 42 }
```

> `executionId` 是本次 dispatch 的数值 Execution 行 id —— 前端据此直接跳
> `/executions/{id}`（字符串 `runId` 自身没有路由）
> （`scenario_composer.py:302-309`）。

### 2.8 PreviewPlateResponse

```json
{
  "ok": true,
  "errors": []
}
```

失败时：
```json
{
  "ok": false,
  "errors": [
    { "path": "steps[3].expectStatus", "message": "期望状态码 200 但收到 422" }
  ]
}
```

---

## 3. 端点总览

| 路径 | 方法 | 角色 | 状态 |
| --- | --- | --- | --- |
| `/api/scenarios` | GET | 列表场景 | ⏳ |
| `/api/scenarios` | POST | 创建场景 | ⏳ |
| `/api/scenarios/{scenarioId}` | GET | 详情 | ⏳ |
| `/api/scenarios/{scenarioId}` | PUT | 更新 | ⏳ |
| `/api/scenarios/{scenarioId}` | DELETE | 删除 | ⏳ |
| `/api/scenarios/{scenarioId}/star` | POST | 收藏 | ⏳ |
| `/api/scenarios/preview-plate` | POST | Plate /convert 预校验 | ⏳ |
| `/api/cases` | GET | 列表用例（跨场景） | ⏳ |
| `/api/cases/{caseId}` | GET | 详情 | ⏳ |
| `/api/cases/{caseId}` | PATCH | 局部更新 | ⏳ |
| `/api/cases/{caseId}` | DELETE | 删除 | ⏳ |
| `/api/data-sets` | GET | 列表（可按 caseId 过滤） | ⏳ |
| `/api/data-sets/{datasetId}` | GET | 详情 | ⏳ |
| `/api/data-sets/{datasetId}` | PUT | 更新 | ⏳ |
| `/api/data-sets/{datasetId}` | DELETE | 删除 | ⏳ |
| `/api/cases/{caseId}/data-sets` | POST | 关联创建 | ⏳ |
| `/api/envs` | GET | 列表执行环境 | ❌ 已退役（D2，`0f136c7`） |
| `/api/runs` | POST | 触发一次运行 | ⏳ |

---

## 4. 详细端点

### 4.1 `GET /api/scenarios`

**角色**：场景库列表（前端 `Scenarios.vue`）  
**权限**：所有登录用户可见

**Query 参数**：

| 名称 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `q` | string | 否 | 模糊匹配 `meta.name` / `meta.scenarioId` / `meta.module` / `meta.description` / `tags[]` |
| `system` | string | 否 | 过滤 `meta.system[]` 包含此值（V3.2 多系统） |
| `module` | string | 否 | 精确匹配 `meta.module` |
| `priority` | int (0–3) | 否 | 精确匹配 `meta.priority` |

**响应**：`200 OK` → `Scenario[]`（见 §2.1）

**示例**：
```bash
curl 'http://localhost:8000/api/scenarios?system=fin&priority=1' \
  -H "Authorization: Bearer <token>"
```

---

### 4.2 `POST /api/scenarios`

**角色**：新建场景（前端 `Scenarios.vue` 「+ 新建场景」按钮）  
**权限**：登录用户

**请求体**：`ScenarioDraft`（无 `caseCount` / `dataSetCount` / `stepCount` / `tags` / `starred`，这些由后端派生）

**字段约束**：

| 字段 | 约束 |
| --- | --- |
| `meta.scenarioId` | 必填，正则 `^sc-[a-z0-9-]+$`；与现有 scenario 唯一 |
| `meta.name` | 必填，1–64 字 |
| `meta.priority` | 必填，枚举 0/1/2/3 |
| `meta.system` | 必填，list[str]，至少 1 个；可选值：`fin` / `logi` / `wms` / `mall` / `common` |
| `meta.tags` | 可选，每条 1–20 字 |
| `meta.expire` | 可选，默认 `false` |
| `meta.version` | 可选，默认 `"v0.1.0"` |
| `steps` | 可选，`[]` 也允许（先建空壳再补步骤） |

**响应**：`201 Created` → `Scenario`（含后端补全的 `caseCount=0`、`stepCount=len(steps)`、`tags`）

**错误**：

- `400 invalid_scenario_id`：scenarioId 不符合正则
- `409 scenario_id_exists`：scenarioId 已被占用

---

### 4.3 `GET /api/scenarios/{scenarioId}`

**角色**：场景详情（前端 `views/CaseComposer.vue:726` 的 `loadScenario` —— 编排页
按 scenarioId 取回整份 `{meta, steps, config, resource}` 重建 `definition`；运行面板
`components/composer/RunPanelHost.vue:115` 同走此端点取展示名 / 步数）

**响应**：`200 OK` → `Scenario`

**错误**：

- `404 scenario_not_found`

---

### 4.4 `PUT /api/scenarios/{scenarioId}`

**角色**：编辑场景  
**权限**：作者本人或 admin

**请求体**：`ScenarioDraft`

**响应**：`200 OK` → `Scenario`（更新后的完整对象）

**错误**：

- `403 not_owner`
- `404 scenario_not_found`
- `409 scenario_id_changed`：禁止改 `scenarioId`（如需变更走 `POST /clone`）

---

### 4.5 `DELETE /api/scenarios/{scenarioId}`

**角色**：删除场景  
**权限**：作者本人或 admin

**级联行为**：删除场景 → 同时删除其下所有 case → 同时删除这些 case 下的所有 data_set（硬删除 + 软删除标记都允许，记录到审计日志）。

**响应**：`204 No Content`

**错误**：

- `403 not_owner`
- `404 scenario_not_found`
- `409 scenario_has_running_runs`：仍有 `status=pending` / `running` 的执行，需先终止

---

### 4.6 `POST /api/scenarios/{scenarioId}/star`

**角色**：收藏 / 取消收藏  
**权限**：登录用户

**请求体**：
```json
{ "starred": true }
```

**响应**：`204 No Content`

**持久化**：与现有 `favorites.json` 同级别文件 `data/stars.json`，结构：

```json
{ "<user_id>": ["sc-xxx", "sc-yyy"] }
```

---

### 4.7 `POST /api/scenarios/preview-plate`

**角色**：把 Platform 拼好的 Scenario dict 一次性交给 Plate `/convert` 校验（前端 `views/CaseComposer.vue:185-188` 的「预校验 Plate」按钮 → `api/scenario-composer.ts:211-219`；列表页的行级导出走同一路径：`views/Scenarios.vue:396` 的 `exportRow` → `stores/scenario-draft.ts:50`）

**请求体**：`ScenarioDraft`

**内部流程**：

1. Platform 拼完整 dict：`{ meta, steps, config: { services, users, timePolicy, retry, vars } }`
2. POST `http://plate-host:8765/api/scenario/action/convert`
3. 把 Plate 的响应包成 `PreviewPlateResponse`

**响应**：`200 OK` → `PreviewPlateResponse`（§2.8）

**错误**：

- `502 plate_unavailable`：Plate 接口调用失败（超时 / 网络错误）
- `422 plate_rejected`：Plate 返回 4xx —— 上游 4xx 是对**客户端草稿**的裁决，不是网关故障，
  故按「输入被拒」报 422 而非 502（`routers/scenarios.py` 的 `preview_plate` 分支注释写明了
  这个取舍：502 会让运维去追一个并不存在的 Plate 故障）；上游 `errors[]` 原样回传

> **同名不同码**：端点目录的 `/full` 代理**也**会发 `plate_rejected`，但那里报 **502**
> （语义是「代理的上游调用失败」，不是「客户端草稿被拒」）—— 见 §10.4。

---

### 4.8 `GET /api/cases`

**角色**：跨场景用例总览（前端 `Cases.vue`） + 场景下用例列表（前端 `CasesOfScenario.vue`）  
**权限**：登录用户

**Query 参数**：

| 名称 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `scenarioId` | string | 否 | 过滤 `scenarioId`（`CasesOfScenario.vue` 用） |
| `q` | string | 否 | 模糊匹配 `name` / `caseId` / `scenarioId` |
| `system` | string | 否 | 透过关联 scenario 的 `meta.system` 过滤 |
| `module` | string | 否 | 透过关联 scenario 的 `meta.module` 过滤 |

**响应**：`200 OK` → `Case[]`（§2.2）

---

### 4.9 `GET /api/cases/{caseId}`

**角色**：用例详情（前端 `CaseEditorBasic.vue`）

**响应**：`200 OK` → `Case`

**错误**：`404 case_not_found`

---

### 4.10 `PATCH /api/cases/{caseId}`

**角色**：局部更新用例（覆盖 env / auth / retry / dataSetIds / name / description）  
**权限**：作者本人或 admin

**请求体**：`Partial<Case>`，**仅允许修改以下字段**：

- `name`
- `description`
- `env`
- `auth.{name, type}`
- `retry.{maxAttempts, intervalMs}`
- `dataSetIds[]`

禁止通过此接口修改 `scenarioId`（绑定关系由 `POST /cases` 创建时确定，删除走 `DELETE` 重建）。

**响应**：`200 OK` → `Case`

---

### 4.11 `DELETE /api/cases/{caseId}`

**角色**：删除用例（前端 `CasesOfScenario.vue` ⋯ → 删除）  
**权限**：作者本人或 admin

**级联**：删除 case → 删除其下所有 data_set。

**响应**：`204 No Content`

---

### 4.12 `GET /api/data-sets`

**角色**：数据集列表（前端 `CaseDataSetsList.vue`）

**Query 参数**：

| 名称 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `caseId` | string | 否 | 过滤 `caseId`（`CaseDataSetsList.vue` 进入时必传） |

**响应**：`200 OK` → `DataSetSummary[]`（§2.4，含前 3 行 preview）

---

### 4.13 `GET /api/data-sets/{datasetId}`

**角色**：单数据集详情（前端 `DataSetEditor.vue`）

**响应**：`200 OK` → `DataSet`（§2.3，含全量 `rows`）

---

### 4.14 `POST /api/cases/{caseId}/data-sets`

**角色**：在 case 下创建数据集（前端 `CaseDataSetsList.vue` 「+ 新建数据集」）  
**权限**：case 的作者或 admin

**请求体**：`DataSetDraft`（§2.3 去掉 `datasetId` / `caseId` / `lastRunStatus` / `lastRunAt`）

**响应**：`201 Created` → `DataSet`（含后端分配的 `datasetId`）

**错误**：

- `404 case_not_found`
- `422 inconsistent_row_columns`：`rows[]` 各行的 keys 必须一致

---

### 4.15 `PUT /api/data-sets/{datasetId}`

**角色**：更新数据集（前端 `DataSetEditor.vue` 保存按钮）

**请求体**：`DataSetDraft`

**响应**：`200 OK` → `DataSet`

---

### 4.16 `DELETE /api/data-sets/{datasetId}`

**角色**：删除数据集  
**权限**：所属 case 的作者或 admin

**响应**：`204 No Content`

---

### 4.17 `GET /api/envs`

**角色**：列出可执行环境 —— **该端点已退役**：执行环境链随 D2 整体删除
（`RunEnv` / `/api/envs` / `envs.yaml` / `envId`，提交 `0f136c7`）。当前后端无该
路由（`app/routers/` 下无 `envs.py`，`schemas/scenario_composer.py` 已无
`RunEnv`），前端亦无调用方。

> 以下原文（响应形状与「静态配置 `app/core/envs.yaml` / 或数据库表 `envs`」的
> 数据来源）描述的是**已删除的实现**：`app/core/envs.yaml`（11 行）与
> `app/services/env_store.py`（39 行）同在上述提交中被删除。保留于此仅为记录
> 历史契约，**不可按现行实现读**。
>
> 原响应形状：`200 OK` → `RunEnv[]`

---

### 4.18 `POST /api/runs`

**角色**：触发一次场景运行（前端运行对话框 `components/composer/RunDialog.vue`；
入口见 `views/CaseComposer.vue:80` 的「运行」与 `views/ScenarioDetailView.vue:36`
的「▶ 立即运行」）  
**权限**：场景的 owner 或 admin，否则 `403 not_owner`（`app/routers/runs.py:62-69`）

**请求体**：`RunRequest`（§2.6）

**响应**：`201 Created` → `RunResponse`（§2.7）。**派发后立即返回** —— 行级执行
跑在后台任务里，进度看 `GET /api/executions/{id}`。

**内部流程**（`app/services/run_dispatcher.py:342-632`）：

1. 优雅关闭窗口内直接拒单（`409 shutting_down`）—— 不建行、不 spawn，
   避免造出「201 返回但永远停在 queued」的僵尸单（`:363-367`）。
2. 载入场景（PK 是字符串 `scenario_id`）→ 查不到 `404 scenario_not_found`
   （`:369-376`）。
3. `stepTo` 校验（仅在显式给出时）：场景无 steps → `404 no_steps`；
   `stepTo >= len(steps)` → `409 step_to_out_of_range`（`:382-391`）。
4. **行级选择归并**（§2.6 的优先级规则）后逐个数据集校验：不存在、或不属于
   该场景 → `404 data_set_not_found`（`:393-420`）。
5. **断言注入条目筛选**（§10）：按 `injectionEntryIds` 选中条目，对每条跑
   悬空检测；悬空的条目 skip + 告警，**绝不炸 dispatch**（`:422-503`）。
6. 建 `Execution` 行（`status=queued`）→ spawn 后台 fan-out → 返回
   `RunResponse`（`:505-632`）。

后台 fan-out 的每 case 链路：`_compose_scenario`（场景定义 + 一行数据，
行值合入 `config.vars`）→ 注入 patch（有选中条目时）→ plate
`POST /api/scenario/action/convert` → `materialize_run_copy`（物化明文
`Config.users`，只进 run 副本）→ 落盘 `case.json` → 子进程
`gimbal run launch <case>`，stdout 的 RunResult 驱动行级计数
（`:636-999`）。

**行级选择归并公式**（代码注释同源，`run_dispatcher.py:393-411`）：

- **段内去重**：同一条目的 `rowIndexes` 取 `sorted(set(...))`（`:400`）；
- **同库多段合并取超集、段序无关**：同一 `datasetId` 出现多段时行集取
  **并集**（`:407`）—— 段在前还是在后不影响结果；
- **整库 ⊇ 任意行集**：任一段的行集为空（= 整库）则整个数据集记为整库，
  与段序无关（`:402-408`）；
- **空数据集 = 隐式基线行**：整库选择下 `rows` 为空的数据集派发一行空行
  `(0, {})`（`:519-522`）。

**交叉矩阵与总量**：派发量 = `Σ 选中行数 × 选中条目数`（无选中条目记 1）
`× nRuns`（`:535-544`）。超过 `MAX_RUNS_PER_EXECUTION`（缺省 200，
`app/core/config.py:59`）→ `409 too_many_runs`（`:545-552`）。**数据集行集为空**
时补一个基线行组合 `(datasetId=None, rows=[(0, {})])`（`:539-540`）—— 故
「什么都不选」是一次合法的基线执行，不是错误。

**有界软取（判定取数不拖住 `/runs` 的同步段）**：

- 悬空判定要读「契约声明面」，来源是 plate `GET /api/endpoint/{id}/full`
  的 `data.item.request.declarations`；**取数归 `plate_client.get_endpoint_full`**
  （进程级 TTL / LRU / 回退窗 / 在飞收敛都在那一层），`endpoint_declarations` 是它
  上面的**派生层**（`declarations_of` / `declared_paths_of` 从同一份 item 派生，
  并另存一份 path 投影）。
- 这条取数是**软取**：只做增强，不是执行的前置条件。它带**自己的短超时**
  `DECLARED_PATHS_TIMEOUT_SEC`（缺省 **3.0 s**，
  `app/core/config.py:100-118`），与 `PLATE_TIMEOUT_SEC`（30 s，`:76`）分离。
  **30 s 那条服务 `convert` 等既有链路（语义是「等不到就报错」），不得改动。**
  该上限落在**共享的**声明面取数（`plate_client.get_endpoint_full`；`endpoint_declarations`
  只是它上面的派生层）上，
  **carry 面同样受它约束**（`declarations_of` 还服务
  `carry_injection.build_carry_context`：后台 fan-out `run_dispatcher.py:748`、
  预览/导出 `routers/scenarios.py:188`）—— 故 carry 面**不只在取数失败时降级，
  plate 慢过 3 s 时也降级**（共享一个有界面的代价，`app/core/config.py:100-118`
  已把这条代价写明）。
- 为什么取数要短：它跑在 `/runs` 的**同步**段里。软取的上限是 3 s，而客户端
  超时是 30 s（`frontend/src/api/http.ts:98`）—— **3 s 远小于 30 s，故同步等待
  有界**。这是设计意图（`app/core/config.py:100-109`）：设计要避免的是两条超时
  线取同值 —— 按该处注释的说法，那样 plate 慢时前端已报失败而后端其实已建出
  执行，用户重试即重复执行。（两个常量可证；该时序本身是设计说明，本文件未
  另行实测。）
- 取数**绝不阻塞执行**（`endpoint_declarations` 的 fail-soft 纪律：任何故障返回 `None`；
  取数层 `plate_client.get_endpoint_full` 绝不抛，失败经 `EndpointFull` 交 `reason`）。拿到
  什么则取决于缓存状态 —— 两条不同的路：
  - **冷缓存**，或**回退窗已过**：拿不到 → 判定**降级从严（只认 body 面）**；
  - **TTL 过期但仍在回退窗内**：刷新失败**回退旧快照**，判定跑在**（可能
    陈旧的）旧契约面**上 —— **不降级、不发 `judgeDegraded`**。该路径**仍会
    告警**，且**带着回退原因**（`plate_client.get_endpoint_full` 的过期分支把
    失败原因放进 `EndpointFull.reason`，`declarations_of` 据此发 `_warn_once`）。
- 成功取到的声明面进**进程内**缓存（TTL `DECLARED_PATHS_TTL_SEC` 缺省 300 s），
  **不是**每次 dispatch 打一次 plate（缓存与打点都在 `plate_client.get_endpoint_full`）。故障期「宁可给一份陈旧，
  也不要静默少带上游的值」是**有意**的语义（`fail-open-to-old`，
  `app/core/config.py:89-99`）；总上界 = TTL + `DECLARED_PATHS_STALE_WINDOW_SEC`
  = 300 s + 3600 s。

**悬空 skip 的可见性（降级时）**：

- 降级期间的跳过记进该次执行的 `Execution.config_json`，两个键：
  `judgeDegraded: true` 与 `entriesSkippedWhileDegraded: [<entryId>, ...]`
  （`run_dispatcher.py:590-594`）。
- **键名如实描述所算**：它记录的是「跳过发生在该步声明面不可得的**时刻**」，
  **跳过的因由不限** —— 与降级无关的 `override-no-match`、写错的 jsonpath
  等一并计入。**它不断言因果**（`:493-497`）。
- **键缺席的含义**：本次执行**没有**发生「降级 + 跳过」的组合 ——
  **不是**「零跳过」（`:591-592`）。
- 对照：端点**真的没有**该声明时取到的是空集而不是 `None`，判定不降级、
  **不留标记**（`declarations_of` 的 `None`（拿不到）/ `[]`（真无声明）契约）。

**错误**（`app/routers/runs.py:76-79` 把 dispatcher 的 `NotFound` / `Conflict`
翻成 404 / 409；`detail` 一律是 `{code, message}` 对象）：

| HTTP | `code` | 触发 |
| --- | --- | --- |
| 403 | `not_owner` | 非场景 owner 且非 admin |
| 404 | `scenario_not_found` | 场景不存在（router 与 dispatcher 同一个 code） |
| 404 | `no_steps` | 给了 `stepTo` 但场景没有 steps |
| 404 | `data_set_not_found` | 选中的数据集不存在或不属于该场景 |
| 409 | `step_to_out_of_range` | `stepTo` ≥ steps 数 |
| 409 | `row_index_out_of_range` | `rowIndexes` 有 `< 0` 或 `>= 该数据集行数` 的下标（`run_dispatcher.py:524-530`） |
| 409 | `too_many_runs` | 派生总量超过 `MAX_RUNS_PER_EXECUTION` |
| 409 | `shutting_down` | 优雅关闭窗口内拒单 |

> **plate / 引擎侧故障不是 HTTP 错误**：fan-out 中途 plate 不可达、plate
> 拒绝、引擎拒绝、launch 超时等一律记进 `Execution` 行与 JSONL，响应仍是
> **201 + runId**（`app/routers/runs.py:15-22`）。

---

## 5. 持久化设计

### 5.1 文件 vs 数据库

Scenario / DataSet / Execution 落 **SQLAlchemy 表**；定义体与配方存在 JSON 列里。
文件面只剩收藏标记与执行审计：

| 资源 | 存储 | 位置 |
| --- | --- | --- |
| `Scenario` | DB 表 | `composer_scenarios`，定义体在 `payload = {definition, orchestration}` JSON 列（`app/models/composer_scenario.py:23`、`:43`） |
| `DataSet` | DB 表 | `composer_data_sets`，行矩阵在 `rows` JSON 列（`app/models/composer_data_set.py:21`、`:34`） |
| `Execution` | DB 表 | `executions`，配方在 `config_json`、场景快照在 `scenario_snapshot`（`app/models/execution.py:35`、`:47`、`:57`） |
| `stars` | JSON 文件 | `data/stars.json`（`app/services/marks_store.py:122`） |
| 行级执行日志 | JSONL 文件 | `data/runs/{YYYY-MM-DD}.jsonl`（追加，`run_dispatcher.py:1349-1350`） |
| 每 run 的 case 快照 | 文件目录 | `data/runs/cases/{runId}/`（`case.json` + 引擎报告，`:1353-1355`） |

> **Case 层已解散** —— 旧的 `Case` 资源不存在了；数据集直接挂在场景上
> （`app/models/composer_data_set.py:4-6`、`app/models/execution.py:7-8`）。
> 下面的 §5.2 / §5.3 是**示意形态**（`payload.definition` 与数据集行的
> 逻辑形状），不是磁盘上的存储形式。

### 5.2 YAML 形态示例（scenario）

```yaml
scenarioId: sc-order-create
meta:
  name: 订单创建
  description: 覆盖订单创建主链路
  module: 订单
  priority: 1
  author: 王
  owner: 王
  tags: [smoke, fin.order]
  system: [fin]
  version: v1.0.0
  expire: false
steps:
  - id: step-001
    name: 创建订单
    kind: http
    service: fin-order
    method: POST
    endpoint: /api/v1/orders
    headers: { Content-Type: application/json }
    body: '{ "qty": 1 }'
    expectStatus: 200
    extractBindings: [{ name: order_id, path: "$.data.id" }]
    dependsOn: []
    enabled: true
```

### 5.3 YAML 形态示例（data-set）

```yaml
datasetId: ds-001
scenarioId: sc-order-create
name: 正常订单集
description: qty=1~100 的正常路径
rows:
  - { customer_id: A001, qty: 1, expected_status: 200 }
  - { customer_id: A002, qty: 2, expected_status: 200 }
```

### 5.4 存储可迁移性约束（SQLite → PostgreSQL）

下面三条与判定面 / 取数缓存 / JSON 列有关。改存储引擎时必须保持
（出处：`docs/superpowers/specs/2026-09-12-architecture-convergence-design.md` §4）。

**约束一：判定面不持久化。** 悬空判定用的「契约声明面」运行时从 plate 契约
派生，**只存在于进程内**（`endpoint_declarations.py` 的 `TtlLruCache` + 在飞
收敛表），不落表、不落字段（该模块 docstring `endpoint_declarations.py:1-58`；
裁决见可注入面 spec §6：「明确选了 dispatch 取 + 缓存，不做快照表/快照字段」）。
`run_dispatcher` 写进 `Execution.config_json` 的是纯值配方 —— `runId` /
`scenarioId` / `dataSetIds` / `dataSetSelection` / `injectedAuths` /
`serviceBindings` / `stepTo` / `nRuns` / `parallel`，外加可选的
`judgeDegraded` / `entriesSkippedWhileDegraded`（`run_dispatcher.py:570-595`）。
该列还会被别的路径追加键：启动期 reconcile 写
`config_json.reconciled`（`:319-323`）；存量历史行另有已退役的旧配方键。
**无论哪条路径，其中都没有任何判定面快照**（`app/models/` 下无**判定面**
快照表/快照字段 —— 已核）。**这里要区分两种「快照」**：`catalog_versions.spec_json`
（`app/models/catalog_version.py:17-25`）确实存了 plate `…/full` 的 `data.item`，
其中**包含** `request.declarations`（写入 `app/services/adaptation_service.py:60-78`、
`:153-156`；读取 `app/services/adaptation_ops.py:31-39`，后者自称
「`CatalogVersion.spec_json` 快照」）—— 但那是**端点契约的版本快照**（派生缓存，
可随时重拉 plate 重建），**不是**本约束所指的判定面（归一化后的 path 集）；
两份 spec 的「不做快照表 / 快照字段」裁定指的也是后者
（`2026-09-12-injectable-path-surface-design.md:116`、
`2026-09-12-architecture-convergence-design.md:128`）。
⇒ PG 迁移不需要为**判定面**写迁移。

**约束二：不依赖 JSON 键序。** 判定与投影一律基于 **Set**，写入一律
`model_dump`；**禁止**任何「按插入序读回」的假设 —— 键序**不由本层保证**
（本层只承诺「不依赖」这个方向；PG 侧列型的实际行为属外部引擎、不在本仓可证
范围）。代码侧落点：可注入面是 `set`（`run_injection.py:128`）、
声明 path 全集是 `frozenset`
（`endpoint_declarations.py:264`）、目录宇宙是 `set`
（`field_state_resolution.py:124-126`）；行集并集是 `set` 运算
（`run_dispatcher.py:400`、`:407`）；写 `config_json` 一律
`model_dump(by_alias=True)`（`:575`、`:584`）；convert memo 的键用
`json.dumps(..., sort_keys=True)`（`:1276-1279`）。

**约束三：显式 null 语义。** `None` / `0` / `""` / `[]` / `False` 一律
**显式判别**，不得用真值（falsy）合并 —— 这是全仓编码约定
（收敛 spec §5）。本仓库既有的同款约定：`carry_binding` 明文「行存在即声明
注入，`value=NULL` 注入 JSON null（显式空）」
（`app/models/carry_binding.py:3`）。代码侧落点：

| 面 | 语义 |
| --- | --- |
| 声明面取数 | 合法空声明 `[]` → 空集（**不是**降级）；只有**拿不到**才是 `None`（`endpoint_declarations.py:55-57`、`:222-232`） |
| 判定面 | `None`（降级）与 `frozenset()`（真无声明）**分别下传**，调用侧显式 `is None` 判别（`run_dispatcher.py:454-458`） |
| `config_json` | `judgeDegraded` **键缺席** ≠ `false`（`run_dispatcher.py:591-592`）；`serviceBindings` 的 `None` 键不落盘（`exclude_none=True`，`:584`） |
| JSONL 回放 | 旧行缺 `injectionId` 键 → 读作 `None`，不炸（`run_dispatcher.py:270-273`） |
| 数据集行 | 缺键 = 继承基线 `config.vars`；`""` = **显式空覆盖**（`run_dispatcher.py:1239-1242`） |

---

## 6. 与 Plate 一期接口的对接

| Platform 端 | Plate 端 | 协议 |
| --- | --- | --- |
| `POST /api/scenarios/preview-plate` | `POST /api/scenario/action/convert` | 拼 dict + 一次性校验 |
| `POST /api/runs` | `POST /api/scenario/action/convert`（Plate）+ `POST /run`（Gimbal runner） | 每行 1 次 convert + 1 次 run |
| 列表 `/scenarios` | `GET /api/scenario/full` | 全量结构 + Platform 元数据合并 |
| 详情 `/scenarios/{id}` | `GET /api/scenario/{id}/full` | 同上 |

**通信机制**：Platform 进程内 `httpx.AsyncClient` 调用 Plate，配置项：

```python
PLATE_BASE_URL: str = "http://127.0.0.1:8765"
PLATE_TIMEOUT_SEC: float = 30.0
```

---

## 7. 实现 TODO（按优先级）

1. ⏳ `app/schemas/scenario_composer.py` — Pydantic 模型（Scenario / Case / DataSet / RunEnv / RunRequest / PreviewPlateResponse）
2. ⏳ `app/services/scenario_store.py` — 文件型 CRUD
3. ⏳ `app/services/case_store.py` — 文件型 CRUD
4. ⏳ `app/services/data_set_store.py` — 文件型 CRUD
5. ⏳ `app/services/plate_client.py` — httpx 包装 Plate `/convert` / `/run`
6. ⏳ `app/services/run_dispatcher.py` — 行级展开 + 调 Plate
7. ⏳ `app/routers/scenarios.py` — §4.1–4.7
8. ⏳ `app/routers/cases.py` — **追加** §4.8–4.11（在现有 `cases.py` 之外或合并均可）
9. ⏳ `app/routers/data_sets.py` — §4.12–4.16
10. ⏳ `app/routers/envs.py` — §4.17
11. ⏳ `app/routers/runs.py` — §4.18
12. ⏳ 在 `app/main.py` 注册以上 router
13. ⏳ 单元测试 `tests/test_scenario_composer_api.py`
14. ⏳ 端到端测试：UI 提交 scenario → 调 Plate → 启动执行 → executions 表可见

---

## 8. 安全 / 审计

- 所有写操作记录到 `data/audit.jsonl`：`{ts, user_id, action, target_type, target_id, payload_hash}`
- 删除走软删除标记 `deleted_at`,默认 7 天后清理（与现有 `cases` 行为一致）
- Plate 凭据：`PLATE_BASE_URL` 不携带 API key（一期 Plate 无鉴权）；如未来加 auth,从 `PLATE_API_KEY` 环境变量读取

---

## 9. 与现有文档的关系

| 现有文档 | 关系 |
| --- | --- |
| `docs/http-api.md` | Plate 一期路由语法；本文件**不重复**，只引用 §4.7 / §6 的对接点 |
| `docs/PLATE-API-SURFACE.md` | Plate 一期 action 列表；本文件假设 V3 `meta.system: list[str]` 已落地（V3.2） |
| `docs/PRD-case-composer.md` | 用例编排产品需求；本文件是其**技术契约** |
| `docs/PLATFORM_REQUIREMENTS.md` | Platform 整体需求；本文件是其中「场景编排」章节的细化 |
| `frontend/src/api/scenario-composer.ts` | 本文件的**前端实现**（一一对应每个端点） |
| `frontend/src/types/scenario-composer.ts` | 与本文件 §2 数据模型一一对应 |

---

## 10. 断言条目与可注入面

> 本节是 §4.18「悬空判定 + 注入物化」的口径来源。实现：
> `app/services/run_injection.py`（纯函数）、`app/services/run_dispatcher.py`
> （接线）、`app/routers/endpoint_catalog.py`（契约面代理）。

### 10.1 断言条目的三元组

一个断言条目是 `{定位 path, 注入值 value, 断言 asserts}` 三元组，外加一个
身份键 `id`：

| 键 | 作用 | 运行时消费点 |
| --- | --- | --- |
| `id` | 条目身份；`RunRequest.injectionEntryIds` 按它选中条目 | `run_dispatcher.py:428`、`:438` |
| `path` | 注入地址；后端读 `{stepIndex, jsonpath}` 两键 | `run_injection.py:222-232` |
| `value` | 写进该地址的字面量（**原样覆写、不 coerce**） | `run_injection.py:276` |
| `asserts[]` | 断言 patch；后端读 `{stepIndex, mode, target, operator?, expected?}` | `run_injection.py:233-242`、`:277-291` |

`stepIndex` 是 **0-based、`definition.steps` 的原始下标**（不填
`steps_from_payload` 的过滤版 —— 过滤版下标会整体错位一位）
（`run_dispatcher.py:433-437`、`:1184-1199`）。

**物化**：`compose_injection_scenario` 在 **plate convert 之前**改**副本**的
`definition.steps[si]`（先 `copy.deepcopy`，`run_injection.py:265` —— 该函数是
纯函数，不改入参）—— 追加一条 `kind=assign` 的策略，target 是
`$.request_body` + jsonpath 尾（根 `"$"` → `$.request_body`）；`asserts[]`
里 `mode == "override"` 的改既有 assertion 的 `expected`，其余追加一条
`kind=assertion`（`run_injection.py:246-292`）。**它不触碰 `config.vars`**：
数据集行值是正交的另一路叠加（§4.18）。

> 三条已知边界（**记录，不是缺陷**）：`value` 为 JSON `null` 无法送达（plate
> 导出会把 `source: None` 整键丢弃，而引擎 `Assign.source` 必填）；整串
> `"${...}"` 形态的 `value` 会被引擎当模板变量解析、平台侧兜不住；
> **`$.` 前缀**的 `value` 若上下文里恰好存在同名 JSONPath，解析命中优先于
> 字面量 —— 该值被上下文值覆写（`run_injection.py:44-65`）。第三条是上面
> 「原样覆写、不 coerce」的反例，故显式列出。

### 10.2 可注入面的定义

某一步的**可注入面**是「哪些 jsonpath 可以锚条目」的判据集合，公式
（`run_injection.py:115-141`）：

```text
body 叶子路径 ∪ 这些叶子的容器前缀
  ∪ normalize(契约声明路径) ∪ 这些前缀
  ∪ {"$"}
```

- **body 叶子**：该步 `request.body` 递归走出的标量叶子，数组带 `[i]` 实例
  下标；**根缺席（无 `request.body`）⇒ 无叶子**；嵌套 JSON `null` 是显式叶子
  （`run_injection.py:83-106`）。
- **容器前缀**：路径的各级容器，按段边界切（`.` 之后 / `[` 之前）——
  `$.a.b` → `['$', '$.a']`；`$.tags[0]` → `['$', '$.tags']`（`:109-112`）。
- **normalize**：声明面一律过 `_template_path` 剥掉数字下标
  （`$.items[0].sku` → `$.items.sku`）—— 契约声明是**模板**路径、条目路径是
  **实例**路径，判定必须两形态都试（`:76-80`、`:169-171`）。
- **`{"$"}`**：根恒可注入。

**判定**：条目 jsonpath 的实例形态**或**模板形态命中该集合即判活；否则退回
`jsonpath.exists(body, path)` 兜底（`run_injection.py:144-172`）。兜底比可注入
面**多认「空容器本身」**（`body={"items":[]}` 的 `$.items`）—— 只会**少判死**，
方向与历史行为一致（`:166-168`）。

**候选面在两处的差异是有意的**（画布的策略路径多一份「用户粘贴的响应样本」，编辑器只有声明面）—— 裁定 M，见 §10.5。

> **已知局限（不在本设计的覆盖范围内，勿读作已支持）**：
> normalize 只吃**数字下标**（正则 `\[\d+\]`，`run_injection.py:73`；前端同款
> `frontend/src/utils/declarations.ts:766`）—— `$.items[*].sku` 这类 **`[*]`
> 写法不被归一**，**无覆盖**。声明面的**模板粒度**边界同理：归一后的模板路径
> 不再区分具体下标，这是**已接受的局限**。两者都将由 `docs/known-issues/`
> 的记录承载（由文档收敛的后续工作建立）。

### 10.3 悬空检查

dispatch 时对每个**被选中**的条目跑 `entry_issues`，产出 issue 列表；
**非空 = 悬空 ⇒ 跳过该条目 + 告警**，绝不炸 dispatch
（`run_dispatcher.py:487-503`）。四类 issue（`run_injection.py:189-243`）：

| kind | 判据 |
| --- | --- |
| `legacy-entry` | `path` 不是 dict（v2 旧形状 `anchor+injection` 或残缺条目） |
| `step-oob` | `path.stepIndex` 归一后越界 / 为负 / 非整数；或某个 `asserts[].stepIndex` 越界 / 为负（**该处归一为 `None` 时不产生 issue** —— 无从寻址，直接跳过） |
| `path-unresolvable` | `jsonpath` 非字符串，或**不落在该步的可注入面上**（§10.2） |
| `override-no-match` | `asserts[]` 里 `mode == "override"` 的 `target` 在该步既有 assertion 策略里找不到 |

`stepIndex` 一律过 `as_step_index`：**拒 `bool`、收整数与整数值浮点**
（`run_injection.py:175-186`），与前端 `Number.isInteger` 同构。

### 10.4 `/endpoint-catalog/{id}/full` 代理职责

平台把 plate 的端点契约代理给前端，让前端只认平台一个 API 面
（`app/routers/endpoint_catalog.py`）：

- **路由**：`GET /api/endpoint-catalog/{endpoint_id:path}/full`，需登录。
- **上游**：`GET {plate}/api/endpoint/{id}/full`，**走 `plate_client.get_endpoint_full`**
  —— 与 §4.18 判定侧那条软取**同一条缓存条目**（同进程内 dispatch 判定与编辑器浏览
  看到同一份快照），故超时也随之统一为 `DECLARED_PATHS_TIMEOUT_SEC`（**3 s** 软取上限，
  不是 `PLATE_TIMEOUT_SEC` 的 30 s）；有缓存（含回退窗内的旧快照）时供上一份契约
  而不是报错。取数层的 TTL/LRU/回退窗/在飞收敛都在 plate_client 那一层。
- **出参**：plate 的 `data.item`（含完整的 `request.declarations`）**原样**透传，
  **另加**一个后端算好的 `declared_surface` —— 声明侧可注入面的**扁平字符串集合**
  （归一化、容器前缀、模板形态全部展开；复用既有纯函数
  `injectable_universe(None, paths)`，未新写投影）。前端据此不再自己推导声明半（§10.2）。
  `declared_surface` 的三种取值（§5 的「不得用真值合并有意义但 falsy 的值」）：
  - **`null`**：该端点的声明面**不可解析**（降级，`declared_paths_of` 返回 `None`）
    ⇒ 前端从严只认 body 面；
  - **`["$"]`**：目录**真无声明**（合法空目录）⇒ 并进来的只有恒在的 `$`；
  - 其余：声明半的完整展开。

  `item` 本身只要是 dict 就原样透传（**空 item `{}` 也算**：它得到空声明树与 `["$"]`，
  不视为错误 —— 不得用真值判等把 `{}` 并成 `None`）。item 另有消费者（候选树 UI），
  故**只增字段、不裁 item**；`declared_surface` 是展开出的新 dict 里的字段，缓存里
  那份 item 是进程级共享只读面，不被就地改写。
- **错误映射**（`routers/endpoint_catalog.py`；状态位取自 `EndpointFull.status`）：
  plate 404 → `404 endpoint_not_found`；**200 但封套里没有可用 `item`**
  （`item is None` 且 `status == 200`）→ `502 plate_invalid_envelope`；
  **其余 4xx → `502 plate_rejected`**（`message` 里带 plate 的真实状态码，形如
  `plate rejected the request (status 401)`）；5xx 或压根没拿到响应 →
  `502 plate_unavailable`。两条纪律：
  1. 映射**嵌在 `item is None` 里** —— 刷新失败时旧快照仍在回退窗内，`item` 是好的
     而 `status` 可能是那次失败的 404，无条件映射会把「健康的旧契约服务」报成
     「端点不存在」；
  2. `plate_rejected` 与 preview/convert 那条**同名不同码**：那里是 **422**（上游 4xx =
     对客户端草稿的裁决，§4.7），这里是 **502**（代理的上游调用失败）。
- 同一路由前缀下另有 `POST /resolve-paths`（响应样本 → 候选 JSONPath）与
  `POST /{id}/field-states/validate`（§3.5 配置编辑校验），后者同样以 `/full`
  取目录，但**自取**（`get_client().get(...)`，不共享 `plate_client` 的缓存），
  错误映射仍用 `routers/strategy_catalog.py` 的 `proxy_error` / `unavailable`
  helper（与 `resolve-paths` 同一套）。

### 10.5 两处「路径候选」的差异是**有意**的（裁定 M）

「候选从哪里来」在两处的口径**不同**，这是阶段二·① 记录下来的裁定，**不是**遗漏：

| | 候选来源 | 触发方式 |
| --- | --- | --- |
| 画布的策略路径字段（`strategy.target` / `extract.expression`） | 端点的**声明面** ∪ 用户**粘贴的响应样本**解析出的路径（`POST /resolve-paths`，§10.4） | 样本路径**由用户显式触发**（点「解析路径」），不是渲染驱动 |
| 断言管理编辑器的 `asserts[].target` | **只有**端点契约的 `assertable` 面（§10.2 的声明半） | 纯缓存读，随判定面一并取数 |

**为什么有意不同**：

1. **服务的对象不同**。画布那条是**运行期表达式**（引擎域 `$.response_body...`），
   「真实响应里到底有什么」比「契约声明了什么」更贴近它的正确性 —— 而契约未声明、
   运行期却真出现的字段（数组下标、动态键）只能靠样本拿；编辑器那条是**断言目标**，
   契约的响应面就是它的唯一标准定义，引入样本等于给同一件事开第二个口径。
2. **样本路径是显式用户动作**。粘贴样本 → 点「解析路径」→ 才产生候选：它**不**在渲染期
   取数，也**不**自动发生（渲染期零请求的纪律因此不受影响）；且候选是**用户自己给的**
   样本的产物，误用风险由用户承担。
3. **不合并的方向已被否决**（编辑器那侧**不**引入样本旁路）：合并会让
   「同一场景里两处判定用的候选集不同」变成「必须解释为什么不同」，而收益只是省一次
   用户动作。约定写进本节，避免后人把这条差异当缺陷修掉。

> 另一处**已评估、不做**的候选差异（编辑器的分层选择器 vs 画布的扁平候选列表）见
> `docs/known-issues/platform/registry/candidate-dropdown-duplication.md`。