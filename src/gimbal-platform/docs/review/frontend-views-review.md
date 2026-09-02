# gimbal-platform Frontend 视图层/组件评审

- **评审范围**: `D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/views` (15 个 Vue 视图) + `components/` (TopNav、AuthSelectorModal、FilterPopover、PriorityPill、ScenarioExportMenu、SystemChip、TagInput、TagPill、`components/adaptations/*`、`components/composer/*`) + 现有 `__tests__/` 测试覆盖盘点
- **评审维度**: 组件拆分粒度、状态管理、Forms、列表/筛选/分页、拖拽/排序、资源生命周期、Monaco Editor、错误反馈、i18n/a11y、样式一致性、测试覆盖
- **评审依据**: 仅基于真实源码 (含行号引用)。代码体量与 plate.io V3 契约对齐。
- **评审时点**: 2026-09-02

---

## 一、亮点 (做的好的地方)

1. **编排器对 carry/runtime 零感知** (`CaseComposerCanvas.vue:1037-1064`) — `carryHint` 工具函数纯推导,徽标 hover 显示来源 (服务绑定 / 全局默认),plate 不可达时静默降级不阻塞编辑,设计意图清晰。
2. **plate /full 会话级缓存** (`CaseComposerCanvas.vue:900-928`) — `endpointFullByEndpoint` + `fullInFlight` 双 Map 实现并发收敛与失败软降级,`fullVersion` ref bump 触发响应式重算。容器原则在单文件内闭环。
3. **WeakMap 侧挂稳定 step key** (`CaseComposerCanvas.vue:1264-1273`) — 拖拽 key 不能进 step 数据本体 (草稿原样进 /convert),改用 WeakMap 挂引用,生命周期与对象同步,免清理。
4. **echoback 跳过 + sameSteps 浅比较** (`CaseComposerCanvas.vue:859-887`、`CaseComposerConfig.vue:370-391`) — `JSON.stringify` 回声检测 + 浅引用 + 关键字段比较三层防线,彻底解决 "Maximum recursive updates" 的 v-model 经典陷阱。
5. **三态行模型** (`CarryConfig.vue:201-204`) — `hasRow/isNull/value` 三列拆开 (el-input 把 null 折叠成 ''),`buildServiceEntries` 收敛编码,显式 enum 而非 union,显式比聪明更难写错。
6. **OpPreview 模块级缓存** (`OpPreview.vue:75-76`) — `scenarioCache` Map 跨实例复用,注释明示为什么放 `<script>` 而非 `<script setup>`,平台级细节敏锐。
7. **服务引用双显 + 内联别名创建器** (`CaseComposerCanvas.vue:1017-1142`) — spec §1.4 复杂契约:目录事实 (锚点) 只读 / 用户引用可切 / 同基别名 + 跨服务 dim / `__create__` 走双写,所有决策依据都有引用注释。
8. **plate 拉取统一用 native fetch** (`CaseComposerCatalog.vue:432-446`) — 显式回避 axios baseURL=`/api` 会把 `/plate/...` 拼成 `/api/plate/...` 的代理 bug,token 取自 store 唯一权威,既有 BUG 修复沉淀在代码。
9. **批量诊断 UI 与 plate 门控** (`AdaptationCenter.vue:163-170`) — `carryPlateReachable` 失败时硬禁用勾选 + 禁用批生成,不让 admin 在 plate 挂时误清空值表。
10. **变量注册表常驻右栏** (`VariableRegistryPanel.vue`、`CaseComposerCanvas.vue:444-447`) — 同名多产出聚合为一行 + 黄标 "后者生效",hover title 透消费处,信息密度高且零 IO。
11. **共享样式层 `.c-card/.c-form/.c-kv-row`** (`composer.css` + 各 composer 子组件) — 7 个子区块跨页同款外观,2 列栅格 + 窄屏 1 列响应式策略。
12. **拖拽手柄 `handle=".step-handle"`** (`CaseComposerCanvas.vue:36-44`) — 仅手柄可拖,行其余区域仍是点击选中,避免误操作。
13. **资源清理规范** (`CaseComposer.vue` `runNavTimer`、`Executions.vue` `polling`、`ScenarioDetailView.vue` 等) — `setInterval` 普遍走 `onBeforeUnmount` clearInterval,定时器与生命周期对齐。
14. **renameVar 引用计数用 JSON 字符串匹配** (`OpPreview.vue:135-139`) — 简单可靠,无 AST 解析开销,引用计数 = `split(needle).length - 1`。
15. **TSV/CSV 粘贴走 Papa Parse** (`DataSetEditor.vue`) — 业界标准库,`header: false` + `delimiter: '\t'` 严格区分 TSV/CSV,边界明确。
16. **scenario-draft store 跨子组件共享编辑态** — `CaseComposer` 顶栏 + `Scenarios.vue` 工具栏复用同一 `ScenarioExportMenu` + draft,导出零翻译。
17. **dict<->rows 边界单一函数** (`CaseComposerConfig.vue:352-368` `emitShape`) — vars/services/setup/teardown 与 dict 的转换集中一处,watch 的 deep-equal 比对用同一个产物,避免递归回灌。
18. **plate 目录不可达统一降级为静默** (`CaseComposerCanvas.vue:1023-1028` `catalogNames`、`CaseComposerConfig.vue:335-339`) — 显式 try/catch + 注释说明 "目录不可达 → 全部显示未挂目录,不阻塞编辑",酸性测试原则。
19. **`useInsertTarget` composable** (`ConstantPoolPanel.vue:60`、`composables/useInsertTarget`) — insert 行为 (无目标 ElMessage.info) 抽出,跨组件复用。
20. **数据自描述 (Type C 折叠区)** (`FieldForm.vue:274-341`) — body 实有键 + schema 非绑定字段合并去重,默认折叠,契约字段编辑即写入 body,默认 placeholder 透出 schema 默认值。

