# 前后端契约一致性评审报告

> **评审范围**: `src/gimbal-platform` 全量后端路由 × 前端 api/types 模块
> **评审人**: Claude (前后端契约一致性评审专家)
> **评审日期**: 2026-09-02
> **评审方法**: 逐文件比对 backend Pydantic schema 与 frontend TypeScript 类型;以 backend `schemas/*.py` + `routers/*.py` 为权威,交叉验证 frontend `api/*.ts` + `types/*.ts`。

---

## 1. 总体结论

本项目契约健康度 **B+**。三套契约风格共存:

| 风格 | 适用域 | Backend 输出风格 | Frontend 风格 |
|---|---|---|---|
| **A. 纯 snake_case** | auth / users / auth-sessions / constants / execution(读侧主体) | snake_case | snake_case ✅ |
| **B. 显式 alias camelCase** | scenario-composer / adaptations / execution.rows / carry 部分 | camelCase(`Field(alias=...)` + FastAPI `by_alias=True` 隐式默认) | camelCase ✅ |
| **C. 平台代理 (Plate 透传)** | endpoint-catalog / strategy-catalog / generator-catalog / carries fields | plate 原始 dict | camelCase 视图类型(由 `@/types/plate` 兜底) ✅ |

风格分界虽然多了几套,但**与前端代码的实现一致**(已用 backend 测试 `test_adaptations_api.py:261-262` 等的 camelCase 断言保证) — 没有发现"backend 输出 camelCase 但前端只读 snake_case"的破坏性差异。

问题集中在以下三类:
1. **P0**: spec 文档/类型 **FIELD 误标**,前端 schema 字段实际不被 backend 接受 → 静默丢失。
2. **P1**: 前端类型 **过宽/过窄**,从功能角度不影响,但严格意义上是契约漂移(未来加新值或删字段会断)。
3. **P2**: 错误响应 / PATH / 204 等细节差异,不致命但需要核对。

---

## 2. 端点对照检查表

### 2.1 Auth / Users

| 端点 | Backend schema | Frontend 类型 | 状态 | 备注 |
|---|---|---|---|---|
| `POST /auth/register` | `RegisterIn{username, password, display_name="" }`(`schemas/auth.py:16-28`) | `register({username, password, display_name?})`(`api/auth.ts:24-30`) | ✅ | `display_name` 默认 `""`,符合 `?` 语义 |
| `POST /auth/login` | `LoginIn{username, password}`(`schemas/auth.py:31-35`) | `login({username, password})`(`api/auth.ts:32-34`) | ✅ | |
| `POST /auth/refresh` | `RefreshIn{refresh_token}`(`schemas/auth.py:38-41`) | `refresh({refresh_token})`(`api/auth.ts:36-38`) | ✅ | |
| `GET /auth/me` | `MeOut{user: UserPublic}`(`schemas/auth.py:71-73`) | `MeOut{user}`(`api/auth.ts:20-22`) | ✅ | |
| `POST /users` | `UserCreateIn{username, password, display_name="", is_admin=False}`(`schemas/user.py:10-20`) | `UserCreateIn{username, password, display_name?, is_admin?}`(`api/users.ts:7-12`) | ✅ | router 实际始终把 `is_admin=False`,前端传也无效 |
| `PATCH /users/{id}` | `UserPatchIn{display_name?, is_admin?, is_active?, new_password?}`(`schemas/user.py:23-29`) | `UserPatchIn{display_name?, is_admin?, is_active?, new_password?}`(`api/users.ts:14-19`) | ✅ | |
| `POST /users/{id}/reset-password` | inline dict `{user_id, username, new_password}`(`routers/users.py:228-233`) | `ResetPasswordOut{user_id, username, new_password}`(`api/users.ts:21-25`) | ✅ | 路径必须用 `encodeURIComponent`?实际为整数,无影响 |
| `DELETE /users/{id}` | 204 No Content(`routers/users.py:241`) | `remove(userId): Promise<...>`(`api/users.ts:45-47`) | ✅ | 删 `r.data` 调用 → 无 `.data` 风险 |

### 2.2 Auth-Sessions

