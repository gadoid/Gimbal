/**
 * dataset-grid.ts — 数据集「变量即列」网格的派生工具(纯函数,零 IO)。
 *
 * 沿袭:旧栈 DataSetEditor 的转置网格工具(6c072bb8~1 的 dataset-grid.ts,
 * D1 2026-09-17 随独立路由退役);2026-11-12 按新列宇宙回迁 —— 列 =
 * config.vars 标量变量(与后端 `_scalar_vars` 同规则)+ `@slot.*` 账号列,
 * 不再是 endpoint 派生的 BaselineColumn。
 *
 * 两个关键事实(实现必须对齐,后端契约见 data_set_store._validate_rows /
 * run_prepare.compose_scenario):
 *   - 数据行是稀疏 dict:`undefined` ↔ 继承基线(config.vars 默认值);
 *     `""` ↔ 显式空串覆盖。UI 必须保留这两种状态的区别(override-empty 红条)。
 *   - 行值统一存字符串:运行期 coerce_row_value 按基线 bool/int/float 类型还原。
 */

import type { DataSetRow } from '@/types/scenario-composer'

/** 账号列前缀(M2b Q3;与后端 run_prepare.ROW_BINDING_PREFIX 同值) */
export const SLOT_PREFIX = '@slot.'

// ─── 列派生 ────────────────────────────────────────────────────

/** 网格列:一变量一列 + 账号列。 */
export interface GridColumn {
  /** var = 变量列;slot = 账号列 */
  kind: 'var' | 'slot'
  /** 显示名:var = 变量名;slot = 槽名 */
  name: string
  /** 行键:var = 变量名;slot = `@slot.<槽名>` */
  key: string
  /** 基线值(var 列 = config.vars 默认;slot 列 = undefined) */
  baseline: unknown
  /** 变量被场景 var_locks 锁定且本数据集未放开 → 列默认隐藏 */
  locked: boolean
}

/** 标量判定:与后端 `_scalar_vars` 同规则 —— 结构化声明(如 {"kind":"seq"})
 *  不入列,行覆盖会破坏引擎生成器语义。 */
export function isScalar(v: unknown): boolean {
  return v === null || typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean'
}

/**
 * 列宇宙:标量变量按声明序 + 行内现存账号列(首见序)。
 * `locked = 变量 ∈ varLocks ∧ ∉ varUnlocks`(数据集级本地放开,
 * var-lock spec §3.2);账号列永不锁。
 */
export function deriveVarColumns(
  configVars: Record<string, unknown> | null | undefined,
  rows: Array<Record<string, unknown>>,
  varLocks: readonly string[] = [],
  varUnlocks: readonly string[] = [],
): GridColumn[] {
  const vars = configVars ?? {}
  const locks = new Set(varLocks)
  const unlocks = new Set(varUnlocks)
  const cols: GridColumn[] = []
  for (const [name, v] of Object.entries(vars)) {
    if (!isScalar(v)) continue
    cols.push({
      kind: 'var', name, key: name, baseline: v,
      locked: locks.has(name) && !unlocks.has(name),
    })
  }
  const seen = new Set(cols.map((c) => c.key))
  for (const row of rows) {
    for (const k of Object.keys(row ?? {})) {
      if (!k.startsWith(SLOT_PREFIX) || k.length <= SLOT_PREFIX.length) continue
      if (seen.has(k)) continue
      seen.add(k)
      cols.push({ kind: 'slot', name: k.slice(SLOT_PREFIX.length), key: k, baseline: undefined, locked: false })
    }
  }
  return cols
}

// ─── cell 三态 ─────────────────────────────────────────────────

export type CellState = 'inherit' | 'override-empty' | 'override-value'

export interface CellDisplay {
  value: string
  state: CellState
  /** state=inherit 时的占位文本(基线标量值的字符串;结构化/无基线 = '') */
  placeholder: string
}

/** 基线的单元格可读文本:标量 → 字符串;结构化 → null(UI 显芯片);
 *  undefined(账号列无基线)→ null。 */
export function baselineText(baseline: unknown): string | null {
  if (baseline === undefined || !isScalar(baseline)) return null
  return baseline === null ? '' : String(baseline)
}

/** 给一行 × 一列:返回当前显示值与三态。
 *  不在 row[key] 时返回 `''` 会丢语义 —— 状态必须由 state 表达。 */
export function cellDisplay(row: Record<string, unknown>, col: GridColumn): CellDisplay {
  const ph = baselineText(col.baseline) ?? ''
  const raw = row[col.key]
  if (raw === undefined) return { value: '', state: 'inherit', placeholder: ph }
  const s = raw === null ? '' : String(raw)
  if (s === '') return { value: '', state: 'override-empty', placeholder: ph }
  return { value: s, state: 'override-value', placeholder: ph }
}

// ─── 摘要统计 / 失效键 ─────────────────────────────────────────

export interface GridStats {
  varCount: number
  rowCount: number
  /** 显式覆写格数(inherit 之外) */
  overrideCount: number
}

/** 顶栏「变量 X · 数据 N 行 · 覆写 M 格」。防御性:只数列宇宙里的键,
 *  行里混进的意外键不算覆写(后端 `_validate_rows` 也不会放行)。 */
export function gridStats(
  columns: GridColumn[],
  rows: Array<Record<string, unknown>>,
): GridStats {
  const keys = new Set(columns.map((c) => c.key))
  let overrideCount = 0
  for (const row of rows) {
    for (const k of Object.keys(row ?? {})) {
      if (keys.has(k)) overrideCount++
    }
  }
  return {
    varCount: columns.filter((c) => c.kind === 'var').length,
    rowCount: rows.length,
    overrideCount,
  }
}

