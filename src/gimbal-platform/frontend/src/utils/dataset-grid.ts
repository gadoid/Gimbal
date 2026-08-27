/**
 * dataset-grid.ts — 转置表格 + 折叠基线视图所需的派生工具(纯函数,零 IO)
 *
 * 输入:`deriveBaselineColumns()` 输出的 `BaselineColumn[]`(已存在
 * dataset-palette.ts)和当前 `rows[]`。只做投影 / 状态推导,不做保存。
 *
 * 三个关键事实(实现必须对齐):
 *   - 数据行是稀疏 dict;`undefined` ↔ 继承基线;`""` ↔ 显式空串覆盖。
 *     UI 必须保留这两种状态的区别(`override-empty` 红条)。
 *   - 后端 `_validate_rows` 只校验键 ⊆ palette,值任意 → cell 统一字符串。
 *   - `promote()` 是本地草稿 mutate,基线 PUT 走 `updateScenario`。
 */

import type { BaselineColumn } from './dataset-palette'

// ─── palette 派生 ──────────────────────────────────────────────

/** 变量列(转置表只显示这些;直填列不进入数据表格)。
 *  返回类型收紧:kind='var' 且 varName 非空,调用方不再需要 `!` 非空断言。 */
export type VarColumn = BaselineColumn & { kind: 'var'; varName: string }

export function varOnlyPalette(columns: BaselineColumn[]): VarColumn[] {
  return columns.filter((c): c is VarColumn => c.kind === 'var' && !!c.varName)
}

/** 基线树形分组(按步骤 → 位置 → 字段);折叠区用。 */
export interface BaselineGroup {
  stepIndex: number
  source: BaselineColumn['source']
  fields: BaselineColumn[]
}

export function groupByStepLocation(columns: BaselineColumn[]): BaselineGroup[] {
  const map = new Map<string, BaselineGroup>()
  for (const c of columns) {
    const key = `${c.stepIndex}:${c.source}`
    let g = map.get(key)
    if (!g) {
      g = { stepIndex: c.stepIndex, source: c.source, fields: [] }
      map.set(key, g)
    }
    g.fields.push(c)
  }
  return [...map.values()].sort((a, b) => {
    if (a.stepIndex !== b.stepIndex) return a.stepIndex - b.stepIndex
    return a.source.localeCompare(b.source)
  })
}

/** 模糊匹配:不区分大小写,字段名 / varName 任一命中即可。空 query = 全显。 */
export function matchesQuery(c: BaselineColumn, q: string): boolean {
  const needle = q.trim().toLowerCase()
  if (!needle) return true
  return c.field.toLowerCase().includes(needle)
    || (c.varName?.toLowerCase().includes(needle) ?? false)
}

// ─── cell 状态 ────────────────────────────────────────────────

export type CellState = 'inherit' | 'override-empty' | 'override-value'

export interface CellDisplay {
  value: string
  state: CellState
  /** state=inherit 时显示的占位文本(基线值)。 */
  placeholder: string
}

/** 给一行 × 一列:返回当前显示值与三态。
 *  重要:不在 row[col.varName] 是 undefined 时返回 `''` — 那会丢语义。 */
export function cellDisplay(
  row: Record<string, unknown>,
  col: BaselineColumn,
): CellDisplay {
  const raw = col.varName ? row[col.varName] : undefined
  if (raw === undefined) {
    return { value: '', state: 'inherit', placeholder: col.baseline }
  }
  const s = raw === null ? '' : String(raw)
  if (s === '') {
    return { value: '', state: 'override-empty', placeholder: col.baseline }
  }
  return { value: s, state: 'override-value', placeholder: col.baseline }
}

// ─── 摘要统计 ─────────────────────────────────────────────────

export interface GridStats {
  varCount: number     // 变量列数
  directCount: number  // 直填列数
  rowCount: number     // 数据条数
  overrideCount: number // 显式覆盖的单元格数(inherit 之外的)
}