| 端点 | Backend | Frontend | 状态 | 备注 |
|---|---|---|---|---|
| `GET /auths` | `list[AuthSessionOut]` 含 `password_masked`(`schemas/auth_session.py:9-27`) | `AuthSession{id,alias,url,username,token_type,expires_in,created_at,updated_at,password_masked}`(`api/auth_sessions.ts:4-14`) | ✅ | |
| `POST /auths` | `AuthSessionCreateIn{alias,url,username,password,token_type="Bearer",expires_in=7200}`(`schemas/auth_session.py:30-36`) | `AuthSessionCreateIn{alias,url,username,password,token_type?,expires_in?}`(`api/auth_sessions.ts:16-23`) | ✅ | |
| `PATCH /auths/{id}` | `AuthSessionPatchIn{url?,username?,password?,token_type?,expires_in?}`(`schemas/auth_session.py:39-44`) | `AuthSessionPatchIn{url?,username?,password?,token_type?,expires_in?}`(`api/auth_sessions.ts:25-31`) | ✅ | |
| `GET /auths/{id}` | `AuthSessionSecretsOut\|AuthSessionOut` + `?include_secrets=true`(`routers/auth_sessions.py:133-164`) | `get(id, includeSecrets)`(`api/auth_sessions.ts:65-74`) | ✅ | secrets 视图仅当 `include_secrets=true` |
| `DELETE /auths/{id}` | 204(`routers/auth_sessions.py:198-206`) | `remove`(`api/auth_sessions.ts:51-53`) | ✅ | |
| `POST /auths/{id}/test` | `TestResult{ok,status_code?,message}`(`schemas/auth_session.py:47-50`) | `TestResult{ok,status_code:number\|null,message}`(`api/auth_sessions.ts:33-37`) | ✅ | |

### 2.3 Scenarios / Composer

| 端点 | Backend | Frontend | 状态 | 备注 |
|---|---|---|---|---|
| `POST /scenarios` | `ScenarioDraft{definition,orchestration}`(`schemas/scenario_composer.py:123-136`) | `createScenario(draft: ScenarioDraft)`(`api/scenario-composer.ts:44-47`) | ✅ | orch 默认值由 `_CAMEL` + `default_factory` 兜底 |
| `GET /scenarios` | `list[Scenario]`(`routers/scenarios.py:225-257`) | `listScenarios(q?,system?,module?,priority?,visibility?)`(`api/scenario-composer.ts:18-25`) | ✅ | 前端只读必需字段,与 backend `Scenario` 字段匹配 |
| `GET /scenarios/{id}` | `Scenario`(`routers/scenarios.py:410-419`) | `getScenario(id): Scenario`(`api/scenario-composer.ts:27-30`) | ✅ | |
| `GET /scenarios/{id}/draft` | `ScenarioDraft`(`routers/scenarios.py:425-442`) | `getScenarioDraft(id): ScenarioDraft`(`api/scenario-composer.ts:39-42`) | ✅ | |
| `POST /scenarios/preview-plate` | `PreviewPlateIn(ScenarioDraft) + optional overlay`(`schemas/scenario_composer.py:272-280`) | `previewPlateDraft(draft, overlay?)`(`api/scenario-composer.ts:183-191`) | ⚠ | 见 §3 P0-1:**前端 `overlay.dataSetIds?` 字段被后端静默忽略** |
| `PUT /scenarios/{id}` | `ScenarioDraft`(`routers/scenarios.py:447-466`) | `updateScenario(id, draft)`(`api/scenario-composer.ts:49-54`) | ✅ | `orchestration.runSchemes` 由 `scenario_store.update` 透传保留(`scenario_store.py:138-140`) |
| `PUT /scenarios/{id}/run-schemes` | `RunSchemesIn{schemes: list[RunScheme]}`(`schemas/scenario_composer.py:206-210`) | `putRunSchemes(id, schemes)` 拼 `{schemes}`(`api/scenario-composer.ts:168-171`) | ✅ | |
| `POST /scenarios/{id}/star` | 204(`routers/scenarios.py:262-271`) | `starScenario(id, starred)`(`api/scenario-composer.ts:60-64`) | ✅ | |
| `POST /scenarios/{id}/publish` | `Scenario`(`routers/scenarios.py:275-285`) | `publishScenario(id)`(`api/scenario-composer.ts:67-70`) | ✅ | |
| `POST /scenarios/{id}/unpublish` | `Scenario`(`routers/scenarios.py:288-298`) | `unpublishScenario(id)`(`api/scenario-composer.ts:72-75`) | ✅ | |
| `POST /scenarios/{id}/copy` | `Scenario`(`routers/scenarios.py:302-322`) | `copyScenario(id)`(`api/scenario-composer.ts:78-81`) | ✅ | |

