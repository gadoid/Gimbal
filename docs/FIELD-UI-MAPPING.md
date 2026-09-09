# 字段 → 渲染 映射文档

> 调研笔记。回答一个核心问题：**当前 schema 字段能否支撑前端页面的所有渲染？**
> 调研对象：`gimbal-plate/src/gimbal-plate/gimbal_plate/schema/`
> 调研目的：校验 PRD v1.0 中所有渲染需求都有 schema 字段支撑，并标注\"够用 / 缺口 / 边界\"。

> **状态更新(2026-09-05,字段状态目录化后)**:IO 声明轴再演进 —— channel
> 三通道(binding/carry/view_only)退役为 `state` 三态
> (form/collapse/carry,默认 form);`type` 升格全条目必填(六原语);
> `children` 内联树取代 `schema_` 成为唯一结构真源(wire 不再有 `schema`
> 键);深实例 path(`$.supplier[0].x` 类)缩并为容器模板 + children;
> `required` 默认翻转为 False(未声明即选填,星标去噪音);响应面单脸
> (全量 + assertable,state 不被读取)。本文 §1.2 表已按现行契约更新。
> 现行契约单点源:`io_spec.py` +
> `docs/superpowers/specs/2026-09-05-field-state-catalog-design.md`。

> **状态更新(2026-09-02,IO declarations 归一化后)**:plate IO 侧已收敛为
> `declarations` 单一承重存储(`DeclarationEntry` 通道标记条目,binding /
> carry / view_only 三通道);`IOFieldBinding` / `CarryEntry` 类与
> `fields` / `carry` / `assertable_fields` 线上键已清除,断言面 =
> view_only 通道 `assertable=True` 条目的 path 集。本文 §1.2 表已按
> 现行 schema 更新;§2-§4 的映射语义(ui_kind / source_kind / Type C
> 差集)不变,只是挂载点从旧三轴换到声明条目。现行契约单点源:
> `io_spec.py` + `docs/superpowers/specs/2026-09-01-io-declarations-unification-design.md`。

---

## 1. 字段清单（按 schema 文件归类）

### 1.1 `base/` — 公共类型

| 类 | 字段 | 类型 | 用途 |
|---|---|---|---|
| `AuthSession` | url | str | 认证接口地址 |
| | username | str | 用户名 |
| | password | str | 密码 |
| | expires_in | int \| None | Token 有效期（秒） |
| | token | str \| None | 访问令牌 |
| | token_type | str | Token 类型（默认 Bearer） |
| | expires_at | datetime \| None | 过期时间 |
| | refresh_token | str \| None | 刷新令牌 |
| *property* | is_authenticated | bool | 是否已认证 |
| | should_refresh | bool | 是否应刷新 |
| | auth_header | str \| None | 生成 Authorization 头 |
| | remaining_seconds | int \| None | 距过期剩余秒 |
| `RefBase` | ref | str | asset ref 字符串 |

### 1.2 `endpoint/` — 接口契约

