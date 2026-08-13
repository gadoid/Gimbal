/**
 * types/scenario-composer.ts — 场景编排 V3 的领域模型
 *
 * 与 gimbal-plate/schema/scenario.py (V3.2) 字段对齐：
 * - meta.system: list[str]        (多系统 + common)
 * - steps / config / resource / meta 维持现有结构
 *
 * Platform 侧只做"组装 + 存储",真正的结构定义仍在 Plate 侧；
 * 这里只为前端表单、表格、对话框提供形状声明。
 *
 * 注意:与 plate endpoint 契约相关的类型(IOFieldBinding 等)已收敛到
 * @/types/plate,本文件复用,不再重复声明。
 */

import type { IOFieldBinding } from '@/types/plate'

// ─── 复用：复用 Plate 的 AuthSession 形状(简化)─────────────────────
export interface AuthSessionRef {
  name: string
  type: 'bearer' | 'cookie' | 'oauth2' | 'apikey'
  ref?: string
}

// ─── 系统 / 模块 ──────────────────────────────────────────────────
export type SystemTag = 'fin' | 'logi' | 'wms' | 'mall' | 'common' | string

// ─── 场景元信息 ──────────────────────────────────────────────────
export interface ScenarioMeta {
  scenarioId: string           // 'sc-order-create'
  name: string
  description: string
  module: string
  priority: 0 | 1 | 2 | 3
  author: string
  owner: string
  tags: string[]
  system: SystemTag[]          // V3.2: list[str]
  version?: string
  expire?: boolean
}

// ─── 场景步骤 ────────────────────────────────────────────────────
export type StepKind = 'http' | 'rpc' | 'sql' | 'script' | 'wait' | 'extract'

/**
 * Reference to the endpoint this step invokes (V3 IOFieldBinding-driven).
 *
 * 注意:endpointRef 的归属(嵌在 step 里随 scenario 存储与转换)后续会单独
 * 重新设计 —— 当前默认"所有定义都是完整结构,而非引用结构"的前提下,本字段
 * 暂作渲染输入保留。本次重构不改动它的归属,只把 bindings 复用 plate 契约类型。
 */
export interface EndpointRef {
  /** Plate endpoint id, e.g. "fin.order_entrust.order_add" */
  endpointId: string
  /** Resolved at design time from Plate /api/endpoint/{id}/full */
  bindings: IOFieldBinding[]
  /** Body fields that exist in the schema but have no IOFieldBinding
   *  (Type C per PRD §5.4) — these are NOT shown in the form editor
   *  but are carried through at runtime.
   *  注意:目前恒为 {}(未实现派生)。正确的派生应为
   *  (schema keys) − (bindings 已绑 keys)。后续 ref 设计时处理。*/
  hiddenFields: Record<string, any>
}

export interface ScenarioStep {
  id: string
  name: string
  kind: StepKind
  service?: string
  endpoint?: string
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH'
  headers?: Record<string, string>
  body?: any
  expectStatus?: number | number[]
  extractBindings?: Array<{ name: string; path: string }>
  dependsOn?: string[]
  enabled: boolean
  /** V3: link to the source endpoint so the form editor knows which
   *  fields to render and the dispatch can build a schema-conformant body. */
  endpointRef?: EndpointRef
}

// ─── 用例（case）───────────────────────────────────────────────
export interface Case {
  caseId: string
  scenarioId: string                   // 1:1 绑定
  name: string
  description?: string
  // 用例层覆盖 (相对于 scenario)
  env: string
  auth: AuthSessionRef
  retry?: { maxAttempts: number; intervalMs: number }
  dataSetIds: string[]                 // 1:N 数据集
  lastRunStatus?: 'PASS' | 'FAIL' | 'SKIP'
  lastRunAt?: string
  createdBy: string
  updatedAt: string
}

// ─── 数据集 ─────────────────────────────────────────────────────
export interface DataSetRow {
  [field: string]: string | number | boolean
}

export interface DataSet {
  datasetId: string
  caseId: string                       // 隶属 case
  name: string
  description?: string
  rowCount: number
  rows: DataSetRow[]                   // 行级数据
  lastRunStatus?: 'PASS' | 'FAIL' | 'SKIP'
  lastRunAt?: string
}

// ─── 执行环境 ────────────────────────────────────────────────────
export interface RunEnv {
  envId: string
  name: string
  baseUrl: string
}

// ─── API 列表（汇总）────────────────────────────────────────────
export interface Scenario {
  meta: ScenarioMeta
  steps: ScenarioStep[]
  caseCount: number
  dataSetCount: number
  stepCount: number
  tags: string[]
  starred?: boolean
}

export interface DataSetSummary {
  datasetId: string
  caseId: string
  caseName: string
  name: string
  rowCount: number
  lastRunStatus?: 'PASS' | 'FAIL' | 'SKIP'
  lastRunAt?: string
  preview: DataSetRow[]
}

// ─── 表单草稿 ───────────────────────────────────────────────────
export interface ScenarioConfig {
  timePolicyKind?: 'record' | 'cost-collect' | 'timeout-check'
  retryMaxAttempts?: number
  retryIntervalMs?: number
  vars?: Array<{ key: string; value: unknown; spec?: string }>
  services?: Record<string, string>
  users?: Record<string, Record<string, unknown>>
  setup?: Array<Record<string, unknown>>
  teardown?: Array<Record<string, unknown>>
}

export interface ScenarioResource {
  items?: Array<{
    kind: 'mock' | 'file' | 'http' | 'custom'
    name: string
    description?: string
    payload?: Record<string, unknown>
  }>
}

export interface ScenarioDraft {
  meta: ScenarioMeta
  steps: ScenarioStep[]
  config?: ScenarioConfig
  resource?: ScenarioResource
  caseMeta?: Pick<Case, 'env' | 'auth' | 'dataSetIds'>
}

export interface DataSetDraft {
  name: string
  description?: string
  rows: DataSetRow[]
}