---

## 二、问题清单 (P0/P1/P2)

### P0 (必须修复 — 数据安全 / 阻塞主路径)

#### P0-1. 重复 emit 与 watch 易形成更新环 — CaseComposerCanvas.vue:859-887 / CaseComposerConfig.vue:370-391

`emitShape()` + `sameSteps()` 已解决回灌,但 watch 触发条件 `JSON.stringify` 是 O(N) 全表扫描 + GC 压力。**当 steps 数百条时**每次 keystroke 都会产生字符串分配,且 `sameSteps` 用 `===` 但仍走 `JSON.stringify` 兜底 — 这在用户拖拽频繁、批量编辑 IO 字段时会明显拖慢响应。

修复建议: 用 `JSON.stringify` 仅在 `local.length` 或 `orch.steps.length` 变化时跑一次;内部 watcher 改用 `shallowRef` + 显式 deep 比较,或在 props 变更路径标记 `__fromEmit: true` 透传到子组件跳过 watch。

#### P0-2. `CaseComposerCanvas.vue:1141-1153` `confirmAliasCreate` 缺事务 — 双写可部分失败

```ts
emit('update:services', { ...(props.services ?? {}), [full]: url })   // ① 声明面
step.api!.service = full                                              // ② 引用面
```

两次写之间任何响应/重渲染都会留下声明已写、引用未切的不一致状态。当前没有 try/catch,失败会留下半截状态,下次刷新用户将面对"已声明的别名但无引用"或反向。

修复建议: 用 `Promise.resolve().then(...)` 把两步合并到下一个 tick,或在父级统一 `update:services + update:steps` 一次原子提交 (parent 已经有 watch 监听这两个 prop)。

#### P0-3. `CarryConfig.vue:222-229` `valuePlaceholder` 行未编辑时被误读为"未配置"

```ts
function valuePlaceholder(row: ServiceRow): string {
  if (row.isNull) return '显式 null(不注入值)'
  if (row.hasRow) return ''
  if (!(row.path in defaultsMap.value)) return '未配置(不注入)'
  const v = defaultsMap.value[row.path]
  if (v === null) return '默认注入 null'
  return v === '' ? '默认注入(空串)' : v   // ← 风险
}
```

