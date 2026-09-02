# Gimbal-Platform 评审汇总报告

> **评审对象**: `D:/Gimbal/Gimbal/src/gimbal-platform`(V3 composer 全量代码)
> **评审时间**: 2026-09-02
> **评审基线**: `feat/carry-fields-storage-injection` 工作树(commit 73cc71b 之前)
> **评审方法**: 5 个并行子 agent 分域评审 + 主评审代码走查;每条结论均带 `file_path:line` 锚点
> **中间产物**:
> - `backend-auth-review.md`(认证 / 用户 / JWT / Fernet / 凭据 / 注册 / 启动)
> - `backend-business-review.md`(router / service / model / 状态机 / 并发 / 一致性 / SQLite)
> - `frontend-views-review.md`(15 views + 25 组件 + 测试盘点)
> - `frontend-state-review.md`(stores / api / types / router / 拦截器 / 错误处理)
> - `contract-review.md`(前后端契约对照表)

---

## 0. 一页摘要

gimbal-platform 是一个 FastAPI + Vue 3 的 V3 composer 平台(V1 case 层已解散),核心链路(scenario → run → execute → adapt)跑通,工程化水平中上偏上。**没有发现数据级硬伤**,但有以下五类需要重视的暗病:

1. **P0 安全**: ephemeral 密钥静默旋转 + 注册完全开放 + 凭据自提放大器(localStorage 明文双 token + refresh 死循环);详见 §2
2. **P0 工程地基**: SQLite 未启用 WAL/busy_timeout + `Execution.scenario_id` 无 FK cascade → case.json 明文凭证残留路径大于 DELETE;详见 §3
3. **P0 并发与一致**: scenario 编辑无乐观锁 + 全局 launch semaphore 8 槽(per-event-loop 共享)+ cancel 与 fanout 间 TOCTOU;详见 §4
4. **P1 契约漂移**: `RunOverlay.dataSetIds` 静默吞 + 错误信封三种混用 + `DataSetSummary.description?` 后端无字段;详见 §5
5. **P1 前端类型与状态**: DataSetEditor / useFieldDescriptions 全链路 any + carry 注入别名顺序预览/执行不一致;详见 §6

整体评级: **B+**(核心业务可用,生产前需补齐 P0)

---

## 1. 评审方法与覆盖

### 1.1 五个并行子 agent 评审域

| Agent | 评审域 | 评审产物 | 主要发现数 |
|---|---|---|---|
| #1 backend-auth | 认证 / 用户 / JWT / Fernet / 凭据 / 注册 / 启动 | `backend-auth-review.md` | P0×3 / P1×7 / P2×8 / 亮点×19 |
| #2 backend-business | router / service / model / 状态机 / 并发 / 一致性 / SQLite | `backend-business-review.md` | P0×4 / P1×10 / P2×14 / 亮点×10 |
| #3 frontend-views | 15 views + 25 components + 测试盘点 | `frontend-views-review.md` | P0×5 / P1×14 / P2×20 / 亮点×20 |
| #4 frontend-state | stores / api / types / router / 拦截器 / 错误处理 | `frontend-state-review.md` | P0×3 / P1×12 / P2×20 / 亮点×15 |
| #5 contract | 前后端契约对照(24+ 端点) | `contract-review.md` | P0×1 / P1×5 / P2×7 / 亮点×6 |

主评审额外走查: `run_dispatcher.py`(56721 字节,56 处 docstring)、`carry_injection.py`、`scenario_store.py`、`run_materialize.py`、`executions.py`、`http.ts`、`auth.ts`、router/topnav/scenario-composer 等 18 个关键文件,产出 §6 中自有的补充观察(carry 注入别名顺序、preview-plate overlay 字段、scenario_endpoint_ref 倒排 FK 缺失)。

### 1.2 真实代码 vs 文档偏差盘点

> 评审要求"不要只基于文档,而要基于真实实现" — 评审过程中发现的"文档承诺但实现未到位"列表:

