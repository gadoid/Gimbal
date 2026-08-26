# 常量池：编排页右栏常驻面板 + 管理页 + 生成器模板目录

- 日期：2026-08-26（设计定稿）/ 2026-08-27（实现完成）
- 状态：**已实现并合并** — 计划 T1-T10 全部落地，合并入 `strbody_avaliable` 并推送远端；验证 plate 436 / backend 268 / frontend 304 全绿，vue-tsc 0 错。后续 UI 微调（白卡外壳、col-info 三卡拆分、rail 16px 间距、管理页发丝线表格）一并合并，见计划文档进度块
- 分支：`strbody_avaliable`（origin 已同步）

## 背景

- 场景编排时存在大量高频复用值：固定业务编号（`bank_id_0 = "319666690256273408_MainBank"`）、
  按生成器规则声明的动态变量（`bl_no = {"kind":"random_decorated","charset":"alnum","length":6,"head":"GIMBAL728","separator":"-"}`）。
  目前只能散落手打，或从旧场景 JSON 里翻找复制。
- gimbal 引擎已有完整生成器体系（`src/gimbal/generator/specs.py`，**9 个 kind**），
  但平台侧没有任何展示/配置入口，用户无从知道有哪些生成器、参数怎么写。
- 需求（用户原话归纳）：
  1. 编排四页（基本信息/资源/配置/步骤编辑）右栏常驻"常量池"panel——步骤编辑页放在
     step 信息模块下方（与 VariableRegistryPanel 同位），其余三页其他模块左移、常量池居右；
     每行提供"复制 / 插入到字段"按钮；RunDialog 不出现。
  2. 单独管理页：展示通用模板配置定义（gimbal 生成器结构 + 说明），允许用户配置常用变量，
     最终展示到编排页 panel。

## 已确认的关键决策

| 决策点 | 结论 |
|---|---|
| 字面量条目插入 | 写字面值文本到目标字段（无播种）|
| 生成器条目 key（`${var.<name>}`）插入 | 写引用文本 + `seedVar` 播种 spec 快照进当前场景 `config.vars`（**已存在同名不覆盖**，提示后仅插引用）|
| 生成器条目 value（spec JSON）| 与 key 同为一等载荷：均可复制、均可插入；spec 插入是纯文本追加（无播种——它本身就是声明）|
| 平台是否求值 | **绝不求值、不造新模板语法**——平台只写配置阶段内容（值文本 / `${var.x}` 引用 / config.vars 声明），求值唯一发生在引擎 preprocess Phase 1.5/Phase 3（用户明确："配置过程没必要再做一次模板转换"）|
| 模板定义元数据供给 | plate 新增 generator 语法 dim（对齐 strategy_dim 先例）→ platform 代理 → 前端消费（用户提议，避免静态拷贝漂移——`random_decorated` 不在任何旧文档即为例证）|
| 池数据可见性 | per-user owner 隔离（AuthSession 模式）|
| 播种语义 | 快照拷贝（同凭证池导入）：池子后续改动不回灌已播种场景 |
| panel 挂载方案 | 方案 A：CaseComposer 右栏 wrapper（步骤 0-2）+ Canvas col-info 追加挂载（步骤 3），两处挂载同一组件 |
| 插入目标机制 | DOM 焦点跟踪（focusin 捕获）+ 值尾追加 + 派发原生 `input` 事件写回 |

## 与整体设计的一致性核查（2026-08-26 与用户确认补充）