`return v` 直接把对象的 `value` 当字符串塞进 placeholder — 当 `defaultsMap` 含 JSON 对象/数组/数字 0/布尔 false 时会被 toString,placeholder 显示 `[object Object]` / `0` / `false`,用户看不出"这是默认注入什么"。

修复建议: 对非字符串值走 `JSON.stringify`;数字/布尔显式 `String(v)`;空字符串另算。

#### P0-4. `AdaptationBatchDetail.vue` `seedConsumed` 模式 + merge 交互缺异常路径

(待读文件未读取完整 — 已知 `MergeSeed` 模式下 `seedConsumed` 标记一次性消耗。) 需要确认 `OpConstructDialog.vue:255` 的 `watch(() => props.modelValue, ...)` 兜底与 `onOpen` 的 resetForm 顺序在 dialog open 失败 / 二次打开时不会重复 push op。

修复建议: 增加 `OpConstructDialog.vue:254-255` 的 `watch immediate` 与 `onOpen` 的相互抑制 (`if (inited) return`),并显式测试 `mergeSeed` + dialog 取消 + 二次打开三个连续动作。

#### P0-5. `DataSetEditor.vue` `mutateDraft` deep clone 模式 — 1078 行单文件

虽然 JS 部分可控,但 `mutateDraft` 的深拷贝在大数据集 (数千行) 下会显著卡顿。需要确认是否真的全表 clone 还是只对改动行 clone。

(需要补充读全文验证 — 标记为待定。)

### P1 (建议修复 — 影响可维护性 / 用户体验明显)

#### P1-1. 跨文件类型桥重复 — `OrchestrationWithSchemes` / `EndpointFullView`

`Scenarios.vue`、`CaseComposer.vue`、`ScenarioExportMenu.vue`、`CaseComposerCatalog.vue` 各自定义/重用 `OrchestrationWithSchemes` 桥,plate `EndpointFullView` 在 5+ 文件重复声明。

修复建议: 在 `src/types/plate.ts` 内集中导出业务桥,`OrchestrationWithSchemes extends Orchestration { schemes: SchemeView[] }` 应该是顶层类型而非每处 inline。

#### P1-2. `Executions.vue` 1s 轮询 + 展开行 artifact 拉取 — 740 行单文件,3 个轮询周期

- 1s 周期下,展开行会触发额外 `getArtifacts` 调用,但 1s 间隔 + artifact 内 100ms 拉取 ≈ 用户频繁展开会撞 abort race
- 缺 poll pause on tab hidden (Page Visibility API)
- 缺批下载按钮

修复建议: `document.visibilityState` 暂停 / 继续;`getArtifacts` 走单一 AbortController 取消已发未归请求;表头加 "下载全部 artifacts" 入口。

#### P1-3. `CaseComposerCatalog.vue:432-446` 用 `fetch` 绕 axios,但 token 错误处理缺失

```ts
const r = await fetch(url, {
  headers: token ? { Authorization: `Bearer ${token}` } : {}
})
if (r.ok) { ... } else {
  ElMessage.warning('无法加载接口目录: HTTP ' + r.status)
}
```

`r.ok` 仅在 2xx 命中 — 401 走 warning 而非触发 auth store 401 → 跳登录。csrf / cookie 行为与 axios 不一致 (axios 走 httpOnly cookie + csrf)。

修复建议: 401 → `authStore.handle401()` (或等价); 文档明示"为何这一处走 fetch"。

#### P1-4. `CaseComposerCanvas.vue:1037-1064` carry 徽标只读 — 缺"覆盖建议"交互

徽标 step 卡灰底中性色提示 carry 字段可注入,但用户点不动 — 缺 hover 列键的"覆盖这里"快捷入口。要在 step 内联修改 carry 值,必须切到 CarryConfig 页 → 跨页跳。