| 文档/注释承诺 | 实际代码 | 严重度 |
|---|---|---|
| `RunOverlay.dataSetIds` 标注"spec §8 已说明" | backend `ExportOverlay` 不收该字段 | P0(contract) |
| spec §6 旧字段(mergePolicy / prefix / injectCredentials)已退役 | runner_dispatcher 调用方确实未读(✅ 一致) | OK |
| `Execution.scenario_id` 应有 cascade 关系 | `models/execution.py:38` 仅 `String(128)`,无 FK | P0(business) |
| `case.json 含明文凭证 → 删除执行必须连带清理` | `execution_store.delete_execution` 手工调 `purge_case_dir`;但用户级 delete 走 ORM cascade 不调 | P0(business) |
| `scenario_endpoint_ref` 倒排与 scenario 同事务 | `models/scenario_endpoint_ref.py` 无 FK,孤儿行可能残留 | P1(business) |
| spec §7 "导出 = 执行 黄金等价" | `scenarios.py:159` 与 `run_dispatcher.py:417` 的 alias 顺序不一致(sorted vs dict.fromkeys) | P2(business) |
| memory 中"plate reload 黑洞"教训 | reload 不在生产路径(已记入 working tree 纪律) | OK |

---

## 2. P0 安全(必修,本周内)

### 2.1 后端认证与凭据

| ID | 标题 | 锚点 | 修复建议 |
|---|---|---|---|
| P0-BE-S1 | `FERNET_KEY` / `JWT_SECRET` 留空时静默生成临时密钥,重启即永久丢失全部已存凭据 | `backend/app/core/config.py:87-92`;`main.py:50-56` | 加 `ENV=dev/prod` 字段,生产模式硬失败 + 暴露 ephemeral 状态到 admin 健康检查端点 |
| P0-BE-S2 | `/api/auth/register` 公开开放,无 admin 开关、无注册开关、无速率限制;首任 admin 后仍可注册 | `backend/app/routers/auth.py:51-83` | 加 `ALLOW_REGISTRATION: bool` 配置项,默认 False,关闭时返回 403 |
| P0-BE-S3 | `/api/auths/{id}/test` + `/api/auths/{id}?include_secrets=true` 形成"凭据自提"放大器,任何持有用户 bearer 的人可一次性导出全部明文 | `backend/app/routers/auth_sessions.py:133-164, 210-227` | `include_secrets` 必须 admin 或 owner + 最近 5min 验证;`/test` 收口为仅 admin 代为调试 |

### 2.2 前端 Token 与刷新

| ID | 标题 | 锚点 | 修复建议 |
|---|---|---|---|
| P0-FE-S4 | Token 明文双重落 localStorage,无任何 `HttpOnly` / 加密兜底;项目目前没有 v-html 但 design 层弱点 | `frontend/src/stores/auth.ts:17-77` | 加 CSP(`script-src 'self'`)+ refresh_token 改 `HttpOnly` cookie 路线 |
| P0-FE-S5 | `refreshOnce` 失败时**不主动清 store**;服务端 invalidate refresh 后前端会"已知失效 token 反复尝试" | `frontend/src/stores/auth.ts:108-124` | refresh 失败(401)时主动 `clear()` |
| P0-FE-S6 | `http.ts` 的 401 拦截器仅依赖 `_retry` 标记,refresh-then-replay 再次 401 时**不会触发第二次 refresh**,用户卡死 | `frontend/src/api/http.ts:131-152` | 加第二次 refresh 兜底(带退避 + 总尝试上限);或放弃 `_retry` 标记,允许"refresh → replay → 401 → 再 refresh 一次"两轮尝试 |

### 2.3 SQLite 工程地基

| ID | 标题 | 锚点 | 修复建议 |
|---|---|---|---|
| P0-BE-EN1 | SQLite 未启用 WAL + busy_timeout,并发写会串行化 + 长事务锁;200 并行行 task 会撞 `SQLITE_BUSY` | `backend/app/core/db.py:16-22`;`core/config.py:32` | `connect_args={"check_same_thread": False, "timeout": 30}` + 钩子 `PRAGMA journal_mode=WAL; PRAGMA busy_timeout=30000` |
| P0-BE-EN2 | `case.json` 明文凭证残留路径大于 `DELETE /executions/{id}`:`Execution.scenario_id` 无 FK + 用户级 ORM cascade 不调 `purge_case_dir` | `backend/app/services/run_dispatcher.py:1145-1148`;`services/execution_store.py:29-41`;`models/execution.py:38` | `Execution.scenario_id` 加 `ForeignKey("composer_scenarios.scenario_id", ondelete="CASCADE")` + 用户删除入口加 `purge_case_dir_by_owner(owner_id)` |

