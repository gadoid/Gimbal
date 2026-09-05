/**
 * types/plate.ts — gimbal-plate 对外契约的前端完整结构表述。
 *
 * 真源(Single Source of Truth)在 plate 侧的 Pydantic schema:
 *   - DeclarationEntry / RequestSpec / ResponseSpec → gimbal_plate/schema/endpoint/io_spec.py
 *   - ApiSpec                                      → gimbal_plate/schema/endpoint/api_spec.py
 *   - EndpointMetadata                             → gimbal_plate/schema/endpoint/metadata.py
 *   - EndpointDetailView(/full 视图)               → gimbal_plate/http/views.py
 *
 * 边界原则(项目已定):plate 输出始终是一个 dict,消费者(本前端)自行建模。
 * 本文件就是前端对该 dict 的建模——它是 plate 契约的"完整结构"表述,
 * 而非投影/选择器/分视图。所有消费 plate endpoint dict 的地方都应引用此处类型,
 * 不要在组件或 api 层再重复声明 endpoint 相关 interface。
 *
 * 对齐约束:plate 侧 schema 改字段时,这里必须同步——加字段是契约变更。
 * 若发现与 dict 实际形状不符,以 plate schema 为准并修正本文件。
 */

// ─── 字面量联合:与 plate 的 Literal 一一对应 ──────────────────────

/** DeclarationEntry.ui_kind —— 控件渲染类型。对齐 io_spec.py DeclarationEntry.ui_kind。 */
export type UiKind =
  | 'text'
  | 'number'
  | 'boolean'
  | 'select'
  | 'textarea'
  | 'json'
  | 'file'
  | 'binary'
  | 'unknown'

/**
 * DeclarationEntry.state —— 字段状态(2026-09-05 目录化,共识默认)。
 *
 * plate 目录盖章的渲染/传递意向,场景 step.field_states 稀疏增量可覆盖
 * (解析链 state(path) = field_states[path] ?? entry.state ?? 'form',
 * 前端同式实现于 utils/declarations.ts resolveState,§3.2):
 * - form:     表单直接渲染面
 * - collapse: 折叠区(渲染但收进折叠面板)
 * - carry:    传递面(值在 platform 值表,编排面零感知;carry 容器
 *             ⇒ 子孙 carry,整容器是注入单元 —— 祖先吸收)
 */
export type FieldState = 'form' | 'collapse' | 'carry'

/**
 * DeclarationEntry.source_kind —— 字段值来源(provenance)。
 *
 * 这是"值从哪来"的语义维度,与渲染/传递状态(state)正交。三态自洽:
 * - independent: 独立字面量,与上下文无关联,表单直接填(默认)
 * - lookup:      可经接口/变量查询得到(如 ${var.xxx} / ${env.xxx}),表单只读展示
 * - generated:   运行时基于其他接口处理结果动态生成(如 Assign 时间戳),表单提示"由策略产出"
 *
 * 注意:schema-only 字段(PRD §5.4 Type C)压根不会生成声明条目,
 * 因此碰不到 source_kind。"隐藏 Type C 字段"属于平台侧渲染关注点,
 * 不混入来源语义。详见 FIELD-UI-MAPPING.md / PRD §5.4。
 */
export type SourceKind = 'independent' | 'lookup' | 'generated'

/** ApiSpec.method —— HTTP 方法。对齐 api_spec.py ApiSpec.method(7 种)。 */
export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH' | 'HEAD' | 'OPTIONS'

/** ApiSpec.auth —— 认证方式。对齐 api_spec.py ApiSpec.auth。 */
export type AuthKind = 'none' | 'bearer' | 'basic' | 'cookie' | 'custom'

/** RequestSpec.body_type —— 请求体类型。对齐 io_spec.py RequestSpec.body_type。 */
export type BodyType = 'none' | 'json' | 'form' | 'multipart' | 'raw' | 'binary'

// ─── IO / 坐标 / 元信息 ──────────────────────────────────────────