| 类 | 字段 | 类型 | 用途 |
|---|---|---|---|
| `ApiSpec` | service | str | 服务名 |
| | method | Literal[GET/POST/PUT/DELETE/PATCH/HEAD/OPTIONS] | HTTP 方法 |
| | path | str | URL 路径（必须 `/` 开头） |
| | headers | dict[str, str] | 自定义头 |
| | timeout_seconds | float | 超时（0-600s） |
| | auth | Literal[none/bearer/basic/cookie/custom] | 认证方式 |
| | produces | list[str] | 响应 Content-Type |
| | consumes | list[str] | 请求 Content-Type |
| `DeclarationEntry` | name | str | 字段名(与 path 末段一致) |
| | path | str | 字段路径（JSONPath，自动归一化 `$.xxx`;children 子树内为模板态,禁 `[i]` 下标） |
| | **state** | Literal[form / collapse / carry] | **状态(默认 form):form=表单直渲染,collapse=折叠面板渲染,carry=值表注入不渲染;响应面不读此键** |
| | type | str | 原语类型(全条目必填:string/number/integer/boolean/object/array) |
| | required | bool | 是否必填(默认 False,未声明即选填) |
| | default | Any \| None | 默认值(表单角色元数据,全条目合法) |
| | example | Any \| None | 示例值(表单角色元数据,全条目合法) |
| | description | str | 描述 |
| | enum | list[Any] \| None | 可选值清单 |
| | **ui_kind** | Literal[text / number / boolean / select / textarea / json / file / binary / unknown] | **UI 渲染类型** |
| | **source_kind** | Literal[independent / lookup / generated] | **字段值来源类型** |
| | **value_source** | ValueSource \| None | **动态取数绑定 `{view, column, group}`(2026-09-07 spec §3.2;null = 未绑定,wire 全条目携带,同 `enum: null` 惯例);group 空缺省 = view name,同 view 多角色拆独立选择器** |
| | **assertable** | bool | 仅响应侧有意义:断言候选(默认 False) |
| | **children** | list[DeclarationEntry] \| None | 子树(仅 object/array 容器可带且须非空;carry 容器 ⇒ 子孙必 carry) |
| `RequestSpec` | body_type | Literal[none / json / form / multipart / raw / binary] | body 类型 |
| | **declarations** | list[DeclarationEntry] | 目录清单(身份 + children 结构 + state 共识默认;构造与 wire 同形 `{body_type, declarations}`) |
| `ResponseSpec` | status | int | 状态码 |
| | description | str | 描述 |
| | **declarations** | list[DeclarationEntry] | 全量目录(响应面单脸,state 不被读取;assertable=True 条目即断言面) |
| `EndpointMetadata` | module | str | 业务模块 |
| | tags | list[str] | 标签 |
| | owner | str | 维护人 |
| | priority | int \| None | 优先级（1/2/3） |
| | **preconditions** | list[str] | 前置条件 |
| | **success_criteria** | str | 成功标准 |
| | **failed_criteria** | list[str] | 失败参考 |
| | **business_notes** | str | 业务备注 |
| | **query_safe** | bool | 写副作用白名单声明(默认 False;非 GET 端点挂 `query_views` 须显式 true,构造期拒,spec §3.3④) |
| | deprecated | bool | 是否废弃 |
| | experimental | bool | 是否实验 |
| `EndpointSpec` | id | str | 唯一标识 |
| | system | str | 归属系统 |
| | service | str | 服务 |
| | name | str | 名称 |
| | description | str | 描述 |
| | api | ApiSpec | API 坐标 |
| | request | RequestSpec \| None | 请求形态 |
| | responses | dict[int, ResponseSpec] | 响应形态（key 状态码） |
| | metadata | EndpointMetadata | 业务元信息 |
| | **query_views** | list[QueryView] \| None | **取数视图注记 `{name, params, items, label}`(spec §3.1;name 全局唯一跨端点;不进 /full 投影,经 plate `GET /api/query-views` 索引消费)** |
| | version | str | 契约版本 |
| | updated_at | datetime \| None | 更新时间 |

### 1.3 `interface/` — 用例层

| 类 | 字段 | 类型 | 用途 |
|---|---|---|---|
| `Meta` | name | str | 用例名 |
| | description | str | 描述 |
| | module | str | 业务模块 |
| | priority | int | 优先级 |
| | author | str | 作者 |
| | owner | str | 维护人 |
| | tags | list[str] | 标签 |
| | version | str | 版本 |
| | createTime | datetime | 创建时间 |
| | expire | bool | 过期 |
| | requirementRef | list[RefBase] | 需求关联 |
| | **system** | **list[str]** | **V3.2 归属系统列表** |
| `Config` | setup | list[SetupUnion] | 前置动作 |
| | teardown | list[TeardownUnion] | 后置动作 |
| | services | dict[str, str] | 服务→URL |
| | users | dict[str, AuthSession] | 用户→会话 |
| | timePolicy | TimePolicyUnion | 时间策略 |
| | retry | RetryPolicy \| None | 重试策略 |
| | **vars** | dict[str, Any] | 变量 |
| `Scenario` | kind | Literal[scenario] | discriminator |
| | scenarioId | str | 用例 ID（`sc` 前缀） |
| | meta | Meta | 元信息 |
| | config | Config | 配置 |
| | resource | dict[str, ResourceUnion] | 资源 |
| | steps | list[StepUnion] | 步骤 |
| | **endpoints** | list[dict] \| None | **平台视图扩展** |
| | **navigation** | dict \| None | **平台视图扩展** |
| | **config_summary** | dict \| None | **平台视图扩展** |
| `Step` | description | str | 步骤描述 |
| | api | ApiSpec | API |
| | request | Request | 请求 |
| | strategy | list[StrategyUnion] | 策略 |
| `Request` | **fields_meta** | dict[str, DeclarationEntry] \| None | **平台视图扩展**(值 = binding 通道 DeclarationEntry dump;deprecated,渲染现拉 /full) |
| | body | str \| dict \| list | body 数据 |
| `Strategy` | `kind` | Literal[extract / assign / assertion / strategy_ref] | discriminator |
| | name | str | 策略名 |
| | scope | Scope | 作用域 |
| | onFailure | FailureStrategy | 失败时 |
| | view_note | str \| None | 平台视图注释 |
| `Extract` | expression | str | JSONPath |
| | target | str | 写入目标 |
| | default | Any \| None | 失败默认值 |
| | required | bool | 失败是否抛错 |
| `Assign` | **source** | Any | 路径或值 |
| | **target** | str | 模板路径 |
| | default | Any \| None | 注入失败默认值 |
| | required | bool | 注入失败是否抛错 |
| `Assertion` | target | str | 断言目标 |
| | operator | AssertOperator | 比较符 |
| | expected | Any | 比较值 |
| | message | str \| None | 失败信息 |
| | soft | bool | 软断言 |
| `Mock` | image | str | 容器镜像 |
| | config | dict[str, Any] | 服务配置 |
| | portMapping | dict[int, int] | 端口映射 |
| `File` | path | str | 文件路径或 ref |