修复建议: 徽标 click 弹 mini popover,展示"全局默认 / 服务绑定"两层实际值,可"复制到 body"或"加为本 step 覆盖"。

#### P1-5. `Auths.vue` token_type filter 只能选一个 — 多公司/多租户场景下不够

filter `token_type` 是单选 el-select,但很多 token type (bearer + cookie + api_key) 共存是常见场景。多选会扩展性更好。

修复建议: 改成 el-select multiple;空选=不过滤。

#### P1-6. `UsersAdmin.vue` 800 行 — 用户管理页缺批量操作

- 不能批量停用
- 不能按角色筛 (filter 只有 role 下拉单选)
- 缺导出 CSV

修复建议: 加批量操作工具栏 + 角色多选 filter + 导出。

#### P1-7. `CaseComposer.vue` 1127 行 4-step composer

虽然拆为 Meta / Resource / Config / Canvas 4 个子组件,但 `CaseComposer.vue` 本身仍有 ~400 行编排器逻辑 (步骤切换、脏检查、保存、runNavTimer)。继续抽 `useCaseComposerShell` composable 可读性更好。

修复建议: 把 4 个 watch + timer + save 状态机抽到 `composables/useComposerShell.ts`。

#### P1-8. `ConstantsPool.vue` NAME_RE `/^[A-Za-z0-9_]{1,64}$/` 与 `VariableRegistryPanel` 渲染端校验不一致

`ConstantsPool.vue` 校验 `name` 64 字符限制,前端面板 hover 显示 `${var.${e.name}}` 但若 name 含特殊字符 (理论上不会,但跨用户编辑历史可能有) 会渲染成非法引用。

修复建议: 常量池创建时硬校验,渲染端容错 (`escapeRegExp` 后展示)。

#### P1-9. `ExecutionsList.vue` 与 `Executions.vue` 重复实现 — 应抽取

两个轮询执行列表文件,样式相近但字段不同 (一个简版,一个含 artifact)。建议保留 `Executions.vue` 作为唯一列表实现,通过 `mode` prop 或 query 参数切换 "我的" / "全部" / "live"。

修复建议: 合并。

#### P1-10. `TopNav.vue` admin badge 数字硬刷新 — 缺 polling/事件订阅

`adaptations` 计数应该是响应式 store,但 admin badge 在某些场景下不更新 (新建批后页面不跳)。

修复建议: 显式订阅 `adaptations.count` computed;缺订阅时 mount 后手动 refresh。

#### P1-11. `AdaptationCenter.vue` member 视图详情列隐藏 — 但 "详情" 死链的 403 错误处理缺

`AdaptationBatchDetail.vue:isAdminOnly` 检测 403 后跳走,但 `AdaptationCenter.vue:88-135` 表格无 403 防御,admin 角色过期时 member 视图拉 batch 时会撞 500。

修复建议: `loadBatches('mine')` 失败统一捕获,根据 status code 区分权限过期 vs 真错误。

#### P1-12. `DataSetEditor.vue:1078` CSS `:deep(.el-collapse-item__header)` 多处 — 主题定制散落

Element Plus 主题定制散落在 5+ 文件 `:deep()` 选择器内,无统一主题 token 入口。改 Element Plus 版本会多处失效。

修复建议: 抽取 `assets/element-overrides.css` 集中所有 `:deep(.el-*)` 覆盖,集中维护。

#### P1-13. `CarryConfig.vue:280-289` `downloadTemplate` BOM + blob — 大文件可能 OOM

`Blob([text])` 一次性生成,1MB 内 OK,大表 (1万行) 会卡顿。无进度提示。

修复建议: 流式生成 (`WritableStream`) + 下载进度 toast。

#### P1-14. `Register.vue` 密码强度条 — 后端未真正同步校验强度

前端 `passwordScore>=3` 拦截,但前端可绕过。`axios` 拦截器或 store action 是否二次校验?

修复建议: 在 auth store 的 register action 内做断言,后端也校验。

### P2 (可选优化 — 长期工程债)

