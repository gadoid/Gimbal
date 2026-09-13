# ADR 0003:已退场功能清单(退场记录收口)

## 状态

已实装 / Accepted。

本文件是**退场知识的唯一归宿**:功能退场后,代码注释不再承载
「已移除/已退场/原为 XX」类历史叙述,统一收录于此。代码中的注释
只描述当前行为;需要追溯历史时查本表与所引 spec/commit。

| # | 功能 | 退场日期 | 替代语义 | 退场提交 |
|---|------|----------|----------|----------|
| 1 | `queryUser` / `query_user`(运行方案查询凭证) | 2026-09-09 | 查询凭证唯一来源 = `config.users` 首键(查询身份 = 执行身份),与运行方案无关 | (裁定日早于本清单,见 spec §3.1/§5) |
| 2 | DataSetEditor 基线区 / 直填列 / 提升入口 | 2026-09-11 | 列宇宙 = `config.vars`(引用扫描派生);var 基线编辑入口 = 置顶基线行;字面值编辑的家在编排器 FieldForm | `bd15cc5`(spec v2 §6/T0) |
| 3 | 期望提升链(exp_*) | 2026-09-11 | 期望偏离的语义位置 = 断言管理注册表(条目自含 injection + asserts,`assertion_registry` 场景级节) | `b912d59`(spec v2 §2/§9) |
| 4 | `step.request.fields_meta` 作为请求目录数据源 | (随会话级现拉改造) | 数据源 = 会话级按 `endpoint_id` 现拉 `/full`,不读持久化快照 | (见 CaseComposerCanvas `stepDecls`) |
| 5 | 契约缓存手工版本号协议 `endpointFullVersion` | 2026-09-13 | 缓存容器本身是 Vue 响应式(`shallowReactive` Map)—— 消费方读缓存即建立依赖,无需手写版本号 | `c756984` |
| 6 | 四个视图各自的本地判定函数副本(`injectablePathsOfStep` / `assertTargetsOf` / `deadOf` / `contractPending`) | 2026-09-13 | 判定面唯一来源 = `useInjectableSurface` composable,视图只消费 | `c719fda` |
| 7 | `endpoint_declarations` 自持 `_CACHE` dict + `_WARNED` 集合 | 2026-09-13 | 共享 `TtlLruCache`(LRU 上界 + 回退窗 + 成功那刻打点)+ 时间老化告警表 `_WARNED_AT` | `ec904ec` |
| 8 | `requestDeclarationsOf`(「读 + 隐式取数」合体口) | 2026-09-13 | 读 / 取分离(裁定 C18):读 = `getEndpointFull` / `endpointFullState`(纯缓存读),取 = `ensureEndpointFull`(幂等,宿主显式触发) | `7ead7d6` |
| 9 | 前端对**声明半**的自行归一化 / 展开(`injectablePathSetOf` 吃 `DeclarationEntryView[]`,内部 `catalogPaths` + `toTemplatePath` 推导) | 2026-09-13 | 声明面由**后端**随 `/full` 算好(`declared_surface`:归一化 / 容器前缀 / 模板形态全部展开的扁平集合),前端只并入(`injectablePathSetOf` 的入参由声明树数组换成扁平字符串数组或 `null`) | `e3c80cd`(后端出口 `84aef02`) |
| 10 | `pathResolvable` 的**容器前缀扫描**(`p.startsWith(form + '.')` / `form + '['`) | 2026-09-13 | 两侧集合都**物化**前缀:body 半由 `bodyPathSetOf` 展平(`containerPrefixes`,与后端 `_container_prefixes` 同构件),声明半由后端加进 `declared_surface` ⇒ 判定只剩两次成员测试 | `e3c80cd` |
| 11 | `endpoint_declarations` 自持的 `/full` **取数与缓存**(`_fetch_declarations` / `_refresh` / `_cache()` / `_CACHE` / `_CACHE_CFG` / `_cache_cfg` / `_build_cache` / `_INFLIGHT` / `_forget_inflight`) | 2026-09-13 | 取数与缓存归 `plate_client.get_endpoint_full`(整份 item 的 TTL/LRU/回退窗/在飞收敛都在那一层);本模块退化为**派生层** —— 只从 item 派生 `declarations` 与 path 投影(`_proj_cache` 留在本模块),降级告警仍在本地 | `b3cec6a`(上移 `f5e43d8`) |

