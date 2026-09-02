# Gimbal-Platform 业务功能与前后端实现评审

> **评审对象**: `D:/Gimbal/Gimbal/src/gimbal-platform`
> **评审时间**: 2026-09-02
> **本报告定位**: 补足 `SUMMARY.md` 中偏安全/并发的视角,**逐业务域审视功能完整性 + 前后端实现细节**(API ergonomics / 状态管理 / 性能 / 类型安全 / 可测试性 / UX 一致性 / 可观测性)
> **评审基线**: 5 份子评审 + 主评审代码走查的真实问题清单(去重后按"业务域 × 实现层"二维归类)
> **关系**: 本报告与 `SUMMARY.md` 互补。SUMMARY 是按严重度排序的总入口;本报告是按业务域 + 实现层切片,方便各域负责人直接认领

---

## 0. 一页摘要

gimbal-platform 业务域覆盖 **9 个核心域**(scenario / dataset / run / execution / auth / adaptation / carry / constant / plate 代理)。**整体功能链路通顺**,但有 3 类明显短板:

1. **业务功能正确性但边界粗糙**(共 14 条):scenario 编辑无乐观锁导致双 tab 丢更新、`_next_dataset_id` 竞态、cancel 与 fanout 之间 TOCTOU、carry 预览与执行注入顺序不一致、`counterDrift` 仅标记不阻止 done、ConstantEntry literal/generator 创建不互斥、runShemes 透传 TOCTOU、`get_scenario_draft` 对 legacy 行 500、case.json 清理依赖手工 sweep、preview-plate overlay 字段后端静默吞、scenario_endpoint_ref 倒排无 FK cascade、`stars.json` 与 DB 弱一致、`max_concurrent_launches=8` 全局共享、ServiceBinding.url 无格式校验。
2. **API ergonomics 与错误处理**(共 9 条):错误信封三种混用、include_secrets 太宽松、`/preview-plate` 命名风格不一致、`getCaseArtifact` 用 query 而非 path 命名、case 复数形态在 routers/scopes 间不一致。
3. **前后端实现细节**(共 35+ 条):覆盖 Pinia store 一致性、组件复用度、类型安全、性能(轮询 / 深拷贝 / JSON.stringify watch)、测试覆盖、UX、a11y、i18n、可观测性。

整体评级: **B**(业务链路通顺,生产前需要按域做 P1 收敛)

---

## 1. 业务功能完整性评审(按域切片)

### 1.1 Scenario CRUD 域

#### ✅ 已落地能力
- 完整 CRUD(`POST/GET/PUT/DELETE /api/scenarios`)
- 收藏(star)、发布/下架(visibility)、复制(copy)、草稿导出(draft)
- server 端强制 owner 覆盖(`scenario_store.create` 中 `effective_owner = new_owner || def_meta.get("owner") || row.owner`),防止客户端伪造属主
- 容器化重构:`{definition, orchestration}` 统一容器;`definition_from_payload` 是全后端唯一解包点
- 倒排索引 `scenario_endpoint_ref` 在 scenario 写时同事务维护

#### ⚠️ 业务功能正确性问题

| ID | 问题 | 位置 | 修复 |
|---|---|---|---|
| BF-SCN-1 | **scenario 编辑无乐观锁,双 tab PUT 丢更新**:`update` 无 `version` 列、无 `SELECT FOR UPDATE`,编辑器两个 tab 同时 PUT 时,后者整体覆盖前者的全部更新(包括 runSchemes、steps 重排、endpoint_ref_index 倒排) | `services/scenario_store.py:107-148, 138-145` | 加 `version: Integer default=0` 列 + `where id=X and version=read_version` 乐观锁;409 提示前端重读 |
| BF-SCN-2 | **`get_scenario_draft` 对 legacy 空 `system: []` 行返回 500**:`ScenarioMeta._validate_system` 拒绝空 system,但读侧 `_meta_from_row` 会兜底填 `["default"]`,写侧不兜底 → 数据迁移期极易踩雷 | `routers/scenarios.py:425-442` | 用 `ScenarioDraft.model_validate(_normalize_legacy(payload))`,与 `_meta_from_row` 同修复路径 |
| BF-SCN-3 | **`runSchemes` 透传保留 + PUT 整体替换 = 并发丢方案**:即便修了 BF-SCN-1,该透传保留逻辑仍是整体替换而非 merge;`runSchemes` 是窄端点专管键,PUT 整体替换会让编辑器拖拽重排时丢失已存的运行方案 | `services/scenario_store.py:138-145` | 透传逻辑改为"读 - 写 - 写三方都有变更才整体替换,否则只动 orchestration 非 runSchemes 部分";或 runSchemes 走独立子表 |
| BF-SCN-4 | **`copy_scenario` 的新 id 拼接可能截断到 128 字符后撞 unique**:`f"{scenario_id}-copy-{suffix}"[:128]` 把原 id 可能截断到 127,加上 `-copy-` 后已 128,如果原 id 长度接近 122 仍可能撞 unique | `services/scenario_store.py:220, 243` | `new_sid = f"{scenario_id[:110]}-copy-{suffix}"` 保留 18 字符给 -copy-6hex |

#### 🔧 实现细节

- **路由顺序敏感**:`main.py:114-128` 注释明确警告 `scenarios.router` MUST be last,`data_sets.create_router` 单独注册打破隐式顺序。修复:把 `data_sets.create_router` 改名 `nested_router` 挪回 data_sets.py。
- **stars.json 与 DB 弱一致**:`marks_store.py` JSON 文件不参与 DB 事务,DB commit 失败而 stars 已更新会反向;JSON 文件丢失/损坏 DB 行还在 → `starred=False` 用户视角丢失。修复:迁移到 `star_marks(owner_id, scenario_id, created_at)` DB 表 + 唯一索引。

---

### 1.2 Dataset 域

#### ✅ 已落地能力
- 数据集直接挂场景 1:N(Case 层解散)
- 行值按基线类型还原(`_coerce_row_value`)
- 编辑器统一字符串落库,执行时按基线类型回退

#### ⚠️ 业务功能正确性问题

| ID | 问题 | 位置 | 修复 |
|---|---|---|---|
| BF-DS-1 | **`_next_dataset_id` 是 read-then-write 竞态**:两个并发请求都读到 `used = {1,...,7}`,都返回 `ds-008`,后 commit 撞 IntegrityError → 当前不重试直接 409 | `services/data_set_store.py:233-251` | 循环重试(限 5 次)或 `SELECT MAX(...) + 1` SQL |
| BF-DS-2 | **`data_set_store.create` 对 IntegrityError 分类容错,但可能误吞 NOT NULL 错**:用 `"dataset_id" not in msg` 黑名单 + `("NOT NULL", "FOREIGN KEY", "CHECK constraint")` 反向排除,如果 NOT NULL 错消息里恰好含 `dataset_id` 字面量 → 误判 collision | `services/data_set_store.py:82-91` | 用 `PRAGMA table_info(composer_data_sets)` 主动检查 NOT NULL 列,按列名 whitelist 判别 |

