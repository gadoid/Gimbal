/**
 * var-registry.ts — 变量全局化(#3):纯草稿推导的变量注册表与引用校验
 *
 * 变量的三个出身(全按全局作用域,第一版不做 step 级隔离):
 *   extract   — step.strategy 里 kind='extract' 的 target(产出者=该 step)
 *   config    — definition.config.vars 的 key(③ 配置步"共享变量")
 *   dataset   — 运行期数据集列(dispatcher layer 进 config.vars,编辑期未知)
 *
 * 消费点:${var.<name>} 出现在 headers value / body 字段值(深扫) /
 * 策略字段值(深扫)。本模块只做推导与判定,不做 IO;数据来源全部是
 * 草稿对象,后端零改动。
 */
import { parseTplRefs, type TplRef } from './tpl-refs'

// ── 注册表 ────────────────────────────────────────────────────────

/** 变量出身 */
export type VarOrigin = 'extract' | 'config'

export interface VarEntry {
  /** 变量名(extract target / config.vars key) */
  name: string
  origin: VarOrigin
  /** 产出者:extract = step 序号(1-based,展示用);config = null */
  stepIdx: number | null
  /** extract 的 JSONPath(config 出身为 null) */
  expression: string | null
}

export interface VarRegistry {
  /** 按注册顺序(= step 序)排列 */
  entries: VarEntry[]
  /** 快速查名 → entry(同名片后注册覆盖前,与运行期 vars layer 语义一致) */
  byName: Map<string, VarEntry>
}

/** 从草稿推导变量注册表。steps 顺序 = 执行顺序 = 注册顺序。 */
export function deriveVarRegistry(
  steps: { strategy?: { kind?: string; target?: string; expression?: string }[] }[],
  configVars: Record<string, unknown> | undefined,
): VarRegistry {
  const entries: VarEntry[] = []
  // config 先注册:同名 extract 覆盖它(row/extract 优先级更高,同
  // dispatcher _compose_scenario 的 layer 方向)
  for (const k of Object.keys(configVars || {})) {
    entries.push({ name: k, origin: 'config', stepIdx: null, expression: null })
  }
  steps.forEach((s, i) => {
    for (const st of s.strategy || []) {
      if (st.kind === 'extract' && st.target) {
        entries.push({
          name: st.target,
          origin: 'extract',
          stepIdx: i,
          expression: st.expression ?? null,
        })
      }
    }
  })
  const byName = new Map(entries.map((e) => [e.name, e]))
  return { entries, byName }
}

// ── 引用收集 ──────────────────────────────────────────────────────

/** 一处 ${var.*} 引用的结构化位置(定位用) */
export interface VarRefSite {
  ref: TplRef
  /** 消费者 step 序号(0-based) */
  stepIdx: number
  /** headers / body / strategy */
  where: 'headers' | 'body' | 'strategy'
  /** 细粒度定位:header key / 策略下标;body 为空串(body 深扫不给路径) */
  detail: string
}

/**
 * 深扫一个值里的 ${var.*} 引用(body/策略字段值可能是任意嵌套)。
 * 返回去重后的 TplRef 列表(同一变量在多处出现只报一次)。
 */
export function varRefsIn(value: unknown, out: Set<string> = new Set()): Set<string> {
  if (typeof value === 'string') {
    for (const r of parseTplRefs(value)) {
      if (r.domain === 'var' && r.alias) out.add(r.alias)
    }
  } else if (Array.isArray(value)) {
    value.forEach((v) => varRefsIn(v, out))
  } else if (value && typeof value === 'object') {
    Object.values(value).forEach((v) => varRefsIn(v, out))
  }
  return out
}

/** StepView 的最小结构签名(避免 import 类型带来的循环依赖) */
export interface StepLike {
  strategy?: { kind?: string; target?: string; expression?: string }[]
  api?: { headers?: Record<string, string> }
  request?: { body?: unknown }
}