---

## 2. 字段 → 渲染映射表

每行回答：前端某个特定视觉元素，用 schema 哪个字段来驱动。

### 2.1 平台视图扩展字段（关键\"如果我们不做出来，平台就缺 X\"）

| 平台元素 | 字段 | 是否存在 | 用途 |
|---|---|---|---|
| 平台渲染视图列表 | `Scenario.endpoints` | ✅ | 前端拿这个 dict 列表渲染 EndpointCatalog |
| 按 service 分组的导航树 | `Scenario.navigation` | ✅ | 平台自动反推，可调 |
| 配置项分类提示 | `Scenario.config_summary` | ✅ | 提示哪些 var/auth 是占位符 |
| 步骤级字段元信息 | `Request.fields_meta` | ✅ | 平台视图扩展，gimbal 自动 exclude |
| 策略人类语言摘要 | `Strategy.view_note` | ✅ | \"response.code eq 0\" 这种提示 |
| API 视图提示 | `ApiSpec.view_hints` | ✅ | 平台后端落库扩展 |

### 2.2 字段编辑器（FieldEditor）控件类型

| 控件 | 触发字段 | 字段值类型 | 缺失场景 |
|---|---|---|---|
| text input | `DeclarationEntry.ui_kind == \"text\"`(binding / view_only 通道) | str | — |
| number input | `ui_kind == \"number\"` | int / float | — |
| boolean toggle | `ui_kind == \"boolean\"` | bool | — |
| select dropdown | **`enum` 非空即 select(2026-09-08 顺车票,spec §7.1):enum 优先于 ui_kind —— plate 目录在 `ui_kind=\"text\"` 字段上回填 enum(action/active_tab/sort_order 等)也走 select 分支;主面/折叠面双面同规则**(旧规则 `ui_kind==\"select\"` + enum 双条件从未命中) | enum 元素(str 化呈现/回显匹配) | 值为模板串(`${…}`)→ 降级 text 输入(选项列表不含模板值);**number 型 enum 写值 Number 包裹**(type integer/number 落 body 前转数字,防落 `\"2\"` 字符串) |
| textarea | `ui_kind == \"textarea\"` | str | — |
| json editor | `ui_kind == \"json\"` | dict / list | — |
| file picker | `ui_kind == \"file\"` | path | — |
| binary upload | `ui_kind == \"binary\"` | bytes | — |
| **fallback（隐藏）** | `ui_kind == \"unknown\"` 或缺省 | — | PRD 5.4 Type B 字段 → **应自动按 text 渲染** |

### 2.3 字段必填标识与默认值

| 视觉 | 字段 | 备注 |
|---|---|---|
| 必填红点 ● | `DeclarationEntry.required == true` | schema 强校验 |
| 选填空心 ○ | `required == false` | — |
| 预填值 | `DeclarationEntry.example` 优先，否则 `default` | PRD 5.5 |
| 字面量展示 | 用户手输 | 灰底 input |

### 2.4 字段绑定动态注入 UI