---

## 3. P0 一致性与并发(必修,2 周内)

| ID | 标题 | 锚点 | 修复建议 |
|---|---|---|---|
| P0-BE-CO1 | `scenario_store.update/copy` 无 SELECT FOR UPDATE / 无版本列,runSchemes 透传在双 tab PUT 下丢更新 | `backend/app/services/scenario_store.py:107-148` | 加 `version: Integer default=0` 列 + `update ... where id=X and version=read_version` 乐观锁 |
| P0-BE-CO2 | `run_dispatcher` 全局信号量 `_global_launch_sem` 8 槽跨所有 execution 共享,长尾执行会饿死其他用户 | `backend/app/services/run_dispatcher.py:160-178, 689-698` | 改 owner-级 quota(Semaphore(2)/owner)或调度器;至少文档化"parallel 字段是请求意图,实际并发受全局闸约束" |
| P0-FE-V1 | `confirmAliasCreate`(CaseComposerCanvas.vue:1136-1141)两次写不原子,中间失败会留下"已声明但无引用"或反向 | `frontend/src/views/CaseComposerCanvas.vue:1141-1153` | 用 `Promise.resolve().then(...)` 把两步合到下一个 tick + try/catch 失败回滚 |
| P0-FE-V2 | `valuePlaceholder`(CarryConfig.vue:222-229)对非字符串值返回 `[object Object]` / `0` / `false`,用户看不出"这是默认注入什么" | `frontend/src/views/CarryConfig.vue:222-229` | 非字符串走 `JSON.stringify`;数字/布尔显式 `String(v)`;空字符串另算 |
| P0-FE-V3 | `CaseComposerCanvas.vue` 的 `JSON.stringify` watch echo 检测是 O(N) GC 压力,大场景下每次 keystroke 都全表扫描 | `frontend/src/views/CaseComposerCanvas.vue:859-887` | 改用 `shallowRef` + 显式 deep 比较;或在 props 变更路径标记 `__fromEmit: true` 跳过 watch |

### 3.1 P1 一致性问题(需关注)

- **P1-BE-CO1** `_next_dataset_id` 是 read-then-write 竞态(`data_set_store.py:233-251`),两个并发请求都拿到 `ds-008` 后 commit 撞车。修复:循环重试(限 5 次)或 `MAX(dataset_id)+1` SQL。
- **P1-BE-CO2** `_finalize_execution` 在 `_bump_counters` 失败的极端窗口下,`counterDrift` 仅标记不阻止 done(`run_dispatcher.py:959-998`)。修复:`counterDrift=True` 显式 `status="failed"` + 前端红条。
- **P1-BE-CO3** `_fanout` 入口的 `_cancel_requested.discard(execution_id)` 与 `cancel_execution` 端点存在 TOCTOU 时序。修复:用 `asyncio.Event/Future` 替代裸 set,或把"cancel 请求已存在"当成"拒绝 spawn fanout"。
- **P1-BE-CO4** `ConstantEntry` 创建不互斥 literal/generator,DB 接受两者并存(`routers/constants.py:84-109`)。修复:`create_constant` 内做与 `_validate_patch` 同款校验。

---

## 4. P1 契约漂移(需在下次前后端联调前对齐)