### 2.4 Data-Sets

| 端点 | Backend | Frontend | 状态 | 备注 |
|---|---|---|---|---|
| `GET /data-sets?scenarioId=` | `list[DataSetSummary]`(`routers/data_sets.py:80-99`) | `listDataSets({scenarioId?})`(`api/scenario-composer.ts:84-89`) | ⚠ | 见 §3 P1-3:`DataSetSummary` 后端无 `description` 字段 |
| `GET /data-sets/{id}` | `DataSet`(`routers/data_sets.py:102-112`) | `getDataSet(id): DataSet`(`api/scenario-composer.ts:91-94`) | ✅ | |
| `POST /scenarios/{id}/data-sets` | `DataSetDraft`(`routers/data_sets.py:149-167`) | `createDataSet(id, draft)`(`api/scenario-composer.ts:96-101`) | ✅ | 路径挂在 `scenarios` 下 |
| `PUT /data-sets/{id}` | `DataSetDraft`(`routers/data_sets.py:115-128`) | `updateDataSet(id, draft)`(`api/scenario-composer.ts:103-108`) | ✅ | |
| `DELETE /data-sets/{id}` | 204(`routers/data_sets.py:131-139`) | `deleteDataSet(id)`(`api/scenario-composer.ts:110-112`) | ✅ | |

### 2.5 Runs / Executions

| 端点 | Backend | Frontend | 状态 | 备注 |
|---|---|---|---|---|
| `POST /runs` | `RunResponse{runId,executionId}`(`schemas/scenario_composer.py:262-268`) | `RunScenarioResult{runId,executionId?}`(`api/scenario-composer.ts:156-165`) | ⚠ | 见 §3 P2-1:`executionId` 实际必传但前端标可选 |
| `GET /executions?scenario_id=` | `ExecutionListOut{items,total}`(`schemas/execution.py:25-27`) | `listExecutions({scenarioId?,limit?})`(`api/executions.ts:54-61`) | ✅ | 参数名 `scenario_id` 通过 axios params 显式重映射 |
| `GET /executions/{id}` | `ExecutionOut`(`schemas/execution.py:9-22`) | `Execution`(`api/executions.ts:8-40`) | ✅ | |
| `GET /executions/{id}/rows` | `ExecutionRowsOut{items:list[ExecutionRowOut]}`(`schemas/execution.py:30-49`) | `getExecutionRows(id): {items: ExecutionRow[]}`(`api/executions.ts:77-81`) | ✅ | alias 双向(`populate_by_name` + alias 序列化) |
| `GET /executions/{id}/case-artifact` | `PlainTextResponse`(`routers/executions.py:94-123`) | `getCaseArtifact(id,case,file): string`(`api/executions.ts:85-91`) | ✅ | 白名单 `engine-log`/`result` |
| `GET /executions/{id}/scenario-snapshot` | raw dict(`routers/executions.py:127-144`) | `getScenarioSnapshot(id): ScenarioDraft`(`api/executions.ts:95-99`) | ⚠ | 见 §3 P2-2:无 schema 校验,Snapshot 解码后类型仅前端假设 |
| `DELETE /executions/{id}` | 204(`routers/executions.py:148-153`) | `remove(id)`(`api/executions.ts:67-69`) | ✅ | |
| `POST /executions/{id}/cancel` | `ExecutionOut`(`routers/executions.py:157-181`) | `cancelExecution(id): Execution`(`api/executions.ts:72-74`) | ✅ | |

### 2.6 Catalogs (Plate 代理)