| 视觉 | 字段 | 触发条件 |
|---|---|---|
| literal 标签 | `source_kind == \"independent\"` | 字面量 |
| lookup 标签 | `source_kind == \"lookup\"` | 从 auth 查 |
| generated 标签 | `source_kind == \"generated\"` | 时间/随机生成 |
| \"🔗 static · ${var.x}\" | `value` 包含 `${var.x}` 模板 | 静态注入 |
| \"🔗 static · ${auth.x.token}\" | `value` 包含 `${auth.x.token}` | 静态注入 |
| \"🔗 dynamic · Assign · ${var.x}\" | `Strategy.kind == \"assign\"` | 动态注入 |
| \"⚠ Assign + Auto-Extract\" | 引用未声明响应路径 | 平台自动生成 Extract |

**当前 schema 字段足以支撑**：所有判定都可以从 `value` 字符串 + `Strategy.kind` 推导出来，**不需要新增字段**。

### 2.5 失败参考 / 前置条件 / 业务备注

| 视觉 | 字段 | 形态 |
|---|---|---|
| 成功标准 · 成功卡 | `EndpointMetadata.success_criteria` | str |
| 失败参考 · 失败卡（多行） | `EndpointMetadata.failed_criteria` | list[str] |
| 前置条件 · 前置卡 | `EndpointMetadata.preconditions` | list[str] |
| 业务备注 · 备注卡 | `EndpointMetadata.business_notes` | str |
| ✅ assertable 标记 | `failed_criteria[i]` 解析路径 ∩ 断言面(view_only 通道 `assertable=True` 条目 path 集) | 平台运行时计算 |
| ○ 未声明标记 | `failed_criteria[i]` 解析路径 ∉ 断言面 | 平台运行时计算 |

`success_criteria` 是 **str**（单条），`failed_criteria` / `preconditions` 是 **list[str]**。形状差异需要前端做不同渲染：成功标准单行、失败参考多行。

### 2.6 跨系统识别

| 视觉 | 字段 | 形态 |
|---|---|---|
| Home 行系统 chip list | `Scenario.meta.system` | list[str] |
| Canvas 顶部系统 chips | `Scenario.meta.system` | 同上 |
| Canvas 步骤流系统徽章 | `Step.api.service.split(\".\")[0]` | 平台运行时反推 |
| 命名空间（fin.codfish） | `Config.users` 的 dict key | 字符串 |
| 跨系统验证 | `meta.system` vs `set(service.split(\".\")[0] for step in steps)` | 平台校验 |

**Meta.system 在 V3.2 已是 list[str]**，schema 直接支持，无需迁移。

### 2.7 步骤流编排

| 视觉 | 字段 | 形态 |
|---|---|---|
| 步骤名 | `Step.description` | str |
| 方法徽章 | `Step.api.method` | enum |
| path | `Step.api.path` | str |
| 系统徽章 | `Step.api.service.split(\".\")[0]` | 平台反推 |
| request body | `Step.request.body` | str/dict/list |
| 字段列表 | `Step.request.fields_meta` | dict（KeyedBy name） |
| 策略链 | `Step.strategy` | list[StrategyUnion] |
| Extract | `Strategy(kind=extract)` | — |
| Assign | `Strategy(kind=assign)` | — |
| Assertion | `Strategy(kind=assertion)` | — |
| 顺序连接符 | steps 数组顺序 | 隐式 |
| 跨系统连接符 | \"→ 切换到 X\" | 平台运行时算 |

### 2.8 用例级配置（Meta ① / Resource ② / Config ③）

| 视觉 | 字段 | 备注 |
|---|---|---|
| scenarioId | `Scenario.scenarioId` | 自动生成 · 锁定 |
| name | `Meta.name` | 必填 |
| description | `Meta.description` | — |
| module | `Meta.module` | 必填 |
| priority | `Meta.priority` | 必填 |
| system chips | `Meta.system` | list[str] |
| author | `Meta.author` | — |
| owner | `Meta.owner` | — |
| tags | `Meta.tags` | list[str] |
| version | `Meta.version` | — |
| requirementRef | `Meta.requirementRef` | list[RefBase] |
| expire | `Meta.expire` | bool |
| Mock 服务列表 | `Scenario.resource[name]` | dict[str, Mock] |
| Mock image | `Mock.image` | str |
| Mock config | `Mock.config` | dict |
| Mock portMapping | `Mock.portMapping` | dict[int, int] |
| File 路径 | `File.path` | str |
| setup | `Config.setup` | list[SetupUnion] |
| teardown | `Config.teardown` | list[TeardownUnion] |
| timePolicy | `Config.timePolicy` | TimePolicyUnion |
| retry | `Config.retry` | RetryPolicy \| None |
| services | `Config.services` | dict[str, str] |
| users | `Config.users` | dict[str, AuthSession] |
| vars | `Config.vars` | dict[str, Any] |