| ID | 标题 | 锚点 | 修复 |
|---|---|---|---|
| P0-CT1 | `RunOverlay.dataSetIds` 前端标 `?` 但后端 `ExportOverlay` 显式不收,新代码陷阱 — 静默丢弃风险 | `backend/app/schemas/scenario_composer.py:217-224`;`frontend/src/api/scenario-composer.ts:133-137` | 删前端类型开口,或后端加上字段(不要保留"声明但被吞"的语义陷阱) |
| P1-CT2 | `DataSetSummary.description?` 前端类型假设存在,但 backend 不返回 | `backend/app/schemas/scenario_composer.py:158-172`;`frontend/src/types/scenario-composer.ts:89-97` | 删 `description?` |
| P1-CT3 | `ImpactItem.source` 联合类型过窄,backend `str` vs frontend `'body'\|'headers'\|null` | `backend/app/schemas/adaptations.py:41`;`frontend/src/api/adaptations.ts:31-36` | 改 `source: string \| null` |
| P1-CT4 | `ExecutionStatus` / `BatchOut.status` / `OpOut.status` 前端 union 比 backend `str` 窄 | 多处 | 选一作真源,加 lint/测试锁定 |
| P1-CT5 | `runScenario().executionId` 标 `?` 实际必传 | `backend/app/schemas/scenario_composer.py:262-268`;`frontend/src/api/scenario-composer.ts:156-160` | 改成 `executionId: number` |
| P1-CT6 | `getScenarioSnapshot` 后端裸返 dict,前端当成 `ScenarioDraft`,旧快照 schema 漂移变非 `ApiError` 抛错 | `backend/app/routers/executions.py:127-144` | 后端 `model_validate` + 校验失败 500 with `code:"snapshot_corrupt"` |
| P1-CT7 | 后端错误信封三种混用(`code:int+msg` / `code:str+message` / `detail:str`),前端 `ApiError` 兼容但单源权威缺失 | 多处 router | 立项统一 `{code: number, message: string}`,把 `_codes.py` 用起来 |
| P1-CT8 | `ExecutionRow.caseDir` 字段命名混搭(`datasetId` camelCase + `caseDir` 单段),未交叉验证 backend schema | `frontend/src/api/executions.ts:43-52` | 与 backend schema 对齐核对 |
| P1-CT9 | `ScenarioMeta.system` 后端 `list[str]`,前端 `SystemTag = '...' \| string`(`| string` 吞掉所有字面量) | `frontend/src/types/scenario-composer.ts:16,53` | 删 `\| string` |

---

## 5. P1 前端状态 / 类型 / 错误处理

| ID | 标题 | 锚点 | 修复 |
|---|---|---|---|
| P1-FE-1 | `App.vue` 首屏 `fetchMe` 异步,`currentUser` 未拉时 admin 入口闪烁 | `App.vue:22-30` | `router.beforeEach` await `fetchMe()` 推进 status |
| P1-FE-2 | `router/index.ts` 没有兜底 404 route,手敲 `/foo` 显示空白 | `router/index.ts:12-97` | 加 `{ path: '/:pathMatch(.*)*', redirect: '/scenarios' }` 或 NotFound.vue |
| P1-FE-3 | `http.ts` `normalizeError` 对 5xx HTML 缺兜底,FastAPI 默认 500 是 HTML | `frontend/src/api/http.ts:65-88` | 检测 `detail.startsWith('<')` 转 `服务器错误 (HTTP ${status})` |
| P1-FE-4 | `stores/auth.ts` `fetchMe` 用 `(e as { status?: number })` unsafe cast | `frontend/src/stores/auth.ts:152-175` | `if (e instanceof ApiError && e.status === 401)` |
| P1-FE-5 | `useFieldDescriptions` 全链路 any,`DataSetEditor` 失去类型保护 | `frontend/src/composables/useFieldDescriptions.ts:67`;`DataSetEditor.vue:328` | 改 `Ref<ScenarioDraft \| null>` + 边界处 unknown cast |
| P1-FE-6 | `ExecutionsList` 轮询无退避 / 无 visibility 监听 / 不响应 401 | `frontend/src/views/ExecutionsList.vue:111-123` | 收敛到 `stores/executions.ts` 的 `startPolling` 模式 |
| P1-FE-7 | `stores/executions.ts` tick 内 `await fetchRows(rid)` 串行,展开 N 行 → N 秒才完成一轮 | `frontend/src/stores/executions.ts:196-199` | `Promise.all(...)` |
| P1-FE-8 | `api/carry.ts` `CarryFieldFace.type: string` 必填,后端 `default="string"` 不一致 | `frontend/src/api/carry.ts:53-89` | `type?: string` + caller 兜底 |
| P1-FE-9 | `CaseComposerCatalog.vue:432-446` 用 `fetch` 绕 axios 但 token 错误处理缺失,401 走 warning 不触发 refresh | `frontend/src/views/CaseComposerCatalog.vue:432-446` | 401 → `authStore.handle401()` |
| P1-FE-10 | `PlateResourceItem.extra` 字段类型过宽,新 kind 默默丢弃 | `frontend/src/api/plate.ts:104-130` | `console.warn` 或 store 层 `unknownResources` 提示 |
| P1-FE-11 | `router/index.ts` 的 `requiresAdmin` 在 fetchMe 未完成时永远 false,首屏 admin 用户被错误重定向 | `router/index.ts:104-117` | await fetchMe 后再判定 |
| P1-FE-12 | `ExecutionsList.vue` 与 `Executions.vue` 重复实现(167 vs 740 行) | 两文件 | 通过 `mode` prop 合并 |

