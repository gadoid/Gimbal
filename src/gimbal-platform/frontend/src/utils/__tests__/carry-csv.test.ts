import { describe, expect, it } from 'vitest'
import { CarryCsvError, buildCarryTemplate, mergeCarryCsv, parseCarryCsv } from '../carry-csv'
import type { ServiceCarryRow } from '../carry-entries'

/** 标准形态:三列、path 在首列、LF、无 BOM。 */
const STD = 'path,value,is_null\n$.remark,对公备注,0\n$.action,,1\n$.notes,,0\n'

describe('parseCarryCsv — 解析(表头按名定位 + RFC4180)', () => {
  it('标准形态:is_null 1→true、0→true 之外按 false;空 value 保留空串', () => {
    const rows = parseCarryCsv(STD)
    expect(rows).toEqual([
      { path: '$.remark', value: '对公备注', isNull: false },
      { path: '$.action', value: '', isNull: true },
      { path: '$.notes', value: '', isNull: false },
    ])
  })

  it('表头按名定位:path 不在第一列(Excel 调过列序)也能解析', () => {
    const rows = parseCarryCsv('is_null,path,value\n0,$.remark,qa 备注\n')
    expect(rows).toEqual([{ path: '$.remark', value: 'qa 备注', isNull: false }])
  })

  it('Excel 导出形态:UTF-8 BOM + CRLF 兼容', () => {
    const rows = parseCarryCsv('﻿path,value,is_null\r\n$.remark,r1,0\r\n')
    expect(rows).toEqual([{ path: '$.remark', value: 'r1', isNull: false }])
  })

  it('表头列名两侧空白容忍,数据 path 亦 trim;value 不 trim(空格是值的一部分)', () => {
    const rows = parseCarryCsv(' path , value , is_null \n $.remark ,  v ,0\n')
    expect(rows).toEqual([{ path: '$.remark', value: '  v ', isNull: false }])
  })

  it('RFC4180:引号字段内嵌换行 + 转义双引号("")→(")', () => {
    const rows = parseCarryCsv(
      'path,value,is_null\n"$.remark","多行\n值""引号""",0\n',
    )
    expect(rows).toEqual([
      { path: '$.remark', value: '多行\n值"引号"', isNull: false },
    ])
  })

  it('RFC4180:引号内逗号不断列,value 含逗号原样保留', () => {
    const rows = parseCarryCsv('path,value,is_null\n$.remark,"a,b",0\n')
    expect(rows).toEqual([{ path: '$.remark', value: 'a,b', isNull: false }])
  })

  it('缺列整单拒绝:报出缺的列名', () => {
    expect(() => parseCarryCsv('path,value\n$.remark,x\n')).toThrow(CarryCsvError)
    expect(() => parseCarryCsv('path,value\n$.remark,x\n')).toThrow(/is_null/)
  })

  it('未知列整单拒绝:报出多余列名(固定格式不容错列)', () => {
    expect(() => parseCarryCsv('path,value,is_null,extra\n$.remark,x,0,y\n'))
      .toThrow(/extra/)
  })

  it('CSV 内重复 path 整单拒绝(R1-M2:dict 键折叠会静默覆盖)', () => {
    expect(() => parseCarryCsv('path,value,is_null\n$.remark,a,0\n$.remark,b,0\n'))
      .toThrow(/\$\.remark/)
  })

  it('非法 is_null(非 0/1/空)→ 报行号拒绝', () => {
    expect(() => parseCarryCsv('path,value,is_null\n$.remark,a,0\n$.notes,b,yes\n'))
      .toThrow(/2/)
  })

  it('空 path 数据行 → 报行号拒绝', () => {
    expect(() => parseCarryCsv('path,value,is_null\n,a,0\n')).toThrow(/1/)
  })

  it('字段数与表头不齐 → 报行号拒绝', () => {
    expect(() => parseCarryCsv('path,value,is_null\n$.remark\n')).toThrow(/1/)
  })

  it('尾随空行/空内容行跳过,不视为数据', () => {
    const rows = parseCarryCsv('path,value,is_null\n$.remark,a,0\n\n\n')
    expect(rows).toEqual([{ path: '$.remark', value: 'a', isNull: false }])
  })

  it('模板安全规则:value 空 + is_null 空 → 该行不导入(未填 = 无操作)', () => {
    const rows = parseCarryCsv('path,value,is_null\n$.remark,,\n$.notes,n1,\n$.action,,0\n')
    // $.remark 两空 → 丢弃;$.notes 只填 value → 导入;$.action 显式 0 + 空 value → 空串
    expect(rows).toEqual([
      { path: '$.notes', value: 'n1', isNull: false },
      { path: '$.action', value: '', isNull: false },
    ])
  })
})