#### 🔧 实现细节

- **`row_count` 列冗余**:`ComposerDataSet.row_count` 已被 `dataset_counts` 用 `GROUP BY SUM(row_count)` 替代,但 `row_count` 列仍被写。修复:删除冗余列,统一读时 SUM。
- **数据集列表 endpoint 不带 description**:P1-CT2 已记录,前端 `DataSetSummary.description?` 是契约漂移。
- **DataSetEditor 1078 行单文件**:`mutateDraft` 深拷贝模式,数千行表时卡顿(待验证是否全表 clone)。

---

### 1.3 Run 派发域

#### ✅ 已落地能力
- 完整 fan-out:`dispatch_run` → 创建 Execution → spawn `_fanout` 任务 → 行级子任务
- 全局 launch semaphore 限流
- plate 熔断(`PLATE_BREAKER_THRESHOLD=3`)
- 协作式 cancel
- 凭证解析 fail-fast
- carry 注入链与导出同源物化(spec §7 黄金等价)

#### ⚠️ 业务功能正确性问题

| ID | 问题 | 位置 | 修复 |
|---|---|---|---|
| BF-RUN-1 | **`MAX_CONCURRENT_LAUNCHES=8` 是全局共享,跨所有 execution 跨 owner**:一个 200 行的长尾执行长时间占 8 槽,其他小执行全部饿死;`parallel` 字段(per-execution, 上限 200)对外显示并发度但实际被全局闸二次限制,UI 显示 "parallel=64" 但实际等 8 | `services/run_dispatcher.py:160-178, 689-698`;`core/config.py:51` | 改 owner-级 quota(Semaphore(2)/owner);或调度器;至少文档化"parallel 字段是请求意图,实际并发受全局闸约束" |
| BF-RUN-2 | **`_cancel_requested.discard(execution_id)` 与 cancel 端点的 TOCTOU 时序**:时序 1:客户端 cancel → `request_cancel(eid)` 入集合 → `_fanout` 启动前 `discard(eid)` 清掉 → 行边界检查永远 False,运行到完不被取消 | `services/run_dispatcher.py:515-519`;`routers/executions.py:157-181` | 用 `asyncio.Event/Future` 替代裸 set;或"cancel 请求已存在" 直接拒绝 spawn fanout |
| BF-RUN-3 | **carry 预览与 dispatch 的 alias 注入顺序不一致**:`scenarios.py:159` 用 `sorted(set([*scanned, *bound]))`,`run_dispatcher.py:417` 用 `list(dict.fromkeys([*scanned, *bound]))` —— 同一请求的 preview 与 dispatch 注入顺序不同,spec §7 "导出 = 执行 黄金等价"被破坏 | `routers/scenarios.py:159`;`services/run_dispatcher.py:417` | 一处统一为 `dict.fromkeys([*scanned, *bound])`,另一处同步 |
| BF-RUN-4 | **`_resolve_exec_auths` 全量读 owner 凭证到内存,长持明文**:30 行 × 300s timeout = 明文凭证在堆中停留数分钟;同时如果 owner 凭证多,`IN` 子句扩大 | `services/run_dispatcher.py:1069-1128` | 改为"按行即时解密"(`_row` 入口传 alias 列表,内部 Lazy decrypt);或让 `_apply_users` 接受"解密回调"避免清单常驻 |
| BF-RUN-5 | **`_finalize_execution` 的 `counterDrift` 仅标记不阻止 done**:某行 `_bump_counters` 两次重试都失败(JSONL 已记 counter_bump_failed),此行 passed/failed 不在 ex 上 → `passed+failed < total_runs` 触发 `counterDrift` 标记,但 Execution 仍标 `done`/`failed`,UI 不感知"还有未结算的行" | `services/run_dispatcher.py:959-998` | `counterDrift=True` 显式 `status="failed"` + `note="counter_drift: 详见 JSONL"`;或新增 Execution 字段 `pending_counters` |
| BF-RUN-6 | **`gimbal_launcher` `engine_log_path.open()` 未包 try/except**:`case_dir` 已 mkdir 但路径非文件而是目录、磁盘满、权限拒绝都会抛 OSError,污染 `_row` 的 except 链记为 `dispatcher_error`;且 `log_fh` 此时未定义 → 后续 `if log_fh: log_fh.flush()` NameError | `services/gimbal_launcher.py:184-256` | 把 `engine_log_path.open` 包 try/except,失败转 `launch_status="error"`(在 spawn 之前返回) |
| BF-RUN-7 | **`runs.py` 把 scenario 预加载给 dispatch_run 但仍重新解析步骤与 datasets**:预加载只省 1 次 scenario 查询;datasets 仍 N 次。`req.data_set_ids` 可能 50 个,加 DB 往返 | `routers/runs.py:54-75`;`services/run_dispatcher.py:357-388` | 同步预加载 datasets:`datasets = await data_set_store.list_for_scenario(db, scen.scenario_id)`,在 dispatch_run 里 dict 查 |

#### 🔧 实现细节

- **`execution_rows` 全日 JSONL glob + 全文解析**:活跃执行走内存 registry(快);历史执行随天数线性恶化。30 天执行历史 = 30 次 open + 全行 JSON parse。
- **`fill_plate_defaults` 就地修改入参 dict**:`setdefault` 是就地改,plate 拒绝时外层 payload 已被添加 `kind/requirementRef/owner` 等;前端拿到的 `body.definition` 不可逆地被污染。
- **`endpoint_id` 在代理 URL 中未 URL encode**:`f"/api/endpoint/{endpoint_id}/full"` 若含 `?`/`#`/` ` 等保留字符会破坏 URL。
- **`ServiceBinding.url` 无 URL 格式校验**:接受任意 512 字符字符串(含 `javascript:`, `file:`, 空字符串等),引擎消费可能引发 SSRF。

---

### 1.4 Execution 观测域

#### ✅ 已落地能力
- 行级实时状态:`RowState` 内存 registry(活跃执行)
- 历史执行 JSONL 回放:按天 JSONL,后行覆盖前行(final 覆盖 dispatched)
- 两段式无缝切换:活跃读内存 / 历史读文件
- case-artifact 白名单:`engine-log` / `result`,`case.json` 刻意不暴露
- 启动期僵尸收敛:`reconcile_stale_executions`

#### ⚠️ 业务功能正确性问题

