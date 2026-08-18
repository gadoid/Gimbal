# Deferred Code Review Items

Items from the 2026-07-16 code review that are intentionally **not**
addressed in the current pass.  Each entry states the reason for
deferral so a future pass can re-evaluate.

The review criteria used for the current pass:
- **Low impact** — no behavior change beyond a bug correction or a pure
  deletion; tests still pass.
- **Reduces redundancy** — net code reduction (helper extraction, dead
  code removal, etc.).

Items that don't meet one of these two criteria are deferred.

---

## P0 — Real risk (deferred, needs design)

| # | Location | Issue | Why deferred |
|---|---|---|---|
| 7 | `backend/app/schemas/hidden_profile.py:14,20` | `scope` field is always `"case"`, never used as discriminator | **Design decision**: drop the field, or add a real discriminator branch.  Not redundancy — feature question. |
| 10 | `frontend/src/components/ExecutionDrawer.vue:486-518` | Three watchers race on textarea content | **State fix**: needs single source of truth for the dirty marker.  Already partially addressed — see FIXED list. |
| 12 | `frontend/src/api/http.ts:82-105` | `refreshInFlight` is a module-level singleton | **Concurrency fix**: needs per-request refresh guard.  Larger refactor of the auth interceptor. |
| 13 | `frontend/src/views/Executions.vue:331-378` | `drainStreamInBackground` double-fetches log on reconnect | **State fix**: needs the reconnect path to skip the legacy fetch.  Touches SSE handling. |

## P3 — Style consistency (deferred, not redundancy)