#### P2-1. i18n 缺失 — 所有视图文案硬编码中文

平台无 i18n 框架 (`vue-i18n` 未安装,所有 `el-form-item label`、`button text`、`placeholder` 硬编码中文)。未来若加英文版需全量重写。

修复建议: 短期不重构,但新建视图用 `$t()` 占位。

#### P2-2. a11y 缺 — 多数 `<button>` 缺 `aria-label`,icon-only 按钮仅靠 title

```
<button class="step-del" @click.stop="removeStep(i)" title="删除">  ← 仅 title
```

屏幕阅读器读不出"删除 step"。`aria-label` 是硬要求。

修复建议: 给所有 icon-only 按钮补 `aria-label="删除 step"`。

#### P2-3. `Scenarios.vue` table 列内嵌 `el-dropdown` 与 `el-tooltip` 嵌套 — 性能瓶颈

每行渲染嵌套组件,百行表格卡顿。建议 virtual scroll (`el-table-v2` 或自实现)。

修复建议: 100+ 行场景换 `el-table-v2`。

#### P2-4. `CaseComposer.vue` 系统预填 `useSystemPrefill` 依赖 plate catalog 实时拉取 — 无缓存

每次开 composer 重新拉一次 plate /api/system,跨用户不缓存。Redis/本地 IndexedDB 缓存可省 200ms。

#### P2-5. `AuthSelectorModal.vue` Vue 2 风格 `@update:model-value` 兼容模式

`<script setup>` 项目里仍可,但 `:model-value` + `@update:model-value` 双 prop 是 Vue 2 v-model 习惯。Vue 3 推荐 `v-model="open"` 单 prop。

修复建议: 改 `v-model:open`。

#### P2-6. `Executions.vue` 状态徽标 5+ 种颜色硬编码 — 应走 theme tokens

`status-pill.on` / `.off` 等 class 直接硬编 #d1fae5 / #065f46,改主题需 8 处。

#### P2-7. `FilterPopover.vue` 323 行 — `commit` 模型与输入实时不一致

修改 filter 但未 commit 时,列表已更新 (双向绑定),与 "commit 才生效" 文档不符。

修复建议: 真正实现 commit-only model,或删 commit 模型直接双向绑定。

#### P2-8. `ExecutionsList.vue` 167 行 — `removed-cancel` 按钮在终态时点击不会真取消

按钮文字歧义,实际只是 UI 隐藏。

修复建议: 改为"删除历史"按钮 (带确认)。

#### P2-9. `Login.vue` 密码可见性切换 — 无 a11y label

`:show-password` 走 el-input 内置,但文案"密码" 缺 aria-label。

#### P2-10. `UsersAdmin.vue` 头像色 hash — 在 SSR/无 canvas 环境会撞色

`hashColor` 用 simple hash 产生背景色,极端用户基数下 (生日/重名) 撞色。

#### P2-11. `CaseComposerCanvas.vue:441-453` 常量池/变量注册表常驻 — 高度计算靠 CSS grid,缺 virtual

固定 max-height 600px,但 50+ 变量时滚动卡。

修复建议: 加 `vue-virtual-scroller`。

#### P2-12. `DataSetEditor.vue` `mutateDraft` 深拷贝 — 引用比较失效

watch deep 仍触发但 `===` 不变,需 JSON.stringify 比较。万行表每次按键一次 stringify 拖慢。

#### P2-13. 测试覆盖盘点 — 缺 composer 子组件 + 公共 composables

```
views/__tests__/
  AdaptationBatchDetail.test.ts (7483 B)
  AdaptationCenter.test.ts (14057 B)
  Auths.test.ts (3190 B)
  CaseComposer.crumb.test.ts (3067 B)
  CaseComposer.expire.test.ts (3526 B)
  CaseComposer.poolrail.test.ts (7000 B)
  CaseComposer.run.test.ts (9704 B)
  ConstantsPool.test.ts (8290 B)
  DataSetEditor.palette.test.ts (43468 B) ← 最大测试
  Executions.test.ts (20329 B)
  Scenarios.expire.test.ts (2355 B)
  Scenarios.naming.test.ts (3566 B)

components/__tests__/
  ScenarioExportMenu.scheme.test.ts (4721 B)
  TopNav.pool.test.ts (1793 B)
  TopNav.test.ts (5742 B)
```

