/** csv-dataset.test.ts — CSV 导出 / 导入(papaparse) */
import { describe, expect, it, vi } from 'vitest'

import { deriveBaselineColumns } from '@/utils/dataset-palette'
import { buildDataSetCsv, exportDataSetCsv, importDataSetCsv } from '@/utils/csv-dataset'
import * as downloadMod from '@/utils/download'

const DRAFT = {
  steps: [{
    api: { view_hints: { endpoint_id: 'fin.order.add' } },
    request: { body: { amount: '${var.amount}', customer_id: '261' } },
  }],
  config: { vars: { amount: '100' } },
}

const cols = deriveBaselineColumns(DRAFT as any)

describe('buildDataSetCsv', () => {
  it('header + baseline + N 数据行', () => {
    const csv = buildDataSetCsv({
      datasetName: 'edge',
      columns: cols,
      rows: [{ amount: '200' }, { amount: '999' }, {}],
      caseNames: ['edge-min', 'edge-max', 'inherit'],
    })
    const lines = csv.split('\n')
    expect(lines[0]).toBe('__case_name,amount')
    expect(lines[1]).toBe('(baseline),100')
    expect(lines[2]).toBe('edge-min,200')
    expect(lines[3]).toBe('edge-max,999')
    expect(lines[4]).toBe('inherit,100')  // inherit → 写出基线值
  })

  it('descriptions 数组存在且长度匹配 → 写 (description) 行在 (baseline) 之前', () => {
    const csv = buildDataSetCsv({
      datasetName: 'with-desc',
      columns: cols,
      rows: [{ amount: '200' }],
      caseNames: ['a'],
      descriptions: ['订单金额(分)'],
    })
    const lines = csv.split('\n')
    expect(lines[0]).toBe('__case_name,amount')
    expect(lines[1]).toBe('(description),订单金额(分)')
    expect(lines[2]).toBe('(baseline),100')
    expect(lines[3]).toBe('a,200')
  })

  it('descriptions 长度与 var 列数不一致 → 跳过 description 行(兜底)', () => {
    const csv = buildDataSetCsv({
      datasetName: 'mismatch',
      columns: cols,
      rows: [{ amount: '200' }],
      caseNames: ['a'],
      descriptions: ['a', 'b'],  // 列数 2 但实际 var 只有 1
    })
    const lines = csv.split('\n')
    expect(lines[0]).toBe('__case_name,amount')
    expect(lines[1]).toBe('(baseline),100')  // 没有 (description) 行
    expect(lines[2]).toBe('a,200')
  })

  it('override-empty 写出空字符串', () => {
    const csv = buildDataSetCsv({
      datasetName: 'empty',
      columns: cols,
      rows: [{ amount: '' }],
      caseNames: ['force-empty'],
    })
    expect(csv.split('\n')[1]).toBe('(baseline),100')
    expect(csv.split('\n')[2]).toBe('force-empty,')
  })

  it('无变量列时只有 header + baseline + data 列', () => {
    const csv = buildDataSetCsv({
      datasetName: 'no-vars',
      columns: [],   // 不可能但兜底
      rows: [],
    })
    expect(csv.split('\n')[0]).toBe('__case_name')
  })
})

