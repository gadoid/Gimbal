# ④ 步骤编辑页 IO 卡片化(request / response 双签)— 设计文档

- 日期:2026-08-18
- 状态:已评审(对话定稿),待实现
- 前置:变量工作台迁移 Canvas 已完成(2026-08-18-var-workbench-canvas-*.md,5 commit 已落地)
- 范围:纯前端(`src/gimbal-platform/frontend`);plate 侧零改动

---

## 0. 背景与问题

### 0.1 策略语域只在响应侧,但 UI 只有请求侧入口

gimbal 引擎执行期,extract / assertion / assign 的 JSONPath 导航对象是 **step scratch**(
`gimbal/strategy/builtin/call.py:101-104` 在 HTTP 响应后写入):

```
response_status / response_headers / response_body / duration_ms / request_body ...
```

实测(`gimbal/utils/jsonpath.py` 引擎同款实现):

| 路径写法 | scratch 解析结果 |
|---|---|
| `$.status` | `None`(实际 key 是 `response_status`) |
| `$.data.orderId` | `None`(须带 `response_body.` 前缀) |
| `$.response_body.data.orderId` | ✅ 命中 |
| `$.response_status` | ✅ 命中 |

plate 自己的 canonical 示例也用 scratch 域写法(`gimbal/schema/strategy.py:100`
`expression="$.response_body.data.id"`)。

**但平台当前 UI 三个写入口全在 plate 域裸写**,产出引擎取不到值的废策略:

| 写入口 | 位置 | 现状产出 | 引擎实际 |
|---|---|---|---|
| 默认断言构造 | `CaseComposerCanvas.vue` `buildInitialStrategies()` | `$.status eq 200` | `None eq 200` → **必失败** |
| 字段菜单"从响应提取" | `onFieldExtract()` → `respPathFor()` | expression=`$.data.orderId`(assertable 直抄) | 提取 `None` |
| 字段菜单"断言该字段" | `onFieldAssert()` → `respPathFor()` | target=`$.data.orderId` | 断言 `None` |

(唯一正确的是 `onFieldAssign` 的 `$.request_body.<path>` — assign 就是要写 request_body。)

### 0.2 `/full` 已含 response 契约,但渲染残缺

`GET /api/endpoint/{id}/full`(`EndpointDetailView`,`gimbal_plate/http/views.py:179`)的
`responses: dict[int, ResponseSpec]` 与 request 同等携带 IOFieldBinding 全量
(`io_spec.py` `_serialize` 输出 `fields` + `assertable_fields`),四跳链路
(plate 定义 → `/full` 视图 → 序列化 → 平台代理)全部验证畅通,真实 endpoint
(`order_order_detail.py`、`audit_audit_page.py`)已填数据。

现状渲染缺口:

- Canvas 右栏"响应字段 (200)"块:只渲染 200,一行只有 `name + ui_kind`,
  无 description / 无 assertable 标 / 无其他状态码
- Catalog 详情面板:有响应字段 tab 但只取 `primaryResponse`(200 优先),
  也不是全状态码;且不在步骤编辑上下文里,写策略时看不到

**结论:不缺数据、不缺取数,缺渲染与路径域映射。**

### 0.3 用户决策(2026-08-18 对话拍板)

- 直接用 `/full` 已有的 response 定义渲染,**不另建结构、不进 draft、不进 /convert**
- gimbal 只认导出的结构化文档,平台内部组织与其解耦 — 现有 definition(plate 形状)
  → `/convert` 原样透传策略的架构不动
- 路径拼接方案:response 侧拼 `response_body.` 前缀,`$.status` 特判 `response_status`;
  request 侧(assign target)维持 `$.request_body.` 现状
- UI 形态:**请求体字段页改造成重叠卡片式**,description 之下,左 request 右 response
  双签页,点击加载对应字段和策略;step 信息(右栏)同步做 response 适配

---

## 1. 目标 / 非目标

### 目标

1. 修正策略路径域(§0.1 的正确性 bug)
2. 步骤编辑中栏改 IO 双签卡片:request 页维持现状编辑能力;response 页以
   FieldForm 同款样式渲染 `/full` 响应契约(只读)+ 本域策略
3. 策略按 phase 分签展示(单数组存储不变)
4. 右栏 step 信息按签页分流,响应契约全状态码展示
5. Type C(schema-only 字段)获得查看入口

### 非目标(明确不做)

- 不改 `StepView` / draft / `/convert` 结构 — 策略仍是单数组,无 IO 分域字段
- 不改 FieldForm 渲染内核与 FieldActionMenu 交互
- 不改 plate 任何 schema / 路由 / 序列化
- 不做响应示例值编辑(响应是运行期产物,不是用例配置)
- 不做 4xx/5xx 的差异化断言模板(仅渲染展示)

---