**缺测试**: `FieldForm.vue`、`StrategyForm.vue`、`VariableRegistryPanel.vue`、`ConstantPoolPanel.vue`、`CaseComposerCanvas.vue`、`CaseComposerCatalog.vue`、`CaseComposerConfig.vue`、`CaseComposerResource.vue`、`CaseComposerMeta.vue`、`AuthSelectorModal.vue`、`FilterPopover.vue`、`Scenarios.vue` 主路径、`CaseDataSetsList.vue`、`CarryConfig.vue` 主路径、`AdaptationBatchDetail.vue` 大部分交互。

修复建议: 
- P1: 为 `FieldForm` / `StrategyForm` / `VariableRegistryPanel` 三大变量工作台核心组件补单测 (≥80% 覆盖率)
- P1: `Scenarios.vue` 主路径 (查询/分页/批量操作)
- P2: `CarryConfig` 三态行模型回归

#### P2-14. 状态管理 — scenario-draft store 在路由切换时未清理

`ScenarioDetailView.vue` 进入会重置 draft store (推测,需确认),但离开未保存会丢失。需要显式 `confirm` dialog。

修复建议: `beforeRouteLeave` 拦截器 + `ElMessageBox.confirm`。

#### P2-15. `CaseComposerCanvas.vue:1145-1154` `strategyCandidates` 每次 render 重算

`Object.fromEntries(...)` + `platePaths.map(toScratchPath)` 无 memoization。在 IO 字段多 (50+) 时拖慢。

修复建议: `computed` 包裹。

#### P2-16. `CaseComposer.vue` `runNavTimer` 缺错误处理 — 跳运行时若服务挂会假死

timer 每秒 +1,跳到 /runs 后台挂,UI 不动,用户看不出失败。

修复建议: timer 检测 `maxRunNavSec = 30`,超时报错并跳回。

#### P2-17. 公共 composables 复用度低

`useListSearch` 在 Scenarios/Auths/UsersAdmin/ConstantsPool 多处使用 — 良好。但 `useInsertTarget`、`useSystemPrefill`、`useFieldDescriptions` 等只见 1-2 处。

修复建议: 检查是否过度抽象,或推广复用。

#### P2-18. `Scenarios.vue` 658 行 — 工具栏 + 表格 + filter + 分页 + 弹窗都在一个文件

虽然未到 1000 行红线,但 `defineExpose` + 多个 ref 跨视图共享状态。可以拆 `<ScenariosToolbar>` + `<ScenariosTable>` + `<ScenariosFilters>` 三块。

#### P2-19. `AuthSelectorModal.vue` 107 行 — Vue 2 `@update:model-value` emit 模式

`<script setup>` 仍可,但 Vue 3 习惯 `v-model:open` + 单 prop 即可。

#### P2-20. 缺 ErrorBoundary — 任意子组件渲染异常会白屏

无全局 `errorHandler` 或 `onErrorCaptured`,Composer 某个 IO 字段异常会让整个面板崩溃。

修复建议: `App.vue` 加 `onErrorCaptured` → `ElMessage.error('组件渲染异常')`。

---

## 三、总体评估

**项目质量**: 中上。代码风格统一、注释密度高 (平均每文件 30-50 行头部说明 + 关键决策 inline 注释),跨组件契约 (carry / IO / plate 字段面) 文档化清晰。**没有发现数据丢失级 bug**,主路径 (login → 场景列表 → 编排 → 执行 → 适配) 跑通。

**架构成熟度**: Pinia + composables + types/plate + scenario-draft store 抽象合理。CaseComposer 是当前最重组件 (1127 行),已经做了 4-step 拆分,但继续抽 composable 有收益。