### 5.1 P1 前端业务视图

- **P1-FE-V1** `CaseComposer.vue` 1127 行 — 可抽 `useCaseComposerShell` composable
- **P1-FE-V2** `Executions.vue` 1s 轮询缺 Page Visibility 暂停;`getArtifacts` 走单一 AbortController
- **P1-FE-V3** `UsersAdmin.vue` 800 行缺批量操作 + 角色多选 filter + 导出
- **P1-FE-V4** `Scenarios.vue` 658 行可拆 `<ScenariosToolbar> + <ScenariosTable> + <ScenariosFilters>`
- **P1-FE-V5** `DataSetEditor.vue` 1078 行,`mutateDraft` 深拷贝行为需确认是否全表 clone
- **P1-FE-V6** `Register.vue` 密码强度条前端可绕过,后端未真正同步校验
- **P1-FE-V7** `Auths.vue` `token_type` filter 单选 → 多选
- **P1-FE-V8** `ConstantsPool.vue` NAME_RE 与 `VariableRegistryPanel` 渲染端校验不一致
- **P1-FE-V9** `CarryConfig.vue:280-289` `downloadTemplate` blob 一次性生成,大表可能 OOM
- **P1-FE-V10** Element Plus `:deep()` 主题定制散落在 5+ 文件,改版本会多处失效

---

## 6. P2 工程债(可选优化)

### 6.1 后端业务

- **P2-BE-1** `execution_rows` 全日 JSONL glob + 全文解析,30 天历史 = 30 次 open
- **P2-BE-2** `list_batches` N+1(`adaptation_service.py:873-878`)
- **P2-BE-3** `impact` 兜底逻辑走全表 `composer_scenarios`(`adaptation_service.py:239-247`)
- **P2-BE-4** Plate client 单例 `set_client_for_tests` 无锁(`plate_client.py:65-83`)
- **P2-BE-5** `fill_plate_defaults` 就地修改入参 dict,污染前端 draft(`plate_client.py:86-115`)
- **P2-BE-6** `endpoint_id` 在代理 URL 中未 URL encode(`endpoint_catalog.py:45`)
- **P2-BE-7** `_resolve_exec_auths` 长持明文凭证在堆中(`run_dispatcher.py:1069-1128`)
- **P2-BE-8** `stars.json` 文件 store 与 DB 弱一致(`marks_store.py:1-122`)
- **P2-BE-9** carry preview 与 dispatch 的 alias 注入顺序不一致(`scenarios.py:159` sorted vs `run_dispatcher.py:417` dict.fromkeys)
- **P2-BE-10** `runs.py` 把 scenario 预加载给 dispatch 但仍重新解析步骤与 datasets(`runs.py:54-75`)
- **P2-BE-11** `cancel_execution` 的 status 更新无原子保护(`executions.py:157-181`)
- **P2-BE-12** `ServiceBinding.url` 无 URL 格式校验(`schemas/scenario_composer.py:186-191`)
- **P2-BE-13** `data_set_store.create` 对 unique 冲突的判别容错但可能误吞 NOT NULL 错
- **P2-BE-14** `main.py` router 注册顺序敏感,`data_sets.create_router` 是单独注册

### 6.2 前端业务