| 核查项 | 结论 |
|---|---|
| PLATFORM_REQUIREMENTS L242"平台不做新模板，原样透传 Gimbal 解析" | **一致**。常量池复用既有 `${var.<name>}` 语法，不引入任何新模板语式；插入产物只有三种引擎原生形态：字面值文本、`${var.x}` 引用、config.vars 的 spec 声明 |
| PLATFORM_REQUIREMENTS L243"保存到 Config.vars 后由 Gimbal preprocessor Phase 1.5 接管" | **一致**。播种链正是"平台只写 scenario.config.vars，不调用 CLI"，执行走既有 launch 子进程 |
| PLATFORM_REQUIREMENTS L594"内置 runtime_vars 模板（`${exec.seq}` 等）V0.1 不做" | **一致且不冲突**。本设计不引入 runtime_vars/`${exec.*}`；池管理的是引擎既有 config.vars spec 体系 |
| var-workbench 两语域模型（静态 `${var.x}` / 动态 `$.name`）| **一致**。生成器播种进 config.vars 属静态语域，preprocess 展开校验（dangling→拒启）照常生效；播种后变量自动出现在 VariableRegistryPanel 的 config 出身列表（`deriveVarRegistry` 以 configVars keys 推导）——两 panel 形成闭环且互不重复实现 |
| asset-domain-complete"常量锁概念取消——未提升即常量" | **不冲突，仅名词撞车**。彼"常量"指字段级锁定语义（已取消）；本"常量池"是用户级常用值/生成器声明库，独立概念。文档记录避免混淆 |
| 认证改造的"凭证池快照导入"先例 | **一致沿用**。播种=快照拷贝、不回灌、明文/明 spec 随场景走 |
| Scenario 导入/导出（基线模板）| **一致**。播种后的 spec 住在 `definition.config.vars`，随场景导出/导入无损迁移；常量池本身（用户级）不进导出产物 |
| plate 语法 dim 模式（strategy_dim L1-15"plate 只暴露语法，结构权威源"）| **一致复刻**。plate 镜像 spec 定义并内省暴露描述符；引擎 specs.py 仍是执行权威源；同步责任与 strategy 相同（既有双权威约定的第二例）|
| no-reverse-import 锁（test_v3_no_reverse_import）| **遵守**。新 plate 模块依赖方向 http → schema |
| 存储哲学"源存果算"（composer_scenarios payload JSON）| **一致**。constant_entries 的 value/spec 以 JSON 列源存，不求值不派生 |
| RunDialog 边界 | **零改动**。RunDialog 是 Teleport modal，panel 挂在步骤视图层天然不出现；焦点监听挂在 composer 根节点，RunDialog 内的 focusin 不会命中 |

## 总体架构与数据流

```
┌─ gimbal 引擎（零改动）──────────────────────────────────────┐
│ generator/specs.py 9 kinds — 执行期权威源                    │
└─────────────────────────────────────────────────────────────┘
        ↑ 手工同步（同 strategy 双权威既有约定，测试钉死清单防漂移）
┌─ gimbal-plate（新增 generator 语法 dim）────────────────────┐
│ schema/generator.py 镜像 9 specs → http 内省暴露描述符        │
│ GET /api/generators · GET /api/generators/{kind}/full       │
└─────────────────────────────────────────────────────────────┘
        ↑ HTTP（plate_client 进程级单例）
┌─ platform 后端（新增）──────────────────────────────────────┐
│ 代理 GET /api/generator-catalog[/{kind}/full]               │
│ 常量池 CRUD /api/constants（owner 隔离，SQLite 新表）          │
└─────────────────────────────────────────────────────────────┘
        ↑ REST
┌─ 前端 ──────────────────────────────────────────────────────┐
│ stores/constants.ts（条目 + 目录缓存，两消费方共享）            │
│ ├ 管理页 /constants：模板定义文档 + 我的常量 CRUD              │
│ └ 编排页 ConstantPoolPanel：                                  │
│    步骤 0-2 右栏 rail ｜ 步骤 3 Canvas col-info（VRP 之下）    │
│    复制/插入 → useInsertTarget（DOM 焦点）→ 原生 input 写回     │
│    生成器 key 插入 → ${var.name} + seedVar →                   │
│      CaseComposer 唯一写点 definition.config.vars[name] ??=    │
│      → 既有 deep watch 同步 store → Canvas configVars 刷新     │
└─────────────────────────────────────────────────────────────┘
```

引擎事实锚点（正确性基础，全部核实于 2026-08-26）：