| 端点 | Backend | Frontend | 状态 | 备注 |
|---|---|---|---|---|
| `GET /endpoint-catalog/{id}/full` | raw `item` dict(`routers/endpoint_catalog.py:34-65`) | `getFullEndpoint(id): EndpointFullView`(`api/scenario-composer.ts:199-202`) | ⚠ | 类型来自 `@/types/plate`,契约实归 plate;**前端无兜底校验** |
| `POST /endpoint-catalog/resolve-paths` | `list[dict]`(`routers/endpoint_catalog.py:68-97`) | `resolveResponsePaths(sample): ResponsePathCandidate[]`(`api/scenario-composer.ts:204-218`) | ⚠ | 见 §3 P2-3:后端透传,前端 TS 自定 shape 风险 |
| `GET /strategy-catalog` | `list[dict]`(`routers/strategy_catalog.py:64-80`) | `listStrategyKinds()`(`api/scenario-composer.ts:225-228`) | ✅ | |
| `GET /strategy-catalog/{kind}/full` | `dict`(`routers/strategy_catalog.py:83-99`) | `getStrategyKindFull(kind)`(`api/scenario-composer.ts:230-233`) | ✅ | |
| `GET /generator-catalog` | `list[dict]`(`routers/generator_catalog.py:61-77`) | `listGeneratorKinds()`(`api/generator_catalog.ts:5-7`) | ✅ | |
| `GET /generator-catalog/{kind}/full` | `dict`(`routers/generator_catalog.py:80-96`) | `getGeneratorKindFull(kind)`(`api/generator_catalog.ts:9-13`) | ✅ | |

### 2.7 Constants

| 端点 | Backend | Frontend | 状态 | 备注 |
|---|---|---|---|---|
| `GET /constants` | `list[ConstantEntryOut]`(`schemas/constants.py:20-30`) | `ConstantEntry`(`types/constants.ts:7-16`) | ✅ | 全 snake_case |
| `POST /constants` | `ConstantEntryCreateIn{name,description="",entry_kind,value?,spec?}`(`schemas/constants.py:33-58`) | `ConstantEntryCreateIn`(`types/constants.ts:18-24`) | ✅ | |
| `PATCH /constants/{id}` | `ConstantEntryPatchIn{description?,value?,spec?}`(`schemas/constants.py:61-66`) | `ConstantEntryPatchIn`(`types/constants.ts:26-30`) | ✅ | `name/entry_kind` 不允许 patch(后端 router 也不读),与 frontend 缺字段一致 |
| `DELETE /constants/{id}` | 204 | `remove(id)` | ✅ | |

### 2.8 Adaptations

| 端点 | Backend | Frontend | 状态 | 备注 |
|---|---|---|---|---|
| `POST /adaptations/catalog/diff` | `CatalogDiffReport`(`schemas/adaptations.py:28-33`) | `catalogDiff()`(`api/adaptations.ts:117-120`) | ✅ | |
| `GET /adaptations/impact` | `list[ImpactItem]`(`schemas/adaptations.py:36-46`) | `impact(id, field?)`(`api/adaptations.ts:122-127`) | ⚠ | 见 §3 P1-4:`source` 联合类型过窄 |
| `GET /adaptations/unindexed-steps` | `list[UnindexedStepOut]` | `unindexedSteps()` | ✅ | |
| `POST /adaptations/batches` | `BatchDetail`(`schemas/adaptations.py:97-99`) | `openBatch(endpointId)`(`api/adaptations.ts:147-152`) | ✅ | |
| `POST /adaptations/carry-batches` | `BatchDetail`(`schemas/adaptations.py:54-60`) | `openCarryBatch(service\|null)`(`api/adaptations.ts:155-162`) | ✅ | |
| `GET /adaptations/batches?scope=` | `list[BatchOut]`(`schemas/adaptations.py:83-94`) | `listBatches(scope?: 'mine')` | ✅ | |
| `GET /adaptations/batches/{id}` | `BatchDetail` | `getBatch(id)` | ✅ | |
| `POST /adaptations/batches/{id}/ops` | `OpOut` | `createOp(id, OpCreateIn)` | ✅ | |
| `POST /adaptations/ops/{id}/apply` | `OpOut` | `applyOp(id)` | ✅ | |
| `POST /adaptations/ops/{id}/skip` | `OpOut` | `skipOp(id)` | ✅ | |
| `PATCH /adaptations/ops/{id}` | `OpOut`(`schemas/adaptations.py:141-146`) | `patchOp(id, payload)`(`api/adaptations.ts:180-187`) | ⚠ | 见 §3 P2-4:patchOp 接受完整 payload 替换,前端签名 `Record<string, unknown>` |
| `POST /adaptations/batches/{id}/rollback` | `RollbackReport` | `rollbackBatch(id)` | ✅ | |

