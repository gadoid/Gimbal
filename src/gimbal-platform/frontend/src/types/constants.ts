/**
 * constants.ts — 常量池前端类型(条目 + plate generators dim 目录)。
 * plate 输出 dict,前端在此建模(边界原则同 plate.ts)。
 */

/** 常量池条目(后端 ConstantEntryOut 镜像)。literal 行 value 有值/spec=null;generator 行相反。 */
export interface ConstantEntry {
  id: number
  name: string
  description: string
  entry_kind: 'literal' | 'generator'
  value: unknown
  spec: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export interface ConstantEntryCreateIn {
  name: string
  description?: string
  entry_kind: 'literal' | 'generator'
  value?: unknown
  spec?: Record<string, unknown> | null
}

export interface ConstantEntryPatchIn {
  description?: string
  value?: unknown
  spec?: Record<string, unknown> | null
}

/** generators dim light view(kind 下拉用)。 */
export interface GeneratorKindView {
  kind: string
  summary: string
}

/** generators dim full view 的参数描述符(动态表单驱动)。 */
export interface GeneratorParamDesc {
  name: string
  type: 'string' | 'integer' | 'number' | 'boolean'
  required: boolean
  default: unknown
  enum: unknown[] | null
  min: number | null
  max: number | null
  description: string
}

/** generators dim full view(文档卡片 + 动态表单契约)。 */
export interface GeneratorKindDetailView {
  kind: string
  summary: string
  description: string
  params: GeneratorParamDesc[]
  example: Record<string, unknown>
}
