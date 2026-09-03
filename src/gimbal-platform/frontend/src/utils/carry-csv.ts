/**
 * carry-csv.ts — CarryConfig 两 tab 共用的 CSV 纯核心:
 * 解析 + 模板/导出编码 + 合并(服务绑定 face 门控 / 全局默认 upsert)。
 *
 * 固定格式:首行表头按名定位(列序任意),列集必须恰为
 * path / value / is_null;数据行 path 必须命中字段面,面外行跳过并报告
 * (契约门控会滤掉未声明字段,导了也不注入)。
 *
 * 三态对齐 carry-entries:is_null=1 → 显式 JSON null(spec §3.1);
 * 空 value + is_null=0 → 合法空串值;path 缺席于 CSV = 不动该行。
 * 行号一律指数据行(表头后第 N 行)。纯函数:单测不挂 Vue(模式同 carry-entries.ts)。
 */
import type { ServiceCarryRow } from './carry-entries'

/** 解析后的 CSV 数据行(value 恒为字符串,类型转换在注入时宽松进行)。 */
export interface ParsedCsvRow {
  path: string
  value: string
  isNull: boolean
}

/** 合并报告:applied = 命中面并写入的行数;skippedUnknown = 面外 path 清单。 */
export interface CsvMergeReport {
  applied: number
  skippedUnknown: string[]
}

/** 格式违规(缺列/多列/重复 path/非法 is_null/字段数不齐等),整单拒绝。 */
export class CarryCsvError extends Error {}

const REQUIRED_COLUMNS = ['path', 'value', 'is_null'] as const

/** RFC4180 分词:引号内逗号/换行是数据,"" 转义为 ";记录分隔 = 引号外换行。 */
function splitRecords(text: string): string[][] {
  const records: string[][] = []
  let record: string[] = []
  let field = ''
  let inQuotes = false
  let i = 0
  const endRecord = () => {
    record.push(field)
    records.push(record)
    record = []
    field = ''
  }
  while (i < text.length) {
    const ch = text[i]
    if (inQuotes) {
      if (ch === '"') {
        if (text[i + 1] === '"') {
          field += '"'
          i += 2
        } else {
          inQuotes = false
          i += 1
        }
      } else {
        field += ch
        i += 1
      }
      continue
    }
    if (ch === '"') {
      inQuotes = true
      i += 1
      continue
    }
    if (ch === ',') {
      record.push(field)
      field = ''
      i += 1
      continue
    }
    if (ch === '\n' || ch === '\r') {
      if (ch === '\r' && text[i + 1] === '\n') i += 1
      endRecord()
      i += 1
      continue
    }
    field += ch
    i += 1
  }
  if (field !== '' || record.length > 0) endRecord()
  return records
}

export function parseCarryCsv(text: string): ParsedCsvRow[] {
  const records = splitRecords(text.replace(/^﻿/, ''))
  if (records.length === 0) {
    throw new CarryCsvError('CSV 为空:缺表头(需 path/value/is_null)')
  }
  const header = records[0].map((h) => h.trim())
  const missing = REQUIRED_COLUMNS.filter((c) => !header.includes(c))
  if (missing.length > 0) {
    throw new CarryCsvError(`表头缺少列: ${missing.join(', ')}(需恰为 path/value/is_null)`)
  }
  const extra = header.filter((h) => !REQUIRED_COLUMNS.includes(h as (typeof REQUIRED_COLUMNS)[number]))
  if (extra.length > 0) {
    throw new CarryCsvError(`表头存在未知列: ${extra.join(', ')}(固定格式不容错列)`)
  }
  const pathIdx = header.indexOf('path')
  const valueIdx = header.indexOf('value')
  const nullIdx = header.indexOf('is_null')

  const out: ParsedCsvRow[] = []
  const seen = new Set<string>()
  for (let ri = 1; ri < records.length; ri++) {
    const rec = records[ri]
    if (rec.length === 1 && rec[0] === '') continue // 空行
    if (rec.length !== header.length) {
      throw new CarryCsvError(
        `第 ${ri} 数据行字段数 ${rec.length} ≠ 表头 ${header.length}`,
      )
    }
    const path = rec[pathIdx].trim()
    if (!path) {
      throw new CarryCsvError(`第 ${ri} 数据行 path 为空`)
    }
    const rawNull = rec[nullIdx].trim()
    let isNull = false
    if (rawNull === '1') {
      isNull = true
    } else if (rawNull !== '' && rawNull !== '0') {
      throw new CarryCsvError(
        `第 ${ri} 数据行 is_null 非法: ${rawNull}(仅 0/1/空)`,
      )
    }
    const value = rec[valueIdx]
    // 模板安全规则:两空 = 未填 = 无操作(不建行)。显式空串走 is_null=0。
    // 没有这条,预填全字段面的模板会把未填行整批导成空串绑定。
    if (value === '' && rawNull === '') continue
    if (seen.has(path)) {
      throw new CarryCsvError(`重复 path: ${path}(第 ${ri} 数据行;dict 键折叠会静默覆盖)`)
    }
    seen.add(path)
    out.push({ path, value, isNull })
  }
  return out
}