- **P2-FE-V1** i18n 缺失,所有视图文案硬编码中文
- **P2-FE-V2** a11y 缺,icon-only 按钮仅靠 title(缺 `aria-label`)
- **P2-FE-V3** `Scenarios.vue` table 列内嵌 `el-dropdown` 与 `el-tooltip` 嵌套,百行表格卡顿(待 virtual scroll)
- **P2-FE-V4** `CaseComposer.vue` `runNavTimer` 缺错误处理 — 跳运行时若服务挂会假死
- **P2-FE-V5** `VariableRegistryPanel` 50+ 变量时滚动卡,加 `vue-virtual-scroller`
- **P2-FE-V6** `DataSetEditor.vue` `mutateDraft` 深拷贝 — 万行表每次按键一次 stringify 拖慢
- **P2-FE-V7** `AuthSelectorModal.vue` Vue 2 `@update:model-value` 兼容模式 → `v-model:open`
- **P2-FE-V8** `ExecutionsList.vue:228` removed-cancel 按钮歧义,实际只是 UI 隐藏
- **P2-FE-V9** 测试覆盖盘点:`FieldForm.vue` / `StrategyForm.vue` / `VariableRegistryPanel.vue` / `ConstantPoolPanel.vue` / `Scenarios.vue` 主路径 / `CarryConfig.vue` 主路径均无单测
- **P2-FE-V10** 缺 ErrorBoundary — 任意子组件渲染异常会白屏

---

## 7. 亮点(优先保留与复用)

### 7.1 后端设计

1. **统一 owner/auth 收紧**(`_ownership.ensure_owner` + `can_read_scenario`)— 404/403 合并避免存在性泄漏
2. **cancel 协作式状态机**(`_cancel_requested` + `_tasks_by_execution` + 行边界检查)
3. **重启僵尸收敛**(`reconcile_stale_executions`)
4. **plate 熔断**(`PLATE_BREAKER_THRESHOLD=3`)
5. **carry 注入链**(preview/export 与 dispatch 同源物化)
6. **rollback 乐观冲突**(避免批次外修改被覆盖)
7. **scenario_endpoint_ref 派生层**(rebuild 兜底)
8. **error_mapping helpers**(`key_error_404` / `not_found_404` / `value_error_http`)
9. **fill_plate_defaults 防明文入库**(`run_dispatcher` 与 `materialize_run_copy` 物理验证)
10. **CORS 设计干净**(JWT 走 Authorization header,`allow_credentials=False`)

### 7.2 前端设计

1. **refresh token single-flight 设计**(`stores/auth.ts:108-124`)— 注释解释 self-deadlock 陷阱
2. **`http.ts` 拦截器 `isRefreshCall` 特判**(`http.ts:128-130`)— 避免递归
3. **`stores/auth.ts` `clear()` idempotent**(防 5 并发 401 触发 5 次 localStorage 写)
4. **`api/adaptations.ts` 的 `errMsg` 单点归一**
5. **`utils/errorFallback.ts` 的 `showError` 收敛**
6. **`stores/executions.ts` 的 polling 失败预算**(10 次连续失败 / 404 → 优雅退场)
7. **`utils/carry-entries.ts` 三态(hasRow/isNull/value)对齐 backend**
8. **`composables/useFieldDescriptions` 的版本号模式**(`fullVersion` ref bump 让 computed 重算)
9. **`utils/carry-drift.ts` 的 `canGenerateCarryBatch` 单点契约**(plate 不可达禁用批生成)
10. **`composables/useSystemPrefill` "成功一次后不再重载" + "失败不消耗首次机会"**

### 7.3 视图/组件亮点(由 frontend-views-review 提炼)

- plate /full 会话级缓存(`CaseComposerCanvas.vue:900-928`)
- WeakMap-pinned drag keys(`CaseComposerCanvas.vue:1264-1273`)
- 三态行模型(`CarryConfig.vue:201-204`)
- service alias dual-display + inline creator(`CaseComposerCanvas.vue:1017-1142`)
- plate 拉取统一用 native fetch(`CaseComposerCatalog.vue:432-446`)— 显式回避 axios baseURL bug
- OpPreview 模块级缓存
- dict↔rows 边界单一函数(`CaseComposerConfig.vue:352-368` emitShape)

