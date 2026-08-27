/** 列调色板/行 0 投影(spec §4):与后端 parse_refs 同一 traversal 规则。 */
import { expect, it } from 'vitest'
import {
  deriveBaselineColumns, renderTemplate, varNameOf,
} from '../dataset-palette'

const DEF = {
  config: { vars: { amount: 100, qty: 2, engine: { kind: 'seq' }, 'fin.customer_id': '261' } },
  steps: [{
    api: {
      view_hints: { endpoint_id: 'fin.order.add' },
      headers: { 'X-Token': '${var.tok}' },
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
  ])
  expect(cols[0].baseline).toBe('261')   // 直填:字面值
  expect(cols[1].baseline).toBe('100')   // 模板:按 vars 渲染
})

// 注:rowFromBaseline / scalarVarNames 已删(死代码 — 计划过但产品入口未触发,
// DataSetEditor / csv-dataset 均无调用方)。