/**
 * 失效键:行键 ∉ 列宇宙。典型成因 = 变量已删/改名未走适配;这些键运行期
 * 合入 vars 无效果(不在调色板的键 compose_scenario 照写,引擎不消费)。
 * `__` 前缀豁免 —— `__rowKey` 是服务端敏感列并回键(authz 评审),不是数据。
 */
export function deadKeysOf(
  columns: GridColumn[],
  rows: Array<Record<string, unknown>>,
): string[] {
  const known = new Set(columns.map((c) => c.key))
  const out: string[] = []
  for (const row of rows) {
    for (const k of Object.keys(row ?? {})) {
      if (k.startsWith('__') || known.has(k) || out.includes(k)) continue
      out.push(k)
    }
  }
  return out
}

/** 移除失效键(不可变;`__` 前缀键保留)。 */
export function stripDeadKeys(
  rows: Array<Record<string, unknown>>,
  dead: readonly string[],
): Array<Record<string, unknown>> {
  const deadSet = new Set(dead)
  return rows.map((row) => {
    const next: Record<string, unknown> = {}
    for (const [k, v] of Object.entries(row ?? {})) {
      if (!deadSet.has(k)) next[k] = v
    }
    return next
  })
}

// ─── TSV 粘贴(网格内,从起始格向右下铺)───────────────────────

export interface PastePlan {
  /** 起始数据行索引 */
  startIdx: number
  /** 起始列起的行键序列(矩形块按序映射;溢出丢弃) */
  colKeys: string[]
  /** 每项是一个 行键 → 值 的覆盖 dict */
  cells: Array<Record<string, string>>
  /** 超出当前行数、需要追加的行数 */
  needsAppend: number
}

/**
 * 解析剪贴板文本:行 `\n`,列 `\t`。不 filter 空行 —— 粘贴 "" 也是一次
 * 显式空覆盖;只去掉末尾单个 trailing 空行(按 Enter 留下的)。
 * 单列(各行都无 tab)→ 纵向填充到 colKeys[0];
 * 矩形块 → 首列落 colKeys[0],其余列按 colKeys 序右铺,超宽丢弃。
 */
export function parseTsvPaste(
  text: string,
  colKeys: readonly string[],
  startIdx: number,
  currentRowCount: number,
): PastePlan {
  const plan: PastePlan = { startIdx, colKeys: [...colKeys], cells: [], needsAppend: 0 }
  if (!colKeys.length) return plan
  let lines = text.replace(/\r\n?/g, '\n').split('\n')
  if (lines.length && lines[lines.length - 1] === '') lines.pop()
  if (!lines.length) return plan
  const rows2d = lines.map((l) => l.split('\t'))
  plan.cells = rows2d.map((r) => {
    const cell: Record<string, string> = {}
    colKeys.forEach((k, j) => { const v = r[j]; if (v !== undefined) cell[k] = v })
    return cell
  })
  plan.needsAppend = Math.max(0, startIdx + plan.cells.length - currentRowCount)
  return plan
}

/** 把 PastePlan 落到 rows 上(不可变拷贝;不足的行补稀疏 `{}`)。 */
export function applyPastePlan(
  rows: Array<Record<string, unknown>>,
  plan: PastePlan,
): Array<Record<string, unknown>> {
  const out = rows.map((r) => ({ ...r }))
  plan.cells.forEach((cell, i) => {
    const idx = plan.startIdx + i
    while (out.length <= idx) out.push({})
    Object.assign(out[idx], cell)
  })
  return out
}

// ─── 账号列候选(注入槽静态近似)───────────────────────────────

const SLOT_REF_RE = /\$\{slot\.([A-Za-z0-9_-]+)\./g
const AUTH_REF_RE = /\$\{auth\.([A-Za-z0-9_-]+)[.}]/g

/**
 * 注入槽名清单(保存期静态近似,与后端 `_injection_slots` 同源同位):
 * 深扫 steps + config 里 `${slot.<名>.` 与 `${auth.<名>.` 两族引用。
 * 后端写侧校验用的是「派发注入清单 ∪ 静态近似」(DB 集更宽),此处仅供
 * 下拉候选;手打槽名交给后端 422 兜底。
 */
export function injectionSlotNames(steps: unknown, config: unknown): string[] {
  const out: string[] = []
  const scan = (v: unknown) => {
    if (typeof v === 'string') {
      for (const m of v.matchAll(SLOT_REF_RE)) {
        if (!out.includes(m[1])) out.push(m[1])
      }
      for (const m of v.matchAll(AUTH_REF_RE)) {
        if (!out.includes(m[1])) out.push(m[1])
      }
    } else if (Array.isArray(v)) {
      v.forEach(scan)
    } else if (v && typeof v === 'object') {
      for (const val of Object.values(v as Record<string, unknown>)) scan(val)
    }
  }
  scan(steps)
  scan(config)
  return out
}

// ─── 导出列序 ──────────────────────────────────────────────────

/**
 * CSV 导出的列序:列宇宙序在前(变量声明序 + 账号列),行内其余键
 * (失效键)按首见序缀后;`__` 前缀键(服务端并回键)不出导出。
 */
export function exportColumnOrder(
  columns: GridColumn[],
  rows: Array<Record<string, unknown>>,
): string[] {
  const out = columns.map((c) => c.key)
  for (const row of rows) {
    for (const k of Object.keys(row ?? {})) {
      if (k.startsWith('__') || out.includes(k)) continue
      out.push(k)
    }
  }
  return out
}

/** 网格行的类型收窄(DataSetRow = 标量值行;wire 层再放宽)。 */
export type GridRow = DataSetRow