| 事实 | 锚点 |
|---|---|
| 生成器 spec 只在 config.vars 求值（Phase 1.5 `_generate_vars` 遍历 config.vars；body 内联 spec 不被求值，会原样发给被测系统）| `src/gimbal/preprocessor/scenario_preprocessor.py:232-261` |
| `${var.x}` 模板展开在 Phase 3，查不到→整场景拒启 | 同上 `:311` 起；jsonpath `resolve_template_strict` |
| 9 kind 全集：uuid / random_str / random_int / random_decimal / timestamp / now / seq（+sequence 别名规范化）/ random_decorated / time_offset | `src/gimbal/generator/registry.py:31-44`、`specs.py` |
| FieldForm 全部原生控件 `@input → setValue(JSONPath)` | `frontend/src/components/composer/FieldForm.vue:37,94,194` |
| 编排四页为 CaseComposer 单页 STEPS（meta/resource/config/canvas），非路由子页 | `frontend/src/views/CaseComposer.vue:241-246` |
| Canvas 右栏 col-info（240-300px grid 第三栏）已有 VariableRegistryPanel（step 信息下方）| `CaseComposerCanvas.vue:374-377`、`:1031-1044` |
| 剪贴板双通道先例（clipboard API + execCommand 回退）| `frontend/src/stores/scenario-draft.ts:95-110` |

## plate：generator 语法 dim

- 新增 `gimbal_plate/schema/generator.py`：9 个 Pydantic spec **镜像**引擎
  `src/gimbal/generator/specs.py`（字段名/类型/默认值/枚举/范围/中文说明逐一对齐）；
  `sequence` 别名只在描述符说明里标注，目录只列规范名 `seq`。plate 只描述、永不执行。
- 新增 dim 模块（对齐 `strategy_dim.py` 的内省与注册方式，依赖方向 http → schema）：
  - `GET /api/generators` → `{data:{items:[{kind, summary}]}}`
  - `GET /api/generators/{kind}/full` → `{data:{item:{kind, summary, description, params:[{name, type, required, default, enum?, min?, max?, description}], example}}}`
  - 未知 kind → 404；信封对齐 strategy 响应。
- 同步责任：引擎 specs.py 变更 → plate 镜像同步；两侧钉死清单测试（P1/P6）防漂移。

## platform 后端：常量池 CRUD + 目录代理

**新表 `constant_entries`**（参照 `models/auth_session.py`）：

| 列 | 说明 |
|---|---|
| id PK · owner_id FK→users CASCADE | `UniqueConstraint(owner_id, name)` |
| name | `^[A-Za-z0-9_]{1,64}$`（可直接进 `${var.name}`）|
| description | 默认 '' |
| entry_kind | `'literal' \| 'generator'` |
| value JSON · spec JSON | literal 存 primitive（str/int/float/bool）；generator 存含字符串 `kind` 的 dict；**互斥**（另一方必须为 null）|
| created_at · updated_at | |

注：schema 变更走既有 DB 重建约定（`init_db` create_all，无启动迁移）。

**API `/api/constants`**（owner-scoped，`_get_owned` 复用模式）：
GET 列表 / POST 201 / PATCH / DELETE；409 `constant_name_exists`；跨 owner 一律 404；
422 覆盖：name 正则/长度、literal 值非 primitive、generator spec 缺 `kind`、value/spec 互斥违反。

后端**不**校验 generator 参数合法性（不耦合引擎/plate 可用性；参数校验由前端表单按目录
描述符执行，引擎 preprocess fail-fast 兜底——与 config.vars 现状一致）。

**代理 `/api/generator-catalog[/｛kind｝/full]`**：克隆 `routers/strategy_catalog.py`
（plate_client 单例、502 plate_unavailable、404 映射、信封透传），`main.py` 注册。

## 前端：panel 挂载与布局

- **步骤 0-2**：CaseComposer.vue 将步骤内容包入 `grid: minmax(0,1fr) minmax(240px,300px)`，
  右栏 sticky 挂 ConstantPoolPanel（即"其他模块左移、常量池居右"）；
  `<1280px` 断点 rail 整行下移（对齐 Canvas col-info 响应式约定）。
- **步骤 3**：Canvas col-info 内、VariableRegistryPanel 之**下**追加挂载；置于
  `v-if="currentStep"` 块**外**，无选中 step 时也常驻（需求"常驻"）。