/** RFC4180 导出转义:含逗号/引号/换行的字段加引号,内嵌引号翻倍。 */
function escapeField(v: string): string {
  return /[",\r\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v
}

/**
 * 字段面 → 模板 CSV:全量 path 预填,值列按当前绑定态编码 ——
 * 已绑定带值(手填者只动 value 列,is_null 留空)/ null 绑定 is_null=1 /
 * 空串绑定显式 is_null=0(与"未填"区分,保住显式空串的 round-trip)/
 * 未绑定两空(导入时按无操作丢弃)。导出→不改→再导入 = 绑定态不变。
 */
export function buildCarryTemplate(rows: readonly ServiceCarryRow[]): string {
  const lines = ['path,value,is_null']
  for (const r of rows) {
    const value = r.hasRow && !r.isNull ? r.value : ''
    const isNull = r.isNull ? '1' : r.hasRow && r.value === '' ? '0' : ''
    lines.push(`${escapeField(r.path)},${escapeField(value)},${isNull}`)
  }
  return `${lines.join('\n')}\n`
}

export function mergeCarryCsv(
  rows: readonly ServiceCarryRow[],
  parsed: readonly ParsedCsvRow[],
): CsvMergeReport {
  const byPath = new Map(rows.map((r) => [r.path, r]))
  let applied = 0
  const skippedUnknown: string[] = []
  for (const p of parsed) {
    const row = byPath.get(p.path)
    if (!row) {
      // 面外:契约门控会滤掉未声明字段,导入无意义 → 报告而非静默造行
      skippedUnknown.push(p.path)
      continue
    }
    if (p.isNull) {
      row.isNull = true
      row.value = '' // 对齐 toggleNull:设 null 时值列失焦清空
    } else {
      row.isNull = false
      row.value = p.value
    }
    row.hasRow = true // 导入值即建行(对齐 buildServiceEntries 的 B1 语义)
    applied += 1
  }
  return { applied, skippedUnknown }
}

// ── 全局默认 tab(同一三列格式;无字段面概念 — 纯 path 跨服务)──────

/** 全局默认编辑行(CarryConfig defaults tab):行存在即配置,无 hasRow 态。 */
export interface DefaultCarryRow {
  path: string
  value: string
  isNull: boolean
}

/** 默认导入合并报告:updated = 更新已有 path 的行数;added = 追加新行数。 */
export interface DefaultsMergeReport {
  updated: number
  added: number
}

/** 服务绑定导出:仅已绑定行(hasRow),编码复用 buildCarryTemplate
 *  (null=1 / 显式空串=0)。导出→不改→导回 = 绑定态不变;未绑定面
 *  字段不进文件 —— 模板才是全 face 编辑形态,导出是纯绑定数据。 */
export function buildBoundCsv(rows: readonly ServiceCarryRow[]): string {
  return buildCarryTemplate(rows.filter((r) => r.hasRow))
}

/** 全局默认导出:当前默认行 → 三列 CSV。空白 path 行(加了行没填)
 *  跳过不导出,对齐 saveDefaults 的落库语义。 */
export function buildDefaultsCsv(rows: readonly DefaultCarryRow[]): string {
  const lines = ['path,value,is_null']
  for (const r of rows) {
    if (!r.path) continue
    const value = r.isNull ? '' : r.value
    const isNull = r.isNull ? '1' : r.value === '' ? '0' : ''
    lines.push(`${escapeField(r.path)},${escapeField(value)},${isNull}`)
  }
  return `${lines.join('\n')}\n`
}

/** 全局默认模板:表头 + 一行示例。示例值列两空 = 导入无操作,
 *  模板原样导回不会误建默认(与服务 tab 模板同一条安全规则)。 */
export function buildDefaultsTemplateCsv(): string {
  return 'path,value,is_null\n$.headers.X-Trace-Id,,\n'
}

/** 全局默认导入 upsert:已有 path 更新值/null 态,新 path 追加行。
 *  任何 path 都合法(无 face 门控);CSV 不删行(缺席 = 不动),
 *  删除留在表格 UI。表内空白 path 行不参与匹配(path 不会撞空)。 */
export function mergeDefaultsCsv(
  rows: DefaultCarryRow[],
  parsed: readonly ParsedCsvRow[],
): DefaultsMergeReport {
  const byPath = new Map(
    rows.filter((r) => r.path).map((r) => [r.path, r] as const),
  )
  let updated = 0
  let added = 0
  for (const p of parsed) {
    const row = byPath.get(p.path)
    if (row) {
      row.isNull = p.isNull
      row.value = p.isNull ? '' : p.value
      updated += 1
    } else {
      const newRow: DefaultCarryRow = {
        path: p.path,
        value: p.isNull ? '' : p.value,
        isNull: p.isNull,
      }
      rows.push(newRow)
      byPath.set(p.path, newRow)
      added += 1
    }
  }
  return { updated, added }
}