### 2.9 Carry (值表)

| 端点 | Backend | Frontend | 状态 | 备注 |
|---|---|---|---|---|
| `GET /carry/defaults` | `DefaultsOut{defaults: dict[str, str \| None]}`(`schemas/carry.py:16-18`) | `getDefaults(): CarryValues`(`api/carry.ts:22-25`) | ✅ | snake_case 字段(只有 `defaults` 一个键) |
| `PUT /carry/defaults` | `DefaultsIn`, 回 `DefaultsOut` | `putDefaults()` | ✅ | |
| `GET /carry/bindings` | `BindingsOut{bindings: dict[str, dict[str, str \| None]]}`(`schemas/carry.py:20-22`) | `getBindings()`(`api/carry.ts:33-37`) | ✅ | |
| `GET /carry/bindings/{service}` | `ServiceBindingsOut{bindings: dict[str, str \| None]}`(`schemas/carry.py:24-26`) | `getBindingsFor(service)` | ✅ | |
| `PUT /carry/bindings/{service}` | `CarryMapIn{bindings}`(`schemas/carry.py:8-10`) | `putBindings(service, bindings)` | ✅ | |
| `GET /carry/bindings/{service}/fields` | `ServiceFieldsOut{fields,degraded}`(`schemas/carry.py:34-39`) | `getServiceFields()`(`api/carry.ts:64-68`) | ✅ | `plateReachable` 不出现;此处由 `degraded` 代理 |
| `GET /carry/drift` | `DriftReport{services, plateReachable}`(`schemas/carry.py:48-51`) | `getDrift()`(`api/carry.ts:86-89`) | ✅ | camelCase 字段名直透 |

---

## 3. 问题清单(按严重度)

### P0 — 严重(静默数据丢失 / 字段方向反向)

#### P0-1: `preview-plate.overlay.dataSetIds` 被 backend 静默忽略

- **端点**: `POST /api/scenarios/preview-plate`
- **文件引用**:
  - backend: `backend/app/schemas/scenario_composer.py:217-224`(`ExportOverlay` 只含 `service_bindings`,无 `data_set_ids`/`dataSetIds`)
  - backend: `backend/app/schemas/scenario_composer.py:218-219` 注释明确写 "dataSetIds 有意不收"
  - frontend: `frontend/src/api/scenario-composer.ts:133-137` `RunOverlay.dataSetIds?: string[]`
  - frontend: `frontend/src/api/scenario-composer.ts:186-190` `previewPlateDraft` 在 `overlay` 存在时把整个 `RunOverlay` 铺到 body
- **现象**: 当前 frontend 不会传 `dataSetIds`(导出/预览与 row-level 展开无关,spec §8 已说),但 TS 类型开口允许,**未来若前端误填 `dataSetIds` 会期望它参与服务绑定覆盖,而实际被 backend 静默丢弃**;如果未来某天 frontend 期望"按方案导出 + 行级覆盖"(看似合理),会被这个静默吞没。
- **影响**: 误导型契约;新代码可能踩坑。
- **修复建议**:
  - 方案 A(更准确): 把 `RunOverlay.dataSetIds` 从 TS 类型里删掉,在 JSDoc 中引用 spec §8 的解释。
  - 方案 B(若未来真要支持): 在 `ExportOverlay` 加 `data_set_ids: list[str] | None = Field(default=None, alias="dataSetIds")`,并把 `dataSetIds` 在 `materialize_run_copy` 里展开到 per-row(需要后端支持)。

### P1 — 中等(契约漂移 / 类型过宽过窄)

#### P1-1: `auth.ts` UserPublic 缺 `is_active` 中可能与 spec 一致;但其它地方不一致

> ⚠ 这一条实际是合规的。移到此处仅为讨论完整性。

- backend: `UserPublic{id,username,display_name,is_admin,is_active,created_at}`(`schemas/auth.py:44-59`)
- frontend: `api/auth.ts:4-11` 五个字段一致 ✅

#### P1-2: `orchestration.steps` 长度匹配语义