## 各条详情

### 1. queryUser(2026-09-09 裁定)

- **原语义**:`ServiceBinding.queryUser`(`query_user`)在运行方案侧车中单独声明查询凭证。
- **现语义**:查询凭证唯一来源 = `config.users` 首键 — 查询身份 = 执行身份,与运行方案解耦。
- **存量处置**:旧侧车残留键由 pydantic `extra=ignore` 静默丢弃,无读兼容、无迁移工具。
- **涉及面**:`frontend/src/api/scenario-composer.ts` ServiceBinding、`backend/app/schemas/scenario_composer.py` ServiceBinding。

### 2. DataSetEditor 基线区 / 直填列 / 提升入口(2026-09-11,spec v2 §6/T0)

- **原语义**:编辑器内折叠式「基线区」直接编辑 step 字面值(直填列);`promote/demote` 在编辑器内声明变量;列派生器 `deriveBaselineColumns / fieldsOf / varNameOf / renderTemplate` 从 step 推导列宇宙。
- **现语义**:列宇宙 = `config.vars`(由 dataset-segments 引用扫描派生,未声明引用变量追加在后);一变量一列;var 基线唯一编辑入口 = 置顶基线行;直填(字面值)的编辑家在编排器 FieldForm;数据集行纯 var-dict(零保留键),CSV 只导值。`dataset-palette.ts` 仅承载 `BaselineColumn` 最小列形状(网格与 CSV 链共用)。
- **存量处置**:数据集行残留直填键由既有死键软提示兜底;无迁移工具。
- **涉及面**:`views/DataSetEditor.vue`、`utils/dataset-palette.ts`、`utils/dataset-grid.ts`、`utils/csv-dataset.ts`。

### 3. 期望提升链 exp_*(2026-09-11,spec v2 §2/§9,提交 `b912d59`)

- **原语义**:断言卡上「设为期望变量」把 expected 提升为 `${var.exp_*}` 变量(撞名改名 / 还原为字面量 / 期望导航 / VarSelector exp_ 紫族标注 / vardemote 链),数据集侧曾按期望列行级化。
- **现语义**:期望偏离的语义位置 = **断言管理注册表**(`assertion_registry` 场景级节,条目自含 injection + asserts;编辑器 = `AssertionRegistryEditor`,运行时汇合 = RunDialog 注入条目多选 → dispatcher 物化注入族)。expected 回归字面量;模板化的一致性断言(`${var.x}` 引用)不受影响 — `deriveSegments` strategy 段 / `ExpectColumn` / 期望徽标 / ↗ 跳断言卡等引用面保留。
- **存量处置**:存量场景的 `${var.exp_*}` 引用与 `config.vars` 的 `exp_*` 键 = 用户手工清理;无读兼容、无迁移工具。测试中 `exp_code`/`exp_msg` 等为夹具变量名,非功能残留。
- **涉及面**:`components/composer/StrategyForm.vue`、`CaseComposerCanvas.vue`、`views/CaseComposer.vue`、`components/composer/VarSelectorModal.vue`、`utils/dataset-segments.ts`(`expectVarNameOf` 已删)。

### 4. fields_meta(随会话级现拉改造)

- **原语义**:`step.request.fields_meta` 持久化字段目录曾作为请求目录数据源。
- **现语义**:会话级按 `endpoint_id` 现拉 `/full`,不读持久化快照(`stepDecls`);`fields_meta` 不再被任何代码读取。

