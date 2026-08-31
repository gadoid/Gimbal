/**
 * deepDefaults — 新建步骤初始 body 合成(单来源)。
 *
 * 只消费 IOFieldBinding 的 default(缺省 example);契约字段(schema 有、
 * binding 无)的 schema default 不再拷贝 — 该职责已移交 carry 通道
 * (platform 值表 + materialize 注入)。
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