## 2. 结构转换与映射关系(核心契约)

### 2.1 路径域映射函数

新纯函数 `src/utils/scratch-path.ts`(唯一映射点,测试先行):

```ts
/**
 * plate /full 域路径 → gimbal 引擎 scratch 域路径。
 * 引擎 scratch 顶层 key:gimbal/strategy/builtin/call.py 写入的
 * response_status / response_body / ...;JSONPath 导航以 scratch 为根。
 */
export function toScratchPath(platePath: string): string {
  if (platePath === '$.status') return '$.response_status'
  if (platePath === '$' || platePath === '') return '$.response_body'
  return platePath.replace(/^\$\./, '$.response_body.')
}
```

语义表:

| /full plate 域 | 引擎 scratch 域 | 说明 |
|---|---|---|
| `$.status` | `$.response_status` | 引擎独立 key,特判 |
| `$` | `$.response_body` | 根 = 整个响应体 |
| `$.data.orderId` | `$.response_body.data.orderId` | 常规:加前缀 |
| `$.data.container[0].id` | `$.response_body.data.container[0].id` | 下标语法原样保留 |

request 域(assign target)**不需要此函数** — 现状 `$.request_body.<path>` 已正确。

### 2.2 三处写入口落地(C1)

| 入口 | 修改 |
|---|---|
| `buildInitialStrategies()` | 首条保底断言 target 由 `$.status` 改 `toScratchPath('$.status')` → `$.response_status` |
| `respPathFor()` | 返回值包一层 `toScratchPath()`;菜单生成的 extract expression / assertion target 自动走对 |
| `strategyCandidates()` | assertable 候选列表逐条 `toScratchPath()` — 用户在下拉里选的就是运行期真实语义 |

**draft 里存的即执行域路径**(现状本来就是这个域,只是值写错),导出零翻译,
plate `/convert`、gimbal 引擎均无需改动。

### 2.3 策略 phase 分域(视图层过滤,不改存储)

plate `_KIND_LABELS`(`gimbal_plate/http/strategy_dim.py:32-36`)已编码归属,
前端经 `getStrategyKindFull` 拿到的 `detail.phase` 同源:

| phase | kind | 归属签页 |
|---|---|---|
| `before_request` | assign | Request 页 |
| `after_request` | extract | Response 页 |
| `verifying` | assertion | Response 页 |

规则:

- `step.strategy` **仍是单数组**(执行序、plate Step 契约、/convert 全不动)
- 签页渲染时按 `strategyDetail(s).phase` 过滤:`requestStrategies = strategy.filter(s => detail(s).phase === 'before_request')`
- 降级 UI(strategyKinds 拉取失败,detail 无 phase)兜底:extract/assertion 归
  Response 页,assign 归 Request 页(kind 名硬映射,与 plate 表一致)
- 未识别 phase 的策略两页都显示(宁多勿丢)

### 2.4 响应字段数据源与缓存

复用现有懒拉缓存,扩展为全状态码:

```ts
// 现状:respFieldsByEndpoint: Map<endpointId, RespField[]>(只 200)
// 改造:respSpecsByEndpoint: Map<endpointId, RespSpecLite[]>(全状态码)
interface RespSpecLite {
  status: number
  description: string
  fields: IOFieldBinding[]       // /full responses[status].fields 原样
  assertable: string[]           // plate 域路径,渲染用;写策略时过 toScratchPath
}
```

拉取点复用 `ensureRespFields`(同一次 `/full` 请求,`assertableByEndpoint` 与
`respSpecsByEndpoint` 一并回填)。存 Canvas 本地 Map — 引用数据不进 draft
(容器原则,与 assertable 现状同宿)。

---

## 3. UI 设计

### 3.1 中栏卡片结构(`col-fields`)

```
┌─ 步骤标题行(序号 + step 名称输入 + 协议徽章)──── 现状保留 ─┐
│  description 只读                                            │
│  api-summary(method/service/path)                            │
├─ IO 卡片 ────────────────────────────────────────────────────┤
│  ┌─────────────┐┌─────────────┐                              │
│  │ ⬅ Request   ││ Response ➡  │   签页头,点击切换            │
│  └─────────────┘└─────────────┘                              │
│  ───────────── 卡片体(两签共用一壳,内容按 activeIoTab 切)── │
│                                                              │
│  [Request 页 activeIoTab='request']                          │
│    headers KV 行(含 ⓘ/Ⓥ/引用徽章)— 仅 request 域          │
│    FieldForm(bindings=request.fields_meta, 可编辑)           │
│      字段值 → 写 request.body                                │
│      ☰ 菜单四项:引用共享变量/从响应提取/注入响应变量/断言    │
│    策略区:before_request 策略(assign)                       │
│                                                              │
│  [Response 页 activeIoTab='response']                        │
│    状态码分组(200 / 4xx / 5xx 按字典序)                    │
│    FieldForm(bindings=respSpecs[status].fields, 只读)        │
│      契约参考值:example ?? default ?? '—'(不可编辑)        │
│      assertable 字段加 ✓ 标                                   │
│      ☰ 菜单两项:从响应提取/断言该字段(路径过 toScratchPath)│
│    策略区:after_request + verifying 策略(extract/assertion)│
└──────────────────────────────────────────────────────────────┘
```