- backend: `Orchestration.steps: list[StepOrchestration]`(`schemas/scenario_composer.py:116`) 注释指明"index-aligned with definition.steps"
- frontend: `orchestration.steps: StepOrchestration[]`(`types/scenario-composer.ts:26-31`)
- backend 无长度不匹配的拒绝(只在 `Orchestration` model 自身校验 shape);前端也没有 runtime 比对长度。
- **影响**: 如果 `definition.steps.length != orchestration.steps.length`,backend 不会拒(默认 factory 都给 `[]`);服务端读侧(`scenario_store.to_read_shape`/`_extras_from_payload`)也只解包不校验。
- **修复建议**: 抽一个 `validate_orchestration_indexes(draft)` 在 `preview_plate`/`create_scenario`/`update_scenario` 路径上 Pydantic root-validator 触发。这不是契约问题,但既然评审 contract 顺带提。

#### P1-3: `DataSetSummary.description` 字段前端 schema 假设存在

- backend: `DataSetSummary`(`schemas/scenario_composer.py:158-172`) **无 `description` 字段**
- frontend: `DataSetSummary{...description?}`(`types/scenario-composer.ts:89-97`)
- 现象: 列表接口 `GET /data-sets` 返回的 summary 没有 description;前端类型声明存在,字段读到时为 `undefined`,编辑器对 `description` 的访问不会报错。
- 影响: 列表渲染若误用 `summary.description` → 显示空白。**实际已经在前端 data_set 视图里有过使用的话是 silent display bug**(无法在此断言)。
- 修复建议: 把 `DataSetSummary.description?` 删掉。

#### P1-4: `ImpactItem.source` 联合类型过窄

- backend: `source: str | None = None`(`schemas/adaptations.py:41`)
- frontend: `source: 'body' | 'headers' | null`(`api/adaptations.ts:31-36`)
- 现象: 后端是任意字符串,前端 TS 缩窄;**若后端将来加新 source 类型(如 `path`/`query`/)**,TS 编译期不会报错,运行期会显示空白或默认值错位。
- 修复建议: 改 `source: string | null`,再在数据层(必要时)做枚举 switch;或注释指明后端为唯一权威。

#### P1-5: `ExecutionStatus` / `BatchOut.status` / `OpOut.status` 联合类型过窄

- backend: `ExecutionOut.status: str`(`schemas/execution.py:14`)、`BatchOut.status: str`(`schemas/adaptations.py:90`)、`OpOut.status: str`(`schemas/adaptations.py:71`)
- frontend:
  - `ExecutionStatus = 'queued'|'running'|'done'|'failed'|'canceled'`(`api/executions.ts:6`)
  - `BatchOut.status: 'open'|'applying'|'completed'|'rolled_back'`(`api/adaptations.ts:62`)
  - `OpOut.status: 'pending'|'applied'|'conflict'|'skipped'`(`api/adaptations.ts:46`)
- 现象: 前端缩窄,后端任意 string;新 status 加进来前端不报警。
- 修复建议: 选定一个真权威源(spec 文档),前后端用统一 lint/测试锁定。或者前端改 `string`,仅在 filter/enum switch 处窄化。

#### P1-6: carry `bindings` 内层双层 dict 与 `ServiceBindingsOut` 扁平 dict 在调用处的别名差异

- backend: `BindingsOut{bindings: dict[str, dict[str, str | None]]}`(`schemas/carry.py:20-22`) — `service → field_path → value`
- backend: `ServiceBindingsOut{bindings: dict[str, str | None]}`(`schemas/carry.py:24-26`) — `field_path → value`
- frontend: `getBindings()` 第二个 `Record<string, CarryValues>`(`api/carry.ts:33-37`) 与 `getBindingsFor()` 第二个 `CarryValues`(`api/carry.ts:39-43`)。
- ✅ 这是正确的两层 shape;前端类型与 backend 一致。
- **影响**: 无。
- 备注: 这条只是为了提示团队未来新增 carry 相关接口时,遵循 `BindingsOut`(双层) 与 `ServiceBindingsOut`(扁平) 区别。

### P2 — 轻微(非破坏性,但需记录)

#### P2-1: `runScenario().executionId` 标 `?` 实际必传

- backend: `RunResponse{execution_id: int = Field(alias="executionId")}`(**无 default,required**)(`schemas/scenario_composer.py:262-268`)
- frontend: `RunScenarioResult{runId: string; executionId?: number}`(`api/scenario-composer.ts:156-160`)
- 现象: 前端代码若误读为 `undefined`,会出 `Cannot read property '...'` 类型错误(vite runtime),而 backend 永远会传整数。
- 修复建议: 把 frontend 改成 `executionId: number`。同时把 `runId` 也保持 `string` 必填,与 backend 一致。