| ID | 问题 | 位置 | 修复 |
|---|---|---|---|
| BF-EXE-1 | **`cancel_execution` 状态更新无原子保护**:无 live fanout 的判断基于模块级 `_tasks_by_execution`;dispatcher 已 finalize 为 done 时,router 端把它改 canceled(覆盖最终态) | `routers/executions.py:157-181` | 把 finalize 幂等化:`update Execution set status=CANCELED where id=? and status in (QUEUED, RUNNING)` |
| BF-EXE-2 | **`reset_shutdown_state` 不清 `_cancel_requested` 与 `_tasks_by_execution`**:`lifespan` startup 调 `reset_shutdown_state` 清标志,但这两个注册表没 reset;生产 server 重启时若复用 execution.id(SQLite 不会,PG 序列恢复有概率)会误判"取消"在边界 | `services/run_dispatcher.py:106-157, 351-356, 449-481` | `reset_cancel_state()` 在 lifespan startup 也调一次;或归一收敛到 `reset_all_module_state()` |
| BF-EXE-3 | **`_fail_whole_execution` 路径把 `auth_resolve_failed` 写在 `status` 字段上,污染 JSONL 的 final-state 枚举**:`_FINAL_STATUSES` 没包含 `auth_resolve_failed`,replay 时 `finishedAt` 不设置 → UI 显示 "运行 0 秒" | `services/run_dispatcher.py:228-232, 863-871` | 把 `auth_resolve_failed` 加入 `_FINAL_STATUSES`,或拆 `level` 字段区分 |
| BF-EXE-4 | **执行删除后 case 案卷清理依赖手工 sweep**:`case.json` 含明文凭证,但 `User` 删除走 ORM cascade 不调 `purge_case_dir`(P0-BE-EN2) | `services/execution_store.py:29-41`;`models/execution.py:38` | 同 P0-BE-EN2 修复 |

#### 🔧 实现细节

- **`execution_rows` 按天 glob**:每次 GET `/executions/{id}/rows` 对历史执行必须扫全部日 JSONL。修复:加 `runs/by-execution/<id>.jsonl` 索引文件。
- **`get_scenario_snapshot` 后端裸返 dict,前端当成 `ScenarioDraft`**(P1-CT6):旧快照 schema 漂移会变成非 `ApiError` 抛错。

---

### 1.5 Auth & Auth Session 域

#### ✅ 已落地能力
- JWT 双 token(access 60min + refresh 14d)
- Fernet 加密 `AuthSession.username_enc/password_enc` at rest
- `_safe_decrypt` 优雅降级(列表场景)
- 启动期 ephemeral 警告
- 404/403 合并避免所有权泄漏
- 用户级 `is_admin` / `is_active` 控制

#### ⚠️ 业务功能正确性问题(已在 SUMMARY §2.1 + §2.2 列出,这里只列业务功能相关)

- **register 完全开放**(P0-BE-S2):首任 admin 后仍可注册。
- **`include_secrets` + `/test` 凭据自提**(P0-BE-S3):任何 bearer 可一次性导出全部明文。
- **`/api/auths/{id}?include_secrets=true` 是 query 参数**:`includeSecrets` 走 query 而非 path/header,违反"敏感操作应该显式"的 API 风格。修复:`POST /api/auths/{id}/reveal` 独立端点,带 audit log。
- **首次启动 ephemeral 警告仅 stdout**:warning 只在 stdout,生产 sink 若只接 stdout/journald 警告可能淹没在启动噪声里。修复:加 `/api/health` 暴露 ephemeral 状态。

#### 🔧 实现细节

- **Auths.vue `token_type` filter 单选**:多公司/多租户场景下不够,改 `el-select multiple`。
- **`AuthSession.password_masked` 前端有声明但 `AuthSessionSecrets extends AuthSession` 时可能冲突**:已撤销(P1-11 撤销),但 `AuthSessionSecrets extends AuthSession` 的 `password` 与 `AuthSession.password_masked` 同名空间但语义相反,扩展时务必保留区分。
- **错误码 BAD_CREDENTIALS=4004 / LAST_ADMIN=4092**:`_codes.py` 已存在但没被广泛使用,只有 auth/users 路由用到;其他 router 仍用字符串 code。

---

### 1.6 Adaptation 域

#### ✅ 已落地能力
- Catalog diff / impact / unindexed-steps / batch lifecycle
- member 自动只读 owner 视图(`scope=mine`)
- rollback 乐观冲突避免批次外修改被覆盖
- `canGenerateCarryBatch` 单点契约(plate 不可达禁用批生成)

#### ⚠️ 业务功能正确性问题

| ID | 问题 | 位置 | 修复 |
|---|---|---|---|
| BF-ADP-1 | **`impact` 兜底逻辑走全表 `composer_scenarios`**:当 `field_name is None`(只传 endpointId)时,必须扫全表找锚点 step,1k+ 场景线性扫 | `services/adaptation_service.py:239-247` | 推到 SQL(JSON 提取)或 endpoint_ref_index 里建 endpoint_id 索引 |
| BF-ADP-2 | **`list_batches` N+1**:`_batch_detail` 每个 batch 查 ops + snapshots + 累 opCounts,N 批次 = N 次 ops + N 次 snapshots 查询 | `services/adaptation_service.py:873-878, 375-402` | `WHERE batch_id IN (selected_ids)` 一次拉 ops/snapshots,Python 端 groupby |
| BF-ADP-3 | **carry drift / service fields 调用 plate 串行 N 次 `/full`**:drift 报告与 `service_fields` 路由对 plate 每个 endpoint 拉一次 `/full`,N 个端点 = N 次串行 HTTP,plate 端连接池未复用 | `services/carry_store.py:60-101`;`services/adaptation_service.py:60-78` | `asyncio.gather` + `asyncio.Semaphore(4)` 限制并发,带超时 |
| BF-ADP-4 | **`ConstantEntry` 创建不互斥 literal/generator**:DB 接受 `value` 和 `spec` 并存;PATCH 的 `_validate_patch` 才校验互斥,但 create 路径只把字段写入 | `routers/constants.py:84-109` | `create_constant` 内做与 `_validate_patch` 同款校验 |

#### 🔧 实现细节

- **AdaptationCenter.vue member 视图缺 403 防御**:`/adaptations/batches/{id}` admin 角色过期时 member 视图拉 batch 时撞 500。
- **`ImpactItem.source` 联合类型过窄**:P1-CT3 已记录。

---

### 1.7 Carry 域(值表)

#### ✅ 已落地能力
- 完整 CRUD:`/carry/defaults` + `/carry/bindings/{service}` + `/carry/drift`
- service → field_path → value 三层嵌套结构
- carry 注入链:`build_carry_context` 在 dispatch 阶段预解析
- preview/export 与 dispatch 同源物化(spec §7 黄金等价)
- `canGenerateCarryBatch` 单点契约

#### ⚠️ 业务功能正确性问题(已在 SUMMARY §3 列出 BF-RUN-3)