/** 顶栏「变量 X / 直填 Y · 数据 N · 覆盖 M 格」用。 */
export function gridStats(
  columns: BaselineColumn[],
  rows: Array<Record<string, unknown>>,
): GridStats {
  const varColumns = varOnlyPalette(columns)
  const varCount = varColumns.length
  const directCount = columns.length - varCount
  // 防御性:只数 palette 里的 varName(后端 _validate_rows 也只允许这些键)。
  // 万一 row 里混进意外键,不被算成 override,避免顶栏数字被污染。
  const varNames = new Set(varColumns.map((v) => v.varName))
  let overrideCount = 0
  for (const row of rows) {
    for (const k of Object.keys(row)) {
      if (varNames.has(k)) overrideCount++
    }
  }
  return { varCount, directCount, rowCount: rows.length, overrideCount }
}

// ─── TSV 粘贴 ─────────────────────────────────────────────────

export interface PastePlan {
  /** 起始数据行索引(粘贴到 row[startIdx] 起)。 */
  startIdx: number
  /** 起始列 varName;null = 单列(横向无意义,纵向填充)。 */
  startVar: string | null
  /** 解析出的二维数据(每项是一个 varName → value 的覆盖 dict)。 */
  cells: Array<Record<string, string>>
  /** 是否需要新增行(超出当前 rows 长度)。 */
  needsAppend: number
}

/** 解析 clipboard 文本:行 `\n`,列 `\t`。
 *  - 第一行首列可能带 var 名(从 header 拷贝的情况),识别规则:
 *    若首格等于目标列的 varName 则丢弃;否则视为数据格。
 *  - 单列纵向填充:rows.length 行,每行一个值,落到 `startVar` 列。
 *  - 矩形块:多列 × 多行,要求首行至少两个 tab 分隔。
 *  - 空字符串视作显式空覆盖;不写 "undefined"。 */
export function parseTsvPaste(
  text: string,
  startVar: string,
  startIdx: number,
  currentRowCount: number,
): PastePlan {
  // 标准化换行。注意:不要 filter 空行 — 粘贴 "" 也算一次空覆盖。
  // 只去掉单个 trailing 空行(用户在文本末尾按了 Enter 留下的)。
  let lines = text.replace(/\r\n?/g, '\n').split('\n')
  if (lines.length && lines[lines.length - 1] === '') lines.pop()
  if (lines.length === 0) {
    return { startIdx, startVar, cells: [], needsAppend: 0 }
  }
  // 每行 split;不切出空尾部
  const rows2d = lines.map((l) => l.split('\t'))

  // 单列(纵向填充):每行 1 个 tab 分隔
  if (rows2d.every((r) => r.length === 1)) {
    const cells = rows2d.map(([v]) => ({ [startVar]: v ?? '' }))
    const needed = startIdx + cells.length
    return {
      startIdx,
      startVar,
      cells,
      needsAppend: Math.max(0, needed - currentRowCount),
    }
  }

  // 矩形块:第 1 列落到 startVar;其余列丢弃(当前未实现多列映射)。
  // —— 多列粘贴场景下次需要时再补。
  const firstCol = rows2d.map((r) => r[0] ?? '')
  const cells = firstCol.map((v) => ({ [startVar]: v }))
  const needed = startIdx + cells.length
  return {
    startIdx,
    startVar,
    cells,
    needsAppend: Math.max(0, needed - currentRowCount),
  }
}

/** 把 PastePlan 落到 rows 数组上,返回新 rows;不处理 needsAppend(由调用方决定)。 */
export function applyPastePlan(
  rows: Array<Record<string, unknown>>,
  plan: PastePlan,
): Array<Record<string, unknown>> {
  const out = rows.map((r) => ({ ...r }))
  // 确保 rows 够长
  while (out.length < plan.startIdx) out.push({})
  plan.cells.forEach((cell, i) => {
    const idx = plan.startIdx + i
    while (out.length <= idx) out.push({})
    Object.assign(out[idx], cell)
  })
  return out
}