/**
 * IOFieldBinding —— 字段元信息的 UI 形状(FieldForm / FieldActionMenu 消费)。
 * 由 utils/declarations.ts 从 DeclarationEntryView 投影(掐掉 state /
 * children / type / assertable 四个声明轴;上级归属由 children 树天然
 * 承载,D12 parentPath/parentChannel 已死);plate 侧 wire 已无同名类,
 * 此为前端本地形状。
 */
export interface IOFieldBinding {
  name: string
  /** 寻址真源(D1):归一化 JSONPath($.xxx / $.a[0].b);name 为显示别名,可不同于 path 末段。 */
  path: string
  required: boolean
  default: unknown
  example: unknown
  description: string
  enum: unknown[] | null
  ui_kind: UiKind
  source_kind: SourceKind
}

/**
 * DeclarationEntry 视图 —— declarations 目录条目(字段状态目录,2026-09-05)。
 * 对齐 io_spec.py DeclarationEntry(extra="forbid");plate 序列化经
 * EndpointDetailView exclude_none 裁剪后,type/state/default/example/enum
 * 为 null 的键不在 dict 中(此处标可选,消费侧按缺省 null 处理)。
 *
 * 条目可携带 children 树(容器模板:type=object/array 的结构真源,
 * §5.2「children 是唯一结构真源」);叶子无 children 键。请求面渲染
 * 走 buildNode 值×结构合并树;响应面单脸 = 全量条目,assertable=True
 * 者即断言候选(state 不被读取)。
 */
export interface DeclarationEntryView {
  name: string
  /** 寻址真源(D1):归一化 JSONPath($.xxx);name 为显示别名,可不同于 path 末段 */
  path: string
  /** 字段状态(共识默认;缺省按 form 解析 —— fail-closed) */
  state?: FieldState | null
  /** 容器模板子孙(仅容器条目;模板路径无实例下标,$.a.b 而非 $.a[0].b) */
  children?: DeclarationEntryView[]
  /** JSON Schema 原语类型(P8 回填后全备;缺省按 string 处理) */
  type?: string | null
  required: boolean
  default?: unknown
  example?: unknown
  description: string
  enum?: unknown[] | null
  ui_kind: UiKind
  source_kind: SourceKind
  /** 仅响应面有意义:该字段是否为断言候选(响应单脸标记) */
  assertable: boolean
}

/**
 * RequestSpec 视图 —— 接口请求 body 的形态。
 *
 * 线上键 = body_type / declarations(恒有)/ schema(可选)。declarations
 * 即字段状态目录(条目 + children 模板树,含 state 共识默认):渲染面由
 * 解析态定面(form 直接渲染 / collapse 折叠区 / carry 不进树 —— 值在
 * platform 值表,服务绑定/全局默认两层,运行时由 platform 注入)。
 */
export interface RequestSpecView {
  body_type: BodyType
  declarations: DeclarationEntryView[]
  schema?: Record<string, unknown>
}

/**
 * ResponseSpec 视图 —— 接口某状态码响应的形态。
 * 线上键 = status / description / declarations(恒有)/ schema(可选);
 * 响应面单脸 = 全量条目,assertable=True 者即断言候选
 * (2026-09-05 目录化:state 不被读取,无三通道投影)。
 */
export interface ResponseSpecView {
  status: number
  description: string
  declarations: DeclarationEntryView[]
  schema?: Record<string, unknown>
}

/** ApiSpec 视图 —— 被接口的坐标与协议元信息。对齐 api_spec.py ApiSpec。 */
export interface ApiSpecView {
  service: string
  method: HttpMethod
  path: string
  headers: Record<string, string>
  timeout_seconds: number
  auth: AuthKind
  produces: string[]
  consumes: string[]
}

/** EndpointMetadata 视图 —— 业务元信息(不进执行产物)。对齐 metadata.py EndpointMetadata。 */
export interface EndpointMetadataView {
  module: string
  tags: string[]
  owner: string
  priority: number | null
  preconditions: string[]
  success_criteria: string
  failed_criteria: string[]
  business_notes: string
  deprecated: boolean
  experimental: boolean
}

