/**
 * dataset-palette.ts — 数据集列调色板 / 行 0 投影(纯推导,spec §4)
 *
 * 与后端 endpoint_ref_index.parse_refs 同一 traversal 规则:
 * body 在 step.request 下,headers/query 在 step.api 下;无
 * view_hints.endpoint_id 的步骤不进投影。变量名正则同后端
 * ([A-Za-z0-9_.]+ — ③ 配置步的 <system>.key 命名空间键含点)。
 * 本模块零 IO,数据全部来自场景 definition。
 */

/** 行 0 / 列头的最小列描述 */
export interface BaselineColumn {
  stepIndex: number
  source: 'body' | 'headers' | 'query'
  field: string
  /** var = 步骤值含 ${var.NAME}(可被数据集列覆盖);direct = 直填 */
  kind: 'var' | 'direct'
  varName: string | null
  /** 行 0 展示值:var 列 = 模板按 vars 渲染;direct 列 = 字面值 */
  baseline: string
}

const VAR_RE = /\$\{var\.([A-Za-z0-9_.]+)\}/

/** 值中第一个 ${var.NAME};非字符串/无匹配为 null(与后端 via_var 语义一致) */
export function varNameOf(value: unknown): string | null {
  if (typeof value !== 'string') return null
  const m = VAR_RE.exec(value)
  return m ? m[1] : null
}

/** 展示用模板渲染:${var.NAME} 替换为 vars 默认值(缺省空串)。仅行 0 展示,不落库。 */
export function renderTemplate(value: string, vars: Record<string, unknown>): string {
  return value.replace(VAR_RE, (__, name: string) => {
    const v = vars[name]
    return v === undefined || v === null ? '' : String(v)
  })
}

function fieldsOf(step: any, source: BaselineColumn['source']): Record<string, unknown> | null {
  const container = source === 'body' ? step?.request : step?.api
  const fields = container?.[source]
  if (!fields || typeof fields !== 'object' || Array.isArray(fields)) return null
  return fields as Record<string, unknown>
}

/** 场景 definition → 行 0 列全集(变量列在前由调用方自行分组;此处保持步骤序) */
export function deriveBaselineColumns(definition: {
  steps?: any[]
  config?: { vars?: Record<string, unknown> }
}): BaselineColumn[] {
  const vars = definition.config?.vars ?? {}
  const out: BaselineColumn[] = []
  ;(definition.steps ?? []).forEach((step, stepIndex) => {
    if (!step?.api?.view_hints?.endpoint_id) return
    for (const source of ['body', 'headers', 'query'] as const) {
      const fields = fieldsOf(step, source)
      if (!fields) continue
      for (const [field, value] of Object.entries(fields)) {
        const varName = varNameOf(value)
        out.push({
          stepIndex, source, field,
          kind: varName ? 'var' : 'direct',
          varName,
          baseline: varName
            ? renderTemplate(String(value), vars)
            : value === null || value === undefined ? '' : String(value),
        })
      }
    }
  })
  return out
}

/** "从基线提取首行":每个变量列取行 0 渲染默认值,生成一条真实数据行。
 *  同一变量被多列引用时取**首个出现列**的基线:内嵌模板列的组合串
 *  (如 "p-100-s")不是变量默认值,不得覆盖整串模板列("100")。 */
export function rowFromBaseline(columns: BaselineColumn[]): Record<string, string> {
  const row: Record<string, string> = {}
  for (const c of columns) {
    if (c.kind === 'var' && c.varName && row[c.varName] === undefined) {
      row[c.varName] = c.baseline
    }
  }
  return row
}

/** 列调色板(后端 _scalar_vars 的前端镜像):vars 中值为标量的键。 */
export function scalarVarNames(vars: Record<string, unknown> | undefined): string[] {
  return Object.entries(vars ?? {})
    .filter(([, v]) => v === null || ['string', 'number', 'boolean'].includes(typeof v))
    .map(([k]) => k)
}