---

## 8. 优先行动(按投资回报排序)

### 行动 1:配置与启动硬失败(估时 0.5 天,解锁所有生产部署)

- `core/config.py:87-92` 加 `ENV=dev|prod` 字段
- 生产模式 FERNET_KEY/JWT_SECRET 留空 → `RuntimeError`
- 暴露 ephemeral 状态到 `/api/health`(admin 可见)
- 主评审建议:加 `app/secret_init.py` 一键生成持久密钥并写 `.env`

### 行动 2:SQLite WAL + busy_timeout(估时 0.5 天,解锁所有并发性能优化)

- `core/db.py:16-22` 加 `connect_args={"timeout": 30}`
- 引擎启动后钩子 `PRAGMA journal_mode=WAL; PRAGMA busy_timeout=30000; PRAGMA synchronous=NORMAL; PRAGMA foreign_keys=ON`

### 行动 3:案例案卷残留闭环(估时 1 天,堵住凭据泄露面)

- `models/execution.py:38` `Execution.scenario_id` 加 `ForeignKey("composer_scenarios.scenario_id", ondelete="CASCADE")`
- `routers/users.py` 删除用户入口加 `await run_dispatcher.purge_case_dir_by_owner(owner_id)`
- 启动期 `sweep_stale_case_dirs` 加 owner 级 sweep

### 行动 4:乐观锁 + 倒排索引 FK(估时 1 天,消双 tab 编辑丢方案与孤儿行)

- `composer_scenarios` 加 `version: Integer default=0` 列 + `update ... where id=X and version=read_version`
- `scenario_endpoint_ref.scenario_id` 加 `ForeignKey("composer_scenarios.scenario_id", ondelete="CASCADE")`
- 加自动化测试断言 scenario 双 PUT 第二次返回 409

### 行动 5:前端 token 安全加固(估时 1 天)

- 加 CSP:`script-src 'self'; object-src 'none'`(vite plugin + nginx 头)
- `stores/auth.ts:108-124` refresh 失败时主动 `clear()`
- `api/http.ts:131-152` 加第二次 refresh 兜底(带退避)

### 行动 6:契约漂移修复(估时 1 天,前后端联调前必做)

- 删 `RunOverlay.dataSetIds` 开口(contract P0)
- 删 `DataSetSummary.description?`(contract P1)
- 改 `ImpactItem.source: string | null`(contract P1)
- 改 `executionId: number` 必填(contract P2)

### 行动 7:前端核心组件单测补齐(估时 1.5 人天)

- `FieldForm.test.ts` — 7 种 ui_kind 渲染 + JSON 域 + 候选下拉
- `StrategyForm.test.ts` — 4 种 phase + onFailure 入口 + summary 推导
- `VariableRegistryPanel.test.ts` — 同名多产出聚合 + unregisteredRefs 推导
- `Scenarios.vue` 主路径(查询/分页/批量操作)

### 行动 8:register 关闭 + 凭据自提收口(估时 0.5 天,与内网测试语境策略一致)

- `core/config.py` 加 `ALLOW_REGISTRATION: bool = False`
- `auth_sessions.py:138` `include_secrets` 必须 admin 或 owner + 最近 5min 验证
- `/test` 端点收口为 admin-only 代调试

---

## 9. 长期防漂移工程(可选)

- **CI 加前后端契约一致性守护测试**:抓 backend `__all__` 导出 schema,生成 OpenAPI,前端用 `openapi-typescript` 生成类型,差异报警
- **`_codes.py` 作为权威 code 表**:把所有 router 拉到 `{code: number, message: string}` 一种形状
- **plate 代理类端点(response 透传)的 shape 用 zod 在前端做 runtime guard**
- **把 `Scenario.tags` 与 `meta.tags` 双源合并(选一作真源)**
- **CSRF / cookie 化 refresh token**:用 SameSite=Lax cookie + double-submit pattern,前端不再持久化 refresh_token

---

## 10. 评审覆盖与盲区

### 10.1 已评审文件