### 5. `endpointFullVersion`(2026-09-13,提交 `c756984`)

- **原语义**:`composables/useEndpointFull.ts` 的手工版本号协议 —— `const endpointFullVersion: Ref<number>` 在**每次缓存写入**(成功回填)与**每次失败**时自增(`endpointFullVersion.value++`),因为「Map 变更不触发 computed」。每个消费方必须在**每一处** computed 里手写 `void endpointFullVersion.value` 才能建立响应依赖:全仓 14 处该语句 + 6 个消费文件的 import(`CaseComposerCanvas.vue` / `RunPanelHost.vue` / `useFieldDescriptions.ts` / `AssertionRegistryEditor.vue` / `CaseComposer.vue` / `CaseDataSetsList.vue`)。漏一处即**静默不重算**。
- **现语义**:缓存容器本身是 Vue 原生响应式 —— `fullByEndpoint` 为 `shallowReactive(new Map(...))`,`failedAt` 为 `reactive(new Map(...))`;消费方读缓存(`Map.get` / `Map.has`)即建立依赖,回填后 computed 自动重算,无需任何手工声明。同批引入**失败负缓存**(`FAILED_RETRY_MS` 窗口内不重发)。
- **存量处置**:无 —— 纯会话级内存状态(刷新即空),不落库 / 不落 localStorage,无外部 wire 面。
- **涉及面**:`composables/useEndpointFull.ts` 及其六个消费文件。

### 6. 四视图本地判定函数副本(2026-09-13,提交 `c719fda`)

- **原语义**:可注入面 / 断言目标 / 死判 / 契约在途信号在四个视图里各有一份本地副本,而四个文件的命名与构成并不统一(`bd99740` 实测):`RunPanelHost.vue` = `injectablePathsOfStep` + `assertTargetsOf` + `deadEntryIds` + `contractPending`(**无** `deadOf`);`AssertionRegistryEditor.vue` = `injectablePathsOfStep` + `assertTargetsOf` + `deadOf`(**无** `contractPending`);`CaseDataSetsList.vue` = `injectablePathsOfStep` + `assertTargetsOf` + `deadOf`(**无** `contractPending`);`CaseComposer.vue` = 同款判据但另起名 `registryInjectablePathsOf` + `registryAssertTargetsOf` + `deadEntryIds` + `contractPending`(**无** `deadOf`)。即:同一判据四个视图各写一份,命名不统一,且契约在途信号只有两个视图有 —— 同一波内各写各的。
- **现语义**:判定面唯一来源 = `composables/useInjectableSurface.ts`,**导出**只有 `useInjectableSurface` 与 `InjectableSurface` 接口;接口成员 = `pathsOfStep` / `deadOf` / `dead`(`intrinsic` 与 `contractDependent` 死因分组)/ `deadIds`(门控后死集:禁选与「悬空」标注共用)/ `stateOf` / `pending` / `ensure()`。视图**只消费**这些成员。(`assertTargetsOf` 是 composable **内部**的局部函数(闭包),只被同文件的 `deadOf` 调用 —— 不在接口里,也不在返回对象 `{ pathsOfStep, deadOf, dead, deadIds, stateOf, pending, ensure }` 里。)取数由 `ensure()` 显式触发,判定与候选走纯缓存读(渲染期零请求)。
- **存量处置**:无 —— 纯前端派生数据,无持久化、无 wire 面。
- **涉及面**:`composables/useInjectableSurface.ts`(新增)、`components/composer/RunPanelHost.vue`、`components/composer/RunDialog.vue`、`views/AssertionRegistryEditor.vue`、`views/CaseComposer.vue`、`views/CaseDataSetsList.vue`。

### 7. `endpoint_declarations` 自持 `_CACHE` / `_WARNED`(2026-09-13,提交 `ec904ec`)

