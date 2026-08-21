/** 列调色板/行 0 投影(spec §4):与后端 parse_refs 同一 traversal 规则。 */
import { describe, expect, it } from 'vitest'
import {
  deriveBaselineColumns, renderTemplate, rowFromBaseline,
  scalarVarNames, varNameOf,
} from '../dataset-palette'

const DEF = {
  config: { vars: { amount: 100, qty: 2, engine: { kind: 'seq' }, 'fin.customer_id': '261' } },
  steps: [{
    api: {
      view_hints: { endpoint_id: 'fin.order.add' },
      headers: { 'X-Token': '${var.tok}' },
      query: { page: 1 },
    },
    request: { body: {
      customer_id: '261',             // 直填
      amount: '${var.amount}',        // 整串模板
      mix: 'p-${var.amount}-s',       // 内嵌模板
    } },
  }, {
    api: { headers: {} }, request: { body: { x: '1' } },  // 无 endpoint_id → 不进投影
  }],
}

it('varNameOf:第一个 ${var.NAME};非串/无匹配 null;名字可含点', () => {
  expect(varNameOf('${var.amount}')).toBe('amount')
  expect(varNameOf('p-${var.fin.amount}-s')).toBe('fin.amount')
  expect(varNameOf(5)).toBeNull()
  expect(varNameOf('plain')).toBeNull()
})

it('renderTemplate:按 vars 渲染默认值,缺省空串', () => {
  expect(renderTemplate('p-${var.amount}-s', { amount: 100 })).toBe('p-100-s')
  expect(renderTemplate('${var.missing}', {})).toBe('')
})

it('deriveBaselineColumns:var/direct 两组列 + 行 0 基线;跳过无 endpoint_id 步骤', () => {
  const cols = deriveBaselineColumns(DEF)
  expect(cols.map((c) => [c.source, c.field, c.kind, c.varName])).toEqual([
    ['body', 'customer_id', 'direct', null],
    ['body', 'amount', 'var', 'amount'],
    ['body', 'mix', 'var', 'amount'],
    ['headers', 'X-Token', 'var', 'tok'],
    ['query', 'page', 'direct', null],
  ])
  expect(cols[0].baseline).toBe('261')   // 直填:字面值
  expect(cols[1].baseline).toBe('100')   // 模板:按 vars 渲染
})

it('rowFromBaseline:仅变量列,取行 0 渲染默认值(从基线提取首行)', () => {
  expect(rowFromBaseline(deriveBaselineColumns(DEF))).toEqual({ amount: '100', tok: '' })
})

it('scalarVarNames:标量键进调色板,结构化声明剔除(镜像后端 _scalar_vars)', () => {
  expect(scalarVarNames(DEF.config.vars)).toEqual(['amount', 'qty', 'fin.customer_id'])
})

it('rowFromBaseline 顺序无关:整串模板列在后仍定义基线(结构性优先)', () => {
  const def = {
    config: { vars: { amount: 100 } },
    steps: [{
      api: { view_hints: { endpoint_id: 'fin.order.add' }, headers: {}, query: {} },
      request: { body: { mix: 'p-${var.amount}-s', amount: '${var.amount}' } },
    }],
  }
  expect(rowFromBaseline(deriveBaselineColumns(def))).toEqual({ amount: '100' })
})

it('rowFromBaseline Pass 2:仅内嵌模板引用的变量整行省略(D10 稀疏行)', () => {
  const def = {
    config: { vars: { tag: 'T1' } },
    steps: [{
      api: { view_hints: { endpoint_id: 'fin.order.add' }, headers: {}, query: {} },
      request: { body: { note: 'n-${var.tag}-s' } },
    }],
  }
  expect(rowFromBaseline(deriveBaselineColumns(def))).toEqual({})
})