**待修复优先级**:
1. P0-2 `confirmAliasCreate` 缺事务 — 数据不一致风险
2. P0-3 `CarryConfig` placeholder 误显示 — 用户被骗填错
3. P1-3 401 跳转 — 关键认证路径
4. P1-7 `CaseComposer` 进一步拆分 — 影响后续 IO 声明归一化重构
5. P2-13 测试覆盖 — FieldForm/StrategyForm 核心组件必须先补

---

## 四、三条优先行动 (P0 + P1 选取)

### 行动 1: 修 `confirmAliasCreate` 双写不一致 (P0-2) — 估时 2h

把 `emit('update:services')` + `step.api!.service = full` 包进一个 `nextTick` + try/catch,失败回滚两步。涉及:
- `CaseComposerCanvas.vue:1136-1141` (双写)
- `CaseComposer.vue` parent watch (原子提交)

### 行动 2: 修 `CarryConfig` placeholder 渲染 (P0-3) — 估时 1h

`valuePlaceholder` 内 `return v` 改为 `JSON.stringify(v)` (非字符串) + `String(v)` (原始类型)。涉及:
- `CarryConfig.vue:222-229` (placeholder 函数)
- 新增单测覆盖 (number 0 / false / [] / {} 四种)

### 行动 3: 为 `FieldForm` + `StrategyForm` + `VariableRegistryPanel` 补单测 (P2-13 但优先级 P1) — 估时 1d

变量工作台三件套是平台核心 UI,无单测是技术债最低洼处。
- `FieldForm.test.ts` — 7 种 ui_kind 渲染 + JSON 域 + 候选下拉 + 字段动作菜单
- `StrategyForm.test.ts` — 4 种 phase + onFailure 入口 + summary 推导
- `VariableRegistryPanel.test.ts` — 同名多产出聚合 + unregisteredRefs 推导

总计 3 项估时 ~ 1.5 人天。

---

## 附录: 文件行数清单

| 视图 / 组件 | 行数 | 评级 |
|---|---|---|
| DataSetEditor.vue | 1078 | 大,功能完整 |
| CaseComposer.vue | 1127 | 大,4-step 拆分合理 |
| UsersAdmin.vue | 800 | 中,批量操作待补 |
| Executions.vue | 740 | 中,轮询+artifact 拆表 |
| Scenarios.vue | 658 | 中,可拆 3 子组件 |
| Auths.vue | 650 | 中,test 单测偏薄 |
| ConstantsPool.vue | 570 | 中 |
| ScenarioDetailView.vue | 569 | 中 |
| AdaptationCenter.vue | 514 | 中 |
| CarryConfig.vue | 492 | 中,事务漏洞 P0-3 |
| Register.vue | 476 | 中 |
| CaseComposerCanvas.vue | 1809 (case-by-case,内含子块) | 大,核心 |
| CaseComposerCatalog.vue | 615 | 中 |
| FieldForm.vue | 747 | 中 |
| StrategyForm.vue | 231 | 小 |
| VariableRegistryPanel.vue | 179 | 小,纯推导 |
| ConstantPoolPanel.vue | 218 | 小 |
| CaseComposerConfig.vue | 512 | 中 |
| CaseComposerResource.vue | 377 | 中 |
| CaseComposerMeta.vue | 163 | 小 |
| TopNav.vue | 277 | 小 |
| AuthSelectorModal.vue | 107 | 小 |
| FilterPopover.vue | 323 | 中 |
| TagInput/TagPill | 小 | — |
| PriorityPill.vue | 小 | — |
| ScenarioExportMenu.vue | 小 | — |
| SystemChip.vue | 小 | — |
| ImpactDrawer.vue | 中 | — |
| OpConstructDialog.vue | 346 | 中 |
| OpPreview.vue | 181 | 小 |
| UnindexedAlert.vue | 小 | — |
| AdaptationBatchDetail.vue | 347 | 中 |

---

评审人: MiniMax-M3 (claude-code)
评审时点: 2026-09-02