- **原语义**:模块自持进程字典 `_CACHE: dict[str, tuple[float, list]]` —— `time.monotonic()` 取在**请求发起时**(慢 plate 上条目一入缓存即已过期,缓存退化);**无容量上界**;刷新失败 `_CACHE.pop(endpoint_id)`(一次 plate 抖动就把声明面从「有面」降级成「空面」)。告警用 `_WARNED: set[str]` —— 同一端点在**当前失败链**内只告警一次,**仅由「同 id 后来成功」清空**(长期失败的端点在恢复前彻底失声,而它的告警正是降级的唯一遥测)。
- **现语义**:复用共享 `services/query_view_cache.py` 的 `TtlLruCache`(ttl / 容量 / 回退窗**构造即冻结**,实例随 settings 惰性重建):成功那刻由 `put` 打点,`DECLARED_PATHS_MAX_ENTRIES` LRU 逐出,TTL 过期后刷新失败**保留旧快照**直到 `DECLARED_PATHS_STALE_WINDOW_SEC` 回退窗走完;条目载荷 = `(decls, frozenset(catalog_paths(decls)))`(投影随取数缓存)。告警表改为 `_WARNED_AT: dict[str, float]`(eid → 最近一次告警时刻),只随 `_WARN_COOLDOWN_SEC` **时间**老化,成功事件不重置。
- **存量处置**:无 —— 纯每进程内存状态(PG 部署下多 worker 各一份,有界、无害),重启即空,无持久化格式。
- **涉及面**:`services/endpoint_declarations.py`、`services/query_view_cache.py`、`core/config.py`(三个 `DECLARED_PATHS_*` settings)。

### 8. `requestDeclarationsOf`(2026-09-13,提交 `7ead7d6`)

- **原语义**:`composables/useEndpointFull.ts` 导出的「读 + 隐式取数」合体口 —— 名字是**读**,内部却 `void ensureEndpointFull(eid)` 并在无缓存时发起取数。渲染期的判定面读经它进行,即渲染期发请求(名实不符,也是渲染期 I/O 的入口)。
- **现语义**:读 / 取分离(裁定 C18)。**读**(纯缓存读,渲染期只走这里)= `getEndpointFull(endpointId)`(端点契约)/ `endpointFullState(endpointId)`(取数状态);**取** = `ensureEndpointFull(endpointId)`(幂等,每端点每会话一次,由宿主 `useInjectableSurface.ensure()` 在挂载 / 步骤面变化时显式调用)。`getEndpointFull` / `endpointFullState` 签名不变。
- **存量处置**:无 —— 模块内导出,无持久化、无 wire 面;调用方全部在同仓内改完。
- **涉及面**:`composables/useEndpointFull.ts`、`composables/useInjectableSurface.ts`、`views/AssertionRegistryEditor.vue`。

### 9. 前端对「声明半」的自行归一化 / 展开(2026-09-13,提交 `e3c80cd`)

- **原语义**:判定面的可注入面由前端自己拼声明半 —— `utils/assertion-registry.ts` 的 `injectablePathSetOf(bodyLeaves, declarations?: DeclarationEntryView[])` 遍历**声明树**并逐个 `toTemplatePath(p)` 得模板形态,即「实例 → 模板」的归一化与路径推导都发生在 TS 侧。这样同一份口径在前后端各有一份实现(跨语言同构负担)。
- **现语义**:声明半由**后端**算好 —— `/full` 代理随契约返回 `declared_surface`(归一化、容器前缀、模板形态**全部展开**的扁平字符串集合,由既有纯函数 `injectable_universe(None, paths)` 得出);前端 `injectablePathSetOf` 的第二个入参改为扁平字符串数组或 `null`(降级),只做并入。`null`(声明面不可解析)与 `["$"]`(真无声明)语义不同、落在集合上恰好同形(§5)。
- **存量处置**:无 —— 纯前端派生数据,无持久化、无 wire 面。`utils/declarations.ts` 的 `catalogPaths` **保留**(候选 UI 等消费方仍在用),退场的只是「判定面用它推导声明半」这一用法;`sanitizeDeclaredSurface` 的**形状消毒**(不可信 wire 字段)同样保留,它不是路径推导。
- **涉及面**:`utils/assertion-registry.ts`、`composables/useInjectableSurface.ts`、`types/plate.ts`;后端出口 `routers/endpoint_catalog.py`(提交 `84aef02`)。