签页状态:`const activeIoTab = ref<'request' | 'response'>('request')`,
切换 step(`activeStepIdx` watch)时重置回 `request`。

### 3.2 FieldForm 适配(最小改动)

新增两个可选 props:

```ts
/** 只读门控:response 页契约参考用,控件禁用,☰ 菜单保留 */
readonly?: boolean
/** 字段域:request 页四项菜单;response 页仅 提取/断言 两项 */
domain?: 'request' | 'response'
```

- `readonly`:各 ui_kind 控件加 `disabled`;`update:body` 不发
- `domain='response'`:传给 FieldActionMenu 或由 FieldForm 过滤菜单项
  (实现取后者简单:FieldForm 内 `v-if="domain !== 'response'"` 掉
  引用/注入两项;菜单组件零改动)
- 值来源:response 页不传 `body`(或传示例拼装对象),`getValue` 走
  `f.default ?? f.example ?? '—'` 现有 fallback 链即可

### 3.3 菜单动作域感知

| 动作 | Request 页 | Response 页 |
|---|---|---|
| 引用共享变量(插 `${var.x}`) | ✅(现状) | ❌ 无值可插 |
| 注入响应变量(assign) | ✅(现状) | ❌ 无 request_body 可写 |
| 从响应提取(extract) | ✅(现状,expression 过 toScratchPath) | ✅ 主入口 |
| 断言该字段(assertion) | ✅(现状,target 过 toScratchPath) | ✅ 主入口 |

Response 页的 extract/assertion 事件流与 request 页共用 Canvas 现有
`onFieldExtract` / `onFieldAssert`(都 push 到当前 step 的 strategy)—
路径域修正已在 `respPathFor` 内统一完成,两页无需分叉 handler。

### 3.4 右栏 step 信息适配(C3)

- `extracts` 块与"响应字段"块按 `activeIoTab` 分流:
  Request 页显示请求侧统计(字段数/headers 数);Response 页显示响应契约
  (全状态码,含 assertable 标)— 现有"响应字段 (200)"块升级为全状态码版
- `HTTP / service / kind / enabled` 基础块与签页无关,保留

### 3.5 Type C 查看入口(附带)

Response/Request 页底部折叠块"Schema 未绑定字段":

- 数据:`request.model_schema`(fallback `schema`)的 `properties` 键集
  与 `fields[].path` 掐头(`$.`)后的已知集求差集
- 展示:字段名 + schema type + 复制 path;纯查看,不进任何结构
- 注:/full 里 response 侧的 `model_schema` 同理可用;两边都渲染折叠块

---

## 4. 数据流总结

```
plate /full ──(懒拉,复用现有 ensureRespFields)──→ Canvas 本地 Map
   responses{status}.fields ──→ Response 页 FieldForm(只读渲染)
   responses{status}.assertable_fields ──→ 候选/标线(plate 域)
                                                        │
用户菜单动作 ──→ onFieldExtract/onFieldAssert ──→ respPathFor() ──→ toScratchPath()
                                                        │(scratch 域)
                                                        ▼
                                              step.strategy.push(...)
                                                        │
                              draft 原样存(执行域路径,现状即此域)
                                                        │
                              /convert 原样透传 ──→ gimbal 引擎 JSONPath 命中 ✅
```

---

## 5. 实施计划(3 commits,TDD)

### C1 — 路径域修正(正确性 bug,独立先行)

1. 新建 `src/utils/__tests__/scratch-path.test.ts`(红):
   - `$.status` → `$.response_status`
   - `$.data.orderId` → `$.response_body.data.orderId`
   - `$.data.container[0].id` → 前缀保留下标
   - `$` → `$.response_body`;`''` → `$.response_body`
2. 新建 `src/utils/scratch-path.ts` `toScratchPath()`(绿)
3. `CaseComposerCanvas.vue` 三写入口接线:
   - `buildInitialStrategies` 保底断言
   - `respPathFor` 返回值
   - `strategyCandidates` 候选列表
4. `CaseComposerCanvas.test.ts` 修既有断言:
   - T5 期望 `$.response_body.data.orderId`
   - T8 期望 `$.response_body.data.orderId`
   - 默认断言(如有直接断言 `$.status` 的用例)→ `$.response_status`
5. 全量 vitest 绿 → commit

### C2 — IO 双签卡片(主体)