// ─── /full 视图(EndpointDetailView) ──────────────────────────────

/**
 * EndpointFullView —— plate `GET /api/endpoint/{id}/full` 返回的完整接口契约。
 *
 * 对齐 gimbal_plate/http/views.py 的 EndpointDetailView(extra="forbid" 强契约视图)。
 * 它是前端渲染接口详情(Catalog 详情面板 / Canvas 表单)的唯一数据形状。
 *
 * - request 为 null 表示该接口无请求体(body_type=none 或未声明)
 * - responses 的 key 是 HTTP 状态码的字符串形式(如 "200"),plate 侧是 dict[int, ...],
 *   JSON 序列化后 key 变字符串
 */
export interface EndpointFullView {
  id: string
  system: string
  service: string
  name: string
  description: string
  api: ApiSpecView
  request: RequestSpecView | null
  responses: Record<string, ResponseSpecView>
  metadata: EndpointMetadataView
  version: string
  updated_at: string | null
}

// ─── 策略语法 dim 视图(对齐 plate http/views.py StrategyKindView/DetailView)──

/**
 * 策略语法引用数据 —— plate `GET /api/strategy`(M6 第 8 dim,语法级)。
 *
 * items 不是数据实例,而是从 StrategyUnion 内省出的 kind 描述符:
 * 回答"策略有哪些 kind、每个 kind 有哪些字段"。策略*实例*仍在
 * StepView.strategy 里(上方 StrategyView),本节类型只用于"添加策略"
 * 的结构渲染,不进 draft。strategy_ref 预埋字段不在 dim 输出中。
 */
export interface StrategyKindView {
  kind: string
  label: string
  phase: string
}

/**
 * 单个策略字段的描述符。词汇表对齐 IOFieldBinding(上方)但独立建模:
 * 无 source_kind(字段值来源语义对策略无意义),name/path 无强一致校验。
 */
export interface StrategyFieldDescView {
  name: string
  path: string
  required: boolean
  default: unknown
  description: string
  enum: unknown[] | null
  ui_kind: UiKind
}

/**
 * plate `GET /api/strategy/{kind}/full` —— 表单渲染契约。
 * base_fields(StrategyBase 公共字段)默认不渲染;onFailure/order 两个编排
 * 高频字段由 StrategyForm 特例露出(缺省值兜底语义不变)。
 */
export interface StrategyKindDetailView extends StrategyKindView {
  fields: StrategyFieldDescView[]
  base_fields: StrategyFieldDescView[]
}

// ─── plate Scenario 视图(编排用,对齐 gimbal_plate/schema/scenario.py + step/api/request/strategy)──

/** plate Api(step 内)。对齐 gimbal_plate/schema/api.py Api + view_hints 扩展。 */
export interface ApiView {
  kind: 'api'
  service: string
  method: HttpMethod
  path: string
  headers?: Record<string, string>
  timeout?: number
  /** 平台视图扩展:endpoint_id/module/tags(GimbalScenarioExporter 导出时剥离) */
  view_hints?: { endpoint_id?: string; module?: string; tags?: string[] }
}

/** plate Request(step 内)。对齐 gimbal_plate/schema/request.py Request。 */
export interface RequestView {
  kind: 'request'
  body: unknown
  /** @deprecated 结构快照不再持久化(容器原则:引用数据不进 payload,
   *  渲染时按 api.view_hints.endpoint_id 现拉 /full)。仅为读存量 payload
   *  保留的类型;新代码禁止写入。值为 fields_meta 键控面:顶层 name 键控,
   *  2026-09-05 目录化起条目携带 state 与 children 树、树全量展开
   *  (值透传的 carry 顶层条目不进表;plate export/platform.py 投影)。 */
  fields_meta?: Record<string, DeclarationEntryView>
}