### 2.9 策略表单（plate 策略语法 dim 驱动）

Canvas 策略区 v2：不再 extract 专用，由 `GET /api/strategy/{kind}/full` 的
`StrategyKindDetailView.fields` 驱动通用渲染（StrategyForm → FieldForm 复用）。

| 视觉 | 字段 | 触发条件 |
|---|---|---|
| kind 徽章（响应断言 等） | `StrategyKindDetailView.label` | phase 4 色左边框（before_request 橙 / after_request 绿 / verifying 紫） |
| kind mono 标签 | `StrategyKindDetailView.kind` | — |
| 头行单行摘要 | 实例字段值（见下方摘要规则） | 溢出 ellipsis；title 悬停看全文 |
| "添加策略 ▾" 下拉项 | `items[].label` + `kind`（S1 列表） | kinds 懒加载；失败降级旧 extract UI |
| 策略字段控件 | `fields[].ui_kind` + `enum` | 词汇表同 §2.2 FieldEditor（text/number/boolean/select/...） |
| operator 下拉 14 项 | assertion kind 的 `fields[operator].enum` | `ui_kind == "select"` |
| 添加骨架默认值 | `fields[].default` 非 null 展开 | `{kind}` + defaults |
| base 公共字段 | `base_fields` | **第一版不渲染**，默认值生效（name/order/enabled/onFailure/...） |
| 删除按钮 × | — | `strategy.splice`（`@click.stop`，不冒泡到头行折叠） |

**折叠-展开交互**（v2.1）：策略卡默认折叠为单头行（徽章 + kind + 摘要 + 箭头 + ×），
点头行任意处（× 除外）切换 `v-show` 字段区。**新添加的策略自动展开**引导填写；
预填/加载的保持折叠降噪。切 step 后"刚添加"标记重置（下标在新 step 语境无意义）。

**头行摘要规则**（按 kind 取最有辨识度的 1-3 个值拼一句，空显"未配置"）：

| kind | 摘要 |
|---|---|
| `extract` | `{target} ← {expression}` |
| `assign` | `{target} = {source}` |
| `assertion` | `{target} {operator} {expected} · {message}`（message 空则省） |
| 未知 kind | 前两个非 kind 非空字段的 `k=v` |

**词汇适配**（前端 StrategyForm 内完成，不改 FieldForm 本体）：
`StrategyFieldDescView` 无 `source_kind`（值来源语义对策略无意义）→ 补
`source_kind: 'independent'` + `example: null` 后按 FieldForm 的字段形状
（前端本地 `IOFieldBinding` 投影,`utils/declarations.ts`）消费。

**初始策略预填（endpoint 契约驱动，替代硬编码）**：加入 endpoint 时由
`/full` 的 `metadata.success_criteria` + `responses[200]` 断言面（view_only
通道 `assertable=True` 条目 path 集）构造：
- 保底第一条：`assertion {target: $.status, operator: eq, expected: 200}`（HTTP 层，恒有）
- 契约驱动追加：`success_criteria` 非空 **且** 断言面含
  `$.code` / `$.data.code` 之一 → 追加 `assertion {target: <codeTarget>, operator: eq, expected: 0, message: success_criteria}`

`strategy_ref`（预埋字段，待重设计）不出现在 dim 输出与策略表单中。

### 2.10 字段状态控制（state 行尾下拉 + 找回搜索框，2026-09-07）

Canvas 请求签字段的 state 控制回路（字段状态目录化 + 找回闭环）：

