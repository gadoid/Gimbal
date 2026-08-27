/** dataset-grid.test.ts — 转置表格派生工具(纯函数) */
import { describe, expect, it } from 'vitest'

import { deriveBaselineColumns } from '@/utils/dataset-palette'
import {
  applyPastePlan,
  cellDisplay,
  gridStats,
  groupByStepLocation,
  matchesQuery,
  parseTsvPaste,
  varOnlyPalette,
  type CellState,
} from '@/utils/dataset-grid'

const DRAFT = {
  steps: [
    {
      api: { view_hints: { endpoint_id: 'fin.order.add' } },
      request: { body: { amount: '${var.amount}', customer_id: '261', remark: '' } },
    },
    {
      // GET 风格步骤:引擎约定查询参数放 request.body(executor 映射为 params=)
      api: { view_hints: { endpoint_id: 'fin.order.query' } },
      request: { body: { page: '${var.page}', size: '20' } },
    },
  ],
  config: { vars: { amount: '100', page: '1' } },
}

const cols = deriveBaselineColumns(DRAFT as any)
const amount = cols.find((c) => c.field === 'amount' && c.kind === 'var')!
const page = cols.find((c) => c.field === 'page' && c.kind === 'var')!
const customer = cols.find((c) => c.field === 'customer_id' && c.kind === 'direct')!

describe('varOnlyPalette', () => {
  it('仅保留 var 列,顺序与原 columns 一致', () => {
    const v = varOnlyPalette(cols)
    expect(v.map((c) => c.field)).toEqual(['amount', 'page'])
    expect(v.every((c) => c.kind === 'var')).toBe(true)
  })
})

describe('groupByStepLocation', () => {
  it('按 (stepIndex, source) 分组;同组 fields 保持步骤内顺序', () => {
    const g = groupByStepLocation(cols)
    expect(g.map((x) => `${x.stepIndex}:${x.source}`)).toEqual(['0:body', '1:body'])
    expect(g[0].fields.map((f) => f.field)).toEqual(['amount', 'customer_id', 'remark'])
    expect(g[1].fields.map((f) => f.field)).toEqual(['page', 'size'])
  })
})

describe('matchesQuery', () => {
  it('空 query = 全显', () => {
    expect(matchesQuery(amount, '')).toBe(true)
    expect(matchesQuery(amount, '  ')).toBe(true)
  })
  it('按 field 名不区分大小写命中', () => {
    expect(matchesQuery(amount, 'AMO')).toBe(true)
  })
  it('按 varName 命中', () => {
    expect(matchesQuery(amount, 'amount')).toBe(true)
  })
  it('不命中', () => {
    expect(matchesQuery(amount, 'customer')).toBe(false)
  })
})

describe('cellDisplay 三态', () => {
  it('undefined → inherit(灰显基线)', () => {
    const d = cellDisplay({}, amount)
    expect(d.state).toBe<CellState>('inherit')
    expect(d.value).toBe('')
    expect(d.placeholder).toBe('100')
  })
  it('空串 → override-empty(显式覆盖)', () => {
    const d = cellDisplay({ amount: '' }, amount)
    expect(d.state).toBe<CellState>('override-empty')
    expect(d.value).toBe('')
  })
  it('非空 → override-value', () => {
    const d = cellDisplay({ amount: '200' }, amount)
    expect(d.state).toBe<CellState>('override-value')
    expect(d.value).toBe('200')
  })
  it('直填列(undefined varName)恒为 inherit', () => {
    const d = cellDisplay({ customer_id: '999' }, customer)
    // 直填列没 varName,统一视为继承(UI 不在表格里出现)
    expect(d.state).toBe<CellState>('inherit')
  })
})

describe('gridStats', () => {
  it('变量数 / 直填数 / 数据行数 / 覆盖单元格数', () => {
    const s = gridStats(cols, [
      { amount: '200', page: '' },
      { amount: '300' },
      {},
    ])
    expect(s.varCount).toBe(2)
    expect(s.directCount).toBe(3)
    expect(s.rowCount).toBe(3)
    expect(s.overrideCount).toBe(3)
  })
})

describe('parseTsvPaste + applyPastePlan', () => {
  it('单列纵向填充 3 行', () => {
    const plan = parseTsvPaste('100\n200\n300', 'amount', 0, 1)
    expect(plan.startVar).toBe('amount')
    expect(plan.startIdx).toBe(0)
    expect(plan.cells.length).toBe(3)
    expect(plan.cells).toEqual([
      { amount: '100' },
      { amount: '200' },
      { amount: '300' },
    ])
    expect(plan.needsAppend).toBe(2)  // rows 现有 1 行,粘贴到 0..2 = 3 行
  })

  it('粘贴到中间行,前面保留', () => {
    const plan = parseTsvPaste('a\nb', 'page', 2, 4)
    expect(plan.startIdx).toBe(2)
    expect(plan.cells).toEqual([{ page: 'a' }, { page: 'b' }])
    expect(plan.needsAppend).toBe(0)
  })

  it('空字符串视作显式空覆盖', () => {
    const plan = parseTsvPaste('\n\n', 'amount', 0, 0)
    expect(plan.cells).toEqual([{ amount: '' }, { amount: '' }])
  })

  it('矩形块回退为取首列(转置表当前不支持多列粘贴)', () => {
    const plan = parseTsvPaste('100\tfoo\n200\tbar', 'amount', 0, 0)
    expect(plan.cells).toEqual([{ amount: '100' }, { amount: '200' }])
  })

  it('applyPastePlan 不 mutate 原 rows', () => {
    const rows = [{ amount: 'orig' }]
    const plan = parseTsvPaste('200\n300', 'amount', 0, 1)
    const out = applyPastePlan(rows, plan)
    // 原 rows 不被 mutate
    expect(rows[0]).toEqual({ amount: 'orig' })
    expect(rows.length).toBe(1)
    // 粘贴从 idx 0 开始 2 个值 → 覆盖 row 0 + 追加 row 1
    expect(out.length).toBe(2)
    expect(out[0]).toEqual({ amount: '200' })
    expect(out[1]).toEqual({ amount: '300' })
  })
})