| 类别 | 数量 | 关键文件 |
|---|---|---|
| 后端 routers | 11 | auth / auth_sessions / users / scenarios / runs / executions / data_sets / carry / adaptations / endpoint_catalog / strategy_catalog / constants / generator_catalog |
| 后端 services | 14 | run_dispatcher / scenario_store / data_set_store / carry_store / carry_injection / run_materialize / adaptation_service / adaptation_ops / gimbal_launcher / plate_client / marks_store / execution_store / endpoint_ref_index / auth_probe |
| 后端 schemas | 7 | auth / user / auth_session / scenario_composer / execution / adaptations / carry / constants |
| 后端 models | 13 | composer_scenario / composer_data_set / execution / auth_session / constant_entry / scenario_endpoint_ref / catalog_version / adaptation_batch / adaptation_op / adaptation_snapshot / carry_binding / user / adaptation_index |
| 后端 core | 4 | db / config / deps / security |
| 前端 views | 15 | Scenarios / CaseComposer / ScenarioDetailView / CaseDataSetsList / DataSetEditor / CarryConfig / UsersAdmin / Auths / ConstantsPool / AdaptationCenter / AdaptationBatchDetail / ExecutionsList / Executions / Login / Register |
| 前端 components | 25+ | TopNav / CaseComposerCanvas / CaseComposerConfig / CaseComposerMeta / CaseComposerResource / CaseComposerCatalog / FieldForm / StrategyForm / VariableRegistryPanel / ConstantPoolPanel / OpConstructDialog / OpPreview / AuthSelectorModal / FilterPopover / PriorityPill / ScenarioExportMenu / SystemChip / TagInput / TagPill / ImpactDrawer / UnindexedAlert |
| 前端 stores | 8 | auth / auth_sessions / scenarios-composer / scenario-draft / users / constants / executions / adaptations / marks |
| 前端 api | 23 | http / auth / auth_sessions / users / scenarios / data-sets / runs / executions / endpoint-catalog / strategy-catalog / carry / constants / adaptations / generator-catalog / scenario-composer / plate |
| 前端 utils/composables | 27+ | useListSearch / useFieldDescriptions / useSystemPrefill / useInsertTarget / errorFallback / jsonpath / csv-dataset / carry-csv / draft-lint / dataset-grid / carry-drift / carry-entries / scratch-path / catalog-services / links / executionStatus / removeExecution |

### 10.2 已知盲区(留待下轮评审)

- **plate 实际契约**:`gimbal-plate` 不在本评审范围,仅看 `plate_client` 的代理;plate 字段面以评论推断,未读 plate 源码
- **engine 子进程**:仅评审 `gimbal_launcher.py` 的 wrapper,实际 `gimbal run launch` CLI 行为不在评审范围
- **CI / 测试覆盖盘点**:仅盘点了 14 个 `__tests__/` 文件,未深读每个 test 的断言质量
- **V1 → V3 数据迁移路径**:没有 migration 脚本可读(spec 中提到 raw-SQL 迁移路径但代码没找到)
- **多租户隔离**:整个平台按 owner_id 隔离,未考虑"跨租户"场景;当前模型假设单租户
- **审计日志**:除 JSONL 调度日志外,无审计面;CRUD 操作无 audit trail

---

## 11. 与 memory 索引的交叉确认

| Memory 条目 | 评审验证 |
|---|---|
| **用户协作画像**:评审时 AI 主动补边界穷举;评估性反馈直说 | ✅ 本报告 P0 直接标"必修",不堆 P3;补的盲区明示 |
| **plate reload 黑洞**:8765 常驻普通模式;--reload 只在用户真终端 | ✅ 未在代码中发现 `--reload` 在生产路径;memory 工作树纪律已记 |
| **step 是顺序抽象,用 plate 结构**:前端 step 直接用 plate 的 Step{api,request,strategy},不另起扁平模型 | ✅ `types/plate.ts` 已是唯一权威,contract-review 中 `EndpointFullView` 类型已对齐 |
| **平台路线图**:carry 已落地;IO 声明归一化 spec+plan 定稿、实现推迟 | ✅ carry 路径已走通(plate 降级门控 + carry_injection);IO 声明归一化未在本评审体现 |

---

**评审结束**. 若对任一条问题有疑问或需要深入读某段 service 代码以佐证判断,请直接指明。
