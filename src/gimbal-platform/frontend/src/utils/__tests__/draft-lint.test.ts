/** 保存前非阻断 lint(C10 前端半 + §4.3 死数据)。 */
import { expect, it } from 'vitest'
import { lintDraft } from '../draft-lint'

it('缺 endpoint_id 的步骤与声明未引用的变量都告警', () => {
  const warns = lintDraft({
    config: { vars: { amount: 1, dead_one: 2 } },
    steps: [
      { call: {}, request: { body: { amount: '${var.amount}' } } },  // 无 endpoint_id
      { endpoint: 'x',
        call: {}, request: { body: {} } },
    ],
  })
  expect(warns).toEqual([
    '步骤 1 未绑定接口目录(endpoint_id 缺失,不进反向索引)',
    '共享变量 dead_one 声明了但未被引用(死数据)',
  ])
})

it('干净草稿零告警', () => {
  expect(lintDraft({
    config: { vars: { amount: 1 } },
    steps: [{ endpoint: 'x', call: { headers: { a: '${var.amount}' } } }],
  })).toEqual([])
})

it('D6 豁免:预填种下的变量不报死数据;未豁免照报', () => {
  const warns = lintDraft(
    { config: { vars: { pre_a: 1, pre_b: 2, mine: 3 } },
      steps: [{ endpoint: 'x', call: {} }] },
    { exemptVars: ['pre_a', 'pre_b'] })
  expect(warns).toEqual(['共享变量 mine 声明了但未被引用(死数据)'])
})

it('D6 豁免不吞 endpoint 告警;已接线变量本就无死数据', () => {
  const warns = lintDraft(
    { config: { vars: { pre_a: 1 } },
      steps: [{ call: {}, request: { body: { k: '${var.pre_a}' } } }] },
    { exemptVars: ['pre_a'] })
  expect(warns).toEqual(['步骤 1 未绑定接口目录(endpoint_id 缺失,不进反向索引)'])
})