1. `FieldForm.vue`:加 `readonly` / `domain` props(先写测试:
   readonly 控件 disabled、domain='response' 时菜单只剩两项)
2. `CaseComposerCanvas.vue`:
   - `activeIoTab` 状态 + 签页头模板 + watch(activeStepIdx)重置
   - 策略区按 phase 过滤(含降级兜底映射)
   - Response 页:`respSpecsByEndpoint` 全状态码缓存改造 +
     状态码分组 FieldForm(readonly + domain)渲染
   - 中栏"响应字段"旧右栏块如与签页重复,删旧留新
3. `FieldForm.test.ts` / `CaseComposerCanvas.test.ts` 补:
   - 切 Response 签 → 响应字段渲染(mock /full responses 两状态码)
   - Response 页字段菜单 → 两项;点提取 → strategy 落 scratch 域路径
   - 策略 phase 过滤:request 页只见 assign,response 页见 extract+assertion
4. 全量 vitest 绿 → commit

### C3 — 右栏 step 信息适配 + Type C

1. 右栏按 `activeIoTab` 分流;响应契约块全状态码 + assertable 标
2. Type C 折叠块(两侧 model_schema 差集)
3. 补测试(右栏分流文案、Type C 空态/非空态)
4. 全量 vitest 绿 + `npx vite build` 绿 → commit

### 验收

- 全量 vitest 绿(基线 18 files / 117 tests,只增不减)
- `npx vite build` 绿
- 手工冒烟:
  1. 新建/打开场景 → 步骤编辑页见双签卡片,默认 Request 页,现状能力全在
  2. 切 Response → 全状态码响应字段渲染,assertable 有标
  3. Response 页字段点 ☰ → 提取/断言;策略落 Response 页签的策略区
  4. 保存 → /convert 预校验通过;导出文档中断言/提取路径以
     `$.response_body.` / `$.response_status` 开头
  5. request 页四项菜单、变量注册表、headers Ⓥ 分流等回归不破

---

## 6. 风险与边界

| 风险 | 缓解 |
|---|---|
| 历史草稿里已存 plate 域路径的废策略 | 不做迁移。存量策略在运行期本来就不工作,不是本次回归;编辑期用户在策略卡看到旧值可手改(候选列表已是 scratch 域,选一下即修) |
| `$.status` 特判与未来引擎演进耦合 | `toScratchPath` 单点维护;引擎 key 变了改一处 + 测试同步 |
| response 字段 `ui_kind=unknown` 占多数(实测) | FieldForm Type B 降级(unknown → 通用文本)已有,只读展示无影响 |
| 签页切换丢正在编辑的半成品状态 | FieldForm 受控组件,值在 `request.body` / strategy 数组,不在签页本地;切换只切视图不切数据 |
| 降级 UI(detail 无 phase)分域错乱 | kind 名硬映射兜底(extract/assertion→Response,assign→Request),与 plate `_KIND_LABELS` 表一致 |
| `/full` 拉 4xx/5xx 契约 miss(部分 endpoint 只定义 200) | 空态文案"该接口未声明其他状态码响应";不阻塞 |

---

## 7. 关键代码位置索引(实现时直接跳)

| 事项 | 位置 |
|---|---|
| scratch 写入(engine 事实源) | `src/gimbal/strategy/builtin/call.py:101-104` |
| JSONPath 语义(engine 同款) | `src/gimbal/utils/jsonpath.py` |
| plate canonical 示例(scratch 域) | `src/gimbal/schema/strategy.py:100`、`schema/step.py:40` |
| phase 归属表 | `src/gimbal-plate/gimbal_plate/http/strategy_dim.py:32-36` |
| /full 视图(responses 契约) | `src/gimbal-plate/gimbal_plate/http/views.py:179-241` |
| ResponseSpec 序列化 | `src/gimbal-plate/gimbal_plate/schema/endpoint/io_spec.py:244-262` |
| 平台代理 | `src/gimbal-platform/backend/app/routers/endpoint_catalog.py:23` |
| 前端类型 `ResponseSpecView` | `src/gimbal-platform/frontend/src/types/plate.ts:99` |
| 三写入口 | `CaseComposerCanvas.vue` 的 `buildInitialStrategies` / `respPathFor` / `strategyCandidates` |
| 懒拉缓存(改造成 respSpecs) | `CaseComposerCanvas.vue` 的 `ensureRespFields` / `respFieldsByEndpoint` |
| FieldForm(加 readonly/domain) | `src/gimbal-platform/frontend/src/components/composer/FieldForm.vue` |
| FieldActionMenu(零改动) | `src/gimbal-platform/frontend/src/components/composer/FieldActionMenu.vue` |
| 既有测试(修断言) | `CaseComposerCanvas.test.ts` T5/T8;`FieldForm.test.ts` |
