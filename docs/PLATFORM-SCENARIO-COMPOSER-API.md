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
| 422 | 数据集 row 缺字段 | 行的 keys 与首行不一致 |
| 502 | Plate /convert 调用失败 | 平台拼好的 dict 被 Plate 拒绝 |

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

```json
{
  "caseId": "case-001",
  "dataSetIds": ["ds-001"],
  "env": { "envId": "test-env-A", "name": "test-env-A", "baseUrl": "http://..." },
  "auths": ["admin@fin", "qa1"],
  "retry": { "maxAttempts": 0, "intervalMs": 500 }
}
```

> `auths`（数组）是执行用认证多选，替代旧的 `auth`（单选字符串，已废）。
> dispatcher 按 alias 解密（fernet）后注入**仅 run 副本**的 `Config.users` —
> convert 那份不带明文（防凭据流进 plate 校验/日志）。headers 里的
> `${auth.<alias>.<field>}` 在 Gimbal 运行期解析。执行记录写
> `Execution.config_json.exec_auth_alias`（与读侧契约对齐；此前误写 `"auth"`
> 导致详情页认证列恒空，已修）。

### 2.7 RunResponse

```json
{ "runId": "run-20260812-001" }
```

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
| `/api/envs` | GET | 列表执行环境 | ⏳ |
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

**角色**：场景详情（前端 `ScenarioEditorMeta/Steps.vue`）

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

**角色**：把 Platform 拼好的 Scenario dict 一次性交给 Plate `/convert` 校验（前端 `CaseEditorBasic.vue` 的 🔍 按钮 + `CaseRunConfig.vue` 的预校验）

**请求体**：`ScenarioDraft`

**内部流程**：

1. Platform 拼完整 dict：`{ meta, steps, config: { services, users, timePolicy, retry, vars } }`
2. POST `http://plate-host:8765/api/scenario/action/convert`
3. 把 Plate 的响应包成 `PreviewPlateResponse`

**响应**：`200 OK` → `PreviewPlateResponse`（§2.8）

**错误**：

- `502 plate_unavailable`：Plate 接口调用失败（超时 / 网络错误）
- `502 plate_rejected`：Plate 返回 4xx，错误详情原样回传

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

**角色**：列出可执行环境（前端 `CaseRunConfig.vue`）

**响应**：`200 OK` → `RunEnv[]`

**数据来源**（实现层）：
- 静态配置 `app/core/envs.yaml`
- 或数据库表 `envs`（id / name / base_url / is_active）

---

### 4.18 `POST /api/runs`

**角色**：触发一次用例运行（前端 `CaseRunConfig.vue` 的 ▶ 提交运行按钮）

**请求体**：`RunRequest`（§2.6）

**内部流程**：

1. 校验 `caseId` 存在、所属 `env` 在 `/api/envs` 中、`dataSetIds[]` 都属于该 case。
2. 计算 `totalRuns = Σ dataSet.rowCount`。
3. 对每行调用 Plate：
   - 拼完整 `Scenario` dict（含行值替换 `vars`）
   - 调 Plate `POST /api/scenario/action/convert`
   - 调 Plate `POST /api/scenario/action/run`（异步；带解密注入的 `Config.users` 副本，见 §2.6 注）
4. 汇总 `runId` 返回。
5. 在 `executions` 表创建一行 `status=pending`。

**响应**：`201 Created` → `RunResponse`（§2.7）

**错误**：

- `404 case_not_found` / `env_not_found` / `data_set_not_found`
- `409 no_data_selected`：未选数据集
- `502 plate_unavailable`：Plate 调用失败

---

## 5. 持久化设计

### 5.1 文件 vs 数据库

Platform 当前后端（`cases.py`）以文件 + JSON 为持久化（与一期 Plate 对齐）。V3 场景编排建议：

| 资源 | 存储 | 路径 |
| --- | --- | --- |
| `Scenario` | 文件 | `data/scenarios/{scenarioId}.yaml` |
| `Case` | 文件 | `data/cases/{caseId}.yaml` |
| `DataSet` | 文件 | `data/data-sets/{datasetId}.yaml` |
| `stars` | JSON | `data/stars.json`（同 `favorites.json` 模式） |
| `runs` | JSONL | `data/runs/{YYYY-MM-DD}.jsonl`（追加；与现有 `executions` 表并行记录） |

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
caseId: case-001
name: 正常订单集
description: qty=1~100 的正常路径
rows:
  - { customer_id: A001, qty: 1, expected_status: 200 }
  - { customer_id: A002, qty: 2, expected_status: 200 }
```

---

## 6. 与 Plate 一期接口的对接

| Platform 端 | Plate 端 | 协议 |
| --- | --- | --- |
| `POST /api/scenarios/preview-plate` | `POST /api/scenario/action/convert` | 拼 dict + 一次性校验 |
| `POST /api/runs` | `POST /api/scenario/action/convert` + `POST /api/scenario/action/run` | 每行 1 次 convert + 1 次 run |
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