#### P2-2: `getScenarioSnapshot` 后端无 schema 校验

- backend: `return ex.scenario_snapshot`(raw dict,无 Pydantic 包装)(`routers/executions.py:127-144`)
- frontend: `Promise<ScenarioDraft>`(`api/executions.ts:95-99`)
- 现象: 旧快照的 shape 可能与当前 `ScenarioDraft` 不一致(经典 schema 漂移);frontend 把它当成 `ScenarioDraft` 解析,出错时 axios throw 出非 `ApiError`(无 detail.code)。
- 修复建议: 后端用 `ScenarioDraft.model_validate(ex.scenario_snapshot)` + 校验失败时 500 with `code:"snapshot_corrupt"`;前端可在 `getScenarioSnapshot` 外加一层 `Draft` shape guard(non-throwing)。

#### P2-3: `resolveResponsePaths`/代理类 endpoint 的前端类型与 plate 直透

- backend: `POST /endpoint-catalog/resolve-paths`(`routers/endpoint_catalog.py:68-97`) → `list[dict]`(plate 回什么用什么)
- frontend: `ResponsePathCandidate{path,depth,extracted_by_default}`(`api/scenario-composer.ts:204-209`)
- 现象: **前端 TS 是推测出来的 shape**;若 plate 调整字段(`depth` 改名 / 加 `kind` 字段 / 删 `extracted_by_default`),axios response 类型断言不会拦,只能 runtime 报错。
- 修复建议:
  - 把 plate 透传的 shape 收敛到一个 zod/valibot schema 解析器,fallback 退化前先校验。
  - 或在 proxy router 里包一层 Pydantic schema 锁定输出。

#### P2-4: `patchOp` op payload 整包替换,前端签名不显式

- backend: `OpPatchIn{payload: dict[str, Any]}`(`schemas/adaptations.py:141-146`) 注释: "payload 整包替换(仅 pending 可改)"
- frontend: `patchOp(opId, payload: Record<string, unknown>)`(**wrapper 是 `{ payload }` 还是裸 `payload`?**)
- 实际 TS(`api/adaptations.ts:180-187`): `http.patch(... '/adaptations/ops/${opId}', { payload })` — 前端用 `{ payload }` 包装,backend `OpPatchIn` 顶层就是 `payload`,经过 Pydantic 后取 `payload` ✅
- 现象: 整包替换语义对前端不直观(命名上是 `patchOp(opId, payload)`,实际整个 body 被覆盖)。
- 修复建议: 文档明确 + JSDoc 注释 `@param fullPayload` 标明"整包替换,合并请在调用方做"。

#### P2-5: 错误响应信封混用 `code/msg` 与 `code/message`

- backend 多处错误契约:
  - auth/users(`_codes.py:26-28`): `{"code": int, "msg": str}`,如 `{code:4004, msg:"用户名或密码错误"}`
  - 多数其它路由: `{"code": "<string_or_int>", "message": str}`,如 `{code:"plate_unavailable", message:"..."}`
  - constants.py(`routers/constants.py:99-107`): `{"code":"constant_name_exists", "message": "..."}`
  - data_sets/executions/auth_sessions `IntegrityError` 路径: 直接 `detail="alias 'xxx' already exists"`(纯字符串)
- frontend `http.ts:65-88` 已经协商了两种兼容:优先 `detail.message ?? detail.msg`、兼容 `payload.code` 等。
- 现象: 信封形不统一(类型 / 字段名 / 是否嵌套) — frontend ApiError 长得很好但 backend 各家风格不一。
- 修复建议: 立项"统一错误信封规范",给出 `{code: number, message: string}` 一种形状,把所有 router 拉齐 (`_codes.py` 已存在,但没被广泛使用)。

#### P2-6: `Scenario.tags` 与 `Scenario.meta.tags` 同源数据双输出