- 同一组件两处挂载，`v-if="stepIdx<3"` 控制 rail；store 供数据，切步零成本。
- **RunDialog 零改动**（Teleport 到 body，panel 不在其树内；焦点监听在 composer 根，
  RunDialog 的 focusin 不命中）。

## 前端：复制/插入交互（生成器双载荷）

行结构（240-300px 紧凑形态）：

```
┌────────────────────────────────────────┐
│ 🧬 bl_no                      [生成器]  │
│ key   ${var.bl_no}        [复制] [插入] │
│ value {"kind":"random_decorated",…}     │
│                          [复制] [插入]  │
├────────────────────────────────────────┤
│ 🔒 bank_id_0                  [常量]    │
│ value 319666690256273408_MainBank       │
│                 [复制] [插入到字段]      │
└────────────────────────────────────────┘
```

| 条目/载荷 | 复制 | 插入到字段 |
|---|---|---|
| 字面量·value | 复制字面值文本 | 追加字面值文本（无播种）|
| 生成器·key | 复制 `${var.<name>}` | 追加 `${var.<name>}` + emit `seedVar`（config.vars 无同名时播种）|
| 生成器·value | 复制完整 spec JSON（紧凑单行，便于粘贴进配置页 vars 声明或任意场合）| 追加 spec JSON 文本（纯文本，无播种）|

- spec JSON 行内紧凑截断显示，title 悬浮看全文；复制/插入的均为完整紧凑 JSON 文本。
- **useInsertTarget**（`composables/useInsertTarget.ts`）：composer 根 focusin 捕获记录
  最后文本可编辑元素（`input[type=text]`/textarea/contenteditable；跳过 number/checkbox/
  radio/file/select）；插入前检查 `isConnected`（字段已卸载视为无目标）。
- **写回机制**：目标元素值尾**追加**（与 FieldActionMenu varInsert 追加语义一致）+ 派发
  原生 `input` 事件。已核实三条链兼容：FieldForm 原生 `@input→setValue(JSONPath)`、
  el-input（v-model 监听原生 input → update:model-value）、原生 textarea。无目标时
  ElMessage.info"请先点击要插入的输入框"。
- **播种链**：panel emit `seedVar(name, spec)` → 两挂载点（rail 直连 / Canvas 上抛）汇到
  CaseComposer 唯一写点：`definition.config.vars ??= {}; definition.config.vars[name] ??= spec`
  （已存在**不覆盖**，info"config.vars 已有同名变量，使用现有值"）→ 既有 deep watch 同步
  store → Canvas `configVars` prop 刷新 → VariableRegistryPanel 自动出现 config 出身条目。
- 剪贴板：从 `scenario-draft.ts copyJson` 抽出 `utils/clipboard.ts` 双通道工具复用。
- panel 头部"常量池" + 管理入口图标 → `/constants`（草稿在 store，跳转无损）。
- 数据拉取：panel 与管理页挂载时 `store.ensureEntries()/ensureCatalog()`（in-flight
  去重，F19）；条目与目录相互独立拉取、独立降级。

## 管理页 `/constants`（views/ConstantsPool.vue）

- **模板定义（只读目录）**：每个 kind 一张可折叠卡片——kind 名 + summary + 说明 +
  参数表（参数/类型/必填/默认/可选值/说明，来自 `/full` 描述符）+ 示例 spec JSON +
  [复制 JSON]。
- **我的常量池**：工具栏（新增）+ el-table（name / 类型徽标 / 内容摘要——literal 显示值、
  generator 显示 kind+关键参数 / 描述 / 更新时间 / 操作：编辑、删除-confirm）。
- **新增/编辑弹框**（共享表单）：
  - name（正则 + 同名唯一性前端预检）、description；
  - 类型单选：字面量 / 生成器；
  - 字面量 → 值类型下拉（字符串/整数/小数/布尔）+ 按类型切换的值控件与校验；
  - 生成器 → kind 下拉（目录驱动，显示 summary）→ **动态参数表单**（enum→select、
    integer/number→InputNumber 带 min/max、boolean→switch、required 校验）+
    实时 spec JSON 预览与复制。
- **降级**：目录服务不可用 → 模板定义区显示降级条、生成器表单禁用并提示；
  字面量 CRUD 与编排页 panel 不受影响（条目 API 与目录 API 相互独立）。
