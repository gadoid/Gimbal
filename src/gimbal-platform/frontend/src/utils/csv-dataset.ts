/**
 * csv-dataset.ts — 数据集 CSV 导出 / 导入(基于 papaparse)
 *
 * 形状约定(给 Excel 用户作模板):
 *   - 第一行:列头,顺序与变量调色板一致(varOnlyPalette 的顺序)
 *   - 第二行(可选):字段描述(以 `(description)` 开头),从
 *     Plate IOFieldBinding 拉来,让 Excel 用户看到每列是什么
 *   - 下一行:基线默认值(以 `(baseline)` 开头),用户编辑时直接看到该填什么
 *   - 之后每条数据一行
 *   - inherit(未覆盖) → 写出基线值(Excel 用户看到有效值)
 *   - override-empty → 写出空字符串(显式空串覆盖)
 *   - override-value → 写出 override 值
 *
 * 导入端:从第二行开始,凡是首列以 `(` 开头的行一律视作元数据
 * (description / baseline),直到第一个不以 `(` 开头的行才是数据行。
 * 这样新增元数据行不需要改导入逻辑。
 *
 * 不导出 varName = '__case_name' 这种特殊列;data 名(旧称 case)走单独列(首列)。
 */

import Papa from 'papaparse'

import type { BaselineColumn } from './dataset-palette'
import { varOnlyPalette, cellDisplay } from './dataset-grid'
import { downloadFile } from './download'

const CASE_NAME_COL = '__case_name'

export interface CsvExportInput {
  datasetName: string
  columns: BaselineColumn[]  // 全部(含 direct);内部按 varOnlyPalette 取
  rows: Array<Record<string, string>>
  /** 后端协议字段名(case-prefix 出于历史协议);UI 层对应 data 名(默认 `data-N`)。
   *  与 rows 等长;不传则用 `data-N` 占位。 */
  caseNames?: string[]
  /** 与 varOnlyPalette 同序的字段描述(从 IOFieldBinding.description)。
   *  不传或全空数组 → 不写 description 行。 */
  descriptions?: string[]
}

/** 构造 CSV 文本(不下载)。便于测试。 */
export function buildDataSetCsv(input: CsvExportInput): string {
  const vars = varOnlyPalette(input.columns)
  // 列头 = data 名 + 变量名(CSV wire header 用 __case_name,与 UI data-N 是两套层)
  const header = [CASE_NAME_COL, ...vars.map((v) => v.varName)]
  // 元数据行:description(可选) + baseline(必有),顺序固定
  const metaRows: string[][] = []
  if (input.descriptions && input.descriptions.length === vars.length) {
    metaRows.push(['(description)', ...input.descriptions])
  }
  metaRows.push(['(baseline)', ...vars.map((v) => v.baseline)])
  // 数据行。inherit 状态写出基线值(给 Excel 用户看有效值),
  // override-empty 写出空字符串(让 Excel 看到「被清空了」),
  // override-value 写出 override 值。
  const dataRows = input.rows.map((row, i) => {
    const name = input.caseNames?.[i] ?? `data-${i + 1}`
    const cells = vars.map((v) => {
      const d = cellDisplay(row, v)
      if (d.state === 'inherit') return v.baseline
      return d.value
    })
    return [name, ...cells]
  })
  return Papa.unparse([header, ...metaRows, ...dataRows], { newline: '\n' })
}

/** 下载 CSV(浏览器环境)。
 *  加 UTF-8 BOM(﻿)— Excel for Windows 中文版默认按 GBK 解析 CSV,
 *  没有 BOM 时 description 列的中文会乱码。BOM 让 Excel 自动识别 UTF-8。 */
export function exportDataSetCsv(input: CsvExportInput): void {
  const csv = buildDataSetCsv(input)
  const fname = `${input.datasetName || 'dataset'}.csv`
  downloadFile(fname, BOM + csv, 'text/csv')
}

/** UTF-8 BOM 字面量(EF BB BF)— Excel 识别 UTF-8 CSV 的标志。
 *  用 ﻿ 转义而非字面 U+FEFF:避免编辑器 / 工具链把不可见字符吞掉。 */
const BOM = '﻿'

export interface CsvImportInput {
  fileText: string
  columns: BaselineColumn[]   // 用于校验 key ⊆ palette
  caseNames?: string[]        // 已存在的 data 名(用于「按名匹配替换」策略)
  mode: 'replace' | 'append' | 'merge-by-name'
  rows: Array<Record<string, string>>
}

export interface CsvImportResult {
  rows: Array<Record<string, string>>
  caseNames: string[]
  /** 解析 / 校验错误。空数组 = 成功。 */
  errors: string[]
}

