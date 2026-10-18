/**
 * types/plate.ts — [DEPRECATED] gimbal-plate 对外契约的前端结构表述。
 *
 * **T5.1（M2 §7 镜像清理）**：M2 A/B 类的类型已由生成物 `types/m2.ts`
 * 取代（同一份 JSON Schema → json-schema-to-typescript，禁改）。
 * 本文件保留两个职责：
 *   1. **M1 视图类型**（endpoint/dictionary/strategy 描述等）——真源在
 *      plate 的 dialect 层，无 M2 生成物对应，继续手写；
 *   2. **平台扩展类型**（FieldState / EndpointFullView / HttpMethod 等）——
 *      属于平台视图层，不属于 M2 结构。
 *
 * **新代码请直接 import from '@/types/m2'**（M2 A/B 类）。
 * 本文件中与 m2.ts 重合的 View 类型已标注 deprecated。
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
 * 动态取数源视图引用(2026-09-07 spec §3.2)。对齐 plate 侧
 * DeclarationEntry.value_source —— 字段值可从被测系统查询视图取回:
 * - view:   查询视图名(query-views 目录键)
 * - column: 行集列名(缺省 = 视图 label 列,由消费方按投影行首键补)
 * - group:  渲染层分组键(缺省 = view;同 view 双角色显式拆组,
 *           §7.3 拆组不拆查询 — 两组同 view 各自打开选择器)
 */
export interface ValueSourceView {
  view: string
  column?: string | null
  group?: string | null
}

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
export type BodyKind = 'none' | 'json' | 'form' | 'multipart' | 'raw' | 'binary'

/** RequestSpec.body_type —— 请求体类型。对齐 io_spec.py RequestSpec.body_type。 */
export type BodyType = 'none' | 'json' | 'form' | 'multipart' | 'raw' | 'binary'

// ─── IO / 坐标 / 元信息 ──────────────────────────────────────────

/**
 * IOFieldBinding —— 字段元信息的 UI 形状(FieldForm / FieldActionMenu 消费)。
 * 由 utils/declarations.ts 从 DeclarationEntryView 投影(掐掉 state /
 * children / assertable 三个声明轴;type 自 2026-09-07 §7.1 起透传 —
 * enum select 的 Number 包裹判据;上级归属由 children 树天然
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
  /** JSON Schema 原语类型(enum Number 包裹判据,2026-09-07 §7.1;缺省 null) */
  type?: string | null
  /** 动态取数源(2026-09-07 §3.2;缺省 null = 无绑定) */
  value_source?: ValueSourceView | null
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
  /** 动态取数源(2026-09-07 §3.2;exclude_none 裁剪后缺省按 null 处理) */
  value_source?: ValueSourceView | null
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

/** Binding 视图 —— 被接口的坐标与协议元信息(A2:api → binding,6.2)。
 * 对齐 dialect/models.py HttpBinding(判别联合首成员;service 在外壳)。 */
