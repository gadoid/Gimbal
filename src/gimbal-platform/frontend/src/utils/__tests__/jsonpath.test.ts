/**
 * deepDefaults — 新建步骤初始 body 合成。
 *
 * 两个来源:① IOFieldBinding 的 default(缺省 example);② plate 契约字段
 * (schema 有、binding 无)的 schema default — 配了默认值才进 body 随请求
 * 发送,没配不造空值。
 */
import { describe, it, expect } from 'vitest'
import { deepDefaults } from '@/utils/jsonpath'

describe('deepDefaults — 绑定字段(既有行为)', () => {
  it('default 优先于 example;都缺省跳过', () => {
    const body = deepDefaults([
      { path: '$.a', default: 1, example: 9 },
      { path: '$.b', default: null, example: 'ex' },
      { path: '$.c', default: null, example: null },
    ])
    expect(body).toEqual({ a: 1, b: 'ex' })
  })

  it('嵌套路径按段写入', () => {
    const body = deepDefaults([{ path: '$.cfg.timeout', default: 30, example: null }])
    expect(body).toEqual({ cfg: { timeout: 30 } })
  })
})

describe('deepDefaults — 契约字段默认值(plate schema 非绑定)', () => {
  it('配了 default 的契约字段写入 body(默认随请求发送)', () => {
    const body = deepDefaults(
      [{ path: '$.order_id', default: 'ord-1', example: null }],
      [{ name: 'risk_note', default: '正常' }],
    )
    expect(body).toEqual({ order_id: 'ord-1', risk_note: '正常' })
  })

  it('没配 default 的契约字段不写入(不造空值)', () => {
    const body = deepDefaults(
      [{ path: '$.order_id', default: 'ord-1', example: null }],
      [{ name: 'risk_note' }, { name: 'flag', default: null }],
    )
    expect(body).toEqual({ order_id: 'ord-1' })
  })

  it('与绑定根段同名 → 绑定已写的值优先', () => {
    const body = deepDefaults(
      [{ path: '$.note', default: 'from-binding', example: null }],
      [{ name: 'note', default: 'from-schema' }],
    )
    expect(body).toEqual({ note: 'from-binding' })
  })
})
