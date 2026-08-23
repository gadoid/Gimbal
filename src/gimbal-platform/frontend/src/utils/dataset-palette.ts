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

/** 场景 step 的最小形状(deriveBaselineColumns / fieldsOf 共用)。
 *  只声明我们实际读到的字段(view_hints.endpoint_id / request.body /
 *  api.{query,headers});其他字段不强类型 — 后端定义在 ScenarioSpec.ts。 */
export interface ScenarioStepShape {
  api?: { view_hints?: { endpoint_id?: string }; query?: unknown; headers?: unknown }
  request?: { body?: unknown }
}

/** 场景 definition 的最小投影 — 仅声明本模块要读的字段。
 *  真实定义见后端 ScenarioSpec / 前端 ScenarioDefinition,本模块只
 *  做列调色板推导,不依赖完整类型。 */
export interface ScenarioDefinitionShape {
  steps?: ScenarioStepShape[]
  config?: { vars?: Record<string, unknown> }
}

/** 取某 step 内某 source 的 fields dict;非对象(空 / 数组)返 null。
 *  导出给 DataSetEditor 共用 — 该逻辑在 promote / demote / setDirectBaseline /
 *  isPromotableVar / directBaselineValue 都重复过,集中后改一处生效。 */
export function fieldsOf(
  step: ScenarioStepShape | undefined | null,
  source: BaselineColumn['source'],
): Record<string, unknown> | null {
  // body 在 step.request 下,headers/query 在 step.api 下 — 两类容器用 union
  // 表示后索引会有歧义,所以分两路。
  const fields: unknown = source === 'body'
    ? (step?.request as { body?: unknown } | undefined)?.body
    : (step?.api as { query?: unknown; headers?: unknown } | undefined)?.[source]
  if (!fields || typeof fields !== 'object' || Array.isArray(fields)) return null
  return fields as Record<string, unknown>
}

/** 场景 definition → 行 0 列全集(变量列在前由调用方自行分组;此处保持步骤序) */
export function deriveBaselineColumns(definition: ScenarioDefinitionShape): BaselineColumn[] {
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