### 10. `pathResolvable` 的容器前缀扫描(2026-09-13,提交 `e3c80cd`)

- **原语义**:`utils/assertion-registry.ts` 的 `pathResolvable(jsonpath, injectablePaths)` 在两次成员测试之外,还对**整个集合**做一遍前缀扫描(`p.startsWith(form + '.')` / `form + '['`)—— 因为彼时集合里只放 body 叶子与契约声明路径,**不**预展开容器前缀,容器锚点(如 `$.items` 之于叶子 `$.items.sku`)只能靠扫描找补。注释当时明写「承重,别当死代码删」。
- **现语义**:两侧都**物化**前缀 —— body 半由 `bodyPathSetOf` 展平各级容器前缀(`containerPrefixes`,与后端 `run_injection._container_prefixes` 同构件、同段边界语义);声明半由后端加进 `declared_surface`。判定因此只剩**两次成员测试**(实例形态 / 模板形态),扫描整段删除。等价性由跨语言对拍用例钉住。
- **存量处置**:无 —— 纯函数内部实现,无持久化、无 wire 面。
- **涉及面**:`utils/assertion-registry.ts`、`utils/__tests__/assertion-registry.test.ts`。

### 11. `endpoint_declarations` 自持的 `/full` 取数与缓存(2026-09-13,提交 `b3cec6a`)

- **原语义**:本模块自己取数、自己缓存 —— `_fetch_declarations`(`GET /api/endpoint/{id}/full` + 解信封)、`_refresh`(TTL 命中 / 回退窗 / 在飞收敛的消费分支)、`_cache()` / `_CACHE` / `_CACHE_CFG` / `_cache_cfg` / `_build_cache`(共享 `TtlLruCache` 实例与其惰性重建)、`_INFLIGHT` / `_forget_inflight`(在飞收敛表)。同进程内 `/full` 代理另有一条自己的取数 ⇒ 两条路径、两份缓存,dispatch 判定与编辑器浏览可能看到不同快照。
- **现语义**:取数与缓存归 `plate_client.get_endpoint_full`(整份契约 **item** 的 TTL/LRU/回退窗/在飞收敛都在那一层;TTL 不是形参,见该函数 docstring);`endpoint_declarations` 退化为**派生层** —— 从 `EndpointFull.item` 派生 `declarations`(`_decls_of_item`,含 `request` 非 dict / `declarations` 非 list 的降级判据),path 投影另存一份 `_proj_cache`(纯函数关系,与 item 缓存同 ttl ⇒ 永不分歧)。**降级告警(`_warn_once` / `_WARNED_AT`)留在本地** —— 「声明面不可得」是消费者侧语义,不是「取数失败」。
- **存量处置**:无 —— 纯每进程内存状态(PG 部署下多 worker 各一份,有界、无害),重启即空,无持久化格式。
- **涉及面**:`services/endpoint_declarations.py`、`services/plate_client.py`、`routers/endpoint_catalog.py`。(本行的退场对象是**取数与缓存那一层**;第 7 行记的是它更早一次「自持 dict → 共享 `TtlLruCache`」的退场,两行不可互替。)

## 维护约定

- 此后退场某功能时:删除代码(含注释),并在本表追加一行 + 详情小节(日期 / 原语义 / 现语义 / 存量处置 / 提交)。
- 代码注释一律现在时描述当前行为;历史性对照(「原为 / 已移除 / 已退场」)只写在本文档。
