/** 保存前非阻断 lint(C10 前端半 + §4.3 死数据)。 */
import { expect, it } from 'vitest'
import { lintDraft } from '../draft-lint'

it('缺 endpoint_id 的步骤与声明未引用的变量都告警', () => {
  const warns = lintDraft({
    config: { vars: { amount: 1, dead_one: 2 } },
    steps: [
      { api: {}, request: { body: { amount: '${var.amount}' } } },  // 无 endpoint_id
      { api: { view_hints: { endpoint_id: 'x' } }, request: { body: {} } },
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
    steps: [{ api: { view_hints: { endpoint_id: 'x' }, headers: { a: '${var.amount}' } } }],
  })).toEqual([])
})
