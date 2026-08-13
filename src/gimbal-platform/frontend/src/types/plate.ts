/**
 * types/plate.ts — gimbal-plate 对外契约的前端完整结构表述。
 *
 * 真源(Single Source of Truth)在 plate 侧的 Pydantic schema:
 *   - IOFieldBinding / RequestSpec / ResponseSpec  → gimbal_plate/schema/endpoint/io_spec.py
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

/** IOFieldBinding.ui_kind —— 控件渲染类型。对齐 io_spec.py IOFieldBinding.ui_kind。 */
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
 * IOFieldBinding.source_kind —— 字段值来源(provenance)。
 *
 * 这是"值从哪来"的语义维度,与"是否在表单展示"正交。三态自洽:
 * - independent: 独立字面量,与上下文无关联,表单直接填(默认)
 * - lookup:      可经接口/变量查询得到(如 ${var.xxx} / ${env.xxx}),表单只读展示
 * - generated:   运行时基于其他接口处理结果动态生成(如 Assign 时间戳),表单提示"由策略产出"
 *
 * 注意:没有 IOFieldBinding 的 schema-only 字段(PRD §5.4 Type C)压根不会出现在
 * fields[] 里,因此碰不到 source_kind。"隐藏 Type C 字段"属于平台侧渲染关注点,
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
 * IOFieldBinding —— 请求/响应 body 中单个字段的元信息。
 * 对齐 io_spec.py IOFieldBinding(extra="forbid")。
 */
export interface IOFieldBinding {
  name: string
  /** 归一化后的 JSONPath 形态($.xxx);与 name 末段一致。 */
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
 * RequestSpec 视图 —— 接口请求 body 的形态。
 *
 * 序列化后(@model_serializer 产生的)线上的键:
 * - body_type / fields:恒有
 * - model_schema / model_name:model 非 None 时才有(把 Pydantic model 类引用换成内嵌 JSON Schema)
 * - schema:schema_ 非 None 时才有(别名为 "schema")
 *
 * 注意:前端拿到的是序列化后的 dict,所以这里是 model_schema/schema 的扁平形式,
 * 而非 Pydantic 侧的 model/schema_ 类引用语义。需要原始 JSON Schema 时优先读
 * model_schema(派生自 model),否则读 schema。
 */
export interface RequestSpecView {
  body_type: BodyType
  fields: IOFieldBinding[]
  model_schema?: Record<string, unknown>
  model_name?: string
  schema?: Record<string, unknown>
}

/**
 * ResponseSpec 视图 —— 接口某状态码响应的形态。
 * 序列化键含义同 RequestSpecView,额外含 status / description / assertable_fields。
 */
export interface ResponseSpecView {
  status: number
  description: string
  fields: IOFieldBinding[]
  assertable_fields: string[]
  model_schema?: Record<string, unknown>
  model_name?: string
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