/** 收集整个草稿全部 ${var.*} 引用(带位置) */
export function collectVarRefs(steps: StepLike[]): VarRefSite[] {
  const sites: VarRefSite[] = []
  steps.forEach((s, i) => {
    for (const [k, v] of Object.entries(s.api?.headers || {})) {
      for (const r of parseTplRefs(String(v))) {
        if (r.domain === 'var' && r.alias) sites.push({ ref: r, stepIdx: i, where: 'headers', detail: k })
      }
    }
    for (const name of varRefsIn(s.request?.body)) {
      sites.push({ ref: { raw: `\${var.${name}}`, domain: 'var', alias: name, field: null }, stepIdx: i, where: 'body', detail: '' })
    }
    (s.strategy || []).forEach((st, j) => {
      for (const name of varRefsIn(st)) {
        sites.push({
          ref: { raw: `\${var.${name}}`, domain: 'var', alias: name, field: null },
          stepIdx: i,
          where: 'strategy',
          detail: `strategy[${j}]`,
        })
      }
    })
  })
  return sites
}

// ── 校验 ──────────────────────────────────────────────────────────

export type VarIssueKind = 'dangling' | 'order' | 'missing_column'

export interface VarIssue {
  kind: VarIssueKind
  /** 引用的变量名 */
  name: string
  /** 消费处(step 序 0-based + 位置描述) */
  stepIdx: number
  where: 'headers' | 'body' | 'strategy'
  detail: string
  /** kind='order': 产出者 step 序;其它为 null */
  producerIdx: number | null
  message: string
}

/**
 * 三类引用校验:
 *
 * 1. dangling — 引用的变量名不在注册表(不含数据集列)。
 * 2. order — extract 产出被更早的 step 消费(时序冲突):headers/body
 *    在请求发出前求值,要求 producer < consumer;strategy 里 extract
 *    (after_request)可以引用本 step 产出的变量,要求 producer ≤
 *    consumer。
 * 3. missing_column — 引用既不在注册表,也不在所选数据集列并集
 *    (运行期 dispatcher 会把列 layer 进 vars;列名对不上就是解不出)。
 *
 * 注意:dangling 与 missing_column 是层级关系 — 先判注册表,落空再
 * 判数据集列;两边都落空报 missing_column(信息量更大:提示列名或
 * 变量名拼错)。纯校验,不 IO。
 */
export function checkVarRefs(
  steps: StepLike[],
  registry: VarRegistry,
  datasetColumns: string[],
): VarIssue[] {
  const dsCols = new Set(datasetColumns)
  const issues: VarIssue[] = []
  for (const site of collectVarRefs(steps)) {
    const name = site.ref.alias!
    const entry = registry.byName.get(name)
    if (entry && entry.origin === 'extract') {
      // 时序:extract 产出必须早于消费(headers/body 严格小于;
      // strategy 允许同 step —— 本 step 的 after_request extract
      // 产出可被本 step 后续策略消费)
      const producer = entry.stepIdx!
      const ok = site.where === 'strategy' ? producer <= site.stepIdx : producer < site.stepIdx
      if (!ok) {
        issues.push({
          kind: 'order',
          name, stepIdx: site.stepIdx, where: site.where, detail: site.detail,
          producerIdx: producer,
          message: `步骤 ${site.stepIdx + 1} 的 ${site.where} 引用 \${var.${name}},但它在步骤 ${producer + 1} 才产出`,
        })
      }
    } else if (!entry) {
      // 注册表落空 → 数据集列兜底
      if (dsCols.size && !dsCols.has(name)) {
        issues.push({
          kind: 'missing_column',
          name, stepIdx: site.stepIdx, where: site.where, detail: site.detail,
          producerIdx: null,
          message: `\${var.${name}} 不在共享变量/extract 中,也不是所选数据集的列`,
        })
      } else if (!dsCols.size) {
        // 没选数据集:只能报悬空(运行期 vars 只有注册表内容)
        issues.push({
          kind: 'dangling',
          name, stepIdx: site.stepIdx, where: site.where, detail: site.detail,
          producerIdx: null,
          message: `\${var.${name}} 未注册(共享变量/extract 均无此名,且未选数据集)`,
        })
      }
      // dsCols 命中:运行期由 dispatcher layer,合法,不报
    }
    // entry 是 config 出身:全局声明,任何位置可用,不校验
  }
  return issues
}

// ── 消费处统计(注册表面板展示用) ──────────────────────────────────

export interface VarUsage {
  name: string
  sites: VarRefSite[]
}

/** 每个注册变量的消费处列表(面板"消费处"列) */
export function varUsages(steps: StepLike[]): Map<string, VarUsage> {
  const out = new Map<string, VarUsage>()
  for (const site of collectVarRefs(steps)) {
    const name = site.ref.alias!
    if (!out.has(name)) out.set(name, { name, sites: [] })
    out.get(name)!.sites.push(site)
  }
  return out
}