- **carry 预览与 dispatch 的 alias 注入顺序不一致**:BF-RUN-3 已记录。
- **`build_carry_context` 索引契约**:`step_fields` 的键 = `definition["steps"]` 原始列表索引,`_apply_carry` 对 converted.steps 做 `enumerate`,锚点索引必须与原始列表对齐;先过滤非 dict 再枚举会让索引漂移、注入错步。**当前实现正确**,但注释依赖人为维护。

#### 🔧 实现细节

- **`CarryConfig.vue:222-229` `valuePlaceholder` 误显示**:P0-FE-V2 已记录。
- **`CarryConfig.vue:280-289` `downloadTemplate` blob 一次性生成**:大表(1万行)卡顿,无进度提示。
- **`AuthSession.password` vs `AuthSession.password_masked` 同名空间**:1.5 已记录。

---

### 1.8 Constants 域

#### ✅ 已落地能力
- 完整 CRUD
- name/entry_kind 不允许 patch
- catalog 失败静默 + entries 失败 throw(单一职责区分)

#### ⚠️ 业务功能正确性问题

- **literal/generator 创建不互斥**(BF-ADP-4)
- **NAME_RE `/^[A-Za-z0-9_]{1,64}$/` 与 `VariableRegistryPanel` 渲染端校验不一致**:常量池 hover 显示 `${var.${e.name}}` 但若 name 含特殊字符会渲染成非法引用。

#### 🔧 实现细节

- **ConstantsPool.vue 570 行中等**,无明显重构机会;但 `useInsertTarget` 复用了(`ConstantPoolPanel.vue:60`)。

---

### 1.9 Plate 代理域(endpoint-catalog / strategy-catalog / generator-catalog)

#### ✅ 已落地能力
- 三个 catalog endpoint 全部代理 plate 域
- `endpoint-catalog/resolve-paths` 响应样本 → JSONPath

#### ⚠️ 业务功能正确性问题

- **`resolveResponsePaths`/代理类 endpoint 的前端类型与 plate 直透**:后端透传 `list[dict]`,前端 TS 是推测出来的 shape。修复:在 proxy router 里包一层 Pydantic schema 锁定输出。

#### 🔧 实现细节

- **`PlateResourceItem.extra` 字段类型过宽**:`api/plate.ts:104-130` 的 `toResourceView` 仅识别 `kind === 'mock'` 和 `kind === 'file'`,其他 kind 默默丢弃。修复:`console.warn` 在丢弃时打日志,或 store 层 `unknownResources` 提示。
- **`utils/catalog-services.ts:30-43` 无 timeout**:裸 `fetch('/plate/api/endpoint?per_page=500')` 没有 AbortController,plate 挂时永远 pending。
- **`api/plate.ts:24` 的 `plateFetch` 走 fetch 而非 http 实例**:accessToken 过期 → 401 → 不走 refresh + 重定向。修复:给 http 加 `baseURL: '/plate'` 的实例。

---

## 2. 前端实现细节评审

### 2.1 状态管理(Pinia stores)

#### ✅ 优秀设计
- **`stores/auth.ts` `refreshOnce()` single-flight**(frontend-state-review 亮点 1)
- **`stores/auth.ts` `clear()` idempotent**(亮点 3)
- **`stores/adaptations.ts` `inflight` + `loaded` 双标志**(亮点 7)
- **`stores/constants.ts` `catalog` 失败静默 + `entries` 失败 throw**(亮点 8)
- **`stores/executions.ts` polling 失败预算**(亮点 9)

#### ⚠️ 实现细节问题

| ID | 问题 | 位置 | 修复 |
|---|---|---|---|
| FE-ST-1 | **`stores/scenario-composer.ts` 写操作混用 `upsertBy` + `splice` + `unshift`**:同一文件内 3 种数组变更模式,watch 行为可能不一致 | `stores/scenario-composer.ts:18-22, 64-74, 88-93, 96-105` | 统一走 `upsertBy` 或全替换 |
| FE-ST-2 | **`stores/auth_sessions.ts` `list.value = [...list.value, a].sort(...)` 修改整个数组引用,触发所有订阅组件重渲染**;部分 patch 走 splice,部分走全替换 | `stores/auth_sessions.ts:37-41, 48` | 统一走全替换或全 splice |
| FE-ST-3 | **`stores/executions.ts` `pollHandle` 单例,store 全局只能同时轮询 1 个 execution**:从 Executions A 跳到 Executions B,A 的 stop 隐式调用,但若用户用 browser back 进 A,不会重新 `startPolling` —— A 的轮询不再恢复 | `stores/executions.ts:178-227` | 轮询绑到组件层,store 仅暴露 `tick(id)` 与 `stop(id)`,组件 onMounted 启动 / onUnmounted 停 |
| FE-ST-4 | **`stores/executions.ts` tick 内 `await fetchRows(rid)` 串行**:展开 N 行级表格 → N 秒才完成一轮 tick,detail 字段仍停留在更早的快照 | `stores/executions.ts:196-199` | `Promise.all(expanded.value.filter(...).map(fetchRows))` |
| FE-ST-5 | **`TopNav.vue` `adaptations.ensureBadgeLoaded()` 没 UI 错误反馈,`lastError` 没有渲染**:plate 502 时徽章不显示,管理员不知道是"无待适配"还是"目录不可用" | `TopNav.vue:69` | TopNav 在 `lastError` 非空时加一个 hint icon(tooltip 显示"目录服务不可用") |
| FE-ST-6 | **`stores/auth.ts` `fetchMe` 用 `(e as { status?: number })` unsafe cast** | `stores/auth.ts:152-175` | `if (e instanceof ApiError && e.status === 401)` |

---

### 2.2 组件复用度

#### ⚠️ 重复定义

| ID | 问题 | 位置 | 修复 |
|---|---|---|---|
| FE-CMP-1 | **`OrchestrationWithSchemes` 桥在 5 个文件重复声明**:`Scenarios.vue` / `CaseComposer.vue` / `ScenarioExportMenu.vue` / `CaseComposerCatalog.vue` 等各自定义/重用 | 多文件 | 顶层 `types/plate.ts` 内集中导出 `OrchestrationWithSchemes extends Orchestration { schemes: SchemeView[] }` |
| FE-CMP-2 | **`EndpointFullView` 在 5+ 文件重复声明**:plate `EndpointFullView` 类型在 api/types/views/components 中反复 inline | 多文件 | 在 `src/types/plate.ts` 内集中导出,所有调用方从统一入口 import |
| FE-CMP-3 | **`JSON.stringify` watch echo 检测在 3+ 文件重复**:`CaseComposerCanvas.vue:859-887` + `CaseComposerConfig.vue:370-391` 等各自实现"防止 v-model 递归更新"的 watch 防护 | 多文件 | 抽 `composables/useNonRecursiveWatch.ts`,三处共用 |

#### 🔧 公共 composables 利用度

