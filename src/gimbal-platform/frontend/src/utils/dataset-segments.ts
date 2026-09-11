/**
 * dataset-segments — 数据集编辑器段派生扫描器(spec §4.1/§6.2,纯函数零 IO)。
 *
 * 打开编辑器时对场景做一次引用扫描:
 *   输入列 = step 的 request body/headers 里 ${var.x} 引用(深扫,数组带 [i]);
 *   期望列 = step.strategy 中 kind=assertion 且 expected 含 ${var.x}(带
 *   target/operator/strategyIdx,供列头徽标与跳转);
 *   段 = 有列的步骤;共享 = 跨段同名 var;列宇宙 = config.vars(裁定 A,
 *   baseline 从 vars 取值,编辑器只消费不声明)。
 * 与 dataset-palette 的 deriveBaselineColumns(traversal 有 endpoint_id 纪律,
 * 服务直填列基线显示)互不依赖:引用扫描与端点契约无关,不设 endpoint_id 门。
 */
export const TPL_RE = /\$\{var\.([A-Za-z0-9_.]+)\}/g
export const TPL_FULL_RE = /^\$\{var\.([A-Za-z0-9_.]+)\}$/

export interface InputColumn {
  stepIndex: number
  source: 'body' | 'headers'
  /** 引用所在字段路径(body 深路径点连;headers 键) */
  field: string
  varName: string
  /** config.vars[varName](未声明 = undefined → 行 placeholder 空) */
  baseline: unknown
}

export interface ExpectColumn {
  varName: string
  target: string
  operator: string
  /** 断言在 step.strategy 数组的下标(跳转 #strategy-card-N 用) */
  strategyIdx: number
  stepIndex: number
  /** config.vars[varName](与 InputColumn.baseline 同语义) */
  baseline: unknown
}

export interface SegmentStepShape {
  request?: { body?: unknown } | null
  api?: { headers?: Record<string, unknown> | null } | null
  strategy?: unknown[]
}

export interface Segment {
  stepIndex: number
  inputs: InputColumn[]
  expects: ExpectColumn[]
}

/** 段网格可编辑列(输入/期望统一:行键 = varName,单一 join key spec §4) */
export interface GridVarColumn {
  varName: string
  baseline: unknown
  stepIndex: number
  source: 'body' | 'headers' | 'expect'
  field: string
  expect?: { target: string; operator: string; strategyIdx: number }
}

function scanValue(
  v: unknown, source: 'body' | 'headers', path: string,
  stepIndex: number, out: (c: InputColumn) => void, vars: Record<string, unknown>,
): void {
  if (typeof v === 'string') {
    for (const m of v.matchAll(TPL_RE)) {
      out({ stepIndex, source, field: path || '(root)', varName: m[1], baseline: vars[m[1]] })
    }
  } else if (Array.isArray(v)) {
    v.forEach((item, i) => scanValue(item, source, `${path}[${i}]`, stepIndex, out, vars))
  } else if (v && typeof v === 'object') {
    for (const [k, child] of Object.entries(v)) {
      scanValue(child, source, path ? `${path}.${k}` : k, stepIndex, out, vars)
    }
  }
}

export function deriveSegments(
  steps: SegmentStepShape[] | null | undefined,
  vars: Record<string, unknown> | null | undefined,
): Segment[] {
  const v = vars ?? {}
  const out: Segment[] = []
  ;(steps ?? []).forEach((step, stepIndex) => {
    const inputs: InputColumn[] = []
    const seen = new Set<string>()
    const push = (c: InputColumn) => {
      if (!seen.has(c.varName)) { seen.add(c.varName); inputs.push(c) }   // 同步去重(首引用位)
    }
    scanValue(step?.request?.body, 'body', '', stepIndex, push, v)
    const headers = step?.api?.headers
    if (headers && typeof headers === 'object') {
      for (const [k, val] of Object.entries(headers)) {
        if (typeof val === 'string') {
          for (const m of val.matchAll(TPL_RE)) {
            push({ stepIndex, source: 'headers', field: k, varName: m[1], baseline: v[m[1]] })
          }
        }
      }
    }
    const expects: ExpectColumn[] = []
    ;(step?.strategy ?? []).forEach((s, strategyIdx) => {
      const st = s as { kind?: string; expected?: unknown; target?: unknown; operator?: unknown }
      if (st?.kind !== 'assertion' || typeof st.expected !== 'string') return
      for (const m of st.expected.matchAll(TPL_RE)) {
        expects.push({
          varName: m[1], target: String(st.target ?? ''), operator: String(st.operator ?? ''),
          strategyIdx, stepIndex, baseline: v[m[1]],
        })
      }
    })
    if (inputs.length || expects.length) out.push({ stepIndex, inputs, expects })
  })
  return out
}

/** 段内可编辑列:输入列在前、期望列在后(行读取顺序 = 段内并排 spec §4.3) */
export function gridColumnsOf(seg: Segment): GridVarColumn[] {
  return [
    ...seg.inputs.map((c) => ({ varName: c.varName, baseline: c.baseline, stepIndex: c.stepIndex, source: c.source, field: c.field })),
    ...seg.expects.map((c) => ({
      varName: c.varName, baseline: c.baseline, stepIndex: c.stepIndex,
      source: 'expect' as const, field: c.target,
      expect: { target: c.target, operator: c.operator, strategyIdx: c.strategyIdx },
    })),
  ]
}

/** 共享 var:跨段引用同名(段内多字段引用同一 var 不算共享,列头首引用位代表) */
export function sharedVarNames(segments: Segment[]): Set<string> {
  const seen = new Map<string, number>()
  for (const seg of segments) {
    const names = new Set<string>([
      ...seg.inputs.map((c) => c.varName),
      ...seg.expects.map((c) => c.varName),
    ])
    for (const n of names) seen.set(n, (seen.get(n) ?? 0) + 1)
  }
  return new Set([...seen.entries()].filter(([, n]) => n > 1).map(([k]) => k))
}

/** 死行键:行键 ∉ config.vars 列宇宙(spec §7 软提示,不硬门禁) */
export function deadRowKeys(
  vars: Record<string, unknown> | null | undefined,
  rows: Array<Record<string, unknown>>,
): string[] {
  const universe = new Set(Object.keys(vars ?? {}))
  const dead = new Set<string>()
  for (const row of rows) for (const k of Object.keys(row)) if (!universe.has(k)) dead.add(k)
  return [...dead]
}

/** 期望命名:exp_ + target 末段(spec §5.2;撞名由调用方对话框处理,不静默 _2)。
 *  末段分隔 = `.[]` 结构符 + `_`(spec 例:$.response_status → exp_status)+
 *  引号(bracket 成员语法 ['weird key'] → weird key → exp_weird_key)。 */
export function expectVarNameOf(target: string): string {
  const segs = target.split(/[._[\]'"]+/).filter(Boolean)
  const last = segs.length ? segs[segs.length - 1] : 'value'
  return `exp_${last.replace(/[^A-Za-z0-9_]/g, '_')}`
}