| 视觉 / 交互 | 字段 | 触发条件 |
|---|---|---|
| 行尾状态下拉（form/collapse/carry） | `DeclarationEntry.state` + `Step.field_states` | 写入走稀疏增量（`step.field_states[path] = 值`，空则整键删除）；校验 `validateEndpointFieldStates`（§3.5 前端门禁，errors 拒 → 整批回滚） |
| 行尾 ↺ 重置 | `Step.field_states` | 清除该条增量；增量空整键删除（读穿共识默认） |
| 容器行尾下拉 carry 一次成功 | `Step.field_states` | sink 级联：容器 + 子孙同批 carry 增量（`cascadeIncrements`，utils/declarations.ts） |
| **字段找回搜索框**（`FieldStateSearch`，请求签顶部常驻） | 目录全量（含共识 carry 字段） | `searchCorpus` 平铺目录（含 children 树内）→ 名称/面包屑过滤；命中行下拉写 `field_states` 同路径增量；surface 级联：深子拉起祖先落 collapse；行内 ↺ 仅清自身（祖先意图保留） |
| 搜索空态 | — | 语料空（无目录）或无命中时提示文案，不报错 |

**为什么需要搜索框**：行尾下拉只挂渲染行，carry 字段不进渲染树
（buildNode 剪除）→ carry→form 无 UI 路径；plate 共识 carry 字段
（备注族）靠搜索框才能进场景表单（09-05 spec §10.0 挂账，2026-09-07
已实施，见 [2026-09-07 spec](superpowers/specs/2026-09-07-field-recovery-and-export-threading-design.md) §2）。

### 2.11 动态取数源（value_source 查钮 / 选择器 / 徽标，2026-09-08）

Canvas 请求签字段的组合期取数回路（[2026-09-07 动态取数源 spec](superpowers/specs/2026-09-07-dynamic-value-source-design.md) §7）：

| 视觉 / 交互 | 字段 | 触发条件 / 语义 |
|---|---|---|
| 行尾「查」按钮 | `DeclarationEntry.value_source` 非空（叶子行） | 点击开 `ValueSourcePicker`；行集由 Canvas 经平台后端 `GET /api/query-views/{view}/rows` 拉取（service_url / query_alias 由前端求值传参：URL 取 authored `config.services` —— 取数上下文唯一 URL 源，方案侧车 `ServiceBinding.url` 不参与；别名取 runSchemes 服务绑定首个显式 `queryUser ?? authAlias`，均缺 = 诚实 422） |
| 参数段（spec §13.5） | `QueryView.query_params`（经 `GET /api/query-views` 索引） | 查钮先拉索引定参数面：`query_params` 非空 → 选择器开即**参数段**（同名约定预填 step body 顶层字面量，模板串/空 → 留空手输）；「查询」确认**携参拉行集**（`params` = JSON-object 字符串查询参，空值剔除 — 未填即未供给，缺键 422 由后端兜底）；「↩ 改参数」回跳值保留（错误态同样可达，参数面不被降级态困住）；刷新复用最近携参；索引不可达按无参处理（rows 侧降级） |
| 选择器分组键 | `value_source.group`（空缺省 = view name） | 同组字段 = 一次业务占用：选行后**一查多填扇出**，组内字段逐列落值（`column` 空 = label 列 = 行首键）；**缺列跳过**（行无该键 → 该字段值保留不覆写）；同 view 双角色（如 `cost_list#to_customer` / `#to_supplier`）拆独立选择器互不覆写，共享同一次查询（后端 L1/L2） |
| 选择器呈现列 | `QueryView.label` + 后端投影列序 | 呈现列 = label 打头 + 其余绑定列去重（保持后端投影列序）；行首键即 label 列 |
| 本地过滤输入框 | — | 纯前端收窄零上游（MAX_ROWS=200 已是呈现面边界，超限 truncated 提示） |
| 「↻ 刷新」按钮 | `refresh=1` 查询参数 | bypass 后端 L1 缓存强制重取 → 新 `fetched_at` |
| 选行落值 | 组字段 × 结果行 | **字面量**落 body（值语义：非注入，落盘即钉死，§7.5）；number 型列写值 Number 包裹 |
| **数组嵌套锚定** | 绑定路径（模板态 vs 实例态） | **组匹配按模板路径**（点击行实例路径剥 `[i]` 下标后与 `value_source` 字段模板路径比对）；**落值/徽标锚定点击行实例路径**（如 `$.fees[0].cost_id`）—— 模板路径落数组子孙会物化 dict 顶替 array，故写值沿实例路径；无实例语境（无 `[i]`）→ 跳过落值（同缺列，值保留） |
| view 徽标 | `queryBadges[实例路径]` = `{view, fetched_at}` | 绑定字段行尾显示来源 view + 取数时间；键与落值写同径（数组嵌套叶 = 实例路径），FieldForm 叶子行按实例路径查询亮起 |
| 降级态：错误条 + 认证页直达 | 路由错误码 | `sut_auth_expired` → 错误条（code + message）+「到认证页刷新凭证」直链（`/auths`），**无自动重登录**；其余错误透出 code/message |
| 降级态：stale 缓存副本 | `stale=true` | 上游失败 → 展示最后成功快照 +「数据可能过期」提示 + **原 fetched_at 不变**（不空白） |
| RunDialog 服务绑定行 queryUser 输入 | `ServiceBinding.queryUser` | 查询凭证别名（挂账 #3 最小配置）；空缺省回落绑定主凭证（authAlias） |