describe('importDataSetCsv', () => {
  it('replace:全量替换 rows + caseNames', () => {
    const r = importDataSetCsv({
      fileText: '__case_name,amount\n(baseline),100\nfoo,200\nbar,999\n',
      columns: cols,
      rows: [{ amount: 'old' }],
      caseNames: ['old'],
      mode: 'replace',
    })
    expect(r.errors).toEqual([])
    expect(r.caseNames).toEqual(['foo', 'bar'])
    expect(r.rows).toEqual([{ amount: '200' }, { amount: '999' }])
  })

  it('merge-by-name:按 caseName 匹配替换,未匹配追加', () => {
    const r = importDataSetCsv({
      fileText: '__case_name,amount\n(baseline),100\nfoo,200\nnew,999\n',
      columns: cols,
      rows: [{ amount: 'old1' }, { amount: 'old2' }],
      caseNames: ['foo', 'other'],
      mode: 'merge-by-name',
    })
    expect(r.caseNames).toEqual(['foo', 'other', 'new'])
    expect(r.rows[0]).toEqual({ amount: '200' })  // foo 替换
    expect(r.rows[1]).toEqual({ amount: 'old2' })  // other 保留
    expect(r.rows[2]).toEqual({ amount: '999' })  // new 追加
  })

  it('append:全量追加', () => {
    const r = importDataSetCsv({
      fileText: '__case_name,amount\n(baseline),100\nx,1\n',
      columns: cols,
      rows: [{ amount: 'old' }],
      caseNames: ['a'],
      mode: 'append',
    })
    expect(r.rows).toEqual([{ amount: 'old' }, { amount: '1' }])
    expect(r.caseNames).toEqual(['a', 'x'])
  })

  it('值等于基线时不写 key(继承语义反向推断)', () => {
    const r = importDataSetCsv({
      fileText: '__case_name,amount\n(baseline),100\nfoo,100\n',
      columns: cols,
      rows: [],
      caseNames: [],
      mode: 'replace',
    })
    expect(r.rows[0]).toEqual({})  // 等于基线 → 不写 amount key
  })

  it('空字符串视作显式覆盖(override-empty)', () => {
    const r = importDataSetCsv({
      fileText: '__case_name,amount\n(baseline),100\nfoo,\n',
      columns: cols,
      rows: [],
      caseNames: [],
      mode: 'replace',
    })
    expect(r.rows[0]).toEqual({ amount: '' })
  })

  it('未知列 → errors 中包含错误信息,rows 仍尽量返回', () => {
    const r = importDataSetCsv({
      fileText: '__case_name,amount,unknown_field\n(baseline),100,xxx\nfoo,200,yyy\n',
      columns: cols,
      rows: [],
      caseNames: [],
      mode: 'replace',
    })
    expect(r.errors.some((e) => e.includes('未知列'))).toBe(true)
    // 仍然保留有效列
    expect(r.rows[0]).toEqual({ amount: '200' })
  })

  it('空 CSV → errors 提示', () => {
    const r = importDataSetCsv({
      fileText: '',
      columns: cols,
      rows: [],
      caseNames: [],
      mode: 'replace',
    })
    expect(r.errors.length).toBeGreaterThan(0)
  })

  it('baseline 行缺失时不报错,把 header 行下方当作 baseline 检查跳过', () => {
    const r = importDataSetCsv({
      fileText: '__case_name,amount\nfoo,200\n',
      columns: cols,
      rows: [],
      caseNames: [],
      mode: 'replace',
    })
    expect(r.errors).toEqual([])
    expect(r.rows[0]).toEqual({ amount: '200' })
  })

  it('(description) 行存在时也能正确跳过,baseline 行生效', () => {
    const r = importDataSetCsv({
      fileText:
        '__case_name,amount\n(description),订单金额(分)\n(baseline),100\nfoo,200\n',
      columns: cols,
      rows: [],
      caseNames: [],
      mode: 'replace',
    })
    expect(r.errors).toEqual([])
    expect(r.rows[0]).toEqual({ amount: '200' })  // 200 ≠ 100 → override
  })

  it('只有 (description) 无 (baseline) → 跳过 description 行,后面直接当数据', () => {
    const r = importDataSetCsv({
      fileText: '__case_name,amount\n(description),订单金额(分)\nfoo,200\n',
      columns: cols,
      rows: [],
      caseNames: [],
      mode: 'replace',
    })
    expect(r.errors).toEqual([])
    // 没有 baseline 行 → baselineValues 为空 → 所有非空格都视作 override
    expect(r.rows[0]).toEqual({ amount: '200' })
  })

  it('(description) 行位置可任意(只要首列以 `(` 开头就被视作元数据)', () => {
    const r = importDataSetCsv({
      fileText:
        '__case_name,amount\n(baseline),100\n(description),订单金额\nfoo,200\n',
      columns: cols,
      rows: [],
      caseNames: [],
      mode: 'replace',
    })
    expect(r.errors).toEqual([])
    expect(r.rows[0]).toEqual({ amount: '200' })
  })
})

// ── UTF-8 BOM ──────────────────────────────────────────────

describe('UTF-8 BOM(Excel 兼容)', () => {
  it('exportDataSetCsv 输出带 BOM 前缀(Excel 中文版识别用)', () => {
    // mock downloadFile 抓取传给它的字符串(第 2 个参数 = content)
    const spy = vi.spyOn(downloadMod, 'downloadFile').mockImplementation(() => {})
    exportDataSetCsv({
      datasetName: 'edge',
      columns: cols,
      rows: [{ amount: '200' }],
      caseNames: ['a'],
    })
    expect(spy).toHaveBeenCalled()
    const content = spy.mock.calls[0][1] as string
    // 必须以 U+FEFF 开头(让 Excel for Windows 中文版识别 UTF-8)
    expect(content.charCodeAt(0)).toBe(0xFEFF)
    // BOM 后面是真 CSV(header 行)
    expect(content.slice(1).split('\n')[0]).toBe('__case_name,amount')
  })

  it('buildDataSetCsv(纯字符串工具)不带 BOM — BOM 只加在下载时', () => {
    const csv = buildDataSetCsv({
      datasetName: 'x',
      columns: cols,
      rows: [{ amount: '200' }],
      caseNames: ['a'],
    })
    expect(csv.charCodeAt(0)).not.toBe(0xFEFF)
  })

  it('exportDataSetCsv(description 行中文 + BOM)— Excel 能正常显示', () => {
    const spy = vi.spyOn(downloadMod, 'downloadFile').mockImplementation(() => {})
    exportDataSetCsv({
      datasetName: 'edge',
      columns: cols,
      rows: [{ amount: '200' }],
      caseNames: ['a'],
      descriptions: ['订单金额(分)'],
    })
    const content = spy.mock.calls[0][1] as string
    // 中文应在 description 行(第二行)
    const lines = content.slice(1).split('\n')  // 剥 BOM
    expect(lines[1]).toBe('(description),订单金额(分)')
  })

  it('importDataSetCsv 兼容带 BOM 的文件(Excel 导出场景)— 不当成元数据', () => {
    const r = importDataSetCsv({
      fileText: '﻿__case_name,amount\n(baseline),100\nfoo,200\n',
      columns: cols,
      rows: [],
      caseNames: [],
      mode: 'replace',
    })
    // header 首列应是 __case_name,不是 BOM 前缀污染的 "﻿__case_name"
    expect(r.errors).toEqual([])
    expect(r.caseNames).toEqual(['foo'])
    expect(r.rows[0]).toEqual({ amount: '200' })
  })
})