- **`useListSearch` 利用好**:Scenarios/Auths/UsersAdmin/ConstantsPool 多处使用 ✅
- **`useInsertTarget` 利用差**:仅 `ConstantPoolPanel.vue:60` 使用,其它常量池插入位置未复用
- **`useFieldDescriptions` 利用好**:DataSetEditor / OpPreview 复用 ✅
- **`useSystemPrefill` 利用好**:CaseComposer 复用 ✅
- **`useSetStatus` 在 4 个 store 各自 keep 一份**:`fetchStatus/lastError` 双字段在 `scenarios-composer` / `constants` / `executions` / `adaptations` 各自实现,应抽 composable。

---

### 2.3 类型安全(frontend-state-review 已大量盘点,这里只列新增)

#### ⚠️ 类型安全盲区

| ID | 问题 | 位置 | 修复 |
|---|---|---|---|
| FE-TY-1 | **`useFieldDescriptions` 全链路 any**:draft 是 `Ref<{ definition: { steps?: any[] } } \| null>`,`DataSetEditor.vue` 的 `mutateDraft((clone: any) => boolean)`、`descriptionByColumnKey` 全 any | `composables/useFieldDescriptions.ts:67`;`DataSetEditor.vue:328` | 改 `Ref<ScenarioDraft \| null>`,边界处加 unknown cast |
| FE-TY-2 | **`utils/jsonpath.ts` 全 any**:`obj: any`,`getByPath/setByPath` 全部 any | `utils/jsonpath.ts:12-45` | 改 `Record<string, unknown>`,仅在最后返回值处 cast |
| FE-TY-3 | **`utils/draft-lint.ts` `steps?: any[]`**:`ScenarioDraft` 已有类型可用,但这里用了 any | `utils/draft-lint.ts:11-18` | 直接 import `StepView` |
| FE-TY-4 | **`api/scenario-composer.ts:178` `converted?: Record<string, any>`**:导出 JSON 时无类型校验,任意字段都直接序列化 | `api/scenario-composer.ts:174-191` | 收紧为 `ScenarioView \| ExecutableScenarioView`,导出前做最小形状断言 |
| FE-TY-5 | **`api/plate.ts` 全 `Record<string, unknown>`**:Plate 代理类 endpoint 透传字段全部 unknown,无类型校验 | `api/plate.ts` 多处 | 在 proxy router 里包一层 Pydantic schema,前端用 zod 在 runtime guard |
| FE-TY-6 | **`utils/useListSearch.ts:88` `String({foo: 1})` 返回 `[object Object]`**:搜索结果里出现 `[object Object]` | `utils/useListSearch.ts:88` | `typeof v === 'string' \|\| typeof v === 'number' \|\| typeof v === 'boolean'` 时才搜索 |
| FE-TY-7 | **`views/CaseComposer.vue:517-568` 用 `(s as any)` 强制 narrow**:既然已经 import 了 `ScenarioView` / `StepView`,`as any` 没必要 | `views/CaseComposer.vue:517,567,568` | 直接用 `s: StepView` |

---

### 2.4 性能

#### ⚠️ 性能瓶颈

| ID | 问题 | 位置 | 修复 |
|---|---|---|---|
| FE-PERF-1 | **`ExecutionsList.vue` 3s 轮询不停,visibility change 不暂停**:1 小时 = 1200 次请求,切到 tab 后回前台看到 stale 列表 0-3 秒 | `views/ExecutionsList.vue:111-123` | 收敛到 `stores/executions.ts` 的 `startPolling` 模式,加 `document.visibilityState` 监听 |
| FE-PERF-2 | **`Executions.vue` 1s 轮询 + tick 内串行 await**:展开 N 行 → N 秒,下一次 tick 启动时上一次还没结束,detail 字段停留在更早的快照 | `views/Executions.vue`;`stores/executions.ts:196-199` | `Promise.all(...)`;并允许错峰(每秒 tick 只 fetch 一个展开 execution) |
| FE-PERF-3 | **`Scenarios.vue` 100+ 行场景不虚拟滚动**:每行渲染嵌套 `el-dropdown` 与 `el-tooltip`,百行表格卡顿 | `views/Scenarios.vue:658 行` | 换 `el-table-v2` 或自实现 virtual scroll |
| FE-PERF-4 | **`VariableRegistryPanel` 50+ 变量时滚动卡**:固定 max-height 600px,但 50+ 变量时滚动卡 | `VariableRegistryPanel.vue` | 加 `vue-virtual-scroller` |
| FE-PERF-5 | **`DataSetEditor.vue` `mutateDraft` 深拷贝在数千行下卡顿** | `views/DataSetEditor.vue:1078 行` | 改为只对改动行 clone |
| FE-PERF-6 | **`CaseComposerCanvas.vue:859-887` `JSON.stringify` watch echo 检测 O(N) GC 压力**:steps 数百条时每次 keystroke 都产生字符串分配 | `views/CaseComposerCanvas.vue:859-887` | 改用 `shallowRef` + 显式 deep 比较;或 `JSON.stringify` 仅在 `local.length` 变化时跑 |
| FE-PERF-7 | **`CaseComposerCanvas.vue:1145-1154` `strategyCandidates` 每次 render 重算**:`Object.fromEntries(...)` + `platePaths.map(toScratchPath)` 无 memoization | `views/CaseComposerCanvas.vue:1145-1154` | `computed` 包裹 |
| FE-PERF-8 | **`Executions.vue` 状态徽标 5+ 种颜色硬编码**:`status-pill.on` / `.off` 等 class 直接硬编 #d1fae5 / #065f46,改主题需 8 处 | `Executions.vue` | 走 theme tokens |
| FE-PERF-9 | **`utils/catalog-services.ts:30-43` 无 timeout**:plate 挂时永远 pending | `utils/catalog-services.ts:30-43` | 加 `AbortController` + `setTimeout(controller.abort, 10000)` |

---

### 2.5 测试覆盖盘点

#### ⚠️ 缺测试的关键组件

| 组件 | 行数 | 风险 |
|---|---|---|
| **`FieldForm.vue`** | 747 | 7 种 ui_kind 渲染 + JSON 域 + 候选下拉 + 字段动作菜单,**0 测试覆盖** |
| **`StrategyForm.vue`** | 231 | 4 种 phase + onFailure 入口 + summary 推导,**0 测试覆盖** |
| **`VariableRegistryPanel.vue`** | 179 | 同名多产出聚合 + unregisteredRefs 推导,**0 测试覆盖** |
| **`ConstantPoolPanel.vue`** | 218 | 三态行模型 + 类型 enum,**0 测试覆盖** |
| **`CaseComposerCanvas.vue`** | 1809 | plate /full 缓存 + WeakMap drag keys + JSON.stringify watch echo,**0 测试覆盖** |
| **`CaseComposerConfig.vue`** | 512 | emitShape + sameSteps 三层防线,**0 测试覆盖** |
| **`CaseComposerCatalog.vue`** | 615 | native fetch 绕 axios + plate 不可达降级,**0 测试覆盖** |
| **`Scenarios.vue`** | 658 | 主路径(查询 / 分页 / 批量操作),**0 测试覆盖** |
| **`CaseDataSetsList.vue`** | - | **0 测试覆盖** |
| **`CarryConfig.vue`** | 492 | 三态行模型回归,**0 测试覆盖** |