- 路由 `requiresAuth`；TopNav 增"常量池"入口。

## 测试策略

**plate pytest**（`tests/plate/test_generator_dim.py`）：
- P1 `GET /api/generators` 返回 9 个规范 kind 钉死清单（sequence 别名不单列）
- P2 random_str `/full`：length（int，默认 8，1..1024）、charset（enum alpha|digit|alnum，默认 alnum）
- P3 time_offset `/full`：unit 八值枚举、direction 枚举、base、base_format
- P4 未知 kind → 404
- P5 no-reverse-import 锁保持绿（新模块 http→schema）
- P6 描述符与 plate 镜像 schema 默认值一致（防 plate 内漂移）

**platform pytest**：
- `test_constants_api.py` B1-B9：literal/generator 创建 happy；同 owner 重名 409、
  异 owner 同名放行；跨 owner PATCH/DELETE 404；name 正则 422；literal 非 primitive 422；
  spec 缺 kind 422；value/spec 互斥 422；PATCH 部分更新保值；删除后可重建
- `test_generator_catalog_proxy.py` B9-B11：列表/详情透传（MockTransport 模式）；
  plate 5xx → 502；未知 kind → 404

**前端 vitest**：
- F1-F3 `useInsertTarget`：跟踪 text/textarea、忽略 number/checkbox/select；
  断连目标清理；appendAndNotify 值尾追加 + input 事件派发（监听 spy）
- F4-F8 `ConstantPoolPanel`：literal/generator 行渲染与类型徽标、空态；
  三种复制载荷（字面值 / `${var.name}` / spec JSON）；生成器 key 插入 emit seedVar + DOM 追加；
  spec 插入**不** emit seedVar 且追加 JSON 文本；无目标提示且不播种；字面量插入不 emit seedVar
- F9-F11 CaseComposer：rail 步骤 0-2 有、步骤 3 无；seedPoolVar `??=` 语义与不覆盖提示；
  RunDialog 挂载时 DOM 内无 panel
- F12-F13 Canvas：panel 在 col-info 内且 DOM 顺序位于 VariableRegistryPanel 之后；
  seedVar 上抛链
- F14-F18 管理页：目录 9 kind 渲染；字面量建表单 round-trip 与 POST payload；
  生成器 kind 下拉 → 动态参数按描述符渲染（enum→select options）与 spec 预览、POST payload
  含 spec；编辑预填 / 删除 confirm；目录降级（提示渲染 + 我的常量区仍可用）
- F19 `stores/constants`：并发 fetch 去重、upsert/remove 乐观更新
- F20 TopNav"常量池"链接

**回归底线**：plate / backend / vitest 现有套件只增不减全绿；`vue-tsc --noEmit` 绿。

## 非目标

- 平台侧样例值求值/预览（明确不做二次模板转换，preprocess 是唯一求值点）
- 团队共享池（v1 per-user）；播种后与池子的联动同步（快照语义）
- body 内联 spec 引擎扩展；runtime_vars/`${exec.*}`
- RunDialog 集成；数据集/认证等非编排页挂载
- 字面量对象/数组类型（v1 四种 primitive）

## 实施影响范围

| 位置 | 新增 | 修改 |
|---|---|---|
| gimbal-plate | `schema/generator.py`、generator dim 模块、`tests/plate/test_generator_dim.py` | dim 注册处 |
| platform 后端 | `models/constant_entry.py`、`schemas/constants.py`、`routers/constants.py`、`routers/generator_catalog.py`、两个测试文件 | `models/__init__.py`、`main.py` |
| 前端 | `api/constants.ts`、`api/generator_catalog.ts`、`stores/constants.ts`、`types/constants.ts`、`composables/useInsertTarget.ts`、`utils/clipboard.ts`、`components/composer/ConstantPoolPanel.vue`、`views/ConstantsPool.vue` 及全部测试 | `views/CaseComposer.vue`、`CaseComposerCanvas.vue`、`router/index.ts`、`TopNav.vue`、`scenario-draft.ts`（copyJson 抽取）|

引擎 `src/gimbal` 与 RunDialog 零改动。
