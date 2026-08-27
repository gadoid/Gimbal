# Strategy 语法服务化设计:plate 第 8 个 dim + 平台通用策略编辑

**日期**: 2026-08-17
**状态**: 待 review
**范围**: gimbal-plate(新增 strategy dim)+ gimbal-platform(后端代理 + 前端 StrategyForm);**两侧 strategy schema 定义零改动**

---

## 1. 背景与问题

### 1.1 现状

- plate 的 [strategy.py](../../../src/gimbal-plate/gimbal_plate/schema/strategy.py) 已有完整策略抽象:`StrategyBase` 公共字段(phase/order/enabled/onFailure/timeout/tags)+ Extract/Assign/Assertion/StrategyRef 判别联合。**结构齐了,但 HTTP 层没暴露。**
- 平台前端 Canvas 只做了 extract 一种策略的增删 UI([CaseComposerCanvas.vue](../../../src/gimbal-platform/frontend/src/components/composer/CaseComposerCanvas.vue) 的 extract 专用区);assign/assertion 无编辑入口。
- 前端 [plate.ts:184-214](../../../src/gimbal-platform/frontend/src/types/plate.ts) **手写镜像**了三种 StrategyView 类型,靠人肉同步,会漂移。

### 1.2 与 IOFieldBinding 的历史同构

这和 endpoint 字段曾经的"手写表单 vs binding 驱动"是同一个决策的第二次出现:plate 拥有结构权威,平台不该自己维护第二份结构描述。endpoint 的解法是 `IOFieldBinding` + `/api/endpoint/{id}/full`;策略照方抓药,把**语法**(有哪些 kind、每个 kind 有哪些字段)也服务化。

### 1.3 术语澄清(讨论中拍板)

**服务化的是"语法",不是"数据"。** 策略实例照旧存在 scenario 的 `steps[*].strategy` 里,归平台管;plate 只暴露策略的种类描述符。8 个 dim 里 7 个服务数据、1 个服务语法,plate 依然是"结构权威源",只是权威范围从 endpoint 结构扩到 strategy 结构。

---

## 2. 设计原则(讨论拍板)

| # | 原则 | 来源 |
|---|---|---|
| 1 | plate 把 strategy 语法注册成 **M6 第 8 个 dim**,复用现成 URL 语法/信封/light-full 视图,不发明裸路由 | "能否复用这些设计风格"讨论 |
| 2 | **strategy schema 定义零改动**:内省是只读的,方向 http → schema,不触碰 schema 锁 | 影响评估讨论 |
| 3 | **strategy_ref 整条排除**,不做 hidden 标注——它是预埋字段,待后续重新设计 | 用户拍板 |
| 4 | 字段描述符**直接复用 `IOFieldBinding`**(name/required/default/enum/ui_kind/description),不新造模型 | 与 endpoint 字段同一套词汇表 |
| 5 | 描述符从 Pydantic model **内省生成**(复用 `_bindings_from_model` 路子),plate 改 strategy.py 即自动生效 | 单一权威源 |
| 6 | 平台侧沿用容器方案:实例已在 `definition.StepView.strategy`,语法是**引用数据不进 draft**,orchestration **零改动**(StrategyBase 原生有 name/enabled/order) | "以配置改造的容器化设计方案处理"讨论 |

---

## 3. plate 侧:strategy dim

### 3.1 URL 面(全部白拿 M6 通用路由)

```
GET /api/strategy                      → kinds 列表(light view,给"添加策略"下拉)
GET /api/strategy/{kind}               → 单个 kind light view
GET /api/strategy/{kind}/full          → 字段描述符(full view,给表单渲染)
GET /api/systems/{system}/strategy...  → 系统作用域变体;语法是全局的,
                                         list_for_system 无视 system 返回全量
                                         (config/meta/resource 已有 flat 先例)
GET /api/strategy/{kind}/references    → 走通用路由,else 分支返回空 signals
```

无 URL 冲突(`strategy` 不与现有 dim 撞名);OpenAPI 文档、错误信封、404、501 行为全部继承通用 handler。

### 3.2 Index 与 View 模型