| # | Location | Issue | Why deferred |
|---|---|---|---|
| 55 | `backend/app/routers/auth.py` vs `users.py` | Mixed Chinese/English `detail` messages | **Style decision**: pick one language per surface, or split auth vs business.  Touches every router. |
| 56 | `backend/app/routers/auth_sessions.py:189,199` | Chinese error strings in otherwise-English file | Same as #55. |
| 57 | `backend/app/routers/cases.py` vs `schemas/execution.py` | 400 vs 422 for validation errors | **Convention**: pick a single error contract.  Cross-router change. |
| 58 | `backend/app/schemas/user.py:47`, `auth.py:49` | `created_at: str` annotation but accepts `datetime` | **Type hygiene**: cosmetic — `model_validate` coerces.  No behavior change. |
| 61 | `frontend/src/views/CasesPublic.vue` | Row-click + case-name button + "查看详情" dropdown all navigate to the same route (three-way duplicate) | **UX decision**: consolidate or differentiate. |
| 62 | `frontend/src/views/*` | Inconsistent error-toast fallback strings (`'保存失败'` / `'操作失败'` / `'删除失败'`) | **Style decision**: centralize the fallback.  Cross-file. |
| 64 | `backend/app/services/executor.py` | `_run_one` spans ~200 lines (yaml render + decrypt + subprocess + DB persist in one function) | **Decomposition**: split into render/decrypt/spawn/persist phases.  Deferred — counter writes are already atomic (see #5 in FIXED 2026-08-19), so the remaining split is structural only. |
| 65 | `backend/app/routers/cases.py` vs `cases_composer.py` | Legacy file-based + V3 DB-backed cases domains coexist; correct routing depends on router registration order + custom `v3_case_id` converter | **Retirement plan**: needs a legacy→V3 migration script + deprecation window.  Structural, not incremental. |

---

## FIXED in the 2026-07-16 review pass

### Backend (158 tests passing)
- Removed: `Case.tag_list` (unused property), `CaseFavorite` (orphan model), `require_admin()` (unused dep), unused imports in `auth_sessions.py` / `cases.py` / `executor.py` / `routers/executions.py`
- Removed test imports: `import yaml` in 3 test files
- Removed dead `logger.info` in `conftest.py:53-57`
- Removed empty `__init__.py` shims
- Merged `run_execution` and `rerun_run` yaml-render paths into a shared `render_execution_yaml` helper
- Removed redundant pump-thread join chain in `_subprocess_run_streaming`
- Removed in-place yaml writing from `rerun_run` (now uses `_write_temp_yaml`)

### Frontend (76 tests passing)
- Removed: `setTokens` / `setUser` exports from `auth.ts`; `fetchToken` from `auth_sessions.ts` (API + store); `lastError` from `editMode.ts`; `auths` prop from `EditableConfigPanel.vue`; whole `src/utils/errors.ts` (orphaned)
- Replaced 3 inline `setStatus` helpers with shared `useSetStatus` composable
- Replaced 4 list-view search filters with shared `useListSearch` composable
- Consolidated 3 status-label maps in `Executions.vue` (`EXEC_LABELS` + `RUN_LABELS`)
- Refactored `loadShow` + watcher into a single idempotent `loadDrawerData`
- Removed `Object.assign` reactivity-hack in `EditableStepCard.removeHeader` (Vue 3 `delete` suffices)
- Fixed `?` keydown scope: now skips `<select>` and `contenteditable` in addition to `INPUT`/`TEXTAREA`
- Removed `onUnmounted(stopPolling)` from `executions.ts` store (the watcher-callback returned `stop` already handles teardown)
- Removed `import yaml` from 3 backend test files
- Admin argv UI: removed placeholder-text pre-population; textarea is empty by default, dirty-marker turns on as soon as the user types; `buildDefaultCommandLine` deleted

---

## FIXED in the 2026-08-19 alignment pass

Backend (218 tests passing):
- **Unified favorites + stars into one `MarkStore`** (`app/services/marks_store.py`): legacy `cases.py` module-global `_FAVORITES`/`favorites.json` (non-atomic write) and `stars_store.py`/`stars.json` (atomic write) replaced by a single class with two instances — `favorites` + `stars`.  Favorites gained atomic tmp+fsync+replace writes; rename/delete migration logic became `rename_item`/`remove_item`.  `stars_store.py` deleted; `scenario_store`/`scenarios.py`/`cases.py` now share the one store.  Resolves the dual-store drift (2026-07 review structural finding).
- **Extracted run-lifecycle machinery** (`app/services/run_lifecycle.py`): `spawn_safe_run` / `drain_in_flight_runners` / `reconcile_orphan_runs` / `_safe_run` / `is_shutting_down` moved out of `routers/executions.py`; `main.py` lifespan no longer imports router internals.  Router now only handles HTTP concerns.
- **Restored env-based CORS** in `main.py` (`settings.CORS_ORIGINS`), replacing the TEMP `allow_origins=["*"]` LAN-debug loosening.
- **Verified already-fixed P0s** (removed from the deferred table): #2 rerun idx race (fixed via `uq_run_idx` unique constraint + IntegrityError retry), #3 fire-and-forget spawn (fixed via `spawn_safe_run` handle tracking + lifespan drain), #5 dual-session counters (fixed via atomic `UPDATE ... + 1` SQL), #6 favorites TOCTOU (superseded by MarkStore's lock-guarded initial load), #8 rerunning flag wiped by polling (fixed via store-managed `markRerunning` Set).

Backend tests (218 passing):
- `conftest.py` `_isolate_favorites` → `_isolate_marks` (repoints both MarkStore instances at tmp dirs; no more router-internals monkeypatching)
- `test_cases_router.py` / `test_upload_saveas.py` / `test_scenario_composer_api.py` / `test_executions.py` rewritten against `marks_store` / `run_lifecycle` public APIs instead of router privates

Frontend (132 tests passing):
- Deleted the `src/utils/http.ts` re-export shim; `api/scenario-composer.ts` imports `@/api/http` directly
- `.priority-pill` base block centralized into `styles/priority.css` (was triplicated in CasesMine / CasesPublic / ExecutionDrawer scoped CSS)
- `CasesMine.vue` now imports `MAX_VISIBLE_TAGS` from `@/utils/case-row` like `CasesPublic.vue` (was a local duplicate const)
- Documented the intentional `encodeURI` (not `encodeURIComponent`) in `api/cases.ts get()` — case ids may contain real path separators

Hygiene:
- Resolved merge-conflict markers in `src/gimbal-platform/.gitignore`
- Removed the stray `nul` file at the repo root

## FIXED in the 2026-08-19 security hardening pass

Backend (232 tests passing):
- **P0 privilege escalation** (`users.py`): member `PATCH is_admin` → 403/4032 (was a one-call self-promotion); member `DELETE` of another user → 403/4031; `reset-password` restricted to admin-or-self (was a full account-takeover: any member received any user's new plaintext password). `require_admin`/`AdminUser` dependency added in `core/deps.py`.
- **P0 path traversal** (`cases.py`): `upload_case` scenarioId and `save_as_case` new_name now pass the same `_is_invalid_stem` validation as `/rename` + `/copy` (was an arbitrary-path write primitive).
- **P1 cross-user read** (`get_case`): private cases are owner-only now (existence-hiding 404, matching `get_case_show`).
- **Rerun orchestration extracted** to `app/services/rerun.py::rerun_single_run`; router is a thin transport layer. Synchronous run-to-completion semantics kept on purpose (frontend depends on the post-run response) — moving to background + polling remains deferred.
- **Executor hardening**: `Literal` import fixed; log-file fd leak fixed (always closed in `_subprocess_run_streaming` finally); live-subprocess registry (`_live_procs` + `kill_all_live_subprocesses`) wired into `run_lifecycle.drain_in_flight_runners` so shutdown kills orphaned `gimbal` children (cancelling the `asyncio.to_thread` task can't).
- **Ephemeral-key startup warnings**: `JWT_SECRET_EPHEMERAL`/`FERNET_KEY_EPHEMERAL` flags on settings; lifespan logs an actionable warning when either secret was freshly generated.
- **preview-plate mapping**: upstream 4xx (draft rejected) now maps to 422 instead of 502.

Frontend (141 tests passing):
- **URL encoding unified** (`api/cases.ts`): single `encodeCaseId` helper (encodeURI, keeps `/` for path-style ids) — `remove`/`publish`/`getHidden`/`putHidden` previously used `encodeURIComponent` and 404'd on slash-ids.
- **fetchMe** clears the session only on a definitive 401; network errors / 5xx keep stored tokens.
- **Cases.vue**: real pagination (was fake — pager rendered but never sliced), delete confirmation dialog, bogus `show-system`/`show-module` FilterPopover props removed.
- **Filter layer defensive** (`filters.ts` + `FilterPopover.vue`): pools typed `Partial<CaseSummary>[]`, missing `tags`/`module`/`updated_at` tolerated (the V3 composer `Case` shape used by Cases.vue lacks them — used to crash `flatMap(c => c.tags)`).
- **UsersAdmin route** admin-gated (`meta.requiresAdmin` + `beforeEach` guard), matching the new backend policy.

Deferred policy items (intentional, tracked):
- **Public uploads by members remain open** by design ("+ 提交公共用例" is a member feature; collisions get `-pub-N` suffix, so no shadow-overwrite). An admin audit queue for public submissions is a product decision — deferred.
- **rerun stays synchronous** in-request (API contract); background + polling deferred.

## 2026-08-19 功能检查轮（安全/功能审计后修复记录）

已修复（含回归测试，后端 235/235、前端 154/154 通过）：
- save-as 越权复制他人私有用例（补源可见性校验，404 隐藏存在性）
- POST /executions 可执行他人私有用例并读输出（补 case 访问校验）
- 空 owner 场景任意 member 可改/删（改为锁死，仅 admin）
- display_name 提权链（composer 所有权基于 display_name — 现强制全局唯一且不得与用户名冲突；register/create/patch 三处）
- DataSetEditor 编辑保存丢行（store preview 截断为 3 行 → 改用 getDataSet 全量）
- CaseEditorBasic 新建用例死表单（接通 POST /cases createCase）
- HeadStepper ④ 数据集死链接（场景级 data-sets 路由不存在 → 指向第一个用例的数据集）
- 4 处删除操作补二次确认（场景/用例/execution×2）
- rerun 同步阻塞 vs axios 30s 超时（rerun 请求单独 330s）
- Auths 测试连通/保存错误吞掉（改用捕获的错误对象）
- CaseComposer 用例持久化失败静默（改报错提示）
- 场景库 Tab 不过滤列表（favorite tab 现真过滤；public 徽标改真实值）
- 场景库变量列恒空（config.vars 是对象，改 Object.keys 计数）
- TopNav 对 member 显示用户管理入口（adminOnly 过滤）
- reconcile_orphan_runs 漏掉 started_at=NULL 的 queued 行（回退 created_at + 连带回收 pending 子行）

结构性欠账（本轮未动，需专项设计）：
- **composer 所有权应从 display_name 迁移到不可变 user.id**（display_name 唯一性只是缓解；迁库需迁移 scenario/case/data-set 存量 owner 数据）
- legacy case_id 以 `case-`/`sc-` 前缀撞 v3_case_id 转换器 → 误路由到 composer 路由（404）
- POST /auths/{id}/test 的 SSRF 面（无 scheme/内网地址白名单）
- CaseSummaryOut.file_path 泄露服务器绝对路径
- V3 路由错误信封（字符串 code + message）与前端 http.ts 解析器（数字 code + msg）不匹配
- v3 runs / data-sets 读侧全局开放（若共享是设计则至少 run 触发应复核）
- GET /users 对 member 开放（用户枚举助攻攻击目标选取）

### 审计第 2 轮（自查回归）— 2026-08-19
上轮修复的自查 + 补漏，全部已修复（backend 235/235, vitest 154/154, vue-tsc 除既有 TS6305 外干净）：

上轮引入的 bug（均已修）：
- CaseEditorBasic 新建：`updatedAt: ''` → Pydantic 422（datetime|None）；caseId 缺 `case-` 前缀 → v3_case_id 转换器不匹配、创建后 404；router.replace 组件复用导致二次保存重复建 case（改 window.location.assign 全量跳转）
- DataSetEditor 加载失败后仍可保存（loadFailed 时禁用保存按钮）
- executions.py 访问检查误用 loader._cache 私有状态（改 scan(owner_id=user.id)）
- run_lifecycle cutoff 时区混用（aware utcnow vs naive DB 列 → naive）

补漏修复：
- RunResponse 增加 executionId（唯一有详情路由的 id）— CaseComposer / CaseRunConfig 运行后跳 `/executions/{executionId}`（此前跳 `/executions/{字符串runId}` 永不匹配 `\d+` 路由）
- CaseComposer 运行确认按钮 800ms 跳转窗口内可双击（runDispatching 保持到导航）；删除 TopNav 死导入
- CaseRunConfig ?dataSetIds 预选不校验（'new'/失效 id 会带进 /runs 导致整次 404）→ 加载后过滤 + 一次性警告；comma-split 加 trim
- 移除 /cases-overview 死路由 + views/Cases.vue（无入口、含假收藏按钮）
- Login "30 天内保持登录" 复选框无任何效果（token 本就持久 localStorage）→ 改为静态提示
- executions store 详情轮询 404 / 连续失败不停（1 req/s 永续）→ pollError + 连续 10 次失败预算 + 404 即停
- auth register / users create 补反向冲突：新 username 不得撞已有 display_name（所有权身份双向唯一）

遗留（本轮未动）：
- Scenarios favoriteCount 与过滤后列表计数口径不一致（展示层小问题）
- DataSetEditor fallback 未校验 full.caseId === caseId（跨 id 覆盖风险低但存在）
- register/patch display_name strip 归一化不一致
- clone-scenario 仍为前端复制草稿的实现，未复用 copy API（若有）
- DataSetEditor / CaseDataSetsList 单条运行按钮仍为"待后端"stub

### 审计第 3 轮 — 2026-08-19
双探针（自查回归 + 未覆盖前端区域）。全部已修复（backend 235/235, vitest 154/154, vue-tsc 除既有 TS6305 外干净）：

P1 修复：
- http.ts refresh 死锁：refresh 请求自身 401 时再次触发 refreshOnce → await 同一 in-flight promise → 永久挂起且不清登录态。refresh 调用现在跳过刷新分支，直接走失败清理 + 跳 /login
- dataSets 部分缓存污染：CaseDataSetsList/DataSetEditor 的 fetchDataSets(caseId) 会整组替换 store.dataSets（只含单 case），此后进 /cases/B/run 时 `if (!dataSets.length)` 跳过拉取 → 网格空 + 预选全被误判无效。CaseRunConfig 现无条件 fetch 全量
- pollError 死状态：轮询放弃后页面永远骨架屏（404 删档/连续失败 10 次无人可见）。Executions.vue 增加错误态（告警条 + 重新加载/返回按钮）；手动刷新成功清除 pollError 且对非终态执行自动恢复轮询；首屏加载失败也走错误态而非无限骨架
- 删除 execution 失败静默（ExecutionsList / Executions.vue 均 await 无 catch）→ 报错 toast
- ExecutionsList 3s 轮询 setInterval 直接调 fetchList（rethrow）→ 后端宕机每 3s 一个 unhandled rejection；列表加载失败也由 el-empty 假装"暂无记录" → 现改 el-alert 错误态
- DataSetEditor 列重命名丢数据：表头 el-input 只改 columns[idx]，rows 仍按旧 key 存值 → 保存带旧键+空新键。watch 增加重命名迁移（同长度+旧名消失时搬 key）
- RunDialog 新建数据集 JSON.parse 失败静默按 [] 创建（整组输入丢失）→ 报错中止；非数组也拒绝

P2 修复：
- DataSetEditor 假状态徽标（['PASS','FAIL','SKIP'][i%3] 伪造结果）→ 移除
- CaseRunConfig "保存为运行模板" 复选框无任何效果 → 移除，改提示文字
- CaseComposer 运行跳转 setTimeout 未清理（用户 800ms 内手动离开仍被强行拉走）→ onUnmounted 清除
- register/create_user 的 display_name 未 strip（与 patch 归一口径不一）→ 三处统一 strip

遗留（未动，多为展示层小问题）：
- CaseComposer 运行入口不发送 auths（与 CaseRunConfig 不一致，${auth.*} 引用会在运行期失败且无警告）
- CaseComposer 打开已有场景后首次"下一步"触发一次多余 auto-save（deep watcher 误置 dirty）
- 场景"克隆为副本"对未保存草稿静默无效；数据集"复制"/单条运行、FieldForm 文件上传仍为待后端 stub
- scenario-composer store fetch 吞错 → 视图层 catch 死代码，加载失败显示为空列表
- ExecutionDrawer 创建失败 toast 可能显示旧 lastError（create 从不写 lastError）；CasesMine 上传失败回退读 casesStore.lastError（直连 api 从不写）
- CasesMine 空态提示指向不存在的自身菜单项（"复制到我的"只在 CasesPublic 行菜单）
- CaseConfigReadonly 有 `to="#"` 占位死链；scenario-draft.loadFromSaved 无调用方

### 审计第 4 轮 — 2026-08-19
双探针（第三轮修复复查 + 后端深挖）。已修复（backend 237/237 含 2 个新增安全回归, vitest 154/154, vue-tsc 除既有 TS6305 外干净）：

后端（本轮重点）：
- **P0** POST /runs 无任何归属检查：任何 member 可枚举/猜测 case_id 运行他人 case（fan-out 会对配置的 env 服务发真实子进程请求）。router 层现校验 created_by == 本人 或 admin（403 not_owner）
- **P1** GET /data-sets 与 /{id} 全局开放：跨用户读他人数据集全量业务参数行。list 现按"父 case created_by == 调用者"过滤（admin 全量）；/{id} 复用写侧 _require_owner
- **P2** auth_sessions：FERNET_KEY 轮换后 GET /auths 与 /fetch-token 因 fernet ValueError 直接 500。list 侧 _safe_decrypt 降级为占位符（行仍可见可编辑）；fetch-token 明确 409 提示重新保存
- **P2** DELETE /executions/{id}：SQLite FK 默认关闭，ON DELETE CASCADE 不生效 → exec_runs 孤儿行永久堆积。现显式 DELETE 子行
- **P2** run_dispatcher fan-out 结束时绝对值回写计数器，会覆盖并发原子增减（用户中途删行 MAX(0,col-1) 被回写冲掉）。改为每行完成即原子 +1/+1，结束时只写终态 status/时间戳

第三轮修复的复查发现（均已修）：
- Executions 详情分支：轮询失败预算耗尽时 detail 保留旧值但无任何提示 → 详情视图顶部补 pollError 警告横幅（数据可能过期）
- DataSetEditor 列名重命名为已有列名会静默覆盖合并两列数据；清空列名使数据失联并注入 '' 键 → 两种非法态均回滚 + 警告
- RunDialog prompt 以 ESC/右上角关闭时 reject 'close' 被当错误弹 toast → 与 'cancel' 同样静默
- 复查确认 CLEAN：http.ts refresh 跳过逻辑、CaseRunConfig 全量拉取、ExecutionsList 错误分支、Pydantic display_name 赋值、CaseComposer runNavTimer

新增回归测试：test_member_cannot_run_another_users_case、test_member_cannot_read_another_users_datasets

遗留（未动）：
- v3 cases/scenarios 读侧（GET by-id / list / draft）仍全局开放——若是"共享库"设计需产品确认；若否需加 visibility 字段（结构性，涉及迁移）
- POST /users 任何 member 可开新账号（Spec-1 文档写明有意，需产品复核）；GET /users member 开放（既有 deferred）
- /auths/{id}/test SSRF 面（既有 deferred）+ 新增小注：错误信息带内网 URL、token 前缀回显
- 并发同 id 创建的 TOCTOU（SQLite 无 busy_timeout → 偶发 500，丢失一次写入，影响小）
- run_dispatcher._fanout 里的 plate_ok/plate_failed 局部计数已不再用于回写（无害残留）