/** 解析 CSV → 行。CSV 形状:
 *   row 0: header(列名;首列应为 `__case_name`)
 *   row 1..N: 任意数量的元数据行(首列以 `(` 开头,如 `(description)` /
 *             `(baseline)`)— 一律跳过
 *   row N+1 起: data rows
 *
 * 与基线行比较:导出时 inherit 已被写出基线值,所以导入时如果某格等于
 * 基线值且 row 中本无该键,需要"删 key";否则视为显式 override。
 * 这个反向推断比较微妙,所以我们用一个简单规则:
 *   - 该列对应的 BaselineColumn.baseline = B;某格 value == B(且 row
 *     之前没这个 key)→ 不写 key(继承语义)。
 *   - 某格 value != B → 显式写 key(覆盖)。
 *   - 某格 value == '' → 显式写 key = '' (覆盖为空)。
 */
export function importDataSetCsv(input: CsvImportInput): CsvImportResult {
  const errors: string[] = []
  // 兼容 Excel 导出的带 BOM 文件 — 剥掉首字符 BOM,避免 header 首列变成 "﻿__case_name"
  const fileText = input.fileText.startsWith(BOM)
    ? input.fileText.slice(BOM.length)
    : input.fileText
  const parsed = Papa.parse<string[]>(fileText, {
    skipEmptyLines: true,
  })
  if (parsed.errors.length) {
    parsed.errors.forEach((e) => errors.push(`CSV 解析: ${e.message}`))
  }
  const data = parsed.data
  if (data.length < 1) {
    return { rows: [], caseNames: [], errors: ['CSV 为空'] }
  }
  // 第一行 = header
  const headerRow = data[0]
  const headerCols = headerRow.slice(1) // 跳过 __case_name
  // 跳过所有元数据行(description / baseline 等;首列以 `(` 开头)
  // 任意多个;先记录 baseline 行(若有)的值,后面反向推断 inherit 用。
  let baselineValues: string[] = []
  let dataStartIdx = 1
  while (dataStartIdx < data.length) {
    const first = (data[dataStartIdx][0] ?? '').trim()
    if (first === '(baseline)') {
      baselineValues = data[dataStartIdx].slice(1)
      dataStartIdx++
      continue
    }
    if (first.startsWith('(')) {
      // 其他元数据行(description 等)— 跳过,不参与 baseline 反推
      dataStartIdx++
      continue
    }
    break
  }

  // 校验 header keys ⊆ palette
  const palette = varOnlyPalette(input.columns)
  const paletteByVar = new Map(palette.map((c) => [c.varName!, c]))
  for (const name of headerCols) {
    if (!paletteByVar.has(name)) {
      errors.push(`未知列: ${name}(不在场景变量调色板中)`)
    }
  }

  // 解析数据行
  const parsedRows: Array<{ name: string; row: Record<string, string> }> = []
  for (let i = dataStartIdx; i < data.length; i++) {
    const r = data[i]
    const name = (r[0] ?? '').trim() || `data-${i + 1}`
    const row: Record<string, string> = {}
    for (let j = 0; j < headerCols.length; j++) {
      const colName = headerCols[j]
      // 跳过未知列(已在上面 errors 记录);仍保留有效列
      if (!paletteByVar.has(colName)) continue
      const baseline = baselineValues[j] ?? ''
      const raw = r[j + 1] ?? ''
      // 若值 == 基线值 → 不写 key(继承);否则写 key(覆盖)
      if (raw !== baseline) row[colName] = raw
    }
    parsedRows.push({ name, row })
  }

  // 按 mode 合并
  let outRows = input.rows.slice()
  // caseNames 缺失时按 rows 长度补 data-N 占位 — 不传 caseNames 是合法用法
  const baseCaseNames = input.caseNames ?? input.rows.map((_, i) => `data-${i + 1}`)
  let outCaseNames = baseCaseNames.slice()
  if (input.mode === 'replace') {
    outRows = parsedRows.map((p) => p.row)
    outCaseNames = parsedRows.map((p) => p.name)
  } else if (input.mode === 'append') {
    parsedRows.forEach((p) => {
      outRows.push(p.row)
      outCaseNames.push(p.name)
    })
  } else {
    // merge-by-name
    const byName = new Map<string, number>()
    outCaseNames.forEach((n, i) => byName.set(n, i))
    parsedRows.forEach((p) => {
      const idx = byName.get(p.name)
      if (idx !== undefined) {
        outRows[idx] = p.row
      } else {
        outRows.push(p.row)
        outCaseNames.push(p.name)
        byName.set(p.name, outRows.length - 1)
      }
    })
  }

  return { rows: outRows, caseNames: outCaseNames, errors }
}