describe('buildCarryTemplate — 字段面 → 模板 CSV', () => {
  const FACE = (): ServiceCarryRow[] => [
    { path: '$.remark', value: '已有值', isNull: false, hasRow: true },
    { path: '$.action', value: '', isNull: true, hasRow: true },
    { path: '$.notes', value: '', isNull: false, hasRow: true }, // 显式空串绑定
    { path: '$.cancel_remark', value: '', isNull: false, hasRow: false }, // 未绑定
  ]

  it('面全量 path 入模板:已绑定带值,null 绑定 is_null=1,空串绑定显式 0,未绑定两空', () => {
    expect(buildCarryTemplate(FACE())).toBe(
      'path,value,is_null\n'
      + '$.remark,已有值,\n'
      + '$.action,,1\n'
      + '$.notes,,0\n'
      + '$.cancel_remark,,\n',
    )
  })

  it('值含逗号/引号/换行时 RFC4180 转义', () => {
    const rows: ServiceCarryRow[] = [
      { path: '$.remark', value: 'a,b\n"c"', isNull: false, hasRow: true },
    ]
    expect(buildCarryTemplate(rows)).toBe(
      'path,value,is_null\n$.remark,"a,b\n""c""",\n',
    )
  })

  it('round-trip:模板导出 → 再导入 = 绑定态不变(未绑定行不建行)', () => {
    const face = FACE()
    const reParsed = parseCarryCsv(buildCarryTemplate(face))
    const target = FACE().map((r) => ({ ...r, value: '', isNull: false, hasRow: false }))
    mergeCarryCsv(target, reParsed)
    expect(target).toEqual(face)
  })
})

describe('mergeCarryCsv — 合并进字段面行', () => {
  /** 页面现场:面两行,一行已有绑定,一行全新。 */
  const FACE = (): ServiceCarryRow[] => [
    { path: '$.remark', value: '旧值', isNull: false, hasRow: true },
    { path: '$.notes', value: '', isNull: false, hasRow: false },
  ]

  it('命中行:值覆盖;无行导入值 = 建行(hasRow=true,对齐 B1 语义)', () => {
    const rows = FACE()
    const report = mergeCarryCsv(rows, [
      { path: '$.remark', value: '新值', isNull: false },
      { path: '$.notes', value: 'n1', isNull: false },
    ])
    expect(rows[0]).toEqual({ path: '$.remark', value: '新值', isNull: false, hasRow: true })
    expect(rows[1]).toEqual({ path: '$.notes', value: 'n1', isNull: false, hasRow: true })
    expect(report.applied).toBe(2)
    expect(report.skippedUnknown).toEqual([])
  })

  it('is_null=1 行:isNull=true 且 value 清空(对齐 toggleNull:设 null 隐含建行)', () => {
    const rows = FACE()
    mergeCarryCsv(rows, [{ path: '$.remark', value: '将被忽略', isNull: true }])
    expect(rows[0]).toEqual({ path: '$.remark', value: '', isNull: true, hasRow: true })
  })

  it('面外 path:进 skippedUnknown 报告,行不动(契约门控会滤掉)', () => {
    const rows = FACE()
    const report = mergeCarryCsv(rows, [
      { path: '$.ghost', value: 'x', isNull: false },
      { path: '$.remark', value: 'ok', isNull: false },
    ])
    expect(report.applied).toBe(1)
    expect(report.skippedUnknown).toEqual(['$.ghost'])
    expect(rows[0].value).toBe('ok')
    // 面外行不会凭空造行
    expect(rows.some((r) => r.path === '$.ghost')).toBe(false)
  })
})