**值语义边界（§7.5）**：查钮钉的是**当时的字面量**，不建立运行期依赖 ——
`value_source` 只是指路的元数据，场景产物里落的是值本身；徽标是用户可见
的溯源面（view + fetched_at），`group` 不进徽标/场景产物。

---

## 3. 渲染缺口与边界

### 3.1 字段类型 — 没有缺口

schema 提供了 `ui_kind` 的 9 种字面量 + `source_kind` 的 3 种字面量。所有 PRD 5.4 节 Type A/B/C 字段和 5.6 节静态/动态/Auto-Extract 三种视觉都能用这两组字面量驱动。

**边界情况**：
- `ui_kind == \"unknown\"`（schema 默认值）→ PRD 5.4 Type B 字段，前端**自动按 text 渲染**（无 schema 缺口）
- `enum == []` 或 `None` → 元素下拉不可用，select 控件退化为 text

### 3.2 失败参考 × 断言面联动

**当前实现**：平台运行时计算 `failed_criteria[i]` 解析路径 ∩ 断言面（view_only 通道 `assertable=True` 条目 path 集,旧 `assertable_fields` 键的继任）。**schema 字段够用**。

### 3.3 跨系统识别

**当前实现**：从 `Step.api.service.split(\".\")[0]` 反推 + 与 `Meta.system` 校验。**schema 字段够用**。

**边界**：用户用 `ref` 引用（`ApiRef`）时，service 字段缺失，平台无法反推归属系统。**需要后端在 ApiRef 解析时填充 service 字段**。

### 3.4 静态 vs 动态注入

**当前实现**：从 `Strategy.kind` 区分。从字段值的字符串模板（`${var.x}` / `${auth.x.token}`）区分**预填值**是字面量还是变量引用。**schema 字段够用**。

**边界**：平台支持**双向注入**（用户输字面量，平台加 Assign 注入变量），`Strategy.kind=assign` 已经能表达。

### 3.5 全量字段请求（Type C 字段运行时携带）

**当前实现**：示例字段值取自 `DeclarationEntry.example` / `default`，缺省时留空。**schema 字段够用**。

**缺口**：schema 没有\"示例字段值缺失时填什么\"的语义约定。这是**业务约定**（PRD 11 节开放问题 #3），非 schema 缺失。

### 3.6 平台视图扩展（5 个字段）

| 字段 | 用途 | 状态 |
|---|---|---|
| `Scenario.endpoints` | EndpointCatalog 渲染视图 | ✅ schema 已定义 |
| `Scenario.navigation` | 按 service 分组的导航树 | ✅ schema 已定义 |
| `Scenario.config_summary` | 配置项分类提示 | ✅ schema 已定义 |
| `Request.fields_meta` | 步骤级字段元信息 | ✅ schema 已定义 |
| `Strategy.view_note` | 策略人类语言摘要 | ✅ schema 已定义 |
| `Api.view_hints` | API 视图提示 | ✅ schema 已定义 |

**所有 6 个扩展字段都已 schema 化**，前端可以直接读取。

### 3.7 已知 schema 不能直接撑的边界

| 渲染需求 | schema 字段 | 备注 |
|---|---|---|
| \"最近使用变量\"快捷区 | 无 | 需要前端在用户态记录 |
| 跨 step 同名字段冲突的 step 标识 | `Step.api.service` 间接 | 平台运行时反推 |
| 类型校验（number 字段填 string） | `DeclarationEntry.ui_kind` | 平台运行时校验 |
| 批量引用（多选字段） | 无 | 高级用户功能 |
| @ 浮层里的\"最近用过\" | 无 | 需要前端在用户态记录 |