```python
# http/grammar.py 新增 StrategyIndex(BaseIndex)
# items 不是数据实例,而是 kind 描述符 —— 这是与现有 7 个 dim 的唯一概念差异,
# docstring 必须写明 "grammar-level dim, not data"。

list_global()  → 从 StrategyUnion 内省出 3 个 kind 描述符
list_for_system(system) → 无视 system,返回全量(语法全局)
get("extract") → 单 kind 描述符;未知 kind → None → 404
to_view(item)  → StrategyKindView

# http/views.py 新增两个 view(对齐 endpoint 的 light/full 语义):
StrategyKindView:        kind / label / phase        # 下拉菜单够用
StrategyKindDetailView:  + fields / base_fields      # 表单渲染用
                         # 两者的字段类型都是 list[IOFieldBinding]
```

### 3.3 内省实现要点

- kind 清源:`{"extract": Extract, "assign": Assign, "assertion": Assertion}`。
  **strategy_ref 显式排除**(union 定义原样保留,预埋语义不丢;后续重设计时去掉过滤行即自动进菜单)。
- 字段派生:对每个类调 `_bindings_from_model()`(io_spec.py 现有私有函数,同包内 import,避免动被 schema 锁住的 `__all__` 面)——`scope`/`operator`/`onFailure` enum→select、`required`/`soft` bool→boolean、`expression`/`target` str→text **全部自动映射**。
- 拆分:`model_json_schema()` 会带出 `kind` 判别字段(const)和 StrategyBase 继承的 8 个公共字段——View 层拆成 `base_fields`(收起,第一版前端不渲染)+ `fields`(业务字段),判别字段剔除。
- `source: Any` / `expected: Any` 无类型信息 → `ui_kind=unknown` → 前端 Type B 兜底渲染 text,可接受。
- 中文 label 与 phase 归属(extract=after_request / assign=before_request / assertion=verifying)schema 里没有编码,放 dim 模块的 `KIND_LABELS` 元数据 dict;后续想精致就给 strategy.py 的 Field 加 `description=`,自动带出。

### 3.4 注册位置(拍板:pragmatic)

在 [dimensions.py](../../../src/gimbal-plate/gimbal_plate/systems/fin/dimensions.py) 的 `register_fin_dims` 里注册,注释标明"strategy 为语法级 dim,非 fin 数据"。理由:该函数是生产(`app._lifespan`)与测试(`tests/plate/conftest.py:fresh_registry`)共用的唯一装配入口,dimensions.py 文档明确警告过新增第二条装配路径会导致生产/测试 drift。洁癖方案(lifespan 单独 `register_strategy_dim`)被否决。

顺手改 app.py 两处"7 个 dim"注释 → "8 个(7 数据 + 1 语法)",纯文档。

---

## 4. 平台侧:容器方案映射

### 4.1 数据归属(容器三段论的套用)

| 东西 | 归属 | 说明 |
|---|---|---|
| 策略**实例** | **已在 definition 里**(`StepView.strategy: StrategyView[]`,配置改造时已进入容器) | 不动;导出零翻译 |
| 策略**语法**(kinds 目录/字段描述符) | **引用数据,不进 draft**——与 envs/endpoint catalog 同级 | 进 Canvas 时拉一次、按 kind 缓存 detail |
| 策略 UI 辅助态(高级字段折叠/widget 覆盖表) | 前端用户态/静态配置 | FIELD-UI-MAPPING.md §3.7 先例 |

### 4.2 orchestration 零改动(容器方案的加分项)

step 需要 `StepOrchestration{enabled,name}` 是因为 plate Step 没这两个字段;但 **StrategyBase 原生自带 `name`/`enabled`/`order`/`tags`**——策略的展示名、启用开关、排序直接读写 definition 里的字段,保存/导出自动生效,不需要 index 对齐的辅助数组。策略这块的"平台附加"比 step 还薄:纯 definition + 纯引用数据。

### 4.3 后端:代理路由

克隆 [endpoint_catalog.py](../../../src/gimbal-platform/backend/app/routers/endpoint_catalog.py) 模式,新增 `routers/strategy_catalog.py`:

```
GET /api/strategy-catalog             → 代理 plate /api/strategy,解信封返回 items
GET /api/strategy-catalog/{kind}/full → 代理 /api/strategy/{kind}/full,解信封返回 item
```

前端继续只感知平台单一 API 面,不感知 plate 地址。

### 4.4 前端:StrategyForm + 通用策略区

```
components/composer/StrategyForm.vue   # 新增:kind 头(标签/phase 徽章)+ 复用 FieldForm
                                       #   bindings=detail.fields, body=策略实例(v-model)
                                       #   base_fields 第一版不渲染(默认值生效)
CaseComposerCanvas.vue                 # extract 专用区 → 通用"策略"区:
                                       #   "+ 添加策略"下拉从 kinds 生成(plate 加新 kind
                                       #   前端零改动出现新条目),按 kind 懒加载 detail
```