#### 🔧 测试覆盖与代码量倒挂
- `DataSetEditor.palette.test.ts` 43468 B(最大)
- `TopNav.test.ts` 5742 B
- 但 FieldForm / StrategyForm / VariableRegistryPanel 完全无单测 → 变量工作台三件套是平台核心 UI,无单测是技术债最低洼处

---

### 2.6 UX 一致性

| ID | 问题 | 位置 | 修复 |
|---|---|---|---|
| FE-UX-1 | **`ExecutionsList.vue:228` removed-cancel 按钮歧义**:按钮文字歧义,实际只是 UI 隐藏 | `views/ExecutionsList.vue:228` | 改为"删除历史"按钮(带确认) |
| FE-UX-2 | **`Scenarios.vue` table 列内嵌 `el-dropdown` 与 `el-tooltip` 嵌套** | `views/Scenarios.vue` | 100+ 行场景换 `el-table-v2` |
| FE-UX-3 | **`AdaptationCenter.vue` member 视图详情列隐藏但 403 死链**:`/adaptations/batches/{id}` admin 角色过期时 member 视图拉 batch 时撞 500 | `views/AdaptationCenter.vue:88-135` | `loadBatches('mine')` 失败统一捕获,根据 status code 区分权限过期 vs 真错误 |
| FE-UX-4 | **`CaseComposer.vue` `runNavTimer` 缺错误处理**:timer 每秒 +1,跳到 /runs 后台挂,UI 不动,用户看不出失败 | `views/CaseComposer.vue` | timer 检测 `maxRunNavSec = 30`,超时报错并跳回 |
| FE-UX-5 | **`AuthSelectorModal.vue` Vue 2 `@update:model-value` 兼容模式**:Vue 3 推荐 `v-model:open` 单 prop | `components/AuthSelectorModal.vue` | 改 `v-model:open` |
| FE-UX-6 | **`CarryConfig.vue:280-289` `downloadTemplate` blob 一次性生成**:1MB 内 OK,大表(1万行)会卡顿,无进度提示 | `views/CarryConfig.vue:280-289` | 流式生成 (`WritableStream`) + 下载进度 toast |
| FE-UX-7 | **`Register.vue` 密码强度条前端可绕过**:`passwordScore>=3` 拦截,但前端可绕过,`axios` 拦截器或 store action 未二次校验 | `views/Register.vue` | 在 auth store 的 register action 内做断言,后端也校验 |
| FE-UX-8 | **`Login.vue` 密码可见性切换无 a11y label**:`:show-password` 走 el-input 内置,但文案"密码" 缺 aria-label | `views/Login.vue` | 加 `aria-label` |
| FE-UX-9 | **`UsersAdmin.vue` 头像色 hash**:在 SSR/无 canvas 环境会撞色 | `views/UsersAdmin.vue` | 收敛色板 hash 空间 |
| FE-UX-10 | **`FilterPopover.vue:323` `commit` 模型与输入实时不一致**:修改 filter 但未 commit 时,列表已更新,与 "commit 才生效" 文档不符 | `views/FilterPopover.vue` | 真正实现 commit-only model,或删 commit 模型直接双向绑定 |

---

### 2.7 a11y 与 i18n

#### ⚠️ 严重缺口