**结论**：这些\"非持久化\"的 UX 增强功能由前端在浏览器层维护，不进 schema。

---

## 4. PRD 渲染需求清单 vs schema 字段支撑

| PRD 需求 | 字段 | 状态 |
|---|---|---|
| CaseComposer Home 显示被测系统 chip 列表 | `Meta.system: list[str]` | ✅ |
| 4 屏 HeadStepper 位置统一 | （前端布局） | ✅ |
| 4 屏导航按钮规范 | （前端布局） | ✅ |
| 字段编辑器按 ui_kind 渲染 | `DeclarationEntry.ui_kind` | ✅ |
| 字段编辑器缺 ui_kind 默认 text | `ui_kind == \"unknown\"` → 兜底 text | ✅ |
| 字段三种类型（Type A/B/C） | `ui_kind` + 是否生成 binding 通道声明条目 | ✅ |
| 字段全量请求运行时携带 | `Request.fields_meta` + `RequestSpec.declarations` binding 通道 | ✅ |
| 静态 vs 动态注入两种视觉 | `Strategy.kind` + 值字符串模板 | ✅ |
| @ 浮层 + Auto-Extract | 用户态 + 平台运行时算 | ✅ |
| 失败参考 + 前置条件 + 业务备注 | 三个 metadata 字段 | ✅ |
| 失败参考 × assertable 联动 | `failed_criteria` + 断言面（view_only `assertable=True` 条目） | ✅ |
| 跨系统识别 | `Meta.system: list[str]` + `service.split(\".\")` | ✅ |
| 命名空间 `<system>.key` | `Config.{services,users,vars}` 是 dict | ✅ |
| 用例编排 4 步 stepper | `Scenario.{meta, config, resource, steps}` 4 段 | ✅ |
| Runner 内嵌于 Canvas | （前端路由切换） | ✅ |
| AddStep / AddStepDetail 内嵌 | （前端子组件） | ✅ |
| HeadStepper 4 步进度条 | `steps[*]` 数量 + 当前 active step | ✅ |
| 字段折叠携带关 toggle | （前端用户态） | ✅ |

**所有 PRD 5-6 节描述的渲染需求都有 schema 字段支撑**。

---

## 5. 建议

### 5.1 schema 字段已足够

**当前 schema 完整支撑 PRD v1.0 所有渲染需求**。不需要新增字段。

### 5.2 建议关注的边界条件

后端实现时需确认：

1. **`RefreshPolicy` 字段命名**：当前是 `maxAttempts` / `backoffSeconds` / `retryOn`，与 PRD 5.5 节的\"最大次数 / 重试间隔 / 触发条件\"一致
2. **失败参考列表的字段形态**：`failed_criteria: list[str]`，前端需自行解析\"状态码 + 描述\"两层（如果想要结构化，建议新增 `failed_criteria: list[FailedCriterion]` 子模型，但当前实现够用）
3. **C2 字段值来源**：schema 没有 `source_kind == \"lookup\"` 时如何从 auth 拿哪个字段的约定——这是**业务约定**，应由被测系统在 DeclarationEntry.example 字段里提供完整路径（如 `${auth.codfish.suppliers}`）

### 5.3 不需要新增字段

明确**不需要**新增字段的场景：

- ❌ \"最近使用变量\" → 前端用户态
- ❌ \"Auto-Extract 元数据\" → 平台运行时算 + 直接修改 Strategy 列表
- ❌ \"跨系统连接符\" → 平台运行时检测相邻 step service 前缀变化
- ❌ \"字段折叠 toggle 状态\" → 前端用户态
- ❌ \"当前选中 step\" → 前端用户态

---

## 6. 结论

**当前 schema 字段对前端渲染是充分且自洽的**。

- 16 类平台视觉元素（字段编辑器、失败参考、跨系统、@ 浮层、HeadStepper 等）全部有 schema 字段支撑
- 6 个平台视图扩展字段已 schema 化
- 5 个用户态 UX 增强（最近使用、Toggle、选中状态等）由前端浏览器层维护，不需进 schema

唯一的开放问题在 `failed_criteria` 的结构化（当前是 `list[str]`）—— 这是**业务形态**选择，不是 schema 缺失。如果未来要拆成 `[{status, description, fail_field}]`，再升级 schema。