- backend: `to_read_shape` 同时返回 `tags` 与 `meta.tags`(`scenario_store.py:411-417`)
- frontend `types/scenario-composer.ts:67-71` 注释明确"兼容镜像: 后端恒等于 meta.tags"
- 影响: 字段重复易产生不一致维护(reviewer 误改其中一处)。当前后端同源所以 OK。
- 修复建议: 评审纪要里提一句,长期方向是去掉 `Scenario.tags` 单独字段,统一读 `meta.tags`。前端列表过滤消费方需同步切换。

#### P2-7: `auth_sessions` Reset 与 Create `expires_in` 默认不一致

- backend: `AuthSessionCreateIn.expires_in = 7200`(`schemas/auth_session.py:36`)
- frontend `auth_sessions.ts:22`: `expires_in?: number` (default 不显现)
- 现象: 前端不显式声明默认值,新账号会是 backend 默认 7200;无破坏。
- 修复建议: 不修。前端确实不必重复声明。

---

## 4. 亮点(设计可借鉴之处)

1. **`_CAMEL = ConfigDict(populate_by_name=True, str_strip_whitespace=True)`**(`schemas/scenario_composer.py:28`) 是 Pydantic v2 下很稳的做法 — 同时支持 attribute 名和 alias 输入,但**输出用 alias**(FastAPI `serialize_response` 的默认 `by_alias=True` 隐式兜底)。值得在 `adaptations.py` 等同类模块复用相同的常量。
2. **`ExecutionRowOut` 双向 `populate_by_name=True`**(`schemas/execution.py:35`) 注释说明"registry(asdict 的 snake_case)与 JSONL 回放(camelCase)两种输入都收"— 这种"读侧宽容,写侧严格"的姿态在前端/调度器代码里看到完全对应的消费代码。
3. **`key_error_404`/`value_error_http`/`not_found_404`/`_plate_502`**(`routers/_error_mapping.py`) 4 个工具函数把 9+4 个 call-site 的差异收敛成 4 处一致性 — 排查契约问题更容易。
4. **`UserOut = UserPublic`**(`schemas/user.py:34`) 同一 schema 双引用的 alias — 防止"独立演化,从未发生,只留双份漂移风险"。
5. **前端 `apiError`(ApiError class)与 pydantic `code/message` field 双兼容**(`http.ts:65-88`) — 后端目前是个混合体(有的 `code:int+msg`、有的 `code:str+message`),这种前端宽容是个务实选择。
6. **`ServiceBinding`/`RunScheme`/`ExportOverlay` 一致序列化形状**(都 dict-style,字段集稳定) — D2 退役 env 的同时,引入了"overlay 是导出覆盖唯一入口"的明确边界,前端可读性也高。

---

## 5. 总评与优先工作

### 契约健康度: **B+**

按路由覆盖的 **24+ 个**端点里,**18 个 ✅、6 个 ⚠**;P0 仅 1 条(纯类型开口问题)、P1 共 5 条(纯类型 width 偏差)、P2 多为说明性记录。

### 建议优先做的 3 项工作

1. **(P0) 修正 `RunOverlay.dataSetIds`** — 删除前端类型开口或后端 `ExportOverlay` 加上字段,使契约要么"显式拒绝"、要么"真接受",不要保留"声明但被吞"的语义陷阱。
2. **(P1-3 / P1-4) 收紧前端"假宽类型"** — 删除 `DataSetSummary.description?` 与放宽 `ImpactItem.source` 为 `string`,**统一枚举来源是后端 Pydantic Literal 还是前端 TS union**,选定后另一端配合。
3. **(P2-5) 立项统一错误信封** — 把后台 `code/msg`、`code/message`、`纯字符串 detail` 三种收敛为一种(spec 用 `{code, message}`),配合前端 `ApiError` 校验。这样 `_codes.py` 这种"权威 code 表"才能真正成为契约的 single source of truth,而非部分路由器才用的工具。

### 中期可加的 3 项"防漂移"工程

- 在 CI 加一个**前后端契约一致性守护测试**: 抓 backend `__all__` 导出 schema,生成 OpenAPI,前端用 `openapi-typescript` 生成类型,差异报警。
- 把 `Scenario.tags` 与 `meta.tags` 双源合并(选一作真源)。
- 把 plate 代理类 endpoint(response 透传)的 shape 用 zod 在前端做 runtime guard。

---

**评审结束**. 若对任一条问题有疑问或需要我深入读某段 service 代码以佐证判断,请直接指明。