### 4.5 endpoint 契约驱动的初始策略预填(2026-08-17 讨论并入)

**现状问题**:`onAddEndpoint` 硬编码一条 `$.status eq 200` 断言;`/full` 响应里的策略原料(`assertable_fields` / `success_criteria` / `failed_criteria`)拉下来就被丢弃,FIELD-UI-MAPPING §2.5 规划的联动从未发生。fin 这类 `code=0` 才算业务成功的接口,预填只覆盖 HTTP 层。

**预填规则**(endpoint 契约驱动,替代平台硬猜):

1. **保底**:`$.status eq 200` 断言永远第一条(HTTP 层,现状行为)。
2. **业务断言**:`success_criteria` 非空 **且** `assertable_fields` 含 `$.code` 或 `$.data.code` 时,追加 `$.code eq 0`(message 携带 success_criteria 文案);条件不满足时跳过——不给没有 code 语义的接口塞无效断言。
3. **原料留存**:`assertable_fields` 按 endpoint 存入 Canvas 本地(Map 或 view_hints),本期只存不消费,作为后续 target/expression 下拉候选的数据基础。
4. 预填策略与用户手动添加的形态无差(同一 StrategyView),可删可改。

**边界**:`$.status` vs plate 导出用的 `response.status` 两种 target 写法差异**不在本期统一**(需 runner resolver 验证),记录到 known-issues 单独立项。

- **组件级复用 FieldForm**:getByPath/setByPath 契约原样成立(描述符 path 归一为 `$.字段名`,与策略实例对象键对应),描述行样式天然一致。
- **widget 覆盖表**(而非硬编码分支):`{ 'extract.expression': JsonPathPicker }` 形态的静态映射;第一版**无覆盖项**,全部走通用渲染。`extract.expression` 联动所选 endpoint 的 `assertable_fields` + 现成 `resolve-paths` action 做 JsonPathPicker 列为**后续增强**,本期不做。
- 类型新增([types/plate.ts](../../../src/gimbal-platform/frontend/src/types/plate.ts)):`StrategyKindView` / `StrategyKindDetailView(= kind view + fields/base_fields: IOFieldBinding[])`。

---

## 5. 影响评估(讨论中逐项查证)

| 影响面 | 结论 |
|---|---|
| plate/runner 两份 strategy.py | **零改动**。runner 消费策略实例,plate 暴露语法,两条线不相交;schema 锁(192 字段/53 `__all__`)不受扰动 |
| export 消费(`_render_strategy` 等) | 零改动,序列化实例不看 dim |
| dim 数量断言 | 无测试断言数量;[test_http_references.py:33-35](../../../tests/plate/test_http_references.py) 等显式枚举 7 个名字,加第 8 个不进参数表,全绿 |
| 通用路由/信封/404 | 白拿,无新路由概念 |
| registry | `register_dim` 纯 dict 写入,无计数无顺序依赖 |
| 平台 CaseComposer.vue / orchestration / store / draft 结构 | **零改动** |
| 旧数据兼容 | 已有 extract 策略的草稿照常渲染(extract 本就在 kinds 列表里) |

## 6. 边界与不做的事

- ❌ strategy_ref 的任何 UI/组件实现(预埋,待重设计)
- ❌ base_fields 的渲染(收进"高级"区是后续迭代)
- ❌ `extract.expression` 的 JsonPathPicker / assertion.target 下拉候选(§4.5 只留存原料不消费;后续增强)
- ❌ `failed_criteria`(B2 解析结果)参与预填——失败路径断言的业务价值低于成功路径,且文案解析覆盖率不稳,后续增强
- ❌ `$.status` vs `response.status` target 写法统一(runner resolver 验证单独立项,known-issues 记录)
- ❌ strategy.py 加 UI 标注字段(会破坏 schema 锁,且 dim 内省已覆盖)
- ❌ 策略实例的存储/校验逻辑变化(plate /convert 依旧是唯一校验点)

## 7. 后续演进路径(记录,不实施)

1. plate 新增策略种类 = strategy.py 加类 + 进 union + KIND_LABELS 加一行 → 前端菜单自动多一项、表单自动渲染。
2. strategy_ref 重设计后:去掉 dim 过滤行即自动进菜单。
3. 字段描述精致化:给 strategy.py Field 加 `description=`,dim 自动带出(与 endpoint description 同路线)。