export interface BindingView {
  protocol: string
  method: HttpMethod
  path: string
  headers: Record<string, string>
  timeout_seconds: number
  auth: AuthKind
  body_type: BodyKind
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
 * - request 为 null 表示该接口无请求体(binding.body_type=none 或未声明)
 * - responses 的 key 是 HTTP 状态码的字符串形式(如 "200"),plate 侧是 dict[int, ...],
 *   JSON 序列化后 key 变字符串
 */
export interface EndpointFullView {
  id: string
  system: string
  service: string
  name: string
  description: string
  capability: string | null
  consumes: string[]
  produces: string[]
  binding: BindingView
  request: RequestSpecView | null
  responses: Record<string, ResponseSpecView>
  metadata: EndpointMetadataView
  shape_hash: string
  /**
   * 轻列表(`GET /api/endpoint`)的**平铺坐标便捷投影**(7.2:http 专属,
   * 取自 binding.locator();完整 binding 对象只在 /full 出现)。轻列表条目
   * 只有这三个扁平字段 + 基础字段,没有 binding/request/responses/metadata;
   * /full 响应则不携带它们。两形态共用本接口时按可选字段读。
   */
  protocol?: string
  method?: HttpMethod
  path?: string
  /**
   * 声明侧的**可注入面**(platform 代理 `GET /api/endpoint-catalog/{id}/full`
   * 附加字段,非 plate EndpointDetailView 的键):扁平字符串列表,每级容器前缀
   * 与模板形态都已展开(spec §2.2)⇒ 消费侧只做成员判定,不再自己归一。
   *
   * - `null` = 声明面**不可解析**(降级)⇒ 判定从严,只剩 body 面;
   * - `["$"]` = 真无声明 —— 与降级不是一件事,不得用真值判等把二者合并(§5);
   * - 字段缺席(旧缓存替身 / 未经代理的响应)同样按降级处理。
   */
  declared_surface?: string[] | null
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

// ─── M2 类型:平台存储/写入面形态(单一真源 = types/m2.ts 生成物)──
// m2.ts 是 plate 契约的机械投影(可执行 M2 形态);本节的 View 类型是
// 平台域自有形态,只在此一处定义:
//   * 存储形态(Release 6.2):锚点步骤 call 不落 binding 派生字段,
//     执行由 plate /convert 按 meta.plate 投影合并后才成为完整 Call;
//   * 平台写入保证(WithRequired):平台采集/写入面保证字段在场;
//   * 命名联合(StrategyView/ResourceView):多个生成类型的联合。
// 身份别名(ExtractView=Extract 一类)已退役 —— 消费方直接用生成名。
import type {
  Meta, Config, Step, Call, Request,
  Extract, Assign, Assertion, RetryPolicy, UserCredential,
  TimeoutPolicy, RecordPolicy, Scenario, Mock, File as M2File,
} from '@/types/m2'

/** 工具:把 T 的指定键从可选变为必填(平台写入时保证这些字段) */
type WithRequired<T, K extends keyof T> = T & Required<Pick<T, K>>

/** 平台采集面保证 tags/system 在场 */
export type MetaView = WithRequired<Meta, 'system' | 'tags'>
/** 平台侧 Config:setup/teardown 平台不建模(opaque 透传);users 为平台表单形态;var_locks 平台旁挂 */
export type ConfigView = Omit<WithRequired<Config,
  'services' | 'users' | 'timePolicy' | 'retry' | 'vars'>,
  'setup' | 'teardown' | 'users' | 'timePolicy'> & {
    setup: unknown[]; teardown: unknown[]; var_locks?: string[];
    users: Record<string, UserAuthView>;
    timePolicy: TimeoutPolicy | RecordPolicy;
  }
/** 存储形态 step:call 为存储形态(派生字段可选,6.2);strategy 即生成的策略联合 */
export type StepView = Omit<Step, 'call'> & { call: CallView }
/**
 * 存储形态 call:带 endpoint 锚点的接口步骤,call 不落
 * protocol/method/path/timeout 等 binding 派生字段(执行由 plate
 * /convert 按 meta.plate 投影提供,存储出现即被拒收)—— 派生字段
 * 在编辑器/存储面上可选,读侧经 stepMethod/stepPath 等帮助函数
 * 兜底或投影查询(4.8);convert 产物(可执行形态)用完整 Call。
 */
export type CallView = Omit<
  Call, 'protocol' | 'method' | 'path' | 'timeout'
> & {
  protocol?: Call['protocol']
  method?: Call['method']
  path?: Call['path']
  timeout?: Call['timeout']
} & { [key: string]: unknown }
/** 编辑器不建模 body 结构(旧版 body=unknown) */
export type RequestView = Omit<Request, 'body'> & { body: unknown }
/** expires_in 平台侧无 null */
export type UserAuthView = Omit<UserCredential, 'expires_in'> & { expires_in?: number }
/** 平台写入保证:maxAttempts/backoffSeconds/retryOn 恒在场 */
export type RetryPolicyView = WithRequired<RetryPolicy, 'maxAttempts' | 'backoffSeconds' | 'retryOn'>
/** 命名联合:策略条目(生成的 Step.strategy 即此联合) */
export type StrategyView = Extract | Assign | Assertion
/** 编辑器定义 = 存储形态:steps 的 call 派生字段可选(6.2) */
export type ScenarioView = Omit<
  WithRequired<Scenario, 'kind'>,
  'resource' | 'config' | 'meta' | 'steps'
> & {
  resource: Record<string, ResourceView>
  config: ConfigView
  meta: MetaView
  steps: StepView[]
}
/** 平台写入保证(resource 编辑面恒提供这些字段) */
export type MockView = WithRequired<Mock, 'kind' | 'name' | 'image' | 'config' | 'portMapping'>
/** 平台写入保证(resource 编辑面恒提供这些字段) */
export type FileView = WithRequired<M2File, 'kind' | 'name' | 'path'>
/** 命名联合:resource 条目 */
export type ResourceView = MockView | FileView

// ─── step 调用信息读取辅助(前端统一入口,call 单读) ───

type StepLike = StepView | Record<string, unknown> | unknown

/**
 * 从 step 读调用信息(call 唯一形态)。返回的引用即 step.call 本体,
 * 需要改值(headers/service 等)时直接在此对象上写。所有前端消费点
 * 一律经此函数,禁止散读 step.call。
 */
export function stepCall(step: StepLike): CallView | null {
  if (!step || typeof step !== 'object') return null
  const c = (step as Record<string, unknown>).call
  return c && typeof c === 'object' ? (c as CallView) : null
}

/** 从 step 读接口锚点(M3 定稿:step.endpoint 一等字段)。 */
export function stepEndpointId(step: StepLike): string | undefined {
  if (!step || typeof step !== 'object') return undefined
  const eid = (step as Record<string, unknown>).endpoint
  return typeof eid === 'string' && eid ? eid : undefined
}

/** 从 step 读 headers(无调用信息返回空对象)。 */
export function stepHeaders(step: StepLike): Record<string, string> {
  const c = stepCall(step)
  return (c?.headers as Record<string, string>) || {}
}

/** 从 step 读 service。 */
export function stepService(step: StepLike): string {
  return String(stepCall(step)?.service ?? '')
}

/** 从 step 读 method。 */
export function stepMethod(step: StepLike): string {
  return String(stepCall(step)?.method ?? '')
}

/** 从 step 读 path。 */
export function stepPath(step: StepView | Record<string, unknown> | undefined | null): string {
  return String(stepCall(step)?.path ?? '')
}

// ─── 归一方案 v1.0:ref 常量与记录域判定(§1.4/§3.3) ────────────────
// 门禁③放行区:常量 + 记录域判定函数(组件内散写 `startsWith('integration@')`
// 会被 verify_all 门禁拦下 —— 判定唯一实现在此,与后端
// run_semantics.record_category 共享 __fixtures__/ref-record-domain.json
// 样例锁定)。

export const PLATE_REF_WORKING = 'working'
export const PLATE_REF_INTEGRATION = 'integration'

/** 记录域分类(``plate_pins`` 值;台账比对用)。与后端 record_category 对称。 */
export type PlateRecordCategory =
  | 'INTEGRATION' | 'WORKING' | 'PIN' | 'UNDECLARED'

export function plateRecordCategory(value: string | null | undefined): PlateRecordCategory {
  const v = (value ?? '').trim()
  if (!v) return 'UNDECLARED'
  if (v === PLATE_REF_WORKING) return 'WORKING'
  if (v === PLATE_REF_INTEGRATION) return 'INTEGRATION'
  if (v.startsWith(PLATE_REF_INTEGRATION + '@')) return 'INTEGRATION'
  return 'PIN'
}