/** plate strategy 三种变体。对齐 gimbal_plate/schema/strategy.py。 */
export interface ExtractView {
  kind: 'extract'
  name?: string
  order?: number           // StrategyBase 公共字段:同 phase 内升序执行,缺省 0
  expression: string       // JSONPath
  target: string
  scope?: string
  default?: unknown
  required?: boolean
  view_note?: string       // 平台视图扩展
}
export interface AssignView {
  kind: 'assign'
  name?: string
  order?: number           // StrategyBase 公共字段:同 phase 内升序执行,缺省 0
  source: unknown
  target: string
  scope?: string
  default?: unknown
  required?: boolean
  view_note?: string
}
export interface AssertionView {
  kind: 'assertion'
  name?: string
  order?: number           // StrategyBase 公共字段:同 phase 内升序执行,缺省 0
  target: string
  operator: string
  expected?: unknown
  message?: string
  soft?: boolean
  view_note?: string
}
export type StrategyView = ExtractView | AssignView | AssertionView

/**
 * plate Step。对齐 gimbal_plate/schema/step.py Step(平台视图在 definition
 * 自由 dict 上扩展 field_states;plate Step 模型 extra=ignore 静默剥除,
 * 注入面在 dispatch 预解析阶段读原始 definition,§3.1)。
 */
export interface StepView {
  kind: 'step'
  description?: string
  api: ApiView
  request: RequestView
  strategy: StrategyView[]
  /**
   * 字段状态稀疏增量(§3.1):{归一化 path → state},与 api/request/strategy
   * 平级。默认不存(空 step 零存储);仅存与目录共识默认不同的条目。
   * 添加字段 = 增量[path]=form/collapse;移除 = 增量[path]=carry。
   * 解析链见 utils/declarations.ts resolveState(单一实现,§3.2)。
   */
  field_states?: Record<string, FieldState>
}

/** plate Meta。对齐 gimbal_plate/schema/scenario.py Meta。 */
export interface MetaView {
  name: string
  description: string
  module: string
  priority: number
  author: string
  owner: string
  tags: string[]
  version: string
  createTime: string
  expire: boolean
  requirementRef: unknown[]
  system: string[]
}

/** plate 时间策略判别对象。对齐 gimbal_plate/schema/time_policy.py。 */
export type TimePolicyView =
  | { kind: 'record' }
  | { kind: 'timeout'; seconds: number }

/** plate 重试策略。对齐 gimbal_plate/schema/retry_policy.py RetryPolicy。 */
export interface RetryPolicyView {
  kind: 'retry_policy'
  maxAttempts: number
  backoffSeconds: number
  retryOn: string[]
}

/** 场景级认证用户快照(plate AuthSession 的配置字段子集,
 *  与 run_dispatcher 执行注入写入形状一致)。字段可选:
 *  兼容导入/历史 payload 的不完整 users。 */
export interface UserAuthView {
  url?: string
  username?: string
  password?: string
  token_type?: string
  expires_in?: number
}

/** plate Config。对齐 gimbal_plate/schema/scenario.py Config。 */
export interface ConfigView {
  setup: unknown[]
  teardown: unknown[]
  services: Record<string, string>
  users: Record<string, UserAuthView>
  timePolicy: TimePolicyView
  retry: RetryPolicyView | null
  vars: Record<string, unknown>
}

/** plate Resource 变体。对齐 gimbal_plate/schema/resource.py。 */
export interface MockView {
  kind: 'mock'
  name: string
  image: string
  config: Record<string, unknown>
  portMapping: Record<number, number>
}
export interface FileView {
  kind: 'file'
  name: string
  path: string
}
export type ResourceView = MockView | FileView

/** plate Scenario 完整视图。对齐 gimbal_plate/schema/scenario.py Scenario。
 *  这就是容器 definition 的形状。 */
export interface ScenarioView {
  kind: 'scenario'
  scenarioId: string
  meta: MetaView
  config: ConfigView
  resource: Record<string, ResourceView>
  steps: StepView[]
  /** 平台视图扩展(可选,来自 PlatformScenarioExporter) */
  endpoints?: unknown[]
  navigation?: unknown
  config_summary?: unknown
}
