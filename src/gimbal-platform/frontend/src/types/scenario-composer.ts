/**
 * types/scenario-composer.ts — 场景编排的平台容器类型
 *
 * 编排结构统一为容器对象(用户 2026-08-13 拍板):
 * - definition: plate 完整结构(ScenarioView),描述"变化的被测系统",原样透传 plate /convert
 * - orchestration: 平台渲染/编排辅助字段,与 definition 易分离
 * - caseMeta: 平台 case 层运行覆盖
 *
 * Plate 是结构权威源;平台不重新描述被测系统,只附加展示/编排元数据。
 * plate 改字段(只要渲染字段还在)前端渲染逻辑不变即可扩展。
 *
 * plate 对外契约类型(ScenarioView/StepView/IOFieldBinding 等)在 @/types/plate。
 */
import type { ScenarioView } from '@/types/plate'

// ─── 复用:Plate 的 AuthSession 形状(简化)─────────────────────────
export interface AuthSessionRef {
  name: string
  type: 'bearer' | 'cookie' | 'oauth2' | 'apikey'
  ref?: string
}

// ─── 系统 / 模块 ──────────────────────────────────────────────────
export type SystemTag = 'fin' | 'logi' | 'wms' | 'mall' | 'common' | string

// ─── 平台编排辅助(与 definition.steps index 对齐)──────────────────
export interface StepOrchestration {
  /** 步骤启用开关(平台编排态;plate Step 无此字段) */
  enabled: boolean
  /** 平台展示名(plate Step 只有 description) */
  name: string
}

export interface Orchestration {
  /** 与 definition.steps 严格同序同长,index 对齐 */
  steps: StepOrchestration[]
  /** resource 的说明文字(plate Resource 基类只有 name),按 name 对齐 */
  resourceMeta: Record<string, string>
}

// ─── 平台 case 层运行覆盖 ──────────────────────────────────────────
export interface CaseOverride {
  env: string
  auth: AuthSessionRef
  dataSetIds: string[]
}

// ─── 平台草稿容器 ──────────────────────────────────────────────────
export interface ScenarioDraft {
  /** plate 完整结构,核心属性,原样透传 plate /convert */
  definition: ScenarioView
  /** 平台渲染/编排辅助字段,易分离,不发给 plate */
  orchestration: Orchestration
  caseMeta?: CaseOverride
}

// ─── 读侧(列表/详情,非草稿)──────────────────────────────────────
// 读侧 step 直接透传 plate 的 step dict,不做表单化建模。
export interface Scenario {
  meta: {
    scenarioId: string
    name: string
    description: string
    module: string
    priority: number
    author: string
    owner: string
    tags: string[]
    system: SystemTag[]
    version?: string
    expire?: boolean
    createTime?: string
    /** 最后编辑时间（编排态透传；“最后编辑”列已在使用） */
    updateTime?: string
  }
  /** plate step dicts (读侧透传) */
  steps: Record<string, unknown>[]
  /** 读侧可能附带 plate 的 config/resource(透传,非表单化) */
  config?: Record<string, unknown>
  resource?: Record<string, unknown>
  /** 平台编排态(平台渲染字段),round-trip 用于 composer reload;缺省时前端回退默认 */
  orchestration?: Orchestration
  caseCount: number
  dataSetCount: number
  stepCount: number
  tags: string[]
  starred?: boolean
  /** P1 读侧收紧:'private' 仅 owner/admin 可读;'public' 全员可读 */
  visibility?: 'private' | 'public'
}

// ─── 用例(case)/ 数据集 / 执行环境(与编排无关,保持原样)─────────────
export interface Case {
  caseId: string
  scenarioId: string
  name: string
  description?: string
  env: string
  auth: AuthSessionRef
  retry?: { maxAttempts: number; intervalMs: number }
  dataSetIds: string[]
  lastRunStatus?: 'PASS' | 'FAIL' | 'SKIP'
  lastRunAt?: string
  createdBy: string
  updatedAt: string
}

export interface DataSetRow { [field: string]: string | number | boolean }

export interface DataSet {
  datasetId: string
  caseId: string
  name: string
  description?: string
  rowCount: number
  rows: DataSetRow[]
  lastRunStatus?: 'PASS' | 'FAIL' | 'SKIP'
  lastRunAt?: string
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

export interface DataSetDraft {
  name: string
  description?: string
  rows: DataSetRow[]
}

export interface RunEnv {
  envId: string
  name: string
  baseUrl: string
}