- **i18n 完全缺失**:平台无 `vue-i18n`,所有 `el-form-item label`、`button text`、`placeholder` 硬编码中文。未来若加英文版需全量重写。
- **a11y 几乎为零**:多数 `<button>` 缺 `aria-label`,icon-only 按钮仅靠 `title`。屏幕阅读器读不出"删除 step"等动作。
- **键盘导航缺**:多数下拉菜单(`el-dropdown`)和折叠面板(`el-collapse`)未显式 `tabindex` 配置,键盘用户无法操作。
- **颜色对比度未校验**:暗色 chrome(#1f2933)上的灰色文字(#cbd5e1)在 WCAG AA 下勉强通过,但 #94a3b8 角色标签对比度仅 3.8:1,低于 AA 标准 4.5:1。

---

## 3. 后端实现细节评审

### 3.1 API ergonomics

#### ⚠️ API 风格问题

| ID | 问题 | 位置 | 修复 |
|---|---|---|---|
| BE-API-1 | **错误信封三种混用**:`code:int+msg` / `code:str+message` / `detail:str`(详见 contract P2-5) | 多 router | 立项统一 `{code: number, message: string}` |
| BE-API-2 | **`include_secrets` 是 query 参数**:`/api/auths/{id}?include_secrets=true` 走 query 而非 path/header,违反"敏感操作应该显式"的 API 风格 | `routers/auth_sessions.py:138` | 拆 `POST /api/auths/{id}/reveal` 独立端点,带 audit log |
| BE-API-3 | **`/preview-plate` 命名风格不一致**:其他端点都用 snake_case (`/preview-plate` 是 kebab-case) | `routers/scenarios.py` | 改 `/preview_plate` 或统一允许 kebab-case |
| BE-API-4 | **`getCaseArtifact` 用 query 而非 path 命名**:`?case=case-001&file=engine-log` 而非常规 path | `routers/executions.py:94-123` | `/api/executions/{id}/artifacts/{case}/{file}` 走 path |
| BE-API-5 | **`runs` router 命名不直观**:`POST /api/runs` 是 fan-out 入口(创建 Execution),与"列出 runs"概念不符 | `routers/runs.py` | 改 `POST /api/runs/dispatch` 或 `POST /api/executions/dispatch` |
| BE-API-6 | **RESTful 不严格**:`POST /api/scenarios/{id}/publish` 与 `POST /api/scenarios/{id}/unpublish` 是动作而非资源;`PUT /api/scenarios/{id}/run-schemes` 整表替换语义与 PUT 增量语义不一致 | `routers/scenarios.py:275-298, 455-466` | `/api/scenarios/{id}` 加 PATCH 字段 `{visibility: 'public'\|'private'}` 替代两个动作端点 |
| BE-API-7 | **`/api/adaptations/catalog/diff` 嵌套层级深**:`/catalog/diff` 是 resource 子层级,但 diff 是动词 | `routers/adaptations.py` | `/api/adaptations/diff`(verb 作 resource) |

#### 🔧 API 文档/可发现性

- **OpenAPI 文档未启用交互式 UI**:`create_app()` 没启用 `swagger_ui` 参数,FastAPI 默认的 `/docs` 启用但未配置 URL。
- **后端错误码 `_codes.py` 已存在但没广泛使用**:只有 auth/users 路由用到 `BAD_CREDENTIALS=4004 / LAST_ADMIN=4092`;其他 router 仍用字符串 code。修复:立项"统一错误信封",给出 `{code: number, message: string}` 一种形状。

---

### 3.2 错误处理

#### ✅ 优秀设计
- **`error_mapping helpers`**(`key_error_404` / `not_found_404` / `value_error_http` / `_plate_502`):9+4 处 copy-paste 收敛到 4 处一致性。
- **`run_dispatcher._log_task_exception`** done-callback:不传播 task 异常到 parent。

#### ⚠️ 错误处理缺口

| ID | 问题 | 位置 | 修复 |
|---|---|---|---|
| BE-ERR-1 | **后台 task 异常仅日志,无 metric**:`run_dispatcher._log_task_exception` 仅 loguru.exception,无 metric 暴露,运维只能靠日志扫描发现 | `services/run_dispatcher.py:119-133` | 加 Prometheus counter / histogram |
| BE-ERR-2 | **`_finalize_execution` 失败仅 warning,无 metric**:DB 写失败仅 logger.warning,无指标告警 | `services/run_dispatcher.py:993-994` | 同上 |
| BE-ERR-3 | **`counterDrift` 标记无 metric**:`counter_drift` 字段在 config_json,但无 metric 暴露,运维无法主动告警 | `services/run_dispatcher.py:990` | 加 counter `run_dispatcher_counter_drift_total` |
| BE-ERR-4 | **`plate_client` 无重试 / 退避**:plate 临时 502 时,行级 retry 失败立即终止 | `services/plate_client.py` | 加指数退避重试(最多 3 次) |
| BE-ERR-5 | **`auth_probe.probe` 无超时配置**:SSRF 目标若响应缓慢,probe 阻塞事件循环 | `services/auth_probe.py` | 加 `asyncio.wait_for(probe, timeout=10)` |
| BE-ERR-6 | **`gimbal_launcher.launch` 无超时配置**:子进程若挂死,`_row` 永远等 | `services/gimbal_launcher.py` | 加 `timeout=300` per-launch,超时 kill |
| BE-ERR-7 | **`plate_unavailable` 与 `plate_rejected` 区分不直观**:`plate_unavailable` 是网络错(502 等),`plate_rejected` 是 schema 错(422);但前端 toast 显示无差异化 | `services/run_dispatcher.py:738-747`;`routers/_error_mapping.py` | 前端 toast 区分:plate 不可用 = "目录服务离线";plate 拒绝 = "场景定义有误" |

---

### 3.3 可观测性 / 调试

#### ⚠️ 可观测性缺口

| ID | 问题 | 位置 | 修复 |
|---|---|---|---|
| BE-OBS-1 | **没有 Sentry / 日志上报**:前端 `main.ts:12-18` 没有 `app.config.errorHandler`,组件未捕获的异常会冒到 `window.onerror` | `frontend/src/main.ts:12-18` | 加最小 `app.config.errorHandler` 上报 |
| BE-OBS-2 | **JSONL 调度日志无索引**:`execution_rows` 全日 glob 扫描,30 天历史性能线性恶化 | `services/run_dispatcher.py:1131-1132` | 加 `runs/by-execution/<id>.jsonl` 索引文件 |
| BE-OBS-3 | **`stars.json` 文件损坏无告警**:启动期从 JSON 重建失败仅 warning | `services/marks_store.py:88` | 启动 health check 暴露 stars.json 状态 |
| BE-OBS-4 | **没有 request id 链路追踪**:每个请求无 correlation id,日志检索跨服务/跨行难 | `core/middleware` 缺 | 加 `X-Request-ID` middleware,日志带 request_id |
| BE-OBS-5 | **没有结构化日志格式**:loguru 默认文本格式,生产接 ELK / Loki 时难解析 | `core/logging` | 配 `serialize=True` JSON 输出 |
| BE-OBS-6 | **`run_dispatcher` 模块级全局状态散落**:`_in_flight` / `_shutting_down` / `_launch_sems` / `_cancel_requested` / `_tasks_by_execution` / `_row_states` 6 个全局变量 | `services/run_dispatcher.py:106-234` | 收敛到一个 `DispatchState` dataclass,方便测试 reset 与 lifespan 检查 |
| BE-OBS-7 | **`P9 async JSONL writes` 写失败仅 warning,无重试**:`_append_log` 写失败只告警,绝不打断 fan-out;但写失败意味着审计面丢失,运维无法追责 | `services/run_dispatcher.py:874-886` | 失败后写本地 `.failed` 文件作为 fallback,启动期扫描回补 |

---

### 3.4 数据库 / 持久化

#### ⚠️ 数据库设计缺口

| ID | 问题 | 位置 | 修复 |
|---|---|---|---|
| BE-DB-1 | **`Execution.scenario_id` 无 FK** | `models/execution.py:38` | P0-BE-EN2 修复 |
| BE-DB-2 | **`scenario_endpoint_ref` 无 FK** | `models/scenario_endpoint_ref.py:1-25` | P1-BE-CO5 修复 |
| BE-DB-3 | **`User` 删除走 ORM cascade 不调 `purge_case_dir`** | `models/user.py` | P0-BE-EN2 修复 |
| BE-DB-4 | **`scenario_composer_scenario` 无 `version` 列,无乐观锁** | `models/composer_scenario.py` | BF-SCN-1 修复 |
| BE-DB-5 | **`ComposerDataSet.row_count` 列冗余** | `models/composer_data_set.py` | 删列,统一读时 SUM |
| BE-DB-6 | **stars 是 JSON 文件而非 DB 表** | `services/marks_store.py` | 迁到 DB 表 |
| BE-DB-7 | **`_next_dataset_id` 不原子** | `services/data_set_store.py:233-251` | BF-DS-1 修复 |
| BE-DB-8 | **`SQLite` 未启用 WAL** | `core/db.py` | P0-BE-EN1 修复 |
| BE-DB-9 | **没有 migration 工具**:V1→V3 迁移路径在 spec 提到 raw-SQL 但代码没找到 | 无 `alembic` / 自研 migration | 加 `alembic` 或自研 migration runner |

---

### 3.5 配置 / 启动 / 部署

#### ⚠️ 配置缺口

| ID | 问题 | 位置 | 修复 |
|---|---|---|---|
| BE-CFG-1 | **`FERNET_KEY` / `JWT_SECRET` ephemeral 时无强失败** | `core/config.py:87-92` | P0-BE-S1 修复 |
| BE-CFG-2 | **`ALLOW_REGISTRATION` 配置项缺失** | `core/config.py` | P0-BE-S2 修复 |
| BE-CFG-3 | **`SERVICE_BINDING_URL_ALLOWED_SCHEMES` 配置项缺失** | `core/config.py` | P2-BE-12 修复需要该配置 |
| BE-CFG-4 | **`MAX_RUNS_PER_EXECUTION` 上限配置存在但无 README 说明** | `core/config.py` | 加 README 配置清单 |
| BE-CFG-5 | **`CORS_ORIGINS` 默认值含 `localhost:5173`**:Vite dev server,但生产部署容易忘记移除 | `core/config.py` | 加 `ENV=prod` 时强制移除 localhost |
| BE-CFG-6 | **没有 secrets 管理集成**:FERNET_KEY / JWT_SECRET 只能从 .env 读,无法从 vault / K8s secret 注入 | `core/config.py` | 加 secrets loader(支持 vault / K8s secret 注入) |
| BE-CFG-7 | **没有 health check 端点分级**:`/api/health` 仅返回 `{"status": "ok"}`,不能区分 DB / plate / JWT secret / Fernet key 状态 | `main.py:130-132` | 加 `/api/health/deep` 返回四组件状态 |

---

## 4. 业务功能优先行动(去重于 SUMMARY,按域归口)

| 域 | 行动 | 估时 | 影响 |
|---|---|---|---|
| **Scenario** | 加 `version` 列 + 乐观锁 + runSchemes 透传保留改造 | 1 天 | 消 BF-SCN-1/3 双 tab 编辑丢更新 |
| **Dataset** | `_next_dataset_id` 改 `MAX()+1` SQL + IntegrityError 分类重构 | 0.5 天 | 消 BF-DS-1/2 并发竞态 |
| **Run** | `MAX_CONCURRENT_LAUNCHES` 改 owner-级 quota + carry 顺序统一 + counterDrift 阻止 done | 1.5 天 | 消 BF-RUN-1/3/5 |
| **Run** | `_cancel_requested` 改 `asyncio.Event` + `_resolve_exec_auths` 改 Lazy decrypt + `_fail_whole_execution` 补 JSONL final 枚举 | 1 天 | 消 BF-RUN-2/4 + BF-EXE-3 |
| **Execution** | `cancel_execution` 改条件 UPDATE + `reset_cancel_state()` 调 lifespan | 0.5 天 | 消 BF-EXE-1/2 |
| **Adaptation** | `impact` 推 SQL + `list_batches` 改 IN 查询 + carry drift 并发拉 + ConstantEntry 互斥校验 | 1 天 | 消 BF-ADP-1/2/3/4 |
| **Plate 代理** | `endpoint_id` URL encode + `plateFetch` 接 http 实例 + 前端 `resolveResponsePaths` 加 zod 守卫 | 0.5 天 | 消 P2-BE-6 + FE-TY-5 |
| **前端 store** | 收敛 `useSetStatus` composable + `pollHandle` 改 per-component + `tick` 内 `Promise.all` + `TopNav` 错误反馈 | 1 天 | 消 FE-ST-1/2/3/4/5/6 |
| **前端组件** | 顶层 `types/plate.ts` 集中 `OrchestrationWithSchemes` / `EndpointFullView` + 抽 `useNonRecursiveWatch` composable | 0.5 天 | 消 FE-CMP-1/2/3 |
| **前端类型** | 收紧 `useFieldDescriptions` / `jsonpath.ts` / `draft-lint.ts` / `converted` 类型 + 删 `SystemTag \| string` | 0.5 天 | 消 FE-TY-1/2/3/4 + P1-CT3 |
| **前端性能** | `ExecutionsList` 收 `startPolling` + `Executions` tick 并发 + `Scenarios` 虚拟滚动 + `VariableRegistryPanel` virtual + `DataSetEditor` 增量克隆 + `CaseComposerCanvas` shallowRef | 1.5 天 | 消 FE-PERF-1~7 |
| **前端测试** | 补 FieldForm / StrategyForm / VariableRegistryPanel / ConstantPoolPanel / CaseComposerCanvas / CaseComposerConfig / CaseComposerCatalog / Scenarios.vue 主路径 / CaseDataSetsList / CarryConfig 单测 | 1.5 人天 | 消 P2-FE-V9 |
| **前端 UX** | `ExecutionsList` 按钮文字 + `CaseComposer` runNavTimer 超时 + `AuthSelectorModal` Vue 3 v-model + `CarryConfig` 流式下载 + `Register` 密码强度后端校验 + `FilterPopover` commit 一致性 | 1 天 | 消 FE-UX-1/2/3/4/5/6/7/10 |
| **后端 API** | 统一错误信封 `{code: number, message: string}` + `/preview-plate` 命名一致 + `runs` 改名 + `_codes.py` 推广 + `getCaseArtifact` 改 path | 1 天 | 消 BE-API-1/3/5 + P1-CT7 |
| **后端可观测性** | 加 Sentry 上报 + 加 `X-Request-ID` middleware + JSON 日志 + metric counter + module 级全局收敛 `DispatchState` | 1.5 天 | 消 BE-OBS-1~7 |
| **数据库** | `Execution.scenario_id` FK + `scenario_endpoint_ref` FK + `version` 列 + `stars` DB 表 + WAL/busy_timeout + `ComposerDataSet.row_count` 删列 | 1.5 天 | 消 BE-DB-1~9 |
| **配置/部署** | 加 `ENV` 字段 + ephemeral 强制失败 + `ALLOW_REGISTRATION` 开关 + `/api/health/deep` + secrets loader | 0.5 天 | 消 BE-CFG-1/2/5/7 |

总计约 **15 人天** 可消解全部业务功能 + 前后端实现 P1/P2(不含 P0 安全)。

---

## 5. 与 SUMMARY 的差异说明

| 维度 | SUMMARY.md | BUSINESS_FUNCTIONALITY_REVIEW.md |
|---|---|---|
| 切分视角 | 按严重度 P0/P1/P2 | 按业务域 + 实现层切片 |
| 内容侧重 | 安全 / 并发 / 状态机 | 业务功能正确性 + 前后端实现细节(API ergonomics / 状态管理 / 性能 / 类型 / 测试 / UX / 可观测性) |
| 适合读者 | 安全 / SRE / 技术负责人 | 各业务域 owner / 前端架构师 / 后端架构师 |
| 行动排序 | 按投资回报(P0 优先) | 按业务域归口(让各 owner 认领) |
| 总体评级 | B+(生产前需 P0) | B(业务链路通顺,生产前需按域 P1 收敛) |

两份互补使用:
- SUMMARY 用于"决定做什么 / 不做什么"的优先级判断
- BUSINESS_FUNCTIONALITY_REVIEW 用于"具体到哪个文件 / 哪一行要改 / 怎么改"

---

**评审结束**. 若对任一业务域需要更深入的代码走查(例如 carry 注入的全链路追溯、scenario 编辑并发场景的时序图),请直接指明。
